# Block 5 — Debugging checkpoint

**Base commit:** `ab15457` (Block 4). Engine version is now 0.4.0.

This update fixes the bug left open in Block 4, fixes six further defects found while reviewing each rule, refactors the validation and CLI modules, and adds 22 regression tests. No existing test was changed or removed.

## Results

| Measure | Block 4 | Block 5 |
| --- | ---: | ---: |
| Total tests | 139 | 161 |
| Passed | 138 | 161 |
| Failed | 1 | 0 |
| Errors | 0 | 0 |
| Pass rate | 99.3% | 100% |

Recorded in the preparation environment (Linux, Python 3.13.18) with `python -m unittest discover -s tests -v`. The same suite also passes under `python -m pytest`. The Block 4 run on the owner's Windows machine skipped the symbolic-link test because the account cannot create symbolic links, so one skip is expected there. Report the counts actually observed locally.

Evidence:

- `block5-tests-before-fixes.txt`: the new regression tests run against the unchanged Block 4 code.
- `block5-test-output.txt`: the full suite after the fixes.
- `block5-test-summary.json`: counts and environment.

## Debugging process

1. **Reproduce first.** Each suspected defect was reproduced with a minimal input, then written as a test in `tests/test_regressions.py`. Against the Block 4 code, 15 of the 22 new tests failed. unittest reports this as 16 failures and 1 error because one test has three failing sub-cases. The other 7 are guard tests that protect behaviour the fixes must not change.
2. **Fix one module at a time.** `cli.py`, then `tokens.py`, then `loading.py`, then the `validation.py` refactor.
3. **Re-run everything.** All 139 earlier tests still pass unchanged, and the findings for every file in `samples/` are identical to the Block 4 code.

A random run of 40,000 generated records through the engine in the preparation environment produced no crash. That script is not part of the repository.

## Bugs identified and fixed

| ID | Impact | Symptom | Root cause | Fix |
| --- | --- | --- | --- | --- |
| B4-001 | Data loss | `--output` pointing at a hard link of the input replaced the input with the report. | `cli.py` compared `Path.resolve()` results. Two hard-link names resolve to different paths but are one file. | `_aliases_input` also compares file identity with `Path.samefile` before anything is written. |
| B5-001 | False positive | `Levels 1-5` → `Niveaux 1 à 5` was reported as a numeric inconsistency because the source was read as 1 and -5. `Top-10` and `Pages 10-20` behaved the same way. | The number pattern accepted any `-` before digits as a minus sign. | A sign counts only when it does not directly follow a letter or digit. |
| B5-002 | Missed error | `Hello {{name}}!` → `Bonjour !` produced no finding. | `{{` and `}}` were always treated as escaped literal braces, so template placeholders in the i18next/Handlebars style were never compared. | `{{identifier}}` and `{{ dotted.path }}` are extracted as placeholder tokens. Other doubled braces remain literals. |
| B5-003 | False positive | A CSV header written as `id, source, translation` or `ID,Source,Translation` made every row report a missing source and translation. | Header labels were used verbatim as field names. | Header labels are trimmed and the five documented field names are accepted in any letter case. Labels that collide after cleaning are rejected. Cell values are untouched. |
| B5-004 | Failed run | An input containing a lone surrogate escape such as a truncated emoji (`"\ud83d"`) made `--output` fail with exit 2 and print no findings. | The report was saved with strict UTF-8 encoding, which cannot encode a lone surrogate. | The file is written with `errors="backslashreplace"`, which stores the character as the JSON escape it came from. |
| B5-005 | Unparseable error | Error JSON on stderr could become invalid JSON on a stream that is not UTF-8, such as a redirected Windows stream. | Errors were serialized with `ensure_ascii=False`; Python then rewrote characters outside the Basic Multilingual Plane as `\U0001f600`, which is not a JSON escape. | All error JSON is ASCII-only, like the normal output. |
| B5-006 | Missed warning | Copied text containing an unbalanced brace, such as `Press } to continue`, was not flagged as copied, although the rule contract says the copied-text review still applies. | A failed brace parse returned empty literal text, so the "contains words" test was false. | A failed parse returns the text it was given. |

**Remaining failures: none.**

## Most important bug: B4-001

It is the only defect that destroys user data. The CLI refused to write a report over its input by comparing the two resolved paths. That handles a repeated path, `..` segments, and symbolic links, because all of those resolve to the same final path. A hard link is different: it is a second directory entry for the same file, so both names are real paths and resolve to themselves. The comparison saw two different paths and allowed the write, which replaced the input.

The fix asks the operating system whether the two paths are the same file. `Path.samefile` compares the device and file identifiers from `os.stat`, which are equal for every name of one file. A destination that does not exist yet raises `FileNotFoundError` and is safe by definition. The Block 4 test `test_hardlink_output_cannot_overwrite_input` now passes without being modified, and an in-process test covers the same path.

## Error handling

- `write_report` is the single place that saves a file. Every filesystem failure becomes an `output_error` with exit code 2 and no traceback.
- `validate_dataset` validates each record inside an isolation boundary. If a rule raises unexpectedly, that record receives a critical `validation_error` finding that names the exception type, and every other record is still checked.

## Refactoring

- `validate_record` was one 100-line function. It is now `_check_fields`, `_check_markup`, `_check_placeholders`, `_check_numbers`, and `_check_copied`, called in a fixed order by `_check_content`. Issue order and wording are unchanged.
- `comparable_text` in `fields.py` replaces four copies of the same normalization expression.
- `cli.py` is split into the parser, one function per command, `write_report`, and `exit_code`.

## Technical decisions changed

- `{{identifier}}` is now a placeholder that must be preserved. It was previously an escaped literal. A translation that keeps it unchanged is unaffected under either reading.
- A hyphen directly after a letter or digit is a separator, not a sign. The trade-off is that `UTC-5` is read as 5.
- CSV header labels are cleaned. This applies to labels only, and not to JSON keys.
- `validation_error` was added to the published rule list.

## Known limitations added or kept

- Only simple names and dotted paths are recognized inside double braces. Block helpers and filters such as `{{#if x}}` or `{{ name | upper }}` remain literal text.
- A negative number written directly after a letter or digit, such as `UTC-5`, loses its sign.
- The file-identity check relies on the filesystem reporting file identifiers, which NTFS, ext4, and APFS do.
- All limitations listed in earlier checkpoints still apply.

## Submission checklist

1. Latest pushed commit reference.
2. Bugs identified and fixed: the table above.
3. Remaining failures: none.
4. Updated test results and pass rate from the local run.
5. Most important bug: B4-001, explained above.
