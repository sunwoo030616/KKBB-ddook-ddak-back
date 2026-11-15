# 정제 메뉴 검색: E5 → JEV

기존 9종 위젯의 `/api/canvas`는 유지한다. 새 `POST /api/menus/select`는 정제한 585개 메뉴 전체를 로컬 E5로 검색하고, 후보에 대해서만 JEV를 **1회** 호출해 메뉴 1개를 선택한다. 업무 기획용 첫 JEV, Strands Decider, 키워드 검색·혼합 점수·질문 확장은 사용하지 않는다. 현재 API는 단일 업무 선택용이며 여러 독립 업무는 확인 요청 대상이다.

## 데이터 점검

입력: 사용자가 제공한 `kb_starbanking_menu_structure_cleaned.json`. 628개에서 활성 585개와 제외 43개(허브/콘텐츠 41개, 상품 변형 통합 2개)로 정리된 데이터다. 활성 ID·정규화 메뉴명 중복은 0개다. 활성 항목을 추가 삭제하거나 합치지 않았다. 제외 항목과 기존 별칭도 보존했다.

이름·설명·선택 조건의 일치 및 유사 메뉴명을 검사하고 해당 항목을 검토했다. 보험사별 상품 5개의 설명/조건, 연금보험 2개의 조건, 공과금 조회 2개의 조건이 반복됐다. 다른 회사/상품은 독립 메뉴이므로 유지하고 조건을 구체화했다. 자동이체 등록/조회/변경/해지, 거래외국환은행 지정의 상위/신청/조회, OTP 신규/재발급도 구분했다. 총 13개 항목을 수정했다. 건강보험 2개의 일반 설명은 같지만 이름과 선택 조건은 다르므로 유지했다. 자녀 티머니 충전과 일반 충전 서비스 가입도 대상/동작이 달라 유지했다.

상세 변경 전후와 원본/통합 파일 해시는 `menu-catalog-audit.json`에 기록한다. 이 검토가 모든 의미 중복 부재나 실제 은행 기능을 보증하지는 않는다. 외부 은행 화면을 새로 검증하지 않았으며, 원문에 없는 기능/이용자격/혜택은 추가하지 않았다.

## 실행

처음 설치하는 환경:

```sh
python3 scripts/semantic/setup.py
```

기존 `.semantic-runtime`이 있으면 검증된 모델 파일을 재사용할 수 있다. 로컬 검색 서버 실행:

```sh
sh scripts/semantic/start.sh
```

다른 터미널에서 `JEV_AI_API_KEY`를 설정한 후 백엔드를 실행한다.

```sh
./mvnw spring-boot:run
curl -X POST http://localhost:8080/api/menus/select \
  -H 'Content-Type: application/json' \
  -d '{"message":"등록해둔 자동이체를 해지하고 싶어요."}'
```

`MENU_TOP_K` 기본 40, 범위 1~40. 검색 서버 주소는 `MENU_SEMANTIC_URL` 기본 `http://127.0.0.1:18083/search`. 로컬 HTTP 주소만 허용한다. 모델은 `intfloat/multilingual-e5-small`, revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`으로 고정하고 파일 해시를 검사한다. 이름·설명·선택 조건·별칭을 `passage:`로, 요청을 `query:`로 임베딩한다. 정규화 벡터 내적을 사용한다.

카탈로그 원본 바이트 해시를 벡터 캐시 키와 검색 요청에 포함한다. 변경한 585개 데이터는 새 캐시를 생성한다. 628개 벡터를 재사용하지 않으며 서버와 백엔드 데이터가 다르면 503으로 실패한다. E5 장애에 JEV 전체 카탈로그 전달이나 키워드 폴백을 하지 않는다.

응답 필드:

- `status`: `selected`, `no_match`, `needs_clarification`.
- `menus`: 선택되면 메뉴 1개, 나머지는 빈 목록.
- `candidateIds`: E5 검색 순서의 후보 ID.
- `confidence`, `pipeline: "e5_jev"`, `catalogSha256`, `retrievalMs`, `selectionMs`, `jevCalls: 1`.

외부 JEV 호출 직전에 기존 민감정보 마스킹을 적용하고, 연속 장애 시 호출을 제한한다. 후보 밖 ID·잘못된 confidence/응답은 502, JEV 연결 오류는 504, 키/검색 서버 미설정 또는 장애는 503. 0.6 기본 임계값은 정확도를 보증하는 보정 확률이 아니다. 이 API는 메뉴 추천만 하며 금융 액션을 생성·실행하지 않는다. 기존 모의 실행 API 권한을 우회하지 않는다.

## 평가

제공한 20문항을 그대로 `src/test/resources/menu-selection-cases-20.json`에 보존했다. 설명 보강 후 실제 로컬 ONNX E5를 실행한 개발 문항 결과:

| 정답 후보 포함 | 결과 |
| --- | --- |
| Top-5 | 18/20 |
| Top-10 | 19/20 |
| Top-20 | 19/20 |
| Top-40 | 20/20 |

자동이체 등록은 9위, 연락처 송금은 21위였다. 이 개발 결과를 보고 기본 K를 40으로 정했으므로 독립 평가가 아니다. 원본 628개와의 성능 비교는 측정하지 않았다. 검색 결과와 해시는 `menu-retrieval-evaluation.json`에 있다.

### 실제 E5 → JEV 최종 평가

2026년 11월 15일 14:11(KST), 실제 `/api/menus/select` 경로를 통해 JEV 모델 `jev-1.14.0`, Top-40, confidence 임계값 0.6으로 동일 20문항을 각 1회 실행했다. JEV 총 20회 호출, 재시도 없음. 정답 ID와 최종 메뉴 ID를 정확 일치로 비교했다.

| 항목 | 결과 |
| --- | --- |
| 최종 정답 | 20/20 (100%) |
| E5 정답 후보 포함 | 20/20 |
| API 오류 / 확인 요청 / 불일치 | 0 / 0 / 0 |
| 평균 HTTP 응답 | 260.30ms |
| P95 HTTP 응답 (nearest-rank) | 312.75ms |

원본 결과는 `menu-e5-jev-evaluation.json`에 문항별 후보 순서, 정답 순위, 선택 ID, confidence, 검색/선택/전체 응답 시간과 카탈로그·문항 해시로 보존했다. 모델 로딩·문서 벡터 준비·서버 시작은 지연에서 제외하고 질의 임베딩·JEV 네트워크·백엔드 처리는 포함한다. **설명 보강과 K 결정에 이미 사용한 개발 문항의 결과이며, 독립 평가나 전체 실사용 정확도 100%를 뜻하지 않는다.** 이번 최종 실행 중 프롬프트·카탈로그·정답은 수정하지 않았다. 외부 응답의 모델명을 별도로 캡처하지 않으므로 기록된 버전은 요청에 고정한 모델 ID다.

검색만 재평가(유료 호출 없음):

```sh
python3 scripts/semantic/evaluate.py --retrieval-only --output target/menu-retrieval.json
```

최종 E5→JEV 평가(먼저 백엔드에 `JEV_MODEL=jev-1.14.0` 설정; 문항당 JEV 1회, 총 20회 유료 API 호출). `--requested-model`은 실행 조건 기록용이며 백엔드 모델을 변경하지 않는다:

```sh
python3 scripts/semantic/evaluate.py --requested-model jev-1.14.0 --output target/menu-e5-jev.json
```

기존 위젯 프론트는 수정하지 않았다. 향후 585개 메뉴를 표시하려면 공통 메뉴 카드 컴포넌트 하나를 만들고 이 API의 이름/설명을 표시할 수 있다. 각 메뉴의 실제 업무 화면과 거래 연동은 별도 구현이 필요하다.
