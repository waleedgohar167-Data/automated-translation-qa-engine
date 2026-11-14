"""Command-line entry points; validation is added in the next checkpoint."""

import argparse
import json
import sys

from . import __version__
from .loading import InputError, load_dataset


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="translation-qa",
                                     description="Inspect translation input files.")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="Load a file and summarize its records.")
    inspect.add_argument("input", help="Input CSV or JSON file")
    inspect.add_argument("--format", choices=("auto", "csv", "json"), default="auto")
    args = parser.parse_args(argv)
    try:
        dataset = load_dataset(args.input, args.format)
    except InputError as exc:
        print(json.dumps({"error": "input_error", "message": str(exc)}, ensure_ascii=False),
              file=sys.stderr)
        return 2
    output = {
        "mode": "load_only",
        "input_file": dataset.filename,
        "input_format": dataset.input_format,
        "records_loaded": len(dataset.records),
        "object_records": sum(isinstance(row.data, dict) for row in dataset.records),
        "records_with_input_problems": sum(bool(row.input_problems) for row in dataset.records),
        "validation_performed": False,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0
