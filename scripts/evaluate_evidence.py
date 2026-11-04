#!/usr/bin/env python3
"""Paired real-model evidence-tool evaluation. Full UI is checked separately.

Gold scope is deterministic from the frozen corpus, not passed to the model.
This measures topic retrieval coverage and missing-evidence handling, NOT entailment.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rag_backend.evidence_agent import WIDGET_TOPICS,TOPICS


def post(url,body):
    request=urllib.request.Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(request,timeout=240) as response:return json.load(response)


def evaluate(args):
    path=ROOT/'data/evidence_cases.json';raw=path.read_bytes();cases=json.loads(raw)
    corpus=json.loads((ROOT/'data/financial_guides.json').read_text())['chunks']
    result={'scope':'Frozen developer-authored cases; repeated wording variants of 8 categories, NOT independent samples. Evidence tool only, not semantic answer benchmark.',
            'dataset_sha256':hashlib.sha256(raw).hexdigest(),'split':args.split,'rows':[]}
    with urllib.request.urlopen(args.url+'/health',timeout=10) as response:result['environment']=json.load(response)
    for case in cases:
        if case['split']!=args.split:continue
        required=list(dict.fromkeys(t for w in case['widgets'] for t in WIDGET_TOPICS.get(w,[])))
        available=[t for t in required if any(t in c['topics'] and c['institution']==(TOPICS[t][0] or case['institution'])
            and all(not c.get(k) or c[k]<=case['as_of'] for k in ('published_at','content_as_of','effective_from'))
            and (not c.get('effective_until') or c['effective_until']>=case['as_of']) for c in corpus)]
        for mode in ('once','adaptive'):
            started=time.perf_counter()
            row={'id':case['id'],'mode':mode,'expected_covered':available,'required':required}
            try:
                output=post(args.url+'/canvas/evidence',{'message':case['message'],'institution':case['institution'],
                    'as_of':case['as_of'],'supported_widgets':case['widgets'],'evidence_mode':mode})
                row.update(output=output,covered_exact=set(output['covered_topics'])==set(available),
                    missing_exact=set(output['missing_topics'])==set(required)-set(available),
                    model_calls=sum(t.get('model_calls',0) for t in output['trace']))
            except Exception as error:row.update(error=type(error).__name__,covered_exact=False,missing_exact=False)
            row['wall_seconds']=round(time.perf_counter()-started,3);result['rows'].append(row)
            (ROOT/f'reports/evidence-{args.split}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
            print(case['id'],mode,row['covered_exact'],row['wall_seconds'],flush=True)
    result['summary']={m:{'n':len(rows),'exact_covered':sum(r['covered_exact'] for r in rows),
        'exact_missing':sum(r['missing_exact'] for r in rows),'errors':sum('error'in r for r in rows),
        'median_seconds':statistics.median(r['wall_seconds'] for r in rows)}
        for m in ('once','adaptive') if (rows:=[r for r in result['rows'] if r['mode']==m])}
    (ROOT/f'reports/evidence-{args.split}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result['summary']))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',default='http://127.0.0.1:8767');p.add_argument('--split',choices=['dev','test'],default='test')
    evaluate(p.parse_args())
