"""Real original-query E5 retrieval coverage; no external API calls."""
import json,urllib.request,hashlib,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'docs/situation-e5-jev100'
raw=(ROOT/'src/main/resources/kb_starbanking_menu_structure_cleaned.json').read_bytes();digest=hashlib.sha256(raw).hexdigest();cases=json.loads((ROOT/'scripts/semantic/situation_goal100/cases.json').read_text());rows=[]
for c in cases:
 req=urllib.request.Request('http://127.0.0.1:18701/search',data=json.dumps({'message':c['query'],'limit':100,'catalog_sha256':digest}).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=15) as response:r=json.load(response)
 assert r['catalog_sha256']==digest and len(r['ids'])==100 and len(set(r['ids']))==100
 allowed=set().union(*map(set,c['acceptable_sets']));rows.append({'case_id':c['case_id'],'family_id':c['family_id'],'query':c['query'],'ids':r['ids'],'duration_ms':r['duration_ms'],'allowed_ranks':[i+1 for i,mid in enumerate(r['ids']) if mid in allowed],'required_groups':c['required_groups']})
summary={str(k):{'at_least_one_allowed':sum(any(rank<=k for rank in r['allowed_ranks']) for r in rows),'mean_required_group_recall':statistics.mean(sum(bool(set(r['ids'][:k])&set(g['acceptable_ids'])) for g in r['required_groups'])/len(r['required_groups']) for r in rows)} for k in [5,10,20,40,80,100]}
(OUT/'retrieval-audit.json').write_text(json.dumps({'catalog_sha256':digest,'cases':100,'summary':summary,'results':rows},ensure_ascii=False,indent=2)+'\n');print(summary)
