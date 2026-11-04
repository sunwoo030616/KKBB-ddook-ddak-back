# Retrieval experiment: test

Corpus: `958da9ca841d3318`. Generation: **extractive, no LLM calls**.

| Method | N | Answerable | Hit@1 | Hit@3 | MRR@3 | End-to-end | p50 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| bm25 | 30 | 19 | 0.684 | 0.895 | 0.772 | 0.967 | 0.156 |
| hybrid | 30 | 19 | 0.947 | 1.000 | 0.974 | 1.000 | 0.625 |
| dense | 30 | 19 | 0.684 | 0.947 | 0.816 | 1.000 | 9.675 |
| fusion | 30 | 19 | 0.789 | 1.000 | 0.886 | 1.000 | 9.098 |

## Limits

- 수작업 소규모 corpus/질문; 외부 독립 벤치마크 아님
- 검색/라우팅/추출형 답변 평가; LLM 품질/환각률 평가 아님
- 로컬 파이프라인 시간; 네트워크/LLM 지연 제외

## Failures (retained, not filtered)

### bm25: 1 failures
- t01: 국민카드를 잃어버렸어요. 앱으로 신고하는 방법이 궁금해요 / missing_topic_evidence / evidence=[]
### hybrid: 0 failures
### dense: 0 failures
### fusion: 0 failures
