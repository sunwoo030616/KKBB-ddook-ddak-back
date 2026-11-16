"""Summarize quota-attempt exclusions without inventing usage when providers omit it."""
import json,sys,collections
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];sys.path.insert(0,str(HERE.parent/'situation_v3'))
from common import usage_counts
OUT=ROOT/'docs/situation-compare-v3'
paths=[ROOT/p for p in ['docs/situation-v3/regression/results.json','docs/situation-v3/regression-completed/results.json','docs/situation-compare-v3/paired/results.json']]
excluded=[]
for p in paths:
 d=json.loads(p.read_text())
 for r in d['results']:
  if any(c.get('http_status')==429 for c in r['calls']):excluded.append({'source':str(p.relative_to(ROOT)),'case_id':r['case_id'],'provider':r['provider'],'calls':r['calls']})
for p in [OUT/'paired-final/excluded-quota-attempts.jsonl',ROOT/'docs/situation-v3/regression-final/excluded-quota-attempts.jsonl']:
 if p.exists():
  for line in p.read_text().splitlines():excluded.append({'source':str(p.relative_to(ROOT)),**json.loads(line)})
counts=collections.Counter(c['provider'] for r in excluded for c in r['calls']);known=collections.defaultdict(lambda:{'input_observed':0,'output_observed':0,'missing_usage_calls':0})
for r in excluded:
 for c in r['calls']:
  u=usage_counts(c.get('usage'));g=known[c['provider']]
  if u['input'] is None or u['output'] is None:g['missing_usage_calls']+=1
  else:g['input_observed']+=u['input'];g['output_observed']+=u['output']
result={'policy':'User requested quota-only replacement and exclusion of original quota-attempt tokens from comparison totals; original attempts preserved separately. Missing usage is unknown, not zero. Different original calls may be visible in multiple historical logs; this list counts quota-failed rows only, never retained nonquota rows.','excluded_attempt_rows':len(excluded),'excluded_upstream_calls':dict(counts),'observed_usage_and_unknowns':dict(known),'attempts':excluded}
(OUT/'quota-exclusions.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('Quota exclusions:',len(excluded),'rows;',dict(counts))
