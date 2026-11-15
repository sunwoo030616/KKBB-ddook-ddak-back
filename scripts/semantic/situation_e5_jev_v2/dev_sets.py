"""Paid development of set choice using saved genuine per-menu Jev judgements."""
import json,sys,time,argparse,hashlib,datetime,urllib.request,urllib.error
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];sys.path.insert(0,str(HERE.parent/'situation_v3'));sys.path.insert(0,str(HERE.parent/'situation_goal100'))
from common import load_keys,usage_counts
from partial_metrics import partial_summary
from set_selection import shortlist,build_choice,decode
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--intellij-config',type=Path,required=True);a=p.parse_args();assert not a.output.exists();a.output.parent.mkdir(parents=True,exist_ok=False)
key=load_keys(a.intellij_config)['JEV_AI_API_KEY'];raw=(ROOT/'src/main/resources/kb_starbanking_menu_structure_cleaned.json').read_bytes();digest=hashlib.sha256(raw).hexdigest();ordered=json.loads(raw)['menus'];menus={m['id']:m for m in ordered};index={m['id']:i for i,m in enumerate(ordered)}
with np.load(Path('/private/tmp/kkbb-e5-model')/f'menus-v2-{digest}-614241f622f53c4eeff9890bdc4f31cfecc418b3.npz',allow_pickle=False) as f:vectors=f['vectors']
prior=json.loads((ROOT/'docs/situation-e5-jev100/run/results.json').read_text());cases=[r for r in prior['results'] if r['case_id'].endswith(('_01','_06'))];assert len(cases)==20
policy=(ROOT/'scripts/semantic/situation_e5_jev100/policy.txt').read_text();rows=[]
for r in cases:
 pool=shortlist(r['candidate_ids'],r['candidate_probabilities'],vectors,index);payload,mapping=build_choice(r['query'],pool,menus,policy);payload['model']='jev-1.14.0';t=time.perf_counter();record={'provider':'e5_jev','stage':'set_choice'}
 try:
  req=urllib.request.Request('https://api.typesafe.ai/v1/systemone',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
  with urllib.request.urlopen(req,timeout=40) as response:body=json.load(response)
  record.update(usage=body.get('usage'),answers=body.get('answers'),model=body.get('model'),http_status=200);selected,status,conf=decode(body,mapping);row={**r,'selected_ids':selected,'status':status,'set_confidence':conf,'shortlist':pool,'set_mapping':mapping,'set_call':record}
 except urllib.error.HTTPError as e:record.update(http_status=e.code,error='HTTP '+str(e.code));row={**r,'selected_ids':[],'status':'error','error':'HTTP '+str(e.code),'set_call':record}
 record['http_ms']=(time.perf_counter()-t)*1000;rows.append(row);a.output.write_text(json.dumps({'development_only':True,'cases':20,'results':rows,'partial':partial_summary(rows)},ensure_ascii=False,indent=2)+'\n');print(r['case_id'],status if not row.get('error') else row['error'],selected if not row.get('error') else [],flush=True)
print(partial_summary(rows))
