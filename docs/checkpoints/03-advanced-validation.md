# Block 3 — Advanced translation validation

Base repository checkpoint: `e3670ce982e9dc7f49ffa0858769ebd1f5c27082` (submitted Block 2).

This update adds the advanced checks to the existing engine. The owner must apply, run, commit, and push it; no new remote commit reference is claimed in this preparation record.

## Complete implemented rule list

| Category | Severity | Behavior |
| --- | --- | --- |
| `empty_translation` | Critical | Empty or whitespace-only translation. |
| `missing_translation` | Critical | Absent or null translation. |
| `missing_placeholder` | Critical | Supported identities/counts removed. |
| `additional_placeholder` | Critical | Supported identities/counts added. |
| `numerical_inconsistency` | Warning | Visible-text numeric values/counts differ. |
| `source_copied` | Warning | Visible words match after normalization. |
| `html_tag_mismatch` | Critical | Malformed, crossed, incomplete, or unclosed source/target markup. |
| `missing_html_tag` | Critical | Tag names/counts were removed. |
| `unexpected_html_tag` | Critical | Tag names/counts were added. |
| `html_structure_changed` | Warning | Well-formed fragments have changed nesting. |
| `placeholder_format_mismatch` | Warning | Conversion/width/format modifiers changed. |
| `placeholder_order_mismatch` | Critical | Unnumbered printf type order changed. |
| `missing_field` | Critical | Required id/source is missing (translation has its dedicated rule). |
| `invalid_field` | Critical | Mandatory field type/value or supplied locale syntax is invalid. |
| `invalid_record` | Critical | Non-object record or malformed CSV row. |
| `duplicate_record_id` | Critical | Repeated public ID; every occurrence is identified by input index. |
| `duplicate_translation` | Informational | An eligible source/translation pair repeats within a locale group. |
| `suspicious_translation_reuse` | Warning | Different sources share a phrase within the same locale group. |
| `placeholder_syntax_unverified` | Informational | Placeholder syntax is outside the supported profile. |
| `number_format_unverified` | Informational | Numeric syntax is outside the supported profile. |
| `html_content_unverified` | Informational | Script/style content or declarations are outside the visible-text profile. |

Rule contracts and scope: `docs/validation-rules.md`.

## Actual execution evidence

Verification timestamp: 2026-11-14T12:46:10.089936+05:00. Commands were executed in the preparation environment; run them in VS Code before claiming execution there.

| Check | Result | Evidence |
| --- | --- | --- |
| Complete automated suite | **101 passed, 0 failed** | `block3-test-output.txt` |
| Advanced control JSON | 6 records, 0 issues; exit 0 | `block3-valid-terminal.txt` |
| Equivalent advanced control CSV | 6 records, 0 issues; exit 0 | `block3-csv-terminal.txt` |
| Advanced issue sample | 17 records, 15 findings, 11 categories; expected exit 1 | `block3-example-terminal.txt`, `block3-example-output.json` |
| Existing Block 2 issue sample | Still 11 records, 10 findings; expected exit 1 | `block3-block2-regression-terminal.txt` |

The advanced sample has **10 critical, 3 warning, and 2 informational** findings. These are rule findings, not measured translation errors or an accuracy percentage.

## Three examples to demonstrate

1. `missing-tag`: `<b>Save</b>` becomes `Enregistrer` — `missing_html_tag`.
2. `argument-order`: `%s has %d lives` becomes `%d vies pour %s` — `placeholder_order_mismatch`.
3. `duplicate-id`: two different records share an ID — `duplicate_record_id`, with separate `record_index` values.

The same dataset also demonstrates missing/invalid fields, malformed rows, modifier changes, repeated pairs, and suspicious phrase reuse. The final valid record after a malformed integer record is still processed.

Input: `samples/block3_examples.json`. Output: `docs/checkpoints/block3-example-output.json`.

## Bugs encountered and fixed

The first run executed **97 tests: 93 passed and 4 failed**. Its original output is preserved in `block3-tests-first-run.txt`.

- Encoded literal tag text such as `&lt;b&gt;` was incorrectly treated as malformed markup after entity decoding.
- An incomplete tag ending in `<b` was missed.
- An unterminated quoted attribute was missed.
- An unfinished HTML comment was missed.

The correction separates raw-input delimiter validation from decoded visible text. A quote-aware scan finds incomplete tags/comments; HTMLParser and an explicit stack check tag nesting. Encoded literals remain text. The failing expectations were preserved, and four additional regression/equivalence tests brought the suite to 101 passing tests.

**Unresolved test failures: 0.** Known profile limitations below remain explicit; passing tests do not certify every possible input.

## Technical decision changed during development

I initially used parser callbacks to decide whether suspicious tag-like text was malformed. The failing cases showed that tolerant parsing and decoded text were insufficient for that decision. The implementation now checks raw delimiters first, then uses parsed tags and a stack for structure, and visible text for numeric/copied-text checks. This also prevents HTML attribute numbers from becoming false quantity warnings.

One existing Block 2 test was updated for the new Block 3 requirement: changing `{amount:.2f}` to `{amount:.3f}` now produces a formatter-consistency warning while still producing no numeric-value warning. This is a documented expansion of behavior; the original numeric-protection requirement remains tested.

## Architecture changes

- `fields.py`: shared identifier, locale, and Unicode normalization helpers.
- `markup.py`: raw delimiter checks, tag nesting/counts, visible-text extraction.
- `duplicates.py`: locale-scoped reuse checks and duplicate IDs.
- `tokens.py`: preserves formatter signatures and implicit printf argument order.
- `validation.py`: coordinates rules and returns deterministic issues by record index.
- `loading.py`: converts oversized JSON integer errors into a clean input error.
- `cli.py`: exposes all current categories and version 0.3.0 using the existing command.

## Known limitations

- Strict balanced fragments are supported, not complete HTML5 recovery or optional omitted end tags. Attribute semantics/changes, rendering, and security sanitization are outside scope.
- Format modifiers are compared, not executed. ICU and all template dialects are not implemented; percent-encoded URLs/template-like literal text can require review.
- Identically typed unnamed printf arguments cannot be semantically distinguished.
- Reused-translation checks require a valid declared target locale and matching source/target locale groups. Targets with fewer than four literal alphabetic characters, numeric-only targets, and placeholder-only targets are excluded. Reuse can be valid and is never automatically declared a semantic defect.
- Unknown metadata fields are permitted. Locale syntax is checked under a simple profile, not against a language registry.
- Numeric formats remain intentionally limited. Locale-aware comparisons do not establish meaning, unit equivalence, or correct translation.
- Whole-file JSON/CSV syntax errors are rejected clearly; valid records inside an unparseable file cannot be recovered reliably by this loader.
- Grouped report statistics remain scheduled for Block 6. No linguistic accuracy or commercial-readiness claim is made.

## Submission checklist — 1:30 PM PKT

1. Actual pushed commit/checkpoint reference.
2. Complete implemented rules listed above.
3. Example input/output demonstrating at least three categories.
4. Known limitations above.
5. No remaining test failures; summarize the four fixed HTML edge cases.
6. Explain the raw-input/parser/visible-text separation decision.
