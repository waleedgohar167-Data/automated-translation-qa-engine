"""Reproduce Day 8 Block 1 audit observations without changing the engine.

Run from the repository root. All input/report writes use temporary files.
Two probes deliberately inject failures and label that fact in their results.
This is an audit probe script, not the Block 2 evaluation dataset or test suite.
"""

import argparse
from contextlib import redirect_stderr, redirect_stdout
import csv
from datetime import datetime, timezone
import errno
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from translation_qa import __version__, duplicates, validation
from translation_qa.cli import main as cli_main
from translation_qa.loading import load_dataset
from translation_qa.markup import scan_markup
from translation_qa.models import InputRecord, LoadedDataset
from translation_qa.reporting import build_report


def dataset(rows):
    return LoadedDataset(tuple(InputRecord(i, row) for i, row in enumerate(rows, 1)),
                         "json", "audit.json")


def cli(*args):
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = cli_main([str(arg) for arg in args])
    return code, stdout.getvalue(), stderr.getvalue()


def checks():
    result = {}
    # Positive control: reporting still agrees with the existing issue fixture.
    control = load_dataset(ROOT / "samples/block3_examples.json")
    found = validation.validate_dataset(control)
    report = build_report(control, found, generated_at="audit-fixed-time")
    result["report_control"] = {
        "records": report["summary"]["total_records"],
        "issues": len(found),
        "category_sum": sum(group["count"] for group in report["issues_by_category"].values()),
        "severity_sum": sum(group["count"] for group in report["issues_by_severity"].values()),
        "record_severity_sum": sum(report["summary"]["records_by_highest_severity"].values()),
        "same_findings_as_validation": report["issues"] == [item.to_dict() for item in found],
    }

    # A01: the single-record guard does not protect the cross-record phase.
    rows = [{"id": "bad", "source": "audit-trigger", "translation": "Bonjour", "target_locale": "fr"},
            {"id": "later", "source": "Save", "translation": ""}]
    data = dataset(rows)
    real_scan = scan_markup

    def interrupted_scan(text):
        if text == "audit-trigger":
            raise RuntimeError("audit-injected parser failure")
        return real_scan(text)

    isolation = {"fault_injected": True,
                 "normal_control_types": [i.issue_type for i in validation.validate_dataset(data)],
                 "expected": "An affected-record diagnostic and later findings remain available; no exception escapes."}
    with patch.object(validation, "scan_markup", interrupted_scan), patch.object(duplicates, "scan_markup", interrupted_scan):
        isolation["single_record_guard_types"] = [i.issue_type for i in validation._validate_isolated(data.records[0])]
        try:
            isolation["returned_types"] = [i.issue_type for i in validation.validate_dataset(data)]
            isolation["exception_escaped"] = None
        except Exception as exc:
            isolation["returned_types"] = None
            isolation["exception_escaped"] = type(exc).__name__
    result["A01_cross_record_isolation"] = isolation

    with tempfile.TemporaryDirectory(prefix="translation-qa-audit-") as directory:
        root = Path(directory)
        source = root / "input.json"
        source.write_text(json.dumps([{"id": "one", "source": "Hello", "translation": "Bonjour"}]), encoding="utf-8")
        original_input = source.read_bytes()
        output = root / "existing-report.json"
        old_report = '{"previous_report": "preserve until replacement succeeds"}\n'
        output.write_text(old_report, encoding="utf-8")
        real_write = Path.write_text

        # A02: simulate a write that writes a prefix then reports ENOSPC.
        def partial_write(path, text, *args, **kwargs):
            if path == output:
                real_write(path, text[:24], *args, **kwargs)
                raise OSError(errno.ENOSPC, "audit-injected partial write")
            return real_write(path, text, *args, **kwargs)

        with patch.object(Path, "write_text", partial_write):
            code, stdout, stderr = cli("report", source, "--output", output)
        remaining = output.read_text(encoding="utf-8")
        try:
            json.loads(remaining)
            valid_json = True
        except json.JSONDecodeError:
            valid_json = False
        result["A02_interrupted_report_write"] = {
            "fault_injected": True,
            "expected": "A failed replacement leaves the previous complete report available.",
            "exit_code": code, "error": json.loads(stderr),
            "stdout_empty": stdout == "", "input_unchanged": source.read_bytes() == original_input,
            "previous_report_preserved": remaining == old_report,
            "remaining_report_is_valid_json": valid_json, "remaining_characters": len(remaining),
        }

        # A03: compare equivalent records just above the active CSV field limit.
        limit = csv.field_size_limit()
        long_rows = [{"id": "long", "source": "A" * (limit + 1), "translation": "B" * (limit + 1)}]
        long_json = root / "long.json"
        long_csv = root / "long.csv"
        long_json.write_text(json.dumps(long_rows), encoding="utf-8")
        with long_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["id", "source", "translation"])
            writer.writeheader()
            writer.writerows(long_rows)
        formats = {}
        for name, path in (("json", long_json), ("csv", long_csv)):
            code, stdout, stderr = cli("check", path)
            formats[name] = {"exit_code": code, "result": json.loads(stdout or stderr)}
        result["A03_csv_json_size_boundary"] = {
            "fault_injected": False, "csv_field_limit_characters": limit,
            "field_length_characters": limit + 1,
            "equivalent_logical_records": True, "formats": formats,
        }

    # A04: measured structure growth, not a wall-time or production load benchmark.
    growth = []
    for depth in (100, 200, 400):
        scan = scan_markup("<b>" * depth + "Hello" + "</b>" * depth)
        growth.append({"depth": depth, "stored_tag_paths": len(scan.paths),
                       "total_stored_path_elements": sum(len(path) for path in scan.paths),
                       "markup_errors": len(scan.errors)})
    result["A04_nesting_resource_growth"] = {
        "fault_injected": False, "observations": growth,
        "note": "Bounded structural probe. No exhaustion or real workload throughput was tested.",
    }

    # A05: distinguish unsupported or context-dependent behavior from contract defects.
    scope_examples = [
        ("unsupported_percent_at", {"id": "unsupported", "source": "Hello %@", "translation": "Bonjour"}),
        ("documented_offset_sign_tradeoff", {"id": "offset", "source": "UTC-5", "translation": "UTC+5"}),
    ]
    scope = {}
    for name, row in scope_examples:
        scope[name] = {"input": row, "issue_types": [i.issue_type for i in validation.validate_dataset(dataset([row]))]}
    reuse = [{"id": "a", "source": "Open file", "translation": "Bonjour"},
             {"id": "b", "source": "Close file", "translation": "Bonjour"}]
    scope["reuse_without_locale"] = [i.issue_type for i in validation.validate_dataset(dataset(reuse))]
    scope["reuse_with_declared_target_locale"] = [i.issue_type for i in validation.validate_dataset(
        dataset([{**row, "target_locale": "fr"} for row in reuse]))]
    result["A05_documented_profile_limits"] = scope

    # A06: repository configuration evidence, not a claim about unseen remote runs.
    workflows = subprocess.run(["git", "ls-tree", "-r", "--name-only", "HEAD", ".github/workflows"],
                               cwd=ROOT, text=True, capture_output=True, check=True)
    result["A06_ci_evidence_gap"] = {"tracked_workflow_paths": workflows.stdout.splitlines(),
                                    "runtime_verified_in_this_audit": platform.python_version(),
                                    "python_3_11_run_in_this_audit": False,
                                    "python_3_13_run_in_this_audit": False,
                                    "remote_ci_checked": False}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    evidence = {"audit": "Day 8 Block 1", "executed_commit": commit,
                "engine_version": __version__, "python": platform.python_version(),
                "platform": platform.platform(), "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
                "note": "Observations only. The engine and test suite are unchanged. Injection is labeled per probe.",
                "observations": checks()}
    text = json.dumps(evidence, ensure_ascii=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
