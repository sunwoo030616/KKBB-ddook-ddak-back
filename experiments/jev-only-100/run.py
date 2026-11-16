"""Frozen 100-case Jev-only benchmark: no E5 retrieval or embedding use.
All 585 menus judged in deterministic chunks (<=80); four in-flight chunks;
global Noul >= .30 top10; identical 3-menu Choice policy as E5/Jev v2.
"""
import argparse, concurrent.futures, hashlib, json, math, os, statistics, time
import urllib.request, urllib.error, xml.etree.ElementTree as ET
from pathlib import Path
from set_selection import build_choice,decode
from partial_metrics import partial_summary
ROOT=Path(__file__).resolve().parent
MODEL='jev-1.14.0';CHUNK_SIZE=80;WORKERS=4
FIELDS=('id','name','purpose','when')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def compact(x):return json.dumps(x,ensure_ascii=False,separators=(',',':')).encode()
def payload(query,chunk,policy):
 menus=[{'id':m['id'],'name':m['name'],'purpose':m['description'],'when':m['select_when']} for m in chunk]
 questions={m['id']:{'type':'noul','instructions':'후보 메뉴 「'+m['id']+' / '+m['name']+'」를 사용자의 현재 목표를 진전시키는 다음 행동으로 제안하는 것이 적절한가?','criteria':{'true':'원문의 목표에 직접 도움이 되는 처리·준비·정보 확인이며, 완료·제외되지 않았고 근거 없는 전제를 추가하지 않는다.','false':'단순 주제 연관·불필요한 상품 권유·완료/제외 업무·잘못 가정한 대상·목표와 무관한 기능이다.'}} for m in chunk}
 return {'model':MODEL,'state':{'user_request':query,'policy':policy,'candidates':menus},'questions':questions}
def chunks(menus):return [menus[i:i+CHUNK_SIZE] for i in range(0,len(menus),CHUNK_SIZE)]
def pool_from(ids,probs):
 assert len(ids)==len(set(ids)) and set(probs)==set(ids)
 return sorted((i for i in ids if probs[i]>=.3),key=lambda i:(-probs[i],ids.index(i)))[:10]
def describe(rows):
 s=partial_summary(rows);times=sorted(r['http_ms'] for r in rows);calls=[c for r in rows for c in r['calls'] if c.get('http_status')==200]
 s.update(mean_http_ms=statistics.mean(times) if times else None,p95_http_ms=times[math.ceil(.95*len(times))-1] if times else None,input_tokens=sum(c['usage']['input_tokens'] for c in calls),output_tokens=sum(c['usage']['output_tokens'] for c in calls),successful_api_calls=len(calls),all_api_attempts=sum(len(r['calls']) for r in rows),accepted_set_correct=sum(not r.get('error') and r['status']==r['expected_status'] and set(r['selected_ids']) in [set(a) for a in r['acceptable_sets']] for r in rows))
 s['estimated_api_usd']=s['input_tokens']*.042/1e6;return s

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--execute',action='store_true');ap.add_argument('--intellij-config',type=Path);ap.add_argument('--limit',type=int,default=100);a=ap.parse_args()
 cases=json.loads((ROOT/'cases.json').read_text());catalog=json.loads((ROOT/'catalog.json').read_text())['menus'];policy=(ROOT/'policy.txt').read_text();ids=[m['id'] for m in catalog];byid={m['id']:m for m in catalog};parts=chunks(catalog)
 assert len(cases)==100 and len(ids)==585 and len(set(ids))==585
 freeze=json.loads((ROOT/'freeze.json').read_text())
 for name,h in freeze['files'].items():assert sha(ROOT/name)==h,name
 sizes=[len(compact(payload(cases[0]['query'],c,policy))) for c in parts]
 if not a.execute:
  print(json.dumps({'dry_run':True,'cases':len(cases),'menus':len(ids),'chunk_sizes':list(map(len,parts)),'concurrent_chunks':WORKERS,'max_calls_per_case':len(parts)+1,'max_normal_calls_100':(len(parts)+1)*100,'first_query_request_bytes':sizes,'labels_sent':False,'e5_calls':0,'e5_vector_use':False}));return
 key=os.environ.get('JEV_AI_API_KEY')
 if not key and a.intellij_config:
  for config in ET.parse(a.intellij_config).getroot().iter('configuration'):
   if config.get('name')=='KbAiBackendApplication':
    for e in config.iter('env'):
     if e.get('name')=='JEV_AI_API_KEY':key=e.get('value')
 if not key:raise ValueError('Missing Jev key; key value never logged')
 out=ROOT/'results.json';rows=[]
 if out.exists():
  previous=json.loads(out.read_text());assert previous['freeze']==freeze;rows=previous['results'];assert [r['case_id'] for r in rows]==[c['case_id'] for c in cases[:len(rows)]]
 def save():
  d={'complete':len(rows)==100,'protocol':freeze['protocol'],'freeze':freeze,'results':rows,'summary':describe(rows) if rows else {}}
  tmp=out.with_suffix('.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n');tmp.replace(out)
 def call(p,stage,chunk_index=None):
  encoded=compact(p);records=[]
  for attempt in range(1,4):
   record={'stage':stage,'chunk_index':chunk_index,'attempt':attempt,'model_requested':MODEL,'payload_sha256':hashlib.sha256(encoded).hexdigest(),'payload_bytes':len(encoded)};start=time.perf_counter()
   try:
    req=urllib.request.Request('https://api.typesafe.ai/v1/systemone',data=encoded,headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
    with urllib.request.urlopen(req,timeout=45) as response:result=json.load(response)
    assert result.get('model')==MODEL
    u=result.get('usage',{});assert all(isinstance(u.get(k),int) for k in ['input_tokens','output_tokens'])
    record.update(http_status=200,usage=u,answers=result['answers'],model=result['model']);return result,records+[record]
   except urllib.error.HTTPError as e:
    record.update(http_status=e.code,error='HTTP '+str(e.code))
    try:record['error_code']=json.loads(e.read()).get('error',{}).get('code')
    except Exception:pass
    records.append(record)
    if e.code==429 and attempt<3:
     time.sleep(min(15,max(2,float(e.headers.get('Retry-After','3')))));continue
    return None,records
   except Exception as e:
    record.update(error=type(e).__name__);return None,records+[record]
   finally:record['http_ms']=(time.perf_counter()-start)*1000
 save()
 for case in cases[len(rows):a.limit]:
  start=time.perf_counter();row={**case,'provider':'jev_only_chunked','calls':[],'catalog_sha256':sha(ROOT/'catalog.json'),'candidate_ids':ids,'selected_ids':[]};prob={}
  with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as executor:
   jobs=[executor.submit(call,payload(case['query'],c,policy),'candidate_judgement',i) for i,c in enumerate(parts)]
   for i,job in enumerate(jobs):
    result,logs=job.result();row['calls'].extend(logs)
    if result is None:row['error']='candidate_api_error';continue
    try:
     expected={m['id'] for m in parts[i]};assert set(result['answers'])==expected
     for mid,ans in result['answers'].items():
      v=ans.get('noul');assert ans.get('type')=='noul' and isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and 0<=v<=1;prob[mid]=v
    except Exception:row['error']='invalid_candidate_answer'
  row['candidate_probabilities']=prob
  if not row.get('error'):
   pool=pool_from(ids,prob);row['shortlist']=pool
   if pool:
    p,mapping=build_choice(case['query'],pool,byid,policy);result,logs=call({'model':MODEL,**p},'set_choice');row['calls'].extend(logs);row['set_mapping']=mapping
    if result:
     try:row['selected_ids'],row['status'],row['set_confidence']=decode(result,mapping)
     except Exception:row['error']='invalid_choice_answer'
    else:row['error']='choice_api_error'
   else:row['status']='needs_clarification'
  if row.get('error'):row['status']='error'
  row['http_ms']=(time.perf_counter()-start)*1000;rows.append(row);save()
  print(json.dumps({'n':len(rows),'case_id':case['case_id'],'status':row['status'],'selected':row['selected_ids'],'ms':round(row['http_ms']),'partial_hit':bool(set(row['selected_ids'])&set().union(*map(set,case['acceptable_sets']))),'errors':[(c.get('http_status'),c.get('error_code')) for c in row['calls'] if c.get('http_status')!=200]},ensure_ascii=False),flush=True)
  if row.get('error'):raise RuntimeError('API/schema failure; saved incomplete run and stopped')
 print(json.dumps(describe(rows),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
