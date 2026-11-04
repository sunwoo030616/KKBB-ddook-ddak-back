# 로컬 생성 LLM을 이용한 금융 복합질문 RAG 실험

**보조 실험 기록:** 서비스 개발 중심은 [Generative UI v2](GENERATIVE_UI_README.md)입니다. 초기 `research-dev-v1`/`research-test-v1`은 프롬프트에 채팅 템플릿이 중복 적용된 문제가 발견되어 성능 주장에 사용하지 않습니다. 생성 경로는 수정했으며 해당 비교는 수정된 프로토콜로 재실행해야 합니다.

기존의 주제 선택형 `/finance/analyze`와 별개로, **자유로운 질문을 생성 LLM이 분해하고 cross-encoder가 문서를 재정렬한 뒤 같은 LLM이 근거를 선택해 답변을 생성**합니다. 유료 API를 호출하지 않습니다.

## 구성

- 생성/질문 분해: `mlx-community/Qwen3-1.7B-4bit`, Apple Silicon MLX 실행. 원본은 Qwen3-1.7B이며 community 4bit 변환본입니다.
- 재정렬: `BAAI/bge-reranker-v2-m3`, 다국어 cross-encoder, CPU 실행.
- 1차 검색: 기존 BM25 + 문자 TF-IDF 순위 결합. 이번 비교에서는 1차 검색기를 고정합니다.
- 구조화 생성: Outlines가 토큰 선택에 JSON 제약을 적용합니다. 생성한 evidence ID는 corpus의 ID 집합으로 제한합니다.
- 기존 서버 검증: 선택한 문맥 안에 ID가 존재하는지, 답변 숫자가 해당 문서에 있는지 검사합니다. `quote`는 모델이 생성하는 대신 서버가 해당 원문 청크 전체로 설정합니다. **이는 provenance이며 문장 의미의 함의를 검증하는 증명은 아닙니다.**
- 질문당 계획 1회, 하위 질문 최대 3개, 기관 최대 3곳, 후보 최대 20개, 최종 근거 최대 4개입니다. LLM이 기관·기준일을 바꾸거나 금융 거래를 실행할 권한은 없습니다.

질문 분해는 새로운 연구 방법을 발명한 것이 아닙니다. [Question Decomposition for Retrieval-Augmented Generation](https://arxiv.org/abs/2507.00355)의 질문 분해→후보 통합→재정렬 구성을 참고해 금융 데이터에서 재현·변형한 소규모 실험입니다.

## 준비

이 생성 모델 실행 경로는 Metal을 지원하는 **Apple Silicon Mac** 전용입니다. 이번 개발 환경은 arm64, 메모리 16 GiB입니다. 재정렬은 CPU를 사용했습니다.

```bash
python -m pip install -r requirements-research.txt
python -m rag_backend.prepare_research_models --download
```

공개 모델 파일 약 3.3 GB를 `var/research_models/`에 저장합니다. 다운로드 시 Hugging Face revision을 고정하고 파일별 SHA-256 manifest를 만듭니다. 이후 실행은 로컬 경로를 사용하며 `trust_remote_code=False`입니다. 모델 가중치는 Git에 추가하지 않습니다.

초기 Outlines grammar/tokenizer 준비가 느릴 수 있습니다. 같은 서버 프로세스에서는 생성기를 재사용합니다. greedy 생성, thinking 비활성, 최대 생성 토큰 수를 고정합니다. JSON 제약도 길이 제한으로 잘리거나 필드 간 의미가 모순되면 검증에서 실패할 수 있습니다.

## 실제 API

```bash
RAG_ENABLE_RESEARCH=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
python -m uvicorn rag_backend.app:create_app --factory --host 127.0.0.1 --port 8767
```

```bash
curl -X POST http://127.0.0.1:8767/research/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"예금을 깨는 것과 담보대출을 받는 것은 어떤 비용 차이가 있고 비교 전에 어떤 정보를 알아야 해?","institutions":["kb_bank"],"as_of":"2026-11-02","decompose":true,"rerank":true,"top_k":4}'
```

`institutions`와 `as_of`는 사용자가 명시한 서버 검색 범위입니다. 하위 질문에 다른 기관명이 생성되어도 이 범위를 넓히지 않습니다. 기존 계산 도구를 쓰려면 선택적으로 `calculation`을 구조화된 값으로 함께 넣을 수 있습니다. 모델이 금액·금리·세율을 추측해 도구에 넣지 않습니다.

- 모델·구조 검증을 통과하면 `answered`입니다.
- 출처가 없거나 모델이 답변을 유보하면 `not_found`입니다.
- JSON·근거 ID·수치 검증에 실패해도 `not_found`와 별도 사유를 반환합니다. 유보와 생성 실패를 trace/reason으로 구분합니다.
- 이 답변은 현재 상품 조건 보장·적합성 판단·실제 금융 거래가 아닙니다.
- 연구 모델을 켜지 않은 서버는 이 경로에 503을 반환합니다.

API의 trace에는 하위 질문·선택 근거 ID·단계 시간만 반환하며 원시 모델 출력은 넣지 않습니다. 감사 DB는 기존처럼 요청 ID/상태/사유/지연만 기록합니다. 오프라인 실험 보고서는 직접 작성한 합성 질문과 그 모델 출력을 별도로 보존합니다.

## 비교 실험

모델 실행 전에 `data/research_questions.json`에 dev 6개, test 16개를 작성했습니다. 정답 근거 ID는 평가 코드에서만 사용하며 모델 프롬프트에 넣지 않습니다.

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python -m rag_backend.evaluate_research --split dev
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python -m rag_backend.calibrate_research
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python -m rag_backend.evaluate_research --split test
```

| 조건 | 질문 분해 | 교차 인코더 재정렬 |
| --- | --- | --- |
| baseline | 없음 | 없음 |
| rerank | 없음 | 있음 |
| decompose | 있음 | 없음 |
| decompose_rerank | 있음 | 있음 |

기본 네 조건 외에 `neural_gate`를 비교합니다. dev 6개의 최고 관련도 점수와 답변 가능 라벨만으로 미리 정한 후보 임계값 중 하나를 선택했고 0.05가 선택되었습니다. 이 조건은 낮은 관련도 근거를 제외하고 근거가 남지 않으면 생성 모델을 호출하지 않습니다. 테스트에서 답변 가능한 질문을 과도하게 막았기 때문에 API 기본값은 **비활성**으로 정했습니다. `evidence_gate:true`로 별도 실험할 수 있습니다. 이 배포 기본값 선택은 테스트 결과를 본 뒤의 판단이며, 보고서의 비교 조건·임계값을 수정하지 않았습니다. 재정렬이 없으면 gate는 적용하지 않습니다.

관련도 점수는 금융 답변의 정답 확률이 아닙니다. dev에 음성 예시가 1개뿐이라 임계값의 일반화는 특히 불확실합니다. test 결과를 보고 임계값을 다시 선택하지 않습니다.

모든 test 질문에서 다섯 조건의 검색을 비교합니다. 생성 비용을 제한하기 위해 **결과를 보기 전에 정한 test 8개**에서 baseline·질문 분해+재정렬·추가 gate 조건의 생성도 비교합니다. 생성 대상은 `t01, t02, t04, t05, t06, t07, t09, t12`입니다. 모델 답변이 잘 나온 질문만 고르는 절차가 아닙니다.

측정 항목:

- Recall@2/4: 정답 근거 집합 중 검색된 비율. 답변 가능한 질문만 평균합니다.
- All evidence@4: 필요한 정답 근거가 모두 상위 4개에 있는 질문 비율.
- Answerability: 생성 파이프라인이 답변/유보를 정답 여부에 맞게 선택했는지.
- 구조·인용 유효성: 실제 생성 결과가 스키마·ID·숫자 검증을 통과했는지.
- 생성 근거 완전성: 답변 가능한 질문에서 모델이 모든 정답 근거를 인용했는지. 답변 전체의 의미 정확도와 다릅니다.
- 지연: 질문 분해를 쓴 조건은 분해 시간을 포함해 보고합니다. 생성 시간은 각 사례에 별도로 저장합니다.

보고서에는 dataset/corpus 스냅샷과 해시, 공개 모델 revision/가중치 해시, 패키지 버전, 실패한 원시 출력, 실제 선택 ID를 함께 기록합니다. 최초 dev 실행에서 인용 필드 누락/placeholder 복사가 발생한 결과도 `reports/research-dev-smoke.json`, `research-dev-constrained-smoke.json`에 남겼습니다.

**한계:** 26개 검수 요약과 같은 작성자가 만든 소규모 질문셋입니다. 원문 전체·독립 금융 벤치마크가 아니며 유사한 dev/test 주제가 있습니다. test를 본 뒤 설정을 바꿔 재실행한다면 해당 결과를 탐색적 결과로 표기해야 합니다. 한 번 실행한 결과만으로 일반화나 통계적 유의성을 주장하지 않습니다.

## 코드

- `rag_backend/research.py`: 자유 질문→생성 분해→검색 통합→재정렬→근거 선택/답변→서버 검증.
- `rag_backend/research_models.py`: 실제 MLX 생성 모델·CPU cross-encoder, 동시 실행 잠금.
- `rag_backend/evaluate_research.py`: 네 조건 비교, 사전에 정한 생성 평가, 체크포인트·실패 기록.
- `tests_rag/test_research.py`: 모의 모델을 이용한 범위 격리·잘못된 근거·생성 실패·API 계약 검증. 실제 신경망 성능 평가는 별도 실험 명령으로 수행합니다.

## 공식 자료

- [MLX LM](https://github.com/ml-explore/mlx-lm)
- [Qwen 원본 모델](https://huggingface.co/Qwen/Qwen3-1.7B) / [MLX 변환본](https://huggingface.co/mlx-community/Qwen3-1.7B-4bit)
- [BAAI reranker 모델 카드](https://huggingface.co/BAAI/bge-reranker-v2-m3)
- [Outlines MLX 구조화 생성](https://github.com/dottxt-ai/outlines/blob/main/docs/features/models/mlxlm.md)
