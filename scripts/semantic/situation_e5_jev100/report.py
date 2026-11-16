# coding: utf-8
"""Verify and report actual LLM-free ablation without pretending offline reranking is a new run."""
from pathlib import Path
import json,sys,statistics,collections,hashlib
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent;OUT=ROOT/'docs/situation-e5-jev100';sys.path.insert(0,str(HERE.parent/'situation_goal100'));sys.path.insert(0,str(HERE.parent/'situation_v3'))
from partial_metrics import partial_summary
from goal_metrics import case_metrics,summary
from common import usage_counts,sha
from selection import select
run=json.loads((OUT/'run/results.json').read_text());assert run['complete'] and len(run['results'])==100
for rel,h in run['freeze']['files'].items():assert sha(ROOT/rel)==h,rel
cases=json.loads((ROOT/run['cases_path']).read_text());audit=[json.loads(l) for l in (OUT/'run/upstream-calls.jsonl').read_text().splitlines()]
assert audit==[c for r in run['results'] for c in r['calls']]
for c,r in zip(cases,run['results']):
 assert all(r[k]==v for k,v in c.items());assert r['score']==case_metrics(r)
 assert all(x['provider']=='e5_jev' for x in r['calls'])
 if not r.get('error'):
  selected,probs=select(r['candidate_ids'],r['calls'][0]['answers']);assert selected==r['selected_ids'] and probs==r['candidate_probabilities'];assert set(selected)<=set(r['candidate_ids'])
assert run['summary']['e5_jev_only']==summary(run['results'])
(OUT/'run/verification.log').write_text('Verified 100 frozen cases, accepted sets, model/selection hashes, actual candidate membership, raw Jev probabilities, all usage, zero OpenAI calls and complete aggregates.\n')
metrics=partial_summary(run['results']);times=sorted(r['http_ms'] for r in run['results']);usages=[usage_counts(c.get('usage')) for r in run['results'] for c in r['calls']];assert all(u['input'] is not None and u['output'] is not None for u in usages)
metrics.update(mean_http_ms=statistics.mean(times),p95_http_ms=times[94],input_tokens=sum(u['input'] for u in usages),output_tokens=sum(u['output'] for u in usages),estimated_api_usd=sum(u['input'] for u in usages)*.042/1e6,openai_calls=0,jev_calls=len(audit))
previous=json.loads((ROOT/'docs/situation-goal100/summary.json').read_text());previous_partial=json.loads((ROOT/'docs/situation-goal100/partial-summary.json').read_text());catalog={m['id']:m['name'] for m in json.loads((ROOT/'src/main/resources/kb_starbanking_menu_structure_cleaned.json').read_text())['menus']}
failures=[];counts=collections.Counter()
for r in run['results']:
 allowed=set().union(*map(set,r['acceptable_sets']));pred=set(r.get('selected_ids',[]))
 if pred&allowed:continue
 possible=set(r.get('candidate_ids',[]))&allowed
 kind='candidate_missing' if not possible else 'below_threshold' if max(r['candidate_probabilities'][i] for i in possible)<.7 else 'ranked_below_top3';counts[kind]+=1
 failures.append({'case_id':r['case_id'],'query':r['query'],'reason':kind,'selected':[{ 'id':i,'name':catalog[i]} for i in pred],'allowed_candidates':[{'id':i,'name':catalog[i],'noul':r['candidate_probabilities'][i]} for i in sorted(possible,key=lambda i:-r['candidate_probabilities'][i])],'possible_reference_gap':r['family_id']=='S06'})
result={'actual_e5_jev_only':metrics,'failure_counts':dict(counts),'reference_gap_candidates':sum(r['possible_reference_gap'] for r in failures),'failure_details':failures,'not_new_blind_test':True}
(OUT/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
lines=['# LLM 없는 E5→JEV 100문항 실제 검증','','사용자 요청에 따라 같은 승인된 상황형 100문항에서 원문 E5 Top80 → JEV 메뉴별 Noul → 최대3개 선택을 실제 실행했다. GPT/OpenAI 호출은 0회다. 상황별 고정 추천표는 넣지 않았다.','', '| 지표 | E5→JEV만 | LLM→E5→JEV | GPT-4.1 단독 |','|---|---:|---:|---:|']
a=previous['summary']['hybrid'];b=previous['summary']['llm_full_catalog'];pa=previous_partial['common_case_summary']['hybrid'];pb=previous_partial['common_case_summary']['llm_full_catalog']
lines += [f"| 부분 적중률 | {metrics['partial_hit_correct']}% | {pa['partial_hit_correct']}% | {pb['partial_hit_correct']}% |",f"| 허용 메뉴 비율 | {100*metrics['menu_level_allowed_precision']:.2f}% | {100*pa['menu_level_allowed_precision']:.2f}% | {100*pb['menu_level_allowed_precision']:.2f}% |",f"| 필수 업무 Recall | {100*metrics['macro_required_outcome_recall']:.2f}% | {100*pa['macro_required_outcome_recall']:.2f}% | {100*pb['macro_required_outcome_recall']:.2f}% |",f"| 문항당 추천 메뉴 | {metrics['mean_recommended_menus']:.2f} | {pa['mean_recommended_menus']:.2f} | {pb['mean_recommended_menus']:.2f} |",f"| 평균 / P95 HTTP ms | {metrics['mean_http_ms']:.2f} / {metrics['p95_http_ms']:.2f} | {a['mean_all_ms']:.2f} / {a['p95_all_ms']:.2f} | {b['mean_all_ms']:.2f} / {b['p95_all_ms']:.2f} |",f"| 문항당 입력 / 출력 토큰 | {metrics['input_tokens']/100:,.2f} / {metrics['output_tokens']/100:,.2f} | {a['input_mean']:,.2f} / {a['output_mean']:,.2f} | {b['input_mean']:,.2f} / {b['output_mean']:,.2f} |",f"| 100문항 API 비용 추정 | ${metrics['estimated_api_usd']:.4f} | ${a['cost_usd']:.4f} | ${b['cost_usd']:.4f} |",'', '## 실패 지점','', f"부분 미적중16건 중 후보 누락 {counts['candidate_missing']}건, 후보가 있지만3위 밖 {counts['ranked_below_top3']}건, 허용 후보 전부0.7미만 {counts['below_threshold']}건이다.", '', '은퇴 상황 9건에서는 나의 은퇴자산 현황·나의 연금자산·은퇴준비를 위한 KB골든라이프 같은 메뉴를 추천했지만 현재 허용 정답 목록 밖이라 실패다. 기능상 타당한 대체인지 사람 검수가 필요하다. 이 9건을 자동으로 정답 처리하거나 기존 점수를 덮어쓰지 않았다. 양쪽 모델을 같은 수정 기준으로 재검산하고 새 상황에서 검증해야 하며, 라벨 변경은 모델 개선이 아니다.', '', '## 오프라인 다양성 재정렬 확인','', '같은 실제 JEV 응답과 실제 E5 벡터로 고정 MMR(lambda0.7) 재정렬을 한 번 확인했다. 부분 적중85/100으로1건 증가했지만 단독 LLM89를 넘지 못했다. 이는 새API 실행이나 새종단간 시간 측정이 아닌 노출된 동일 데이터의 개발 분석이다. 매개변수 탐색으로 좋은 수치만 고르지 않았다.', '', '## 다음 개선 후보','', '- 후보별 독립 확률 상위3개 대신, 최종 후보10개에서1~3개로 구성된 실제 메뉴 조합(175개)을 만들어 JEV가 조합 단위로 선택하는 실험. 한 목적의 비슷한 메뉴가 자리를 독점하는지 확인한다. 개선을 보장하지 않으며 아직 실행하지 않았다.', '- 검색 누락3건은 별칭·표현 차이를 점검하고 실제 키워드 검색/벡터 검색의 결합을 별도 검증한다. 현재후보포함97%를 최종정확도로 부르지 않는다.', '- 모든 신규 정책·임계값 조정은 개발 데이터에서 하고, 새 상황군에서 단독 LLM과 같은 메뉴 예산으로 검증한다. 평가 정답표를 추론 규칙에 넣지 않는다.', '', '## 비교 한계','', '- 같은100문항이지만 이미 노출된 개발용 비교다. K=80도 로컬 후보 포함률을 본 뒤 선택했다. 독립 검증이나 실제 사용자 정확도라고 표현하지 않는다. 10상황군×10표현이다.', '- 순수 경로는 최대3개, 이전두조건은 최대8개였다. 기존 단독 LLM 응답의 첫3개만 잘랐을 때 부분적중78%지만, 이는 단독 LLM에 처음부터3개만 요구한 공정한 재실험은 아니다. 이수치를 우월성 증명으로 쓰지 않는다.', '- 이번실험은 로컬Python E5/직접JEV, 이전혼합은 실제Java API/proxy를 거쳤고 실행시각도다르다. 기동은제외했지만 네트워크·구현 오버헤드가 달라 생산환경 SLA나 완벽한 인과비교가 아니다.', '- 비용은 관측JEV입력×$0.042/M, 출력무료라는 [TypeSafe 공개 단가](https://help.typesafe.ai/articles/5187202169-how-much-does-jev-cost)에 따른 추정이다. 로컬E5 CPU/운영비·세금은제외했고 청구서가 아니다. 다른제공자의 토큰수를 같은가격단위로 비교하지않는다.', '- 실제 선택코드·0.7기준·최대3개는 API판단실행 전에 고정했다. 정답과 허용대체는 이전승인버전그대로다. 기본프로젝트 API를 이경로로 배포하거나 GitHub에 게시하지 않았다.', '', '실제 결과·확률·사용량: run/results.json 및 upstream-calls.jsonl. 검산: run/verification.log. 후보 포함률: retrieval-audit.json. 다양성 분석: diversity-audit.json. 설정/조건: PROTOCOL.md.']
(OUT/'README.md').write_text('\n'.join(lines)+'\n');print(json.dumps(metrics,ensure_ascii=False));print(dict(counts))
