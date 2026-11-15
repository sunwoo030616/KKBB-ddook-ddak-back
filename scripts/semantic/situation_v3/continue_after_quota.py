"""Prepare a new final-run directory with only quota failures scheduled for replacement.
Original attempts remain immutable. No API call occurs unless --execute is explicitly set.
"""
import argparse,json,subprocess,sys,datetime
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--prior',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--execute',action='store_true');a,rest=p.parse_known_args()
assert not a.output.exists(),'Never overwrite original attempts'
d=json.loads(a.prior.read_text());quota=lambda r:any(c.get('http_status')==429 for c in r['calls'])
replaced=[r for r in d['results'] if quota(r)];kept=[r for r in d['results'] if not quota(r)]
assert replaced,'No quota-failed rows to replace'
root=Path(__file__).resolve().parents[3];cases=json.loads((root/d['cases_path']).read_text());order={c['case_id']:i for i,c in enumerate(cases)}
# Current partial run has a retained prefix. Refuse a non-prefix seed instead of corrupting row order.
assert [r['case_id'] for r in kept]==[c['case_id'] for c in cases[:len(kept)]],'Non-prefix retained rows require explicit ordered merge'
a.output.parent.mkdir(parents=True,exist_ok=False)
d.update(complete=False,results=kept,updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
sys.path.insert(0,str(Path(__file__).parent));from metrics import summary
d['summary']={'hybrid':summary(kept)};d['by_split']={'hybrid':{s:summary([r for r in kept if r['split']==s]) for s in sorted({r['split'] for r in kept})}}
a.output.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
(a.output.parent/'upstream-calls.jsonl').write_text(''.join(json.dumps(c,ensure_ascii=False)+'\n' for r in kept for c in r['calls']))
(a.output.parent/'continuation-policy.json').write_text(json.dumps({'prior':str(a.prior.resolve()),'preserved_nonquota_rows':len(kept),'quota_case_ids_to_replace':[r['case_id'] for r in replaced],'unattempted_cases':len(cases)-len(d['results'])-len(replaced),'excluded_original_quota_attempts':sum(len(r['calls']) for r in replaced),'user_authorized_replacement':True,'original_attempts_preserved':True},indent=2)+'\n')
print('Prepared preserved prefix:',len(kept),'quota replacements:',len(replaced),'remaining final requests:',len(cases)-len(kept))
if a.execute:
 subprocess.run([sys.executable,str(Path(__file__).with_name('resume.py')),'--cases',str(root/d['cases_path']),'--freeze',str(root/'scripts/semantic/situation_v3/freeze-evaluation.json'),'--providers','hybrid','--output',str(a.output.resolve()),*rest],check=True)
