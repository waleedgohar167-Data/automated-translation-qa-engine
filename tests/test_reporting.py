"""Reporting engine tests: aggregation, text layout, and the report command."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from translation_qa.cli import main
from translation_qa.loading import load_dataset
from translation_qa.models import InputRecord, LoadedDataset
from translation_qa.reporting import SEVERITY_ORDER, build_report, render_text
from translation_qa.validation import ALL_RULES, validate_dataset


ROOT = Path(__file__).resolve().parents[1]
FIXED_TIME = "2026-11-14T00:00:00Z"


def report_for_rows(rows):
    dataset = LoadedDataset(tuple(InputRecord(i, row) for i, row in enumerate(rows, start=1)),
                            "json", "memory.json")
    return build_report(dataset, validate_dataset(dataset), generated_at=FIXED_TIME)


def report_for_file(relative_path):
    dataset = load_dataset(ROOT / relative_path)
    return build_report(dataset, validate_dataset(dataset), generated_at=FIXED_TIME)


class ReportAggregationTests(unittest.TestCase):
    def test_sample_csv_totals_severities_and_affected_records(self):
        report = report_for_file("samples/translations.csv")
        summary = report["summary"]
        self.assertEqual((summary["total_records"], summary["total_issues"]), (6, 4))
        self.assertEqual((summary["records_with_issues"], summary["records_without_issues"]), (4, 2))
        self.assertEqual(summary["records_with_issues_percent"], 66.7)
        self.assertEqual(summary["average_issues_per_record"], 0.67)
        self.assertEqual(summary["highest_severity"], "critical")
        self.assertEqual(report["issues_by_severity"], {
            "critical": {"count": 2, "record_ids": ["sample-003", "sample-004"]},
            "warning": {"count": 2, "record_ids": ["sample-005", "sample-006"]},
            "informational": {"count": 0, "record_ids": []},
        })
        self.assertEqual(report["affected_record_ids"],
                         ["sample-003", "sample-004", "sample-005", "sample-006"])
        self.assertEqual(report["input"], {"file": "translations.csv", "format": "csv"})

    def test_category_and_severity_counts_both_add_up_to_the_total(self):
        report = report_for_file("samples/block3_examples.json")
        total = report["summary"]["total_issues"]
        self.assertEqual((report["summary"]["total_records"], total), (17, 15))
        self.assertEqual(sum(group["count"] for group in report["issues_by_category"].values()), total)
        self.assertEqual(sum(group["count"] for group in report["issues_by_severity"].values()), total)
        self.assertEqual([report["issues_by_severity"][s]["count"] for s in SEVERITY_ORDER], [10, 3, 2])
        self.assertEqual(report["summary"]["distinct_issue_types"], 11)
        self.assertEqual(len(report["issues"]), total)

    def test_every_severity_is_listed_even_when_its_count_is_zero(self):
        report = report_for_rows([{"id": "a", "source": "Hello", "translation": "Bonjour"}])
        self.assertEqual(list(report["issues_by_severity"]), ["critical", "warning", "informational"])
        self.assertTrue(all(group == {"count": 0, "record_ids": []}
                            for group in report["issues_by_severity"].values()))

    def test_clean_dataset_reports_no_issues(self):
        report = report_for_file("samples/block3_valid.json")
        summary = report["summary"]
        self.assertEqual((summary["total_records"], summary["total_issues"]), (6, 0))
        self.assertEqual(summary["records_with_issues_percent"], 0.0)
        self.assertIsNone(summary["highest_severity"])
        self.assertIsNone(summary["most_common_issue_type"])
        self.assertEqual((report["issues_by_category"], report["affected_records"],
                          report["affected_record_ids"], report["issues"]), ({}, [], [], []))

    def test_empty_dataset_has_zero_statistics_without_dividing_by_zero(self):
        summary = report_for_rows([])["summary"]
        self.assertEqual(summary["total_records"], 0)
        self.assertEqual(summary["records_with_issues_percent"], 0.0)
        self.assertEqual(summary["average_issues_per_record"], 0.0)
        self.assertEqual(summary["max_issues_on_one_record"], 0)
        self.assertEqual(summary["records_by_highest_severity"],
                         {"critical": 0, "warning": 0, "informational": 0, "none": 0})

    def test_categories_are_ordered_by_count_then_name(self):
        report = report_for_rows([
            {"id": "c", "source": "Settings", "translation": "Settings"},
            {"id": "a", "source": "Open", "translation": ""},
            {"id": "b", "source": "Close", "translation": " "},
        ])
        self.assertEqual(report["issues_by_category"], {
            "empty_translation": {"count": 2, "severity": "critical", "record_ids": ["a", "b"]},
            "source_copied": {"count": 1, "severity": "warning", "record_ids": ["c"]},
        })
        self.assertEqual(list(report["issues_by_category"]), ["empty_translation", "source_copied"])
        self.assertEqual(report["summary"]["most_common_issue_type"], "empty_translation")
        tied = report_for_file("samples/translations.csv")["issues_by_category"]
        self.assertEqual(list(tied), sorted(tied))

    def test_each_record_is_counted_once_under_its_worst_severity(self):
        report = report_for_rows([
            {"id": "a", "source": "Settings", "translation": "Settings"},
            {"id": "b", "source": "Hex %x", "translation": "Hexadécimal"},
            {"id": "c", "source": "Hello {name} 3", "translation": "Bonjour 4"},
            {"id": "d", "source": "Hello", "translation": "Bonjour"},
        ])
        by_worst = report["summary"]["records_by_highest_severity"]
        self.assertEqual(by_worst, {"critical": 1, "warning": 1, "informational": 1, "none": 1})
        self.assertEqual(sum(by_worst.values()), report["summary"]["total_records"])
        self.assertEqual([report["issues_by_severity"][s]["count"] for s in SEVERITY_ORDER], [1, 2, 1])
        record_c = report["affected_records"][2]
        self.assertEqual(record_c, {"record_id": "c", "record_index": 3, "issue_count": 2,
                                    "highest_severity": "critical",
                                    "issue_types": ["missing_placeholder", "numerical_inconsistency"]})
        self.assertEqual(report["summary"]["max_issues_on_one_record"], 2)

    def test_duplicate_identifiers_stay_separate_records_located_by_index(self):
        report = report_for_rows([
            {"id": "same", "source": "Open", "translation": ""},
            {"id": "same", "source": "Close", "translation": "Fermer"},
        ])
        self.assertEqual([(r["record_id"], r["record_index"], r["issue_count"]) for r in report["affected_records"]],
                         [("same", 1, 2), ("same", 2, 1)])
        self.assertEqual(report["affected_record_ids"], ["same"])
        self.assertEqual(report["summary"]["records_with_issues"], 2)

    def test_record_without_identifier_is_reported_by_row_fallback(self):
        report = report_for_rows([{"source": "Hello", "translation": "Bonjour"}, 42])
        self.assertEqual(report["affected_record_ids"], ["row:1", "row:2"])
        self.assertEqual(report["issues_by_category"]["invalid_record"]["record_ids"], ["row:2"])

    def test_report_is_plain_json_and_reproducible_for_a_fixed_time(self):
        first = report_for_file("samples/block3_examples.json")
        second = report_for_file("samples/block3_examples.json")
        self.assertEqual(first, second)
        self.assertEqual(json.loads(json.dumps(first)), first)
        self.assertEqual(first["generated_at"], FIXED_TIME)
        self.assertEqual(first["rules"], list(ALL_RULES))

    def test_generated_time_defaults_to_a_utc_timestamp(self):
        dataset = LoadedDataset((), "json", "memory.json")
        self.assertRegex(build_report(dataset, [])["generated_at"],
                         r"\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")

    def test_report_findings_are_the_findings_from_validation(self):
        dataset = load_dataset(ROOT / "samples/block3_examples.json")
        issues = validate_dataset(dataset)
        self.assertEqual(build_report(dataset, issues)["issues"], [issue.to_dict() for issue in issues])


class TextReportTests(unittest.TestCase):
    def test_text_report_shows_totals_severities_categories_and_records(self):
        text = render_text(report_for_file("samples/translations.csv"))
        flat = " ".join(text.split())
        for expected in ("Translation QA report", "Input: translations.csv (csv)", "Records analyzed: 6",
                         "Records with issues: 4 (66.7%)", "Total issues: 4", "Highest severity: critical",
                         "critical 2", "informational 0", "empty_translation 1 critical",
                         '#3 "sample-003" [critical] empty_translation',
                         '#6 "sample-006" [warning] source_copied'):
            with self.subTest(expected=expected):
                self.assertIn(expected, flat)

    def test_text_report_for_a_clean_dataset_says_none(self):
        text = render_text(report_for_file("samples/block3_valid.json"))
        self.assertIn("Highest severity:        none", text)
        self.assertEqual(text.count("\n  none"), 2)

    def test_identifier_containing_a_line_break_stays_on_one_line(self):
        text = render_text(report_for_rows([{"id": "line1\nline2", "source": "Save", "translation": ""}]))
        self.assertIn('#1 "line1\\nline2" [critical] empty_translation', text)


class ReportCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="translation-qa-report-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_rows(self, rows):
        path = self.root / "input.json"
        path.write_text(json.dumps(rows), encoding="utf-8")
        return path

    def run_cli(self, *arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main([str(argument) for argument in arguments])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_json_report_is_printed_and_saved_identically(self):
        source = self.write_rows([{"id": "a", "source": "Hello", "translation": ""}])
        output = self.root / "reports" / "report.json"
        code, stdout, stderr = self.run_cli("report", source, "--output", output)
        self.assertEqual((code, stderr), (1, ""))
        report = json.loads(stdout)
        self.assertEqual(report, json.loads(output.read_text(encoding="utf-8")))
        self.assertEqual(report["report"], "translation_qa_report")
        self.assertEqual(report["summary"]["total_issues"], 1)
        self.assertEqual(report["affected_record_ids"], ["a"])

    def test_text_report_is_printed_and_saved_identically(self):
        source = self.write_rows([{"id": "a", "source": "Hello", "translation": ""}])
        output = self.root / "report.txt"
        code, stdout, stderr = self.run_cli("report", source, "--report-format", "text", "--output", output)
        self.assertEqual((code, stderr), (1, ""))
        self.assertTrue(stdout.startswith("Translation QA report\n"))
        self.assertEqual(output.read_text(encoding="utf-8"), stdout)

    def test_report_uses_the_same_exit_policy_as_check(self):
        warning_only = self.write_rows([{"id": "a", "source": "Settings", "translation": "Settings"}])
        self.assertEqual(self.run_cli("report", warning_only)[0], 0)
        self.assertEqual(self.run_cli("report", warning_only, "--fail-on", "warning")[0], 1)
        critical = self.write_rows([{"id": "a", "source": "Hello", "translation": ""}])
        self.assertEqual(self.run_cli("report", critical)[0], 1)
        code, stdout, _ = self.run_cli("report", critical, "--fail-on", "none")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout)["summary"]["total_issues"], 1)

    def test_report_cannot_overwrite_its_input(self):
        source = self.write_rows([{"id": "a", "source": "Hello", "translation": "Bonjour"}])
        original = source.read_bytes()
        code, stdout, stderr = self.run_cli("report", source, "--output", source)
        self.assertEqual((code, stdout), (2, ""))
        self.assertEqual(json.loads(stderr)["error"], "output_error")
        self.assertEqual(source.read_bytes(), original)

    def test_unreadable_input_is_a_structured_error(self):
        code, stdout, stderr = self.run_cli("report", self.root / "missing.json")
        self.assertEqual((code, stdout), (2, ""))
        self.assertEqual(json.loads(stderr)["error"], "input_error")

    def test_text_report_survives_a_console_that_cannot_encode_an_identifier(self):
        source = self.write_rows([{"id": "বাংলা", "source": "Save", "translation": ""}])
        raw = io.BytesIO()
        console = io.TextIOWrapper(raw, encoding="ascii")  # strict, like a legacy console
        with redirect_stdout(console), redirect_stderr(io.StringIO()):
            code = main(["report", str(source), "--report-format", "text"])
            console.flush()
        printed = raw.getvalue()
        self.assertEqual(code, 1)
        self.assertIn(b"Translation QA report", printed)
        self.assertIn(b"\\u09ac", printed)

    def test_module_entry_point_reports_the_same_findings_as_check(self):
        environment = dict(os.environ, PYTHONIOENCODING="utf-8")

        def run(command):
            return subprocess.run([sys.executable, "-m", "translation_qa", command, "samples/translations.csv"],
                                  cwd=ROOT, env=environment, capture_output=True, text=True,
                                  encoding="utf-8", timeout=15, check=False)

        report, check = run("report"), run("check")
        self.assertEqual((report.returncode, report.stderr), (1, ""))
        parsed = json.loads(report.stdout)
        self.assertEqual(parsed["summary"]["total_records"], 6)
        self.assertEqual(parsed["issues"], json.loads(check.stdout)["issues"])


if __name__ == "__main__":
    unittest.main()
