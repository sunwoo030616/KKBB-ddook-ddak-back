# 실제 E5 메뉴 UMAP

금융 메뉴 585개의 실제 384차원 E5 벡터를 UMAP으로 투영한다. 원본 코드·운영 API를 바꾸지 않는 독립 분석 도구다. 기존 평가의 실제 JEV 최종 선택을 재생하며 새 JEV 호출은 하지 않는다.

- `output/overview.png`: 전체 메뉴. 색은 원본 384차원 벡터에서 계산한 KMeans 12개 군집이며 공식 금융 업무 분류가 아니다.
- `output/example-1.png` ~ `example-3.png`: 엔화 환전·카드 분실신고·연락처 이체. 파란 원은 새로 계산한 E5 Top-40, 별은 기존 실제 JEV 선택이다. 숫자는 Top-10 순위이며 옆 목록에 원본 cosine을 표시한다.
- `output/e5_umap.html`: 인터넷 없이 여는 독립 HTML. 질문 드롭다운, 확대·축소·메뉴명/ID/실제 순위/cosine 호버를 제공한다. HTML에서 질문을 고르면 해당 후보·선택만 바뀐다.
- `output/embeddings.npz`: 실제 추론으로 생성한 ID 순서와 585×384 벡터. 모델 자체는 포함하지 않는다.
- `output/data.json`: 전체 좌표·군집·예시별 후보 순위·cosine·최종 선택.
- `output/metadata.json`: 모델·카탈로그·운영 코드·JEV 근거 파일·출력 SHA256, 실행 환경과 설정.
- `run.log`, `tests.log`, `verification.log`, `environment.txt`: 실제 생성·테스트·출력 검증 로그와 설치 환경.

## 실행

Python 3.9에서 실행했다. 운영 E5와 같은 ONNX·tokenizer 버전을 고정했으며 `environment.txt`에 하위 의존성까지 기록했다. 다른 플랫폼에서는 PNG 폰트와 UMAP 좌표의 미세한 수치 차이가 발생할 수 있다. 한글 PNG에는 AppleGothic 또는 NanumGothic/Noto Sans CJK KR 폰트가 필요하다.

```sh
python3 -m venv /tmp/e5-umap-venv
/tmp/e5-umap-venv/bin/pip install -r visualization/requirements.txt
# 모델은 기존 scripts/semantic/setup.py 안내에 따라 준비한다.
# model.onnx/tokenizer.json은 scripts/semantic/model_manifest.json의 해시와 일치해야 한다.
/tmp/e5-umap-venv/bin/python visualization/generate_umap.py \
  --model-dir /path/to/e5-model --output /tmp/new-e5-umap
python3 -m unittest discover -s visualization -v
/tmp/e5-umap-venv/bin/python visualization/verify_output.py
```

완료 결과 덮어쓰기는 거부한다. 별도 빈 출력 경로를 사용한다. 기본 예시 인덱스는 `--examples 2 0 9`, K=40이다. `--seed 42 --neighbors 15 --min-dist 0.1 --clusters 12`로 실행했으며 metric=cosine, n_jobs=1, SciPy KMeans 100회 반복·실제 점 표본 초기화이다. 인덱스는 0부터 시작한다.

## 실제 데이터와 재생 근거

`production_vectors()`는 현재 `scripts/semantic/server.py`를 로드하고 실제 운영 encode closure와 메뉴 벡터를 받는다. HTTP 서버 생성만 캡처하므로 포트가 필요 없다. 임시 모델 디렉터리에 원본 모델을 링크하고 빈 캐시에서 전체 585개 passage를 새로 추론한다. 운영 코드가 모델 manifest의 SHA256을 검증한다. 기존 캐시·가상 벡터·가상 점수·임의 선택 ID는 사용하지 않는다. 운영 closure 구조가 바뀌면 어댑터를 검토해야 한다.

`query: ` 접두어, 256토큰 제한, attention-mask 평균 pooling과 L2 정규화, 원본 float32 내적 및 stable 정렬을 그대로 사용한다. 모델은 `intfloat/multilingual-e5-small`, revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`이다.

JEV 근거는 기존 `docs/menu-e5-jev-evaluation.json`의 2026-11-15 실측 `jev-1.14.0` 응답이다. 새 실행으로 오해하지 않도록 PNG·HTML과 metadata에 재생임을 표시한다. 새 E5 Top-40 순서가 당시 후보 순서와 완전히 일치하는지 확인한다. 카탈로그 해시 불일치, 후보 순서 변경, 실제 호출이 없는 기록, 후보 밖 최종 선택은 오류로 거부한다. 기존 20문항 결과 전체를 다시 평가했다는 뜻은 아니며 3개 예시의 후보를 재현한 것이다.

다른 질문을 보여주려면 실제 E5→JEV 평가 결과 JSON을 `--evidence /path/to/measured.json --examples 0`으로 공급한다. 기존 평가와 같은 `mode`, `catalog_sha256`, `started_at`, `requested_model`, `results[].query/candidate_ids/selected/status/jev_calls` 형식이 필요하다. 수동으로 선택 ID를 넣어 실제 측정으로 취급해서는 안 된다.

## 해석과 한계

UMAP의 2차원 거리·군집 간 간격은 원본 cosine이나 순위가 아니다. 검색 순위와 점수는 항상 원본 384차원에서 계산한다. 색은 SciPy KMeans의 임의 군집 번호로 금융 업무의 정답 분류나 군집 품질 보증이 아니다. 시각화를 위해 모델을 재학습하지 않았다.

JEV 결과는 개발 질문에서 얻은 과거 실측이며 새로운 운영 정확도 검증이 아니다. 실제 사용자 트래픽, 복수 의도 처리, 최종 UI·거래 실행은 검증하지 않는다. 기존 Recall 300 변경을 포함하지 않고 기본 커밋 `3d65ad0`에서 독립 분기했다.

검증: 지표와 별개로 JEV 근거 검증 테스트 5개, 585개 벡터/좌표/해시·세 예시 후보 검증을 통과했다. 두 번의 새 임베딩 실행에서 동일 seed UMAP 좌표 585개가 모두 같았다. PNG는 직접 열어 한글과 강조 표시를 확인했다. HTML은 외부 스크립트가 없는지 정적으로 검증했으나, 브라우저의 로컬 파일 URL 접근 정책으로 클릭·호버 화면 검증은 수행하지 못했다. 실행 로그의 scikit-learn 인자명 변경 FutureWarning은 생성 실패가 아니다.
