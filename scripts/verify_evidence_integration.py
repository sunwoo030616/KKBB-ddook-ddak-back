#!/usr/bin/env python3
"""Actual Spring -> local model integration, including a zero-call form edit."""
import json
from pathlib import Path
import time
import urllib.request
import uuid

ROOT=Path(__file__).resolve().parents[1]


def http(url,body=None):
    req=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,
                              headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=240) as response:return json.load(response)


def compose(body):
    submitted=http('http://127.0.0.1:8088/api/canvas/v2/jobs',{'request':body,'client_request_id':str(uuid.uuid4())})
    started=time.perf_counter()
    while time.perf_counter()-started<240:
        job=http('http://127.0.0.1:8088/api/canvas/v2/jobs/'+submitted['job_id'])
        if job['status'] in ('completed','failed'):return job
        time.sleep(.2)
    raise TimeoutError('integration_job')


if __name__=='__main__':
    report={'scope':'Actual local Spring/model integration, not a public financial service.','checks':{}}
    try:
        first=compose({'message':'예금 해지와 담보대출 비용 비교 화면을 만들어줘','evidence_mode':'once',
                       'intent_mode':'auto','retrieval_mode':'multi'})
        report['initial']=first
        screen=first['result'];assert screen and screen['status']=='composed'
        node=next(w for w in screen['widgets'] if w['type']=='funding_comparison_widget')
        assert node['knowledge']['evidence'];report['checks']['official_evidence_on_financial_screen']=True
        edited=compose({'message':'현재 조건으로 계산해줘','evidence_mode':'once','session_id':screen['session_id'],
            'expected_revision':screen['revision'],'calculation':{'kind':'funding_comparison',
            'maturity_interest_net_won':'1000000','early_interest_net_won':'300000','loan_principal_won':'10000000',
            'annual_loan_rate_percent':'3.65','loan_days':100,'extra_loan_cost_won':'10000'}})
        report['calculation']=edited
        node2=next(w for w in edited['result']['widgets'] if w['type']=='funding_comparison_widget')
        assert node2['data']['values']['interest_difference_won']=='590000'
        assert node2['knowledge']==node['knowledge']
        assert all(t['step'] not in ('llm_plan','evidence_decision') for t in edited['result']['trace'])
        report['checks']['zero_model_call_calculation_preserves_evidence']=True
        papers=http('http://127.0.0.1:8767/research/papers',{'question':'Find research on evidence evaluation in retrieval augmented generation.'})
        report['papers']=papers
        records={r['doi']:r for r in json.loads((ROOT/'data/paper_metadata.json').read_text())['records']}
        assert papers['records'] and all(r==records[r['doi']] for r in papers['records'])
        report['checks']['real_model_paper_tools_return_only_observed_metadata']=True
    except Exception as error:
        report['error_type']=type(error).__name__
    (ROOT/'reports/evidence-integration.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'checks':report['checks'],'error':report.get('error_type')}))
    if 'error_type' in report:raise SystemExit(1)
