# Automated Translation QA Engine

A Python command-line tool for inspecting source and translated text for common localization issues.

**Current checkpoint: Block 1 — input foundation.** CSV and JSON loading are implemented. Translation validation and issue reporting are planned for subsequent checkpoints; loading a file does not certify translation quality.

## Requirements

- Python 3.11 or later.
- No third-party packages, API keys, or model access are required for this checkpoint.

## Run locally

Open a terminal in the repository root:

```bash
python -m translation_qa inspect samples/translations.csv
python -m translation_qa inspect samples/translations.json
```

On systems where Python is named `python3`, replace `python` with `python3`.
Both sample files contain the same six synthetic records. The command prints a JSON loading summary; it does not yet run translation checks.

## Input contract

CSV uses a header row. JSON accepts either a list of records or an object containing a `records` list. Text files use UTF-8; an optional UTF-8 byte-order mark is supported.

```json
{
  "id": "example-001",
  "source": "Hello {name}",
  "translation": "Bonjour {name}",
  "source_locale": "en",
  "target_locale": "fr"
}
```

The intended record fields are `id`, `source`, and `translation`. Locale fields are optional. The loader preserves missing, null, and incorrectly typed values so later validation can report them without silently changing the data. A blank translation is distinct from an absent translation field.

Unreadable files, invalid UTF-8, malformed JSON/CSV, and unsupported top-level JSON structures produce a clear error and exit code `2`. Individual malformed records are retained for later field validation. Successful loading exits with `0`.

## Project structure

```text
translation_qa/
    __init__.py       Package version
    __main__.py       Command entry point
    cli.py            Command parsing and terminal output
    loading.py        CSV and JSON input adapters
    models.py         Shared input data structures
samples/              Equivalent synthetic CSV and JSON datasets
tests/                Automated loading tests
docs/checkpoints/     Checkpoint notes and recorded verification output
```

## Tests

```bash
python -m unittest discover -s tests -v
```

The foundation uses Python's standard-library `unittest` framework. Subsequent blocks will extend this suite to the required validation and regression scenarios.

## Engineering decisions

- Keep file loading separate from validation, so both formats feed the same future rules.
- Preserve input values instead of guessing how malformed data should be repaired.
- Use a command-line interface and the standard library for reproducible setup without credentials or services.
- Use synthetic examples: these are test fixtures, not a measured translation-quality dataset.

## Current limitations

- This checkpoint loads data only. Empty/missing translation checks, placeholder and number checks, HTML rules, duplicate detection, and issue reports are not implemented yet.
- CSV and JSON are read into memory; this is not a streaming loader.
- A file that cannot be parsed is rejected as a whole. Parseable records are preserved for row-level checks.
- This project will provide deterministic checks, not a guarantee of semantic translation quality, game compatibility, or commercial readiness.

## Development transparency

This project is being developed with AI assistance. Checkpoint notes distinguish implemented behavior, verification actually run, and pending work. Repository access and remote commits must be confirmed on the hosting service; this README does not claim that access is enabled.
