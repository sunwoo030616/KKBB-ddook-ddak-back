# Local neural RAG ablation (test)

Corpus `dc20def3b9a26c5e`; actual local MLX + cross-encoder execution.

| Variant | Answerable N | Recall@2 | Recall@4 | All evidence@4 | p50 ms incl plan |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 12 | 0.806 | 0.958 | 0.917 | 1.2 |
| rerank | 12 | 0.931 | 1.000 | 1.000 | 1875.8 |
| decompose | 12 | 0.722 | 1.000 | 1.000 | 1489.5 |
| decompose_rerank | 12 | 0.931 | 1.000 | 1.000 | 2638.7 |
| neural_gate | 12 | 0.806 | 0.833 | 0.833 | 2482.9 |

## Generation pilot

| Variant | N | Answerability | Valid structure/citations | Complete gold evidence coverage |
| --- | ---: | ---: | ---: | ---: |
| baseline | 8 | 0.875 | 1.000 | 0.833 |
| decompose_rerank | 8 | 0.875 | 1.000 | 0.833 |
| neural_gate | 8 | 0.625 | 1.000 | 0.500 |

## Limits

- Small same-author hand-labeled dataset and 26 reviewed paraphrases, not independent financial benchmark
- Test generation subset declared before inference; retrieval evaluated on all test cases
- Citation validity and gold evidence coverage do not establish semantic entailment or financial advice accuracy
- Greedy local generation, constrained JSON decoding; no model training or new research-method claim
- Single run; no confidence intervals or cross-model generalization claim

Every question, plan, selected ID, raw synthetic generation and failure is retained in the JSON report.
