# OpenAI credit balance exhausted

Confirmed by actual API response: HTTP 429, code `credit_balance_exhausted`, type `insufficient_quota`, message `You have no credits remaining. Add credits to continue using the API at https://platform.openai.com/settings/organization/billing/.`

This is not a confirmed per-minute throughput problem. The initial interpretation was corrected after safely recording provider error details. Six quota failures remain in the 24 attempted regression rows. 276 cases have not been attempted. The separate 100-case holdout is complete and verified at 95/100.

The user authorized replacing quota-failed rows after re-execution and excluding quota-attempt tokens from comparison totals. Those calls returned no usage, which must be recorded as unknown, not estimated or invented as zero. The audit retains original attempts. Once credits are available, rerun only the six quota failures plus the 276 unattempted cases, preserving all other results and frozen inference code. This should yield exactly 300 final cases. Do not reclassify genuine accuracy/format failures as quota errors.

No billing action or automatic payment was taken. Results remain local.
