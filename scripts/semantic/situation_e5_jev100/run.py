# coding: utf-8
"""Actual E5(original query)→JEV multi-menu ablation; zero generative LLM calls."""
import argparse,json,time,datetime,hashlib,sys,urllib.request,urllib.error,math
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];sys.path.insert(0,str(HERE.parent/'situation_v3'));sys.path.insert(0,str(HERE.parent/'situation_goal100'))
from common import sha,load_keys
from goal_metrics import case_metrics,summary
from selection import select
MODEL='jev-1.14.0'
def main():
 p=argparse.ArgumentParser();p.add_argument('--intellij-config',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--freeze',type=Path,required=True);a=p.parse_args();a.output=a.output.resolve();assert not a.output.exists()
 freeze=json.loads(a.freeze.read_text())
 for rel,h in freeze['files'].items():assert sha(ROOT/rel)==h,rel
 env=load_keys(a.intellij_config);key=env['JEV_AI_API_KEY'];cases=json.loads((ROOT/'scripts/semantic/situation_goal100/cases.json').read_text());raw=(ROOT/'src/main/resources/kb_starbanking_menu_structure_cleaned.json').read_bytes();digest=hashlib.sha256(raw).hexdigest();menus={m['id']:m for m in json.loads(raw)['menus']};policy=(HERE/'policy.txt').read_text();a.output.parent.mkdir(parents=True,exist_ok=False);rows=[];started=datetime.datetime.now(datetime.timezone.utc).isoformat()
 def save(complete=False):
  d={'complete':complete,'started_at':started,'updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'freeze':freeze,'cases_path':'scripts/semantic/situation_goal100/cases.json','planned_cases':100,'providers':['e5_jev_only'],'models':{'e5':'intfloat/multilingual-e5-small','e5_revision':'614241f622f53c4eeff9890bdc4f31cfecc418b3','jev':MODEL},'settings':{'candidate_k':80,'noul_threshold':.7,'max_recommendations':3,'llm_calls':0,'candidate_k_chosen_after_local_coverage_audit':True},'results':rows,'summary':{'e5_jev_only':summary(rows)}}
  tmp=a.output.with_suffix('.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');tmp.replace(a.output)
 def post(url,payload,headers=None,timeout=40):
  req=urllib.request.Request(url,data=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode(),headers={'Content-Type':'application/json',**(headers or {})})
  with urllib.request.urlopen(req,timeout=timeout) as response:return json.load(response)
 save();failures=0
 for index,case in enumerate(cases,1):
  attempt=0
  while True:
   attempt+=1;start=time.perf_counter();row={**case,'provider':'e5_jev_only','calls':[]};call=None
   try:
    retrieval=post('http://127.0.0.1:18701/search',{'message':case['query'],'limit':80,'catalog_sha256':digest},timeout=15);candidate_ids=retrieval['ids'];assert retrieval['catalog_sha256']==digest and len(candidate_ids)==80 and set(candidate_ids)<=set(menus)
    candidates=[{'id':mid,'name':menus[mid]['name'],'purpose':menus[mid]['description'],'when':menus[mid]['select_when']} for mid in candidate_ids]
    questions={mid:{'type':'noul','instructions':'후보 메뉴 「'+mid+' / '+menus[mid]['name']+'」를 사용자의 현재 목표를 진전시키는 다음 행동으로 제안하는 것이 적절한가?','criteria':{'true':'원문의 목표에 직접 도움이 되는 처리·준비·정보 확인이며, 완료·제외되지 않았고 근거 없는 전제를 추가하지 않는다.','false':'단순 주제 연관·불필요한 상품 권유·완료/제외 업무·잘못 가정한 대상·목표와 무관한 기능이다.'}} for mid in candidate_ids}
    payload={'model':MODEL,'state':{'user_request':case['query'],'policy':policy,'candidates':candidates},'questions':questions};t=time.perf_counter();call={'provider':'e5_jev','stage':'candidate_judgement','model_requested':MODEL,'request_payload_bytes':len(json.dumps(payload,ensure_ascii=False).encode())}
    try:
     response=post('https://api.typesafe.ai/v1/systemone',payload,{'Authorization':'Bearer '+key},timeout=40);call.update(http_status=200,model=response.get('model'),usage=response.get('usage'),answers=response.get('answers'))
    except urllib.error.HTTPError as e:
     call.update(http_status=e.code,error='HTTP '+str(e.code))
     try:detail=json.loads(e.read()).get('error',{});call['error_detail']={k:detail.get(k) for k in ['code','type']}
     except Exception:pass
     raise
    finally:
     call['provider_http_ms']=(time.perf_counter()-t)*1000;row['calls']=[call]
     with open(a.output.parent/'upstream-calls.jsonl','a') as f:f.write(json.dumps(call,ensure_ascii=False)+'\n')
    selected,probabilities=select(candidate_ids,response['answers']);row.update(status='ready' if selected else 'needs_clarification',selected_ids=selected,candidate_ids=candidate_ids,candidate_probabilities=probabilities,retrieval_ms=retrieval['duration_ms'],catalog_sha256=digest)
    failures=0
   except urllib.error.HTTPError as e:row.update(status='error',error='HTTP '+str(e.code));failures+=1
   except Exception as e:row.update(status='error',error=type(e).__name__);failures+=1
   row['http_ms']=(time.perf_counter()-start)*1000
   if call and call.get('http_status')==429 and attempt<4:
    with open(a.output.parent/'excluded-quota-attempts.jsonl','a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    failures=0;time.sleep(5);continue
   row['score']=case_metrics(row);rows.append(row);save();print(index,row['status'],'accepted_set_exact',row['score']['status_and_menu_exact'],'menus',row.get('selected_ids',[]),'ms',round(row['http_ms']),flush=True)
   if failures>=3:raise RuntimeError('Three consecutive errors; incomplete data preserved')
   break
 save(True);print('Completed 100 actual E5→JEV cases; no LLM calls',flush=True)
if __name__=='__main__':main()
