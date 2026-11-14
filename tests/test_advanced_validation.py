from pathlib import Path
import csv
import json
import sys
import tempfile
import unittest

from translation_qa.loading import InputError, load_dataset
from translation_qa.models import InputRecord, Severity
from translation_qa.validation import validate_dataset, validate_record


class AdvancedValidationTests(unittest.TestCase):
    def issues(self, source="Hello", translation="Bonjour", **extra):
        return validate_record(InputRecord(1, {"id": "r1", "source": source, "translation": translation, **extra}))

    def types(self, source="Hello", translation="Bonjour", **extra):
        return {i.issue_type for i in self.issues(source, translation, **extra)}

    def test_balanced_matching_html(self):
        self.assertEqual(self.issues("<b>Hello</b>", "<b>Bonjour</b>"), [])

    def test_missing_html_tag(self):
        issues = self.issues("<b>Hello</b>", "Bonjour")
        self.assertEqual([(i.issue_type, i.severity) for i in issues], [("missing_html_tag", Severity.CRITICAL)])

    def test_unexpected_html_tag(self):
        self.assertEqual(self.types("Hello", "<i>Bonjour</i>"), {"unexpected_html_tag"})

    def test_mismatched_closing_tag(self):
        self.assertEqual(self.types("<b>Hello</b>", "<b>Bonjour</i>"), {"html_tag_mismatch"})

    def test_crossed_nesting_is_invalid(self):
        self.assertEqual(self.types("Hello", "<b><i>Bonjour</b></i>"), {"html_tag_mismatch"})

    def test_unclosed_tag(self):
        self.assertEqual(self.types("Hello", "<b>Bonjour"), {"html_tag_mismatch"})

    def test_incomplete_tag_is_reported(self):
        self.assertEqual(self.types("Hello", "Bonjour <b"), {"html_tag_mismatch"})

    def test_unclosed_attribute_quote_is_reported(self):
        self.assertEqual(self.types("Hello", '<span title="broken>Bonjour</span>'), {"html_tag_mismatch"})

    def test_unclosed_comment_is_reported(self):
        self.assertEqual(self.types("Hello", "Bonjour <!-- unfinished"), {"html_tag_mismatch"})

    def test_invalid_source_does_not_imply_missing_translation_tags(self):
        issues = self.issues("<b>Hello", "Bonjour")
        self.assertEqual([i.issue_type for i in issues], ["html_tag_mismatch"])
        self.assertIn("Source fragment", issues[0].description)

    def test_void_and_self_closing_tags(self):
        self.assertEqual(self.issues('<br>Hello<img src="a.png">', '<br/>Bonjour<img src="b.png"/>'), [])

    def test_void_tag_must_not_have_close_tag(self):
        self.assertEqual(self.types("Hello", "<br>Bonjour</br>"), {"html_tag_mismatch"})

    def test_tag_names_are_case_insensitive(self):
        self.assertEqual(self.issues("<B>Hello</B>", "<b>Bonjour</b>"), [])

    def test_complete_sibling_tags_may_reorder(self):
        self.assertEqual(self.issues("<b>Hello</b><i>Bye</i>", "<i>Au revoir</i><b>Bonjour</b>"), [])

    def test_balanced_nesting_change_is_review_warning(self):
        issues = self.issues("<b><i>Hello</i></b>", "<i><b>Bonjour</b></i>")
        self.assertEqual([(i.issue_type, i.severity) for i in issues], [("html_structure_changed", Severity.WARNING)])

    def test_tag_multiplicity_is_preserved(self):
        issues = self.issues("<b>Hello</b><b>Bye</b>", "<b>Bonjour</b>")
        self.assertEqual([i.issue_type for i in issues], ["missing_html_tag"])
        self.assertIn("<b> (count 1)", issues[0].description)

    def test_encoded_tag_text_is_literal_text(self):
        self.assertEqual(self.issues("Use &lt;b&gt; literally", "Utilisez &lt;b&gt; littéralement"), [])

    def test_encoded_and_real_tags_can_coexist(self):
        self.assertEqual(self.issues("<b>Use &lt;b&gt; literally</b>", "<b>Utilisez &lt;b&gt; littéralement</b>"), [])

    def test_greater_than_inside_quoted_attribute_is_not_a_tag_end(self):
        self.assertEqual(self.issues('<b title="a>b">Hello</b>', '<b title="a>b">Bonjour</b>'), [])

    def test_literal_comparison_with_spaces_is_not_a_tag(self):
        self.assertEqual(self.issues("Check a < b", "Vérifiez a < b"), [])

    def test_numeric_comparison_with_angle_brackets(self):
        self.assertEqual(self.issues("Check 2 < 3", "Vérifiez 2 < 3"), [])

    def test_comments_do_not_supply_visible_quantities(self):
        self.assertEqual(self.issues("<!-- 12 -->Hello", "<!-- 99 -->Bonjour"), [])

    def test_attribute_numbers_are_not_visible_quantities(self):
        self.assertEqual(self.issues('<span data-count="10">3 items</span>', '<span data-count="99">3 objets</span>'), [])

    def test_placeholders_inside_attributes_remain_checked(self):
        self.assertEqual(self.types('<a href="/{id}">Open</a>', '<a href="/fixed">Ouvrir</a>'), {"missing_placeholder"})

    def test_malformed_html_prevents_numeric_guesses(self):
        self.assertEqual(self.types("3 items", "<b>4 objets"), {"html_tag_mismatch"})

    def test_script_content_is_explicitly_unverified(self):
        kinds = self.types("<script>doSomething()</script>Hello", "<script>doSomething()</script>Bonjour")
        self.assertIn("html_content_unverified", kinds)
        self.assertNotIn("html_tag_mismatch", kinds)

    def test_tag_like_script_content_is_not_a_markup_error(self):
        kinds = self.types('<script>print("<b")</script>Hello', '<script>print("<b")</script>Bonjour')
        self.assertEqual(kinds, {"html_content_unverified"})

    def test_brace_conversion_change_is_review_warning(self):
        self.assertEqual(self.types("Value {item!r}", "Valeur {item!s}"), {"placeholder_format_mismatch"})

    def test_printf_width_change_is_review_warning(self):
        self.assertEqual(self.types("Count %03d", "Nombre %d"), {"placeholder_format_mismatch"})

    def test_implicit_printf_order_change_is_critical(self):
        issues = self.issues("%s has %d lives", "%d vies pour %s")
        self.assertEqual([(i.issue_type, i.severity) for i in issues], [("placeholder_order_mismatch", Severity.CRITICAL)])

    def test_explicit_printf_positions_may_reorder(self):
        self.assertEqual(self.issues("%1$s has %2$d lives", "%2$d vies pour %1$s"), [])

    def test_named_fields_keep_their_format_when_reordered(self):
        self.assertEqual(self.issues("{a:.2f} with {b:d}", "{b:d} avec {a:.2f}"), [])

    def test_mixed_printf_argument_styles_are_unverified(self):
        self.assertEqual(self.types("%s has %1$d", "Bonjour"), {"placeholder_syntax_unverified"})

    def test_missing_id_is_distinct_from_invalid_id(self):
        missing = validate_record(InputRecord(7, {"source": "Hello", "translation": "Bonjour"}))
        invalid = self.issues(id=True)
        self.assertEqual([(i.record_id, i.issue_type) for i in missing], [("row:7", "missing_field")])
        self.assertEqual([i.issue_type for i in invalid], ["invalid_field"])

    def test_missing_and_null_source_are_reported(self):
        for row in ({"id": "r1", "translation": "Bonjour"}, {"id": "r1", "source": None, "translation": "Bonjour"}):
            with self.subTest(row=row):
                self.assertEqual([i.issue_type for i in validate_record(InputRecord(1, row))], ["missing_field"])

    def test_wrong_field_types_do_not_raise(self):
        for value in ([], {}, True, 1.5):
            with self.subTest(value=value):
                self.assertIn("invalid_field", self.types(source=value))
                self.assertIn("invalid_field", self.types(translation=value))

    def test_integer_zero_is_a_valid_record_identifier(self):
        self.assertEqual(self.issues(id=0), [])

    def test_bad_optional_locale_is_reported_without_numeric_guess(self):
        for value in (12, True, [], "en--US", "fr$bad"):
            with self.subTest(value=value):
                self.assertEqual(self.types("3 lives", "4 vies", target_locale=value), {"invalid_field"})

    def test_optional_null_and_blank_locales_are_unspecified(self):
        self.assertEqual(self.issues(source_locale=None, target_locale="  "), [])

    def test_same_locale_is_normalized_before_copied_check(self):
        self.assertEqual(self.issues("Settings", "Settings", source_locale=" EN_us ", target_locale="en-US"), [])

    def test_copied_visible_words_are_found_despite_attribute_changes(self):
        self.assertEqual(self.types('<span class="a">Settings</span>', '<span class="b">Settings</span>'), {"source_copied"})

    def test_malformed_csv_row_does_not_trigger_unreliable_comparison(self):
        row = InputRecord(1, {"id": "a", "source": "3 lives", "translation": "4 vies"}, ("CSV row has extra cells.",))
        self.assertEqual([i.issue_type for i in validate_record(row)], ["invalid_record"])

    def test_oversized_json_integer_is_a_clean_input_error(self):
        limit = sys.get_int_max_str_digits()
        if not limit:
            self.skipTest("Interpreter integer parsing limit is disabled.")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "huge.json"
            path.write_text("[" + "9" * (limit + 1) + "]", encoding="utf-8")
            with self.assertRaises(InputError):
                load_dataset(path)

    def test_csv_json_equivalence_for_advanced_html_rules(self):
        rows = [
            {"id": "a", "source": '<b title="a>b">Hello</b>', "translation": '<b title="a>b">Bonjour</b>'},
            {"id": "b", "source": "<i>Save</i>", "translation": "Enregistrer"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "input.json").write_text(json.dumps(rows), encoding="utf-8")
            with (root / "input.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["id", "source", "translation"])
                writer.writeheader()
                writer.writerows(rows)
            csv_issues = validate_dataset(load_dataset(root / "input.csv"))
            json_issues = validate_dataset(load_dataset(root / "input.json"))
            self.assertEqual([i.to_dict() for i in csv_issues], [i.to_dict() for i in json_issues])
            self.assertEqual([i.issue_type for i in csv_issues], ["missing_html_tag"])


if __name__ == "__main__":
    unittest.main()
