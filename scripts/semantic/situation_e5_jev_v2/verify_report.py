# coding: utf-8
"""Offline verification/report for improved E5/Jev; no provider calls."""
from pathlib import Path
import json,sys,collections,statistics,math,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent;OUT=ROOT/'docs/situation-e5-jev-v2'
for folder in ['situation_goal100','situation_v3','situation_e5_jev100']:sys.path.insert(0,str(HERE.parent/folder))
from common import sha,usage_counts
from goal_metrics import case_metrics,summary
from partial_metrics import partial_summary
from set_selection import shortlist,build_choice,decode
from selection import select
raw=(ROOT/'src/main/resources/kb_starbanking_menu_structure_cleaned.json').read_bytes();digest=hashlib.sha256(raw).hexdigest();ordered=json.loads(raw)['menus'];menus={m['id']:m for m in ordered};index={m['id']:i for i,m in enumerate(ordered)};policy=(ROOT/'scripts/semantic/situation_e5_jev100/policy.txt').read_text()
with np.load(Path('/private/tmp/kkbb-e5-model')/f'menus-v2-{digest}-614241f622f53c4eeff9890bdc4f31cfecc418b3.npz',allow_pickle=False) as f:vectors=f['vectors']

def verify(name):
 p=OUT/name/'results.json';d=json.loads(p.read_text());assert d['complete'];cases=json.loads((ROOT/d['cases_path']).read_text());assert len(cases)==100 and len(d['results'])==100*len(d['providers'])
 for rel,h in d['freeze']['files'].items():assert sha(ROOT/rel)==h,rel
 for i,case in enumerate(cases):
  rows=d['results'][i*len(d['providers']):(i+1)*len(d['providers'])];assert [r['provider'] for r in rows]==(d['providers'] if i%2==0 else list(reversed(d['providers'])))
  for r in rows:
   assert all(r[k]==v for k,v in case.items());assert r['score']==case_metrics(r);assert all(c['provider']=='e5_jev' and c['model_requested']=='jev-1.14.0' for c in r['calls'])
   if r.get('error'):continue
   assert r['catalog_sha256']==digest and set(r['selected_ids'])<=set(r['candidate_ids']) and len(r['selected_ids'])<=3
   original,probs=select(r['candidate_ids'],r['calls'][0]['answers']);assert probs==r['candidate_probabilities']
   if r['provider']=='original':assert original==r['selected_ids'] and len(r['calls'])==1
   else:
    assert set(r['original_candidate_ids'])<=set(r['candidate_ids']) and len(r['candidate_ids'])<=100
    pool=shortlist(r['candidate_ids'],probs,vectors,index);assert pool==r['shortlist']
    if pool:
     payload,mapping=build_choice(r['query'],pool,menus,policy);assert mapping==r['set_mapping'];chosen,status,confidence=decode({'answers':r['calls'][1]['answers']},mapping);assert chosen==r['selected_ids'] and status==r['status'] and confidence==r['set_confidence']
 for v in d['providers']:assert summary([r for r in d['results'] if r['provider']==v])==d['summary'][v]
 audit=[json.loads(l) for l in (p.parent/'upstream-calls.jsonl').read_text().splitlines()];excluded_file=p.parent/'excluded-quota-attempts.jsonl';excluded=[json.loads(l) for l in excluded_file.read_text().splitlines()] if excluded_file.exists() else []
 enc=lambda c:json.dumps(c,sort_keys=True,ensure_ascii=False)
 assert collections.Counter(map(enc,audit))==collections.Counter(enc(c) for r in d['results'] for c in r['calls'])+collections.Counter(enc(c) for r in excluded for c in r['calls'])
 (p.parent/'verification.log').write_text('Verified 100 cases, frozen references/source, alternating conditions, actual E5 vectors/candidates, raw per-menu judgements, reproduced shortlist and set-choice mapping, scores/usage, zero OpenAI calls.\n')
 return d

def describe(rows):
 result=partial_summary(rows);times=sorted(r['http_ms'] for r in rows);usages=[usage_counts(c.get('usage')) for r in rows for c in r['calls']];assert all(u['input'] is not None and u['output'] is not None for u in usages)
 result.update(mean_http_ms=statistics.mean(times),p95_http_ms=times[math.ceil(.95*len(times))-1],input_tokens=sum(u['input'] for u in usages),output_tokens=sum(u['output'] for u in usages),jev_calls=sum(len(r['calls']) for r in rows),openai_calls=0,accepted_set_correct=sum(r['score']['status_and_menu_exact'] for r in rows));result['estimated_api_usd']=result['input_tokens']*.042/1e6
 return result
reg=verify('regression');fresh=verify('fresh');old=json.loads((ROOT/'docs/situation-e5-jev100/run/results.json').read_text())
result={'regression':{'old_actual':describe(old['results']),'improved':describe(reg['results'])},'fresh':{v:describe([r for r in fresh['results'] if r['provider']==v]) for v in fresh['providers']},'reference_changed':False,'new_intent_families':False,'new_expressions':100,'openai_calls':0}
# Same improved retrieval/judgement, fixed3 individual ranking, no paid re-execution.
ablation=[]
for r in reg['results']:
 if r.get('error'):ablation.append(r);continue
 rank={i:k for k,i in enumerate(r['candidate_ids'])};chosen=sorted(r['candidate_ids'],key=lambda i:(-r['candidate_probabilities'][i],rank[i]))[:3];ablation.append({**r,'selected_ids':chosen,'status':'ready'})
result['offline_fixed3_individual_on_improved_candidates']=partial_summary(ablation)
family={v:{f:describe([r for r in fresh['results'] if r['provider']==v and r['family_id']==f]) for f in sorted({r['family_id'] for r in fresh['results']})} for v in fresh['providers']};result['fresh_families']=family
pairs=collections.defaultdict(dict)
for r in fresh['results']:pairs[r['case_id']][r['provider']]=bool(set(r.get('selected_ids',[]))&set().union(*map(set,r['acceptable_sets']))) if not r.get('error') else False
result['fresh_disagreement']=dict(collections.Counter('both_correct' if p['original'] and p['improved'] else 'improved_only' if p['improved'] else 'original_only' if p['original'] else 'both_wrong' for p in pairs.values()))
(OUT/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
a=result['fresh']['original'];b=result['fresh']['improved'];ro=result['regression']['old_actual'];rn=result['regression']['improved'];pct=lambda x:f'{100*x:.2f}%'
lines=['# E5→JEV만 개선한 실제 재측정','', '**OpenAI 호출0회. 평가용 정답·허용 대체는 바꾸지 않았다.** 기존 문항은 개발 회귀, 새100개는 같은10개상황의 새로운 표현이다. 부분 적중은 허용 메뉴 하나 이상을 포함하는 경우이며 완전 업무 해결률이 아니다.', '', '## 새 표현100개: 같은 시점의 기존/개선 비교','', '| 지표 | 기존 E5→JEV | 개선 E5→JEV |','|---|---:|---:|',f"| 부분 적중률 | {a['partial_hit_correct']}/100 · {pct(a['partial_hit_rate'])} | {b['partial_hit_correct']}/100 · {pct(b['partial_hit_rate'])} |",f"| 추천 중 허용 메뉴 비율 | {pct(a['menu_level_allowed_precision'])} | {pct(b['menu_level_allowed_precision'])} |",f"| 필수 업무 Recall | {pct(a['macro_required_outcome_recall'])} | {pct(b['macro_required_outcome_recall'])} |",f"| 문항당 추천 수 | {a['mean_recommended_menus']:.2f} | {b['mean_recommended_menus']:.2f} |",f"| 일부 적중+비허용 메뉴 없음 | {a['partial_with_no_disallowed_correct']}/100 | {b['partial_with_no_disallowed_correct']}/100 |",f"| 전체 조합+상태 완전일치 | {a['accepted_set_correct']}/100 | {b['accepted_set_correct']}/100 |",f"| 평균 / P95 HTTP ms | {a['mean_http_ms']:.2f} / {a['p95_http_ms']:.2f} | {b['mean_http_ms']:.2f} / {b['p95_http_ms']:.2f} |",f"| 입력 / 출력 토큰 합계 | {a['input_tokens']:,} / {a['output_tokens']:,} | {b['input_tokens']:,} / {b['output_tokens']:,} |",f"| 100문항 API비용 추정 | ${a['estimated_api_usd']:.4f} | ${b['estimated_api_usd']:.4f} |",f"| 실제JEV 호출 | {a['jev_calls']} | {b['jev_calls']} |",'', '## 기존100개 개발 회귀','', f"부분 적중 {ro['partial_hit_correct']}% → {rn['partial_hit_correct']}%, 허용 메뉴 비율 {pct(ro['menu_level_allowed_precision'])} → {pct(rn['menu_level_allowed_precision'])}.", '', '같은 이전100문항의 단독 GPT-4.1 부분 적중은89%였다. 개선판93%가 이 점수를 넘었으나, 그100개는 개발에 노출됐으므로 독립적인 LLM우월성 검증이 아니다. 새100개에서 단독 LLM은 호출하지 않았다.', '', f"오프라인 분해 확인: 개선판의 실제 동일 검색 후보·동일 Noul판단을 그대로 두고 개별 확률 상위3개만 뽑으면 {result['offline_fixed3_individual_on_improved_candidates']['partial_hit_correct']}%, 최종 조합 선택은 {rn['partial_hit_correct']}%다. 단순히 추천 수를3개로 채운 효과만으로 전체 상승을 설명하지는 못한다. 이 분해는 새API측정이 아닌 개발 분석이다.", '', '## 변경 내용','', '1. 원문 E5 Top80은 보존하고 일반 동의어·키워드 검색의 보완 후보를 최대20개 추가했다. 실제 메뉴만 최대100개이며 가상 벡터·유사도·정답ID검색표를 쓰지 않는다.', '2. JEV의 실제 메뉴별 판단과 E5 벡터의 MMR로 후보10개를 추렸다. 메뉴 텍스트에서 연결·조회·상담·계산·실행 같은 일반 기능 역할을 표시한다.', '3. 후보가 충분하면 실제3개메뉴 조합120개 중 JEV가 하나를 선택한다. 목적별 고정 메뉴 묶음을 넣지 않았고 단계별 판단의 서로 다른 답을 가정하지 않는다. none/unsure도 가능하다.', '', '## 한계·비용·검증','', '- 처음 조합 실험은20개중15개로 실패했고 보존했다. 두 번째 개발20개는19개였다. 최종 소스·질문·정답·임계값은 최종 API실행 전에 고정했고 결과를 본 뒤 바꾸지 않았다.', '- 새100개는 10개 승인된 상황의 새표현이지 새로운100개 독립상황이 아니다. 개발과 같은 상황군·메뉴를 공유하므로 독립 일반화나 실제사용자90%보장은 아니다.', '- 개선판은 후보가 충분하면3개를 반환한다. 기존은0.7기준으로3개이하만 반환한다. 추천수 차이·추가 오답·완전일치도 표에 함께 보존한다. 부분적중93%를 필요한 일을 모두 처리한 정확도93%라고 표현하면 안 된다.', '- 원래 정답표의 은퇴자산·연결 기능 등 동등성 누락 가능성도 그대로다. 이 실험에서는 라벨을 수정해 점수를 올리지 않았다. 추가 사람검수가 필요하다.', '- 동의어·기능역할은 일반 텍스트 규칙 기반이므로 범위 밖 표현·메뉴에서 오분류할 수 있다. 별도 상황군·실사용 검증 전에는 제품에 곧바로 배포하지 않는다.', '- JEV가 조합 하나를 고른 confidence는 업무 성공확률이 아니다. 원래0.6기준을122개선택문제에 무작정 적용하지 않았고, 선택값·확률은 원시로그에 보존했다.', '- 시간은 로컬 E5/키워드 처리·실제JEV 1~2회·선택을 포함하고 기동/인덱스준비는 제외했다. 1회 실행의 네트워크·모델 변동을 포함한다.', '- 비용은 관측JEV입력×$0.042/M, 출력무료인 [공식단가](https://help.typesafe.ai/articles/5187202169-how-much-does-jev-cost)에 따른 API추정이다. 로컬E5 CPU/운영비·세금·개발비·제외한 한도오류 시도는 제외하고 청구서가 아니다.', '- 순수JEV키만 필요하며 OpenAI키/호출 의존성은 없다. 기존 프로젝트 화면/기본API를 바꾸거나 GitHub에 게시하지 않았다.', '', '원본: regression/results.json, fresh/results.json 및 각각 upstream-calls.jsonl. 각 verification.log에 오프라인검산을 남겼다. 집계: summary.json. 조건: PROTOCOL.md. 최종질문: scripts/semantic/situation_e5_jev_v2/fresh-100.json.']
(OUT/'README.md').write_text('\n'.join(lines)+'\n');print(json.dumps({k:result[k] for k in ['regression','fresh','fresh_disagreement']},ensure_ascii=False))
