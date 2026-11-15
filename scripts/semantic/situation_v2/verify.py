"""Validate any completed v2 run without external calls."""
import argparse,json
from pathlib import Path
from common import sha
from metrics import case_metrics,summary
from run import ROOT
p=argparse.ArgumentParser();p.add_argument('result',type=Path);a=p.parse_args()
r=json.loads(a.result.read_text());assert r['complete']
cases=json.loads((ROOT/r['cases_path']).read_text());assert len(cases)==r['planned_cases']
assert len(r['results'])==len(cases)*len(r['providers'])
for name,digest in r['freeze']['files'].items():assert sha(ROOT/name)==digest,name
known={m['id'] for m in json.loads((ROOT/'src/main/resources/kb_starbanking_menu_structure_cleaned.json').read_text())['menus']}
for i,case in enumerate(cases):
 rows=r['results'][i*len(r['providers']):(i+1)*len(r['providers'])]
 assert [x['provider'] for x in rows]==(r['providers'] if i%2==0 else list(reversed(r['providers'])))
 for row in rows:
  assert all(row[k]==v for k,v in case.items())
  assert row['score']==case_metrics(row)
  assert set(row.get('selected_ids',[]))<=known
  if row.get('error'):continue
  if row['provider']=='e5_jev':
   assert len(row['calls'])==row['metrics']['jevCalls']
   for rec in row['recommendations']:
    assert rec['menu']['id'] in row['candidateIdsByNeed'][rec['needId']]
for provider in r['providers']:
 rows=[x for x in r['results'] if x['provider']==provider]
 assert r['summary'][provider]==summary(rows)
 for group,s in r['by_split'][provider].items():assert s==summary([x for x in rows if x['split']==group])
print('Verified complete run:',len(cases),'cases;',r['providers'],'; labels, hashes, set scores, raw usage, order, and candidate membership')
