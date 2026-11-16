# Day 8 — Adversarial testing and evaluation

**Project:** Automated Translation QA Engine v0.5.0

**Prepared for:** Training & Engineering Team

**Candidate:** Waleed Khan

**Date:** 16 November 2026

**Evaluated base:** [`5f02ae8`](https://github.com/waleedgohar167-Data/automated-translation-qa-engine/tree/5f02ae8)

## 1. Engineering conclusion

**38 of 40 scenario expectations matched.** All 12 clean controls produced no findings, and all 18 defective/review-worthy scenarios produced exactly the required findings. The two mismatches are separate boundary gaps: an absent unsupported-syntax notice for `%@`, and CSV/JSON acceptance differences for long fields. Neither result is a measurement of translation quality.

The 20 ordinary CSV/JSON parity scenarios were consistent. The additional long-field boundary scenario was inconsistent. The engine was not changed, and expectations were not weakened after observing results.

**Highest-priority engineering finding:** the interrupted-report replacement failure from audit A02 remains the strongest focused improvement candidate. A supplementary controlled I/O probe reproduced loss of the previous complete report. It is kept outside the 40 input-case counts. Within the input dataset itself, B09 is the highest-impact observed ingestion gap.

## 2. Dataset and method

The independently constructed synthetic fixture contains **40 scenarios: 12 valid, 18 defective, and 10 boundary/malformed/unsupported**. Some scenarios contain multiple records to exercise duplicates and neighbor isolation; scenario counts are not record counts. The long-field scenario deterministically expands a 131,073-character field description, keeping the fixture readable.

The fixture includes named, repeated, template and printf placeholders; HTML balance and nesting; locale-specific numbers; Unicode; duplicate identifiers and translation reuse; missing/invalid fields; malformed CSV/JSON; and invalid UTF-8. It was authored for this assessment rather than copied from the existing test suite. Expectations follow the published repository contracts and the explicitly stated diagnostic/parity expectations below. This is not a blind holdout or independent third-party certification. AI assistance was used for preparation; the inputs, expectations, execution evidence and reasoning are inspectable.

- **Expectations frozen:** 16 November 2026, 01:27:55 PM PKT.
- **Fixture SHA-256:** `847e74634d6ad48c49b43c72ca8b6d4b51d5840c6500c1f5e61946275f221597`.
- **Executed:** 16 November 2026, 01:29:38 PM PKT to 16 November 2026, 01:29:41 PM PKT.
- **Environment:** Linux, Python 3.12.14; preparation environment, not the owner's Windows machine or remote CI.
- **Execution path:** real `python -m translation_qa check` subprocesses, with the default `critical` failure threshold.
- **Runs:** 61 CLI executions: 40 primary scenarios, 20 ordinary alternate-format runs and one long-field alternate-format run. These are not 61 independent examples.

Each supported expectation specifies the complete multiset of `(record_index, record_id, issue_type, severity)`. The runner also checks exit codes, nonempty descriptions, issue counts, record counts, structured error channels and absence of tracebacks. Human-readable descriptions are retained as evidence but are not matched verbatim. Duplicate findings are counted rather than collapsed into sets.

The fixture hash before execution matches the hash recorded in the evaluation results. No expectation was changed after the first run. Engine source hashes are recorded in the results; engine files, README and project configuration match the evaluated base commit.

### Interpreting the labels

“Valid” means a clean example under the declared mechanical profile. “Defective” includes policy violations and intentionally suspicious cases requiring review; a copied-text or reuse warning is not proof of linguistic error. Unsupported cases are separated from supported-rule detection results. For B08, the expectation is a warning-of-unsupported-content diagnostic, not support for validating `%@` arguments. For B09, the expectation tests the documented two-format ingestion contract and absence of a documented CSV-only length boundary; it does not establish that arbitrarily large fields should be allowed.

## 3. Results against the frozen expectations

| Measure | Calculation | Observed result | Interpretation |
| --- | --- | --- | --- |
| Clean scenarios without findings | 12 / 12 | 100% | No false alarms observed in these 12 controls. |
| Defective scenarios with exact required results | 18 / 18 | 100% | Correct issue identity, count, severity and exit behavior for this challenge set. |
| Required finding events recovered | 25 / 25 | 100% | Supported-profile event coverage on manually specified expectations. |
| Missing required events in defective scenarios | 0 / 25 | 0 | No supported-rule false negatives observed in this set. |
| Unexpected finding events in defective scenarios | 0 | 0 | No extra findings relative to these expectations. |
| Boundary scenarios matching expectations | 8 / 10 | 80% | B08 and B09 remain open. |
| All scenario expectations matched | 38 / 40 | 95% | Mixed contract-conformance result, not translation accuracy. |
| Ordinary CSV/JSON scenarios consistent | 20 / 20 | 100% | Equivalent supported inputs produced equivalent finding multisets and exit status. |
| Long-field CSV/JSON boundary consistent | 0 / 1 | 0% | Undocumented format boundary reproduced. |

The percentages are descriptive arithmetic on a small deliberately constructed set. No population false-positive rate, precision/recall for natural language, F1 score, real-client accuracy or commercial readiness claim follows from them. B08's missing diagnostic is excluded from supported-rule recall: `%@` itself is explicitly unsupported. B09 is an ingestion inconsistency, not a translation false negative.

### Complete expected-versus-observed matrix

`C` = critical, `W` = warning, `I` = informational. The matrix summarizes types/counts/severity; exact IDs and record indexes are checked and retained in the machine-readable results. Exit 0 may include warnings or informational findings because the engine's default threshold is critical.

#### Valid controls — 12

| Case | Scenario | Expected | Observed | Result |
| --- | --- | --- | --- | --- |
| V01 | Named arguments may move | No findings; exit 0 | No findings; exit 0 | Match |
| V02 | Template whitespace and repeated occurrences | No findings; exit 0 | No findings; exit 0 | Match |
| V03 | Explicit printf positions may move | No findings; exit 0 | No findings; exit 0 | Match |
| V04 | Declared German grouping and decimals | No findings; exit 0 | No findings; exit 0 | Match |
| V05 | Unicode decimal digits preserve value | No findings; exit 0 | No findings; exit 0 | Match |
| V06 | Balanced nested tags retain structure | No findings; exit 0 | No findings; exit 0 | Match |
| V07 | Attribute placeholders are retained | No findings; exit 0 | No findings; exit 0 | Match |
| V08 | Equivalent locale spelling and Unicode normalization | No findings; exit 0 | No findings; exit 0 | Match |
| V09 | Escaped percent remains literal | No findings; exit 0 | No findings; exit 0 | Match |
| V10 | Unicode minus and quantity reordering | No findings; exit 0 | No findings; exit 0 | Match |
| V11 | CSV quotes, commas and embedded newline | No findings; exit 0 | No findings; exit 0 | Match |
| V12 | Integer zero is a valid identifier | No findings; exit 0 | No findings; exit 0 | Match |

#### Defective / review-worthy scenarios — 18

| Case | Scenario | Expected | Observed | Result |
| --- | --- | --- | --- | --- |
| D01 | Whitespace-only translation | `empty_translation` (C); exit 1 | `empty_translation` (C); exit 1 | Match |
| D02 | Absent translation field | `missing_translation` (C); exit 1 | `missing_translation` (C); exit 1 | Match |
| D03 | One repeated placeholder occurrence disappears | `missing_placeholder` (C); exit 1 | `missing_placeholder` (C); exit 1 | Match |
| D04 | Unexpected named placeholder | `additional_placeholder` (C); exit 1 | `additional_placeholder` (C); exit 1 | Match |
| D05 | Quantity changed | `numerical_inconsistency` (W); exit 0 | `numerical_inconsistency` (W); exit 0 | Match |
| D06 | Repeated quantity occurrence disappears | `numerical_inconsistency` (W); exit 0 | `numerical_inconsistency` (W); exit 0 | Match |
| D07 | Copied source after Unicode normalization | `source_copied` (W); exit 0 | `source_copied` (W); exit 0 | Match |
| D08 | Missing closing tag | `html_tag_mismatch` (C); exit 1 | `html_tag_mismatch` (C); exit 1 | Match |
| D09 | Formatting tag removed | `missing_html_tag` (C); exit 1 | `missing_html_tag` (C); exit 1 | Match |
| D10 | Unexpected formatting tag | `unexpected_html_tag` (C); exit 1 | `unexpected_html_tag` (C); exit 1 | Match |
| D11 | Same tag counts, different nesting | `html_structure_changed` (W); exit 0 | `html_structure_changed` (W); exit 0 | Match |
| D12 | Implicit printf argument order changes | `placeholder_order_mismatch` (C); exit 1 | `placeholder_order_mismatch` (C); exit 1 | Match |
| D13 | Numeric format precision changes | `placeholder_format_mismatch` (W); exit 0 | `placeholder_format_mismatch` (W); exit 0 | Match |
| D14 | Both identifier and source are absent | `missing_field` ×2 (C); exit 1 | `missing_field` ×2 (C); exit 1 | Match |
| D15 | Duplicate identifiers on different rows | `duplicate_record_id` ×2 (C); exit 1 | `duplicate_record_id` ×2 (C); exit 1 | Match |
| D16 | Suspicious reuse across opposing actions | `suspicious_translation_reuse` ×2 (W); exit 0 | `suspicious_translation_reuse` ×2 (W); exit 0 | Match |
| D17 | Markup, placeholder identity and quantity changed | `additional_placeholder` (C); `missing_html_tag` (C); `missing_placeholder` (C); `numerical_inconsistency` (W); exit 1 | `additional_placeholder` (C); `missing_html_tag` (C); `missing_placeholder` (C); `numerical_inconsistency` (W); exit 1 | Match |
| D18 | Text values have invalid types | `invalid_field` ×2 (C); exit 1 | `invalid_field` ×2 (C); exit 1 | Match |

#### Boundary, malformed and unsupported scenarios — 10

| Case | Scenario | Expected | Observed | Result |
| --- | --- | --- | --- | --- |
| B01 | A non-object between usable neighbors | `invalid_record` (C); `missing_placeholder` (C); exit 1 | `invalid_record` (C); `missing_placeholder` (C); exit 1 | Match |
| B02 | Null target, Boolean ID and invalid locale | `invalid_field` ×2 (C); `missing_translation` (C); exit 1 | `invalid_field` ×2 (C); `missing_translation` (C); exit 1 | Match |
| B03 | Duplicate JSON property | `input_error`; exit 2 | `input_error`; exit 2 | Match |
| B04 | Unterminated CSV quoted field | `input_error`; exit 2 | `input_error`; exit 2 | Match |
| B05 | Invalid UTF-8 byte sequence | `input_error`; exit 2 | `input_error`; exit 2 | Match |
| B06 | ICU plural expression | `placeholder_syntax_unverified` (I); exit 0 | `placeholder_syntax_unverified` (I); exit 0 | Match |
| B07 | Ambiguous comma without locale metadata | `number_format_unverified` (I); exit 0 | `number_format_unverified` (I); exit 0 | Match |
| B08 | Unsupported object printf placeholder disappears | `placeholder_syntax_unverified` (I); exit 0 | No findings; exit 0 | Gap |
| B09 | Equivalent 131073-character fields across formats | No findings; exit 0 | JSON: no findings, exit 0. CSV: `input_error`, exit 2. | Gap |
| B10 | Script content is explicitly outside visible-text checks | `html_content_unverified` ×2 (I); exit 0 | `html_content_unverified` ×2 (I); exit 0 | Match |

## 4. CSV/JSON equivalence

The ordinary parity set is **V01, V02, V03, V04, V05, V06, V07, V08, V09, V10, V11, D01, D03, D04, D05, D06, D07, D09, D10, D15**. Each of its inputs contains all five known fields with string values, so serialization is lossless. The CSV writer quotes commas, quotes and embedded newlines; V11 explicitly exercises this. Each scenario runs separately in both formats to preserve its duplicate-analysis boundaries.

Parity compares issue identities, occurrence counts, severities, record indexes, record counts, error class and exit code. File names and format labels necessarily differ and are excluded from semantic comparison. Both runs must also match the independently specified expectation, so equal-but-wrong results would not count as a scenario match.

JSON-only missing/null/type-invalid cases are not converted into CSV: doing so would erase distinctions the engine is supposed to preserve. This is an intentional fidelity constraint, not an omitted parity failure. B09 is reported separately because it probes an exceptional size boundary rather than the ordinary profile.

## 5. What the two dataset gaps establish

### B08 / audit A05 — Unsupported-syntax notification gap

**Input:** `Hello %@` → `Bonjour`.

**Expected:** one informational `placeholder_syntax_unverified` notice, based on the README's broad promise that unsupported printf-like text is reported as unverified. No supported-token missing-placeholder finding is expected.

**Observed:** zero findings, exit 0. `_UNSUPPORTED_PRINTF` recognizes letter-based conversions but does not recognize `%@`. The README explicitly lists `%@` as unsupported, so absence of full validation is a documented limitation; the discrepancy concerns the promised diagnostic and the risk of interpreting silence as verification.

**Action:** narrow the documented diagnostic guarantee or add conservative recognition for this unsupported form. Do not claim that the engine can validate Apple/object-format arguments without implementing that grammar. This is a confirmed diagnostic/documentation gap, not newly discovered linguistic inaccuracy.

### B09 / audit A03 — Long-field format inconsistency

**Input:** the same ID, source, translation and locales; source and target are each 131,073 characters.

**Observed:** JSON loads successfully with no findings; CSV returns structured `input_error`, exit 2: `field larger than field limit (131072)`. The CLI handles the rejection cleanly, so this is not a crash or data-loss event.

**Cause:** CSV retains the interpreter's field limit while JSON has no equivalent application policy. An operator exporting the same logical record in another supported format receives different acceptance behavior.

**Action:** define an explicit shared field-size budget, document it, and test just below/at/above the boundary for both formats. Do not simply remove the CSV cap: the whole-file loading and deep-markup resource risks from A04 still apply. Whether to accept or reject fields this long is a product policy decision; the confirmed weakness is inconsistent, undocumented policy.

## 6. Highest-priority engineering finding and proposed next block

The supplemental reliability probe re-ran the existing audit script at commit `5f02ae8`. It deliberately interrupted a write after 24 characters in a temporary existing report. The real CLI returned `output_error` with exit 2 and preserved the input, but the previous report was lost and the remaining file was invalid JSON. This confirms **A02 under controlled I/O fault injection**; no real client incident or observed production frequency is claimed.

I recommend a focused **atomic report replacement** improvement for Block 3. Report preservation protects previously generated evidence, applies across the tool's workflows, and can be tested with clear criteria within the block. B09 needs a shared size policy first; B08 is a narrower diagnostic/wording gap. A01 remains important, but no natural input trigger for its injected cross-record exception was identified here. This ranking is based on impact and implementability, not the number of failing examples.

Proposed acceptance criteria, to finalize before implementation:

1. Successful writes still produce the expected UTF-8 JSON/text and preserve the existing exit-code behavior.
2. A partially failed write or failed replacement leaves any previous complete report intact; a failed first write leaves no partial final report.
3. Temporary files are removed after success and ordinary handled failures.
4. Existing direct-path, symbolic-link and hard-link protections continue to prevent input overwrite.
5. The original suite and new focused regression tests pass; encoding behavior remains supported.

A same-directory temporary file followed by replacement is a candidate design, not an implemented fix in this submission. Crash durability, unusual filesystem semantics and concurrent writers need explicit scope decisions; atomic replacement alone does not prove those properties.

## 7. Evidence quality and remaining limits

- The evaluator passed **five separate controls**, including deliberately incorrect expectations, wrong severity/exit code, an expected file rejection and invalid fixture counts. Mutations were made only to temporary copies; the frozen fixture is unchanged.
- These are **40 evaluation scenarios plus five evaluator controls**, reported separately from the existing **183-test baseline** recorded in Block 1. They are not presented as 228 passing engine unit tests. No engine fix or new engine regression test is included here.
- The set covers deterministic contracts, not meaning, fluency, culturally appropriate localization, browser rendering, complete HTML5 behavior or every placeholder dialect.
- A small hand-authored set cannot establish production false-positive rates. No real customer corpus, representative load benchmark, exhaustion test, external Autonomo integration or deployment was evaluated.
- Invalid-file examples are rejected as whole files; malformed individual-record isolation is separately demonstrated by B01.
- The scripted fault injections are outside the 40-case detection denominator. They are reliability evidence, not ordinary malformed translation inputs.
- Python 3.11/3.13 and remote CI evidence remain Block 4 work. Windows results should be captured separately by the owner.

## 8. Reproduction and evidence files

From the repository root, using Python 3.11 or later and the standard library:

```bash
python scripts/evaluate_day8.py --output docs/assessment/evidence/day8-local-evaluation-results.json
python scripts/check_day8_evaluator.py --output docs/assessment/evidence/day8-local-evaluator-self-check.json
python docs/assessment/evidence/day8-audit-probes.py --output docs/assessment/evidence/day8-local-reliability-recheck.json
```

At the unchanged evaluated engine version, the full evaluator exits **1** because B08 and B09 do not match expectations. This is an intentionally retained evaluation result. It must not be hidden by changing the expectations or forcing a zero exit code. Exit **0** means all selected expectations match; exit **2** indicates an evaluation setup error. The underlying engine's exit codes are checked separately.

To inspect one scenario:

```bash
python scripts/evaluate_day8.py --case B09 --output docs/assessment/evidence/day8-local-B09.json
```

The labeled fixture contains scenario definitions, malformed-byte examples and generation instructions. The evaluation runner materializes each input in a temporary directory and invokes the actual engine. It removes those temporary inputs after execution and retains their hashes, CLI output and results. No network, credentials or external services are required.

- [40-case fixture](../../tests/fixtures/day8_adversarial.json)
- [Evaluation runner](../../scripts/evaluate_day8.py)
- [Evaluator control script](../../scripts/check_day8_evaluator.py)
- [Frozen expectation record](evidence/day8-expectations-frozen.json)
- [Full results and raw CLI output](evidence/day8-evaluation-results.json)
- [Terminal summary](evidence/day8-evaluation-terminal.txt)
- [Evaluator control results](evidence/day8-evaluator-self-check.json)
- [Supplementary reliability recheck](evidence/day8-reliability-recheck.json)
- [Block 1 audit](day8-audit.md)

This submission completes the evaluation block. The two dataset gaps and the reliability finding remain open for a justified, scoped engineering improvement.
