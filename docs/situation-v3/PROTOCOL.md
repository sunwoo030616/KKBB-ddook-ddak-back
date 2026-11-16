# General multi-menu experiment, v3

## Target and prohibited shortcuts

The target is >=90% exact set-and-status match for multi-request cases, with explicit multi and situational requests reported separately. Precision/recall and partial overlap cannot substitute for exact match. Failure cases, API errors and requests for clarification remain in denominators. No travel route, country trigger, fixed scenario-to-menu bundle, task whitelist, test-ID lookup, gold-label input, or result-based label rewriting is allowed.

Development uses previously exposed questions only. A new synthetic holdout is frozen before external execution and used once per frozen version. Report intent-family clustering and lack of independent human label review. Broad situations have inherently non-unique recommendations; distinguish that label uncertainty from actual incorrect actions. Do not claim a universal 90% or a production guarantee based on a synthetic test.

Keep the original menu catalog and E5 embeddings. Measure end-to-end time, each actual upstream call, and raw input/output/cache usage, including any additional planner. Do not report a hybrid planner as E5+JEV alone. Preserve v2 results unchanged. Keep results local; remote publication remains unapproved.

## Frozen holdout definition

The new 100-case primary set has 50 named explicit multi-outcome queries (2–5 menus) and 50 contextual multi-outcome queries (25 families × 2 phrasings). Contextual queries include the desired functional outcomes in natural language. They are not an evaluation of unconstrained, open-ended lifestyle advice. There are no single-target cases to inflate the overall multi-task score. There is no exact whitespace-normalized query overlap with the exposed previous 400 questions. Menu IDs/intent families can overlap. These are synthetic, catalog-authored labels, not independent human labels.

Broad goals such as “I want to travel” have multiple defensible recommendation sets. The unchanged original 300-case regression includes previously defined broad-situation labels and is reported separately; its old travel-bundle expectation is an evaluation label, not a rule in the new planner. Do not claim that >=90% on contextual outcomes solves every open-ended situation. Report the scenario regression score even if it is worse.

Architecture: a generative planner receives user text and a compact 585-menu capability index (names and purposes, no menu IDs). It returns independent search queries and verbatim evidence, not final menu identifiers. Actual E5 retrieves 20 candidates per task; JEV chooses independently. Only unresolved tasks expand to 40. Missing/collapsed outcomes force partial/clarification. Up to eight tasks are supported; overflow is rejected without truncation. The original /api/menus/recommend retains the previous version for comparison; the new experimental endpoint is /api/menus/recommend-general. Never describe the new endpoint as pure E5→JEV.

The user explicitly allowed adding an auxiliary LLM. Provider sends for development/evaluation will be audited separately from the previous approval budget. No calls are made by tests. Proposed maximum for this experiment is 40 development requests + 300 regression + 100 holdout = 440 OpenAI planner calls and up to 880 JEV calls. Data is the redacted request plus the compact capability index to OpenAI; the redacted request, task plan and actual E5 candidates go to JEV. No gold labels are sent to either provider.

## Development revisions

The first completed 12-case development run used gpt-4o-mini-2024-07-18 and matched 5/12 (one invalid-evidence error). Failures included merging separate outcomes, choosing broad management/help menus, and copying evidence from the capability index. This is a development result, not final validation. The planner was changed to pinned gpt-4.1-2025-04-14, with generic per-outcome completeness and exact evidence checks reinforced. No situation-specific rule or country/menu bundle was added. The held-out question/label files remain unchanged after the preflight correction.

The strong planner's development run exposed that previous labels sometimes enforce a single interpretation of ambiguous wording (e.g. ATM withdrawal help vs execution, broad travel alternatives, generic transaction history). Those existing labels are preserved, with disagreements disclosed rather than silently rewritten. A generic instruction now prevents narrowing an unspecified target to a particular facility/product/payment method. No test-specific mapping is added. The main /api/menus/recommend endpoint is now wired to the general pipeline too; the previous implementation remains as a historical comparator and shared response records, not the active controller path.
