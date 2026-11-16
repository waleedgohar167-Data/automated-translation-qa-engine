"""Run the frozen Day 8 challenge set through the actual CLI.

This is a mechanical contract evaluation, not a linguistic accuracy benchmark.
The fixture defines expectations; this runner never derives them from output.
Exit 0: all selected expectations and parity checks match.
Exit 1: evaluation completed with a mismatch. Exit 2: evaluation setup failed.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "tests/fixtures/day8_adversarial.json"
DEFAULT_OUTPUT = ROOT / "docs/assessment/evidence/day8-evaluation-results.json"
FIELDS = ("id", "source", "translation", "source_locale", "target_locale")
EVENT_FIELDS = ("record_index", "record_id", "issue_type", "severity")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def event_counts(issues: list[dict]) -> Counter:
    return Counter(tuple(issue[key] for key in EVENT_FIELDS) for issue in issues)


def describe_events(events: Counter) -> list[dict]:
    return [dict(zip(EVENT_FIELDS, key), count=count)
            for key, count in sorted(events.items())]


def input_bytes(case: dict, file_format: str) -> tuple[bytes, int | None]:
    spec = case["input"]
    if "text" in spec or "bytes_hex" in spec:
        if file_format != spec["format"]:
            raise ValueError(f"{case['id']}: raw input has a different format")
        data = bytes.fromhex(spec["bytes_hex"]) if "bytes_hex" in spec else spec["text"].encode("utf-8")
        return data, None
    if "generator" in spec:
        generator = spec["generator"]
        if generator["kind"] != "long_fields":
            raise ValueError("Unknown input generator")
        length = generator["length"]
        if not isinstance(length, int) or isinstance(length, bool) or not 1 <= length <= 1_000_000:
            raise ValueError("Evaluation generator length must be between 1 and 1000000")
        records = [{"id": generator["id"],
                    "source": generator["source_character"] * length,
                    "translation": generator["translation_character"] * length,
                    "source_locale": "en", "target_locale": "fr"}]
    else:
        records = spec["records"]
    if file_format == "json":
        return (json.dumps(records, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8"), len(records)
    # Only the explicitly designated, losslessly representable parity inputs
    # take this route. Missing/null/type-invalid cases remain JSON-only.
    for record in records:
        if not isinstance(record, dict) or any(key not in record for key in FIELDS):
            raise ValueError(f"{case['id']}: CSV parity requires all five fields")
        if any(not isinstance(record[key], str) for key in FIELDS):
            raise ValueError(f"{case['id']}: CSV parity requires string values")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n", extrasaction="raise")
    writer.writeheader()
    writer.writerows(records)
    return stream.getvalue().encode("utf-8"), len(records)


def execute(case: dict, file_format: str, directory: Path) -> dict:
    data, record_count = input_bytes(case, file_format)
    path = directory / f"{case['id']}.{file_format}"
    path.write_bytes(data)
    command = [sys.executable, "-m", "translation_qa", "check", str(path)]
    result = {"format": file_format, "input_bytes": len(data),
              "input_sha256": digest(data), "expected_records": record_count,
              "expected": case["expected"], "checks": {}, "actual_issues": []}
    environment = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        process = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True,
                                 text=True, encoding="utf-8", errors="replace", timeout=10)
    except subprocess.TimeoutExpired:
        result.update(exit_code=None, execution_error="timeout_after_10_seconds", matched=False)
        return result
    result.update(exit_code=process.returncode, stdout=process.stdout, stderr=process.stderr)
    expected = case["expected"]
    checks = result["checks"]
    checks["exit_code"] = process.returncode == expected["exit_code"]
    checks["no_traceback"] = "Traceback (most recent call last)" not in process.stderr
    payload = None
    try:
        payload = json.loads(process.stdout if process.stdout.strip() else process.stderr)
    except (ValueError, TypeError):
        pass
    checks["structured_output"] = isinstance(payload, dict)
    if not isinstance(payload, dict):
        result.update(actual_error_type=None, records_analyzed=None, matched=False)
        return result
    result["actual_error_type"] = payload.get("error")
    result["records_analyzed"] = payload.get("records_analyzed")
    if expected["error_type"] is not None:
        checks["expected_error"] = payload.get("error") == expected["error_type"]
        checks["error_channel"] = not process.stdout.strip() and bool(process.stderr.strip())
        checks["message_present"] = isinstance(payload.get("message"), str) and bool(payload["message"].strip())
    else:
        checks["no_error"] = payload.get("error") is None
        checks["clean_stderr"] = not process.stderr.strip()
        issues = payload.get("issues")
        valid_issues = isinstance(issues, list) and all(
            isinstance(issue, dict) and all(key in issue for key in EVENT_FIELDS)
            and isinstance(issue.get("description"), str) and bool(issue["description"].strip())
            and type(issue["record_index"]) is int and isinstance(issue["record_id"], str)
            and isinstance(issue["issue_type"], str)
            and issue["severity"] in {"critical", "warning", "informational"}
            for issue in issues)
        checks["issue_schema"] = valid_issues
        checks["record_count"] = payload.get("records_analyzed") == record_count
        checks["issue_count"] = valid_issues and payload.get("issue_count") == len(issues)
        if valid_issues:
            result["actual_issues"] = issues
            actual_counts = event_counts(issues)
        else:
            actual_counts = Counter()
        expected_counts = event_counts(expected["issues"])
        result["missing_events"] = describe_events(expected_counts - actual_counts)
        result["unexpected_events"] = describe_events(actual_counts - expected_counts)
        checks["exact_issue_multiset"] = valid_issues and actual_counts == expected_counts
    result["matched"] = all(checks.values())
    return result


def parity_signature(result: dict) -> dict:
    return {"exit_code": result.get("exit_code"), "error_type": result.get("actual_error_type"),
            "records_analyzed": result.get("records_analyzed"),
            "events": describe_events(event_counts(result["actual_issues"])),
            "execution_error": result.get("execution_error")}


def summarize(results: list[dict]) -> dict:
    groups = {}
    for group in ("valid", "defective", "boundary"):
        members = [result for result in results if result["group"] == group]
        groups[group] = {"cases": len(members), "matched": sum(r["matched"] for r in members)}
    # Count only the primary format, so a parity rerun cannot double-count a
    # translation scenario or inflate detection results.
    clean = [r["runs"][0] for r in results if r["group"] == "valid"]
    defective = [r["runs"][0] for r in results if r["group"] == "defective"]
    expected_events = sum(len(r["expected"]["issues"]) for r in defective)
    missing_events = sum(sum(event["count"] for event in r.get("missing_events", [])) for r in defective)
    unexpected_events = sum(sum(event["count"] for event in r.get("unexpected_events", [])) for r in defective)
    parity = {}
    for cohort in ("ordinary", "long_field_boundary"):
        members = [r for r in results if r["parity_cohort"] == cohort]
        parity[cohort] = {"cases": len(members), "consistent": sum(r["parity_match"] for r in members)}
    return {"cases": len(results), "case_matches": sum(r["matched"] for r in results),
            "case_mismatches": [r["id"] for r in results if not r["matched"]],
            "cli_executions": sum(len(r["runs"]) for r in results),
            "cli_expectation_matches": sum(run["matched"] for r in results for run in r["runs"]),
            "by_group": groups,
            "valid_cases_with_unexpected_findings": sum(bool(r["actual_issues"]) for r in clean),
            "valid_cases_with_execution_or_contract_error": sum(not r["matched"] for r in clean),
            "defective_expected_events": expected_events,
            "defective_matching_events": expected_events - missing_events,
            "defective_missing_events": missing_events,
            "defective_unexpected_events": unexpected_events,
            "parity": parity}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--case", action="append", dest="case_ids", help="Select case IDs; requires explicit --output")
    args = parser.parse_args()
    if args.case_ids and args.output is None:
        parser.error("--case requires --output so a partial run cannot replace the full evaluation")
    output = args.output or DEFAULT_OUTPUT
    try:
        if output.resolve() == args.fixture.resolve():
            raise ValueError("Evaluation output cannot overwrite its fixture")
        fixture_bytes = args.fixture.read_bytes()
        fixture = json.loads(fixture_bytes)
        cases = fixture["cases"]
        if fixture["schema_version"] != 1 or Counter(c["group"] for c in cases) != Counter(valid=12, defective=18, boundary=10):
            raise ValueError("Expected schema 1 with exactly 12 valid, 18 defective and 10 boundary cases")
        if len({c["id"] for c in cases}) != 40:
            raise ValueError("Case IDs must be unique")
        if args.case_ids:
            unknown = set(args.case_ids) - {c["id"] for c in cases}
            if unknown:
                raise ValueError(f"Unknown case IDs: {sorted(unknown)}")
            cases = [c for c in cases if c["id"] in args.case_ids]
        started = datetime.now(timezone.utc).isoformat()
        results = []
        with TemporaryDirectory(prefix="translation-qa-day8-") as temporary:
            for case in cases:
                runs = [execute(case, kind, Path(temporary)) for kind in case["formats"]]
                parity_match = None
                if case["parity_required"]:
                    parity_match = (len(runs) == 2 and
                                    all(r.get("execution_error") is None for r in runs) and
                                    parity_signature(runs[0]) == parity_signature(runs[1]))
                results.append({key: case[key] for key in
                                ("id", "group", "category", "title", "rationale", "classification", "parity_cohort")}
                               | {"runs": runs, "parity_match": parity_match,
                                  "matched": all(r["matched"] for r in runs) and parity_match is not False})
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
        summary = summarize(results)
        document = {"evaluation": "Day 8 mechanical contract challenge", "schema_version": 1,
                    "environment": {"python": platform.python_version(), "platform": platform.platform(),
                                    "runtime": sys.executable, "commit": commit.stdout.strip() or None,
                                    "started_at_utc": started, "finished_at_utc": datetime.now(timezone.utc).isoformat()},
                    "fixture_sha256": digest(fixture_bytes), "runner_sha256": digest(Path(__file__).read_bytes()),
                    "engine_files_sha256": {p.relative_to(ROOT).as_posix(): digest(p.read_bytes())
                                            for p in sorted((ROOT / "translation_qa").glob("*.py"))},
                    "command_template": "python -m translation_qa check <materialized-case.json-or-csv>",
                    "failure_threshold": "critical (engine default)",
                    "metric_scope": "Synthetic mechanical expectations only; no semantic accuracy or production-rate claim.",
                    "summary": summary, "results": results}
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(document, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=True, indent=2))
        print(f"Evidence saved to {output}")
        return int(bool(summary["case_mismatches"]))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Evaluation setup error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
