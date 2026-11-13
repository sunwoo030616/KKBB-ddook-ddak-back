#!/usr/bin/env python3
"""Export one provider's benchmark report as case-level JSONL without calling an API."""
import argparse
import json
from pathlib import Path


def rows(report, provider):
    if report.get("scope") != "widget_selection_only":
        raise ValueError("expected a widget_selection_only benchmark report")
    seen = set()
    for result in report["results"]:
        if result["provider"] != provider:
            continue
        case = result["caseId"]
        repeat = result["repeat"]
        if not isinstance(case, str) or not case or type(repeat) is not int or repeat < 0:
            raise ValueError("invalid case ID or repeat")
        key = (case, repeat)
        if key in seen:
            raise ValueError(f"duplicate result: {case}, repeat {repeat}")
        seen.add(key)

        success = result["success"]
        if type(success) is not bool:
            raise ValueError(f"invalid success value: {case}")
        row = {"id": case if repeat == 0 else f"{case}#repeat={repeat}", "pass": False}
        if success:
            expected = set(result["expected"])
            selected = set(result["widgets"])
            row.update({
                "pass": expected == selected,
                "missingWidgets": sorted(expected - selected),
                "extraWidgets": sorted(selected - expected),
                "needsReview": bool(result.get("needsReview")),
                "latencyMs": result.get("durationMs"),
            })
        else:
            row.update({"error": result.get("error", "request failed")})
        yield row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--provider", choices=("jev", "openai"), default="jev")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        results = list(rows(report, args.provider))
        if not results:
            raise ValueError(f"no results for provider {args.provider}")
        if len({row["id"] for row in results}) != len(results):
            raise ValueError("case IDs overlap with repeat suffixes")
        if args.report.resolve() == args.output.resolve():
            raise ValueError("output must differ from the source report")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in results),
            encoding="utf-8",
        )
    except (OSError, KeyError, TypeError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
