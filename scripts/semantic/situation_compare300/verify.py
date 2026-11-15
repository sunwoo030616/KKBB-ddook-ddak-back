"""Recompute completed multi-menu comparison without any external calls."""
import json
from pathlib import Path
from common import sha
from metrics import case_metrics,summary
from run import ROOT,HERE,MODELS
r=json.loads((ROOT/'docs/situation-compare300/results.json').read_text())
assert r['complete'] and len(r['results'])==600
assert r['freeze']==json.loads((HERE/'freeze.json').read_text())
for name,digest in r['freeze']['files'].items():assert sha(ROOT/name)==digest,name
cases=json.loads((HERE/'cases.json').read_text());assert len(cases)==300
known={m['id'] for m in json.loads((ROOT/'src/main/resources/kb_starbanking_menu_structure_cleaned.json').read_text())['menus']}
for i,case in enumerate(cases):
 pair=r['results'][2*i:2*i+2]
 assert [x['provider'] for x in pair]==(list(MODELS) if i%2==0 else list(reversed(MODELS)))
 for row in pair:
  assert all(row[k]==v for k,v in case.items())
  assert row['score']==case_metrics(row)
  assert set(row.get('selected_ids',[]))<=known
  for call in row['calls']:assert call['provider']==row['provider']
  if not row.get('error') and row['provider']=='e5_jev':
   assert len(row['calls'])==row['metrics']['jevCalls']
   for rec in row['recommendations']:
    assert rec['menu']['id'] in row['candidateIdsByNeed'][rec['needId']]
for p in MODELS:
 rows=[x for x in r['results'] if x['provider']==p];assert len(rows)==300
 assert r['summary'][p]==summary(rows)
 for group,s in r['by_split'][p].items():assert s==summary([x for x in rows if x['split']==group])
print('Verified 600 paired rows; all frozen hashes, unchanged labels, alternating order, set scores, split summaries, raw provider usage sums, and selected-menu candidate membership')
