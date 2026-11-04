# Retrieval experiment: dev

Corpus: `958da9ca841d3318`. Generation: **extractive, no LLM calls**.

| Method | N | Answerable | Hit@1 | Hit@3 | MRR@3 | End-to-end | p50 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| bm25 | 12 | 8 | 0.625 | 0.875 | 0.750 | 0.917 | 0.163 |
| hybrid | 12 | 8 | 0.875 | 1.000 | 0.938 | 1.000 | 0.622 |
| dense | 12 | 8 | 0.500 | 0.875 | 0.667 | 1.000 | 7.466 |
| fusion | 12 | 8 | 0.750 | 1.000 | 0.854 | 1.000 | 7.861 |

## Limits

- 수작업 소규모 corpus/질문; 외부 독립 벤치마크 아님
- 검색/라우팅/추출형 답변 평가; LLM 품질/환각률 평가 아님
- 로컬 파이프라인 시간; 네트워크/LLM 지연 제외

## Failures (retained, not filtered)

### bm25: 1 failures
- d03: KB증권 체크카드 찾았어. 분실신고를 풀려면? / missing_topic_evidence / evidence=[]
### hybrid: 0 failures
### dense: 0 failures
### fusion: 0 failures
