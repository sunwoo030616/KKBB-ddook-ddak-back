# Console failure and continuation

The initial evaluation saved 181 responses (JEV 91, GPT 90) before console formatting attempted `:.2f` on the undefined precision/recall of a negative example. The API response and usage had already been saved. This was a local reporting failure, not a provider failure.

`resume.py` executes the original frozen runner with only continuation/display adjustments: load existing rows and call audit, skip every saved case/provider pair, retain the original start time, append startup logs, and print nullable metrics without numeric formatting. The frozen source, prompts, thresholds, catalog, labels, provider order, and scoring are unchanged. A first continuation stopped at a case identifier lookup before any additional API call; the lookup was corrected from `id` to `case_id`. Both local failures remain in logs.

The second continuation requests only the remaining 19 responses. There are no repeated saved requests and no model/API retries. Verification checks the original expected case/provider order, full result counts, usage, and unchanged frozen inference inputs. Startup/test setup runs again; setup time remains excluded from request latency. The interruption and restarted local process can affect latency/cache conditions and prevent interpreting timing differences as a controlled causal result.
