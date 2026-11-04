# 금융 안내 근거검색 API

2026-11-03 추가: 실제 로컬 생성 LLM의 질문 분해·답변 생성과 다국어 cross-encoder 재정렬 실험은 [RESEARCH_README](RESEARCH_README.md)를 확인하세요. 아래 내용은 기존 주제 선택형/발췌형 API 설명입니다.

금융 안내 문서를 검색할 때 기관·상품의 절차를 섞지 않고, 답변의 출처와 처리 과정을 확인할 수 있는 백엔드 실험입니다.
기존 깨비뚝딱 Spring 서버와 독립적으로 실행하는 Python 서비스입니다. 기존 서비스와 HTTP 연동은 아직 하지 않았습니다.

## 실행

저장소 루트에서 Python 3.12 기준으로 실행합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-rag.txt
python -m uvicorn rag_backend.app:create_app --factory --host 127.0.0.1 --port 8765
```

API 문서: `http://127.0.0.1:8765/docs`. `/health`에서 corpus 버전과 모델 설정을 확인합니다.

이 작업 환경에는 `.venv`와 로컬 모델을 준비했습니다. `.venv/bin/python`으로 바로 실행할 수 있습니다.

### 로컬 의미 검색 활성화

```bash
python -m pip install -r requirements-local-embeddings.txt
python -m rag_backend.dense
RAG_ENABLE_DENSE=1 HF_HUB_OFFLINE=1 python -m uvicorn rag_backend.app:create_app --factory --host 127.0.0.1 --port 8765
```

모델 준비 명령만 공개 가중치를 다운로드합니다. API 실행과 평가는 준비된 모델 파일만 읽습니다.
모델은 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, 384차원, CPU 실행입니다.
모델·캐시·SQLite는 `var/`에 저장하며 Git에 포함하지 않습니다.

## API 예시

```bash
curl http://127.0.0.1:8765/health
curl -X POST http://127.0.0.1:8765/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"분실 신고한 카드를 찾았어요. 해제하려면?","institution":"kb_securities","retriever":"hybrid","generation":"extractive"}'
```

기관을 `kb_card`로 바꾸면 해당 기관 문서 범위에서 다시 검색합니다. 기관을 특정할 수 없으면 `clarify`로 재질문합니다.

| 경로 | 역할 |
| --- | --- |
| `GET /health` | corpus 버전, 문서 수, 사용 가능한 검색기, LLM 설정 여부 |
| `GET /sources` | 원문 URL, 기관, 확인일 |
| `POST /search` | 기관 범위 내 검색 결과와 점수 |
| `POST /finance/analyze` | 최대 4개 주제별 근거 검색·날짜 검증·선택한 계산 도구 실행 |
| `POST /finance/calculate` | 단리·원리금균등 상환표·유지/해지 이자 차이 계산 |
| `POST /ask` | 기관/질문 확인 → 검색 → 주제 근거 확인 → 답변 → 근거 검증 |

`status`는 `answered`, `clarify`, `not_found`, `blocked` 중 하나입니다.
질문·기관이 충돌하면 확인을 요청하며, corpus에 없는 배송·수수료·환율·보상 판단을 추측하지 않도록 제한합니다.
이는 제한된 도메인용 규칙 기반 라우팅입니다. 임의의 모든 금융 질문에 대한 근거 부족을 판별하는 범용 모델은 아닙니다.

### 검색 방식

| `retriever` | 구현 |
| --- | --- |
| `bm25` | 공백/단어 토큰 BM25 기준선 |
| `hybrid` | BM25 + 한국어 문자 2/3-gram TF-IDF + 고정 용어 확장, RRF 결합. **둘 다 lexical 검색** |
| `dense` | 실제 로컬 다국어 신경망 임베딩과 exact cosine search |
| `fusion` | lexical hybrid와 dense 순위를 RRF로 결합 |

문자 TF-IDF를 의미 임베딩으로 부르지 않습니다. 작은 corpus이므로 exact cosine을 사용하며, 대규모 ANN 벡터DB 성능은 검증하지 않았습니다.
기관 metadata 필터는 네 검색 방식 모두에 적용됩니다. RRF 점수는 확률이나 신뢰도가 아닙니다.
`/ask`의 근거 주제 필터와 `/search`의 원시 순위는 다르므로 평가도 구분합니다.

### LLM 모드

`OPENAI_API_KEY`, 선택적으로 `OPENAI_MODEL`을 서버 환경에 설정한 뒤 `generation: "llm"`을 명시해야 호출합니다.
기본 모델 이름은 기존 프로젝트와 같은 `gpt-4o-mini`입니다. `.env`를 자동으로 읽거나 키를 저장하지 않습니다.
Responses API의 JSON Schema 출력, 타임아웃, 실패 시 추출형 fallback을 구현했습니다.
사용자 요청에 따라 이 개발 작업에서는 유료 API를 호출하지 않았습니다.

LLM이 반환한 evidence ID, 정확한 인용문 포함 여부, 숫자 일관성을 서버에서 검사합니다.
**이 검사만으로 문장 전체의 의미적 사실성을 보장하지 않습니다.** 실제 LLM 평가에는 별도 사람 검수가 필요합니다.
API 키가 없으면 명시적으로 503을 반환하며, 실패/검증 오류는 `extractive_fallback`으로 구분합니다.

## 데이터와 재현

- 공식 원문 8개를 웹에서 확인해 사람이 재서술한 검수 요약 26개입니다. 기존 카드 안내 19개에 금융 제도·예금담보대출·중도해지 비교 7개를 추가했습니다. 원문 전체 자동 크롤링 자료가 아닙니다.
- 확인일은 2026-11-02이며, 문서 내용의 시행일/최신성을 보장하는 날짜가 아닙니다.
- 원문: [KB국민카드 안내](https://kbthink.com/card/lost.html), [KB증권 FAQ](https://www.kbsec.com/go.able?linkcd=s010423030000), [KB국민은행 도움말](https://obank.kbstar.com/quics?helppage=C019937&page=C019698), [신한카드 안내](https://www.shinhancard.com/pconts/html/helpdesk/guide/CONFM90016/CONFM90016R03.html).
- 실제 고객 자료·계좌·실거래 API가 아닙니다. 신고/해제/송금/재발급을 실행하지 않습니다.
- SQLite corpus는 원자적으로 교체합니다. 중복 ID·허용되지 않은 출처·기관/호스트 불일치·미래 확인일은 거부합니다.
- corpus SHA-256 버전, 평가 데이터 SHA-256, corpus 스냅샷을 보고서에 남깁니다.
- 임베딩 캐시는 문서 내용 SHA-256과 ONNX 가중치 SHA-256 기반 모델 식별자로 분리합니다. 질문은 디스크에 캐시하지 않습니다.
- 요청 감사 로그에는 ID·상태·사유·지연만 저장하며 질문 원문·비밀번호·API 응답 본문은 저장하지 않습니다.

### 새 문서 준비

`rag_backend.prepare_document`는 로컬 PDF/TXT/Markdown을 겹침이 있는 청크로 나누고 PDF 페이지 번호와 입력 파일 해시를 보존합니다.
스캔 PDF OCR은 지원하지 않습니다. 후보 파일 생성 후 사람이 추출문·기관·주제·출처를 검수해야 하며, 승인 corpus에 자동 반영하지 않습니다.

```bash
python -m rag_backend.prepare_document local-guide.pdf \
  --source-id reviewed-guide --institution kb_card \
  --url https://kbthink.com/card/lost.html --title '검수할 안내 문서' \
  --topic report --verified-at 2026-11-02 --output var/review-candidates.json
```

위 URL은 형식 예시입니다. 실제 입력 문서에 맞는 원문 URL로 바꾸어야 합니다.

## 테스트·실험

```bash
python -m pytest tests_rag -q
python -m rag_backend.evaluate --split dev --output reports/dev.json
HF_HUB_OFFLINE=1 python -m rag_backend.evaluate --split test --local-dense --output reports/test-local.json
```

평가 스크립트는 유료 API를 호출하지 않습니다. 고정 질문은 dev 12개와 test 30개이며 사람이 같은 corpus를 보고 작성했습니다.
개발 중 확인한 dev 결과로 신고 방법/시간/해외 신고의 근거 범위를 분리했습니다.
test는 개발과 나누어 보고하지만 **외부 독립 블라인드 벤치마크는 아닙니다**. 이후 반복 사용 시 탐색적 회귀 평가로 해석해야 합니다.

- Hit@1/3: 답변 가능한 19개 질문에서 정답 근거 청크가 상위 1/3개에 있는 비율
- MRR@3: 상위 3개 내 첫 정답 근거 순위의 역수 평균
- 상태 정확도: 답변/재질문/근거 없음/차단의 정답 상태 일치율
- End-to-end: 상태와 반환된 근거 ID가 수작업 정답에 맞는 비율. 의미적 답변 품질 점수가 아님
- 지연: 모델 초기화 후 로컬 파이프라인 처리 시간. 외부 API·LLM 생성·네트워크·부하 지연을 포함하지 않음

ONNX 초기화/파일 해싱 시간과 임베딩 cache hit 수는 별도 metadata로 기록합니다.
단위 테스트의 모의 임베더·모의 LLM과 `--local-dense`의 실제 모델 실행을 혼동하지 마세요.


## 금융 워크플로 확장

`/finance/analyze`는 자연어를 자동 해석하는 LLM 계획기가 아닙니다. 호출자가 지정한 주제를 서버의 고정 레지스트리에 따라 처리합니다.
지원 주제: `protection`, `collateral`, `collateral_eligibility`, `collateral_close`, `funding_compare`, `funding_inputs`. 한 번에 서로 다른 주제 최대 4개입니다.
기관은 각 주제 레지스트리에 고정하며, 서로 다른 기관의 자료는 출처별 claim으로 반환합니다.

```bash
curl -X POST http://127.0.0.1:8765/finance/analyze \
  -H 'Content-Type: application/json' \
  -d '{"topics":["protection"],"as_of":"2025-08-31","retriever":"fusion"}'

curl -X POST http://127.0.0.1:8765/finance/analyze \
  -H 'Content-Type: application/json' \
  -d '{"topics":["funding_compare","funding_inputs"],"calculation":{"kind":"funding_comparison","maturity_interest_net_won":"1000000","early_interest_net_won":"300000","loan_principal_won":"10000000","annual_loan_rate_percent":"3.65","loan_days":100,"extra_loan_cost_won":"10000"}}'
```

단리 `simple_interest`와 월 원리금균등 `amortized_loan` 입력 필드는 `/docs`의 스키마에서 확인합니다.
금액 단위는 원, 이율 단위는 퍼센트(3.65 = 연 3.65%)이며 금리·세율·비용은 모두 사용자 입력입니다.
계산 결과는 원 단위 ROUND_HALF_UP, 문자열 금액·수식·가정과 함께 반환합니다. 실제 상품의 절사/휴일/복리/변동금리 규칙은 반영하지 않습니다.
예금 유지/해지 계산은 이자 차이만 비교하며 재투자·시점별 현금흐름을 포함한 종합 추천이 아닙니다.

`as_of`는 `/search`, `/ask`, `/finance/analyze`에 사용할 수 있습니다. 미래 날짜는 422로 거부합니다.
발표일 이전·내용 기준일 이전·시행 구간 밖 문서는 검색에서 제외합니다.
발표일/시행일이 없는 기존 안내는 시점 보장을 하지 않습니다. 미기재 종료일은 최신성 자동 확인을 뜻하지 않습니다.
일부 주제의 근거만 있으면 `partial`, 겹치는 시행 기록은 `conflict` 구간으로 응답합니다.

```bash
HF_HUB_OFFLINE=1 python -m rag_backend.evaluate_finance
```

금융 날짜 실험은 7개 날짜와 4개 표현의 조합입니다. 기존 test 30개와 별도로 해석합니다.
자세한 결과·한계·지원서 문장은 [개발 정리](docs/RAG_개발정리.md)를 확인하세요.

## 배포 준비

`Dockerfile.rag`는 기본 추출형 API용이며 로컬 임베딩 모델을 포함하지 않습니다.
이 환경에는 Docker 실행기가 없어서 이미지 빌드/컨테이너 실행은 미검증입니다.
현재는 localhost 개발 서버용이며 공개 배포 전 인증·사용자별 권한·요청 제한·운영 로깅을 추가해야 합니다.

```bash
docker build -f Dockerfile.rag -t kkbb-rag .
docker run --rm -p 127.0.0.1:8765:8000 kkbb-rag
```

## 참고 문서

- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)
- [FastEmbed 지원 모델](https://qdrant.github.io/fastembed/examples/Supported_Models/)

실험 해석, 지원 분야와의 연결, 남은 작업은 [개발 정리](docs/RAG_개발정리.md)를 확인하세요.
