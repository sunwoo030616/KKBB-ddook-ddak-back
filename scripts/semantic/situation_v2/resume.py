# coding: utf-8
"""Resume saved rows after a console-only None formatting failure; never repeat a saved API request."""
from pathlib import Path
import json,sys
path=Path(__file__).with_name('run.py')
source=path.read_text()
changes={
 "if args.output.exists():raise ValueError('Refuse to overwrite prior run')":"prior=json.loads(args.output.read_text());assert not prior['complete']",
 "calls=[];rows=[];template=":"calls=[json.loads(line) for line in (args.output.parent/'upstream-calls.jsonl').read_text().splitlines()];rows=prior['results'];assert len(calls)==sum(len(r['calls']) for r in rows);template=",
 "started=datetime.datetime.now(datetime.timezone.utc).isoformat();processes=[]":"started=prior['started_at'];processes=[]",
 "f=open(out/name,'w');logs.append(f)":"f=open(out/name,'a');logs.append(f)",
 "queued=queue_wait() if provider=='llm_full_catalog' else 0;":"if any(r['case_id']==case['case_id'] and r['provider']==provider for r in rows):continue\n     queued=queue_wait() if provider=='llm_full_catalog' else 0;",
 "{row['score']['precision']:.2f} R={row['score']['recall']:.2f}":"{row['score']['precision']} R={row['score']['recall']}"
}
for before,after in changes.items():
 assert source.count(before)==1,before
 source=source.replace(before,after)
namespace={'__file__':str(path),'__name__':'__main__'}
exec(compile(source,str(path),'exec'),namespace)
