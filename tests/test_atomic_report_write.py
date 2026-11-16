import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from translation_qa.cli import OutputError, _aliases_input, write_report


class AtomicReportWriteTests(unittest.TestCase):
    """Regression coverage for the Day 8 A02 interrupted-report finding."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="translation-qa-atomic-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input_path = self.root / "input.json"
        self.input_path.write_text(
            '[{"id":"one","source":"Hello","translation":"Bonjour"}]\n',
            encoding="utf-8",
        )
        self.output = self.root / "reports" / "report.json"

    def test_new_report_is_written_as_valid_utf8_text(self):
        write_report(self.output, self.input_path, '{"status":"ok","text":"é"}\n')

        self.assertEqual(
            self.output.read_text(encoding="utf-8"),
            '{"status":"ok","text":"é"}\n',
        )
        self.assertEqual(list(self.output.parent.glob(f".{self.output.name}.*.tmp")), [])

    def test_successful_replacement_replaces_previous_complete_report(self):
        self.output.parent.mkdir(parents=True)
        self.output.write_text('{"status":"old"}\n', encoding="utf-8")

        write_report(self.output, self.input_path, '{"status":"new"}\n')

        self.assertEqual(
            self.output.read_text(encoding="utf-8"),
            '{"status":"new"}\n',
        )
        self.assertEqual(list(self.output.parent.glob(f".{self.output.name}.*.tmp")), [])

    def test_temporary_write_failure_preserves_previous_report(self):
        self.output.parent.mkdir(parents=True)
        previous = '{"status":"complete","version":1}\n'
        self.output.write_text(previous, encoding="utf-8")

        with patch(
            "translation_qa.cli.Path.write_text",
            side_effect=OSError("simulated partial write failure"),
        ):
            with self.assertRaises(OutputError):
                write_report(self.output, self.input_path, '{"status":"new"}\n')

        self.assertEqual(self.output.read_text(encoding="utf-8"), previous)
        self.assertEqual(list(self.output.parent.glob(f".{self.output.name}.*.tmp")), [])

    def test_replacement_failure_preserves_previous_report(self):
        self.output.parent.mkdir(parents=True)
        previous = '{"status":"complete","version":2}\n'
        self.output.write_text(previous, encoding="utf-8")

        with patch(
            "translation_qa.cli.os.replace",
            side_effect=OSError("simulated replacement failure"),
        ):
            with self.assertRaises(OutputError):
                write_report(self.output, self.input_path, '{"status":"new"}\n')

        self.assertEqual(self.output.read_text(encoding="utf-8"), previous)
        self.assertEqual(list(self.output.parent.glob(f".{self.output.name}.*.tmp")), [])

    def test_failed_first_write_leaves_no_final_report(self):
        with patch(
            "translation_qa.cli.Path.write_text",
            side_effect=OSError("simulated first-write failure"),
        ):
            with self.assertRaises(OutputError):
                write_report(self.output, self.input_path, '{"status":"new"}\n')

        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.output.parent.glob(f".{self.output.name}.*.tmp")), [])

    def test_failed_replacement_does_not_expose_partial_json(self):
        self.output.parent.mkdir(parents=True)
        previous = '{"records":[{"id":"old"}]}\n'
        self.output.write_text(previous, encoding="utf-8")

        with patch(
            "translation_qa.cli.os.replace",
            side_effect=OSError("simulated replacement failure"),
        ):
            with self.assertRaises(OutputError):
                write_report(
                    self.output,
                    self.input_path,
                    '{"records":[{"id":"new","translation":"Bonjour"}]}\n',
                )

        preserved = json.loads(self.output.read_text(encoding="utf-8"))
        self.assertEqual(preserved, {"records": [{"id": "old"}]})

    def test_input_alias_protection_is_checked_before_temporary_write(self):
        self.input_path.write_text(
            '[{"id":"one","source":"Hello","translation":"Bonjour"}]\n',
            encoding="utf-8",
        )

        with self.assertRaises(OutputError):
            write_report(self.input_path, self.input_path, '{"not":"input"}\n')

        self.assertTrue(_aliases_input(self.input_path, self.input_path))
        self.assertEqual(
            self.input_path.read_text(encoding="utf-8"),
            '[{"id":"one","source":"Hello","translation":"Bonjour"}]\n',
        )

    def test_unicode_backslashreplace_contract_survives_atomic_write(self):
        self.output.parent.mkdir(parents=True)
        text_with_surrogate = '{"value":"\ud83d"}\n'

        write_report(self.output, self.input_path, text_with_surrogate)

        saved = self.output.read_text(encoding="utf-8")
        self.assertIn(r"\ud83d", saved)
        self.assertNotIn("\ud83d", saved)
        json.loads(saved)


if __name__ == "__main__":
    unittest.main()
