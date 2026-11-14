"""Load CSV/JSON without making translation-quality judgments."""

import csv
import json
from pathlib import Path
from typing import Any

from .models import InputRecord, LoadedDataset


class InputError(ValueError):
    """The input file cannot be read or interpreted as a record collection."""


def _reject_nonfinite(value: str) -> None:
    raise InputError(f"JSON contains a non-standard numeric value: {value}")


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f"Duplicate JSON object field: {key!r}")
        result[key] = value
    return result


def _json_records(handle: Any) -> tuple[InputRecord, ...]:
    payload = json.load(handle, parse_constant=_reject_nonfinite,
                        object_pairs_hook=_unique_json_object)
    if isinstance(payload, dict):
        payload = payload.get("records")
    if not isinstance(payload, list):
        raise InputError("JSON must be a list of records or an object with a 'records' list.")
    return tuple(InputRecord(index=i, data=row) for i, row in enumerate(payload, start=1))


def _csv_records(handle: Any) -> tuple[InputRecord, ...]:
    reader = csv.DictReader(handle, strict=True)
    headers = reader.fieldnames
    if not headers:
        raise InputError("CSV must contain a header row.")
    if any(not header.strip() for header in headers):
        raise InputError("CSV header names must not be empty.")
    if len(set(headers)) != len(headers):
        raise InputError("CSV header names must be unique.")
    records = []
    for index, row in enumerate(reader, start=1):
        problems = []
        extra = row.pop(None, None)
        if extra is not None:
            problems.append(f"CSV row has {len(extra)} extra cell(s).")
        if any(value is None for value in row.values()):
            problems.append("CSV row has fewer cells than the header.")
        records.append(InputRecord(index=index, data=row, input_problems=tuple(problems)))
    return tuple(records)


def load_dataset(path: str | Path, input_format: str = "auto") -> LoadedDataset:
    source = Path(path)
    kind = source.suffix.lower().lstrip(".") if input_format == "auto" else input_format
    if kind not in {"csv", "json"}:
        raise InputError("Use a .csv or .json file, or specify --format csv/json.")
    try:
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            records = _csv_records(handle) if kind == "csv" else _json_records(handle)
    except (OSError, UnicodeError, csv.Error, json.JSONDecodeError, RecursionError) as exc:
        raise InputError(f"Cannot load {source.name}: {exc}") from exc
    return LoadedDataset(records=records, input_format=kind, filename=source.name)
