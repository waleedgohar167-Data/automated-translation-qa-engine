import unittest

from translation_qa.models import InputRecord, LoadedDataset, Severity
from translation_qa.validation import validate_dataset


class CrossRecordTests(unittest.TestCase):
    def issues(self, rows):
        dataset = LoadedDataset(tuple(InputRecord(i, row) for i, row in enumerate(rows, start=1)), "json", "test.json")
        return validate_dataset(dataset)

    def row(self, identifier, source="Open file", translation="Ouvrir le fichier", **extra):
        return {"id": identifier, "source": source, "translation": translation,
                "source_locale": "en", "target_locale": "fr", **extra}

    def test_duplicate_identifiers_flag_every_occurrence(self):
        issues = self.issues([self.row("same"), self.row("same", "Close file", "Fermer le fichier")])
        self.assertEqual([(i.record_id, i.record_index, i.issue_type) for i in issues],
                         [("same", 1, "duplicate_record_id"), ("same", 2, "duplicate_record_id")])

    def test_string_and_integer_same_public_identifier_collide(self):
        issues = self.issues([self.row(1), self.row("1", "Close file", "Fermer le fichier")])
        self.assertEqual([i.issue_type for i in issues], ["duplicate_record_id", "duplicate_record_id"])

    def test_record_identifier_case_is_preserved(self):
        self.assertEqual(self.issues([self.row("A"), self.row("a", "Close file", "Fermer le fichier")]), [])

    def test_repeated_pair_is_informational(self):
        issues = self.issues([self.row("a"), self.row("b")])
        self.assertEqual([(i.issue_type, i.severity) for i in issues],
                         [("duplicate_translation", Severity.INFORMATIONAL), ("duplicate_translation", Severity.INFORMATIONAL)])

    def test_different_sources_same_translation_are_review_warnings(self):
        issues = self.issues([self.row("a"), self.row("b", "Close file")])
        self.assertEqual([(i.issue_type, i.severity) for i in issues],
                         [("suspicious_translation_reuse", Severity.WARNING), ("suspicious_translation_reuse", Severity.WARNING)])

    def test_different_target_locales_are_not_grouped(self):
        self.assertEqual(self.issues([self.row("a"), self.row("b", "Close file", target_locale="de")]), [])

    def test_different_source_locales_are_not_grouped(self):
        self.assertEqual(self.issues([self.row("a"), self.row("b", "Datei öffnen", source_locale="de")]), [])

    def test_unspecified_target_locale_does_not_imply_a_language(self):
        self.assertEqual(self.issues([self.row("a", target_locale=None), self.row("b", "Close file", target_locale=None)]), [])

    def test_short_labels_are_excluded_from_reuse_heuristic(self):
        self.assertEqual(self.issues([self.row("a", "Accept", "OK"), self.row("b", "Continue", "OK")]), [])

    def test_number_and_placeholder_only_translations_are_excluded(self):
        self.assertEqual(self.issues([self.row("a", "123", "123"), self.row("b", "123", "123"),
                                     self.row("c", "{name}", "{name}"), self.row("d", "{name}", "{name}")]), [])

    def test_locale_whitespace_and_separator_normalization(self):
        issues = self.issues([self.row("a", target_locale="FR_fr"), self.row("b", target_locale=" fr-FR ")])
        self.assertEqual([i.issue_type for i in issues], ["duplicate_translation", "duplicate_translation"])

    def test_bad_record_does_not_prevent_cross_record_analysis(self):
        issues = self.issues([None, self.row("a"), self.row("b", "Close file")])
        self.assertEqual([(i.record_index, i.issue_type) for i in issues],
                         [(1, "invalid_record"), (2, "suspicious_translation_reuse"), (3, "suspicious_translation_reuse")])


if __name__ == "__main__":
    unittest.main()
