"""File-boundary acceptance tests using real temporary CSV/JSON files."""

import csv
import json
from pathlib import Path
import tempfile
import unittest

from translation_qa.loading import InputError, load_dataset


class InputBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="translation-qa-input-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rows = [{"id": "one", "source": "Hello", "translation": "Bonjour"}]

    def write(self, name, text, encoding="utf-8"):
        path = self.root / name
        path.write_text(text, encoding=encoding)
        return path

    def test_json_records_wrapper_preserves_records(self):
        path = self.write("wrapped.json", json.dumps({"records": self.rows, "batch": "demo"}))
        dataset = load_dataset(path)
        self.assertEqual([record.data for record in dataset.records], self.rows)
        self.assertEqual([record.index for record in dataset.records], [1])

    def test_json_utf8_bom_is_accepted(self):
        path = self.write("bom.json", json.dumps(self.rows), encoding="utf-8-sig")
        self.assertEqual(load_dataset(path).records[0].data, self.rows[0])

    def test_csv_utf8_bom_does_not_change_first_field_name(self):
        path = self.write("bom.csv", "id,source,translation\none,Hello,Bonjour\n", "utf-8-sig")
        self.assertEqual(load_dataset(path).records[0].data, self.rows[0])

    def test_quoted_csv_commas_quotes_and_newlines_are_preserved(self):
        rows = [{"id": "quoted", "source": 'Hello, "reader"\nNext line',
                 "translation": 'Bonjour, "lecteur"\nLigne suivante'}]
        path = self.root / "quoted.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["id", "source", "translation"])
            writer.writeheader()
            writer.writerows(rows)
        dataset = load_dataset(path)
        self.assertEqual([record.data for record in dataset.records], rows)
        self.assertEqual(dataset.records[0].input_problems, ())

    def test_empty_json_collection_is_a_valid_empty_dataset(self):
        dataset = load_dataset(self.write("empty.json", "[]"))
        self.assertEqual(dataset.records, ())
        self.assertEqual(dataset.input_format, "json")

    def test_header_only_csv_is_a_valid_empty_dataset(self):
        dataset = load_dataset(self.write("empty.csv", "id,source,translation\n"))
        self.assertEqual(dataset.records, ())
        self.assertEqual(dataset.input_format, "csv")

    def test_noncollection_json_payloads_are_rejected(self):
        for payload in (None, True, "text", 42, {}, {"records": {}}, {"records": None}):
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(InputError, "list of records"):
                    load_dataset(self.write("bad.json", json.dumps(payload)))

    def test_nonfinite_json_constants_are_rejected(self):
        for constant in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(constant=constant):
                with self.assertRaisesRegex(InputError, "non-standard numeric value"):
                    load_dataset(self.write("bad.json", "[" + constant + "]"))

    def test_duplicate_csv_headers_are_rejected(self):
        with self.assertRaisesRegex(InputError, "unique"):
            load_dataset(self.write("bad.csv", "id,source,source\na,Hello,Bonjour\n"))

    def test_blank_csv_header_names_are_rejected(self):
        for header in ("id,,translation", "id,   ,translation"):
            with self.subTest(header=header):
                with self.assertRaisesRegex(InputError, "must not be empty"):
                    load_dataset(self.write("bad.csv", header + "\na,Hello,Bonjour\n"))

    def test_unterminated_csv_quote_is_a_clean_input_error(self):
        with self.assertRaises(InputError):
            load_dataset(self.write("bad.csv", 'id,source,translation\na,Hello,"Bonjour\n'))

    def test_invalid_utf8_is_a_clean_input_error(self):
        path = self.root / "bad.json"
        path.write_bytes(b'["\xff"]')
        with self.assertRaises(InputError):
            load_dataset(path)

    def test_missing_file_is_a_clean_input_error(self):
        with self.assertRaises(InputError):
            load_dataset(self.root / "does-not-exist.json")

    def test_directory_input_is_a_clean_input_error(self):
        path = self.root / "directory.json"
        path.mkdir()
        with self.assertRaises(InputError):
            load_dataset(path)

    def test_unknown_extension_requires_explicit_format(self):
        with self.assertRaisesRegex(InputError, "specify --format"):
            load_dataset(self.write("records.data", json.dumps(self.rows)))

    def test_explicit_format_can_load_an_extensionless_file(self):
        path = self.write("records", json.dumps(self.rows))
        self.assertEqual(load_dataset(path, "json").records[0].data, self.rows[0])

    def test_uppercase_extension_is_detected(self):
        dataset = load_dataset(self.write("records.JSON", json.dumps(self.rows)))
        self.assertEqual(dataset.input_format, "json")
        self.assertEqual(len(dataset.records), 1)


if __name__ == "__main__":
    unittest.main()
