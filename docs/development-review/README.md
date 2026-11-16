# 금융 메뉴 추천 개발·평가 정리

## 변경 범위

기반 API 개발은 상황별 복수 메뉴 추천과 범용 LLM 업무 분해→E5 검색→JEV 선택 경로를 포함한다. E5→JEV 개선판은 `scripts/semantic/situation_e5_jev_v2`의 독립 평가 도구이며 운영 기본 API에 자동 통합한 변경이 아니다.

개선판은 원문E5 Top80을 보존하고 정규화·어휘 검색으로 최대20개를 보완한다. JEV 개별 Noul≥0.30 후보에서 실제E5 벡터 MMR로 최대10개를 고른 뒤120개3종 조합 중 Choice 한 번으로 최종 선택한다. 최종 Choice confidence 하한은 없다.

## 실제 결과와 해석

기존100문항: 허용 메뉴 최소1개 포함93%, 최소2개66%, 평균0.753초, P950.931초,100문항 API비용추정$0.11344221. 새표현100문항도 부분적중93%였으나 기존10개상황의 표현 변형이다. 전체 업무 해결률93% 또는100개독립상황 일반화 검증이 아니다.

정답표를 사용자 승인으로 넓혀 재채점한 수치는 별도 후속 PR에서 보존하며 이 원시 실행과 고정 평가기준을 덮어쓰지 않는다. JEV단독 비교와 UMAP 실행재생도 별도 PR로 분리한다.

## 검증

- 오프라인 Maven: MenuRecommendationControllerTest, GeneralMenuRecommendationServiceTest, JevDecisionClientTest, MenuTaskPlannerTest, PlannedMenuSelectorTest, SemanticMenuRecommendationServiceTest 통과.
- `python -m unittest discover -s scripts/semantic/situation_e5_jev_v2 -p 'test_*.py' -v`:5개 통과.
- `python scripts/semantic/situation_e5_jev_v2/verify_report.py`:100문항 회귀/새표현 비교의 소스·정답해시, 후보·MMR·조합·실제응답·토큰 검산 통과. 실제메뉴384차원 벡터 캐시 필요, 새 API호출 없음.
- 이 게시 준비 과정에서 새 유료 API평가는 실행하지 않았다.

커밋 이력에는 이전300문항·개발실험·한도오류·중단 실행의 증거도 보존된다. 서로 다른 평가셋의 수치를 합치지 않는다. 원시 로그에는 평가용합성문항과 실제응답이 있으며 사용자실계좌정보는 없다. 인증키는 포함하지 않는다.
