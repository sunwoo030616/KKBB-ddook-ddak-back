#!/usr/bin/env python3
"""Local HTTP job-queue benchmark with real model calls, not distributed serving.

Run separately from evaluation. Count all submitted requests and errors.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import statistics
import time
import urllib.request
import uuid
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def request(url,body=None):
    req=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,
                              headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=180) as response:return json.load(response)


def one(url,index):
    started=time.perf_counter()
    try:
        submission=request(url+'/canvas/jobs',{'client_request_id':str(uuid.uuid4()),'request':{
            'message':['대출 월 상환표만 보여줘','예금보호 기준만 보여줘'][index%2],
            'retrieval_mode':'multi','intent_mode':'auto','evidence_mode':'off'}})
        while time.perf_counter()-started<240:
            job=request(url+'/canvas/jobs/'+submission['job_id'])
            if job['status'] in ('completed','failed'):
                return {'wall_seconds':round(time.perf_counter()-started,3),'status':job['status'],
                        'timings_ms':job['timings_ms'],'screen_status':(job['result'] or {}).get('status'),
                        'widget_types':[w['type'] for w in (job['result'] or {}).get('widgets',[])]}
            time.sleep(.15)
        return {'status':'timeout','wall_seconds':round(time.perf_counter()-started,3)}
    except Exception as error:return {'status':'error','error_type':type(error).__name__,
                                     'wall_seconds':round(time.perf_counter()-started,3)}


def percentile(values,p):
    values=sorted(values);position=(len(values)-1)*p;lo=int(position);hi=min(lo+1,len(values)-1)
    return values[lo]+(values[hi]-values[lo])*(position-lo)


def memory_snapshot():
    """macOS process RSS snapshot, NOT GPU peak allocation or machine RAM usage."""
    try:
        pid=subprocess.check_output(['lsof','-t','-iTCP:8767','-sTCP:LISTEN'],text=True).splitlines()[0]
        rss=int(subprocess.check_output(['ps','-o','rss=','-p',pid],text=True).strip())
        return {'rss_kib':rss,'scope':'Server process RSS snapshot; not peak GPU memory.'}
    except Exception:return {'available':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8767');p.add_argument('--per-level',type=int,default=8);args=p.parse_args()
    result={'scope':'Single Apple Silicon process, warmed model; small exploratory sample. No multi-GPU or distributed claim.',
            'evidence_mode':'off to isolate screen serving; end-to-end evidence measured separately','levels':[]}
    result['environment']=request(args.url+'/health')
    result['memory_before']=memory_snapshot()
    warm=one(args.url,0);result['warmup']=warm
    for concurrency in (1,2,4):
        started=time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            rows=list(pool.map(lambda i:one(args.url,i),range(args.per_level)))
        elapsed=time.perf_counter()-started;latencies=[r['wall_seconds'] for r in rows]
        result['levels'].append({'concurrency':concurrency,'submitted':len(rows),'elapsed_seconds':elapsed,
            'completed':sum(r['status']=='completed' for r in rows),
            'valid_screens':sum(r.get('screen_status')=='composed' for r in rows),
            'requests_per_second':len(rows)/elapsed,'p50_seconds':statistics.median(latencies),
            'p95_seconds':percentile(latencies,.95),'p95_is_unstable_small_n':True,
            'memory_after':memory_snapshot(),'rows':rows})
        (ROOT/'reports/serving-load.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(concurrency,elapsed,flush=True)
