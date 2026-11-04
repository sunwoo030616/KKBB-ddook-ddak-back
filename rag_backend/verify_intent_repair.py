"""Targeted actual-model retest after deterministic duplicate canonicalization.

Retain all v2 successes and the original failure; do not claim a new full neural run.
"""
import hashlib
import json
import time
import uuid

import httpx

from .canvas import ScreenDraft,ScreenStore,compile_screen
from .store import ROOT


def run():
    previous_path=ROOT/'reports/intent-contract-v2.json';report=json.loads(previous_path.read_text())
    assert 'summary' in report
    report['protocol']+=' V3: canonicalizes duplicate selections after the unchanged planner schema/prompt. Retains v2 unique valid outcomes; targeted real-model retest only for s10, plus actual calculation/clear smoke checks. Not a new full 20-case inference run.'
    report['retained_v2_sha256']=hashlib.sha256(previous_path.read_bytes()).hexdigest()
    report['source_sha256']={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('rag_backend/canvas.py','rag_backend/intent_contract.py','rag_backend/research_models.py')}
    report['retained_failure']=next(r for r in report['results'] if r['id']=='s10')
    output=ROOT/'reports/intent-contract-v3.json'
    case=next(c for c in json.loads((ROOT/'data/semantic_review_cases.json').read_text())['cases'] if c['id']=='s10')
    nodes,_=compile_screen(ScreenDraft(title='기존 화면',widgets=[{'type':k,'priority':1} for k in case['previous_roots']],clarification=''))
    sid=str(uuid.uuid4());ScreenStore(ROOT/'var/rag.screens.db').commit(sid,0,{'greeting':'기존 화면','widgets':nodes,'context':{},'revision':1,'session_id':sid})
    with httpx.Client(timeout=15) as client:
        def submit(req):
            start=time.perf_counter();r=client.post('http://127.0.0.1:8767/canvas/jobs',json={'request':req,'client_request_id':str(uuid.uuid4())})
            r.raise_for_status();job=r.json();stages=[];state={}
            while time.perf_counter()-start<240:
                try:
                    r=client.get('http://127.0.0.1:8767/canvas/jobs/'+job['job_id']);r.raise_for_status();state=r.json()
                except httpx.TransportError:time.sleep(.5);continue
                if not stages or stages[-1]!=state['stage']:stages.append(state['stage'])
                if state['status'] in ('completed','failed'):break
                time.sleep(.4)
            result=state.get('result') or {'status':state.get('status','timeout'),'error':state.get('error')}
            return result,stages,round((time.perf_counter()-start)*1000,1)
        request={'message':case['message'],'session_id':sid,'expected_revision':1,'intent_mode':'auto','retrieval_mode':'multi','review_mode':'off'}
        result,stages,wall=submit(request)
        actual=sorted(n['type'] for n in result.get('widgets',[]) if not n['type'].endswith('inputs_widget'))
        replacement={'suite':'regression','id':'s10','mode':'auto','gold':sorted(case['gold_roots']),
                     'actual':actual,'exact':actual==sorted(case['gold_roots']) and result['status']=='composed',
                     'wall_ms':wall,'stages':stages,'response':result,'targeted_retest':True}
        report['results']=[replacement if x['id']=='s10' else x for x in report['results']]
        report['smoke_checks']=[]
        print(json.dumps({k:replacement[k] for k in ('id','exact','actual','wall_ms')},ensure_ascii=False),flush=True)
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        if replacement['exact']:
            calc={'kind':'funding_comparison','maturity_interest_net_won':'1000000','early_interest_net_won':'300000','loan_principal_won':'10000000','annual_loan_rate_percent':'3.65','loan_days':100,'extra_loan_cost_won':'10000'}
            calculated,_,_=submit({'message':'현재 화면은 유지하면서 입력 조건으로 비용을 계산해줘','calculation':calc,
                'session_id':result['session_id'],'expected_revision':result['revision'],'intent_mode':'enforce','retrieval_mode':'multi'})
            node=next((n for n in calculated.get('widgets',[]) if n['type']=='funding_comparison_widget'),{})
            report['smoke_checks'].append({'name':'calculation_preserves_layout_without_intent_model',
                'passed':node.get('data',{}).get('values',{}).get('interest_difference_won')=='590000' and not any(t['step'] in ('llm_plan','intent_contract') for t in calculated.get('trace',[])),
                'response':calculated})
            cleared,_,_=submit({'message':'화면을 모두 지워줘','session_id':calculated['session_id'],
                'expected_revision':calculated['revision'],'intent_mode':'auto','retrieval_mode':'multi'})
            report['smoke_checks'].append({'name':'explicit_clear_commits_empty_screen',
                'passed':cleared.get('status')=='composed' and cleared.get('widgets')==[], 'response':cleared})
        reg=[x for x in report['results'] if x['suite']=='regression']
        baseline={x['id']:x for x in json.loads((ROOT/'reports/component-query-v1.json').read_text())['results']}
        report['summary']['regression'].update(after=sum(x['exact'] for x in reg),
             improved=[x['id'] for x in reg if x['exact'] and not baseline[x['id']]['exact']],regressed=[x['id'] for x in reg if not x['exact'] and baseline[x['id']]['exact']])
        report['summary']['smoke_checks']={'total':len(report['smoke_checks']),'passed':sum(x['passed'] for x in report['smoke_checks'])}
        report['completed']=True
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report['summary']),flush=True)


if __name__=='__main__':run()
