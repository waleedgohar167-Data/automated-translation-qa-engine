"""CLI for input inspection, deterministic translation validation, and reporting."""

import argparse
import json
from pathlib import Path
import sys

from . import __version__
from .loading import InputError, load_dataset
from .models import Issue, LoadedDataset
from .reporting import build_report, render_text
from .validation import ALL_RULES, validate_dataset


# "none" ranks above every severity, so no finding can reach it.
_FAIL_RANKS = {"informational": 1, "warning": 2, "critical": 3, "none": 4}


class OutputError(Exception):
    """The report destination is unsafe or cannot be written."""


def _print_error(kind: str, message: str) -> None:
    # ASCII-only JSON stays parseable whatever encoding stderr has, for example
    # a redirected Windows stream using cp1252 (bug B5-005).
    print(json.dumps({"error": kind, "message": message}, ensure_ascii=True), file=sys.stderr)


def _aliases_input(output: Path, input_path: Path) -> bool:
    """Return True when writing ``output`` would replace the input file.

    Comparing resolved paths catches spelling aliases and symbolic links.
    ``samefile`` compares the identity of the underlying file, which also
    catches a hard link: a second name that resolves to a different path but
    shares the same data (bug B4-001).
    """
    if output.resolve() == input_path.resolve():
        return True
    try:
        return output.samefile(input_path)
    except FileNotFoundError:
        return False  # A destination that does not exist yet cannot be an alias.


def write_report(output: Path, input_path: Path, text: str) -> None:
    """Save ``text`` as UTF-8 without ever overwriting the input file."""
    try:
        if _aliases_input(output, input_path):
            raise OutputError("Output must not overwrite the input file.")
        output.parent.mkdir(parents=True, exist_ok=True)
        # A lone surrogate (for example a truncated "\ud83d" escape in the input)
        # cannot be encoded as UTF-8. backslashreplace writes it back as the JSON
        # escape \udXXX, so the saved report stays valid JSON (bug B5-004).
        output.write_text(text, encoding="utf-8", errors="backslashreplace", newline="\n")
    except (OSError, ValueError, RuntimeError) as exc:
        raise OutputError(str(exc)) from exc


def exit_code(issues: list[Issue], fail_on: str) -> int:
    """Return 1 when any finding is at or above the chosen threshold, otherwise 0."""
    return int(any(_FAIL_RANKS[issue.severity.value] >= _FAIL_RANKS[fail_on] for issue in issues))


def _print_console(text: str) -> None:
    """Print text that may hold any character without crashing a legacy console.

    stdout raises on characters its encoding cannot represent, such as cp1252
    on Windows. Those characters are shown as backslash escapes instead.
    """
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    print(text.encode(encoding, errors="backslashreplace").decode(encoding))


def _add_run_arguments(command: argparse.ArgumentParser, output_help: str) -> None:
    """Arguments shared by every command that runs validation."""
    command.add_argument("input", help="Input CSV or JSON file")
    command.add_argument("--format", choices=("auto", "csv", "json"), default="auto")
    command.add_argument("--output", type=Path, help=output_help)
    command.add_argument("--fail-on", choices=("critical", "warning", "informational", "none"),
                         default="critical", help="Exit 1 for issues at or above this severity (default: critical)")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="translation-qa",
                                     description="Inspect and validate translation input files.")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="Load a file and summarize its records.")
    inspect.add_argument("input", help="Input CSV or JSON file")
    inspect.add_argument("--format", choices=("auto", "csv", "json"), default="auto")
    check = commands.add_parser("check", help="Run translation validation and emit structured issues.")
    _add_run_arguments(check, "Also save the JSON result to this file")
    report = commands.add_parser("report", help="Run validation and emit an aggregated report.")
    _add_run_arguments(report, "Also save the report to this file")
    report.add_argument("--report-format", choices=("json", "text"), default="json",
                        help="Report layout: structured JSON or a plain-text summary (default: json)")
    return parser


def _inspect(dataset: LoadedDataset) -> int:
    summary = {
        "mode": "load_only",
        "input_file": dataset.filename,
        "input_format": dataset.input_format,
        "records_loaded": len(dataset.records),
        "object_records": sum(isinstance(row.data, dict) for row in dataset.records),
        "records_with_input_problems": sum(bool(row.input_problems) for row in dataset.records),
        "validation_performed": False,
    }
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    return 0


def _check(dataset: LoadedDataset, args: argparse.Namespace) -> int:
    issues = validate_dataset(dataset)
    result = {
        "mode": "translation_validation",
        "engine_version": __version__,
        "input_file": dataset.filename,
        "input_format": dataset.input_format,
        "records_analyzed": len(dataset.records),
        "rules": list(ALL_RULES),
        "issue_count": len(issues),
        "issues": [issue.to_dict() for issue in issues],
    }
    if args.output is not None:
        # Save first: if the destination is unsafe, nothing is printed and the exit is 2.
        write_report(args.output, Path(args.input), json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return exit_code(issues, args.fail_on)


def _report(dataset: LoadedDataset, args: argparse.Namespace) -> int:
    issues = validate_dataset(dataset)
    report = build_report(dataset, issues)
    if args.report_format == "text":
        saved = printed = render_text(report)
    else:
        saved = json.dumps(report, ensure_ascii=False, indent=2)
        printed = json.dumps(report, ensure_ascii=True, indent=2)
    if args.output is not None:
        write_report(args.output, Path(args.input), saved + "\n")
    _print_console(printed)
    return exit_code(issues, args.fail_on)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        dataset = load_dataset(args.input, args.format)
        if args.command == "inspect":
            return _inspect(dataset)
        if args.command == "report":
            return _report(dataset, args)
        return _check(dataset, args)
    except InputError as exc:
        _print_error("input_error", str(exc))
    except OutputError as exc:
        _print_error("output_error", str(exc))
    return 2
