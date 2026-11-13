import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "compare_widget_evaluation_jsonl.py"
SPEC = importlib.util.spec_from_file_location("comparison", SCRIPT)
comparison = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(comparison)


class CompareWidgetEvaluationTest(unittest.TestCase):
    def test_same_score_still_exposes_a_regression_and_counts_new_cases_separately(self):
        old = {"a": {"pass": True, "latencyMs": 10}, "b": {"pass": False, "latencyMs": 20}}
        failed = {"id": "a", "pass": False, "missingWidgets": ["insurance"], "extraWidgets": ["qr"]}
        new = {"b": {"pass": True, "latencyMs": 15}, "a": failed, "c": {"pass": True}}
        result = comparison.compare(old, new)
        self.assertEqual(result["sharedBefore"], result["sharedAfter"])
        self.assertEqual(result["regressed"], [failed])
        self.assertEqual(result["fixed"], ["b"])
        self.assertEqual(result["added"]["score"], {"passed": 1, "total": 1})
        self.assertEqual(result["latency"], {"pairedCases": 1, "beforeMedianMs": 20, "afterMedianMs": 15})

    def test_missing_baseline_case_and_duplicate_ids_have_distinct_exit_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            before, after = (Path(directory) / name for name in ("before.jsonl", "after.jsonl"))
            before.write_text('{"id":"a","pass":true}\n', encoding="utf-8")
            after.write_text('{"id":"new","pass":true}\n', encoding="utf-8")
            command = [sys.executable, str(SCRIPT), str(before), str(after)]
            removed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(removed.returncode, 1)
            self.assertEqual(json.loads(removed.stdout)["removed"], ["a"])
            self.assertEqual(json.loads(removed.stdout)["sharedAfter"]["total"], 0)
            after.write_text(before.read_text() * 2, encoding="utf-8")
            duplicate = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(duplicate.returncode, 2)
            self.assertIn("duplicate ID", duplicate.stderr)


if __name__ == "__main__":
    unittest.main()
