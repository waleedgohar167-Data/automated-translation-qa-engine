# Automated Translation QA Engine

A Python command-line tool that compares source and translated text and reports deterministic localization issues. It reads CSV or JSON, emits one structured finding per problem, and produces an aggregated report.

**Status: final delivery, engine version 0.5.0.** The suite has 183 automated tests and all of them pass. The work was built in checkpoints; notes and execution evidence for each one are in [docs/checkpoints](docs/checkpoints).

## Project purpose

Translated strings break in mechanical ways that are slow to find by eye: a dropped `{name}`, a changed number, a missing `</b>`, an empty cell, a source string pasted in untranslated. This engine finds the problems that can be decided from the text alone and reports each one with a record identifier, an issue type, a description, and a severity.

It does not judge meaning, grammar, or style. Where a comparison is outside the documented profile, it says so with an informational finding instead of guessing.

## Installation

Requirements: Python 3.11 or later. Nothing else is needed to run the tool or its tests: no third-party packages, API keys, credentials, or network access.

```bash
git clone https://github.com/waleedgohar167-Data/automated-translation-qa-engine.git
cd automated-translation-qa-engine
python --version
```

Use `python3` instead of `python` where your system requires it.

Optional: install the `translation-qa` command and pytest into a virtual environment.

```bash
python -m pip install -e ".[test]"
```

After that, `translation-qa` can be used in place of `python -m translation_qa`.

## Execution

Run commands from the repository root.

```bash
python -m translation_qa inspect samples/translations.csv
python -m translation_qa check samples/translations.csv
python -m translation_qa check samples/translations.json
python -m translation_qa report samples/translations.csv --report-format text
python -m translation_qa report samples/block3_examples.json --output reports/report.json
```

| Command | What it does |
| --- | --- |
| `inspect` | Loads the file and summarizes its records. No validation. |
| `check` | Runs every rule and prints the structured issue list as JSON. |
| `report` | Runs every rule and prints an aggregated report as JSON or plain text. |

| Option | Commands | Meaning |
| --- | --- | --- |
| `--format auto\|csv\|json` | all | Input format. `auto` (default) uses the file extension. |
| `--output PATH` | `check`, `report` | Also save the result to a file. The input file is never overwritten, including through a symbolic link or hard link. |
| `--fail-on critical\|warning\|informational\|none` | `check`, `report` | Lowest severity that produces exit code 1. Default `critical`. It never hides findings. |
| `--report-format json\|text` | `report` | Report layout. Default `json`. |
| `--version` | | Print the engine version. |

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Processing succeeded and no issue met the failure threshold. Warnings may still exist. |
| `1` | Processing succeeded and at least one issue met the failure threshold. |
| `2` | Input, output, or command usage failed. A JSON error is printed to stderr. |

**The issue samples exit with code `1` because critical findings were detected. That is the expected validation result, not a crash.** An exit code of zero does not certify translation quality.

### Sample datasets

| File | Records | Issues | Purpose |
| --- | ---: | ---: | --- |
| `samples/translations.csv`, `samples/translations.json` | 6 | 4 | The same data in both formats |
| `samples/block2_valid.json` | 4 | 0 | Core rules, clean control |
| `samples/block2_examples.json` | 11 | 10 | Core rules, issue examples |
| `samples/block3_valid.json`, `samples/block3_valid.csv` | 6 | 0 | Advanced rules, clean control |
| `samples/block3_examples.json` | 17 | 15 | Advanced rules, 11 issue categories |

All samples are synthetic.

## Input structure

CSV has a header row. Header labels are trimmed, and the documented field names are accepted in any letter case. JSON accepts a list of records or an object containing a `records` list. Files use UTF-8, with an optional byte-order mark.

```json
{
  "id": "example-001",
  "source": "Hello {name}",
  "translation": "Bonjour {name}",
  "source_locale": "en",
  "target_locale": "fr"
}
```

| Field | Required | Rules |
| --- | --- | --- |
| `id` | Yes | Non-blank string or integer. A missing or invalid value gets a critical finding and a fallback such as `row:1`. |
| `source` | Yes | Non-blank string. |
| `translation` | Yes | String. Absent or `null` is **missing**; whitespace-only is **empty**. Values are never converted to strings to hide a type error. |
| `source_locale`, `target_locale` | No | Locale strings such as `en` or `fr-FR`. They select the number format, exempt same-language copies, and scope duplicate detection. |

Other fields are allowed and ignored. An empty CSV cell is an empty string. A CSV row with too few or too many cells is reported and its texts are not compared, because the cell alignment is unreliable. Every finding also carries `record_index`, the 1-based position of the record in the file.

## Validation rules

| Issue type | Severity | Meaning |
| --- | --- | --- |
| `empty_translation` | Critical | Translation is empty or whitespace-only. |
| `missing_translation` | Critical | Translation field is absent or null. |
| `missing_placeholder` | Critical | A placeholder in the source is absent from the translation, or appears fewer times. |
| `additional_placeholder` | Critical | The translation contains a placeholder the source does not. |
| `placeholder_format_mismatch` | Warning | Placeholders match but a format, conversion, or width modifier differs. |
| `placeholder_order_mismatch` | Critical | Unnumbered printf argument types changed order. |
| `numerical_inconsistency` | Warning | Numeric values or their counts differ. |
| `source_copied` | Warning | Visible translation equals the source. |
| `html_tag_mismatch` | Critical | Source or translation has mismatched, unclosed, or incomplete markup. |
| `missing_html_tag`, `unexpected_html_tag` | Critical | Tag names or counts were removed or added. |
| `html_structure_changed` | Warning | Tag counts match but nesting differs. |
| `missing_field`, `invalid_field`, `invalid_record` | Critical | Required data is absent, has the wrong type, or the record is malformed. |
| `duplicate_record_id` | Critical | Several records share one identifier. |
| `duplicate_translation` | Informational | The same source and translation pair repeats within a locale group. |
| `suspicious_translation_reuse` | Warning | Different sources share one translation within a locale group. |
| `placeholder_syntax_unverified`, `number_format_unverified`, `html_content_unverified` | Informational | The content is outside the supported profile, so that comparison was skipped and needs manual review. |
| `validation_error` | Critical | A rule failed unexpectedly on this record. The other records were still checked. |

Supported placeholder styles: `{name}`, `{0}`, `{amount:.2f}`, `{{name}}`, `%s`, `%d`, `%i`, `%f`, `%(name)s`, and `%1$s`. Severity expresses review priority under this tool's policy, not proof of a runtime failure. The full contracts are in [docs/validation-rules.md](docs/validation-rules.md).

## Output structure

### `check`

Each issue contains the record identifier, issue type, description, and severity, plus the record's position in the file.

```json
{
  "record_id": "sample-004",
  "record_index": 4,
  "issue_type": "missing_placeholder",
  "description": "Translation is missing placeholder occurrences: {name} (count 1).",
  "severity": "critical"
}
```

The surrounding object holds `mode`, `engine_version`, `input_file`, `input_format`, `records_analyzed`, `rules`, `issue_count`, and `issues`.

### `report`

Abbreviated example from `samples/translations.csv`. The lists are shortened here, and `note` and `rules` are omitted.

```json
{
  "report": "translation_qa_report",
  "report_version": 1,
  "engine_version": "0.5.0",
  "generated_at": "2026-11-14T11:25:08Z",
  "input": {"file": "translations.csv", "format": "csv"},
  "summary": {
    "total_records": 6,
    "total_issues": 4,
    "records_with_issues": 4,
    "records_without_issues": 2,
    "records_with_issues_percent": 66.7,
    "average_issues_per_record": 0.67,
    "max_issues_on_one_record": 1,
    "distinct_issue_types": 4,
    "most_common_issue_type": "empty_translation",
    "highest_severity": "critical",
    "records_by_highest_severity": {"critical": 2, "warning": 2, "informational": 0, "none": 2}
  },
  "issues_by_severity": {
    "critical": {"count": 2, "record_ids": ["sample-003", "sample-004"]},
    "warning": {"count": 2, "record_ids": ["sample-005", "sample-006"]},
    "informational": {"count": 0, "record_ids": []}
  },
  "issues_by_category": {
    "empty_translation": {"count": 1, "severity": "critical", "record_ids": ["sample-003"]}
  },
  "affected_record_ids": ["sample-003", "sample-004", "sample-005", "sample-006"],
  "affected_records": [
    {"record_id": "sample-003", "record_index": 3, "issue_count": 1,
     "highest_severity": "critical", "issue_types": ["empty_translation"]}
  ],
  "issues": []
}
```

- `issues_by_category` is ordered by count, then by name. `issues_by_severity` always lists all three severities.
- `affected_records` has one entry per input row, because identifiers can be missing or duplicated. `affected_record_ids` lists each identifier once.
- `records_by_highest_severity` counts each record once under its worst finding, so its values add up to `total_records`.
- Counts are rule findings, not a translation accuracy score.

`--report-format text` prints the same data as a readable summary. A generated example is in [docs/checkpoints/block6-report.json](docs/checkpoints/block6-report.json) and [block6-report.txt](docs/checkpoints/block6-report.txt).

## Testing commands

```bash
python -m unittest discover -s tests -v
```

The tests use only the standard library. They also run under pytest:

```bash
python -m pip install -e ".[test]"
python -m pytest
```

Latest recorded result: **183 tests, 183 passed, 0 failed, 0 errors** (Linux, Python 3.13). On Windows the symbolic-link test is skipped when the account cannot create symbolic links, so `OK (skipped=1)` is expected there. Counts are test methods; `subTest` cases are not counted separately.

| Module | Tests | Focus |
| --- | ---: | --- |
| `test_loading.py` | 6 | CSV and JSON adapters, raw-value preservation |
| `test_input_boundaries.py` | 17 | Encodings, malformed files, paths |
| `test_validation.py` | 33 | Core rules: empty, missing, placeholders, numbers, copied text |
| `test_advanced_validation.py` | 44 | HTML, placeholder format and order, fields, edge cases |
| `test_duplicates.py` | 12 | Duplicate identifiers and translation reuse |
| `test_pipeline_contracts.py` | 8 | Combined errors, ordering, non-mutation, serialization |
| `test_cli.py` | 6 | Command handlers and exit codes |
| `test_cli_integration.py` | 13 | The real `python -m translation_qa` process and file safety |
| `test_regressions.py` | 22 | One class per bug fixed in Block 5 |
| `test_reporting.py` | 22 | Report aggregation, text layout, `report` command |

The mapping from assignment requirements to tests is in [docs/testing.md](docs/testing.md). No line-coverage percentage or linguistic-accuracy metric has been measured.

## Architecture summary

```text
translation_qa/
    __main__.py       Entry point for python -m translation_qa
    cli.py            Argument parsing, commands, safe file output, exit codes
    loading.py        CSV and JSON adapters; raw values preserved
    models.py         InputRecord, LoadedDataset, Severity, Issue
    fields.py         Identifier, locale, and text-normalization helpers
    tokens.py         Placeholder and number extraction
    markup.py         HTML tag stack and visible-text extraction
    duplicates.py     Cross-record checks, scoped by locale
    validation.py     Rule orchestration, one small function per rule family
    reporting.py      Aggregated report and plain-text layout
samples/              Synthetic control and issue datasets
tests/                unittest suite
docs/                 Rule contracts, test plan, checkpoint evidence
```

Data flows one way:

```text
file -> loading.load_dataset -> validation.validate_dataset -> reporting.build_report -> cli (print / save)
```

For each record, `validate_record` runs `_check_fields` first. Only if both texts are usable does it run `_check_markup`, `_check_placeholders`, `_check_numbers`, and `_check_copied`, always in that order. `cross_record_issues` then adds duplicate findings, and everything is sorted by input position.

Design principles:

- **One engine for both formats.** The loaders only adapt the file into records. Every rule sees the same structure.
- **Raw values are preserved.** Nothing is trimmed or converted, so a type error is reported instead of hidden.
- **Rules are pure.** They return `Issue` objects and never write files or change the input. The CLI owns all input and output.
- **Unverifiable is labelled, not guessed.** Unsupported syntax yields an informational finding and skips only the affected comparison.
- **One bad record cannot stop the run.** Malformed records produce findings, and an unexpected rule failure is isolated to its record.
- **Deterministic output.** The same input always produces the same findings in the same order.

To add a rule: write a `_check_...` function in `validation.py` that calls `add(issue_type, description, severity)`, call it from `_check_content`, add the issue type to one of the `*_RULES` tuples, and add tests.

## Known limitations

- No semantic, grammar, or style assessment, and no language identification.
- HTML uses a strict balanced-fragment profile. It is not a browser, a full HTML5 validator, or a security sanitizer. Optional end-tag omission is unsupported and attribute values are not compared.
- Placeholders: the styles listed above are compared. ICU plurals, `%@`, length modifiers such as `%ld`, and template helpers or filters such as `{{#if x}}` are not implemented. Unsupported printf-like text is reported as unverified.
- Numbers use limited locale profiles (`en`, `bn`, `de`, `es`, `fr`, and Arabic separators). Thousands separators without a declared locale, space grouping, and scientific notation are reported as unverified. Dates, ranges, and units are not understood semantically.
- A hyphen directly after a letter or digit is read as a separator, so `1-5` and `Top-10` are not negative numbers. The trade-off is that `UTC-5` is read as 5.
- Copied text can be valid for names, brands, and shared words, so it is a warning. The comparison is case-sensitive.
- Translation-reuse checks need a valid `target_locale` and ignore targets with fewer than four letters.
- Record identifiers are compared as text, so integer `1` and string `"1"` collide. `record_index` separates them.
- Files are loaded into memory. A file that is not valid CSV or JSON as a whole is rejected; records inside it are not recovered.
- Reports are JSON or plain text. A CSV export is not implemented.
- Passing the samples, or a run with no findings, does not demonstrate whole-corpus translation accuracy.

## Evidence and development transparency

Checkpoint notes: [Block 1](docs/checkpoints/01-foundation.md), [Block 2](docs/checkpoints/02-core-validation.md), [Block 3](docs/checkpoints/03-advanced-validation.md), [Block 4](docs/checkpoints/04-automated-testing.md), [Block 5](docs/checkpoints/05-debugging.md), [Block 6](docs/checkpoints/06-reporting.md), and [Block 7](docs/checkpoints/07-final-delivery.md).

AI tools assisted development. Results state the environment in which they were actually generated, and local results are reported separately.
