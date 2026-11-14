"""Aggregate findings into a structured report. Pure functions: no file or console I/O.

``build_report`` turns a validated dataset and its findings into one
JSON-serializable dictionary. ``render_text`` lays the same dictionary out for
reading in a terminal. Counts are rule findings, not a translation accuracy score.
"""

from collections import Counter
from datetime import datetime, timezone
import json
from typing import Any, Iterable

from . import __version__
from .models import Issue, LoadedDataset, Severity
from .validation import ALL_RULES


REPORT_VERSION = 1
# Most severe first: this order decides "highest severity" and the report layout.
SEVERITY_ORDER = (Severity.CRITICAL.value, Severity.WARNING.value, Severity.INFORMATIONAL.value)
_NOTE = "Counts are rule findings under the documented profiles, not a translation accuracy score."


def _highest(severities: Iterable[str]) -> str | None:
    return min(severities, key=SEVERITY_ORDER.index, default=None)


def _unique(values: Iterable[str]) -> list[str]:
    """Remove repeats while keeping first-seen order."""
    return list(dict.fromkeys(values))


def _percent(part: int, whole: int) -> float:
    return round(100 * part / whole, 1) if whole else 0.0


def build_report(dataset: LoadedDataset, issues: list[Issue],
                 generated_at: str | None = None) -> dict[str, Any]:
    """Summarize ``issues`` for ``dataset``.

    Findings are grouped three ways in a single pass: by input record, by
    category (issue type), and by severity. Records are keyed by their 1-based
    input index because identifiers can be missing or duplicated. Pass
    ``generated_at`` to obtain a reproducible report; it defaults to the
    current UTC time.
    """
    total_records = len(dataset.records)
    by_record: dict[int, list[Issue]] = {}
    by_category: dict[str, list[Issue]] = {}
    by_severity: dict[str, list[Issue]] = {severity: [] for severity in SEVERITY_ORDER}
    for issue in issues:
        by_record.setdefault(issue.record_index, []).append(issue)
        by_category.setdefault(issue.issue_type, []).append(issue)
        by_severity[issue.severity.value].append(issue)

    affected_records = [
        {
            "record_id": found[0].record_id,
            "record_index": index,
            "issue_count": len(found),
            "highest_severity": _highest(issue.severity.value for issue in found),
            "issue_types": _unique(issue.issue_type for issue in found),
        }
        for index, found in sorted(by_record.items())
    ]
    issues_by_severity = {
        severity: {"count": len(found), "record_ids": _unique(issue.record_id for issue in found)}
        for severity, found in by_severity.items()
    }
    # Largest category first; equal counts are ordered by name so output is stable.
    issues_by_category = {
        kind: {
            "count": len(found),
            "severity": _highest(issue.severity.value for issue in found),
            "record_ids": _unique(issue.record_id for issue in found),
        }
        for kind, found in sorted(by_category.items(), key=lambda pair: (-len(pair[1]), pair[0]))
    }
    worst = Counter(record["highest_severity"] for record in affected_records)
    records_by_highest_severity = {severity: worst[severity] for severity in SEVERITY_ORDER}
    records_by_highest_severity["none"] = total_records - len(affected_records)

    summary = {
        "total_records": total_records,
        "total_issues": len(issues),
        "records_with_issues": len(affected_records),
        "records_without_issues": total_records - len(affected_records),
        "records_with_issues_percent": _percent(len(affected_records), total_records),
        "average_issues_per_record": round(len(issues) / total_records, 2) if total_records else 0.0,
        "max_issues_on_one_record": max((record["issue_count"] for record in affected_records), default=0),
        "distinct_issue_types": len(by_category),
        "most_common_issue_type": next(iter(issues_by_category), None),
        "highest_severity": _highest(issue.severity.value for issue in issues),
        "records_by_highest_severity": records_by_highest_severity,
    }
    return {
        "report": "translation_qa_report",
        "report_version": REPORT_VERSION,
        "engine_version": __version__,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "input": {"file": dataset.filename, "format": dataset.input_format},
        "note": _NOTE,
        "summary": summary,
        "issues_by_severity": issues_by_severity,
        "issues_by_category": issues_by_category,
        "affected_record_ids": _unique(record["record_id"] for record in affected_records),
        "affected_records": affected_records,
        "rules": list(ALL_RULES),
        "issues": [issue.to_dict() for issue in issues],
    }


def _label(record_id: str) -> str:
    # JSON quoting keeps an identifier containing a newline or tab on one line.
    return json.dumps(record_id, ensure_ascii=False)


def render_text(report: dict[str, Any]) -> str:
    """Lay a report from ``build_report`` out as plain text for a terminal."""
    summary = report["summary"]
    lines = [
        "Translation QA report",
        f"Input:      {report['input']['file']} ({report['input']['format']})",
        f"Engine:     {report['engine_version']}",
        f"Generated:  {report['generated_at']}",
        "",
        "Summary",
        f"  Records analyzed:        {summary['total_records']}",
        f"  Records with issues:     {summary['records_with_issues']} ({summary['records_with_issues_percent']}%)",
        f"  Records without issues:  {summary['records_without_issues']}",
        f"  Total issues:            {summary['total_issues']}",
        f"  Average per record:      {summary['average_issues_per_record']}",
        f"  Highest severity:        {summary['highest_severity'] or 'none'}",
        "",
        "Issues by severity",
    ]
    lines += [f"  {severity:<15}{group['count']:>5}" for severity, group in report["issues_by_severity"].items()]

    lines += ["", "Issues by category"]
    categories = report["issues_by_category"]
    width = max(map(len, categories), default=0)
    lines += [f"  {kind:<{width}}{group['count']:>5}  {group['severity']}" for kind, group in categories.items()] or ["  none"]

    lines += ["", "Affected records"]
    lines += [
        f"  #{record['record_index']} {_label(record['record_id'])} [{record['highest_severity']}] "
        + ", ".join(record["issue_types"])
        for record in report["affected_records"]
    ] or ["  none"]
    lines += ["", report["note"]]
    return "\n".join(lines)
