# Validation rule contracts — Blocks 2 and 3

The engine reports violations of a defined deterministic profile. It does not infer translation quality, blame an AI model, or repair text automatically.

## Required fields and rule ordering

1. Preserve the 1-based input index and use the supplied non-blank string/integer ID where valid.
2. Report non-object records, row-width errors, missing/invalid mandatory fields, and invalid supplied locale values without stopping neighboring records. Skip comparisons for a malformed CSV row because cell alignment is unreliable.
3. Treat absent/null translation as missing and whitespace-only text as empty. Do not add misleading placeholder/number errors when no translation exists.
4. Compare placeholders and numbers only when the relevant text and syntax can be interpreted.
5. Independently flag directly copied visible words as a review warning where applicable.
6. Check duplicate IDs and eligible reused translations across records; preserve record_index and deterministic record order.

Missing id/source fields use `missing_field`; invalid values use `invalid_field`. Missing/null translation keeps its dedicated `missing_translation` category. Omitted/null/blank locale values are unspecified. Other locale values must match the documented simple syntax; malformed values are reported and numeric comparisons are skipped. Extra application metadata fields are permitted and ignored.

## Placeholders

Supported brace identities: `{name}`, `{player_name}`, and numeric fields such as `{0}`. `{{` and `}}` are escaped literal braces. A simple field with a non-nested modifier, such as `{amount:.2f}`, contributes its identity `{amount}`; the modifier is compared as a signature, without executing or certifying its formatter semantics.

Supported printf conversions: `%s`, `%d`, `%i`, `%f`, named forms such as `%(name)s`, and explicit positions such as `%1$s`. Simple width/precision flags can be consumed, such as `%03d` and `%.2f`. An argument must end before whitespace, punctuation, another placeholder, or end-of-text. `%%` is a literal percent escape. Adjacent alphanumeric suffixes and unrecognized conversions such as `%x` require review.

Compare **multisets**: preserve identity and occurrence count. Named brace/printf arguments and explicit printf positions may reorder. Missing/additional tokens generate separate critical findings. When identities/counts match, different modifier signatures generate `placeholder_format_mismatch` warnings. Unnumbered printf argument types must preserve order; a changed order generates critical `placeholder_order_mismatch`. Identically typed unnamed arguments cannot be semantically distinguished. Format modifiers are masked before numeric scanning so `{0}` and `%.2f` do not introduce spurious quantities.

Unsupported/unbalanced brace expressions, nested format fields, attribute/index expressions, mixed printf argument styles, and recognizable unsupported printf conversions produce `placeholder_syntax_unverified`. Placeholder and numeric comparisons for that record are skipped rather than guessed; missing/empty/field checks and copied-text review still apply where possible.

These conventions are a limited declared profile. They are not a complete implementation of every template, programming language, or RimWorld formatting grammar. Unsupported syntaxes that do not resemble the recognized brace/printf forms (for example application-specific square-bracket tokens) are outside this profile.

## Numbers

After supported markup is parsed and placeholders in visible text are masked, compare multisets of numeric values using `Decimal`, not binary floating point. Attribute values and comments are excluded. Malformed/unverified markup or invalid locale fields prevent numeric guesses. Unicode decimal digits are normalized to ASCII. Signs and occurrence counts are preserved, while order and insignificant trailing decimal zeros may differ.

| Declared numeric profile | Decimal separator | Group separator |
| --- | --- | --- |
| `en`, `bn` (including region suffixes) | `.` | `,`, with groups of three |
| `de`, `es` | `,` | `.`, with groups of three |
| `fr` | `,` | Not supported in this block |
| Omitted/other locale | `.` | Not inferred |
| Explicit Arabic separators in a token | Arabic decimal `٫` | Arabic grouping `٬`, with groups of three |

The table defines the tool's supported profile, not every valid formatting convention for a language. In particular, Indian digit grouping and space grouping are not supported. Locale fields are optional; if needed, declare them in each record rather than assuming a comma's meaning.

Unsupported grouping, scientific notation, leading-dot decimals, or unknown comma formatting produces `number_format_unverified` and skips the numeric comparison for the record. The engine does not interpret dates, ranges, fractions, units, or identifiers semantically, and does not compare non-placeholder attribute values. Numeric differences are warnings because some changes are intentional or require context.

## Copied source

Compare case-sensitive visible text after Unicode NFC and whitespace normalization. Flag matching text containing literal alphabetic characters. Do not flag numeric-only or supported-placeholder-only strings. Skip this warning when both declared locale strings match after case and underscore/hyphen normalization.

This is a suspicion signal: brands, personal names, technical terms, and words shared between languages can be valid unchanged translations. Language identification and dictionaries are not implemented.

## HTML fragments

Use raw-input delimiter checks plus HTMLParser callbacks and an explicit tag stack. Encoded literal tags such as `&lt;b&gt;` remain text. Source and translation must be independently well formed under the strict fragment profile before inferring missing or extra tags. Count start/self-closing tags; standard void tags such as `br` and `img` do not need end tags. Tag names are case-insensitive. Optional HTML5 end-tag omission is intentionally unsupported.

Missing/extra names or counts are critical under the preservation policy. Valid sibling fragments may reorder. Different nesting with matching counts produces a review warning. Source-side markup errors are labeled as source issues. Incomplete tags, quoted attributes, and comments are detected before entity decoding.

Script/style contents and declarations are explicitly unverified. These checks do not validate rendering, safety, attribute semantics, or the complete HTML5 grammar. Raw placeholder checks still include attribute values; visible-text number/copied-word checks exclude attributes and comments.

## Cross-record checks

Every occurrence of a duplicated valid public record ID receives `duplicate_record_id`. Numeric 1 and string `"1"` share the same public representation. Fallback IDs for malformed rows are not treated as supplied IDs; record_index always identifies the input location.

Translation reuse is only compared when the target locale is explicitly supplied and valid. Group by normalized source locale, target locale, and visible target text. Two different known source locales are not combined, and unknown target locales are not assigned a language. Normalize Unicode/whitespace; exclude malformed/unverified markup and short, numeric-only, or placeholder-only targets. The minimum is four literal alphabetic characters after supported placeholders are removed.

An identical repeated source/target pair is informational (`duplicate_translation`). Different sources mapped to the same target produce `suspicious_translation_reuse` warnings. Context may justify reuse. No embeddings, fuzzy semantic matching, or language identification are used.

## Severity and process status

- **Critical:** missing/empty translations, supported placeholder identity/count or implicit-order differences, malformed/missing/unexpected tags, duplicate IDs, or invalid record fields/structure. This is the engine's policy for review priority.
- **Warning:** copied words, numerical differences, formatter changes, nesting changes, and suspicious phrase reuse that require context.
- **Informational:** a specific comparison/content could not be assessed under the supported profile, or a source/translation pair repeats.

Each issue contains the required identifier, category, description, and severity, plus a 1-based input index. A record may have multiple findings. Counts represent findings, not distinct bad translations.

No score, recall, precision, or translation-accuracy percentage is claimed. The CLI's failure threshold controls the exit code without suppressing issues.
