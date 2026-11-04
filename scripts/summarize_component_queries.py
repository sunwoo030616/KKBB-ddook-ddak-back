#!/usr/bin/env python3
"""Summarize complete end-to-end experiment without hiding errors or confounds."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
report=json.loads((ROOT/'reports/component-query-v1.json').read_text())
if 'summary' not in report:raise SystemExit('Experiment incomplete')
s=report['summary'];pairs=s['comparable_model_pairs']
lines=['# 복합 요청 검색·GPU 실행 보강 결과','',
       '개발자가 작성한 진단 자료를 실패 관찰 후 다시 사용한 시스템 개발 비교다. 독립·블라인드 벤치마크가 아니며 새 사용자 전체에 대한 정확도 추정이 아니다.','',
       '| 비교 | 기존 single/CPU float32 | 새 multi/MPS float16 |',
       '| --- | ---: | ---: |',
       f"| 연결 오류를 제외한 정확 위젯 집합 | {pairs['single_exact']}/{pairs['total']} | {pairs['multi_exact']}/{pairs['total']} |",
       f"| 전체 요청의 정확 집합(연결 오류 포함) | {s['single_exact']}/{s['total']} | {s['multi_exact']}/{s['total']} |",
       f"| 비교 가능한 문항의 후보 Recall | {s['single_candidate_recall']:.3f} | {s['multi_candidate_recall']:.3f} |",'',
       f"새 시스템 지연 중앙값: {s['multi_median_wall_ms']/1000:.2f}초. 장치·정밀도·캐시·장비 부하가 함께 달라 엄밀한 속도 향상률로 해석하지 않는다.",'',
       '| 문항 | 기존 | 보강 후 | 소요 시간 |','| --- | --- | --- | ---: |']
for r in report['results']:
    old='연결 오류' if r['baseline_infrastructure_error'] else '일치' if r['baseline_exact'] else '불일치'
    lines.append(f"| {r['id']} | {old} | {'일치' if r['exact'] else '불일치'} | {r['wall_ms']/1000:.2f}초 |")
lines+=['','## 변경과 해석','',
       '- 원문과 최대 3개 보조 절의 신경망 검색 후보를 합치고, 낮은 관련도에서는 후보 강제 선택을 중단했다.',
       '- 검색 모델을 CPU float32에서 Apple MPS float16으로 바꿨다. 같은 가중치이지만 정밀도도 바뀐 시스템 비교이며 검색 분할 하나의 인과 효과가 아니다.',
       '- 생성 모델·프롬프트·출력 스키마와 정답 목록은 유지했다. 정답 목록은 평가기에만 전달했다.',
       '- s11 기존 실행의 연결 오류를 모델의 오답으로 해석하지 않도록 주 비교에서 해당 쌍을 제외했다. 전체 요청 결과도 함께 남겼다.',
       '- 후보 Recall은 업무 위젯 기준이다. 필수 입력 의존 위젯은 컴파일러가 추가한다.',
       '- 후속 요청은 동일 구조의 세션 fixture다. 실제 전체 대화 생성 평가와 구분한다.',
       '- 0.001 중단 기준은 개발 휴리스틱이다. 별도 자료로 보정한 확률이 아니며 미지 표현에서 오거부가 생길 수 있다.',
       '- CPU 실행 중 207초 지연으로 중단한 부분 기록과 자기 검토의 부정적 결과도 보존했다.','',
       '실제 코드·프로토콜: [검색 설계](../docs/복합요청_위젯검색.md), [AI 개발 정리](../docs/AI_개발_정리.md).','']
(ROOT/'reports/component-query-results.md').write_text('\n'.join(lines))
print('\n'.join(lines[:13]))
