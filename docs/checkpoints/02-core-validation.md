# Block 2 — Core validation engine

Base repository checkpoint: `bc60c630400497d5df98f8dddc121a665bc536b1`.

This checkpoint adds the six required core validation categories, a structured issue model, the `check` CLI command, synthetic examples, and focused tests. A new remote commit reference must be recorded after the repository owner applies and pushes these changes; no remote push is claimed here.

## Completed rules

| Rule | Default severity | Example |
| --- | --- | --- |
| Empty translation | Critical | Translation is `""` or whitespace-only. |
| Missing translation | Critical | Translation field is absent or null. |
| Missing placeholder | Critical | Source has `{name}` but the translation does not. |
| Additional placeholder | Critical | Translation adds `{name}` when the source has none. |
| Numerical inconsistency | Warning | Source has 3 lives; translation has 2. |
| Directly copied source | Warning | Both texts contain `Settings` for different/unspecified locales. |

All issue objects include `record_id`, `issue_type`, `description`, and `severity`, plus a 1-based `record_index`. Basic malformed-record guards are included so invalid records do not prevent later records from being checked.

## Actual verification

- Full suite: **45 tests passed, 0 failed**.
- Four-record control fixture: **0 issues**, exit code **0**.
- Eleven-record issue fixture: **10 issues** (6 critical, 3 warning, 1 informational), expected exit code **1**.
- Existing six-record CSV fixture: **4 issues**, expected exit code **1**.
- A test verifies that the equivalent CSV/JSON fixtures produce identical issue objects.

Execution timestamp: 2026-11-14T11:49:48.675008+05:00. These results were generated in the preparation environment. Run the same commands in the owner's VS Code terminal before claiming execution there.

Evidence files:
- `block2-test-output.txt`
- `block2-example-terminal.txt`
- `block2-example-output.json`
- `block2-valid-terminal.txt`
- `block2-csv-terminal.txt`

Example input: `samples/block2_examples.json`. Control input: `samples/block2_valid.json`.

## Bugs encountered and fixed during this block

The first run executed 44 tests: 41 passed and 3 failed. Its unmodified output is retained in `block2-tests-first-run.txt`.

| Reproduced problem | Correction |
| --- | --- |
| Leading-dot `.5` was incorrectly extracted as integer 5. | Identify this unsupported notation and emit a numeric-format review notice. |
| A dot-formatted number was accepted under the limited French decimal-comma profile. | Require the integer part to match the selected numeric profile; otherwise mark the comparison unverified. |
| Unsupported printf `%x` was silently ignored. | Recognize unsupported printf-style expressions and explicitly report the comparison as unverified. |

The failing expectations were retained. After the fixes, all 44 tests passed. One additional CSV/JSON equivalence test brought the final suite to 45 passing tests. No known test failures remain at this checkpoint.

## Decisions to explain

- **One engine for both formats:** loaders preserve values and feed the same rules.
- **Count tokens rather than using sets:** losing one of two repeated placeholders is a meaningful difference; changing word order is not automatically an error.
- **Mask placeholders before checking numbers:** placeholder indices and formatting precision are not translated quantities.
- **Use Decimal and limited declared numeric profiles:** avoid binary rounding artifacts and unsupported punctuation guesses.
- **Warnings for copied words and numeric changes:** these can be valid in context and need review.
- **Explicit notices for unsupported syntax:** inability to validate is not equivalent to a clean result.
- **Tests during development:** focused tests are added with features; the later testing block will expand advanced-rule and edge-case coverage.

## Incomplete rules and limitations

All six Block 2 categories work within the documented profiles. HTML/tag checks, placeholder format/order consistency, duplicate/suspicious cross-record translations, and complete optional-field validation remain scheduled for Block 3. Grouped report statistics remain scheduled for Block 6.

The tool does not assess meaning, fluency, game behavior, or all formatting dialects. Unsupported numeric/placeholder profiles are detailed in `docs/validation-rules.md`. No linguistic accuracy metrics are claimed.

## Blockers

No local implementation blocker was encountered. The owner must apply the update, execute it in VS Code, and push the checkpoint to GitHub. Repository credentials were not available in the preparation environment.

## Submission checklist (12:30 PM PKT)

1. Actual pushed commit reference.
2. List of the six completed rules above.
3. Example input `samples/block2_examples.json`.
4. Generated output `docs/checkpoints/block2-example-output.json`.
5. Known scope limitations and later-block rules.
6. The three bugs encountered and their fixes, summarized above.
