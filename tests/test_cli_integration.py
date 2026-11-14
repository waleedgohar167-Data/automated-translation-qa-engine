"""Exercise the public module command in a separate Python process.

All writes, including file-alias safety checks, use disposable temporary files.
No repository sample or user input file is modified by these tests.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CliIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="translation-qa-cli-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_rows(self, rows, name="input.json"):
        path = self.root / name
        path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        return path

    def valid_input(self):
        return self.write_rows([{"id": "one", "source": "Hello", "translation": "Bonjour"}])

    def run_module(self, *arguments):
        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "utf-8"
        return subprocess.run(
            [sys.executable, "-m", "translation_qa", *map(str, arguments)],
            cwd=ROOT, env=environment, capture_output=True, text=True,
            encoding="utf-8", timeout=15, check=False,
        )

    def test_module_entry_point_saves_unicode_json_and_keeps_input(self):
        source = self.write_rows([{"id": "বাংলা", "source": "Hello {name}",
                                   "translation": "হ্যালো {name}"}])
        original = source.read_bytes()
        output = self.root / "nested" / "result.json"
        result = self.run_module("check", source, "--output", output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        report = json.loads(result.stdout)
        self.assertEqual(report, json.loads(output.read_text(encoding="utf-8")))
        self.assertEqual(report["records_analyzed"], 1)
        self.assertEqual(report["issues"], [])
        self.assertEqual(source.read_bytes(), original)

    def test_warning_remains_visible_with_default_success_exit(self):
        source = self.write_rows([{"id": "one", "source": "Settings", "translation": "Settings"}])
        result = self.run_module("check", source)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([(i["issue_type"], i["severity"]) for i in json.loads(result.stdout)["issues"]],
                         [("source_copied", "warning")])

    def test_fail_on_none_does_not_hide_critical_findings(self):
        source = self.write_rows([{"id": "one", "source": "Hello", "translation": ""}])
        default = self.run_module("check", source)
        permissive = self.run_module("check", source, "--fail-on", "none")
        self.assertEqual(default.returncode, 1)
        self.assertEqual(permissive.returncode, 0)
        self.assertEqual(json.loads(default.stdout), json.loads(permissive.stdout))
        self.assertEqual(json.loads(permissive.stdout)["issues"][0]["severity"], "critical")

    def test_informational_threshold_changes_exit_without_changing_findings(self):
        source = self.write_rows([{"id": "one", "source": "Value %x", "translation": "Valeur"}])
        default = self.run_module("check", source)
        strict = self.run_module("check", source, "--fail-on", "informational")
        self.assertEqual(default.returncode, 0)
        self.assertEqual(strict.returncode, 1)
        self.assertEqual(json.loads(default.stdout), json.loads(strict.stdout))
        self.assertEqual(json.loads(strict.stdout)["issues"][0]["severity"], "informational")

    def test_fail_on_none_does_not_suppress_input_errors(self):
        source = self.root / "broken.json"
        source.write_text("[broken", encoding="utf-8")
        result = self.run_module("check", source, "--fail-on", "none")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertEqual(json.loads(result.stderr)["error"], "input_error")
        self.assertNotIn("Traceback", result.stderr)

    def test_invalid_cli_choice_returns_usage_error(self):
        result = self.run_module("check", self.valid_input(), "--fail-on", "silent")
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid choice", result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("Traceback", result.stderr)

    def test_missing_input_has_structured_error_without_traceback(self):
        result = self.run_module("check", self.root / "missing.json")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertEqual(json.loads(result.stderr)["error"], "input_error")
        self.assertNotIn("Traceback", result.stderr)

    def test_output_parent_file_is_a_clean_error_and_is_preserved(self):
        blocker = self.root / "not-a-directory"
        blocker.write_text("preserve this file", encoding="utf-8")
        result = self.run_module("check", self.valid_input(), "--output", blocker / "report.json")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stderr)["error"], "output_error")
        self.assertEqual(blocker.read_text(encoding="utf-8"), "preserve this file")
        self.assertEqual(result.stdout, "")
        self.assertNotIn("Traceback", result.stderr)

    def test_cli_format_override_reaches_loader(self):
        source = self.write_rows([{"id": "one", "source": "Hello", "translation": "Bonjour"}], "input.data")
        result = self.run_module("check", source, "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["input_format"], "json")
        self.assertEqual(json.loads(result.stdout)["issue_count"], 0)

    def test_rule_catalog_is_consistent_for_clean_and_failing_inputs(self):
        clean = json.loads(self.run_module("check", self.valid_input()).stdout)
        bad_file = self.write_rows([{"id": "bad", "source": "Hello", "translation": ""}], "bad.json")
        findings = json.loads(self.run_module("check", bad_file).stdout)
        self.assertEqual(clean["rules"], findings["rules"])
        self.assertIn("html_structure_changed", clean["rules"])
        self.assertEqual(len(clean["rules"]), len(set(clean["rules"])))
        self.assertTrue({i["issue_type"] for i in findings["issues"]}.issubset(set(clean["rules"])))

    def test_output_path_with_parent_segments_cannot_overwrite_input(self):
        source = self.valid_input()
        original = source.read_bytes()
        subdirectory = self.root / "nested"
        subdirectory.mkdir()
        alias = subdirectory / ".." / source.name
        result = self.run_module("check", source, "--output", alias)
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stderr)["error"], "output_error")

    def test_symlink_output_cannot_overwrite_input(self):
        source = self.valid_input()
        original = source.read_bytes()
        alias = self.root / "linked.json"
        try:
            alias.symlink_to(source)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"This environment cannot create symbolic links: {exc}")
        result = self.run_module("check", source, "--output", alias)
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stderr)["error"], "output_error")

    def test_hardlink_output_cannot_overwrite_input(self):
        source = self.valid_input()
        original = source.read_bytes()
        alias = self.root / "hardlinked.json"
        try:
            os.link(source, alias)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"This filesystem cannot create hard links: {exc}")
        result = self.run_module("check", source, "--output", alias)
        self.assertEqual(source.read_bytes(), original,
                         "Writing a report through a hard link must not replace the input data.")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stderr)["error"], "output_error")


if __name__ == "__main__":
    unittest.main()
