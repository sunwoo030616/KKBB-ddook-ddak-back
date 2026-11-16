"""Verify final paired or regression data, allowing audited quota-only replacement."""
import argparse,json,sys,collections
from pathlib import Path
HERE=Path(__file__).resolve().parent;BASE=HERE.parent/'situation_v3';sys.path.insert(0,str(BASE))
from metrics import summary,case_metrics
from common import sha
ROOT=HERE.parents[2]
p=argparse.ArgumentParser();p.add_argument('result',type=Path);a=p.parse_args();d=json.loads(a.result.read_text());assert d['complete']
for name,digest in d['freeze']['files'].items():assert sha(ROOT/name)==digest,name
cases=json.loads((ROOT/d['cases_path']).read_text());assert len(cases)==d['planned_cases']
assert len(d['results'])==len(cases)*len(d['providers'])
known={m['id'] for m in json.loads((ROOT/'src/main/resources/kb_starbanking_menu_structure_cleaned.json').read_text())['menus']}
for i,case in enumerate(cases):
 rows=d['results'][i*len(d['providers']):(i+1)*len(d['providers'])]
 assert [r['provider'] for r in rows]==(d['providers'] if i%2==0 else list(reversed(d['providers'])))
 for r in rows:
  assert all(r[k]==v for k,v in case.items());assert r['score']==case_metrics(r)
  assert not any(c.get('http_status')==429 for c in r['calls']),'Quota errors must be replaced, not hidden'
  if r.get('error'):continue
  assert len(r['selected_ids'])<=8 and len(set(r['selected_ids']))==len(r['selected_ids']) and set(r['selected_ids'])<=known
  if r['provider']=='hybrid':
   assert len(r['calls'])==1+r['metrics']['jevCalls']
   assert r['metrics']['retrievalMode']=='llm_planner_e5_jev'
   for rec in r['recommendations']:assert rec['menu']['id'] in r['candidateIdsByNeed'][rec['needId']]
  else:
   assert len(r['calls'])==1 and r['calls'][0]['model']=='gpt-4.1-2025-04-14'
   raw=json.loads(r['calls'][0]['baseline_content']);assert raw['selected_ids']==r['selected_ids'] and raw['status']==r['status']
for provider in d['providers']:
 rows=[r for r in d['results'] if r['provider']==provider];assert d['summary'][provider]==summary(rows)
 for split,s in d['by_split'][provider].items():assert s==summary([r for r in rows if r['split']==split])
audit=[json.loads(l) for l in (a.result.parent/'upstream-calls.jsonl').read_text().splitlines()]
excluded_file=a.result.parent/'excluded-quota-attempts.jsonl';excluded=[json.loads(l) for l in excluded_file.read_text().splitlines()] if excluded_file.exists() else []
assert all(any(c.get('http_status')==429 for c in x['calls']) for x in excluded)
encode=lambda c:json.dumps(c,sort_keys=True,ensure_ascii=False)
assert collections.Counter(map(encode,audit))==collections.Counter(encode(c) for r in d['results'] for c in r['calls'])+collections.Counter(encode(c) for r in excluded for c in r['calls'])
print('Verified:',len(cases),'cases;',d['providers'],'; frozen source/labels, exact sets/status, model IDs, actual candidates, all usage, and separated quota attempts')
