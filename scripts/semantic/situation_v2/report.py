# coding: utf-8
"""Summarize v2 regression and separately frozen paired additional validation."""
from pathlib import Path
import json,datetime
from run import ROOT,HERE
out=ROOT/'docs/situation-v2'
reg=json.loads((out/'regression/results.json').read_text());fresh=json.loads((out/'fresh/results.json').read_text())
assert reg['complete'] and fresh['complete']
old=json.loads((ROOT/'docs/situation-compare300/results.json').read_text())
a=old['summary']['e5_jev'];b=reg['summary']['e5_jev'];c=fresh['summary']['e5_jev'];d=fresh['summary']['llm_full_catalog']
def pct(v):return '—' if v is None else f'{v:.2%}'
def n(v):return '미제공' if v is None else f'{v:,}' if isinstance(v,int) else f'{v:,.2f}'
def t(s,k,f='mean_per_case'):return n(s['tokens'][k][f])
def rows_table(left,right):
 return [f"| 상태+메뉴 집합 정확 일치 | {left['status_and_menu_correct']}/{left['cases']} · {pct(left['status_and_menu_accuracy'])} | {right['status_and_menu_correct']}/{right['cases']} · {pct(right['status_and_menu_accuracy'])} |",
 f"| 메뉴 집합만 정확 일치 | {pct(left['menu_exact_accuracy'])} | {pct(right['menu_exact_accuracy'])} |",f"| Macro P / R / F1 (positive 문항) | {pct(left['macro_precision'])} / {pct(left['macro_recall'])} / {pct(left['macro_f1'])} | {pct(right['macro_precision'])} / {pct(right['macro_recall'])} / {pct(right['macro_f1'])} |",
 f"| 누락 / 추가 메뉴 수 | {left['missing_menus']} / {left['extra_menus']} | {right['missing_menus']} / {right['extra_menus']} |",f"| 오류 | {left['errors']} | {right['errors']} |",f"| 평균 / P95 HTTP ms | {n(left['mean_http_ms'])} / {n(left['p95_http_ms'])} | {n(right['mean_http_ms'])} / {n(right['p95_http_ms'])} |",
 f"| 입력 / 출력 토큰 평균 | {t(left,'input')} / {t(left,'output')} | {t(right,'input')} / {t(right,'output')} |",f"| 입력 / 출력 토큰 합계 | {t(left,'input','sum')} / {t(left,'output','sum')} | {t(right,'input','sum')} / {t(right,'output','sum')} |",f"| 캐시 입력 합계 | {t(left,'cached_input','sum')} | {t(right,'cached_input','sum')} |",f"| 실제 외부 호출 | {left['actual_upstream_calls']} | {right['actual_upstream_calls']} |"]
lines=['# 복수 메뉴 v2 재측정','', '54개 업무 순위 슬롯을 제거하고 단일 경로 재사용·원문별 독립 선택·상황 정책 묶음·후보별 Noul을 사용했다. 개발 확인과 본 평가를 분리했다. 소스·질문·정답은 각 실행 전에 해시 고정했다.','', '## 동일 300문항 전후 회귀 비교','', '동일한 이전 질문·정답이다. 실패를 보고 구조를 개선했으므로 이 결과는 개발 회귀 지표이며 독립 일반화 성능이 아니다. 시점도 달라 네트워크 지연의 인과 효과로 단정하지 않는다.','', '| 지표 | 이전 v1 | 개선 v2 |','|---|---:|---:|']+rows_table(a,b)
lines+=['','| 구간 | v1 정확 일치 | v2 정확 일치 |','|---|---:|---:|']
for s,x in old['by_split']['e5_jev'].items():
 y=reg['by_split']['e5_jev'][s];lines.append(f"| {s} | {x['menu_exact_correct']}/{x['cases']} · {pct(x['menu_exact_accuracy'])} | {y['menu_exact_correct']}/{y['cases']} · {pct(y['menu_exact_accuracy'])} |")
lines+=['','## 별도 고정 합성 100문항의 같은 시점 대응 비교','', '새 표현의 100문항(단일 30·복수 30·상황 30·무관/모호 10)으로 각 제공자를 1회 실행했다. 같은 메뉴·상황 의도는 공유하므로 전문가 독립 검수나 실제 트래픽 평가로 표현하지 않는다. P/R/F1은 정답 메뉴가 있는 90문항, 상태+집합 정확 일치는 전체 100문항 기준이다.','', '| 지표 | JEV v2 | GPT 전체 메뉴 |','|---|---:|---:|']+rows_table(c,d)
lines+=['','| 구간 | JEV v2 상태+집합 일치 | GPT 상태+집합 일치 |','|---|---:|---:|']
for s,x in fresh['by_split']['e5_jev'].items():
 y=fresh['by_split']['llm_full_catalog'][s];lines.append(f"| {s} | {x['status_and_menu_correct']}/{x['cases']} | {y['status_and_menu_correct']}/{y['cases']} |")
lines+=['','## 한계와 재현','', '- 모델은 jev-1.14.0과 gpt-4o-mini-2024-07-18이다. GPT는 전체 585개 메뉴와 동일 v2 제품 정책을 받으며 프롬프트가 이전 실험과 달라 예전 GPT 점수와 직접 개선율로 비교하지 않는다.', '- Choice confidence=0.6과 후보별 Noul probability=0.7은 다른 의미다. 평가 결과를 보고 임계값을 변경하지 않았다. 원문 분해 규칙은 한국어 접속 표현을 일부만 처리하므로 일반적인 의미 분해를 보장하지 않는다. 최대 3개 독립 업무를 지원한다.', '- API 입력·출력·캐시 토큰은 원본 usage를 집계했다. 미제공은 0이 아니다. 제공자별 tokenizer와 usage 정의가 달라 입력+출력 합계를 동일 비용/연산량으로 환산하지 않는다. JEV 출력 토큰은 공개 단가에서 무료이며 로컬 E5 비용은 포함하지 않았다.', '- 모든 시간에는 요청 경로의 로컬 처리·외부 호출이 포함되며 기동·컴파일·메뉴 임베딩 준비는 제외됐다. 실패·확인 요청·후보 확대 호출을 숨기지 않았다. 단일 실행의 네트워크/모델 변동성이 있다.', '- 개발 사례는 이미 본 12개이며 개발 결과는 본 평가 점수나 토큰에 합치지 않았다. 회귀 300개는 학습용으로 노출된 평가이고, 추가 100개도 합성 라벨·공유 의도이므로 실사용 정확도 보장이 아니다.', '- 기존 /api/menus/select와 9종 위젯 화면은 수정하지 않았다. 새 메뉴 추천 API와 실제 화면/거래 연결은 별개다. 원격 게시 없이 로컬 결과를 보존한다.', '', '실행 조건: PROTOCOL.md. 입력 라벨·해시: scripts/semantic/situation_v2. 실제 결과: regression/results.json, fresh/results.json. 진행·테스트·검산 로그는 각 폴더에 있다.']
# Preserve every observed failure for review, without changing its gold label.
failures={}
for label,r in [('regression_v2',reg),('fresh',fresh)]:
 failures[label]=[{k:x.get(k) for k in ['case_id','provider','query','expected_ids','expected_status','selected_ids','status','score','reviews']} for x in r['results'] if not x['score']['status_and_menu_exact']]
(out/'failures.json').write_text(json.dumps(failures,ensure_ascii=False,indent=2)+'\n')
(out/'README.md').write_text('\n'.join(lines)+'\n')
print('Rendered v2 regression/fresh report and all failures')
