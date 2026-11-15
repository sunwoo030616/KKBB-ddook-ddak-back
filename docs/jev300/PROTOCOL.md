# 실제 E5→JEV 300문항 평가 조건

기존 Recall 평가와 정확히 같은 `scripts/semantic/recall300/cases.json`의 300문항을 원래 순서로 실행한다. 질문·정답·카탈로그·모델·선택 정책을 점수를 보고 바꾸지 않는다. 이 세트는 기존 합성 질문을 재사용했으므로 독립 실사용 평가가 아니다.

## 사전 판정 규칙

- 단일 업무 270문항: `status=selected`이며 반환 메뉴 ID가 기존 단일 정답과 정확히 일치해야 성공. 잘못된 메뉴, 확인 요청, no_match, API 오류는 모두 실패이며 분모 270에서 제외하지 않는다.
- 두 독립 업무 요청 30문항: 현재 운영 정책이 여러 독립 업무에 `unsure`를 요구하므로 공개 API가 `needs_clarification`과 빈 메뉴 목록을 반환해야 성공. 정답 두 개 중 하나만 고르면 실패. 메뉴 두 개를 모두 반환하는 정확도를 측정하는 실험은 아니다.
- 공개 API는 모델의 `unsure` 선택과 confidence<0.6을 모두 `needs_clarification`으로 변환한다. 따라서 이 비율은 API 확인 요청 적합률이며 JEV 원시 unsure 선택률이나 판단 근거의 정확도를 뜻하지 않는다.
- 전체 정책 준수율은 단일 업무 메뉴 일치와 복수 업무 확인 요청의 합계 / 300으로 별도 표기한다. 서로 다른 성공 조건을 합친 수치이므로 '300문항 메뉴 정확도'라고 부르지 않는다.
- 단일 업무에서 메뉴를 실제 반환한 경우만의 일치율도 보조 지표로 저장하지만, 오류·확인 요청을 제외한 이 수치로 전체 정확도를 대체하지 않는다.

## 실행

운영 Spring Boot `POST /api/menus/select`를 호출한다. 실제 백엔드가 민감정보 마스킹 → 실제 E5 검색 → JEV 선택 → 후보/응답 검증을 수행한다. 별도의 JEV 모사 호출이나 과거 결과 재생을 하지 않는다.

`jev-1.14.0`, `MENU_TOP_K=40`, `JEV_MIN_CONFIDENCE=0.6`, 로컬 E5는 기존 manifest의 ONNX 모델과 585개 메뉴 캐시를 사용한다. 질문당 1회 순차 호출, 재시도 없음. 3회 연속 오류면 중단하고 부분 결과를 보존한다. 오류가 생겨도 결과 행과 분모에서 제거하지 않는다. confidence는 정답 확률로 해석하지 않는다.

입력·운영 검색/선택 코드·평가 코드 해시는 `scripts/semantic/jev300/freeze.json`에 실행 전에 기록한다. 기존 IntelliJ 실행 설정의 키를 메모리에서 읽어 사용했고 키·인증 헤더는 결과나 로그에 기록하지 않는다. 결과는 응답별 후보 ID·최종 선택·상태·지연·JEV 호출 수를 저장한다. HTTP 오류의 upstream 호출 여부는 공개 API에서 확인할 수 없으므로 반환된 호출 수와 구분해야 한다.

## 재현

기존 E5 설치 안내로 모델을 준비하고 실행한다. 다른 터미널에서 키를 환경 변수로 설정한 후 다음과 같이 실제 백엔드를 실행한다.

```sh
# 터미널 1
.semantic-runtime/venv/bin/python scripts/semantic/server.py \
  --model-dir /path/to/model \
  --catalog src/main/resources/kb_starbanking_menu_structure_cleaned.json --port 18107
# 터미널 2: JEV_AI_API_KEY는 기존 보안 설정으로 제공
JEV_MODEL=jev-1.14.0 MENU_TOP_K=40 JEV_MIN_CONFIDENCE=0.6 \
MENU_SEMANTIC_URL=http://127.0.0.1:18107/search \
./mvnw spring-boot:run -Dspring-boot.run.arguments=--server.port=18108
# 터미널 3: 기존 결과 덮어쓰기 금지
python3 scripts/semantic/jev300/evaluate.py --output /tmp/new-jev300-results.json
python3 -m unittest discover -s scripts/semantic/jev300 -v
python3 scripts/semantic/jev300/verify.py
```

`verify.py`는 커밋에 보존된 `docs/jev300/results.json`을 재검산한다. 외부 JEV 응답은 서비스 상태·모델 배포 변화에 따라 달라질 수 있으며 같은 결과의 비트 단위 재현을 보장하지 않는다. 합성 단일 라벨의 대체 정답 누락과 독립 검수 부재는 기존 Recall 보고서의 한계를 그대로 갖는다. 최종 GenUI/거래 실행 정확도는 평가 범위 밖이다.
