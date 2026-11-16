# Day 8 — Independent technical audit

**Project:** Automated Translation QA Engine v0.5.0  
**Prepared for:** Training & Engineering Team  
**Candidate:** Waleed Khan  
**Date:** 16 November 2026  
**Audited commit:** [`df4d0f5f1e944e42712faf26f41e5db7085a1741`](https://github.com/waleedgohar167-Data/automated-translation-qa-engine/tree/df4d0f5f1e944e42712faf26f41e5db7085a1741)

## 1. Audit conclusion

The existing **183-test baseline passes** in the preparation environment. The reviewed architecture separates loading, validation, reporting, and CLI operations, and the sampled report totals agree with the underlying findings. This supports the implemented deterministic behavior covered by those tests; it does not establish production readiness.

The audit identifies **six prioritized findings**. An exception can escape the cross-record phase under controlled fault injection, and an interrupted report replacement can destroy the previous report. A real long-field input also exposes different CSV and JSON acceptance boundaries. Resource growth, localization-profile limits, and missing automated compatibility evidence remain separate risks or gaps.

No engine code, existing test, validation threshold, or public API was changed for this audit. The handover was used for orientation; the baseline, code paths, and observations below were checked against the repository. AI-assisted analysis and execution were used, with reproduction material supplied for review.

## 2. Baseline and evidence

| Item | Verified result |
| --- | --- |
| Engine / repository | v0.5.0 / `df4d0f5` |
| Command | `python -m unittest discover -s tests -v` |
| Environment | Linux, Python 3.12.14; preparation environment |
| Execution time | 16 November 2026, 12:53:12–12:53:13 PM PKT |
| Discovered tests | 183 methods across 10 test modules |
| Outcome | **183 passed, 0 failed, 0 errors, 0 skipped; exit 0** |
| Reporting control | 17 records / 15 findings; category and severity counts both total 15; highest-severity record counts total 17 |
| Findings preservation | The report contains the same findings returned by validation |

The recorded run occurred after the scheduled **12:40 PM PKT** checkpoint. It must not be presented as an on-time checkpoint or as execution on the owner's Windows machine. This audit does not claim fresh Python 3.11, Python 3.13, pytest, or remote CI verification; those checks are assigned later in today's assessment.

Evidence files:

- [Original baseline terminal output](evidence/day8-baseline-unittest.txt)
- [Baseline environment and counts](evidence/day8-baseline-environment.json)
- [Reproducible audit probes](evidence/day8-audit-probes.py)
- [Recorded probe observations](evidence/day8-audit-probe-results.json)

Fault injection below means a dependency is deliberately made to fail to inspect error handling. It does **not** establish that ordinary customer data naturally triggers that exception or that a real disk-full incident occurred.

## 3. Architecture and behavior reviewed

| Layer | Current behavior | Audit implication |
| --- | --- | --- |
| Loading | CSV/JSON adapters preserve record values; CSV headers are normalized. Whole-file read/decode/parse errors become `InputError`. | Malformed-file handling is explicit, but format size boundaries differ. |
| Field and content validation | Structural checks run first; markup, placeholders, numbers, and copied text follow in a fixed order. | Invalid records generally avoid misleading comparison errors. |
| Error isolation | `_validate_isolated` converts single-record exceptions into critical diagnostics. | The subsequent cross-record pass sits outside that boundary. |
| Cross-record analysis | Duplicate IDs and eligible translation reuse are grouped, with locale boundaries. | Source/target text is parsed again; failures and resource cost need separate consideration. |
| Reporting | Pure aggregation keyed by record index; duplicate public IDs remain distinguishable. | Sample count invariants pass; a no-finding record is not proof of linguistic correctness. |
| CLI and output | Thresholds control exit status without suppressing findings; path and identity checks protect the input from aliases. | Normal output safety is tested, but replacement of an existing report is not atomic. |

The `rules` field is a catalog of supported rule categories, not evidence that every comparison was applicable or completed for every record. Unsupported content and absent locale context must be considered when interpreting reports.

## 4. Ranked findings

Severity means impact if triggered. Likelihood is a qualitative exposure judgment, not a measured production frequency: no real deployment or workload distribution is available. Priorities combine impact, exposure, evidence strength, and a practical mitigation path.

| Rank / ID | Finding and classification | Severity | Likelihood / exposure | Practical impact |
| --- | --- | --- | --- | --- |
| 1 / A02 | Existing report can be truncated on a failed replacement — **confirmed failure mode under injected I/O failure** | High | Conditional on a partial write, such as storage failure; frequency unknown | Loses the previous complete report and leaves invalid output. |
| 2 / A01 | Cross-record exceptions bypass isolation — **confirmed robustness defect under fault injection** | High | Conditional on an unexpected exception in that phase; no natural triggering input identified | No combined finding list is returned, including valid neighboring findings. |
| 3 / A04 | Deep markup has quadratic stored-path growth — **measured property; potential availability risk** | High for untrusted deep input | Low for ordinary short strings; plausible with unbounded imported input | Memory/time use can grow sharply; no exhaustion threshold is established. |
| 4 / A03 | CSV and JSON accept different long-field sizes — **confirmed boundary inconsistency** | Medium | Conditional on a field exceeding the active CSV parser limit | An equivalent CSV export fails while JSON is accepted. |
| 5 / A05 | Unsupported/context-dependent content can produce no findings — **existing documented limitations; diagnostic/documentation gap** | Medium | Depends on template dialect, numeric context, and locale metadata | Consumers may overinterpret an apparently clean result. |
| 6 / A06 | No tracked CI workflow or fresh target-version matrix — **confirmed automation/evidence gap** | Medium | Every change depends on manual verification | Regressions and version differences are not automatically demonstrated. |

### A02 — Interrupted replacement loses the previous report

**Evidence:** `A02_interrupted_report_write` in the probe results. A temporary existing report was replaced through the real `report` command while a patched write operation wrote the first 24 characters and then raised `OSError(ENOSPC)`. The CLI correctly returned exit 2 and `output_error`, printed no success report, and preserved the input. However, the previous report was gone and the remaining 24-character file was invalid JSON.

**Cause:** [cli.py:45](https://github.com/waleedgohar167-Data/automated-translation-qa-engine/blob/df4d0f5/translation_qa/cli.py#L45) writes directly to the final destination. Input-alias protection does not make a report replacement atomic.

**Coverage gap:** Existing tests protect the input from aliases and verify successful replacement of an unrelated report. They do not assert preservation of the previous report after a partially successful write.

**Recommendation:** Consider writing a complete temporary file in the destination directory, then replacing the final path only after success, with cleanup and retained input-identity checks. Define whether crash durability or concurrent writers are in scope before claiming either. Acceptance should cover a successful new file, successful replacement, failed write, failed replacement, alias rejection, and temporary-file cleanup.

### A01 — Isolation stops before cross-record analysis

**Evidence:** `A01_cross_record_isolation`. The normal control returns the later record's `empty_translation` finding. Under a deliberately injected `RuntimeError` in both markup-scanning call sites, the single-record guard returns `validation_error`, but the full dataset call raises `RuntimeError` instead of returning the collected findings. A declared target locale ensures the duplicate-analysis path actually runs.

**Cause:** [validation.py:194](https://github.com/waleedgohar167-Data/automated-translation-qa-engine/blob/df4d0f5/translation_qa/validation.py#L194) calls `cross_record_issues` outside the isolation boundary; [duplicates.py:30](https://github.com/waleedgohar167-Data/automated-translation-qa-engine/blob/df4d0f5/translation_qa/duplicates.py#L30) parses text again.

**Coverage gap:** `RecordFailureIsolationTests` patches the record-validation scanner and uses records without a target locale. The duplicate-analysis parser is therefore not exercised by that failure test. The existing test is valid but proves only part of the documented isolation guarantee.

**Recommendation:** Define isolation for cross-record candidate preparation, retain unaffected findings, and emit an explicit diagnostic for any skipped comparison. Avoid a broad catch that silently returns an empty issue list. This is a robustness defect demonstrated by fault injection; no ordinary source/translation pair has yet been shown to cause the injected exception naturally.

### A04 — Nesting depth amplifies memory requirements

**Evidence:** `A04_nesting_resource_growth`. Valid nested fragments at depths 100, 200, and 400 store respectively **5,050; 20,100; and 80,200 path elements**, without markup errors. These are bounded structural measurements, not performance benchmarks or exhaustion tests.

**Cause:** [markup.py:86](https://github.com/waleedgohar167-Data/automated-translation-qa-engine/blob/df4d0f5/translation_qa/markup.py#L86) copies the full nesting path for each opening tag: total path elements grow as `d(d + 1) / 2`. The loaders also materialize complete inputs, and eligible records are scanned again for reuse analysis. There are no application-level file, record, or nesting budgets.

**Recommendation:** Define finite input-size and nesting policies, reject oversized input explicitly, and test just below/at/above each boundary. Profile a representative bounded corpus before considering streaming or a different nesting representation. Do not claim a throughput capacity from the 183-test runtime.

### A03 — Long-field acceptance differs by input format

**Evidence:** `A03_csv_json_size_boundary`. In this interpreter the active `csv.field_size_limit()` is **131,072 characters**. Equivalent one-record files with 131,073-character source and translation fields produce JSON exit 0 with no findings, but CSV exit 2 with `input_error: field larger than field limit (131072)`.

**Cause:** [loading.py:52](https://github.com/waleedgohar167-Data/automated-translation-qa-engine/blob/df4d0f5/translation_qa/loading.py#L52) uses the interpreter's CSV field limit without a matching application policy for JSON.

**Interpretation:** This is an observed format-boundary inconsistency and an undocumented ingestion limit, not a linguistic false negative. Whether fields this long should be supported remains a product decision.

**Recommendation:** Choose and document a shared field-length policy across both adapters. Preserve clean error reporting and test boundary parity. Simply removing the CSV limit would increase the resource risk in A04.

### A05 — No findings can mean the content is outside the profile

**Evidence:** `A05_documented_profile_limits`:

- `Hello %@` → `Bonjour` produces no finding. `%@` is listed as unsupported in the README, but this case also receives no unverified-syntax notice.
- `UTC-5` → `UTC+5` produces no finding, consistent with the documented sign/separator trade-off.
- Two different sources sharing `Bonjour` produce no reuse findings without locale metadata; adding `target_locale: fr` produces two reuse warnings.

**Sources:** [tokens.py:16](https://github.com/waleedgohar167-Data/automated-translation-qa-engine/blob/df4d0f5/translation_qa/tokens.py#L16), [duplicates.py:27](https://github.com/waleedgohar167-Data/automated-translation-qa-engine/blob/df4d0f5/translation_qa/duplicates.py#L27), and [README limitations](https://github.com/waleedgohar167-Data/automated-translation-qa-engine/blob/df4d0f5/README.md#L262).

**Interpretation:** These are documented scope boundaries, not newly proven failures of supported linguistic validation. However, the README's broad statement that unsupported printf-like text is reported as unverified is too broad for `%@`. The reporting contract should make that exception clear.

**Recommendation:** Establish allowed template/locale profiles for any pilot, narrow the diagnostic wording, and treat unsupported cases separately in Block 2. Do not inflate defect counts by treating every unsupported syntax as a promised feature. A future syntax extension should be driven by the accepted input profile.

### A06 — Target-runtime and continuous-integration evidence is incomplete

**Evidence:** `A06_ci_evidence_gap`. `git ls-tree -r --name-only HEAD .github/workflows` returns no tracked workflow files at the audited commit. Today's reproduced baseline is Python 3.12.14 only. Historical handover claims about other runtimes are not a substitute for today's requested verification.

**Recommendation:** Complete the assigned Block 4 workflow for Python 3.11 and 3.13, unittest and pytest, and CLI exit-code smoke checks. Record local and remotely observed results separately. This is scheduled engineering work, not a claim that either target version currently fails.

## 5. Assessment of testing quality

The 183 tests are substantive: core rules, advanced markup checks, loader boundaries, duplicate heuristics, actual CLI subprocesses, prior regressions, and report aggregation are represented. The original failing hard-link regression now passes without removing its assertion. Existing report tests check count reconciliation, empty datasets, duplicate identifiers, and deterministic output when a fixed timestamp is supplied.

The audit nevertheless demonstrates gaps in abnormal I/O, cross-record failure isolation, size-policy parity, and bounded-resource behavior. A green baseline cannot establish those properties when the cases are absent. No line/branch coverage percentage, real-corpus false-positive rate, linguistic accuracy, or production load capacity has been measured in this block.

## 6. Proposed sequence for the next blocks

1. **Block 2:** Create the independently labeled 40-case evaluation and the required CSV/JSON parity subset. Define expectations before execution. Separate supported-profile defects, review heuristics, unsupported syntax, and malformed-file behavior. Include normal controls around any suspected weakness.
2. **Block 3:** Provisionally prioritize A02 for preservation of existing report evidence, or A01 if evaluation finds a natural triggering case or greater practical exposure. Final selection follows the evaluation and explicit acceptance criteria; neither fix is implemented in Block 1.
3. **Block 4:** Produce the requested CI/runtime evidence and fail visibly on unexpected results.
4. **Final decision:** Assess a bounded pilot only after the improvement and evaluation. Client input profiles, size limits, operator review, and residual risks must be stated; the baseline test count alone is insufficient.

The maximum expected file size, nesting depth, template dialect, and storage guarantees are **non-blocking unknowns for this audit**. They should be resolved or constrained before a pilot; no additional Autonomo platform access is needed to complete today's repository assessment.

## 7. Reproduction and local verification

From the repository root:

```bash
python -m unittest discover -s tests -v
python docs/assessment/evidence/day8-audit-probes.py --output docs/assessment/evidence/day8-local-audit-probes.json
```

The probe script writes test data only inside temporary directories. It does not modify engine code or client files. Its exit 0 means the observation script finished, **not** that every observed behavior is acceptable. The two failure-injection probes are explicitly marked in their JSON results.

The owner should record actual local test results before claiming Windows verification. If 183 tests run with one permission-related symbolic-link skip and no failures, that means **182 passed, 1 skipped**, not 183 passed. Preserve the preparation evidence separately from local output.
