"""Candidate-union experiment against retained single-query model outputs."""
import hashlib
import json
import statistics
import time
import uuid

import httpx

from .canvas import ScreenDraft,ScreenStore,compile_screen
from .store import ROOT


def run():
    dataset=ROOT/'data/semantic_review_cases.json'
    prior=json.loads((ROOT/'reports/semantic-review-v2.json').read_text())
    if 'summary' not in prior:raise RuntimeError('Finish paired semantic-review experiment first')
    if hashlib.sha256(dataset.read_bytes()).hexdigest()!=prior['dataset_sha256']:raise RuntimeError('Dataset changed')
    cases=json.loads(dataset.read_text())['cases']
    baseline={r['id']:r for r in prior['results'] if r['mode']=='off'}
    output=ROOT/'reports/component-query-v1.json';store=ScreenStore(ROOT/'var/rag.screens.db')
    report={'scope':'Developer diagnostic set reused after observing single-query failures; exploratory development, not held-out or external performance.',
            'protocol':'End-to-end development comparison: retained CPU-float32 single-query baseline vs MPS-float16 multi-query/abstention system. Same neural weight snapshots and planner prompt/schema, but retrieval and execution precision both change; not a one-factor causal ablation. Model review disabled in both.',
            'execution':{'reranker_device':'mps','reranker_dtype':'float16','precision_check':'reports/reranker-mps-parity.json'},
            'baseline_report_sha256':hashlib.sha256((ROOT/'reports/semantic-review-v2.json').read_bytes()).hexdigest(),
            'dataset_sha256':prior['dataset_sha256'],'baseline_models':prior['models'],
            'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ('rag_backend/canvas.py','rag_backend/component_queries.py','rag_backend/research_models.py')},'results':[]}
    def candidates(row):
        trace=next((t for t in row.get('trace',[]) if t['step']=='component_retrieval'),{})
        return set(trace.get('candidate_ids',[]))
    with httpx.Client(timeout=30) as client:
        execution=client.get('http://127.0.0.1:8767/health').json().get('reranker_execution')
        if execution!={'device':'mps','dtype':'float16'}:raise RuntimeError('Expected verified MPS float16 reranker')
        report['execution']['actual_health']=execution
        for case in cases:
            req={'message':case['message'],'review_mode':'off','retrieval_mode':'multi','institution':case['institution']}
            if case['supported_widgets']:req['supported_widgets']=case['supported_widgets']
            if case['previous_roots']:
                nodes,_=compile_screen(ScreenDraft(title='기존 화면',widgets=[{'type':k,'priority':1} for k in case['previous_roots']],clarification=''))
                sid=str(uuid.uuid4());store.commit(sid,0,{'greeting':'기존 화면','widgets':nodes,'context':{},'revision':1,'session_id':sid})
                req.update(session_id=sid,expected_revision=1)
            start=time.perf_counter();print('start '+case['id'],flush=True)
            response=client.post('http://127.0.0.1:8767/canvas/jobs',json={'request':req,'client_request_id':str(uuid.uuid4())})
            response.raise_for_status();job=response.json();stages=[]
            while time.perf_counter()-start<240:
                try:
                    response=client.get('http://127.0.0.1:8767/canvas/jobs/'+job['job_id']);response.raise_for_status();state=response.json()
                except httpx.TransportError:
                    time.sleep(.5);continue
                if not stages or stages[-1]!=state['stage']:stages.append(state['stage'])
                if state['status'] in ('completed','failed'):break
                time.sleep(.5)
            result=state.get('result') or {'status':state['status'],'error':state.get('error')}
            actual={w['type'] for w in result.get('widgets',[]) if not w['type'].endswith('inputs_widget')};gold=set(case['gold_roots'])
            row={'id':case['id'],'gold':sorted(gold),'actual':sorted(actual),'exact':actual==gold and result['status'] in ('composed','clarify'),
                 'baseline_exact':baseline[case['id']]['exact'],'baseline_infrastructure_error':baseline[case['id']]['response']['status']=='exception','wall_ms':round((time.perf_counter()-start)*1000,1),
                 'candidate_covered':len(gold & candidates(result)),'baseline_candidate_covered':len(gold & candidates(baseline[case['id']]['response'])),
                 'candidate_count':len(candidates(result)),'baseline_candidate_count':len(candidates(baseline[case['id']]['response'])),
                 'stages':stages,'response':result}
            report['results'].append(row);output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
            print(json.dumps({k:row[k] for k in ('id','exact','baseline_exact','actual','wall_ms')},ensure_ascii=False),flush=True)
    rows=report['results'];total_gold=sum(len(r['gold']) for r in rows if not r['baseline_infrastructure_error'])
    report['summary']={'single_exact':sum(r['baseline_exact'] for r in rows),'multi_exact':sum(r['exact'] for r in rows),'total':len(rows),
        'improved':[r['id'] for r in rows if r['exact'] and not r['baseline_exact']],
        'regressed':[r['id'] for r in rows if not r['exact'] and r['baseline_exact']],
        'single_candidate_recall':sum(r['baseline_candidate_covered'] for r in rows if not r['baseline_infrastructure_error'])/total_gold,
        'multi_candidate_recall':sum(r['candidate_covered'] for r in rows if not r['baseline_infrastructure_error'])/total_gold,
        'multi_median_wall_ms':statistics.median(r['wall_ms'] for r in rows),
        'comparable_model_pairs':{'total':sum(not r['baseline_infrastructure_error'] for r in rows),
            'single_exact':sum(r['baseline_exact'] for r in rows if not r['baseline_infrastructure_error']),
            'multi_exact':sum(r['exact'] for r in rows if not r['baseline_infrastructure_error'])},
        'model_improved':[r['id'] for r in rows if not r['baseline_infrastructure_error'] and r['exact'] and not r['baseline_exact']],
        'model_regressed':[r['id'] for r in rows if not r['baseline_infrastructure_error'] and not r['exact'] and r['baseline_exact']],
        'baseline_infrastructure_errors':[r['id'] for r in rows if r['baseline_infrastructure_error']]}
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report['summary']),flush=True)


if __name__=='__main__':run()
