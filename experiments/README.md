# 실제 응답과 사용자 승인 평가 기준

- `jev-only-100/README.md`: 전체585개메뉴 청킹 JEV단독과E5→JEV실측 비교. 원래정답표를유지한다.
- `model-answer-review/answers.html`: 최초5개구성의100문항실제답 비교. 이전평가기준으로작성된원본이다.
- `utility-review-100/`:메뉴설명기반 사후검토v1.
- `utility-review-100-v2/`:계좌·카드·연금·통신서비스보유여부를추정해감점하지않도록한수정.
- **현재승인기준: `utility-review-100-v3/README.md`, `answers.html`**. 사용자가기존조건부유효도모두유효정답으로승인한재집계다. E5→JEV개선·LLM단독·JEV단독만비교한다.

v3에서유효메뉴최소2개포함은100%/64%/100%,추천메뉴유효비율은95%/87.76%/96.67%다. 이수치는사후사용자승인기준의메뉴유용성이며,기존고정정답표의93%부분적중이나실제업무완료율을대체하지않는다. LLM은0~8개,다른두모델은3개추천으로출력개수도다르다. 원시정답표·실제응답·이전판정을보존했다.

## 오프라인 재현

`python experiments/model-answer-review/build.py`는기존실행결과에서원문·정답·실제답을다시추출한다. 별도API호출없음.

`python experiments/utility-review-100-v3/define_review.py`

`python experiments/utility-review-100-v3/score.py`

`python experiments/utility-review-100-v3/build_report.py`

v3의build_report.py는finalize_report.py를포함해사용자승인표현의HTML·보고서를생성한다. 각verification.log와freeze해시로입력·판정·응답이보존됐는지확인한다. 개인환경경로와브라우저fileURL은당시의참조이며GitHub에서는상대경로자료를연다.
