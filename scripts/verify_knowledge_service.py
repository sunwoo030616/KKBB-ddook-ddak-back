#!/usr/bin/env python3
"""Verify exact inference reuse does not reuse screen sessions or dated evidence."""
import json
from pathlib import Path
import time
import urllib.request
import uuid

ROOT=Path(__file__).resolve().parents[1]


def http(url,body=None):
    req=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,
                              headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=180) as response:return json.load(response)


def compose(as_of):
    base='http://127.0.0.1:8088/api/canvas/v2/jobs'
    submission=http(base,{'client_request_id':str(uuid.uuid4()),'request':{
        'message':'예금보호 기준만 보여줘','as_of':as_of,'retrieval_mode':'multi','intent_mode':'auto','evidence_mode':'once'}})
    started=time.perf_counter()
    while time.perf_counter()-started<180:
        job=http(base+'/'+submission['job_id'])
        if job['status']=='failed':raise RuntimeError('composition_failed')
        if job['status']=='completed':return job['result']
        time.sleep(.2)
    raise TimeoutError('composition_timeout')


if __name__=='__main__':
    for attempt in range(40):
        try:
            environment=http('http://127.0.0.1:8767/health');break
        except Exception:
            if attempt==39:raise
            time.sleep(.5)
    first=compose('2026-11-04');second=compose('2026-11-04');past=compose('2025-08-31')
    evidence=lambda s:{h['chunk_id'] for w in s['widgets'] for h in w.get('knowledge',{}).get('evidence',[])}
    steps=[t for t in second['trace'] if t['step'] in ('llm_plan','evidence_decision')]
    status=http('http://127.0.0.1:8767/knowledge/status')
    search=http('http://127.0.0.1:8767/knowledge/search',{'question':'검색 질의 자체를 고쳐서 필요한 문서를 찾는 연구',
                                                       'kind':'abstract','mode':'neural'})
    checks={'new_request_has_distinct_screen_session':first['session_id']!=second['session_id'],
            'duplicate_plan_requires_zero_actual_model_calls':bool(steps) and all(t.get('model_calls')==0 for t in steps),
            'current_date_uses_current_evidence':'fsc-protection-current' in evidence(first),
            'past_date_does_not_reuse_current_financial_data':evidence(past)=={'fsc-protection-before'},
            'knowledge_store_has_expected_corpus':status['documents']==len(json.loads((ROOT/'data/financial_guides.json').read_text())['chunks'])+len(json.loads((ROOT/'data/expanded_literature_manifest.json').read_text())['records']),
            'neural_knowledge_api_retrieves_query_rewriting':'arxiv:2305.14283' in [h['id'] for h in search['hits']]}
    result={'checks':checks,'first_screen':first['session_id'],'second_screen':second['session_id'],
            'current_evidence_ids':sorted(evidence(first)),'past_evidence_ids':sorted(evidence(past)),
            'duplicate_trace':steps,'knowledge_status':status,
            'knowledge_search_ids':[h['id'] for h in search['hits']],
            'environment':environment,'after':http('http://127.0.0.1:8767/health')}
    (ROOT/'reports/knowledge-service.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(checks))
    if not all(checks.values()):raise SystemExit(1)
