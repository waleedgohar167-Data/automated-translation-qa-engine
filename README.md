# Automated Translation QA Engine

A Python command-line tool that compares source and translated text and reports deterministic localization issues.

**Current checkpoint: Block 5 — debugging.** CSV/JSON loading, all six core categories, HTML-fragment checks, placeholder consistency, field validation, and cross-record review rules are implemented within the documented profiles. The suite has 161 tests and all of them pass. The hard-link overwrite bug found in Block 4 and six further defects are fixed; see the [Block 5 checkpoint](docs/checkpoints/05-debugging.md). Aggregate reporting remains scheduled for Block 6.

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

Validate the six-record advanced control fixture in either format:

```bash
python -m translation_qa check samples/block3_valid.json
python -m translation_qa check samples/block3_valid.csv
```

Validate the seventeen-record advanced issue fixture and save its structured result:

```bash
python -m translation_qa check samples/block3_examples.json --output docs/checkpoints/block3-example-output.json
```

**The issue fixture intentionally exits with code `1` because critical findings were detected. That is an expected validation result, not an application crash.** It produces 15 issues across 11 categories: 10 critical, 3 warning, and 2 informational. The original Block 2 issue fixture still produces 10 findings.

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

CSV has a header row; header labels are trimmed and the documented field names are accepted in any letter case. JSON accepts a list of records or an object containing a `records` list. Files use UTF-8, with an optional UTF-8 byte-order mark.

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
- `source_locale`, `target_locale`: optional locale strings used by numeric profiles, copied-text exceptions, and cross-record grouping. Omitted/null/blank values mean unspecified; supplied values are checked against a simple locale syntax profile. This is not an IANA locale registry check. See [rule definitions](docs/validation-rules.md).

An empty CSV cell is an empty string. A row ending before the translation cell yields a missing value and a row-width diagnostic. JSON can represent an absent field or explicit `null` directly.

## Implemented rules

| Issue type | Default severity | Meaning |
| --- | --- | --- |
| `empty_translation` | Critical | Translation is empty or whitespace-only. |
| `missing_translation` | Critical | Translation field is absent or null. |
| `missing_placeholder` | Critical | Supported placeholder identities/occurrence counts are missing. |
| `additional_placeholder` | Critical | Supported placeholder identities/occurrence counts were added. |
| `numerical_inconsistency` | Warning | Parsed numeric values or occurrence counts differ; intentional changes need review. |
| `source_copied` | Warning | Visible source and translation match after Unicode and whitespace normalization. |
| `html_tag_mismatch` | Critical | A source or target fragment has mismatched, unclosed, or incomplete markup. |
| `missing_html_tag` / `unexpected_html_tag` | Critical | Tag names or occurrence counts were removed/added. |
| `html_structure_changed` | Warning | Balanced tag counts match but nesting differs. |
| `placeholder_format_mismatch` | Warning | Placeholder identities match but format/conversion/width modifiers differ. |
| `placeholder_order_mismatch` | Critical | Unnumbered printf argument types changed order. |
| `missing_field` / `invalid_field` / `invalid_record` | Critical | Required schema or input structure is invalid. |
| `duplicate_record_id` | Critical | Multiple records share the same public identifier. |
| `duplicate_translation` | Informational | A source/translation pair repeats within the same declared locale group. |
| `suspicious_translation_reuse` | Warning | Different sources share a translated phrase within a declared locale group. |

Malformed records do not stop valid neighbors. If a rule fails unexpectedly on one record, that record receives a critical `validation_error` finding and the remaining records are still checked. `placeholder_syntax_unverified`, `number_format_unverified`, and `html_content_unverified` explicitly identify comparisons or content outside the supported profile. Critical severity expresses the tool's preservation/schema policy, not proof of a game/runtime failure. A malformed source fragment is labeled as a source problem; tag changes are not inferred from it.

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

The surrounding output includes the engine version, input file/format, analyzed record count, supported issue categories, issue count, and issue list. Grouped category/severity statistics are scheduled for Block 6.

## Architecture

```text
translation_qa/
    __init__.py       Package version
    __main__.py       Command entry point
    cli.py            Commands, JSON output, and exit policy
    loading.py        CSV/JSON adapters; raw values preserved
    models.py         Input records, severity, and issue schema
    fields.py         Shared field, identifier, and locale helpers
    tokens.py         Placeholder/number extraction and format signatures
    markup.py         Raw delimiters, tag stack, and visible-text extraction
    duplicates.py     Locale-scoped cross-record review checks
    validation.py     Rule orchestration and deterministic issue ordering
samples/              Synthetic control and issue fixtures
tests/                Input, rule, and CLI tests
docs/checkpoints/     Checkpoint notes and actual execution evidence
```

Both file formats use the same validation engine. Rules return issue objects and do not write files or modify inputs. The CLI handles output and failure thresholds. No source or translation text is executed.

## Tests

```bash
python -m unittest discover -s tests -v
```

Current checkpoint: **161 tests: 161 passed, 0 failed, 0 errors, 0 skipped** in the Linux preparation environment. The 139 Block 4 tests are unchanged; 22 tests in `tests/test_regressions.py` cover the defects fixed in Block 5. Counts are discovered test methods; additional `subTest` examples are not counted separately. The same suite also runs under `python -m pytest` when pytest is installed.

The Block 4 failing test, `test_hardlink_output_cannot_overwrite_input`, now passes without having been modified. Bug **B4-001** (a report path that is a hard link to the input could overwrite that input) is fixed by comparing file identity before anything is written.

On Windows, symbolic-link tests may be skipped when the account cannot create them. Hard-link tests skip only if the filesystem cannot create a hard link. Record actual local results and any skips; the Linux result above is not a claim about another machine.

See the [requirements-to-tests map](docs/testing.md), [Block 5 checkpoint](docs/checkpoints/05-debugging.md), [test summary](docs/checkpoints/block5-test-summary.json), and [terminal output](docs/checkpoints/block5-test-output.txt). Tests verify explicit expectations for core/advanced rules, file formats, malformed inputs, CLI exits, serialized findings, non-mutation, and deterministic results. No line/branch coverage percentage or linguistic-accuracy metric has been measured.

Python's standard-library `unittest` framework was chosen for automatic assertions, discovery, and reproducible execution without installing a testing dependency.

## Known limitations

- No semantic/grammar assessment, language identification, native-speaker review, or game execution is performed.
- HTML uses a strict balanced-fragment profile. It is not a browser, full HTML5 validator, security sanitizer, or rendering test. Optional omitted end tags are not supported; attribute semantics/changes are not generally compared.
- Placeholder identities, counts, modifier strings, and implicit printf type order are compared. The engine does not evaluate every formatter grammar, infer the meaning of identically typed argument reordering, or implement ICU plurals and all template dialects. Percent-encoded URLs or template-like literal text may require review.
- Numeric checks use documented limited profiles. Scientific notation, leading-dot decimals, space-grouped numbers, and unsupported comma/grouping patterns produce review notices. Numbers in dates, ranges, identifiers, and unit conversions are not understood semantically. Numeric comparison uses visible text; attribute values are outside its scope.
- Copied text can be valid for names, brands, or shared words; it is a warning. Zero-width/control-character validation is not yet provided.
- Loaders read files into memory. Invalid whole-file syntax is rejected; parseable malformed records are reported individually. Duplicate JSON object fields are rejected to avoid silent overwrites.
- A hyphen directly after a letter or digit is read as a separator, so `1-5` and `Top-10` are not negative numbers. The trade-off is that `UTC-5` is read as 5.
- Double-brace placeholders are recognized for simple names and dotted paths such as `{{name}}` and `{{ user.name }}`. Block helpers and filters remain literal text.
- Cross-record translation checks require a valid declared target locale and compare only matching source/target locale groups. Short labels (fewer than four literal alphabetic characters), numeric-only values, and placeholder-only values are excluded. The heuristic can miss problems or flag valid reuse; findings require context.
- Record identifiers are compared by their public string representation; integer `1` and string `"1"` collide. The 1-based `record_index` disambiguates each occurrence.
- Passing a fixture or obtaining no findings does not demonstrate commercial readiness or whole-corpus translation accuracy.

## Evidence and development transparency

See [Block 1](docs/checkpoints/01-foundation.md), [Block 2](docs/checkpoints/02-core-validation.md), [Block 3](docs/checkpoints/03-advanced-validation.md), [Block 4](docs/checkpoints/04-automated-testing.md), [Block 5](docs/checkpoints/05-debugging.md), and [rule definitions](docs/validation-rules.md). Samples are synthetic. AI assisted development; results state the environment where they were actually generated. Remote commit references and reviewer access must be verified on GitHub.
