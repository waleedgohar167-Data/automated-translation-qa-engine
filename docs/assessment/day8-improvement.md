# Block 3 — Engineering Improvement

## Selected finding

**A02 — interrupted report replacement can destroy a previously complete report.**

The Block 2 adversarial evaluation retained A02 as the highest-priority focused improvement candidate after a controlled I/O fault-injection probe reproduced the failure. During an interrupted write to an existing report, the CLI returned `output_error` with exit code 2 and preserved the input, but the previous report was lost and the destination was left incomplete/invalid. This is a reliability defect because a report that was already complete can be destroyed by a failed replacement.

Block 2 explicitly ranked A02 above B08 and B09 because report preservation applies across the tool's workflows and has clear acceptance criteria that can be implemented and tested within the available block. The improvement is intentionally narrow: it does not attempt crash-durability guarantees, concurrent-writer coordination, or a general storage abstraction.

## Root cause

`write_report()` previously wrote directly to the final destination with `Path.write_text()`. A write failure after the destination had been truncated could therefore leave the old report unavailable and the new report incomplete.

The input-alias protection was correct, but it protected the input file rather than the integrity of an existing output report.

## Expected behavior

Report replacement should follow this sequence:

1. Validate the output is not an alias of the input.
2. Create a temporary file in the destination directory.
3. Write the complete report to the temporary file using the existing UTF-8 and `backslashreplace` behavior.
4. Close the temporary file.
5. Replace the destination with `os.replace()`.
6. Remove the temporary file on handled failures.

Because the temporary file is in the destination directory, the replacement remains on the same filesystem.

## Acceptance criteria

- Successful writes produce the same UTF-8 JSON/text output as before.
- A failed write does not destroy a previously complete report.
- A failed replacement does not destroy a previously complete report.
- A failed first write leaves no partial final report.
- Temporary files are removed after successful writes and handled failures.
- Existing direct-path, symbolic-link and hard-link input protections remain active.
- Existing encoding behavior, including `backslashreplace`, remains supported.
- Existing tests remain passing.
- New regression coverage contains at least six meaningful cases.

## Implementation

`translation_qa/cli.py` now writes the report to a same-directory temporary file and calls `os.replace()` only after the temporary write succeeds.

The implementation deliberately does not call `fsync()` or claim crash-durability. It guarantees protection against ordinary handled write/replacement failures covered by the regression tests, while filesystem crash semantics remain outside this block's scope.

## Regression coverage

`tests/test_atomic_report_write.py` covers:

1. New report creation.
2. Successful replacement of an existing report.
3. Failure while writing the temporary report.
4. Failure during final replacement.
5. Failure during the first report write.
6. Preservation of valid JSON after replacement failure.
7. Input-alias protection before any temporary write.
8. Preservation of the existing Unicode `backslashreplace` behavior.

## Validation plan

From the repository root on Windows PowerShell:

```powershell
python -m unittest discover -s tests
python -m pytest
```

The expected baseline is the existing 183 tests plus the 8 new regression tests, for **191 tests**, with zero failures.

The final local result must be recorded from the owner's terminal. This patch itself does not claim Windows execution or remote CI verification.

## Remaining risks

- A process or operating-system crash can still leave a temporary file behind.
- `os.replace()` does not by itself establish crash durability of the directory entry.
- Concurrent writers are not coordinated.
- Filesystem-specific semantics can differ.
- The report remains fully materialized in memory before writing.

These are intentionally not addressed by this focused Block 3 improvement.
