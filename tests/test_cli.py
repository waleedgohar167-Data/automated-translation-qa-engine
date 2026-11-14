from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest

from translation_qa.cli import main


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def run_cli(self, arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def write(self, payload):
        path = self.root / "input.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_valid_input_exits_zero_with_no_issues(self):
        path = self.write([{"id": "a", "source": "Hello", "translation": "Bonjour"}])
        code, stdout, stderr = self.run_cli(["check", str(path)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout)["issues"], [])
        self.assertEqual(stderr, "")

    def test_critical_issue_exits_one_and_writes_output(self):
        path = self.write([{"id": "a", "source": "Hello", "translation": ""}])
        output = self.root / "reports/result.json"
        code, stdout, stderr = self.run_cli(["check", str(path), "--output", str(output)])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(stdout), json.loads(output.read_text(encoding="utf-8")))
        self.assertEqual(json.loads(stdout)["issue_count"], 1)
        self.assertEqual(stderr, "")

    def test_warning_threshold_is_configurable(self):
        path = self.write([{"id": "a", "source": "Settings", "translation": "Settings"}])
        self.assertEqual(self.run_cli(["check", str(path)])[0], 0)
        self.assertEqual(self.run_cli(["check", str(path), "--fail-on", "warning"])[0], 1)
        self.assertEqual(self.run_cli(["check", str(path), "--fail-on", "none"])[0], 0)

    def test_input_cannot_be_overwritten_by_output(self):
        path = self.write([{"id": "a", "source": "Hello", "translation": "Bonjour"}])
        original = path.read_bytes()
        code, stdout, stderr = self.run_cli(["check", str(path), "--output", str(path)])
        self.assertEqual(code, 2)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(stdout, "")
        self.assertEqual(json.loads(stderr)["error"], "output_error")

    def test_parse_error_has_no_traceback(self):
        path = self.write([])
        path.write_text("[broken", encoding="utf-8")
        code, stdout, stderr = self.run_cli(["check", str(path)])
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertEqual(json.loads(stderr)["error"], "input_error")
        self.assertNotIn("Traceback", stderr)

    def test_original_inspect_command_still_works(self):
        path = self.write([{"id": "a", "source": "Hello", "translation": "Bonjour"}])
        code, stdout, stderr = self.run_cli(["inspect", str(path)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout)["records_loaded"], 1)
        self.assertFalse(json.loads(stdout)["validation_performed"])


if __name__ == "__main__":
    unittest.main()
