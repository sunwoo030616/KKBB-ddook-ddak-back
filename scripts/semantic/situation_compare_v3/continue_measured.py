"""Resume unchanged inference with quota-only replacement and explicit excluded-attempt audit."""
import argparse,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;BASE=HERE.parent/'situation_v3';sys.path.insert(0,str(BASE))
p=argparse.ArgumentParser();p.add_argument('--mode',choices=['paired','regression'],required=True);p.add_argument('--prior',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a,rest=p.parse_known_args()
assert not a.output.exists();prior=json.loads(a.prior.read_text());kept=[r for r in prior['results'] if not any(c.get('http_status')==429 for c in r['calls'])]
a.output.parent.mkdir(parents=True,exist_ok=False);seed=dict(prior,complete=False,results=kept)
a.output.write_text(json.dumps(seed,ensure_ascii=False,indent=2)+'\n')
(a.output.parent/'upstream-calls.jsonl').write_text(''.join(json.dumps(c,ensure_ascii=False)+'\n' for r in kept for c in r['calls']))
(a.output.parent/'continuation-policy.json').write_text(json.dumps({'prior':str(a.prior.resolve()),'preserved_nonquota_rows':len(kept),'excluded_prior_quota_rows':len(prior['results'])-len(kept),'quota_only_replacement_authorized':True,'excluded_quota_tokens':True},indent=2)+'\n')
sys.argv=[sys.argv[0],'--output',str(a.output.resolve()),*rest]
def transform(source):
 source=source.replace("if args.output.exists():raise ValueError('Refuse to overwrite prior run')", "prior=json.loads(args.output.read_text());assert not prior['complete']")
 source=source.replace("calls=[];rows=[];template=", "calls=[json.loads(line) for line in (args.output.parent/'upstream-calls.jsonl').read_text().splitlines()];rows=prior['results'];assert len(calls)==sum(len(r['calls']) for r in rows);template=")
 source=source.replace("started=datetime.datetime.now(datetime.timezone.utc).isoformat();processes=[]", "started=prior['started_at'];processes=[]")
 source=source.replace("f=open(out/name,'w');logs.append(f)","f=open(out/name,'a');logs.append(f)")
 source=source.replace('from rate_gate import wait as shared_wait','from rate_window import wait as shared_wait')
 if 'from rate_window import' not in source:source=source.replace('from common import sha,load_keys,usage_counts','from common import sha,load_keys,usage_counts\nfrom rate_window import wait as shared_wait')
 # Final row ordering remains the planned alternating-provider ordering, even when prior successes have gaps.
 source=source.replace('def save(complete=False):','def save(complete=False):\n  order={(c["case_id"],p):i*len(providers)+j for i,c in enumerate(cases) for j,p in enumerate(providers if i%2==0 else list(reversed(providers)))}\n  rows.sort(key=lambda r:order[(r["case_id"],r["provider"])])')
 start=source.index('     queued=',source.index('for i,case in enumerate(cases):'));end=source.index('   final=save(True)',start);block=source[start:end]
 # The original frozen source has no shared queue; the paired source does.
 if 'queued=shared_wait' not in block:block=block.replace("queued=queue_wait() if provider=='llm_full_catalog' else 0;", "queued=shared_wait(28000 if provider=='llm_full_catalog' else 21000);")
 marker="     row['score']=case_metrics(row);rows.append(row);save()"
 assert marker in block
 quota="""     if any(c.get('http_status')==429 for c in row['calls']) and attempt<4:
      excluded={'case_id':case['case_id'],'provider':provider,'attempt':attempt,'http_ms':row['http_ms'],'calls':row['calls'],'excluded_from_comparison_tokens':True}
      with open(out/'excluded-quota-attempts.jsonl','a') as f:f.write(json.dumps(excluded,ensure_ascii=False)+'\\n')
      failures[provider]=0
      print('Quota-only retry scheduled; original attempt excluded:',case['case_id'],provider,flush=True)
      continue
"""
 block=block.replace(marker,quota+marker)
 source=source[:start]+"     if any(r['case_id']==case['case_id'] and r['provider']==provider for r in rows):continue\n     attempt=0\n     while True:\n      attempt+=1\n"+''.join(' '+line+'\n' for line in block.splitlines())+'      break\n'+source[end:]
 return source
if a.mode=='paired':
 path=HERE/'paired.py';wrapper=path.read_text();old="exec(compile(source,str(path),'exec'),{'__file__':str(path),'__name__':'__main__'})";assert old in wrapper
 wrapper=wrapper.replace(old,"source=transform(source)\n"+old)
 exec(compile(wrapper,str(path),'exec'),{'__file__':str(path),'__name__':'__main__','transform':transform})
else:
 path=BASE/'run.py';source=transform(path.read_text());exec(compile(source,str(path),'exec'),{'__file__':str(path),'__name__':'__main__'})
