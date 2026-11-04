"""Actual-model intent contract regression and frozen challenge comparison."""
import hashlib
import json
import statistics
import time
import uuid

import httpx

from .canvas import ScreenDraft,ScreenStore,compile_screen
from .store import ROOT


def run():
    challenge_path=ROOT/'data/intent_contract_challenge_v1.json'
    challenge=json.loads(challenge_path.read_text());regression=json.loads((ROOT/'data/semantic_review_cases.json').read_text())
    baseline=json.loads((ROOT/'reports/component-query-v1.json').read_text())
    old={r['id']:r for r in baseline['results']}
    prior=json.loads((ROOT/'reports/intent-contract-v1.json').read_text())
    output=ROOT/'reports/intent-contract-v2.json';store=ScreenStore(ROOT/'var/rag.screens.db')
    report={'scope':challenge['scope'],'protocol':'V2 adds neural-bound exclusions after retained v1 s10 regression. Eight challenge off results reused unchanged from v1 (off path unaffected); 20 auto requests rerun. Same MPS-float16 BGE and greedy Qwen3-4B snapshots. Challenge pairs off/auto, prior 12-case regression auto vs retained multi/MPS off. Gold is evaluator-only. Adaptive feature informed by prior failure; not independent research benchmark.',
            'challenge_sha256':hashlib.sha256(challenge_path.read_bytes()).hexdigest(),
            'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('rag_backend/canvas.py','rag_backend/intent_contract.py','rag_backend/research_models.py')},
            'retained_challenge_baseline_sha256':hashlib.sha256((ROOT/'reports/intent-contract-v1.json').read_bytes()).hexdigest(),
            'results':[r for r in prior['results'] if r['suite']=='challenge' and r['mode']=='off']}
    def request(case,mode):
        req={'message':case['message'],'intent_mode':mode,'retrieval_mode':'multi','review_mode':'off','institution':case.get('institution','kb_card')}
        if case.get('supported_widgets'):req['supported_widgets']=case['supported_widgets']
        if case['previous_roots']:
            nodes,_=compile_screen(ScreenDraft(title='기존 화면',widgets=[{'type':k,'priority':1} for k in case['previous_roots']],clarification=''))
            sid=str(uuid.uuid4());store.commit(sid,0,{'greeting':'기존 화면','widgets':nodes,'context':{},'revision':1,'session_id':sid})
            req.update(session_id=sid,expected_revision=1)
        return req
    with httpx.Client(timeout=15) as client:
        execution=client.get('http://127.0.0.1:8767/health').json()['reranker_execution'];report['execution']=execution
        for suite,cases in [('regression',regression['cases']),('challenge',challenge['cases'])]:
            for case in cases:
                for mode in ('auto',):
                    print('start '+case['id']+' '+mode,flush=True);start=time.perf_counter();stages=[];job=None
                    try:
                        response=client.post('http://127.0.0.1:8767/canvas/jobs',json={'request':request(case,mode),'client_request_id':str(uuid.uuid4())})
                        response.raise_for_status();job=response.json();state={}
                        while time.perf_counter()-start<240:
                            try:
                                response=client.get('http://127.0.0.1:8767/canvas/jobs/'+job['job_id']);response.raise_for_status();state=response.json()
                            except httpx.TransportError:time.sleep(.5);continue
                            if not stages or stages[-1]!=state['stage']:stages.append(state['stage'])
                            if state['status'] in ('completed','failed'):break
                            time.sleep(.4)
                        result=state.get('result') or {'status':state.get('status','timeout'),'error':state.get('error')}
                    except Exception as error:result={'status':'exception','error':str(error)}
                    actual={n['type'] for n in result.get('widgets',[]) if not n['type'].endswith('inputs_widget')}
                    row={'suite':suite,'id':case['id'],'mode':mode,'gold':sorted(case['gold_roots']),
                         'actual':sorted(actual),'exact':actual==set(case['gold_roots']) and result['status'] in ('composed','clarify'),
                         'wall_ms':round((time.perf_counter()-start)*1000,1),'stages':stages,'job_id':(job or {}).get('job_id'),'response':result}
                    report['results'].append(row);output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
                    print(json.dumps({k:row[k] for k in ('suite','id','mode','exact','actual','wall_ms')},ensure_ascii=False),flush=True)
    reg=[r for r in report['results'] if r['suite']=='regression'];ch=[r for r in report['results'] if r['suite']=='challenge']
    report['summary']={'regression':{'total':len(reg),'before':sum(old[r['id']]['exact'] for r in reg),'after':sum(r['exact'] for r in reg),
        'improved':[r['id'] for r in reg if r['exact'] and not old[r['id']]['exact']],
        'regressed':[r['id'] for r in reg if not r['exact'] and old[r['id']]['exact']]},
        'challenge':{mode:{'exact':sum(r['exact'] for r in ch if r['mode']==mode),'total':sum(r['mode']==mode for r in ch),
            'median_wall_ms':statistics.median(r['wall_ms'] for r in ch if r['mode']==mode)} for mode in ('off','auto')}}
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report['summary']),flush=True)


if __name__=='__main__':run()
