#!/usr/bin/env python3
"""Run the frozen Recall 300 questions once through the actual E5→JEV endpoint."""
import argparse
import datetime
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def successful(row):
    if row.get('error'):
        return False
    if len(row['expected_ids']) == 1:
        return row.get('status') == 'selected' and row.get('selected_ids') == row['expected_ids']
    # Public API maps both unsure and low confidence to needs_clarification.
    return row.get('status') == 'needs_clarification' and row.get('selected_ids') == []

def summarize(rows):
    single = [r for r in rows if len(r['expected_ids']) == 1]
    multi = [r for r in rows if len(r['expected_ids']) > 1]
    selected = [r for r in single if r.get('status') == 'selected' and not r.get('error')]
    n = len(rows)
    def rate(count, total):
        return count / total if total else None
    timings = sorted(r['http_ms'] for r in rows if not r.get('error'))
    return {'cases': n, 'errors': sum(bool(r.get('error')) for r in rows),
            'reported_jev_calls': sum(r.get('jev_calls', 0) for r in rows),
            'single_cases': len(single), 'single_exact_correct': sum(successful(r) for r in single),
            'single_exact_accuracy': rate(sum(successful(r) for r in single), len(single)),
            'single_selected_cases': len(selected),
            'single_accuracy_among_selected': rate(sum(successful(r) for r in selected), len(selected)),
            'multi_cases': len(multi), 'multi_clarification_correct': sum(successful(r) for r in multi),
            'multi_clarification_rate': rate(sum(successful(r) for r in multi), len(multi)),
            'policy_success_count': sum(successful(r) for r in rows),
            'policy_success_rate': rate(sum(successful(r) for r in rows), n),
            'statuses': {s:sum(r.get('status') == s for r in rows) for s in sorted({r.get('status', 'error') for r in rows})},
            'single_candidate_hit_at_40': rate(sum(r['expected_ids'][0] in r.get('candidate_ids', []) for r in single), len(single)),
            'single_retrieval_hit_but_final_failed': [r['case_id'] for r in single if r['expected_ids'][0] in r.get('candidate_ids', []) and not successful(r)],
            'mean_http_ms': statistics.mean(timings) if timings else None,
            'p95_http_ms': timings[math.ceil(.95*len(timings))-1] if timings else None}

def validate_response(body, catalog_hash, known_ids):
    if body.get('catalogSha256') != catalog_hash or body.get('pipeline') != 'e5_jev':
        raise ValueError('Pipeline/catalog mismatch')
    ids = body.get('candidateIds', [])
    selected = [m['id'] for m in body.get('menus', [])]
    if len(ids) != 40 or len(set(ids)) != 40 or set(ids) - known_ids:
        raise ValueError('Invalid candidates')
    if body.get('jevCalls') != 1:
        raise ValueError('Expected exactly one actual JEV call')
    status = body.get('status')
    confidence = body.get('confidence')
    if not isinstance(confidence, (int, float)) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
        raise ValueError('Invalid confidence')
    if status == 'selected':
        if len(selected) != 1 or not set(selected) <= set(ids):
            raise ValueError('Selection outside candidates')
    elif status not in ('needs_clarification', 'no_match') or selected:
        raise ValueError('Invalid status/selection')
    return ids, selected

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--url', default='http://127.0.0.1:18108/api/menus/select')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise ValueError('Refuse to overwrite a prior run')
    freeze = json.loads((HERE/'freeze.json').read_text())
    for name, digest in freeze['files'].items():
        if sha(ROOT/name) != digest:
            raise ValueError('Frozen input changed: '+name)
    cases = json.loads((ROOT/'scripts/semantic/recall300/cases.json').read_text())
    assert len(cases) == 300 and len({r['case_id'] for r in cases}) == 300
    catalog = ROOT/'src/main/resources/kb_starbanking_menu_structure_cleaned.json'
    catalog_hash = sha(catalog)
    known_ids = {m['id'] for m in json.loads(catalog.read_text())['menus']}
    old = json.loads((ROOT/'docs/recall300/results.json').read_text())
    old_candidates = {r['case_id']:r.get('candidate_ids', [])[:40] for r in old['results']}
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rows = []
    def save(complete=False):
        data = {'mode':'actual_e5_jev_300', 'started_at':started,
                'updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'complete':complete, 'planned_cases':300, 'freeze':freeze,
                'python':platform.python_version(), 'platform':platform.platform(),
                'summary':summarize(rows),
                'by_type':{g:summarize([r for r in rows if r['question_type']==g]) for g in sorted({r['question_type'] for r in rows})},
                'by_domain':{g:summarize([r for r in rows if r['domain']==g]) for g in sorted({r['domain'] for r in rows})},
                'results':rows}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        temporary = args.output.with_suffix('.tmp')
        temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
        temporary.replace(args.output)
        return data
    consecutive_errors = 0
    for case in cases:
        row = dict(case)
        row['expected_behavior'] = 'selected_gold_menu' if len(case['expected_ids']) == 1 else 'needs_clarification'
        start = time.perf_counter()
        try:
            request = urllib.request.Request(args.url,data=json.dumps({'message':case['query']}).encode(),headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(request,timeout=35) as response:
                body = json.load(response)
            # Preserve API response before validation, including provider call evidence.
            row['response'] = body
            ids, selected = validate_response(body,catalog_hash,known_ids)
            row.update(candidate_ids=ids, selected_ids=selected,status=body['status'],confidence=body['confidence'],
                       retrieval_ms=body.get('retrievalMs'),selection_ms=body.get('selectionMs'),jev_calls=body['jevCalls'],
                       same_candidates_as_recall_run=ids==old_candidates[case['case_id']])
            consecutive_errors = 0
        except urllib.error.HTTPError as error:
            # Deliberately do not log credentials or provider error bodies.
            row.update(error='HTTP '+str(error.code),status='error')
            consecutive_errors += 1
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as error:
            row.update(error=type(error).__name__+': '+str(error),status='error')
            consecutive_errors += 1
        row['http_ms'] = (time.perf_counter()-start)*1000
        row['policy_success'] = successful(row)
        rows.append(row)
        save()
        if len(rows) % 10 == 0 or row.get('error'):
            print(f"{len(rows)}/300 status={row['status']} policy_success={row['policy_success']}",flush=True)
        if consecutive_errors >= 3:
            raise SystemExit('Stopped after three consecutive errors; partial run preserved, no retries')
    data = save(complete=True)
    print(json.dumps(data['summary'],ensure_ascii=False),flush=True)

if __name__ == '__main__':
    main()
