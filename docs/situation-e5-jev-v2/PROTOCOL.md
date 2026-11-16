# E5→JEV-only improvement, reference unchanged

User requested improving and rechecking E5/JEV only. No generative/OpenAI model is used. Original 100 approved cases/allowed sets remain unchanged, including known questionable reference gaps. No score is increased by relabeling cases. No goal→menu lookup table is inserted into inference. No deployment, remote publication or Figma page edits.

## Development

Saved actual Jev per-menu judgements were reused for 20 previously exposed cases (two per family), paying only one new set-choice call per case. Initial listwise selection over sets of1–3 produced15/20 partial hits and was rejected. A second generic version used actual-E5-vector MMR to shortlist10, functional-role metadata (connection/information/advice/calculation/execution/protection/product/general content) derived from menu text, and sets of3 when at least3 candidates exist. It produced19/20. These are development results on repeated cases, not independent accuracy. Both attempts and the first source snapshot are preserved.

## Frozen improved procedure

Preserve original-query E5 Top80. Add at most20 extra candidates via generic synonym-normalized E5 search and char-trigram/word BM25 evidence, with at most100 actual catalog entries overall. The synonym lexicon maps ordinary language terms (vehicle disposal/sale, home/property, proprietor/business), not situation IDs to menus. It was developed after earlier retrieval failures; this is explicitly development-informed.

Jev Noul judges every candidate, same policy/questions as original. Shortlist10 among p>=0.3 using fixed MMR lambda0.7 and real menu embedding cosines. Enumerate actual3-menu combinations: C(10,3)=120 options, plus none/unsure. Fewer than3 available candidates yields a smaller set. Jev makes one typed Choice for the whole set with original request, actual candidates and generic functional roles. It can explicitly abstain; choice confidence is recorded, not treated as a calibrated task-success probability or subjected to the old0.6 threshold. No scenarios or answer IDs appear in instructions.

Original control is unchanged raw-query E5 Top80→Jev Noul p>=0.7→top3 by probability/E5 tie order. Both variants have max3 output budget. Improved intentionally offers three complementary candidates when possible, so actual output count and allowed-menu precision must accompany partial hit. Do not call a hit-rate increase a universal quality improvement if extra errors increase.

## Final runs

1. Regression: improved version on the exposed original100, with original actual84% E5/JEV,83% hybrid and89% standalone LLM references retained. This is development regression, not blind superiority over LLM.
2. Fresh-expression comparison: 100 new expressions (same10 approved intent families×10), old and improved E5/JEV, alternating order. Expressions/labels and implementation are frozen before first final API request. These are fresh wording, not unseen intent families or independent human validation. No source/threshold/label change after final results begin.

Primary: user-requested partial hit (one allowed ID including approved optional outcomes). Also report allowed-menu precision, mandatory-outcome recall, clean partial hits, exact sets/status, number of recommendations, all-case latency/P95 and observed standard-rate API-cost estimates. Error/format failures remain in denominators. Do not combine the two datasets into an independent200-intent score.

Paid scope: development40 set-choice Jev calls, original regression up to200 Jev calls, fresh controls up to300 Jev calls, total nominal540; quota-only replacements at most4 attempts, original quota attempts excluded from comparison tokens as user requested and retained in audit. No OpenAI dependency/key/calls in final runner. Original requests and actual candidates are sent only to api.typesafe.ai/v1/systemone, never expected labels.

All timings include E5/local lexical retrieval, actual Jev judging, set construction/decision and local compute; startup/index/vector loading excluded. Conditions sequential within each question, order alternates. Rate $0.042/M Jev input, output free, source https://help.typesafe.ai/articles/5187202169-how-much-does-jev-cost ; estimates exclude E5 CPU/hosting/tax/account differences. Standard rate verified in prior experiment; this is not an invoice.
