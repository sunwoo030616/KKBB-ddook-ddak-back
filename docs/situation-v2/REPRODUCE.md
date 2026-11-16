# Reproduction

From repository root, use Python 3, Java 17, the project's Maven wrapper and dependencies, and the existing E5 runtime/model described in `scripts/semantic/README.md`. Supply `JEV_AI_API_KEY` and `OPENAI_API_KEY` in the environment; do not put keys in commands/logs. Model files are not committed.

The measured inference implementation is commit `419911c` and its SHA256 hashes are in `scripts/semantic/situation_v2/evaluation-freeze.json`. The original frozen runner is retained unchanged; `run_safe.py` fixes only nullable console display for new runs. Existing output files are never overwritten. Actual provider calls incur usage and require authorization for the chosen data/scope.

```sh
python3 -m unittest discover -s scripts/semantic/situation_v2 -p test_metrics.py
python3 scripts/semantic/situation_v2/verify.py docs/situation-v2/regression/results.json
python3 scripts/semantic/situation_v2/verify.py docs/situation-v2/fresh/results.json
python3 scripts/semantic/situation_v2/report.py
```

For a new authorized run, replace the local E5 paths and choose a new output directory:

```sh
python3 scripts/semantic/situation_v2/run_safe.py --e5-python /path/to/e5-venv/bin/python --model-dir /path/to/e5-model --cases scripts/semantic/situation_v2/fresh-100.json --freeze scripts/semantic/situation_v2/evaluation-freeze.json --providers e5_jev llm_full_catalog --output /path/to/new-output/results.json
```

For the 300 regression cases, use `regression-300.json` and `--providers e5_jev`. The runner executes the full Java suite before external requests, compiles a temporary project copy, and starts local actual E5 and backend processes. Port 18500–18502 must be available. Changes to frozen inference inputs must be recorded as a new experiment and freeze, not represented as a rerun of these results.

Development source freezes refer to historical commits and were checked at their corresponding development stage. The current-source verifier is intended for the final regression/fresh evaluation freeze.
