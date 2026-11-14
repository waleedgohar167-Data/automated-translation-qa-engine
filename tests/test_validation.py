from decimal import Decimal
from pathlib import Path
import unittest

from translation_qa.loading import load_dataset
from translation_qa.models import InputRecord, Issue, LoadedDataset, Severity
from translation_qa.tokens import scan_numbers
from translation_qa.validation import validate_dataset, validate_record


class CoreValidationTests(unittest.TestCase):
    def issues(self, source="Hello", translation="Bonjour", **extra):
        return validate_record(InputRecord(1, {"id": "r1", "source": source, "translation": translation, **extra}))

    def types(self, source="Hello", translation="Bonjour", **extra):
        return {issue.issue_type for issue in self.issues(source, translation, **extra)}

    def test_correct_translation_has_no_findings(self):
        self.assertEqual(self.issues("Hello {name}, 3 items", "Bonjour {name}, 3 objets"), [])

    def test_missing_field_is_missing_translation(self):
        issues = validate_record(InputRecord(1, {"id": "r1", "source": "Open"}))
        self.assertEqual([i.issue_type for i in issues], ["missing_translation"])

    def test_null_is_missing_translation(self):
        self.assertEqual(self.types(translation=None), {"missing_translation"})

    def test_blank_text_is_empty_translation(self):
        for text in ("", " \t\r\n", "\u00a0\u2003"):
            with self.subTest(text=repr(text)):
                self.assertEqual(self.types(translation=text), {"empty_translation"})

    def test_number_zero_is_not_coerced_to_text(self):
        self.assertEqual(self.types(translation=0), {"invalid_field"})

    def test_missing_placeholder_is_critical(self):
        issues = self.issues("Hello {name}", "Bonjour")
        self.assertEqual([(i.issue_type, i.severity) for i in issues], [("missing_placeholder", Severity.CRITICAL)])

    def test_additional_placeholder_is_critical(self):
        self.assertEqual(self.types("Hello", "Bonjour {name}"), {"additional_placeholder"})

    def test_repeated_placeholder_counts_are_preserved(self):
        issues = self.issues("{name} called {name}", "{name} a appelé")
        self.assertEqual([i.issue_type for i in issues], ["missing_placeholder"])
        self.assertIn("{name} (count 1)", issues[0].description)

    def test_named_placeholders_can_reorder(self):
        self.assertEqual(self.issues("From {from} to {to}", "Vers {to} depuis {from}"), [])

    def test_placeholder_index_is_not_a_quantity(self):
        self.assertEqual(self.types("Hello {0}", "Bonjour {1}"), {"missing_placeholder", "additional_placeholder"})

    def test_brace_format_change_is_not_a_numeric_difference(self):
        # Block 3 adds a formatter-consistency warning. Precision is still not
        # a translated quantity and must not produce a numerical inconsistency.
        self.assertEqual(self.types("Cost {amount:.2f}: 3", "Coût {amount:.3f} : 3"),
                         {"placeholder_format_mismatch"})

    def test_printf_named_and_positional_tokens_are_compared(self):
        for token in ("%s", "%d", "%f", "%(name)s", "%1$s", "%03d"):
            with self.subTest(token=token):
                self.assertEqual(self.types("Hello " + token, "Bonjour"), {"missing_placeholder"})

    def test_escaped_braces_and_percent_are_literals(self):
        self.assertEqual(self.issues("Code {{name}} and 100%%", "Code littéral {{name}} et 100%%"), [])

    def test_complex_braces_are_explicitly_unverified(self):
        for source in ("Hello {user.name}", "Hello {name", "Amount {value:{width}.2f}"):
            with self.subTest(source=source):
                self.assertEqual(self.types(source, "Bonjour"), {"placeholder_syntax_unverified"})

    def test_unsupported_printf_is_explicitly_unverified(self):
        self.assertEqual(self.types("Hex %x", "Hexadécimal"), {"placeholder_syntax_unverified"})

    def test_number_difference_is_warning(self):
        issues = self.issues("You have 3 lives", "Vous avez 2 vies")
        self.assertEqual([(i.issue_type, i.severity) for i in issues], [("numerical_inconsistency", Severity.WARNING)])

    def test_numbers_can_reorder(self):
        self.assertEqual(self.issues("3 red and 5 blue", "5 bleus et 3 rouges"), [])

    def test_number_occurrence_counts_are_preserved(self):
        self.assertEqual(self.types("2 red and 2 blue", "2 rouges"), {"numerical_inconsistency"})

    def test_negative_number_is_different_from_positive(self):
        self.assertEqual(self.types("Balance -3", "Solde 3"), {"numerical_inconsistency"})

    def test_unicode_digits_compare_by_value(self):
        self.assertEqual(self.issues("You have 12 lives", "لديك ١٢ حياة"), [])

    def test_declared_locale_supports_decimal_comma(self):
        self.assertEqual(self.issues("Price 12.50", "Prix 12,50", source_locale="en", target_locale="fr"), [])

    def test_declared_locale_supports_thousands_grouping(self):
        self.assertEqual(self.issues("Total 1,234.50", "Summe 1.234,50", source_locale="en-US", target_locale="de"), [])

    def test_unknown_comma_format_is_not_guessed(self):
        self.assertEqual(self.types("Total 1,000", "Somme 1000"), {"number_format_unverified"})

    def test_unsupported_french_dot_format_is_not_guessed(self):
        self.assertTrue(scan_numbers("Prix 1.234", "fr").unverified)

    def test_leading_dot_decimal_is_not_silently_treated_as_integer(self):
        scan = scan_numbers("Price .5")
        self.assertTrue(scan.unverified or scan.values == (Decimal("0.5"),))

    def test_copied_words_are_warning(self):
        issues = self.issues("Settings", "  Settings  ")
        self.assertEqual([(i.issue_type, i.severity) for i in issues], [("source_copied", Severity.WARNING)])

    def test_copied_words_use_unicode_normalization(self):
        self.assertEqual(self.types("Café", "Cafe\u0301"), {"source_copied"})

    def test_equal_known_locales_are_not_copied_warning(self):
        self.assertEqual(self.issues("Settings", "Settings", source_locale="en-US", target_locale="en_US"), [])

    def test_only_number_or_placeholder_is_not_copied_warning(self):
        for value in ("123", "{0}", "%s"):
            with self.subTest(value=value):
                self.assertEqual(self.issues(value, value), [])

    def test_multiple_independent_errors_are_retained(self):
        self.assertEqual(self.types("Order {order_id}: 3", "Commande {client_id}: 4"),
                         {"missing_placeholder", "additional_placeholder", "numerical_inconsistency"})

    def test_malformed_records_do_not_stop_following_records(self):
        dataset = LoadedDataset((InputRecord(1, 42), InputRecord(2, {"id": "ok", "source": "Hello", "translation": "Bonjour"}),
                                 InputRecord(3, {"id": "bad", "source": "Save", "translation": ""})), "json", "test.json")
        issues = validate_dataset(dataset)
        self.assertEqual([(i.record_id, i.issue_type) for i in issues], [("row:1", "invalid_record"), ("bad", "empty_translation")])

    def test_every_issue_has_required_serializable_fields(self):
        issue = Issue("r1", 3, "source_copied", "Review copied text.", Severity.WARNING)
        self.assertEqual(issue.to_dict(), {"record_id": "r1", "record_index": 3, "issue_type": "source_copied",
                                          "description": "Review copied text.", "severity": "warning"})

    def test_csv_and_json_feed_identical_core_rules(self):
        root = Path(__file__).resolve().parents[1]
        csv_issues = validate_dataset(load_dataset(root / "samples/translations.csv"))
        json_issues = validate_dataset(load_dataset(root / "samples/translations.json"))
        self.assertEqual([i.to_dict() for i in csv_issues], [i.to_dict() for i in json_issues])
        self.assertEqual({i.issue_type for i in csv_issues},
                         {"empty_translation", "missing_placeholder", "numerical_inconsistency", "source_copied"})


if __name__ == "__main__":
    unittest.main()
