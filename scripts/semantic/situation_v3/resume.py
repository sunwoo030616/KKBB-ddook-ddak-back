"""Resume unattempted rows only, retaining errors; add pacing and safe error diagnostics."""
from pathlib import Path
path=Path(__file__).with_name('run.py');source=path.read_text()
changes={
 "if args.output.exists():raise ValueError('Refuse to overwrite prior run')":"prior=json.loads(args.output.read_text());assert not prior['complete']",
 "calls=[];rows=[];template=":"calls=[json.loads(line) for line in (args.output.parent/'upstream-calls.jsonl').read_text().splitlines()];rows=prior['results'];assert len(calls)==sum(len(r['calls']) for r in rows);template=",
 "started=datetime.datetime.now(datetime.timezone.utc).isoformat();processes=[]":"started=prior['started_at'];processes=[]",
 "f=open(out/name,'w');logs.append(f)":"f=open(out/name,'a');logs.append(f)",
 "def queue_wait():":"last_start=[time.monotonic()-3]\n def queue_wait():\n  delay=max(0,3-(time.monotonic()-last_start[0]));time.sleep(delay);last_start[0]=time.monotonic();return delay*1000\n def unused_original_queue_wait():",
 "queued=queue_wait() if provider=='llm_full_catalog' else 0;":"if any(r['case_id']==case['case_id'] and r['provider']==provider for r in rows):continue\n     queued=queue_wait();",
 "except urllib.error.HTTPError as e:record.update(error='HTTP '+str(e.code),http_status=e.code);raise":"except urllib.error.HTTPError as e:\n   record.update(error='HTTP '+str(e.code),http_status=e.code,error_headers={k:e.headers.get(k) for k in ['retry-after','x-ratelimit-limit-tokens','x-ratelimit-remaining-tokens','x-ratelimit-limit-requests','x-ratelimit-remaining-requests','x-ratelimit-reset-tokens','x-ratelimit-reset-requests'] if e.headers.get(k)})\n   try:\n    detail=json.loads(e.read()).get('error',{});record['error_detail']={k:detail.get(k) for k in ['code','type','param']};record['error_detail']['message']=re.sub(r'(?:org-|proj-|sk-)[A-Za-z0-9_-]+','[redacted]',str(detail.get('message','')))[:1000]\n   except Exception:pass\n   raise"
}
for old,new in changes.items():assert source.count(old)==1,old;source=source.replace(old,new)
exec(compile(source,str(path),'exec'),{'__file__':str(path),'__name__':'__main__'})
