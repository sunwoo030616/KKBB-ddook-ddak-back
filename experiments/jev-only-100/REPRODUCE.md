# 재현

`python -m pip install -r experiments/jev-only-100/requirements.txt`

`python -m unittest discover -s experiments/jev-only-100 -p test_protocol.py -v`

`python experiments/jev-only-100/verify_report.py`는 저장된900회 실제응답과 payload해시를 오프라인 재검산한다. 새 API호출 없음. 결과를 덮어쓸 수 있으므로 먼저 원본을 보관한다.

유료 재실행은 `JEV_AI_API_KEY` 환경변수와 `python experiments/jev-only-100/run.py --execute`를 사용한다. 기존 results.json이완료이면 재호출하지않는다. 새실행은디렉토리를복제하고기존결과를따로보존한뒤시작한다. 로컬IntelliJ설정경로는이전실행의개인환경참조이며필수아니다. 키는기록하지않는다.

이 runner는기존사례·정책·소스를freeze.json해시로고정한다. 기본카탈로그순서80×7+25청크,동시4청크,전역Noul상위10,최종120조합선택이다. 결과와비용·한계를README.md에서확인한다.
