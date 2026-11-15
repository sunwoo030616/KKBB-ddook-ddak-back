"""Recompute every aggregate from committed per-question rankings."""
import hashlib
import json
from evaluate import ROOT, HERE, metrics, audit

r=json.loads((ROOT/'docs/recall300/results.json').read_text())
cases=json.loads((HERE/'cases.json').read_text())
assert len(r['results'])==len(cases)==300
for key,digest in r['freeze']['files'].items():
    assert hashlib.sha256((ROOT/key).read_bytes()).hexdigest()==digest, key
assert r['summary']==metrics(r['results'])
for field,out in [('question_type','by_type'),('domain','by_domain')]:
    for group,summary in r[out].items():
        assert summary==metrics([x for x in r['results'] if x[field]==group])
for case,row in zip(cases,r['results']):
    assert all(row[k]==v for k,v in case.items())
    for gold,rank in row.get('expected_ranks',{}).items():
        assert rank==(row['candidate_ids'].index(gold)+1 if gold in row['candidate_ids'] else None)
menus=json.loads((ROOT/'src/main/resources/kb_starbanking_menu_structure_cleaned.json').read_text())['menus']
prior=json.loads((ROOT/'src/test/resources/menu-selection-cases-20.json').read_text())
assert r['audit']==audit(cases,menus,prior)
print('Verified: 300 rows, all input hashes, gold ranks, overall/type/domain aggregates and audit')
