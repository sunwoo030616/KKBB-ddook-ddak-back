"""Recompute actual 300-case final selection metrics, provenance and per-case validity."""
import json
from evaluate import ROOT, HERE, sha, summarize, successful, validate_response

out=ROOT/'docs/jev300'
r=json.loads((out/'results.json').read_text())
cases=json.loads((ROOT/'scripts/semantic/recall300/cases.json').read_text())
assert r['complete'] and r['planned_cases']==len(r['results'])==len(cases)==300
assert r['freeze']==json.loads((HERE/'freeze.json').read_text())
for name,digest in r['freeze']['files'].items():
    assert sha(ROOT/name)==digest,name
assert r['summary']==summarize(r['results'])
for field,key in [('question_type','by_type'),('domain','by_domain')]:
    for group,s in r[key].items():
        assert s==summarize([row for row in r['results'] if row[field]==group])
catalog=ROOT/'src/main/resources/kb_starbanking_menu_structure_cleaned.json'
known_ids={m['id'] for m in json.loads(catalog.read_text())['menus']}
prior={row['case_id']:row for row in json.loads((ROOT/'docs/recall300/results.json').read_text())['results']}
for case,row in zip(cases,r['results']):
    assert all(row[k]==v for k,v in case.items())
    assert row['policy_success']==successful(row)
    if not row.get('error'):
        ids, selected=validate_response(row['response'],sha(catalog),known_ids)
        assert ids==row['candidate_ids'] and selected==row['selected_ids']
        assert row['same_candidates_as_recall_run']==(ids==prior[case['case_id']]['candidate_ids'][:40])
print('Verified: all 300 cases and frozen inputs, actual response constraints, final-selection/clarification scores, all type/domain aggregates, and prior E5 candidate comparisons')
