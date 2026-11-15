# User-requested metric change during execution

After seeing low interim acceptable-set exact-match results, the user requested partial-hit scoring. This change is recorded as post-start metric selection; it is not presented as if it had been the original primary metric. No model, prompt, case, accepted set or required-outcome reference was changed. No new provider requests are necessary to recalculate this metric.

Partial hit: at least one returned ID appears in the union of preapproved acceptable sets (approved optional suggestions included). Model/format errors fail. An extra unauthorized menu does not erase a hit, so menu-level allowed precision, mean recommendation count, required-outcome recall and exact-match results are retained. A broad list of many menus can raise Hit rate while lowering precision; do not call a high partial-hit rate complete task accuracy.

Interim comparisons use only case IDs finished by both conditions. Final comparison must use exactly the same 100 cases per condition. First-1/2/3 response budgets are diagnostic only; pipeline output order is task order and is not guaranteed global relevance ranking.
