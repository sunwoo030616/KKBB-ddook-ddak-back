#!/usr/bin/env python3
"""Build interview notes from completed artifacts, refusing partial release results."""
import json
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[1]


def read(name):return json.loads((ROOT/'reports'/name).read_text())


def main():
    final=read('literature-release-profile.json')
    if len(final['rows'])!=24 or 'score_cache_stats' not in final:raise ValueError('complete_24_case_profile_required')
    retrieval=read('expanded-retrieval.json')
    if 'summary' not in retrieval:raise ValueError('complete_retrieval_comparison_required')
    first=read('durable-curation-first.json');noop=read('durable-curation-noop.json')
    migration=read('curation-migration.json');baseline=read('model-routing-bge-diagnostic.json')
    service=read('knowledge-service.json')
    if not all(service['checks'].values()):raise ValueError('financial_service_regression_failed')
    text=['# 무료 모델 개발 결과와 면접 정리','',
      '깨비뚝딱의 채팅 → 금융 위젯 화면 구성을 유지하면서, 내부 문헌 탐색·지식 검토·추론 처리 경로를 확장했다. 아래 값은 로컬 실행 보고서에서 읽은 값이다. 수상 당시 구현과 이번 개인 확장을 구분해 설명한다.','',
      '## 실제 작업 범위','',
      '- 공식 초록 30편과 금융 안내 요약 26개를 버전별로 관리한다. 초록 원문과 검토 후보는 로컬에 보관한다.',
      '- 서버가 원문 절 경계를 고정하고 LLM이 영어 검색 질의를 만든다. 명시적 나열을 처리하는 표면 규칙이며 일반 의미 분석기가 아니다.',
      '- 소형 영어 문서 임베딩 → 최대 10개 후보 → 소형 CPU Cross-Encoder → 문장 문맥 후보 순서로 비용을 제한한다.',
      '- 실제 출처 ID·URL·해시·인용 위치는 서버가 붙이고, 선택된 문서 버전이 바뀌면 결과를 거부한다.',
      '- 모델은 검토 후보를 만들며, 별도 검토 리비전과 내부 릴리스가 승인·반려·롤백을 기록한다.','',
      '## 생성 모델 비교: 같은 6편과 개발 질문 8개','',
      '두 생성 모델을 각각 별도 프로세스에 적재한 진단이다. 값은 문헌 ID 집합 일치이며 답변의 의미 정확도가 아니다. 작은 모델은 빠른 경우가 있어도 누락과 주제 손실 때문에 자동 채택하지 않았다.','',
      '| 구성 | 완료 문항 | 문헌 ID 일치 | 필수 누락 표시 실패 | 중앙값(초) |',
      '| --- | ---: | ---: | ---: | ---: |']
    for key in ('4b_compact','1.7b_compact','4b_fast'):
        s=baseline['dev'][key]
        text.append(f"| {key}{' (부분 실행)' if s['n']<8 else ''} | {s['n']} | {s['exact']} | {s['missing_aspect_failures']} | {s['median_seconds']:.2f} |")
    text+=['','두 모델 동시 적재, 과분해가 남은 계획, 번역 문장·잘린 질의, 절별 개별 호출의 형식 실패도 보고서에 보존했다. 중단한 실행을 완성된 비교처럼 합산하지 않는다.','',
      '## 확장 문헌 경로: 30편과 내부 진단 24개','',
      '모델 준비 시간은 제외하고 요청 처리 시간을 측정했다. 최초 문항의 디코더 초기화는 각 행에 포함한다. 개발·회귀·추가 진단으로 나눴지만 모두 개발자가 만든 내부 문항이다. 일부를 관찰하며 설계를 보완했으므로 외부 블라인드 평가나 운영 정확도라고 주장하지 않는다.','',
      '| 집합 | 문항 | 문헌 ID 일치 | 문헌 ID·필수 누락 조건 모두 충족 | 중앙값(초) | 최대(초) |',
      '| --- | ---: | ---: | ---: | ---: | ---: |']
    for split in ('dev','regression','fresh'):
        rows=[r for r in final['rows'] if r['split']==split]
        text.append(f"| {split} | {len(rows)} | {sum(r['exact'] for r in rows)} | {sum(r['exact'] and r['missing_aspect_ok'] for r in rows)} | {statistics.median(r['seconds'] for r in rows):.2f} | {max(r['seconds'] for r in rows):.2f} |")
    text+=['','중앙값이 짧아도 최초 호출과 복잡한 요청의 긴 대기 시간은 남는다.',
      '이전 21.20초는 6편·다른 시점·다른 구성의 기록이다. 이번 값과의 차이를 한 가지 수정의 독립적인 개선율로 계산하지 않는다. 문헌 ID가 맞아도 구절이 충분한 의미 근거인지 별도로 검토해야 한다.','',
      '### 남은 실패','']
    failed=[r for r in final['rows'] if not (r['exact'] and r['missing_aspect_ok'])]
    text+=['| 문항 | 상태 | 실제 문헌 | 기대 문헌 |','| --- | --- | --- | --- |']
    text += [f"| {r['id']} | {r['status']} | {', '.join(r.get('actual',[])) or '-'} | {', '.join(r['expected']) or '-'} |" for r in failed]
    if not failed:text.append('| 전체 | 정의한 진단 조건 충족 | - | - |')
    text+=['','## 검색 단계 비교: 60개 한·영 질의','',
      '30개 문헌마다 한·영 질의를 쌍으로 만들고 문헌 단위로 15개씩 집합을 구분했다. 언어 쌍은 독립 표본이 아니다. 모델 학습이나 외부 벤치마크 재현은 수행하지 않았다. Tiny 경로는 영어 전용이며 한국어 성능으로 합산하지 않는다. 임베딩 모델과 장치도 다른 파이프라인 비교다.','',
      '| 경로 | 언어 | 문항 | Target Hit@1 | Target Hit@3 | MRR@3 | 중앙값(초) |',
      '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for mode,langs in retrieval['summary'].items():
        for lang,s in langs.items():text.append(f"| {mode} | {lang} | {s['n']} | {s['hit_at_1']} | {s['hit_at_3']} | {s['mrr_at_3']:.3f} | {s['median_seconds']:.3f} |")
    text+=['','## KV 캐시와 실제 데이터','',
      '동일 입력 결과 메모이제이션, 디코더 스키마 캐시, 검색 점수 캐시, 문서 벡터 캐시, 시스템 KV 캐시를 구분한다. 시스템 KV는 신뢰한 시스템 지시문만 미리 계산한다. 전체 프롬프트와 prefix+suffix의 토큰열이 정확히 같을 때만 적용하고, 저장한 KV를 복제해 사용자 입력이 원본 prefix를 바꾸지 못하게 한다. 다른 사용자 코드 8회 검증과 캐시 끔·켬의 출력 비교를 기록했다.',
      'KV 저장 상한은 4개·192MiB이다. `RAG_MLX_CACHE_MB=128`은 별도의 MLX 미사용 메모리 캐시 정책이며 모델 가중치·활성 KV·프로세스 전체 메모리를 128MiB로 제한하는 기능이 아니다. 다음 할당에서 회수되는 정책이므로 순간값의 엄격한 상한도 아니다.',
      '금융 화면은 모델의 계획을 재사용하더라도 기준일·계산·공식 근거 데이터를 서버에서 다시 구한다. 실제 금융 API 회귀에서 서로 다른 세션, 중복 계획의 실제 모델 호출 0, 과거·현재 근거 분리를 확인했다.','',
      '## 실제 지식 자동화','',
      f"- 기존 후보 {migration['migration']['imported']}개는 원문·모델·프롬프트 일치 검사를 거쳐 모델 적재 없이 이관했다.",
      f"- 첫 추가 실행: 처리 {first['curation']['processed']}개, 완료된 모델 호출 {first['curation']['model_calls']}회, 모델 적재 {first['model_loads']}회.",
      f"- 현재 작업 상태: `{json.dumps(first['curation']['status']['states'],ensure_ascii=False)}`. 출처·검토 이력 감사: `{first['curation']['audit']['valid']}`.",
      f"- 무변경 재실행: 모델 호출 {noop['curation']['model_calls']}회, 적재 {noop['model_loads']}회, 내부 처리 {noop['seconds']:.3f}초. 프로세스 시작 시간은 이 타이머에 포함하지 않는다.",
      '- 실제 카드의 업무 검토와 발행은 대기 상태다. 승인·롤백 테스트는 합성 fixture에서 수행했다.','',
      '## 면접 답변','',
      '> 채팅으로 금융 위젯 화면을 만드는 서비스에서 지식과 추론 경로를 확장했습니다. 작은 모델로 단순 교체하지 않고 과제 손실과 없는 정보의 인용을 비교했습니다. 출처 위치·문서 버전은 서버가 검증하고, AI 후보의 검토·릴리스는 별도 상태로 관리했습니다. 모델의 의미 정확성과 JSON 형식, 검색 회수, 처리 시간을 나눠 평가했습니다.',
      '',
      '**3번:** 문헌 수집·버전 추적·데이터 정제·검토 후보 생성·오류 분석을 설명한다.',
      '**9번:** 단일 Mac의 CPU/GPU 경로 비교, 단계별 지연, 입력 예산, 구조화 디코더 재사용, 시스템 KV 경계와 자원 정책을 설명한다. 분산 학습이나 이종 가속기 클러스터를 구현했다고 말하지 않는다.',
      '**금융권·대기업 백엔드:** 멱등 작업 키, 임대 토큰, 낙관적 리비전, 트랜잭션 경계, 장애 복구, 기준일 데이터와 모델 계획의 책임 분리를 중심으로 설명한다. 내부 진단 문항을 실제 사용자 수나 운영 TPS로 바꾸어 쓰지 않는다.','',
      '재현 자료: `reports/literature-release-profile.json`, `reports/expanded-retrieval.json`, `reports/durable-curation-first.json`, `reports/durable-curation-noop.json`, `reports/system-prefix-isolation.json`, `reports/knowledge-service.json`, `reports/release-environment.json`.','',
      '설계 참고: [Retrieve & Re-Rank](https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html), [MLX-LM cache](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/models/cache.py), [MLX 메모리 캐시](https://ml-explore.github.io/mlx/build/html/python/_autosummary/mlx.core.set_cache_limit.html). 해당 모델·논문의 학습이나 전체 벤치마크를 재현한 것은 아니다.','']
    (ROOT/'docs/무료모델_개발결과_면접정리.md').write_text('\n'.join(text))


if __name__=='__main__':main()
