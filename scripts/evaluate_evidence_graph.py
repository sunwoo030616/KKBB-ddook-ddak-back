#!/usr/bin/env python3
"""Compare single retrieval with task decomposition at the same three-document budget."""
import hashlib
import json
from pathlib import Path
import statistics
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]


if __name__=='__main__':
    path=ROOT/'data/evidence_graph_cases.json';raw=path.read_bytes()
    report={'scope':'Eight developer-authored diagnostic requests over six abstracts. Source-set coverage is not answer correctness.',
            'dataset_sha256':hashlib.sha256(raw).hexdigest(),'rows':[]}
    for case in json.loads(raw):
        for mode in ('single','decompose'):
            row={'id':case['id'],'mode':mode,'expected_sources':case['expected_sources']};started=time.perf_counter()
            try:
                request=urllib.request.Request('http://127.0.0.1:8767/knowledge/research',
                    data=json.dumps({'question':case['question'],'mode':mode}).encode(),headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(request,timeout=300) as response:result=json.load(response)
                sources=sorted({e['source_id'] for e in result['edges']})
                # Do not publish abstract quotations in this evaluation artifact.
                edges=[{k:v for k,v in e.items() if k not in ('text','title')} for e in result['edges']]
                valid=result['status'] not in ('invalid_plan','invalid_selection','stale_snapshot')
                expected=set(case['expected_sources']);actual=set(sources)
                row.update(status=result['status'],tasks=result['tasks'],edges=edges,selected_sources=sources,
                    exact_sources=valid and actual==expected,
                    recall=len(actual&expected)/len(expected) if expected else None,
                    all_required=valid and expected<=actual if expected else None,
                    exposes_missing=bool(result.get('missing_task_ids')),
                    missing_task_ids=result.get('missing_task_ids',[]),trace=result.get('trace',[]))
            except Exception as error:row.update(error=type(error).__name__,exact_sources=False)
            row['seconds']=time.perf_counter()-started;report['rows'].append(row)
            (ROOT/'reports/evidence-graph.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
            print(case['id'],mode,row.get('status',row.get('error')),row['exact_sources'],round(row['seconds'],2),flush=True)
    report['summary']={mode:{'n':len(rows),'exact_source_sets':sum(r['exact_sources'] for r in rows),
        'invalid_or_error':sum('error'in r or r.get('status') in ('invalid_plan','invalid_selection','stale_snapshot') for r in rows),
        'all_required':sum(r.get('all_required') is True for r in rows),
        'answerable_n':sum(r.get('all_required') is not None for r in rows),
        'median_seconds':statistics.median(r['seconds'] for r in rows)} for mode in ('single','decompose')
        if (rows:=[r for r in report['rows'] if r['mode']==mode])}
    (ROOT/'reports/evidence-graph.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report['summary']))
