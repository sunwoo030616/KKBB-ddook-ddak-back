# MCP·Skill과 수집 파이프라인 실행

깨비뚝딱 내부 지식을 검색·검수하는 로컬 도구다. 금융 위젯 화면 구성은 기존 React → Spring → 로컬 AI 흐름을 사용한다. 최신 수치와 한계는 [병목 분석·플랫폼 개선](문헌검색_병목분석_플랫폼개선.md)을 참고한다.

## 모델과 서버

기존 로컬 Qwen3·BGE·임베딩 준비는 [기존 실행 안내](모델비교_검색최적화.md)를 따른다. 이번에 추가한 작은 다국어 모델은 명시적으로 준비한다.

```bash
.venv/bin/python -m pip install -r requirements-research.txt -r requirements-local-embeddings.txt
.venv/bin/python scripts/prepare_multilingual_literature.py

OPENAI_API_KEY='' RAG_SYSTEM_PREFIX_CACHE=1 RAG_MLX_CACHE_MB=128 \
RAG_MPS_CACHE_POLICY=release .venv/bin/python scripts/dev_stack.py
```

서버가 이미 실행 중이면 실행 도구는 기존 프로세스를 재사용한다. 새 코드를 검사하려면 본인이 시작한 기존 AI 서버를 종료하고 다시 준비 상태를 확인한다. 모델 복사본을 중복 적재한 상태로 지연을 비교하지 않는다.

`POST /knowledge/research`의 기본은 `adaptive`다. 한국어·영어 원래 요청으로 검색하며, 불확실한 후보의 지원 여부만 최대 한 번 생성 모델에 묻는다. `anchored` 등 이전 실험 모드는 명시적으로 요청할 수 있다. 새 모델이 없으면 503, 문헌 작업이 이미 실행 중이면 429, 잘못된 입력은 422로 반환한다.

응답의 `latency_ms`는 그래프 처리, `resource_setup_ms`는 모델 자원 준비, `request_latency_ms`는 해당 엔드포인트의 처리 시간을 구분한다. 실제 HTTP 왕복 시간은 검증 스크립트에서 별도로 측정한다. 생성 결과 캐시 적중의 과거 prefill 관측값을 새 추론 시간으로 합산하지 않는다.

## MCP 도구 실행

```bash
.venv/bin/python -m pip install -r requirements-mcp.txt
.venv/bin/python -m rag_backend.knowledge_mcp --db var/knowledge.sqlite3
```

stdio 서버이므로 MCP 클라이언트가 이 명령을 저장소 루트에서 자식 프로세스로 실행한다. 클라이언트별 설정 파일을 자동 수정하지 않았다. 실제 SDK 연결 예시는 [검증 스크립트](../scripts/verify_knowledge_mcp.py)에 있다.

| 도구 | 역할 |
| --- | --- |
| `catalog_sources` | 종류별 문서 메타데이터와 키셋 커서 |
| `search_sources` | 모델을 부르지 않는 FTS5 어휘 검색 |
| `read_source_span` | ID·기대 해시·구간으로 현재 인용 재조회 |
| `research_literature` | 로컬 AI 검색 후 MCP에서 원문을 재검증 |
| `curation_status` | 검토 대기·준비·활성 릴리스 상태 읽기 |
| `knowledge_statistics` | 종류·문자 수·버전·중복 표본 집계 |

MCP에는 승인·발행·삭제·임의 SQL 실행 도구가 없다. 실제 승인은 기존 검토 CLI의 별도 작업이다. 검색 근거의 현재 버전과 인용 일치는 의미적 진실성의 인증이 아니다.

`knowledge://prompts/literature-adjudication/3`에서 현재 검증 지침과 해시를 읽는다. 이전 버전은 버전 번호를 바꿔 조회할 수 있으며, 현재 에이전트가 과거 출력 계약으로 실행되는 것은 아니다.

```bash
# 합성 자료로 실제 stdio 초기화·탐색·검색·인용 검증
.venv/bin/python scripts/verify_knowledge_mcp.py

# 실행 중인 AI 서버와 실제 문헌을 사용하는 읽기 전용 연결 검증
.venv/bin/python scripts/verify_knowledge_mcp_live.py
```

## Skill

[문헌 검토 Skill](../.agents/skills/kkbb-literature-review/SKILL.md)은 MCP 도구 선택, 인용 재조회, 본문을 지시로 취급하지 않는 규칙, 부족한 근거의 표시를 정리한다. 저장소에 작성·검증했으며, Skill을 사용하는 호스트에서 이 저장소의 Skill을 발견하거나 명시적으로 읽어 사용할 수 있다.

## JSONL 배치 수집과 SQL 조회

한 줄에 `id`, `title`, `text`, `kind`, `source_url`을 가진 JSON 객체를 넣는다. `kind`는 `abstract` 또는 `financial_summary`이고 출처는 HTTPS다. 레코드·행·배치 크기를 제한하며 입력 오류는 해당 배치를 커밋하지 않는다.

```bash
# 같은 파일로 재실행하면 파일 해시와 DB 커서로 이어서 처리
.venv/bin/python scripts/ingest_knowledge_jsonl.py var/input.jsonl \
  --db var/knowledge.sqlite3 --batch-size 200 --max-batches 5

.venv/bin/python scripts/analyze_knowledge.py

# 실제 지식베이스를 건드리지 않는 합성 5천 건 실험
.venv/bin/python scripts/benchmark_knowledge_pipeline.py --documents 5000
```

파일 해시·바이트 위치·행·리비전을 `ingestion_runs`에서 관리한다. 문서와 버전, FTS 트리거, 재개 위치를 하나의 트랜잭션으로 저장한다. 완료된 동일 파일은 다시 처리하지 않는다. 수정된 파일은 새 데이터셋 해시로 읽되 각 문서의 내용 해시가 같은 경우 재사용한다.

문서 종류와 ID를 함께 쓰는 표현식 색인으로 키셋 페이지를 조회한다. `OFFSET`으로 깊은 페이지의 앞부분을 반복 건너뛰지 않는다. FTS 질의는 제한된 리터럴 단어로 만들고 SQL 값은 매개변수로 전달한다. 이 저장소에서 검증한 규모는 실제 문서 56개와 별도 합성 5천 건이다.

설계 참고: [공식 MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk), [SQLite FTS5](https://sqlite.org/fts5.html), [SQLite 트랜잭션](https://sqlite.org/lang_transaction.html), [사용한 다국어 모델](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1).
