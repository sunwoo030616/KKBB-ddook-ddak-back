#!/usr/bin/env python3
"""Evaluate the supplied development cases once; errors remain visible in the denominator."""
import argparse, datetime, hashlib, json, math, statistics, time, urllib.error, urllib.request
from pathlib import Path

def main():
    root = Path(__file__).resolve().parents[2]
    p = argparse.ArgumentParser()
    p.add_argument('--url', default='http://127.0.0.1:8080/api/menus/select')
    p.add_argument('--retrieval-only', action='store_true')
    p.add_argument('--search-url', default='http://127.0.0.1:18083/search')
    p.add_argument('--requested-model', default=None, help='Record the model configured on the backend; does not change it')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    raw = (root/'src/main/resources/kb_starbanking_menu_structure_cleaned.json').read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    cases_raw = (root/'src/test/resources/menu-selection-cases-20.json').read_bytes()
    cases = json.loads(cases_raw)
    results = []
    started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    def save():
        durations = sorted(r['duration_ms'] for r in results if not r.get('error'))
        rank = lambda r: r.get('expected_rank')
        summary = {'mode': 'e5_only' if args.retrieval_only else 'e5_jev', 'started_at': started_at,
            'requested_model': args.requested_model, 'catalog_sha256': digest,
            'cases_sha256': hashlib.sha256(cases_raw).hexdigest(), 'planned_cases': len(cases), 'cases': len(results),
            'errors': sum(bool(r.get('error')) for r in results),
            'candidate_recall': {str(k): sum(rank(r) is not None and rank(r) <= k for r in results)/len(results) for k in [5,10,20,40]},
            'final_correct': None if args.retrieval_only else sum(r.get('correct',False) for r in results),
            'accuracy': None if args.retrieval_only else sum(r.get('correct',False) for r in results)/len(results),
            'mean_ms': round(statistics.mean(durations),2) if durations else None,
            'p95_ms': durations[max(0, math.ceil(.95*len(durations))-1)] if durations else None,
            'limitation': 'Supplied development cases; catalog descriptions and K were clarified using these cases before this run. Not held-out production accuracy. No retries.',
            'results': results}
        temporary = args.output.with_suffix(args.output.suffix+'.tmp')
        temporary.write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n');temporary.replace(args.output)
        return summary
    for index,row in enumerate(cases,1):
        payload = {'message': row['query']}
        if args.retrieval_only: payload.update(limit=40, catalog_sha256=digest)
        request = urllib.request.Request(args.search_url if args.retrieval_only else args.url,
            data=json.dumps(payload, ensure_ascii=False).encode(), headers={'Content-Type': 'application/json'})
        start = time.perf_counter()
        result = {**row,'candidate_ids':[],'expected_rank':None,'selected':[], 'correct':False if not args.retrieval_only else None}
        try:
            with urllib.request.urlopen(request, timeout=30) as response: body = json.load(response)
            if body.get('catalog_sha256', body.get('catalogSha256')) != digest: raise ValueError('Catalog mismatch')
            ids = body['ids'] if args.retrieval_only else body['candidateIds']
            selected = [m['id'] for m in body.get('menus', [])]
            result.update(candidate_ids=ids, expected_rank=ids.index(row['expected'])+1 if row['expected'] in ids else None,
                selected=selected, status=body.get('status'), confidence=body.get('confidence'),
                retrieval_ms=body.get('retrievalMs'), selection_ms=body.get('selectionMs'), jev_calls=body.get('jevCalls'),
                correct=None if args.retrieval_only else selected == [row['expected']])
        except urllib.error.HTTPError as error:
            result.update(status='error',error='HTTP '+str(error.code))
        except (urllib.error.URLError,TimeoutError,ValueError,KeyError) as error:
            result.update(status='error',error=type(error).__name__)
        result['duration_ms']=round((time.perf_counter()-start)*1000,2)
        results.append(result);summary=save()
        print(f"{index}/{len(cases)} status={result.get('status')} correct={result.get('correct')} rank={result['expected_rank']}",flush=True)
    print(json.dumps({k:v for k,v in summary.items() if k!='results'}, ensure_ascii=False))
if __name__ == '__main__': main()
