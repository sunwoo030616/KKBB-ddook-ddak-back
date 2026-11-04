# Financial temporal retrieval ablation

Corpus: `dc20def3b9a26c5e`

| Method | Cases | Without date scope | With date scope |
| --- | ---: | ---: | ---: |
| bm25 | 28 | 10 | 22 |
| hybrid | 28 | 12 | 28 |
| dense | 28 | 12 | 28 |
| fusion | 28 | 12 | 28 |

## Limits

- 28개는 7개 날짜와 4개 표현을 조합한 상관된 탐색적 사례; 독립 표본 28개가 아님
- 공식 출처 2개/정답 청크 2개의 좁은 제도 사례
- 분류·검색 평가이며 생성 LLM·실상품 지급 판정 평가 아님
- 무기한 effective_until은 최신 정책 자동 확인을 의미하지 않음

각 사례의 실패와 실제 워크플로 출력은 같은 이름의 JSON 파일에 보존했습니다.
