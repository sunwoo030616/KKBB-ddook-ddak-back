# Local neural RAG ablation (dev)

Corpus `dc20def3b9a26c5e`; actual local MLX + cross-encoder execution.

| Variant | Answerable N | Recall@2 | Recall@4 | All evidence@4 | p50 ms incl plan |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 5 | 0.900 | 1.000 | 1.000 | 2.3 |
| rerank | 5 | 1.000 | 1.000 | 1.000 | 3207.3 |
| decompose | 5 | 0.900 | 1.000 | 1.000 | 1606.5 |
| decompose_rerank | 5 | 1.000 | 1.000 | 1.000 | 2468.8 |

## Generation pilot

| Variant | N | Answerability | Valid structure/citations | Complete gold evidence coverage |
| --- | ---: | ---: | ---: | ---: |
| baseline | 6 | 0.833 | 1.000 | 0.800 |
| decompose_rerank | 6 | 0.833 | 1.000 | 0.800 |

## Limits

- Small same-author hand-labeled dataset and 26 reviewed paraphrases, not independent financial benchmark
- Test generation subset declared before inference; retrieval evaluated on all test cases
- Citation validity and gold evidence coverage do not establish semantic entailment or financial advice accuracy
- Greedy local generation, constrained JSON decoding; no model training or new research-method claim
- Single run; no confidence intervals or cross-model generalization claim

Every question, plan, selected ID, raw synthetic generation and failure is retained in the JSON report.
