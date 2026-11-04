"""Paired local-model experiment. Labels are never supplied to planner/reviewer."""
import hashlib
import json
import statistics
import time
import uuid

import httpx

from .canvas import ScreenDraft,ScreenStore,compile_screen
from .store import ROOT


def run():
    source=ROOT/'data/semantic_review_cases.json'
    cases=json.loads(source.read_text())
    output=ROOT/'reports/semantic-review-v2.json'
    store=ScreenStore(ROOT/'var/rag.screens.db')
    report={'scope':cases['limits'],'dataset_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'protocol':'Paired off/repair, greedy Qwen3-4B-4bit; fixture previous screens, no labels in inference. V2 adds history/capability-specific critic grammar after partial v1 format failures. Same-model critique is fallible. All outcomes retained.',
            'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ('rag_backend/canvas.py','rag_backend/semantic_review.py','rag_backend/research_models.py')},
            'models':{role:json.loads((ROOT/'var/research_models'/role/'manifest.local.json').read_text()) for role in ('canvas_generator','reranker')},
            'results':[]}
    def fixture(case):
        if not case['previous_roots']:return {}
        nodes,_=compile_screen(ScreenDraft(title='기존 화면',widgets=[{'type':k,'priority':1} for k in case['previous_roots']],clarification=''))
        sid=str(uuid.uuid4())
        store.commit(sid,0,{'greeting':'기존 화면','widgets':nodes,'context':{},'revision':1,'session_id':sid})
        return {'session_id':sid,'expected_revision':1}
    with httpx.Client(timeout=30) as client:
        for case in cases['cases']:
            for mode in ('off','repair'):
                req={'message':case['message'],'review_mode':mode,'retrieval_mode':'single','institution':case['institution'],**fixture(case)}
                if case['supported_widgets']:req['supported_widgets']=case['supported_widgets']
                start=time.perf_counter()
                try:
                    response=client.post('http://127.0.0.1:8767/canvas/jobs',json={'request':req,'client_request_id':str(uuid.uuid4())})
                    response.raise_for_status();job=response.json();stages=[]
                    while time.perf_counter()-start<240:
                        response=client.get('http://127.0.0.1:8767/canvas/jobs/'+job['job_id']);response.raise_for_status();state=response.json()
                        if not stages or stages[-1]!=state['stage']:stages.append(state['stage'])
                        if state['status'] in ('completed','failed'):break
                        time.sleep(.5)
                    result=state.get('result') or {'status':state['status'],'error':state.get('error')}
                except Exception as exc:result={'status':'exception','error':str(exc)};stages=[]
                actual={n['type'] for n in result.get('widgets',[]) if not n['type'].endswith('inputs_widget')}
                gold=set(case['gold_roots'])
                row={'id':case['id'],'mode':mode,'gold':sorted(gold),'actual':sorted(actual),
                     'exact':actual==gold and result['status'] in ('composed','clarify'),
                     'wall_ms':round((time.perf_counter()-start)*1000,1),'stages':stages,'response':result}
                report['results'].append(row)
                output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
                print(json.dumps({k:row[k] for k in ('id','mode','exact','actual','wall_ms')},ensure_ascii=False),flush=True)
    summaries={}
    for mode in ('off','repair'):
        rows=[r for r in report['results'] if r['mode']==mode]
        summaries[mode]={'exact':sum(r['exact'] for r in rows),'total':len(rows),'median_wall_ms':statistics.median(r['wall_ms'] for r in rows)}
    pairs=[report['results'][i:i+2] for i in range(0,len(report['results']),2)]
    report['summary']={**summaries,'improved':[a['id'] for a,b in pairs if not a['exact'] and b['exact']],
                       'regressed':[a['id'] for a,b in pairs if a['exact'] and not b['exact']]}
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report['summary']),flush=True)


if __name__=='__main__':run()
