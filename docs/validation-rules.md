# Core rule contracts — Block 2

The engine reports violations of a defined deterministic profile. It does not infer translation quality, blame an AI model, or repair text automatically.

## Required fields and rule ordering

1. Preserve the 1-based input index and use the supplied non-blank string/integer ID where valid.
2. Report non-object records, row-width errors, and invalid mandatory fields without stopping neighboring records.
3. Treat absent/null translation as missing and whitespace-only text as empty. Do not add misleading placeholder/number errors when no translation exists.
4. Compare placeholders and numbers only when the relevant text and syntax can be interpreted.
5. Independently flag directly copied words as a review warning where applicable.

## Placeholders

Supported brace identities: `{name}`, `{player_name}`, and numeric fields such as `{0}`. `{{` and `}}` are escaped literal braces. A simple field with a non-nested modifier, such as `{amount:.2f}`, contributes its identity `{amount}`; the modifier is not interpreted or compared in this block.

Supported printf conversions: `%s`, `%d`, `%i`, `%f`, named forms such as `%(name)s`, and explicit positions such as `%1$s`. Simple width/precision flags can be consumed, such as `%03d` and `%.2f`. An argument must end before whitespace, punctuation, another placeholder, or end-of-text. `%%` is a literal percent escape. Adjacent alphanumeric suffixes and unrecognized conversions such as `%x` require review.

Compare **multisets**: preserve identity and occurrence count while allowing order changes. Missing and additional tokens generate separate critical findings. This block does not certify implicit printf argument ordering; that consistency check remains pending. Format modifiers are masked before numeric scanning so `{0}` and `%.2f` do not introduce spurious quantities.

Unsupported/unbalanced brace expressions, nested format fields, attribute/index expressions, and recognizable unsupported printf conversions produce `placeholder_syntax_unverified`. Placeholder and numeric comparisons for that record are skipped rather than guessed; missing/empty/field checks and copied-text review still apply where possible.

These conventions are a limited declared profile. They are not a complete implementation of every template, programming language, or RimWorld formatting grammar. Unsupported syntaxes that do not resemble the recognized brace/printf forms (for example application-specific square-bracket tokens) are outside this profile.

## Numbers

After placeholders are masked, compare multisets of numeric values using `Decimal`, not binary floating point. Unicode decimal digits are normalized to ASCII. Signs and occurrence counts are preserved, while order and insignificant trailing decimal zeros may differ.

| Declared numeric profile | Decimal separator | Group separator |
| --- | --- | --- |
| `en`, `bn` (including region suffixes) | `.` | `,`, with groups of three |
| `de`, `es` | `,` | `.`, with groups of three |
| `fr` | `,` | Not supported in this block |
| Omitted/other locale | `.` | Not inferred |
| Explicit Arabic separators in a token | Arabic decimal `٫` | Arabic grouping `٬`, with groups of three |

The table defines the tool's supported profile, not every valid formatting convention for a language. In particular, Indian digit grouping and space grouping are not supported. Locale fields are optional; if needed, declare them in each record rather than assuming a comma's meaning.

Unsupported grouping, scientific notation, leading-dot decimals, or unknown comma formatting produces `number_format_unverified` and skips the numeric comparison for the record. The engine does not interpret dates, ranges, fractions, units, identifiers, or HTML attributes semantically. Numeric differences are warnings because some changes are intentional or require context.

## Copied source

Compare case-sensitive text after Unicode NFC normalization and outer-whitespace trimming. Flag matching text containing literal alphabetic characters. Do not flag numeric-only or supported-placeholder-only strings. Skip this warning when both declared locale strings match after case and underscore/hyphen normalization.

This is a suspicion signal: brands, personal names, technical terms, and words shared between languages can be valid unchanged translations. Language identification and dictionaries are not implemented.

## Severity and process status

- **Critical:** missing/empty translations, supported placeholder differences, or invalid mandatory record structure. This is the engine's policy for review priority.
- **Warning:** copied words and numerical differences that require context.
- **Informational:** a specific comparison could not be completed under the supported profile.

Each issue contains the required identifier, category, description, and severity, plus a 1-based input index. A record may have multiple findings. Counts represent findings, not distinct bad translations.

No score, recall, precision, or translation-accuracy percentage is claimed. The CLI's failure threshold controls the exit code without suppressing issues.
