import json
from pathlib import Path
import tempfile
import unittest

from translation_qa.loading import InputError, load_dataset


class LoadingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, filename, content):
        path = self.root / filename
        path.write_text(content, encoding="utf-8")
        return path

    def test_csv_and_json_samples_have_identical_records(self):
        root = Path(__file__).resolve().parents[1]
        csv_data = load_dataset(root / "samples/translations.csv")
        json_data = load_dataset(root / "samples/translations.json")
        self.assertEqual(len(csv_data.records), 6)
        self.assertEqual([r.data for r in csv_data.records], [r.data for r in json_data.records])

    def test_json_preserves_missing_null_and_empty_values(self):
        rows = [{"id": "a"}, {"id": "b", "translation": None}, {"id": "c", "translation": ""}]
        data = load_dataset(self.write("rows.json", json.dumps(rows)))
        self.assertNotIn("translation", data.records[0].data)
        self.assertIsNone(data.records[1].data["translation"])
        self.assertEqual(data.records[2].data["translation"], "")

    def test_malformed_record_does_not_discard_valid_neighbors(self):
        data = load_dataset(self.write("rows.json", '[{"id":"a"}, 42, {"id":"b"}]'))
        self.assertEqual(len(data.records), 3)
        self.assertEqual(data.records[1].data, 42)
        self.assertEqual(data.records[2].data["id"], "b")

    def test_malformed_json_becomes_clear_input_error(self):
        with self.assertRaises(InputError):
            load_dataset(self.write("broken.json", '[{"id":'))

    def test_csv_row_width_problem_is_retained(self):
        data = load_dataset(self.write("rows.csv", "id,source,translation\na,Hello\nb,Bye,Salut,extra\n"))
        self.assertEqual(len(data.records), 2)
        self.assertIsNone(data.records[0].data["translation"])
        self.assertTrue(data.records[0].input_problems)
        self.assertTrue(data.records[1].input_problems)

    def test_duplicate_json_field_is_rejected(self):
        with self.assertRaisesRegex(InputError, "Duplicate JSON object field"):
            load_dataset(self.write("duplicate.json", '[{"id":"a","id":"b"}]'))


if __name__ == "__main__":
    unittest.main()
