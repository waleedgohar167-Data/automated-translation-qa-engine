# Automated Translation QA Engine

A Python command-line tool that compares source and translated text and reports deterministic localization issues.

**Current checkpoint: Block 2 — core validation.** CSV/JSON loading and all six core rule categories are implemented within the documented syntax profiles. Advanced HTML/consistency checks and aggregate reporting remain scheduled for later blocks.

## Requirements and setup

- Python 3.11 or later.
- No third-party runtime/test packages, API keys, or model access are required.
- Run commands from the repository root. Use `python3` instead of `python` where appropriate.

```bash
git clone https://github.com/waleedgohar167-Data/automated-translation-qa-engine.git
cd automated-translation-qa-engine
python --version
```

## Run the application

Inspect the existing six-record input samples:

```bash
python -m translation_qa inspect samples/translations.csv
python -m translation_qa inspect samples/translations.json
```

Validate a four-record control fixture that should produce no findings:

```bash
python -m translation_qa check samples/block2_valid.json
```

Validate the eleven-record issue fixture and save its structured result:

```bash
python -m translation_qa check samples/block2_examples.json --output docs/checkpoints/block2-example-output.json
```

**The issue fixture intentionally exits with code `1` because critical findings were detected. That is an expected validation result, not an application crash.** It produces 10 issues: 6 critical, 3 warning, and 1 informational.

The same rules also accept CSV:

```bash
python -m translation_qa check samples/translations.csv
```

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Processing succeeded and no issue met the selected failure threshold. Warnings may still exist. |
| `1` | Processing succeeded and at least one issue met the failure threshold. |
| `2` | Input, output, or command usage failed. |

`--fail-on critical` is the default. Use `--fail-on warning` to also fail on warnings, `--fail-on informational` to fail on any finding, or `--fail-on none` to emit findings without a findings-based nonzero exit. None of these settings changes the detected issues. An exit code of zero does not certify translation quality.

## Input structure

CSV has a header row. JSON accepts a list of records or an object containing a `records` list. Files use UTF-8, with an optional UTF-8 byte-order mark.

```json
{
  "id": "example-001",
  "source": "Hello {name}",
  "translation": "Bonjour {name}",
  "source_locale": "en",
  "target_locale": "fr"
}
```

- `id`: non-blank string or integer. Invalid/missing IDs receive a critical finding and a fallback such as `row:1`; `record_index` remains available to locate the input.
- `source`: non-blank string.
- `translation`: string. An absent/null value is **missing**; a whitespace-only string is **empty**. Values are never converted to strings to hide a type error.
- `source_locale`, `target_locale`: optional locale strings used by the limited numeric profiles and same-locale copied-text exception. See [rule definitions](docs/validation-rules.md).

An empty CSV cell is an empty string. A row ending before the translation cell yields a missing value and a row-width diagnostic. JSON can represent an absent field or explicit `null` directly.

## Implemented rules

| Issue type | Default severity | Meaning |
| --- | --- | --- |
| `empty_translation` | Critical | Translation is empty or whitespace-only. |
| `missing_translation` | Critical | Translation field is absent or null. |
| `missing_placeholder` | Critical | Supported placeholder identities/occurrence counts are missing. |
| `additional_placeholder` | Critical | Supported placeholder identities/occurrence counts were added. |
| `numerical_inconsistency` | Warning | Parsed numeric values or occurrence counts differ; intentional changes need review. |
| `source_copied` | Warning | Source and translation match after NFC normalization and outer-whitespace trimming. |

Basic `invalid_record` and `invalid_field` guards prevent malformed records from stopping other records. `placeholder_syntax_unverified` and `number_format_unverified` are informational findings: they explicitly report comparisons that could not be completed safely. Critical severity is a configured rule policy, not proof of a game/runtime failure.

## Output structure

`check` prints JSON and can save the same result as a UTF-8 file with `--output`. Each issue contains `record_id`, `record_index`, `issue_type`, `description`, and `severity`.

```json
{
  "record_id": "missing-token",
  "record_index": 4,
  "issue_type": "missing_placeholder",
  "description": "Translation is missing placeholder occurrences: {name} (count 1).",
  "severity": "critical"
}
```

The surrounding output includes the engine version, input file/format, analyzed record count, core rule categories, issue count, and issue list. Grouped category/severity statistics are scheduled for Block 6.

## Architecture

```text
translation_qa/
    __init__.py       Package version
    __main__.py       Command entry point
    cli.py            Commands, JSON output, and exit policy
    loading.py        CSV/JSON adapters; raw values preserved
    models.py         Input records, severity, and issue schema
    tokens.py         Placeholder/number extraction and supported profiles
    validation.py    Record guards and the shared core rule engine
samples/              Synthetic control and issue fixtures
tests/                Input, rule, and CLI tests
docs/checkpoints/     Checkpoint notes and actual execution evidence
```

Both file formats use the same validation engine. Rules return issue objects and do not write files or modify inputs. The CLI handles output and failure thresholds. No source or translation text is executed.

## Tests

```bash
python -m unittest discover -s tests -v
```

Current checkpoint: **45 tests, 45 passed, 0 failed** in the preparation environment. Tests use explicit assertions for core rules, supported syntax, value/count preservation, CSV/JSON equivalence, malformed inputs, output structure, and CLI behavior. The suite is being expanded as later requirements are implemented; this is not a measured linguistic-accuracy result.

Python's standard-library `unittest` framework was chosen for automatic assertions, discovery, and reproducible execution without installing a testing dependency.

## Known limitations

- No semantic/grammar assessment, language identification, native-speaker review, or game execution is performed.
- HTML/tag validation, cross-record duplicate checks, placeholder format/order consistency, and full optional-field validation are pending Block 3.
- Placeholder checks compare supported identities and counts. They do not yet validate brace format modifiers or the order of unnumbered printf arguments. ICU plurals, attribute/index expressions, and other dialects require further work.
- Numeric checks use documented limited profiles. Scientific notation, leading-dot decimals, space-grouped numbers, and unsupported comma/grouping patterns produce review notices. Numbers in dates, ranges, identifiers, HTML attributes, and unit conversions are not understood semantically.
- Copied text can be valid for names, brands, or shared words; it is a warning. Zero-width/control-character validation is not yet provided.
- Loaders read files into memory. Invalid whole-file syntax is rejected; parseable malformed records are reported individually. Duplicate JSON object fields are rejected to avoid silent overwrites.
- Duplicate record IDs are not yet checked; use `record_index` to disambiguate findings.
- Passing a fixture or obtaining no findings does not demonstrate commercial readiness or whole-corpus translation accuracy.

## Evidence and development transparency

See [Block 1](docs/checkpoints/01-foundation.md), [Block 2](docs/checkpoints/02-core-validation.md), and [rule definitions](docs/validation-rules.md). Samples are synthetic. AI assisted development; results state the environment where they were actually generated. Remote commit references and reviewer access must be verified on GitHub.
