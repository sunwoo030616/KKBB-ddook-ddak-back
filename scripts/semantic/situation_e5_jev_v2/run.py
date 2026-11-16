# coding: utf-8
"""Actual original/improved E5→JEV comparison, no OpenAI dependency or calls."""
import argparse,json,time,datetime,hashlib,sys,urllib.request,urllib.error,xml.etree.ElementTree as ET,os
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
for folder in ['situation_v3','situation_goal100','situation_e5_jev100']:sys.path.insert(0,str(HERE.parent/folder))
from common import sha
from goal_metrics import case_metrics,summary
from selection import select
from set_selection import shortlist,build_choice,decode
from retrieval import normalize,LexicalIndex,merge
MODEL='jev-1.14.0'
def load_jev_key(config):
 key=os.environ.get('JEV_AI_API_KEY')
 if not key and config:
  for c in ET.parse(config).getroot().iter('configuration'):
   if c.get('name')=='KbAiBackendApplication':
    for e in c.iter('env'):
     if e.get('name')=='JEV_AI_API_KEY':key=e.get('value')
 if not key:raise ValueError('Missing JEV_AI_API_KEY; no key value logged')
 return key

def main():
 p=argparse.ArgumentParser();p.add_argument('--intellij-config',type=Path);p.add_argument('--cases',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--freeze',type=Path,required=True);p.add_argument('--variants',nargs='+',choices=['original','improved'],default=['original','improved']);a=p.parse_args();a.output=a.output.resolve();assert not a.output.exists();freeze=json.loads(a.freeze.read_text())
 for rel,h in freeze['files'].items():assert sha(ROOT/rel)==h,rel
 key=load_jev_key(a.intellij_config);cases=json.loads(a.cases.read_text());raw=(ROOT/'src/main/resources/kb_starbanking_menu_structure_cleaned.json').read_bytes();digest=hashlib.sha256(raw).hexdigest();ordered=json.loads(raw)['menus'];menus={m['id']:m for m in ordered};index={m['id']:i for i,m in enumerate(ordered)};lexical=LexicalIndex(ordered)
 cache=Path('/private/tmp/kkbb-e5-model')/f'menus-v2-{digest}-614241f622f53c4eeff9890bdc4f31cfecc418b3.npz'
 with np.load(cache,allow_pickle=False) as f:vectors=f['vectors']
 assert vectors.shape==(len(menus),384) and np.isfinite(vectors).all()
 policy=(ROOT/'scripts/semantic/situation_e5_jev100/policy.txt').read_text();rows=[];started=datetime.datetime.now(datetime.timezone.utc).isoformat();a.output.parent.mkdir(parents=True,exist_ok=False)
 def save(complete=False):
  data={'complete':complete,'started_at':started,'updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cases_path':str(a.cases.resolve().relative_to(ROOT)),'planned_cases':len(cases),'providers':a.variants,'freeze':freeze,'models':{'e5':'intfloat/multilingual-e5-small','jev':MODEL,'openai_calls':0},'settings':{'original_k':80,'supplemented_k_max':100,'shortlist_size':10,'shortlist_noul_min':.3,'mmr_lambda':.7,'combination_size':3,'set_choice_confidence_filter':None,'role_metadata':'generic name/description patterns, no menu-ID or goal lookup','max_output_menus':3},'results':rows,'summary':{v:summary([r for r in rows if r['provider']==v]) for v in a.variants}}
  temp=a.output.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');temp.replace(a.output)
 def post(url,payload,headers=None):
  req=urllib.request.Request(url,data=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode(),headers={'Content-Type':'application/json',**(headers or {})})
  with urllib.request.urlopen(req,timeout=40) as response:return json.load(response)
 def retrieve(query,k):
  result=post('http://127.0.0.1:18701/search',{'message':query,'limit':k,'catalog_sha256':digest});assert result['catalog_sha256']==digest and len(result['ids'])==k and set(result['ids'])<=set(menus);return result['ids']
 def jev(payload,stage,row):
  payload={'model':MODEL,**payload};encoded=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode();record={'provider':'e5_jev','stage':stage,'model_requested':MODEL,'request_payload_sha256':hashlib.sha256(encoded).hexdigest(),'request_payload_bytes':len(encoded)};start=time.perf_counter()
  try:
   result=post('https://api.typesafe.ai/v1/systemone',payload,{'Authorization':'Bearer '+key});record.update(http_status=200,model=result.get('model'),usage=result.get('usage'),answers=result.get('answers'));return result
  except urllib.error.HTTPError as e:
   record.update(http_status=e.code,error='HTTP '+str(e.code))
   try:d=json.loads(e.read()).get('error',{});record['error_detail']={k:d.get(k) for k in ['code','type']}
   except Exception:pass
   raise
  finally:
   record['provider_http_ms']=(time.perf_counter()-start)*1000;row['calls'].append(record)
   with open(a.output.parent/'upstream-calls.jsonl','a') as f:f.write(json.dumps(record,ensure_ascii=False)+'\n')
 save();failures=0
 for i,case in enumerate(cases):
  for variant in (a.variants if i%2==0 else list(reversed(a.variants))):
   attempt=0
   while True:
    attempt+=1;start=time.perf_counter();row={**case,'provider':variant,'calls':[]}
    try:
     ids=retrieve(case['query'],80);original_ids=list(ids);expanded=[];lexical_ids=[]
     if variant=='improved':
      q=normalize(case['query']);expanded=retrieve(q,40) if q!=case['query'] else [];lexical_ids=lexical.search(case['query']);ids=merge(ids,expanded,lexical_ids)
     row.update(candidate_ids=ids,original_candidate_ids=original_ids,expanded_candidate_ids=expanded,lexical_candidate_ids=lexical_ids,catalog_sha256=digest)
     candidates=[{'id':mid,'name':menus[mid]['name'],'purpose':menus[mid]['description'],'when':menus[mid]['select_when']} for mid in ids]
     questions={mid:{'type':'noul','instructions':'후보 메뉴 「'+mid+' / '+menus[mid]['name']+'」를 사용자의 현재 목표를 진전시키는 다음 행동으로 제안하는 것이 적절한가?','criteria':{'true':'원문의 목표에 직접 도움이 되는 처리·준비·정보 확인이며, 완료·제외되지 않았고 근거 없는 전제를 추가하지 않는다.','false':'단순 주제 연관·불필요한 상품 권유·완료/제외 업무·잘못 가정한 대상·목표와 무관한 기능이다.'}} for mid in ids}
     result=jev({'state':{'user_request':case['query'],'policy':policy,'candidates':candidates},'questions':questions},'candidate_judgement',row)
     selected,probs=select(ids,result['answers']);status='ready' if selected else 'needs_clarification';row['candidate_probabilities']=probs
     if variant=='improved':
      pool=shortlist(ids,probs,vectors,index);row['shortlist']=pool
      if pool:
       payload,mapping=build_choice(case['query'],pool,menus,policy);result=jev(payload,'set_choice',row);selected,status,confidence=decode(result,mapping);row.update(set_mapping=mapping,set_confidence=confidence)
      else:selected=[];status='needs_clarification'
     row.update(selected_ids=selected,status=status);failures=0
    except urllib.error.HTTPError as e:row.update(status='error',error='HTTP '+str(e.code));failures+=1
    except Exception as e:row.update(status='error',error=type(e).__name__);failures+=1
    row['http_ms']=(time.perf_counter()-start)*1000
    if any(c.get('http_status')==429 for c in row['calls']) and attempt<4:
     with open(a.output.parent/'excluded-quota-attempts.jsonl','a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
     failures=0;time.sleep(5);continue
    row['score']=case_metrics(row);rows.append(row);save();print(i+1,variant,row['status'],row.get('selected_ids',[]),'ms',round(row['http_ms']),flush=True)
    if failures>=3:raise RuntimeError('Three consecutive errors; incomplete preserved')
    break
 save(True);print('Complete; zero OpenAI calls',flush=True)
if __name__=='__main__':main()
