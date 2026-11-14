# Block 4 — Automated testing checkpoint

**Base commit:** `1dc755db76a498f8931beb5b40018cbf851a5153` (Block 3).

This update adds tests and documentation. Application code and version remain unchanged at 0.3.0. The owner must apply the update, run the tests locally, and push the checkpoint before claiming a new remote commit.

## Work completed

- Re-ran the pushed Block 3 baseline: all 101 existing tests passed.
- Added 38 assertion-based tests: 17 file-boundary tests, 13 subprocess CLI tests, and 8 pipeline contract tests.
- Mapped every required test category to concrete test methods in `docs/testing.md`.
- Preserved the failing regression and original execution evidence; no earlier tests or application code were changed to influence the result.

## Actual preparation results

| Measure | Result |
| --- | ---: |
| Total discovered tests | 139 |
| Passed | 138 |
| Failed | 1 |
| Errors | 0 |
| Skipped | 0 |
| Process exit code | 1 |

These are unittest test-method counts, not linguistic quality metrics. The run used Python 3.12.14 on Linux. Environment details and the PKT recording timestamp are in `block4-test-summary.json`. Local Windows results may include filesystem-permission skips and must be reported as actually observed.

Evidence:

- `block4-test-output.txt`: original full test execution output.
- `block4-test-summary.json`: recorded counts, environment, and failed-test identifier.
- `block4-hardlink-reproduction.json`: separate minimal reproduction using disposable files.

## Bug discovered: B4-001 — output hard link can overwrite input

**Status:** Open for the scheduled Block 5 debugging work.

**Failing test:** `test_cli_integration.CliIntegrationTests.test_hardlink_output_cannot_overwrite_input`.

**Impact:** Input data can be replaced by the generated report if the report destination is an existing hard link to that input. A hard link is a second filename for the same underlying file. This is an input-preservation defect, not a translation-rule failure.

**Expected:** Reject the aliased destination with `output_error`, exit 2, and preserve input bytes.

**Observed:** The CLI returned exit 0 and replaced the temporary input contents. A separate reproduction confirmed both paths referred to the same file and that input bytes changed from 53 to 794 bytes. Only disposable temporary files were used; no repository sample or user file was modified.

**Diagnosis:** `cli.py` compares `Path.resolve()` results. That catches spelling aliases and symbolic links, but different hard-link names resolve to different paths while referring to one underlying file. The subsequent write replaces the input through its second name.

**Interim usage:** Write reports to a new, separate filename. Do not use an existing filesystem alias of an input as the report destination.

**Planned Block 5 fix:** Add an existing-file identity check before writing, keep the current resolved-path guard, and report filesystem-check errors cleanly. Keep the regression unchanged; re-run it and then the full suite. Review neighboring output-error paths for reproducible issues without manufacturing failures.

Safe isolated reproduction:

```bash
python -m unittest discover -s tests -p test_cli_integration.py -k hardlink -v
```

There is one unresolved failing test in this checkpoint. All 101 original tests still pass. Unsupported formatting and other existing scope limitations remain documented in the README and rule contracts.

## Submission checklist — 2:50 PM PKT

1. Repository link and actual pushed Block 4 commit reference.
2. Test suite under `tests/` and requirements map in `docs/testing.md`.
3. Actual local total, passing, failing, error, and skipped counts.
4. Bug B4-001 and its current status; do not describe the suite as fully passing.
5. Terminal output/screenshot of the local test execution.

No new remote commit or local Windows execution is asserted by this preparation document. The scheduled Block 5 will address the reproduced bug and preserve the test/fix history in separate commits.
