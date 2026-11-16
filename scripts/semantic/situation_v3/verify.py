"""Offline verification of complete real hybrid runs, including exact sets and all provider usage."""
import json,argparse
from pathlib import Path
from common import sha
from metrics import case_metrics,summary
ROOT=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser();p.add_argument('result',type=Path);a=p.parse_args();d=json.loads(a.result.read_text());assert d['complete']
for name,digest in d['freeze']['files'].items():assert sha(ROOT/name)==digest,name
cases=json.loads((ROOT/d['cases_path']).read_text());assert len(cases)==d['planned_cases']==len(d['results'])
catalog=json.loads((ROOT/'src/main/resources/kb_starbanking_menu_structure_cleaned.json').read_text());known={m['id'] for m in catalog['menus']}
for case,row in zip(cases,d['results']):
 assert all(row[k]==v for k,v in case.items())
 assert row['provider']=='hybrid' and row['score']==case_metrics(row)
 assert len(row.get('selected_ids',[]))<=8 and set(row.get('selected_ids',[]))<=known
 if row.get('error'):continue
 assert len(row['calls'])==1+row['metrics']['jevCalls']
 assert sum(c['provider']=='llm_task_planner' for c in row['calls'])==1
 assert sum(c['provider']=='e5_jev' for c in row['calls'])==row['metrics']['jevCalls']
 assert row['metrics']['retrievalMode']=='llm_planner_e5_jev'
 assert row['raw_response']['catalogSha256']==sha(ROOT/'src/main/resources/kb_starbanking_menu_structure_cleaned.json')
 assert [x['id'] for x in row['raw_response']['menus']]==row['selected_ids']
 for rec in row['recommendations']:assert rec['menu']['id'] in row['candidateIdsByNeed'][rec['needId']]
 plan=json.loads(next(c['planner_content'] for c in row['calls'] if c['provider']=='llm_task_planner'))
 assert all(t['evidence'] in row['query'] for t in plan['tasks'])
assert d['summary']['hybrid']==summary(d['results'])
for split,s in d['by_split']['hybrid'].items():assert s==summary([r for r in d['results'] if r['split']==split])
audit=[json.loads(line) for line in (a.result.parent/'upstream-calls.jsonl').read_text().splitlines()]
assert audit==[c for r in d['results'] for c in r['calls']]
print('Verified:',len(cases),'cases; exact frozen labels/source, raw responses, candidate membership, task evidence, all calls/usage and score aggregates')
