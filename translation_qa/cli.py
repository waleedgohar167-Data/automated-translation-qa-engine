"""CLI for input inspection and deterministic core validation."""

import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .loading import InputError, load_dataset
from .validation import CORE_RULES, validate_dataset


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="translation-qa",
                                     description="Inspect and validate translation input files.")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="Load a file and summarize its records.")
    inspect.add_argument("input", help="Input CSV or JSON file")
    inspect.add_argument("--format", choices=("auto", "csv", "json"), default="auto")
    check = commands.add_parser("check", help="Run core validation and emit structured issues.")
    check.add_argument("input", help="Input CSV or JSON file")
    check.add_argument("--format", choices=("auto", "csv", "json"), default="auto")
    check.add_argument("--output", type=Path, help="Also save the JSON result to this file")
    check.add_argument("--fail-on", choices=("critical", "warning", "informational", "none"),
                       default="critical", help="Exit 1 for issues at or above this severity (default: critical)")
    args = parser.parse_args(argv)
    try:
        dataset = load_dataset(args.input, args.format)
    except InputError as exc:
        print(json.dumps({"error": "input_error", "message": str(exc)}, ensure_ascii=False),
              file=sys.stderr)
        return 2
    if args.command == "inspect":
        output = {
            "mode": "load_only",
            "input_file": dataset.filename,
            "input_format": dataset.input_format,
            "records_loaded": len(dataset.records),
            "object_records": sum(isinstance(row.data, dict) for row in dataset.records),
            "records_with_input_problems": sum(bool(row.input_problems) for row in dataset.records),
            "validation_performed": False,
        }
        print(json.dumps(output, ensure_ascii=True, indent=2))
        return 0
    issues = validate_dataset(dataset)
    output = {
        "mode": "core_validation",
        "engine_version": __version__,
        "input_file": dataset.filename,
        "input_format": dataset.input_format,
        "records_analyzed": len(dataset.records),
        "rules": list(CORE_RULES),
        "issue_count": len(issues),
        "issues": [issue.to_dict() for issue in issues],
    }
    if args.output is not None:
        try:
            if args.output.resolve() == Path(args.input).resolve():
                raise ValueError("Output must not overwrite the input file.")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except (OSError, ValueError) as exc:
            print(json.dumps({"error": "output_error", "message": str(exc)}), file=sys.stderr)
            return 2
    print(json.dumps(output, ensure_ascii=True, indent=2))
    ranks = {"informational": 1, "warning": 2, "critical": 3, "none": 4}
    return int(any(ranks[issue.severity.value] >= ranks[args.fail_on] for issue in issues))
