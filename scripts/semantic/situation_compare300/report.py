# -*- coding: utf-8 -*-
"""Create the completed actual comparison report and optional chart."""
import json,datetime
from pathlib import Path
from run import ROOT,HERE,MODELS
out=ROOT/'docs/situation-compare300';r=json.loads((out/'results.json').read_text());assert r['complete']
a=r['summary']['e5_jev'];b=r['summary']['llm_full_catalog']
menus=json.loads((ROOT/'src/main/resources/kb_starbanking_menu_structure_cleaned.json').read_text())['menus'];names={m['id']:m['name'] for m in menus}
def pct(v):return f'{v:.2%}' if v is not None else '미제공'
def fmt(v):return '미제공' if v is None else f'{v:,}' if isinstance(v,int) else f'{v:,.2f}'
def token(s,k,f):return fmt(s['tokens'][k][f])
def token_total(s):
 if any(s['tokens'][k]['observed_calls']!=s['actual_upstream_calls'] for k in ['input','output']):return None
 return s['tokens']['input']['sum']+s['tokens']['output']['sum']
lines=['# 상황별 복수 메뉴: E5→JEV / 전체 메뉴 LLM 실제 비교','',f"실행: {datetime.datetime.fromisoformat(r['started_at']).astimezone(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S KST')} → {datetime.datetime.fromisoformat(r['updated_at']).astimezone(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S KST')}. 같은 300문항을 양쪽 조건에서 한 번씩 순서를 교대해 실행했다. 오류·누락·추가 메뉴를 숨기지 않고 분모에 포함했다.",'','| 항목 | JEV 업무 판단 → E5 → JEV 복수 선택 | 전체 585개 메뉴 GPT |','|---|---:|---:|',
 f"| 메뉴 집합 정확 일치 | {a['menu_exact_correct']}/300 · {pct(a['menu_exact_accuracy'])} | {b['menu_exact_correct']}/300 · {pct(b['menu_exact_accuracy'])} |",
 f"| 상태+메뉴 집합 정확 일치 | {a['status_and_menu_correct']}/300 · {pct(a['status_and_menu_accuracy'])} | {b['status_and_menu_correct']}/300 · {pct(b['status_and_menu_accuracy'])} |",
 f"| Macro Precision | {pct(a['macro_precision'])} | {pct(b['macro_precision'])} |",
 f"| Macro Recall | {pct(a['macro_recall'])} | {pct(b['macro_recall'])} |",
 f"| Macro F1 | {pct(a['macro_f1'])} | {pct(b['macro_f1'])} |",
 f"| Micro Precision / Recall / F1 | {pct(a['micro_precision'])} / {pct(a['micro_recall'])} / {pct(a['micro_f1'])} | {pct(b['micro_precision'])} / {pct(b['micro_recall'])} / {pct(b['micro_f1'])} |",
 f"| 누락 메뉴 수 / 누락 문항 | {a['missing_menus']} / {a['cases_with_missing_menus']} | {b['missing_menus']} / {b['cases_with_missing_menus']} |",
 f"| 추가 메뉴 수 / 추가 문항 | {a['extra_menus']} / {a['cases_with_extra_menus']} | {b['extra_menus']} / {b['cases_with_extra_menus']} |",
 f"| API·검증 오류 | {a['errors']} | {b['errors']} |",
 f"| 평균 / 중앙값 / P95 HTTP ms | {fmt(a['mean_http_ms'])} / {fmt(a['median_http_ms'])} / {fmt(a['p95_http_ms'])} | {fmt(b['mean_http_ms'])} / {fmt(b['median_http_ms'])} / {fmt(b['p95_http_ms'])} |",
 f"| 실제 외부 호출 | {a['actual_upstream_calls']} | {b['actual_upstream_calls']} |",
 f"| 입력 토큰 합계 / 문항 평균 | {token(a,'input','sum')} / {token(a,'input','mean_per_case')} | {token(b,'input','sum')} / {token(b,'input','mean_per_case')} |",
 f"| 출력 토큰 합계 / 문항 평균 | {token(a,'output','sum')} / {token(a,'output','mean_per_case')} | {token(b,'output','sum')} / {token(b,'output','mean_per_case')} |",
 f"| 입력+출력 토큰 합계 / 문항 평균 | {fmt(token_total(a))} / {fmt(token_total(a)/300 if token_total(a) is not None else None)} | {fmt(token_total(b))} / {fmt(token_total(b)/300 if token_total(b) is not None else None)} |",
 f"| 캐시 입력 토큰 합계 | {token(a,'cached_input','sum')} | {token(b,'cached_input','sum')} |",
 f"| 입력/출력/캐시 usage 관측 호출 수 | {a['tokens']['input']['observed_calls']} / {a['tokens']['output']['observed_calls']} / {a['tokens']['cached_input']['observed_calls']} | {b['tokens']['input']['observed_calls']} / {b['tokens']['output']['observed_calls']} / {b['tokens']['cached_input']['observed_calls']} |"]
lines+=['',f"이번 실행에서 GPT 평균 시간 / E5→JEV 평균 시간은 {b['mean_http_ms']/a['mean_http_ms']:.2f}배다. 반복 실행의 고정 배수나 순수 모델 처리속도 비율이 아니다.",'', '## 구간별 결과','', '| 구간 | 문항 | E5→JEV 집합 일치 | GPT 집합 일치 | E5→JEV Macro F1 | GPT Macro F1 |','|---|---:|---:|---:|---:|---:|']
for split,x in r['by_split']['e5_jev'].items():
 y=r['by_split']['llm_full_catalog'][split]
 lines.append(f"| {split} | {x['cases']} | {x['menu_exact_correct']} · {pct(x['menu_exact_accuracy'])} | {y['menu_exact_correct']} · {pct(y['menu_exact_accuracy'])} | {pct(x['macro_f1'])} | {pct(y['macro_f1'])} |")
left_pairs={x['case_id']:x for x in r['results'] if x['provider']=='e5_jev'}
right_pairs={x['case_id']:x for x in r['results'] if x['provider']=='llm_full_catalog'}
common_ids=[k for k in left_pairs if left_pairs[k]['score']['menu_exact'] and right_pairs[k]['score']['menu_exact']]
early=sum(not x.get('error') and (x.get('metrics') or {}).get('jevCalls')==1 for x in left_pairs.values())
lines+=['',f'E5→JEV에서 업무 판단 후 검색 전에 조기 종료한 문항은 {early}개다. 전체 평균 시간·토큰에는 이 빠른 확인 요청/no_match도 포함되므로 낮은 비용을 같은 품질의 절감으로 단정하지 않는다.']
if common_ids:
 from metrics import summary
 ca=summary([left_pairs[k] for k in common_ids]);cb=summary([right_pairs[k] for k in common_ids])
 lines+=['','## 양쪽 모두 정답 묶음을 반환한 동일 문항의 보조 비교','',f'양쪽 모두 메뉴 집합 정확 일치인 같은 {len(common_ids)}문항만 조건부로 비교했다. 쉬운 문항으로 선택된 부분집합이므로 전체 정확도를 대체하지 않는다.','', '| 항목 | E5→JEV | GPT |','|---|---:|---:|',f"| 평균 HTTP ms | {fmt(ca['mean_http_ms'])} | {fmt(cb['mean_http_ms'])} |",f"| 입력 토큰 / 문항 | {token(ca,'input','mean_per_case')} | {token(cb,'input','mean_per_case')} |",f"| 출력 토큰 / 문항 | {token(ca,'output','mean_per_case')} | {token(cb,'output','mean_per_case')} |"]
lines+=['','## 읽는 방법과 한계','', '- 메뉴 집합 정확 일치는 필요한 모든 메뉴를 골랐고 불필요한 메뉴를 추가하지 않은 경우다. 순서는 무시한다. 일본 여행 묶음에서 환전·QR·보험 중 하나라도 빠지면 정확 일치는 실패다. 확인 요청도 이 positive 정답을 대신할 수 없다.', '- Precision은 반환한 메뉴 중 정답 비율, Recall은 필요한 메뉴 중 찾은 비율이다. Macro는 질문별 값을 평균하고 Micro는 전체 TP/FP/FN을 합쳐 계산한다. F1은 Precision과 Recall의 조화평균이다. 이번 Recall은 최종 반환 메뉴에 대한 값이며 기존 E5 후보 Recall@40과 다르다.', '- E5 쪽은 JEV 업무 판단과 메뉴 선택을 최대 두 번 호출한다. 토큰과 시간에 두 단계가 모두 포함된다. GPT는 검색 없이 전체 카탈로그를 받아 한 번 응답한다. 모델만 교체한 통제 실험이나 9종 위젯 비교가 아니다.', '- GPT 모델은 gpt-4o-mini-2024-07-18, JEV는 jev-1.14.0이다. 공통 confidence 기준은 0.6이나 척도·보정은 같지 않다. GPT 전용 프롬프트 최적화나 모델별 임계값 보정은 하지 않았다.', '- 입력·출력·캐시 토큰은 API의 실제 usage다. 캐시는 입력의 부분집합이며 미제공은 0이 아니다. 제공자 tokenizer와 usage 정의가 다르므로 금액·연산량 차이로 같은 비율 환산하지 않는다. E5 로컬 추론은 JEV API 토큰에 포함되지 않는다.', '- 시간에는 각 제품 경로의 로컬 구현·네트워크·스키마 처리·캐시 효과가 포함된다. 컴파일·모델 시작·메뉴 벡터 준비·명시적 토큰 예산 대기는 제외했다. 단일 순차 실행이며 부하 성능이나 통계적 유의성을 주장하지 않는다.', '- 100개 단일 요청은 과거 질문을 재사용했고 100개 명시적 복수 요청은 이를 결합했다. 상황형 100개는 20개 가족의 표현 5종이다. 독립 의도 300개가 아니며 일본 여행은 개발용 정책 확인 예시다. 전문가 독립 검수·실제 고객 표본이 아니다.', '- 현재 지원은 최대 3개 업무와 54개 업무 정의/fallback이다. 같은 fallback에 해당하는 복수의 미지원 업무를 모두 분리하지 못할 수 있다. 모든 메뉴를 호출하거나 화면을 구현한 것은 아니다. 모호·무관한 negative 요청, 설명 품질·이후 대화·실제 거래는 이번 300개에서 평가하지 않았다.', '- 앞선 단일 선택 300문항의 98.89% 및 확인 요청 100%와 과제가 달라 직접 개선·하락으로 비교하지 않는다. 중단한 단일 선택 비교 191쌍은 이번 점수와 합치지 않았다.','', '## 일본 여행 예시와 실패 분석','']
for p in MODELS:
 row=next(x for x in r['results'] if x['case_id']=='situation_01_1' and x['provider']==p)
 lines.append(f"- {p}: {row['status']} / "+', '.join(names[x] for x in row.get('selected_ids',[])))
lines+=['','전체 문항별 누락·추가 메뉴와 실제 응답은 results.json에 보존했다. 아래는 적어도 한 방식이 메뉴 집합을 맞히지 못한 경우다.','', '| 문항 | 정답 메뉴 | E5→JEV | GPT |','|---|---|---|---|']
left={x['case_id']:x for x in r['results'] if x['provider']=='e5_jev'};right={x['case_id']:x for x in r['results'] if x['provider']=='llm_full_catalog'}
for cid,x in left.items():
 y=right[cid]
 if x['score']['menu_exact'] and y['score']['menu_exact']:continue
 def actual(z):return z['status']+' / '+', '.join(names[v] for v in z.get('selected_ids',[]))
 lines.append(f"| {cid} | {', '.join(names[v] for v in x['expected_ids'])} | {actual(x)} | {actual(y)} |")
lines+=['','## 재현 근거','', '사전 조건은 PROTOCOL.md, 사전 고정 입력·코드 해시는 scripts/semantic/situation_compare300/freeze.json, 라벨 출처와 가족 중복 한계는 label-audit.json이다. 실제 600개 조건별 응답·usage는 results.json, 실행/테스트/재계산 로그는 이 폴더의 *.log다. approval.json은 변경된 범위의 사용자 승인 기록이다.']
(out/'README.md').write_text('\n'.join(lines)+'\n')
try:
 import os,tempfile
 os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'kkbb-situation-mpl'))
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 from matplotlib import font_manager
 for name in ['AppleGothic','NanumGothic','Noto Sans CJK KR']:
  if name in {f.name for f in font_manager.fontManager.ttflist}:plt.rcParams['font.family']=name;break
 plt.rcParams['axes.unicode_minus']=False
 fig,axs=plt.subplots(1,3,figsize=(16,6));colors=['#1967d2','#e78326']
 splits=['single_explicit','explicit_multi','situation_bundle']
 for i,p in enumerate(MODELS):
  bars=axs[0].bar([j-.18+i*.36 for j in range(3)],[r['by_split'][p][s]['menu_exact_accuracy']*100 for s in splits],width=.34,color=colors[i],label='E5→JEV' if i==0 else '전체 메뉴 GPT')
  axs[0].bar_label(bars,fmt='%.0f%%',padding=3,fontsize=9)
 axs[0].set(xticks=[0,1,2],xticklabels=['단일','명시적 복수','상황 묶음'],ylim=(0,115),title='메뉴 집합 정확 일치');axs[0].legend(loc='lower left')
 for ax,values,title,unit in [(axs[1],[a['mean_http_ms'],b['mean_http_ms']],'평균 HTTP 시간','ms'),(axs[2],[a['tokens']['input']['mean_per_case'],b['tokens']['input']['mean_per_case']],'문항당 API 입력 토큰','tokens')]:
  bars=ax.bar(['E5→JEV','전체 메뉴 GPT'],values,color=colors);ax.bar_label(bars,fmt='%.0f',padding=3);ax.set(title=title,ylabel=unit,ylim=(0,max(values)*1.2))
 fig.suptitle('상황별 복수 메뉴 · 같은 합성 300문항 · 실제 API 비교',fontsize=18)
 fig.text(.05,.025,'JEV planning + selection included. Provider token accounting differs. Synthetic reused families; not production accuracy.',fontsize=10)
 fig.tight_layout(rect=(0,.07,1,.92));fig.savefig(out/'comparison.png',dpi=180);plt.close(fig)
except ImportError:print('Optional chart skipped: install matplotlib==3.9.4')
print('Rendered completed actual results to README.md and optional comparison.png')
