# Block 7 — Final engineering delivery

Engine version 0.5.0. This checkpoint finalizes the README, adds pytest configuration, and records a verification of the project from a fresh clone. No application code changed after Block 6.

## Final verification

Each item was checked in a fresh clone with no files carried over. The full transcript is in `block7-clean-setup.txt`.

| Check | Result | How it was verified |
| --- | --- | --- |
| CSV input works | Pass | `inspect`, `check`, and `report` on `samples/translations.csv`; `check` on `samples/block3_valid.csv` |
| JSON input works | Pass | `inspect` and `check` on `samples/translations.json`; `report` on `samples/block3_examples.json` |
| CSV and JSON agree | Pass | The two `translations` samples give the same 4 findings |
| Validation rules work | Pass | 22 issue types; the Block 3 issue sample gives 15 findings in 11 categories; rule-level tests |
| Test suite runs | Pass | 183 of 183 under `python -m unittest` and under `python -m pytest` |
| Report generation works | Pass | Text report printed; JSON report saved and parsed back |
| README instructions are correct | Pass | Every command in the README was executed in the fresh clone |
| Reproducible from a clean setup | Pass | Clone, create a virtual environment, `pip install -e ".[test]"`, run the installed `translation-qa` command and both test runners |
| No credentials or sensitive information | Pass | Pattern scan of tracked files for API keys, passwords, private keys, and access tokens found nothing; no `.env` file is tracked |
| Generated files stay out of version control | Pass | `git status` is empty after running everything; `.venv/`, `reports/`, and build output are ignored |
| Final code is committed | Owner to confirm | Confirm on GitHub after the final push |

The verification was recorded in the preparation environment (Linux, Python 3.13.18). The owner's local Windows results are reported separately. One note for transparency: `block4-local-test-output.txt` contains local file paths from the owner's machine, which include a Windows account name. It contains no credentials.

## Test results across the project

| Checkpoint | Tests | Passed | Failed |
| --- | ---: | ---: | ---: |
| Block 3 | 101 | 101 | 0 |
| Block 4 | 139 | 138 | 1 |
| Block 5 | 161 | 161 | 0 |
| Block 6 and final | 183 | 183 | 0 |

Final run: `block7-test-output.txt`.

## Technical summary

### What was built

A Python command-line engine that reads source and translated text from CSV or JSON and reports mechanical translation defects as structured findings. It has three commands: `inspect` (load only), `check` (structured issue list), and `report` (aggregated statistics as JSON or text). It implements 22 issue types across empty and missing translations, placeholders, numbers, copied text, HTML tags, record structure, and duplicates, each with a severity of critical, warning, or informational. It has no third-party runtime dependencies.

### Key engineering decisions

- **One engine, two adapters.** The CSV and JSON loaders only turn a file into records, so every rule behaves identically for both formats. A test asserts that the two sample files give identical findings.
- **Raw values are preserved.** Nothing is trimmed or converted, so a wrong type or a missing value is reported instead of hidden.
- **Unverifiable is labelled, not guessed.** Unsupported placeholder, number, or markup syntax yields an informational finding and skips only that comparison. This keeps false positives down and makes the tool's limits visible in its output.
- **Rules are pure and ordered.** Rules return `Issue` objects and do no input or output. Findings come out in a fixed order, so results are reproducible and can be compared between runs.
- **Malformed data cannot stop a run.** Bad records become findings, an unexpected rule failure is isolated to its record, and unreadable files end with a structured error and exit code 2.
- **Severity as policy.** The exit code depends on a configurable threshold, which never hides findings.
- **Standard library only.** `unittest` was chosen so the suite runs on a clean Python install; the same tests run under pytest.

### Problems encountered and solved

- **Tolerant HTML parsing (Block 3).** Python's `HTMLParser` accepts incomplete markup, so unfinished tags, quotes, and comments were missed. Solved by scanning the raw delimiters first, then using the parser and an explicit tag stack for structure.
- **Input overwrite through a hard link (Blocks 4 and 5).** A test showed that `--output` could replace the input file when given a hard link to it, because resolved paths differ for two names of one file. Solved by comparing file identity before writing.
- **Six further defects found by review (Block 5).** Hyphens read as minus signs, double-brace placeholders ignored, padded CSV headers, a failed save on a lone surrogate, error output that was not always valid JSON, and a skipped copied-text review. Each was reproduced with a failing test before it was fixed.
- **A long validation function (Block 5).** `validate_record` was split into one small function per rule family, with behaviour held constant by the existing tests.
- **Schedule.** Blocks 5 to 7 were delivered later than originally scheduled because the AI tool in use reached its usage limit. This was reported to the Engineering Team and development continued with a different tool.

### Remaining limitations

- No assessment of meaning, grammar, or style, and no language identification.
- HTML support is a strict balanced-fragment profile; attribute values are not compared.
- Placeholder support covers brace, double-brace, and common printf forms. ICU plurals, `%@`, length modifiers such as `%ld`, and template helpers are not implemented.
- Number comparison uses a small set of locale profiles. Thousands separators without a declared locale are reported as unverified, and a negative number written directly after a letter, such as `UTC-5`, loses its sign.
- Translation-reuse detection needs a declared target locale.
- Files are loaded into memory, and reports are JSON or text only.
- No line-coverage figure and no linguistic-accuracy metric have been measured.

The complete list is in the README.

## Final submission checklist

1. Final repository link and final commit reference.
2. Test results: local run, plus `block7-test-output.txt`.
3. Generated evaluation report: `block6-report.json` and `block6-report.txt`.
4. Final README.
5. Technical summary: the section above.
