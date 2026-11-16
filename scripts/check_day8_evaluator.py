"""Check that the Day 8 evaluator detects deliberate oracle mistakes.

All mutations are made to temporary copies; the frozen fixture is unchanged.
These five checks are evaluator controls, not additional engine unit tests.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/assessment/evidence/day8-evaluator-self-check.json")
    args = parser.parse_args()
    fixture_path = ROOT / "tests/fixtures/day8_adversarial.json"
    original = fixture_path.read_bytes()
    fixture = json.loads(original)
    outcomes = []
    with TemporaryDirectory(prefix="day8-evaluator-controls-") as tmp:
        directory = Path(tmp)

        def run(name: str, data: dict, case_id: str, expected_exit: int, extra_check=None) -> None:
            path = directory / f"{name}.json"
            report = directory / f"{name}-result.json"
            path.write_text(json.dumps(data, ensure_ascii=True), encoding="utf-8")
            process = subprocess.run(
                [sys.executable, str(ROOT / "scripts/evaluate_day8.py"),
                 "--fixture", str(path), "--case", case_id, "--output", str(report)],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30,
                env=dict(os.environ, PYTHONIOENCODING="utf-8"))
            result = json.loads(report.read_text(encoding="utf-8")) if report.exists() else None
            checked = extra_check(result) if extra_check else True
            outcomes.append({"control": name, "expected_exit": expected_exit,
                             "actual_exit": process.returncode, "detail_check": checked,
                             "passed": process.returncode == expected_exit and checked})

        run("clean_control", fixture, "V01", 0,
            lambda r: r["summary"]["case_matches"] == 1 and r["summary"]["parity"]["ordinary"]["consistent"] == 1)
        changed = deepcopy(fixture)
        changed["cases"][0]["expected"]["issues"] = [
            {"record_index": 1, "record_id": "named-order", "issue_type": "numerical_inconsistency", "severity": "warning"}]
        run("fabricated_expected_finding_is_rejected", changed, "V01", 1,
            lambda r: bool(r["results"][0]["runs"][0]["missing_events"]))
        changed = deepcopy(fixture)
        target = next(c for c in changed["cases"] if c["id"] == "D05")
        target["expected"]["issues"][0]["severity"] = "critical"
        target["expected"]["exit_code"] = 1
        run("wrong_severity_and_exit_are_rejected", changed, "D05", 1,
            lambda r: not r["results"][0]["runs"][0]["checks"]["exit_code"]
            and bool(r["results"][0]["runs"][0]["missing_events"])
            and bool(r["results"][0]["runs"][0]["unexpected_events"]))
        run("expected_input_rejection_is_accepted", fixture, "B03", 0,
            lambda r: r["results"][0]["runs"][0]["exit_code"] == 2)
        changed = deepcopy(fixture)
        changed["cases"].pop()
        run("invalid_fixture_count_is_setup_error", changed, "V01", 2)
    preserved = fixture_path.read_bytes() == original
    evidence = {"fixture_sha256": hashlib.sha256(original).hexdigest(),
                "frozen_fixture_preserved": preserved, "controls": outcomes,
                "passed": sum(item["passed"] for item in outcomes),
                "failed": sum(not item["passed"] for item in outcomes)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return int(not preserved or any(not item["passed"] for item in outcomes))


if __name__ == "__main__":
    raise SystemExit(main())
