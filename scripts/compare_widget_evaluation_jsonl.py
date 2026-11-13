#!/usr/bin/env python3
"""Compare two exported widget evaluations by case ID without calling a provider."""
import argparse
import json
import math
import statistics
from pathlib import Path


def read_results(path):
    results = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError("expected an object")
            case_id = row.get("id")
            if not isinstance(case_id, str) or not case_id.strip() or type(row.get("pass")) is not bool:
                raise ValueError("expected a nonempty id and a boolean pass")
            if case_id in results:
                raise ValueError(f"duplicate ID: {case_id}")
            for key in ("missingWidgets", "extraWidgets"):
                values = row.get(key, [])
                if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
                    raise ValueError(f"{key} must be a list of strings")
            latency = row.get("latencyMs")
            if latency is not None and (type(latency) not in (int, float)
                                        or not math.isfinite(latency) or latency < 0):
                raise ValueError("invalid latencyMs")
        except ValueError as error:
            raise ValueError(f"{path}:{line_number}: {error}") from error
        results[case_id] = row
    if not results:
        raise ValueError(f"{path}: no evaluation results")
    return results


def counts(rows, ids):
    return {"passed": sum(rows[case_id]["pass"] for case_id in ids), "total": len(ids)}


def compare(before, after):
    shared = sorted(before.keys() & after.keys())
    added = sorted(after.keys() - before.keys())
    removed = sorted(before.keys() - after.keys())
    regressed, fixed, changed_failures = [], [], []
    latencies = []
    for case_id in shared:
        old, new = before[case_id], after[case_id]
        if old["pass"] and not new["pass"]:
            regressed.append(new)
        elif not old["pass"] and new["pass"]:
            fixed.append(case_id)
        elif not new["pass"]:
            fields = ("missingWidgets", "extraWidgets", "error", "needsReview")
            if any(old.get(field) != new.get(field) for field in fields):
                changed_failures.append({"before": old, "after": new})
        if (not old.get("error") and not new.get("error")
                and old.get("latencyMs") is not None and new.get("latencyMs") is not None):
            latencies.append((old["latencyMs"], new["latencyMs"]))
    return {
        "sharedBefore": counts(before, shared),
        "sharedAfter": counts(after, shared),
        "added": {"score": counts(after, added), "cases": added},
        "removed": removed,
        "regressed": regressed,
        "fixed": fixed,
        "changedFailures": changed_failures,
        "latency": {
            "pairedCases": len(latencies),
            "beforeMedianMs": statistics.median(pair[0] for pair in latencies) if latencies else None,
            "afterMedianMs": statistics.median(pair[1] for pair in latencies) if latencies else None,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    args = parser.parse_args()
    try:
        result = compare(read_results(args.before), read_results(args.after))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(bool(result["regressed"] or result["removed"]))


if __name__ == "__main__":
    raise SystemExit(main())
