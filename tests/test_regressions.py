"""Regression tests for defects diagnosed during the Block 5 debugging review.

Each class names the bug it covers. A test either reproduces the defect (it
failed against the Block 4 code; see docs/checkpoints/block5-tests-before-fixes.txt)
or is marked "guard": it protects neighbouring behaviour the fix must not change.
File tests use disposable temporary files only.
"""

from contextlib import redirect_stderr, redirect_stdout
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from translation_qa import validation
from translation_qa.cli import main
from translation_qa.loading import InputError, load_dataset
from translation_qa.models import InputRecord, LoadedDataset
from translation_qa.tokens import scan_numbers, scan_placeholders
from translation_qa.validation import ALL_RULES, validate_dataset, validate_record


def issues_for(source, translation, **extra):
    row = {"id": "r1", "source": source, "translation": translation, **extra}
    return validate_record(InputRecord(1, row))


def issue_types(source, translation, **extra):
    return {issue.issue_type for issue in issues_for(source, translation, **extra)}


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="translation-qa-regression-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_cli(self, arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main([str(argument) for argument in arguments])
        return code, stdout.getvalue(), stderr.getvalue()

    def write_rows(self, rows, name="input.json"):
        path = self.root / name
        path.write_text(json.dumps(rows), encoding="utf-8")
        return path


class OutputAliasTests(TempDirCase):
    """B4-001: a report path that is a hard link to the input replaced the input."""

    def test_hard_link_alias_is_rejected_before_writing(self):
        source = self.write_rows([{"id": "one", "source": "Hello", "translation": "Bonjour"}])
        original = source.read_bytes()
        alias = self.root / "hardlinked.json"
        try:
            os.link(source, alias)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"This filesystem cannot create hard links: {exc}")
        code, stdout, stderr = self.run_cli(["check", source, "--output", alias])
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertEqual(json.loads(stderr)["error"], "output_error")

    def test_existing_unrelated_report_file_can_still_be_replaced(self):
        # Guard: the identity check must only reject aliases of the input.
        source = self.write_rows([{"id": "one", "source": "Hello", "translation": "Bonjour"}])
        output = self.root / "old-report.json"
        output.write_text("stale report", encoding="utf-8")
        code, stdout, stderr = self.run_cli(["check", source, "--output", output])
        self.assertEqual((code, stderr), (0, ""))
        self.assertEqual(json.loads(output.read_text(encoding="utf-8")), json.loads(stdout))


class OutputEncodingTests(TempDirCase):
    """B5-004 and B5-005: text that cannot be encoded broke the saved report and error output."""

    def test_lone_surrogate_in_input_does_not_block_the_saved_report(self):
        source = self.root / "input.json"
        # "\ud83d" is half of an emoji escape: valid JSON, but UTF-8 cannot encode it.
        source.write_text('[{"id": "\\ud83d", "source": "Hello", "translation": ""}]', encoding="utf-8")
        output = self.root / "report.json"
        code, stdout, stderr = self.run_cli(["check", source, "--output", output])
        self.assertEqual(stderr, "")
        self.assertEqual(code, 1)
        saved = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(saved, json.loads(stdout))
        self.assertEqual([(i["record_id"], i["issue_type"]) for i in saved["issues"]],
                         [("\ud83d", "empty_translation")])

    def test_error_output_is_ascii_json_for_any_file_name(self):
        missing = self.root / "файл-😀.json"
        code, stdout, stderr = self.run_cli(["check", missing])
        self.assertEqual((code, stdout), (2, ""))
        self.assertTrue(stderr.isascii(), "Error output must survive any console encoding.")
        error = json.loads(stderr)
        self.assertEqual(error["error"], "input_error")
        self.assertIn("файл-😀.json", error["message"])


class NumberSignTests(unittest.TestCase):
    """B5-001: a hyphen directly after a letter or digit was read as a minus sign."""

    def test_ranges_compounds_and_dates_are_not_negative_numbers(self):
        cases = (
            ("Levels 1-5", "Niveaux 1 à 5"),
            ("Pages 10-20", "Pages 10–20"),
            ("Top-10 players", "Les 10 meilleurs joueurs"),
            ("Released 2026-11-14", "Sortie le 2026-11-14"),
        )
        for source, translation in cases:
            with self.subTest(source=source):
                self.assertEqual(issue_types(source, translation), set())

    def test_scan_reads_range_endpoints_as_positive_values(self):
        self.assertEqual(scan_numbers("Levels 1-5").values, (Decimal(1), Decimal(5)))
        self.assertEqual(scan_numbers("COVID-19").values, (Decimal(19),))

    def test_standalone_signs_are_still_negative_numbers(self):
        # Guard: a sign after a space, bracket, or at the start is still a sign.
        self.assertEqual(scan_numbers("-5 to -1").values, (Decimal(-5), Decimal(-1)))
        cases = (
            ("Balance -3", "Solde 3"),
            ("Temperature: -5", "Température : 5"),
            ("(-2) points", "(2) points"),
            ("Offset −4", "Décalage 4"),
        )
        for source, translation in cases:
            with self.subTest(source=source):
                self.assertEqual(issue_types(source, translation), {"numerical_inconsistency"})

    def test_changed_range_endpoint_is_still_reported(self):
        # Guard: only the sign interpretation changed, not the value comparison.
        self.assertEqual(issue_types("Levels 1-5", "Niveaux 1 à 6"), {"numerical_inconsistency"})


class DoubleBracePlaceholderTests(unittest.TestCase):
    """B5-002: {{name}} template placeholders were treated as literal text and never compared."""

    def test_dropped_double_brace_placeholder_is_missing(self):
        issues = issues_for("Hello {{name}}!", "Bonjour !")
        self.assertEqual([(i.issue_type, i.severity.value) for i in issues],
                         [("missing_placeholder", "critical")])
        self.assertIn("{{name}} (count 1)", issues[0].description)

    def test_renamed_double_brace_placeholder_is_missing_and_additional(self):
        self.assertEqual(issue_types("Hello {{ name }}!", "Bonjour {{nom}} !"),
                         {"missing_placeholder", "additional_placeholder"})

    def test_added_double_brace_placeholder_is_additional(self):
        self.assertEqual(issue_types("Welcome back", "Bon retour {{name}}"), {"additional_placeholder"})

    def test_inner_spacing_and_order_may_change(self):
        # Guard: {{ count }} and {{count}} are the same placeholder; order is free.
        self.assertEqual(issue_types("{{count}} files from {{ user.name }}",
                                     "{{user.name}} a envoyé {{ count }} fichiers"), set())

    def test_digits_inside_a_double_brace_name_are_not_quantities(self):
        self.assertEqual(issue_types("Step {{step2}} of 3", "Étape {{step2}} sur 3"), set())
        self.assertEqual(issue_types("Step {{step2}}", "Étape {{step3}}"),
                         {"missing_placeholder", "additional_placeholder"})

    def test_other_doubled_braces_remain_escaped_literals(self):
        # Guard: only {{identifier}} is a placeholder; Python-style escapes are unchanged.
        literal = scan_placeholders("Open {{ then close }} or {{}}")
        self.assertEqual((literal.tokens, literal.unverified), ((), False))
        self.assertEqual(scan_placeholders("Value {{{name}}}").tokens, ("{name}",))


class CopiedTextReviewTests(unittest.TestCase):
    """B5-006: an unbalanced brace silently disabled the copied-text review."""

    def test_copied_text_with_unbalanced_brace_is_still_flagged(self):
        self.assertEqual(issue_types("Press } to continue", "Press } to continue"),
                         {"placeholder_syntax_unverified", "source_copied"})

    def test_translated_text_with_unbalanced_brace_is_not_called_copied(self):
        # Guard.
        self.assertEqual(issue_types("Press } to continue", "Appuyez sur } pour continuer"),
                         {"placeholder_syntax_unverified"})


class CsvHeaderTests(TempDirCase):
    """B5-003: padded or capitalised CSV headers made every row look incomplete."""

    def load(self, text):
        path = self.root / "input.csv"
        path.write_text(text, encoding="utf-8")
        return load_dataset(path)

    def test_spaces_around_header_names_are_ignored(self):
        dataset = self.load("id, source , translation\n1,Hello,Bonjour\n")
        self.assertEqual(dataset.records[0].data, {"id": "1", "source": "Hello", "translation": "Bonjour"})
        self.assertEqual(validate_dataset(dataset), [])

    def test_documented_field_names_are_accepted_in_any_letter_case(self):
        dataset = self.load("ID,Source,TRANSLATION,Target_Locale,Notes\n1,Hello,Bonjour,fr,Greeting\n")
        self.assertEqual(list(dataset.records[0].data),
                         ["id", "source", "translation", "target_locale", "Notes"])
        self.assertEqual(validate_dataset(dataset), [])

    def test_headers_that_collide_after_cleaning_are_rejected(self):
        with self.assertRaisesRegex(InputError, "unique"):
            self.load("id,ID ,source,translation\n1,2,Hello,Bonjour\n")

    def test_cell_values_are_still_not_trimmed(self):
        # Guard: only header labels are cleaned; record values stay raw.
        dataset = self.load("id,source,translation\n1, Hello , Bonjour \n")
        self.assertEqual(dataset.records[0].data["source"], " Hello ")
        self.assertEqual(dataset.records[0].data["translation"], " Bonjour ")


class RecordFailureIsolationTests(unittest.TestCase):
    """Error handling: an unexpected failure in one record must not abort the dataset."""

    def test_unexpected_rule_error_becomes_a_finding_for_that_record_only(self):
        real_scan = validation.scan_markup

        def failing_scan(text):
            if text == "boom":
                raise RuntimeError("simulated rule failure")
            return real_scan(text)

        rows = [{"id": "a", "source": "boom", "translation": "boum"},
                {"id": "b", "source": "Save", "translation": ""}]
        dataset = LoadedDataset(tuple(InputRecord(i, row) for i, row in enumerate(rows, start=1)),
                                "json", "test.json")
        with mock.patch.object(validation, "scan_markup", failing_scan):
            issues = validate_dataset(dataset)
        self.assertEqual([(i.record_id, i.issue_type, i.severity.value) for i in issues],
                         [("a", "validation_error", "critical"), ("b", "empty_translation", "critical")])
        self.assertIn("RuntimeError", issues[0].description)

    def test_validation_error_is_in_the_published_rule_catalog(self):
        self.assertIn("validation_error", ALL_RULES)


if __name__ == "__main__":
    unittest.main()
