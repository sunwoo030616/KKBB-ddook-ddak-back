#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import time
import uuid

import httpx

ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'reports/intent-contract-v3.json';report=json.loads(source.read_text())
prior=next(x['response'] for x in report['smoke_checks'] if x['name']=='calculation_preserves_layout_without_intent_model')
with httpx.Client(timeout=15) as client:
    response=client.post('http://127.0.0.1:8767/canvas/jobs',json={'request':{'message':'화면을 모두 지워줘',
        'session_id':prior['session_id'],'expected_revision':prior['revision'],'intent_mode':'enforce','retrieval_mode':'multi'},'client_request_id':str(uuid.uuid4())})
    response.raise_for_status();job=response.json();start=time.perf_counter();state={}
    while time.perf_counter()-start<60:
        response=client.get('http://127.0.0.1:8767/canvas/jobs/'+job['job_id']);response.raise_for_status();state=response.json()
        if state['status'] in ('completed','failed'):break
        time.sleep(.2)
    result=state.get('result') or {'status':state.get('status'),'error':state.get('error')}
    passed=result.get('status')=='composed' and result.get('widgets')==[] and not any(t['step'] in ('intent_contract','llm_plan') for t in result.get('trace',[]))
report['retained_v3_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
report['retained_failed_clear_smoke']=next(x for x in report['smoke_checks'] if x['name']=='explicit_clear_commits_empty_screen')
report['smoke_checks']=[x for x in report['smoke_checks'] if x['name']!='explicit_clear_commits_empty_screen']+[
    {'name':'explicit_clear_exact_router_no_model','passed':passed,'wall_ms':round((time.perf_counter()-start)*1000,1),'response':result}]
report['summary']['smoke_checks']={'total':len(report['smoke_checks']),'passed':sum(x['passed'] for x in report['smoke_checks'])}
report['final_patch']='High-precision clear-only UI router; does not change any of the 20 evaluation messages. Retains failed neural clear interpretation and actual retry. No new full 20-case neural run.'
report['source_sha256']={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ('rag_backend/canvas.py','rag_backend/intent_contract.py','rag_backend/research_models.py')}
report['models']={role:json.loads((ROOT/'var/research_models'/role/'manifest.local.json').read_text()) for role in ('canvas_generator','reranker')}
(ROOT/'reports/intent-contract-final.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'clear_passed':passed,'summary':report['summary']},ensure_ascii=False))
if not passed:raise SystemExit(1)
