# 깨비뚝딱 Generative UI v2 — 제약조건을 검증하는 금융 화면 구성

**서비스 흐름 기준:** [PDF 페이지별 구현 대응](docs/PDF_구현대응.md). 기존 채팅에서 상황을 입력해 금융 위젯 화면을 구성하는 경험을 유지합니다. 미리보기도 채팅을 시작점으로 수정했으며, 기존 React 프론트의 로컬 통합은 [프론트 연동 문서](FRONTEND_INTEGRATION.md)를 참고하세요. 공개 배포는 아직 변경하지 않았습니다.

개발 중심은 **자연어 요청 → 금융 위젯 선택·우선순위 → 의존관계 검증 → 화면 JSON → 렌더링 → 후속 수정**입니다. 문서 검색과 계산은 필요한 위젯 안에 넣는 데이터 공급자입니다.

## 기존 서비스에서 확장한 지점

v1은 GPT Function Calling으로 정해진 9개 위젯 중 최대 3개를 선택합니다. 여행·모임·분실 시나리오별로 세 개를 묶어 고르도록 프롬프트가 되어 있습니다.

v2는 기존 type ID를 포함하는 16개 레지스트리에서 필요한 기능을 조합합니다. 모델은 결과·업무 위젯 최대 4개를 선택하고, 서버가 입력 의존성을 추가한 최종 화면은 최대 6개입니다. 서로 다른 목적을 한 화면에 묶고, 후속 요청으로 일부 위젯을 추가·삭제·이동할 수 있습니다. 후보 검색의 상대 점수 컷오프는 휴리스틱이며 정답 확률이 아닙니다. 후보 누락도 평가해야 합니다. 임의 HTML/JS를 생성하지 않고 승인된 컴포넌트의 구조화된 화면 설계만 생성합니다.

| 단계 | 실제 구현 |
| --- | --- |
| 위젯 카탈로그 검색 | 실제 다국어 cross-encoder가 요청과 위젯 목적의 관련도를 계산하고 후보를 좁힘. 기존 위젯은 후속 수정 후보에 유지 |
| AI 화면 설계 | 로컬 Qwen3-4B 4bit 모델이 title / widget type / priority / clarification을 생성 |
| 생성 제약 | Outlines JSON 토큰 제약 + Pydantic 재검증 |
| 화면 컴파일 | 중복·허용 목록·최대 6개·정지/해제 충돌 검사 |
| 데이터 흐름 | 결과 위젯의 필수 입력 위젯 자동 추가, 위상 정렬, binding 생성 |
| 후속 수정 | 현재 위젯 목록을 모델 문맥에 전달하고 새 전체 설계에서 add/remove/update patch 계산 |
| 상태 보존 | 유지된 계산 위젯의 입력값과 계산 결과를 후속 화면에서도 보존 |
| 동시 수정 | SQLite revision 비교 후 조건부 갱신; 낡은 revision은 HTTP 409 |
| 제한적 재시도 | 설계가 서버 검증에 실패하면 사유를 주고 1회만 모델 재시도 |
| 실제 서비스 연동 | Spring `POST /api/canvas/v2` → Python `/canvas/compose` |
| 미리보기 | `/canvas/preview`가 같은 JSON을 실제 위젯 카드·입력 폼·계산 결과로 렌더링 |

### 예시

1. “예금 유지·해지 비용과 예금보호 기준을 같이 보고 싶어.”
2. AI가 비용 비교 + 보호 기준을 고르면, 서버가 비교 조건 입력 위젯을 추가하고 입력→결과 binding을 연결합니다.
3. 입력 폼에서 원금·금리·기간 등을 넣으면 서버 Decimal 계산 결과를 해당 위젯에 넣습니다.
4. “기존 화면에 대출 월 상환표도 추가해줘.”라는 후속 요청에서 기존 화면과 계산 상태를 유지하며 상환 입력/결과 위젯을 추가합니다.

위 설명은 원하는 기능의 흐름입니다. 실제 모델이 모든 표현에 정확한 위젯을 선택한다는 보장은 없습니다. 재현 가능한 구성 평가와 실패는 `reports/canvas-local-v3.json`에 기록합니다.

## 왜 백엔드·AI 과제로 설명할 수 있나

화면 디자인 자체보다 **생성 모델의 출력을 실행 가능한 UI 계약으로 바꾸는 과정**이 과제입니다.

- JSON이 문법적으로 맞아도 필요한 기능이 빠지거나 불필요한 위젯이 섞일 수 있습니다. 구조 검증과 의미적 위젯 선택 평가를 구분합니다.
- 계산 결과가 입력보다 먼저 오거나 입력 위젯이 빠지면 화면에서 작업할 수 없습니다. 의존관계와 데이터 binding을 서버에서 다룹니다.
- “이것만 빼줘”가 나머지 상태를 지우거나 동시에 보낸 요청이 서로 덮어쓰면 서비스가 깨집니다. patch·상태 보존·revision 충돌을 확인합니다.
- 카드 정지 같은 실행 기능을 보여주는 것과 금융 API를 실제 실행하는 것은 다릅니다. v2는 인증·기관 연결이 없는 액션을 비활성으로 반환하고 완료 상태를 생성하지 않습니다.

새 알고리즘을 발명했다거나 연구 수준이 보장된다는 주장은 아닙니다. 작은 프로토타입을 서비스 중심으로 확장해 실험·검증하는 작업입니다.

## 실행

### 1. 로컬 화면 설계 서비스

Apple Silicon Mac에서 준비한 무료 공개 모델을 실행합니다. 화면 모델은 `mlx-community/Qwen3-4B-4bit`, 후보 검색 모델은 `BAAI/bge-reranker-v2-m3`입니다. 유료 API 키는 필요 없습니다.

```bash
python -m pip install -r requirements-research.txt
python -m rag_backend.prepare_research_models --download
RAG_ENABLE_CANVAS=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
python -m uvicorn rag_backend.app:create_app --factory --host 127.0.0.1 --port 8767
```

미리보기: `http://127.0.0.1:8767/canvas/preview`

### 2. 기존 Spring 서비스

```bash
MAVEN_USER_HOME="$PWD/var/maven-home" ./mvnw \
  -Dmaven.repo.local="$PWD/var/maven-repository" spring-boot:run \
  -Dspring-boot.run.arguments=--server.port=8088
```

```bash
curl -X POST http://127.0.0.1:8088/api/canvas/v2 \
  -H 'Content-Type: application/json' \
  -d '{"message":"예금 유지 해지 비교와 예금보호를 같이 보여줘","institution":"kb_bank","as_of":"2026-11-02","expected_revision":0}'
```

최초 응답의 `session_id`, `revision`을 후속 요청의 `session_id`, `expected_revision`으로 전달합니다. 기본 세션 유효기간은 30분입니다. 요청 원문과 원시 모델 출력은 화면 상태 DB에 저장하지 않습니다. **입력 금액과 컴파일한 화면 상태는 세션 DB에 남습니다.** 실제 사용자 데이터 운영 전 접근제어·보존정책 설계가 필요합니다.

`CANVAS_COMPOSER_URL`로 Spring이 연결할 주소를 서버 설정에서 바꿀 수 있습니다. 사용자 요청으로 이 주소를 덮어쓰지 않습니다.

## 연결된 데이터와 남은 부분

- 예금 비교·대출 상환 위젯: 사용자가 입력한 수치로 실제 서버 계산. 모델이 숫자를 생성하지 않습니다.
- 예금보호·카드 해제·자동납부 안내: 검수된 공식 문서 청크를 위젯 안에 반환. 기관·기준일 조건을 적용합니다.
- 기존 여행·모임·출금 등의 v2 위젯: 데이터 어댑터 미연결 상태를 표시하는 미리보기입니다. 계좌 잔액·실거래·보험 가입·인증번호를 생성하지 않습니다.
- 기존 React 프론트의 로컬 체크아웃은 v2 작업 API와 연결했고 안정적인 ID·폼 상태 보존을 적용했습니다. 공개 배포는 변경하지 않았습니다.
- 정해진 레지스트리 밖의 새로운 React 컴포넌트를 AI가 직접 코딩하는 기능은 없습니다.
- layout은 AI가 위젯/우선순위를 정하면 서버가 12열 grid 규칙으로 배치합니다. 임의 좌표를 AI가 최적화하는 모델은 아닙니다.

## 검증 명령과 파일

```bash
python -m pytest tests_rag -q
python -m rag_backend.evaluate_canvas_http
MAVEN_USER_HOME="$PWD/var/maven-home" ./mvnw -q \
  -Dmaven.repo.local="$PWD/var/maven-repository" test
```

화면 평가 스크립트는 localhost의 실제 모델을 호출합니다. 개발자가 만든 작은 회귀 사례이며, 외부 블라인드 벤치마크가 아닙니다. 결과를 보고 수정한 뒤 재평가한 실행은 그 사실을 표시합니다.

- `rag_backend/canvas.py`: 레지스트리·화면 DSL·컴파일러·세션·데이터 공급자.
- `rag_backend/canvas_preview.html`: 실제 화면 렌더러와 사용자 입력 폼.
- `src/main/java/.../CanvasV2Controller.java`, `CanvasComposerClient.java`: Spring 연동.
- `tests_rag/test_canvas.py`: 의존관계·수정 상태·동시 갱신·액션 계약 테스트.
- `reports/canvas-initial-protocol-failure.json`: 초기 프롬프트 중복 처리에서 발생한 실패.
- `reports/canvas-local-v3.json`: 더 큰 모델·후보 검색·프롬프트를 개선한 뒤 실제 모델 회귀 결과. 같은 개발 사례를 재사용했으므로 독립 성능 추정이 아닙니다.

## 보조 실험 위치

문서 RAG와 임베딩 학습은 이 서비스의 위젯 검색·근거 공급에 활용할 후보 기술입니다. 별도 금융 챗봇을 제품의 중심으로 삼지 않습니다.

- [기존 근거 검색·계산](RAG_README.md)
- [생성 모델·재정렬 보조 실험과 프로토콜 한계](RESEARCH_README.md)
- `reports/encoder-adaptation-v1.json`: 52개 관련성 쌍으로 임베딩 모델 마지막 2개 층, 3,548,928개 파라미터를 실제 로컬 학습한 탐색 결과. 일부 단일 근거 검색은 개선됐지만 복합 질문 Recall@2는 악화되어, 화면 구성의 기본 검색기로 채택하지 않았습니다.
