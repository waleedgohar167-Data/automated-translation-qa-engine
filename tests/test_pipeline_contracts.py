"""Acceptance contracts across rules, records, and serialized findings."""

import copy
import json
from pathlib import Path
import unittest

from translation_qa.loading import load_dataset
from translation_qa.models import InputRecord, LoadedDataset
from translation_qa.validation import validate_dataset


ROOT = Path(__file__).resolve().parents[1]


class PipelineContractTests(unittest.TestCase):
    def dataset(self, rows):
        return LoadedDataset(tuple(InputRecord(i, row) for i, row in enumerate(rows, start=1)),
                             "json", "acceptance.json")

    def test_validation_does_not_modify_raw_fields_or_nested_metadata(self):
        rows = [{"id": "a", "source": "Order {id}: 3", "translation": "Commande 4",
                 "metadata": {"tags": ["keep", {"value": 2}]}, "target_locale": "FR_fr"},
                {"id": "b", "source": "Hello", "translation": None}, ["bad", "record"]]
        original = copy.deepcopy(rows)
        issues = validate_dataset(self.dataset(rows))
        self.assertTrue(issues)
        self.assertEqual(rows, original)

    def test_repeated_validation_produces_identical_structured_findings(self):
        dataset = load_dataset(ROOT / "samples/block3_examples.json")
        first = [i.to_dict() for i in validate_dataset(dataset)]
        second = [i.to_dict() for i in validate_dataset(dataset)]
        self.assertEqual(first, second)
        self.assertEqual(len(first), 15)

    def test_local_and_cross_record_findings_remain_in_input_order(self):
        dataset = self.dataset([
            {"id": "same", "source": "Open", "translation": ""},
            {"id": "same", "source": "Close", "translation": "Fermer"},
        ])
        issues = validate_dataset(dataset)
        self.assertEqual([(i.record_index, i.issue_type) for i in issues],
                         [(1, "empty_translation"), (1, "duplicate_record_id"), (2, "duplicate_record_id")])

    def test_multiple_markup_placeholder_and_number_errors_are_retained(self):
        dataset = self.dataset([{"id": "combined", "source": "<b>Order {order_id}: 3</b>",
                                 "translation": "<i>Commande {customer_id}: 4</i>"}])
        issues = validate_dataset(dataset)
        self.assertEqual({i.issue_type for i in issues},
                         {"missing_html_tag", "unexpected_html_tag", "missing_placeholder",
                          "additional_placeholder", "numerical_inconsistency"})
        self.assertEqual(len(issues), 5)

    def test_absent_translation_does_not_generate_comparison_noise(self):
        issues = validate_dataset(self.dataset([{"id": "missing", "source": "<b>Order {id}: 3</b>"}]))
        self.assertEqual([(i.issue_type, i.severity.value) for i in issues], [("missing_translation", "critical")])

    def test_empty_dataset_has_no_findings(self):
        self.assertEqual(validate_dataset(self.dataset([])), [])

    def test_all_actual_fixture_findings_meet_the_public_issue_contract(self):
        dataset = load_dataset(ROOT / "samples/block3_examples.json")
        findings = [i.to_dict() for i in validate_dataset(dataset)]
        self.assertEqual(json.loads(json.dumps(findings)), findings)
        for finding in findings:
            with self.subTest(record=finding["record_index"], category=finding["issue_type"]):
                self.assertEqual(set(finding), {"record_id", "record_index", "issue_type", "description", "severity"})
                for field in ("record_id", "issue_type", "description"):
                    self.assertIsInstance(finding[field], str)
                    self.assertTrue(finding[field].strip())
                self.assertIsInstance(finding["record_index"], int)
                self.assertGreaterEqual(finding["record_index"], 1)
                self.assertLessEqual(finding["record_index"], len(dataset.records))
                self.assertIn(finding["severity"], {"critical", "warning", "informational"})

    def test_multiple_malformed_record_types_do_not_drop_later_errors(self):
        invalid_rows = [None, [], "not an object", 42, True]
        rows = [*invalid_rows, {"id": "last", "source": "Save", "translation": ""}]
        issues = validate_dataset(self.dataset(rows))
        self.assertEqual([(i.record_index, i.issue_type) for i in issues],
                         [(1, "invalid_record"), (2, "invalid_record"), (3, "invalid_record"),
                          (4, "invalid_record"), (5, "invalid_record"), (6, "empty_translation")])


if __name__ == "__main__":
    unittest.main()
