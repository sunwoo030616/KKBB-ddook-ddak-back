"""Offline independent trace and aggregate verification; no model calls."""
import collections, hashlib, json, math, statistics
from pathlib import Path
from run import payload,chunks,pool_from,describe,compact,MODEL
from set_selection import build_choice,decode
ROOT=Path(__file__).resolve().parent

def main():
 d=json.loads((ROOT/'results.json').read_text());assert d['complete']
 cases=json.loads((ROOT/'cases.json').read_text());menus=json.loads((ROOT/'catalog.json').read_text())['menus'];byid={m['id']:m for m in menus};ids=list(byid);parts=chunks(menus);policy=(ROOT/'policy.txt').read_text()
 freeze=json.loads((ROOT/'freeze.json').read_text());assert d['freeze']==freeze
 for name,h in freeze['files'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h,name
 assert len(d['results'])==100
 for case,row in zip(cases,d['results']):
  assert all(row[k]==v for k,v in case.items())
  assert row['candidate_ids']==ids and row['catalog_sha256']==hashlib.sha256((ROOT/'catalog.json').read_bytes()).hexdigest()
  assert not row.get('error'),row['case_id']
  probs={};raw_calls=[c for c in row['calls'] if c.get('http_status')==200]
  for i,part in enumerate(parts):
   c=next(c for c in raw_calls if c['stage']=='candidate_judgement' and c['chunk_index']==i)
   assert c['model']==MODEL
   assert c['payload_sha256']==hashlib.sha256(compact(payload(case['query'],part,policy))).hexdigest()
   assert set(c['answers'])=={m['id'] for m in part}
   probs.update({mid:v['noul'] for mid,v in c['answers'].items()})
  assert len(probs)==585 and probs==row['candidate_probabilities']
  pool=pool_from(ids,probs);assert pool==row['shortlist']
  if pool:
   p,mapping=build_choice(case['query'],pool,byid,policy);assert mapping==row['set_mapping']
   c=next(c for c in raw_calls if c['stage']=='set_choice')
   assert c['payload_sha256']==hashlib.sha256(compact({'model':MODEL,**p})).hexdigest()
   assert decode({'answers':c['answers']},mapping)==(row['selected_ids'],row['status'],row['set_confidence'])
  assert len(row['selected_ids'])<=3 and set(row['selected_ids'])<=set(pool)
 s=describe(d['results']);assert s==d['summary']
 base=json.loads((ROOT/'baseline.json').read_text());b=json.loads((ROOT/'baseline-summary.json').read_text())
 assert len(base['results'])==100
 for case,r in zip(cases,base['results']):assert all(r[k]==v for k,v in case.items())
 # Independently rederive partial hits, P95, accepted-set and tokens for both arms.
 def calc(rows):
  hits=sum(not r.get('error') and bool(set(r['selected_ids'])&set().union(*map(set,r['acceptable_sets']))) for r in rows)
  ts=sorted(r['http_ms'] for r in rows);calls=[c for r in rows for c in r['calls'] if c.get('http_status')==200]
  return hits,statistics.mean(ts),ts[94],sum(c['usage']['input_tokens'] for c in calls),sum(c['usage']['output_tokens'] for c in calls)
 for rows,summary in [(base['results'],b),(d['results'],s)]:
  hit,mean,p95,inp,out=calc(rows);assert hit==summary['partial_hit_correct'];assert abs(mean-summary['mean_http_ms'])<1e-6;assert abs(p95-summary['p95_http_ms'])<1e-6;assert inp==summary['input_tokens'];assert out==summary['output_tokens']
 diffs=collections.Counter()
 for a,r in zip(base['results'],d['results']):
  allow=set().union(*map(set,r['acceptable_sets']));ha=bool(set(a['selected_ids'])&allow);hb=bool(set(r['selected_ids'])&allow)
  diffs['both_hit' if ha and hb else 'e5_jev_only_hit' if ha else 'jev_only_hit' if hb else 'both_miss']+=1
 families={f:describe([r for r in d['results'] if r['family_id']==f]) for f in sorted({r['family_id'] for r in d['results']})}
 audit={'baseline':b,'jev_only':s,'paired_hits':dict(diffs),'families':families,'ratio':{'mean_time':s['mean_http_ms']/b['mean_http_ms'],'p95_time':s['p95_http_ms']/b['p95_http_ms'],'cost':s['estimated_api_usd']/b['estimated_api_usd']},'case_and_label_identity_verified':True,'all_585_judged_for_every_case':True,'raw_response_and_payload_hash_replayed':True,'e5_used_by_new_arm':False,'baseline_historical_not_concurrent':True}
 (ROOT/'comparison.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
 def pct(v):return f'{v*100:.2f}%'
 table=['| 지표 | E5→JEV 개선판 (기존 실측) | JEV 단독 (이번 실측) |','|---|---:|---:|',f"| 부분 적중률 | {pct(b['partial_hit_rate'])} | {pct(s['partial_hit_rate'])} |",f"| 평균 응답 시간 | {b['mean_http_ms']/1000:.3f}초 | {s['mean_http_ms']/1000:.3f}초 |",f"| P95 응답 시간 | {b['p95_http_ms']/1000:.3f}초 | {s['p95_http_ms']/1000:.3f}초 |",f"| 100문항 API 비용 추정 | ${b['estimated_api_usd']:.6f} | ${s['estimated_api_usd']:.6f} |",f"| 입력 토큰 합계 | {b['input_tokens']:,} | {s['input_tokens']:,} |",f"| 출력 토큰 합계 (무료) | {b['output_tokens']:,} | {s['output_tokens']:,} |",f"| 성공 API 호출 수 | {b['jev_calls']} | {s['successful_api_calls']} |",f"| 추천 메뉴 중 허용 메뉴 비율 | {pct(b['menu_level_allowed_precision'])} | {pct(s['menu_level_allowed_precision'])} |",f"| 필수 업무 Macro Recall | {pct(b['macro_required_outcome_recall'])} | {pct(s['macro_required_outcome_recall'])} |",f"| 전체 조합·상태 완전 일치 | {b['accepted_set_correct']}/100 | {s['accepted_set_correct']}/100 |"]
 report=['# JEV 단독 100문항 실제 비교','',*table,'','## 측정 방법','', '같은 기존 100문항·정답/허용 메뉴 집합·모델 jev-1.14.0을 사용했다. 정답은 inference payload에 전송하지 않았다. JEV 단독은 전체585개를80개씩7묶음과25개1묶음으로 나누고 최대4개 묶음을 동시에 평가했다. 묶음마다 평가한 모든585개 Noul을 합친 뒤, 0.30이상 전역 상위10개를 고르고 기존 코드와 동일한120개 3종 조합 Choice를 적용했다. E5 임베딩·검색·MMR은 사용하지 않았다. 점수가 같으면 카탈로그 순서를 사용했다.','', '부분 적중은 허용 메뉴가 하나 이상 포함된 문항 비율이며 추가 오답이 있어도 적중으로 센다. 정확한 전체 업무 처리율과 다르므로 허용 메뉴 비율과 필수 업무 Recall, 완전일치도 함께 표시한다.','', '## 비교의 한계','', '- E5→JEV 기준은 기존 실측이며 이번과 동시에 재실행한 결과는 아니다. 네트워크·제공자 부하에 따른 시간 차이가 섞인다.','- JEV 단독 시간은4개 청크 동시 실행을 포함한 한 질문 전체의 실제 경과시간이다. 청크 시간을 더하거나 단일 API 요청 시간으로 오해하면 안 된다.','- E5를 완전히 제외하기 위해 MMR도 제외했다. 이 비교는 두 시스템 전체의 비교이고, 검색만의 인과 효과를 분리한 실험이 아니다.','- 각 청크의 문맥이 달라 Noul 점수의 청크 간 비교 가능성이 완벽히 보장되지는 않는다.','- 기존100문항은 이전 개발 과정에 노출된10상황×10표현이다. 새로운100개 상황이나 실제 서비스 일반화 검증이 아니다.','- 비용은 성공 응답의 실제 input_tokens에 공식 $0.042/백만 토큰을 곱한 추정치다. output은무료. 실패 한도시도는 비용 합계에서 제외하고 원시로그에 보존한다. CPU/운영비·세금은 제외한다. 성공 호출이 발생한 실패 문항이 있으면 그 성공 호출 사용량은 비용에 포함한다.','',f"요청 시도 {s['all_api_attempts']}회, 성공 {s['successful_api_calls']}회, 문항 오류 {s['errors']}건. 실제 청구서 금액은 아니다.",'', '공식 단가: https://help.typesafe.ai/articles/5187202169-how-much-does-jev-cost','공식 컨텍스트 제한: https://docs.typesafe.ai/models','', '원시 결과 results.json, 실행 로그 execution.log, 동결 조건 freeze.json, 재검산 comparison.json. GitHub나 Figma에 게시하지 않았다.']
 (ROOT/'README.md').write_text('\n'.join(report)+'\n')
 (ROOT/'verification.log').write_text('PASS 100 identical cases/labels; frozen inputs/source hashes; 585 menu coverage per question; all candidate payload hashes; all actual Noul scores; global top10 >= .30; Choice payload/mapping/decoding; selected ID constraints; independent partial-hit, latency/P95 and token aggregates for both arms.\n')
 print(json.dumps({k:audit[k] for k in ['baseline','jev_only','paired_hits','ratio']},ensure_ascii=False))
if __name__=='__main__':main()
