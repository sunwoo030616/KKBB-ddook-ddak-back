# Reproduction and continuation

Run from repository root with Python 3, Java 17, Maven dependencies, actual E5 runtime/model and existing API keys in the environment. Do not place keys in commands or logs. Inference source is frozen at commit 18d7f96 and scripts/semantic/situation_v3/freeze-evaluation.json. Original measurements are never silently overwritten.

Offline checks:

```sh
python3 -m unittest discover -s scripts/semantic/situation_v3 -p test_metrics.py
python3 scripts/semantic/situation_v3/verify.py docs/situation-v3/holdout/results.json
python3 scripts/semantic/situation_v3/report.py
```

The 300-case regression is incomplete because OpenAI credits are exhausted. `resume.py` skips saved rows and retains failures. `continue_after_quota.py` prepares a separate final-run directory that retains the 18 non-quota rows and schedules exactly the six quota failures plus 276 unattempted cases. Without `--execute` it makes no API calls. After funding, first preserve original quota rows, explicitly schedule those six cases for replacement as the user requested, then resume all unattempted cases. Account for successful replacements in final token totals and exclude original HTTP 429 attempts. The raw audit must retain both attempts and distinguish them. Do not mark the regression complete until exactly 300 final rows have been verified.

For a new authorized evaluation, use `run.py --e5-python /path/to/e5-venv/bin/python --model-dir /path/to/e5-model --cases scripts/semantic/situation_v3/holdout-100.json --freeze scripts/semantic/situation_v3/freeze-evaluation.json --providers hybrid --output /path/to/new-output/results.json`. It refuses to overwrite existing outputs, tests the backend first and uses actual provider APIs. Calls incur usage. The historical development freezes refer to earlier versions; current-source verification is for the final evaluation freeze.
