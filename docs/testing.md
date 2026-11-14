# Automated test plan — Blocks 4 and 5

## Purpose and approach

Check the declared behavior using explicit expected results. Exercise both the reusable validation functions and the real `python -m translation_qa` process. Temporary files isolate input/output tests. No model access, network calls, third-party test packages, or real client data are needed.

The engine already had 101 tests at Block 3. Block 5 adds 22 regression tests for the defects it fixed. Block 4 adds 38 tests for meaningful gaps; it does not count `subTest` examples as extra test methods, change earlier expectations, or add assertions just to increase the total. Python's standard-library `unittest` meets the assignment's automated-testing requirement without changing frameworks.

## Run the complete suite

From the repository root:

```bash
python -m unittest discover -s tests -v
```

Save your actual Windows terminal evidence with PowerShell:

```powershell
python -m unittest discover -s tests -v 2>&1 | Tee-Object -FilePath docs/checkpoints/block5-local-test-output.txt
$LASTEXITCODE
```

Block 4 ended with one known failing regression, B4-001. Block 5 fixed the defect without changing that test, so the whole suite is expected to pass. A test exit code of 1 is a real test failure, not the expected issue-detection exit of an application fixture. Keep those two meanings separate.

To isolate the discovered bug safely:

```bash
python -m unittest discover -s tests -p test_cli_integration.py -k hardlink -v
```

All file-alias tests create their own temporary input and output files. If the environment cannot create symbolic links or hard links, the corresponding test reports a skip with the reason. Windows accounts commonly lack symbolic-link permission; no elevated privileges are required for the rest of the suite. An unsupported filesystem check is a skip, not a pass.

## Test inventory

| Module | Tests | Focus |
| --- | ---: | --- |
| `test_loading.py` | 6 | Existing CSV/JSON adapters and raw-value preservation |
| `test_validation.py` | 33 | Core validation, numbers, placeholders, and severity |
| `test_advanced_validation.py` | 44 | HTML fragments, placeholder format/order, fields, and edge cases |
| `test_duplicates.py` | 12 | Locale-scoped reuse and duplicate identifiers |
| `test_cli.py` | 6 | Existing command handlers and basic output protection |
| `test_input_boundaries.py` | 17 | New real-file encoding, syntax, schema-container, and path tests |
| `test_cli_integration.py` | 13 | New subprocess command, exit policy, output, and file-alias tests |
| `test_pipeline_contracts.py` | 8 | New combined-rule, non-mutation, ordering, and serialization tests |
| `test_regressions.py` | 22 | Block 5 regression and guard tests for B4-001 and B5-001 to B5-006, plus record-failure isolation |
| **Total** | **161** | Discovered test methods |

## Assignment requirements mapped to assertions

Names below are actual test methods. This is a behavioral coverage map, not a measured statement/branch coverage percentage.

| Required category | Test examples | Expected behavior |
| --- | --- | --- |
| Correct translations | `test_correct_translation_has_no_findings`, `test_balanced_matching_html` | Synthetic valid controls produce no findings. |
| Empty translations | `test_blank_text_is_empty_translation`, `test_critical_issue_exits_one_and_writes_output` | Empty/whitespace text is critical; CLI emits a report and exit 1. |
| Missing translations | `test_missing_field_is_missing_translation`, `test_null_is_missing_translation`, `test_absent_translation_does_not_generate_comparison_noise` | Missing/null target is reported without misleading comparison errors. |
| Missing placeholders | `test_missing_placeholder_is_critical`, `test_repeated_placeholder_counts_are_preserved` | Identity and occurrence-count loss is detected. |
| Extra placeholders | `test_additional_placeholder_is_critical`, `test_placeholder_index_is_not_a_quantity` | Added identities are critical and are not treated as numeric quantities. |
| Incorrect numbers | `test_number_difference_is_warning`, `test_negative_number_is_different_from_positive`, `test_declared_locale_supports_decimal_comma` | Values/signs/counts differ only when supported formats justify comparison. |
| HTML problems | `test_crossed_nesting_is_invalid`, `test_missing_html_tag`, `test_unexpected_html_tag`, `test_encoded_tag_text_is_literal_text` | Broken/missing/added markup is detected; escaped text remains literal. |
| Missing fields | `test_missing_id_is_distinct_from_invalid_id`, `test_missing_and_null_source_are_reported` | Missing and invalid mandatory fields have explicit structured findings. |
| Malformed inputs | `test_noncollection_json_payloads_are_rejected`, `test_unterminated_csv_quote_is_a_clean_input_error`, `test_multiple_malformed_record_types_do_not_drop_later_errors` | Unparseable files fail clearly; parseable invalid records do not stop later records. |
| Untranslated text | `test_copied_words_are_warning`, `test_copied_words_use_unicode_normalization`, `test_warning_remains_visible_with_default_success_exit` | Copied words remain review warnings, including at CLI success threshold. |
| Multiple errors | `test_multiple_independent_errors_are_retained`, `test_multiple_markup_placeholder_and_number_errors_are_retained` | Independent findings across rule families are retained. |
| Edge cases | `test_json_utf8_bom_is_accepted`, `test_quoted_csv_commas_quotes_and_newlines_are_preserved`, `test_symlink_output_cannot_overwrite_input`, `test_hardlink_output_cannot_overwrite_input` | Encoding/quoting is preserved and output must not destroy its input through aliases. |

## Additional contracts

- The real module entry point returns documented process exit codes and parseable JSON.
- `--fail-on none` does not hide findings or suppress input errors.
- Output-file and stdout results agree after JSON parsing.
- Rule catalogs remain consistent for clean and failing inputs.
- Validation does not mutate input values or nested metadata.
- Repeated runs yield the same structured findings in input order.
- Real fixture findings contain valid identifiers, indices, categories, descriptions, and severities.

## Results and limits

The Block 5 preparation run recorded **161 tests, 161 passed, 0 failed, 0 errors, 0 skipped**. See `checkpoints/block5-test-output.txt` and `checkpoints/block5-test-summary.json`. The Block 4 run recorded 139 tests with one failure, B4-001, documented in `checkpoints/04-automated-testing.md`; its fix is described in `checkpoints/05-debugging.md`.

There is no translation accuracy benchmark, native-speaker evaluation, measured performance benchmark, browser rendering test, or exhaustive Unicode/formatter coverage. These tests verify the declared deterministic profile. A passing test is evidence for its specific asserted behavior only.
