#!/usr/bin/env python3
"""Render a complete paired experiment, retaining failures and validity limits."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[1]
report=json.loads((ROOT/'reports/semantic-review-v2.json').read_text())
if 'summary' not in report:raise SystemExit('Experiment incomplete: no final summary yet')
cases=json.loads((ROOT/'data/semantic_review_cases.json').read_text())
if hashlib.sha256((ROOT/'data/semantic_review_cases.json').read_bytes()).hexdigest()!=report['dataset_sha256']:
    raise SystemExit('Dataset changed since experiment')
rows=report['results']
if len(rows)!=2*len(cases['cases']):raise SystemExit('Missing paired cases')
by_key={(r['id'],r['mode']):r for r in rows}
lines=['# LLM 화면 의미 검토: 실제 모델 비교 결과','',
       '개발자가 작성한 12개 진단 문항이다. 외부·독립·블라인드 평가가 아니다. 초기 계약 오류와 중단 기록도 reports에 보존했다. 정답 목록은 모델에 전달하지 않았다.','',
       '| 방식 | 정확 위젯 집합 일치 | 지연 중앙값 | 추적된 모델 호출 합계 |',
       '| --- | ---: | ---: | ---: |']
metrics={}
for mode in ('off','repair'):
    selected=[r for r in rows if r['mode']==mode]
    # Each llm_plan, semantic_review, or nonempty refinement trace is one inference.
    calls=sum(sum(t['step'] in ('llm_plan','semantic_review','semantic_refinement') and 'latency_ms' in t
                  for t in r['response'].get('trace',[])) for r in selected)
    actual=sum(len(set(r['actual'])) for r in selected);gold=sum(len(set(r['gold'])) for r in selected)
    correct=sum(len(set(r['actual'])&set(r['gold'])) for r in selected)
    metrics[mode]={'calls':calls,'micro_precision':correct/actual if actual else None,'micro_recall':correct/gold if gold else None}
    lines.append(f"| {mode} | {sum(r['exact'] for r in selected)}/{len(selected)} | {statistics.median(r['wall_ms'] for r in selected)/1000:.2f}초 | {calls} |")
lines+=['','| 문항 | 기존 | 검토·수정 | 결과 |','| --- | --- | --- | --- |']
for case in cases['cases']:
    a,b=(by_key[(case['id'],mode)] for mode in ('off','repair'))
    verdict='개선' if not a['exact'] and b['exact'] else '악화' if a['exact'] and not b['exact'] else '동일'
    lines.append(f"| {case['id']} {case['message']} | {'일치' if a['exact'] else '불일치'} | {'일치' if b['exact'] else '불일치'} | {verdict} |")
traces=[t for r in rows if r['mode']=='repair' for t in r['response'].get('trace',[]) if t['step'].startswith('semantic')]
counts=Counter((t['step'],t['status']) for t in traces)
lines+=['','## 검토·수정 기록','']+[f'- {step}/{status}: {count}건' for (step,status),count in sorted(counts.items())]
lines+=['','## 해석 범위','',
       '- 정확 집합은 업무/결과 위젯 기준이다. 서버가 붙이는 입력 의존 위젯은 별도 컴파일 테스트에서 검사한다.',
       '- unsupported 요청은 composed/clarify 상태에서 빈 집합이어야 맞다. failed/exception은 정답으로 세지 않는다.',
       '- 후속 화면은 같은 구조의 세션 fixture를 사용했다. 실제 전체 대화 생성 평가와 구분한다.',
       '- 실패를 관찰하고 검토 스키마를 개선한 개발 실험이다. 이 데이터의 성능으로 새 사용자 전체의 정확도를 추정할 수 없다.',
       '- 같은 모델의 자기 검토가 정답을 보장하지 않는다. 인용 출처·지원 목록·이력 검증과 수정 수 제한을 함께 적용한다.',
       '- 장비의 메모리 압박, 실행 순서와 캐시가 지연에 영향을 준다. 엄밀한 서버 처리량 평가가 아니다.','']
lines+=['','## 기본 설정 결정','','연결 오류가 발생한 s11 쌍을 제외하면 두 방식 모두 6/11이다. 이 실험에서 자기 검토의 정확도 개선은 입증되지 않았고 지연은 증가했다. review 기본값은 off로 두었다. 위젯 수정 의견 없이 clarification만 있는 경우 추가 재생성도 생략한다.','']
(ROOT/'reports/semantic-review-results.md').write_text('\n'.join(lines))
(ROOT/'reports/semantic-review-metrics.json').write_text(json.dumps({'metrics':metrics,'trace_counts':{f'{a}/{b}':c for (a,b),c in counts.items()}},ensure_ascii=False,indent=2)+'\n')
print('\n'.join(lines[:9]))
