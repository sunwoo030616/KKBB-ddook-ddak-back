"""One fixed MMR ablation using actual E5 menu vectors and saved actual JEV probabilities.
This is offline development on exposed cases, not new end-to-end measurement.
"""
from pathlib import Path
import json,sys,hashlib,time
import numpy as np
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'situation_goal100'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'situation_v3'))
from partial_metrics import partial_summary
from goal_metrics import case_metrics
raw=(ROOT/'src/main/resources/kb_starbanking_menu_structure_cleaned.json').read_bytes();digest=hashlib.sha256(raw).hexdigest();menus=json.loads(raw)['menus'];index={m['id']:i for i,m in enumerate(menus)}
path=Path('/private/tmp/kkbb-e5-model')/f'menus-v2-{digest}-614241f622f53c4eeff9890bdc4f31cfecc418b3.npz'
with np.load(path,allow_pickle=False) as f:v=f['vectors']
assert v.shape==(585,384) and np.isfinite(v).all()
d=json.loads((ROOT/'docs/situation-e5-jev100/run/results.json').read_text());assert d['complete'];rows=[]
for r in d['results']:
 if r.get('error'):rows.append(r);continue
 start=time.perf_counter();remaining=[i for i in r['candidate_ids'] if r['candidate_probabilities'][i]>=.7];picked=[]
 while remaining and len(picked)<3:
  def score(mid):
   redundancy=max(float(v[index[mid]]@v[index[chosen]]) for chosen in picked) if picked else 0
   return .7*r['candidate_probabilities'][mid]-.3*redundancy
  best=max(remaining,key=score);picked.append(best);remaining.remove(best)
 out={**r,'selected_ids':picked,'status':'ready' if picked else 'needs_clarification','offline_rerank_ms':(time.perf_counter()-start)*1000};out['score']=case_metrics(out);rows.append(out)
result={'method':'fixed MMR lambda0.7, original probability threshold0.7 and max3; cosine from actual E5 vectors','not_new_api_measurement':True,'baseline':partial_summary(d['results']),'mmr':partial_summary(rows),'results':rows}
(ROOT/'docs/situation-e5-jev100/diversity-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('saved-API original',result['baseline']['partial_hit_correct'],'fixed-MMR offline',result['mmr']['partial_hit_correct'])
