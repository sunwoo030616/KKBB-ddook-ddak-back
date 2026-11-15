#!/usr/bin/env python3
"""Evaluate frozen synthetic questions against the production E5 HTTP server."""
import argparse
import collections
import datetime
import hashlib
import json
import platform
import re
import time
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
KS = (1, 5, 10, 20, 40, 100)

def normalize(text):
    return re.sub(r'\W+', '', unicodedata.normalize('NFKC', text).casefold())

def metrics(rows):
    if not rows:
        return {'cases': 0, 'macro_recall': None, 'hit_rate': None}
    # Deduplicate retrieved IDs so repeats cannot inflate recall. Errors score zero.
    def recall(row, k):
        return len(set(row.get('candidate_ids', [])[:k]) & set(row['expected_ids'])) / len(set(row['expected_ids']))
    return {'cases': len(rows), 'errors': sum('error' in r for r in rows),
            'macro_recall': {str(k): sum(recall(r, k) for r in rows) / len(rows) for k in KS},
            'hit_rate': {str(k): sum(recall(r, k) > 0 for r in rows) / len(rows) for k in KS},
            'all_gold_rate': {str(k): sum(recall(r, k) == 1 for r in rows) / len(rows) for k in KS}}

def audit(cases, menus, previous):
    ids = {m['id'] for m in menus}
    if len(cases) != 300 or len({r['case_id'] for r in cases}) != 300:
        raise ValueError('Require exactly 300 unique case IDs')
    for row in cases:
        gold = row['expected_ids']
        if not row['query'].strip() or not gold or len(gold) != len(set(gold)) or set(gold) - ids:
            raise ValueError('Invalid gold or query: ' + row['case_id'])
    counts = collections.Counter(normalize(r['query']) for r in cases)
    prior = {normalize(r['query']) for r in previous}
    prior_ids = {r['expected'] for r in previous}
    # Lexical near-duplicates are candidates for review, not semantic equivalence.
    from difflib import SequenceMatcher
    near = []
    for i, a in enumerate(cases):
        for b in cases[i+1:]:
            score = SequenceMatcher(None, normalize(a['query']), normalize(b['query'])).ratio()
            if score >= .9:
                near.append([a['case_id'], b['case_id'], round(score, 4)])
    return {'normalized_duplicate_groups': sum(n > 1 for n in counts.values()),
            'near_duplicate_pairs_threshold_0_9': near,
            'prior20_exact_query_overlaps': [r['case_id'] for r in cases if normalize(r['query']) in prior],
            'prior20_target_overlaps': sorted({x for r in cases for x in r['expected_ids']} & prior_ids),
            'multi_gold_cases': sum(len(r['expected_ids']) > 1 for r in cases),
            'catalog_name_in_query_cases': sum(any(normalize(m['name']) in normalize(r['query']) for m in menus if m['id'] in r['expected_ids']) for r in cases),
            'label_reliability': 'Catalog-derived synthetic labels, no independent human review; alternatives may be missing.',
            'exposure': '270 questions reused from an already evaluated 300-set; 30 composites reuse its intents. Not held-out. No model/catalog tuning in this run.',
            'training_leakage': 'Model pretraining corpus unavailable; absence of pretraining leakage cannot be established.'}

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--search-url', default='http://127.0.0.1:18093/search')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.output.exists():
        raise ValueError('Refuse to overwrite a completed run')
    freeze = json.loads((HERE/'freeze.json').read_text())
    for name, digest in freeze['files'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen input changed: ' + name)
    cases = json.loads((HERE/'cases.json').read_text())
    menus = json.loads((ROOT/'src/main/resources/kb_starbanking_menu_structure_cleaned.json').read_text())['menus']
    previous = json.loads((ROOT/'src/test/resources/menu-selection-cases-20.json').read_text())
    audit_result = audit(cases, menus, previous)
    catalog_hash = freeze['files']['src/main/resources/kb_starbanking_menu_structure_cleaned.json']
    with urllib.request.urlopen(args.search_url.replace('/search', '/health'), timeout=10) as response:
        health = json.load(response)
    if health['catalog_sha256'] != catalog_hash or health['menus'] != len(menus):
        raise ValueError('Server catalog mismatch')
    rows = []
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    for case in cases:
        row = dict(case)
        start = time.perf_counter()
        try:
            req = urllib.request.Request(args.search_url, data=json.dumps({'message': case['query'], 'limit': 100, 'catalog_sha256': catalog_hash}).encode(), headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req, timeout=30) as response:
                body = json.load(response)
            candidates = body['ids']
            if body['catalog_sha256'] != catalog_hash or len(candidates) != 100 or len(set(candidates)) != 100 or set(candidates) - {m['id'] for m in menus}:
                raise ValueError('Invalid response catalog/ranking')
            row.update(candidate_ids=candidates, expected_ranks={g: candidates.index(g)+1 if g in candidates else None for g in case['expected_ids']})
        except Exception as exc:
            row['error'] = type(exc).__name__ + ': ' + str(exc)
        row['http_ms'] = (time.perf_counter()-start)*1000
        rows.append(row)
        if len(rows) % 20 == 0:
            print(f'Completed {len(rows)}/300', flush=True)
    output = {'started_at': started, 'completed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'server': health, 'python': platform.python_version(), 'platform': platform.platform(),
              'freeze': freeze, 'retrieval_limit':100, 'operating_top_k':40, 'jev_calls':0,
              'audit':audit_result, 'summary':metrics(rows),
              'by_type':{g:metrics([r for r in rows if r['question_type']==g]) for g in sorted({r['question_type'] for r in rows})},
              'by_domain':{g:metrics([r for r in rows if r['domain']==g]) for g in sorted({r['domain'] for r in rows})}, 'results':rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(output['summary']), flush=True)
    if output['summary']['errors']:
        raise SystemExit('Evaluation contains errors; see output')

if __name__ == '__main__':
    main()
