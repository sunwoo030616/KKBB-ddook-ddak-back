# 백엔드 확장: 되묻기 · 안전 실행 · 판단 근거 · 피드백

대회 버전은 "AI가 위젯을 고르면 서버가 데이터를 채워 보여주는 것"까지였다.
jev 기반 위젯 선택(PR #8) 위에, 화면이 만들어진 **이후**를 백엔드에서 책임지도록 네 가지를 추가했다.

| 영역 | 해결한 문제 | 핵심 |
|---|---|---|
| 되묻기 + 세션 | 정보가 하나만 빠져도 빈 화면이 나옴 | 빠진 정보만 묻고, 답하면 jev 재호출 없이 완성 |
| 정책 엔진 + 안전 실행 | 위젯 버튼이 실제로 무엇을 실행하는지 경로가 없음 | 정책 as code → OTP → 1회 실행, 해시체인 감사 |
| 판단 근거 트레이스 | 왜 이 화면이 나왔는지 설명할 근거가 없음 | 요청별 위젯 판정·슬롯·단계 지연 조회 |
| 피드백 랭킹 | 모든 사용자에게 같은 순서 | 반응 점수로 순서만 보정 (추가·삭제 없음) |

```text
사용자 발화
  └─ POST /api/canvas {message, sessionId}
       ├─ 세션 조회 ── 되묻기에 대한 답? ──예──▶ 보류 위젯 완성 (jev 생략)
       │                                  └아니오▼
       ├─ jev 위젯 선택 → allowlist·개수·중복 검증
       ├─ 슬롯 추출 + 세션 병합 → 필수 슬롯 확인
       ├─ 준비된 위젯: 피드백 점수로 순서 보정 → 구성
       ├─ 빠진 슬롯: clarification_widget
       └─ DecisionTrace 저장 (GET /api/canvas/{requestId}/trace)

위젯 버튼 (action.type)
  └─ POST /api/actions → 정책 평가 ─ DENY ─▶ 차단 (사유 반환)
                                 ├ STEP_UP ▶ OTP 발송 → confirm(otp)
                                 └ ALLOW ──▶ confirm()
                         └─ ActionExecutor(Mock → Sandbox → KB API) 1회 실행
                         └─ 모든 단계 해시체인 감사 로그 (GET /api/audit/verify)
```

## 1. 되묻기 위젯과 세션

**문제**: "여행 환전이랑 보험 알려줘"처럼 통화가 빠지면, 기존 구현은 보험 위젯까지 포함해 화면 전체를 비우고 다시 입력하라고 했다.

**변경**
- 위젯별 필수 슬롯을 정의하고(`SlotRequirements`, 현재는 환전 위젯의 통화), 빠진 위젯만 보류한다.
- 나머지 위젯은 바로 그리고, 마지막에 `clarification_widget`으로 빠진 정보만 묻는다.
- 응답에 `sessionId`를 주고, 다음 요청에 `sessionId`가 오면 이전 슬롯과 병합한다 (30분 TTL).
- 다음 발화가 **빠진 정보에 대한 답**이면 jev를 다시 부르지 않고 보류 위젯을 완성한다. 새 요청이면 기존처럼 선택부터 다시 한다.
- 여행지가 바뀌면 이전 여행지의 통화·금액은 이어받지 않는다 (엔화 금액이 파운드로 넘어가는 오류 방지).

```text
1) "여행 환전이랑 보험 알려줘"
   → status: needs_clarification
     widgets: [travel_insurance_widget, clarification_widget(통화)]
2) "엔화로 3만엔"  (sessionId 포함)
   → status: ready, widgets: [travel_card_charge_widget(JPY, 30000)]   ← jev 호출 없음
```

`SessionStore`는 인터페이스이고 지금은 인메모리 구현이다. 인스턴스를 늘릴 때 Redis 구현으로 바꾸면 된다.

## 2. 정책 엔진과 안전 실행

**원칙**: AI는 화면만 제안한다. 돈이 움직이거나 보호를 푸는 실행은 `ActionService`에서만 일어난다.

### 정책 as code
| 규칙 | 결과 |
|---|---|
| `risk-level` | 고위험 액션(정지 해제, 카드 없는 출금)은 항상 추가 인증 |
| `amount-limit` | 100만원 초과 추가 인증, 500만원 초과 차단 |
| `night-time` | 0~6시 비보호성 액션은 추가 인증 |
| `velocity` | 10분 안에 같은 액션 3회 초과 시 차단 |

- 여러 규칙 중 **가장 엄격한 결과**가 최종 결정이고, 걸린 규칙과 사유는 전부 남긴다.
- **보호 방향은 빠르게, 위험 방향은 엄격하게**: 카드 일괄 정지 같은 보호성 액션은 심야·반복 규칙에서 제외했다. 지갑을 잃어버린 새벽 2시에 카드 정지를 추가 인증으로 막으면 안 되기 때문이다.
- 한도·시간대·횟수는 `application.properties`의 `app.policy.*`로 조정한다.

### 실행 흐름
- `POST /api/actions` (prepare): 정책 평가 후 차단 / OTP 발송 / 확인 대기
- `POST /api/actions/{id}/confirm`: 만료(5분)·소유자·OTP 확인 후 실행
- OTP는 해시로만 보관하고 상수 시간 비교, 3회 실패하면 잠기고 이후엔 맞는 번호도 거부
- `Idempotency-Key`가 같으면 새 액션을 만들지 않는다 (재시도·연타로 충전이 두 번 되는 것 방지)
- confirm을 여러 번 보내도 실제 실행은 1회
- 다른 사용자의 액션은 존재 여부도 알려주지 않는다 (404)
- 실행기는 `ActionExecutor` 포트로 분리했다. 지금은 Mock이고, Sandbox → KB API 순서로 구현체만 바꾸면 된다.

| 오류 코드 | HTTP |
|---|---|
| INVALID_REQUEST | 400 |
| DENIED | 403 |
| NOT_FOUND | 404 |
| IDEMPOTENCY_CONFLICT | 409 |
| EXPIRED | 410 |
| OTP_REQUIRED, OTP_MISMATCH | 422 (+ `remainingOtpAttempts`) |
| LOCKED | 423 |
| EXECUTION_FAILED | 502 |

### 해시체인 감사 로그
- 각 기록은 이전 기록의 SHA-256 해시를 포함한다. 중간 기록을 고치거나 지우면 연결이 깨진다. 마지막 기록 삭제나 전체 체인 재작성까지 확인하려면 별도로 보관한 최신 해시와 비교해야 한다.
- `GET /api/audit/verify` → `{valid, size, brokenAtSeq, headHash}`
- OTP·인증번호·계좌번호 등은 저장 전에 마스킹한다.

위젯에는 실행 정보만 붙는다.
```json
{ "type": "card_freeze_all", "...": "...",
  "action": { "type": "CARD_FREEZE_ALL", "endpoint": "/api/actions", "params": {} } }
```

## 3. 판단 근거 트레이스

`GET /api/canvas/{requestId}/trace` (`requestId`는 canvas 응답 본문과 `X-Request-Id` 헤더에 있음)

```json
{
  "status": "ready",
  "resumedFromSession": false,
  "selection": { "provider": "jev", "needsReview": false,
                 "selected": ["travel_insurance_widget"],
                 "candidates": [{"widget": "travel_insurance_widget", "choice": "include", "confidence": 0.91}, "..."] },
  "slots": { "currency": "JPY", "destination": "일본", "tripDays": 4 },
  "missingSlots": [],
  "rankingScores": { "travel_insurance_widget": 0.5 },
  "stages": [ {"name": "session", "durationMs": 0}, {"name": "selection", "durationMs": 212},
              {"name": "parameters", "durationMs": 1}, {"name": "build", "durationMs": 3} ]
}
```
- 깨비가 "왜 이 화면을 만들었는지" 설명할 근거, 오답 분석, 느린 단계 확인에 쓴다.
- 원문 메시지는 저장하지 않고 길이만 남긴다. 최근 500건, 1시간만 보관한다.
- 실패한 요청도 오류와 함께 기록된다.

## 4. 피드백 랭킹

- `POST /api/feedback {requestId, widgetType, event: CLICKED|COMPLETED|DISMISSED}`, `GET /api/feedback/scores`
- 해당 화면에서 표시한 위젯만 접수하고 같은 요청·위젯·이벤트는 한 번만 집계한다. 트레이스가 만료되면 404를 반환한다.
- 노출(SHOWN)은 화면을 만들 때 서버가 자동으로 기록한다.
- 점수 = (min(클릭 + 0.5×완료, 노출) + 1) / (노출 + 닫기 + 2). 노출 20회 미만이면 중립값 0.5로 원래 순서를 유지한다.
- **선택된 위젯의 순서만** 바꾼다. 어떤 위젯을 띄울지는 jev와 서버 검증이 정하고, 학습 결과가 그 범위를 넓히지 않는다.

## 발표용 로컬 프로필

`SPRING_PROFILES_ACTIVE=presentation ./mvnw spring-boot:run`으로 시작한다. 서버는 `127.0.0.1:8080`에서 열리고 JEV 키 없이 고정 입력과 예시 환율로 동작한다. 이 프로필은 화면 구성의 실제 세션·실행·피드백 API를 그대로 사용하며, 실행 결과는 모의 데이터다.

프론트 첫 화면의 **지갑 분실**, **해외여행 준비**, **동아리 회비 관리** 예시도 실행할 수 있다. 각 시나리오는 위젯 3개를 표시하며, 해외여행 예시는 위안화 예시 환율을 사용한다.

1. 프론트에서 **여행 환전이랑 보험 알려줘**를 눌러 보험 위젯과 통화 질문을 확인한다.
2. **엔화로 3만엔**을 보내면 `resumedFromSession: true`와 환전 위젯이 반환된다. 프론트는 먼저 표시한 보험 위젯을 유지한다.
3. **새 대화 → 분실 카드 정지해줘 → 카드 일괄 정지 → 정지 확인**으로 모의 실행과 완료 화면을 확인한다.
4. 위젯을 닫으면 해당 화면의 `requestId`로 피드백이 기록된다. `GET /api/feedback/scores`에서 집계를 확인할 수 있다.

일반 실행에서 환율은 6시간 캐시한다. 만료된 캐시를 갱신하는 동안 다른 요청은 최근 저장값을 바로 받는다. 환율 API 실패 뒤 30초간 재호출을 제한하며, 24시간이 지난 값은 제공하지 않는다.

## 시연 순서 (curl)

모의 실행·감사 조회를 시연하려면 로컬에서 `APP_ACTION_DEMO_ENABLED=true ./mvnw spring-boot:run`으로 서버를 시작한다. 기본 설정에서는 해당 API와 위젯의 실행 정보가 비활성화된다.

```bash
# 1) 되묻기
curl -s localhost:8080/api/canvas -H 'Content-Type: application/json' \
  -d '{"message":"여행 환전이랑 보험 알려줘"}'
# → sessionId 확인 후
curl -s localhost:8080/api/canvas -H 'Content-Type: application/json' \
  -d '{"message":"엔화로 3만엔","sessionId":"<sessionId>"}'

# 2) 판단 근거
curl -s localhost:8080/api/canvas/<requestId>/trace

# 3) 보호성 액션: 바로 확인 후 실행
curl -s localhost:8080/api/actions -H 'Content-Type: application/json' -d '{"type":"CARD_FREEZE_ALL"}'
curl -s -X POST localhost:8080/api/actions/<actionId>/confirm

# 4) 고위험 액션: OTP (시연 환경은 demoOtp로 응답)
curl -s localhost:8080/api/actions -H 'Content-Type: application/json' -d '{"type":"SMART_WITHDRAWAL_CODE"}'
curl -s localhost:8080/api/actions/<actionId>/confirm -H 'Content-Type: application/json' -d '{"otp":"<demoOtp>"}'

# 5) 한도 초과 차단
curl -s localhost:8080/api/actions -H 'Content-Type: application/json' \
  -d '{"type":"TRAVEL_CARD_CHARGE","params":{"amountKrw":9000000}}'

# 6) 감사 로그 검증
curl -s localhost:8080/api/audit/verify
```

## 테스트

| 테스트 | 내용 |
|---|---|
| `InMemorySessionStoreTest` | TTL 만료·연장, 용량 초과 정리, 슬롯 병합 |
| `JevCanvasClarificationTest` | 부분 렌더링, jev 재호출 없는 완성, 이전 슬롯 재사용, 새 요청 전환 |
| `PolicyEngineTest` | 규칙별 결과, 가장 엄격한 결과 선택, 보호성 액션 예외, 자정 넘는 구간 |
| `ActionServiceTest` | OTP 성공·실패·잠금, 차단, 1회 실행, 멱등키, 만료, 타 사용자, 실행 실패, 감사 기록 |
| `HashChainAuditLogTest` | 연결, 수정·삭제 탐지, 마스킹 |
| `JevCanvasTraceTest`, `TraceStoreTest` | 판정·슬롯·단계 기록, 되묻기 표시, 보관 상한 |
| `FeedbackRankerTest`, `JevCanvasRankingTest` | 최소 노출 전 순서 유지, 순서 보정, 추가·삭제 없음 |
| `ActionControllerTest`, `FeedbackControllerTest` | HTTP 상태·응답 계약 |

## 한계와 다음 단계

- 세션·액션·트레이스·피드백이 메모리에 있어 서버를 재시작하면 사라진다. 여러 인스턴스로 늘릴 때 Redis(세션·멱등키)와 DB(감사 로그·피드백)로 옮긴다.
- 사용자 식별은 시연용 `X-User-Id` 헤더다. 운영에서는 인증 토큰의 사용자로 대체한다.
- 필수 슬롯은 환전 통화 하나만 정의했다. 628개 기능 카탈로그가 들어오면 기능별 파라미터 스키마에서 필수 슬롯을 읽도록 바꾼다.
- 피드백 점수는 전체 사용자 기준이다. 사용자별·시간대별 분리는 데이터가 쌓인 뒤 판단한다.
