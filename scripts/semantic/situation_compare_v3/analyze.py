# coding: utf-8
"""Report matched real results and published-rate costs without result-driven inference changes."""
from pathlib import Path
import json,sys,statistics,collections,math
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];OUT=ROOT/'docs/situation-compare-v3';sys.path.insert(0,str(HERE.parent/'situation_v3'))
from common import usage_counts
prices=json.loads((OUT/'unit-prices.json').read_text());d=json.loads((OUT/'paired-final/results.json').read_text());assert d['complete']
def costs(rows):
 grouped=collections.defaultdict(lambda:{'calls':0,'input':0,'cached_input':0,'output':0,'estimated_usd':0.,'uncached_estimated_usd':0.,'unknown_usage_calls':0})
 for row in rows:
  for c in row['calls']:
   assert c.get('http_status')!=429
   role=c['provider'];g=grouped[role];g['calls']+=1;u=usage_counts(c.get('usage'));i,o,cache=u['input'],u['output'],u['cached_input']
   if i is None or o is None:g['unknown_usage_calls']+=1;continue
   g['input']+=i;g['output']+=o
   if role=='e5_jev':g['cached_input']=None;p=prices['jev-1.14.0'];g['estimated_usd']+=i*p['input']/1e6;g['uncached_estimated_usd']+=i*p['input']/1e6
   else:
    assert cache is not None and 0<=cache<=i
    p=prices['gpt-4.1-2025-04-14'];g['cached_input']+=cache;g['estimated_usd']+=((i-cache)*p['input']+cache*p['cached_input']+o*p['output'])/1e6;g['uncached_estimated_usd']+=(i*p['input']+o*p['output'])/1e6
 return dict(grouped)
result={}
for provider in d['providers']:
 rows=[r for r in d['results'] if r['provider']==provider];s=d['summary'][provider];stage=costs(rows);times=sorted(r['http_ms'] for r in rows)
 result[provider]={'n':len(rows),'exact':s['status_and_menu_correct'],'accuracy':s['status_and_menu_accuracy'],'errors':s['errors'],'mean_all_http_ms':statistics.mean(times),'p95_all_http_ms':times[math.ceil(.95*len(times))-1],'input_mean':s['tokens']['input']['mean_per_case'],'output_mean':s['tokens']['output']['mean_per_case'],'estimated_usd_total':sum(v['estimated_usd'] for v in stage.values()),'uncached_estimated_usd_total':sum(v['uncached_estimated_usd'] for v in stage.values()),'stages':stage,'by_split':{k:{'correct':v['status_and_menu_correct'],'n':v['cases'],'accuracy':v['status_and_menu_accuracy']} for k,v in d['by_split'][provider].items()},'queue_wait_total_ms':sum(r.get('queue_wait_ms',0) for r in rows)}
a=result['hybrid'];b=result['llm_full_catalog'];diff={'accuracy_pp':(a['accuracy']-b['accuracy'])*100,'mean_http_percent':(a['mean_all_http_ms']/b['mean_all_http_ms']-1)*100,'input_percent':(a['input_mean']/b['input_mean']-1)*100,'cost_percent':(a['estimated_usd_total']/b['estimated_usd_total']-1)*100}
# Paired disagreement is more meaningful than treating the same 100 questions as independent samples.
bycase=collections.defaultdict(dict)
for r in d['results']:bycase[r['case_id']][r['provider']]=r['score']['status_and_menu_exact']
disagreement=collections.Counter(('both_correct' if x['hybrid'] and x['llm_full_catalog'] else 'hybrid_only' if x['hybrid'] else 'llm_only' if x['llm_full_catalog'] else 'both_wrong') for x in bycase.values())
summary={'comparison':result,'hybrid_minus_or_relative_to_llm':diff,'paired_disagreement':dict(disagreement),'price_sources':prices,'dataset_caveat':'50 named explicit multi, 50 contextual multi from 25 families; synthetic, no independent human labels; no unrestricted broad-situation accuracy claim'}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
fmt=lambda x:f'{x:,.2f}'
lines=['# GPT-4.1 단독과 LLM→E5→JEV 실제 대응 비교','', '같은 100문항·같은 GPT-4.1-2025-04-14·같은 585개 메뉴 이름/설명·최대 8개 선택 조건이다. 단독 모델은 ID를 추가로 받아 직접 최종 선택한다. 삼단계 구조는 고정 v3 코드로 실제 E5와 JEV-1.14.0을 사용한다. 단독 모델을 불리하게 만드는 예전 3개 슬롯·긴 메타데이터 형식·여행 고정 정책은 사용하지 않았다.', '', '| 지표 | LLM→E5→JEV | GPT-4.1 단독 |','|---|---:|---:|',f"| 상태+전체 메뉴 정확 일치 | {a['exact']}/100 | {b['exact']}/100 |",f"| 명시적 복수 50 | {a['by_split']['explicit_multi']['correct']}/50 | {b['by_split']['explicit_multi']['correct']}/50 |",f"| 상황 설명형 50 | {a['by_split']['contextual_multi']['correct']}/50 | {b['by_split']['contextual_multi']['correct']}/50 |",f"| 전체 평균 / P95 HTTP ms | {fmt(a['mean_all_http_ms'])} / {fmt(a['p95_all_http_ms'])} | {fmt(b['mean_all_http_ms'])} / {fmt(b['p95_all_http_ms'])} |",f"| 요청당 입력 / 출력 토큰 | {fmt(a['input_mean'])} / {fmt(a['output_mean'])} | {fmt(b['input_mean'])} / {fmt(b['output_mean'])} |",f"| 캐시 반영 API 비용 추정 /100요청 | ${a['estimated_usd_total']:.4f} | ${b['estimated_usd_total']:.4f} |",f"| 캐시 없이 환산한 비용 /100요청 | ${a['uncached_estimated_usd_total']:.4f} | ${b['uncached_estimated_usd_total']:.4f} |",f"| 오류(정확도 실패 포함) | {a['errors']} | {b['errors']} |", '',f"삼단계 기준 차이: 정확 일치 {diff['accuracy_pp']:+.2f}%p, 평균 시간 {diff['mean_http_percent']:+.2f}%, 입력 토큰 {diff['input_percent']:+.2f}%, 캐시 반영 비용 {diff['cost_percent']:+.2f}%.", '', '## 해석과 한계','', '- 설계상의 선택 이유는 업무별 근거·검색 후보·선택 로그를 나누어 오류 원인을 추적하고 미해결 업무만 확대하는 것이다. 단독 LLM도 ID 제약·서버 검증을 적용할 수 있으므로 삼단계만 안전하거나 무조건 더 정확하다고 주장하지 않는다.', '- 원하는 결과가 드러난 합성 복수 업무 100문항이다. 명시적 복수는 실제 메뉴명을 포함하며, 상황 설명형은 25개 의도군의 두 표현이다. 전문가 독립 검수·실사용·자유로운 상황 추천 전체 성능이 아니다.', '- 소스·모델·라벨은 고정했다. 단독 모델 프롬프트는 실행 전 고정했고 결과를 보고 조정하지 않았다. 실제 메뉴/형식 실패는 재시도하지 않았으며 실패로 포함했다.', '- 한도 오류만 사용자의 지시에 따라 다시 실행해 최종 행을 교체했다. 최초 시도와 중간 시도는 별도 폴더 및 excluded-quota-attempts.jsonl에 남고 비교 토큰·비용에서 제외했다. 이 비용은 제외 정책에 따른 비교치이며 전체 청구액이 아니다.', '- 단독 LLM은 간결한 ID·이름·설명 목록을 받는다. 혼합 구조의 JEV는 검색된 후보의 select_when도 받으므로 모든 상세 입력 필드까지 동일한 통제 실험은 아니다. 정의된 두 경로의 비교이며 단독 LLM의 모든 프롬프트 구성이 최적이라는 뜻은 아니다.', '- 원래 조건별 순서를 번갈아 계획했으나 한도 오류·재개 때문에 일부 쌍의 실제 호출 시간은 떨어져 있다. 큐 대기·컴파일·서버/임베딩 준비는 HTTP 시간에서 제외했다. 단일 회차 네트워크·캐시 상태 차이가 있다.', '- 비용은 관측 usage와 공개 표준 단가 추정이다. 캐시 입력은 전체 입력의 일부다. 제공자별 토큰 정의가 다르고 JEV 출력은 무료이므로 입력+출력 토큰 총량을 동일 비용으로 비교하면 안 된다. 로컬 E5 비용·세금·계정별 요금 차이는 제외했다.', '', '단가 출처: [GPT-4.1 공식 모델 문서](https://developers.openai.com/api/docs/models/gpt-4.1), [TypeSafe 공식 요금 안내](https://help.typesafe.ai/articles/5187202169-how-much-does-jev-cost). 2026-11-15 확인.', '', '원본: paired-final/results.json 및 upstream-calls.jsonl. 분해 집계와 비용: summary.json. 기존 300문항 최종 회귀는 docs/situation-v3/regression-final/results.json에 별도로 보존하며 새 100문항 비교와 합치지 않는다. 발표 페이지 구성은 사용자 요청으로 중단했다. GitHub에 게시하지 않았다.']
(OUT/'README.md').write_text('\n'.join(lines)+'\n');print(json.dumps(summary['comparison'],ensure_ascii=False));print(diff)
