# 채팅 → 금융 캔버스: 기존 React 프론트 통합

2026-11-03 로컬 구현. 대상은 기존 `sunwoo030616/kkbb-ddook-ddak-front` React 앱입니다. 깨비 캐릭터, 최초 채팅 입력, 위젯 카드 흐름을 유지하면서 Spring v2와 연결했습니다.

## 실행

프론트는 백엔드 폴더와 나란히 `../kkbb-ddook-ddak-front`에 있습니다. 최초 준비:

```bash
# backend 디렉터리
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-research.txt
.venv/bin/python -m rag_backend.prepare_research_models --download --role canvas_generator --role reranker
# frontend 디렉터리
npm ci
```

Java 17과 Node/npm이 필요합니다. 첫 실행은 Maven 의존성을 네트워크로 준비합니다. 이미 준비한 환경에서만 `DEV_MAVEN_OFFLINE=1`로 오프라인 실행할 수 있습니다. 개발 스택 실행:

```bash
# backend 디렉터리
.venv/bin/python scripts/dev_stack.py
```

실제 응답으로 준비 상태를 확인해 Python AI → Spring → Vite를 시작합니다. 이미 같은 서비스가 응답하면 재사용하고, Ctrl+C는 이 스크립트가 시작한 프로세스만 종료합니다. 로그는 `var/dev-stack/`입니다.

접속: **http://localhost:5173**

| 경로 | 역할 |
| --- | --- |
| React `localhost:5173` | 기존 채팅·깨비·금융 위젯 화면 |
| Vite `/api` proxy | localhost Spring 연결; 브라우저에서 외부 LLM 호출 안 함 |
| Spring `127.0.0.1:8088/api/canvas/v2/jobs` | 작업 제출·진행 조회, FX 데이터 어댑터 |
| Python `127.0.0.1:8767/canvas/jobs` | 작업 큐·모델·화면 컴파일·세션 상태 |

`VITE_CHAT_API_URL=/api/canvas/v2`를 로컬 `.env.local`에 설정했습니다. 기존 `/api/canvas` v1 주소를 사용하는 배포 환경은 v2 주소와 프록시 설정을 함께 바꿔야 합니다. **공개 Netlify 사이트에 배포하지 않았습니다.**

## 실제 확인한 대화

1. “일본 여행 갈 거야” → 여행 목적지와 JPY를 기억하고 금융 위젯을 구성.
2. “3박4일이야. 보험은 빼줘” → 일본/JPY 유지, 4일 반영, 보험 제거.
3. “2만엔으로 환전 금액을 바꿔줘” → 금액과 통화 반영, 기간·나머지 위젯 유지.
4. 예금 유지·해지 비교 화면에서 입력한 수치로 결과 갱신. 같은 요청을 재전송해도 동일한 작업 ID를 재사용.

`reports/integrated-ui-v1.json`은 실제 로컬 모델·Spring 작업 API를 통과한 개발 회귀 기록입니다. 6개 요청의 10개 검사 항목을 통과했습니다. 동일 작성자·동일 사례를 반복 개선한 결과이므로 독립 성능 벤치마크로 해석하지 않습니다. 초기 실패 결과도 별도 파일에 남겼습니다.

## AI와 백엔드 개선

### 1. 상황 기억과 출처 검사

`canvas_context.py`는 목적지·기간·금액·통화·모임 정보를 typed slot으로 병합합니다. 모델이 제안한 값은 이번 발화의 정확한 인용 부분과 맞는지 검증합니다. 목적지에서 유도한 통화는 `destination_lookup`, 사용자가 직접 말한 정보는 `user_quote`로 구분합니다.

명확한 기간·금액 단위는 로컬 정규화기가 처리합니다. 모델이 과거 문장을 이번 입력처럼 다시 인용하거나 엉뚱한 정보를 제안하면 해당 슬롯을 거부하고 trace에 기록합니다. 유효한 화면 편집과 이미 확인한 맥락은 보존합니다. 이 처리는 모델이 항상 정확하게 추출했다는 주장이 아닙니다.

### 2. 구성 판단과 기계적 갱신을 분리

새 목적·기능 조합은 다국어 cross-encoder로 후보를 찾고 Qwen3-4B 4bit가 구조화된 화면을 설계합니다. 순수 기간·금액 변경과 기존 계산 폼 제출은 기존 화면 계약을 유지해 갱신하므로 LLM 호출이 없습니다. `trace.router.model_calls=0`으로 구분합니다.

후보 압축에는 상대 점수 휴리스틱과 포괄적 여행 준비 정책을 사용합니다. 부정 요청·복합 의도·미지명 지명 등 범용 한국어 의미 이해를 완전히 해결한 시스템은 아닙니다.

### 3. 화면 계약과 renderer capability

프론트가 표시할 수 있는 16개 type을 매 요청에 알립니다. 서버는 활성 registry와 capability의 교집합만 후보로 줍니다. 필수 입력 위젯 연결·중복·정지/해제 충돌·화면 예산을 검사하며, 실패한 설계는 1회만 재시도합니다.

registry의 활성 상태는 SQLite에 저장하며 실행 중 CLI로 on/off 할 수 있습니다:

```bash
python -m rag_backend.widget_registry disable travel_insurance_widget
python -m rag_backend.widget_registry enable travel_insurance_widget
```

새로운 React 컴포넌트 type의 무제한 무배포 등록을 구현한 것은 아닙니다. 신규 type 추가에는 typed 계약과 렌더러 구현이 필요합니다.

### 4. 비동기 모델 작업·중복 방지

프론트는 client request ID를 붙여 작업을 제출하고 실제 단계 상태를 조회합니다. 동일 ID/동일 내용은 동일 job을 반환해 중복 모델 호출을 막고, 동일 ID/다른 내용은 409입니다. 대기/실행 작업은 최대 8개, 완료 보관은 최대 128개, 기본 보관은 30분입니다. 단일 worker로 모델 자원 사용을 제한합니다.

작업 큐와 idempotency cache는 프로세스 메모리입니다. 서버 재시작 후 작업 복구와 여러 서버 간 중복 방지를 구현한 분산 큐는 아닙니다. 화면 세션은 SQLite revision으로 덮어쓰기를 막습니다.

### 5. React 상태 보존

위젯 key는 배열 위치가 아닌 안정적인 widget ID입니다. 입력 중인 폼 값은 ID별로 별도 보관합니다. API 실패·확인 요청에서는 기존 화면을 지우지 않고, 다른 세션/낡은 revision의 응답도 덮어쓰지 않습니다.

### 6. 서버가 공급하는 환율·금액

기존 ExchangeRate-API 어댑터를 v2 환전 위젯에 연결했습니다. 통화당 원화 참고 환율과 사용자가 지정한 외화 금액의 원화 추정치를 서버에서 계산합니다. 모델이 환율·잔액을 생성하지 않습니다.

출처·조회 시점·오래된 캐시 여부를 함께 반환하며 외부 호출에는 연결/읽기 제한시간, 단일 refresh, 장애 재시도 간격을 적용했습니다. 이 공급자의 open endpoint는 일 단위 자료이며 실제 은행 거래 환율이 아닙니다. 표시 화면에 출처 링크를 넣었습니다. [공급자 문서](https://www.exchangerate-api.com/docs/free)

## 실제 라우팅 기록

6개 자동 회귀 요청 중 4개는 LLM 계획을 사용하고, 금액 변경과 폼 계산 2개는 LLM 호출 없이 처리했습니다. 각 요청의 호출 수·실제 wall time은 `reports/integrated-ui-v1.json`의 `routing_profile`에 있습니다. 이 수치는 작은 회귀 사례의 실행 기록이며 운영 비용 절감률 실험으로 표현하지 않습니다.

React 브라우저에서는 추가로 입력 폼 제출 후 590,000원 계산 결과를 확인하고, 채팅으로 대출 월 상환표를 추가해도 기존 입력값과 결과가 보존되는지 확인했습니다. 기록은 `reports/browser-ui-verification.json`과 화면 이미지에 있습니다.

## 검증

```bash
# frontend
node --test tests/*.test.mjs
npm run lint
npm run build

# backend
.venv/bin/python -m pytest tests_rag -q
MAVEN_USER_HOME="$PWD/var/maven-home" ./mvnw -q -o -Dmaven.repo.local="$PWD/var/maven-repository" test
.venv/bin/python -m rag_backend.evaluate_integrated_ui
```

실제 React 화면의 대화·폼·결과는 브라우저에서도 확인합니다. 단위 테스트의 모의 모델과 실제 모델 회귀 결과를 구분해야 합니다.

## 남은 범위

로컬 통합이며 실제 금융 거래·계좌 연동·본인인증은 미연결입니다. 민감한 실행 버튼은 인증·기관 연결이 필요한 상태로 둡니다. 세션에는 선택된 상황 정보와 입력 금액이 저장될 수 있으며 실제 고객 서비스용 접근제어·보존정책은 별도 구현이 필요합니다.

## 설계 참고

- [Generative Interfaces for Language Models](https://arxiv.org/abs/2508.19227): 구조화된 인터페이스 표현과 반복 수정.
- [AI SDK의 Generative UI state 설명](https://ai-sdk.dev/docs/ai-sdk-rsc/generative-ui-state): 모델용 직렬화 상태와 렌더링 상태의 구분. 해당 RSC 기능은 실험적이며 이번 앱에 라이브러리를 도입한 것은 아닙니다.
- [AG-UI events](https://github.com/ag-ui-protocol/ag-ui/blob/main/docs/concepts/events.mdx): snapshot/delta 개념 참고. 이번 API는 자체 REST/job 계약이며 AG-UI 전체 호환 구현이 아닙니다.

## LLM 의미 검토 확장

복합·후속 요청의 누락·제외·유지를 원문 인용과 활성 카탈로그로 검토하고, 유효한 수정 의견이 있으면 한 번만 재설계하는 경로를 추가했습니다. 자기 검토의 오류와 지연을 포함해 비교합니다. 구현·프로토콜·제약은 [의미 검토 실험](docs/LLM_의미검토_실험.md)에 정리했습니다.

복합 요청 검색과 실제 비교에 따른 기본 설정 판단은 [AI 개발 정리](docs/AI_개발_정리.md)에서 함께 확인할 수 있습니다.


### 현재 프론트의 AI 실행 설정

React 요청은 `retrieval_mode=multi`, `review_mode=off`를 명시합니다. 복합 요청을 절별로 추가 검색하고 매우 낮은 관련도에서는 생성을 중단합니다. LLM 자기 검토는 비교에서 이득이 확인되지 않아 기본 UI 흐름에서 사용하지 않습니다. API의 `retrieval_mode` 기본값은 기존 호출 호환을 위해 `single`이며 직접 호출할 때는 `multi`를 지정합니다.

검색 모델의 장치는 기본 `auto`입니다. MPS가 있으면 float16, 없으면 CPU float32를 사용합니다. `RERANKER_DEVICE=cpu`로 기존 실행을 재현할 수 있고 `/health.reranker_execution`에서 실제 장치와 정밀도를 확인합니다. GPU 점수 차이는 `reports/reranker-mps-parity.json`에 기록했습니다.

## 검색 전 LLM 의도 계약

React는 `intent_mode=auto`도 명시합니다. 요청·제외·상황의 원문 구간 분류를 검색에 반영하고, 연결된 제외 type을 생성 후보에서 제거합니다. 삭제된 위젯의 입력 초안은 정리하고 남은 위젯의 값은 유지합니다. 정확한 전체 화면 비우기는 추가 모델 호출 없이 새 revision을 저장합니다. [의도 계약 문서](docs/LLM_의도계약.md)와 [실패·재시험 포함 결과](reports/intent-contract-results.md)에 정리했습니다.
