# Block 6 — Reporting engine

**Base:** Block 5 (engine 0.4.0). Engine version is now 0.5.0.

## Work completed

- `translation_qa/reporting.py`: `build_report` aggregates the findings into one structured dictionary, and `render_text` lays the same data out for a terminal.
- A `report` command in the CLI. The existing `check` and `inspect` commands and their output are unchanged.
- `tests/test_reporting.py`: 22 tests for the aggregation, the text layout, and the command.

## Run it

```bash
python -m translation_qa report samples/block3_examples.json --output docs/checkpoints/block6-report.json
python -m translation_qa report samples/translations.csv --report-format text
```

`--report-format` is `json` (default) or `text`. `--output` saves the chosen format to a file as well as printing it. `--format` and `--fail-on` behave exactly as they do for `check`, so exit code 1 means findings at or above the threshold were detected, not that the command failed.

## Report structure

| Requirement | Where it is in the report |
| --- | --- |
| Total records analyzed | `summary.total_records` |
| Total issues detected | `summary.total_issues` |
| Issues by category | `issues_by_category`: one entry per issue type with `count`, `severity`, and `record_ids`. Largest count first, then by name. |
| Issues by severity | `issues_by_severity`: `critical`, `warning`, and `informational` are always present, each with `count` and `record_ids`. |
| Affected record identifiers | `affected_record_ids` (unique identifiers in input order) and `affected_records` (one entry per input row with `record_id`, `record_index`, `issue_count`, `highest_severity`, and `issue_types`). |
| Summary statistics | The rest of `summary`: records with and without issues, the percentage of records with issues, average issues per record, the largest number of issues on one record, the number of distinct issue types, the most common issue type, the highest severity, and `records_by_highest_severity`. |

The report also carries `report`, `report_version`, `engine_version`, `generated_at` (UTC), `input` (file name and format), `rules` (every rule that was evaluated), a `note`, and the full `issues` list in the same shape that `check` prints.

`records_by_highest_severity` counts each record once under its worst finding, with `none` for clean records, so its four values always add up to `total_records`.

## Sample dataset and generated report

Dataset: `samples/block3_examples.json`, the 17-record issue fixture from Block 3.

| Measure | Value |
| --- | ---: |
| Records analyzed | 17 |
| Total issues | 15 |
| Records with issues | 15 (88.2%) |
| Records without issues | 2 |
| Critical / warning / informational | 10 / 3 / 2 |
| Distinct issue types | 11 |

Evidence, recorded in the preparation environment (Linux, Python 3.13.18):

- `block6-report.json`: the generated JSON report.
- `block6-report.txt`: the same report in the text layout.
- `block6-terminal.txt`: the commands and their terminal output, including the CSV sample and a clean dataset.
- `block6-test-output.txt`: the full suite, **183 tests, 183 passed**.

## Design decisions

- **Aggregation is pure.** `build_report` does no file or console work, so it is tested directly with in-memory datasets. The CLI owns printing and saving.
- **Records are grouped by input index.** Identifiers can be missing or duplicated, so the row number is the only reliable key. `affected_record_ids` gives the public identifiers, and `affected_records` gives every affected row.
- **Stable shape and order.** All three severities are always present and categories have a fixed ordering rule, so reports can be compared between runs. `generated_at` is the only value that changes, and `build_report` accepts a fixed value for reproducible output.
- **The same safety as `check`.** Saving goes through `write_report`, so a report can never overwrite its input, including through a hard link.
- **Console safety.** JSON is printed as ASCII. The text layout escapes any character the console cannot encode instead of raising an error. Saved files are UTF-8.
- **No quality score.** The numbers are counts of rule findings. The report states this in `note` and does not present a translation accuracy figure.

## Known limitations

- The report is built in memory, like the rest of the engine.
- JSON and plain text are supported. A CSV export is not implemented.
- `record_ids` lists are not truncated, so they grow with the number of findings.

## Submission checklist

1. Latest pushed commit reference.
2. Generated report: `block6-report.json` and `block6-report.txt`.
3. Sample dataset used: `samples/block3_examples.json`.
4. Terminal output showing successful execution: `block6-terminal.txt`, plus a local run.
5. Reporting structure: the table above.
