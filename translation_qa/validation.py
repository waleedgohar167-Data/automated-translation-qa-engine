"""Deterministic record and cross-record checks; no semantic quality scores.

``validate_record`` works in two stages. ``_check_fields`` reports structural
problems and decides whether the two texts can be compared at all.
``_check_content`` then runs the markup, placeholder, number, and copied-text
checks in a fixed order, so a record's findings always appear in the same
sequence. To add a rule, write a ``_check_...`` function that calls ``add``,
call it from ``_check_content``, and list its issue type in a ``*_RULES`` tuple.
"""

from collections import Counter
from typing import Any, Callable

from .duplicates import cross_record_issues
from .fields import comparable_text, normalized_locale, record_identifier, valid_identifier, valid_locale
from .markup import MarkupScan, compare_markup, scan_markup
from .models import InputRecord, Issue, LoadedDataset, Severity
from .tokens import PlaceholderScan, describe_counts, scan_numbers, scan_placeholders


CORE_RULES = (
    "empty_translation", "missing_translation", "missing_placeholder",
    "additional_placeholder", "numerical_inconsistency", "source_copied",
)
ADVANCED_RULES = (
    "html_tag_mismatch", "missing_html_tag", "unexpected_html_tag", "html_structure_changed",
    "html_content_unverified", "placeholder_format_mismatch", "placeholder_order_mismatch",
    "invalid_record", "missing_field", "invalid_field", "duplicate_record_id",
    "duplicate_translation", "suspicious_translation_reuse",
)
DIAGNOSTIC_RULES = ("placeholder_syntax_unverified", "number_format_unverified", "validation_error")
ALL_RULES = CORE_RULES + ADVANCED_RULES + DIAGNOSTIC_RULES

# add(issue_type, description, severity=Severity.CRITICAL)
AddIssue = Callable[..., None]


def _check_fields(record: InputRecord, add: AddIssue) -> tuple[str, str, bool] | None:
    """Report structural problems.

    Returns ``(source, translation, locales_valid)`` only when both texts are
    usable strings, so content checks never run on missing or misaligned data.
    """
    row = record.data
    if not isinstance(row, dict):
        add("invalid_record", "Record must be an object containing id, source, and translation fields.")
        return None
    for problem in record.input_problems:
        add("invalid_record", problem)
    if "id" not in row:
        add("missing_field", "Required field 'id' is absent; a row identifier was assigned.")
    elif not valid_identifier(row["id"]):
        add("invalid_field", "Field 'id' must be a non-blank string or an integer; a row identifier was assigned.")

    source = row.get("source")
    source_valid = isinstance(source, str) and bool(source.strip())
    if source is None:
        add("missing_field", "Required field 'source' is absent or null.")
    elif not source_valid:
        add("invalid_field", "Field 'source' must be a non-blank string.")
    locales_valid = True
    for name in ("source_locale", "target_locale"):
        if not valid_locale(row.get(name)):
            locales_valid = False
            add("invalid_field", f"Optional field '{name}' must be a locale string such as en or fr-FR, or be unspecified. Numeric comparison was skipped.")

    translation = row.get("translation")
    if translation is None:
        add("missing_translation", "Translation field is absent or null.")
        return None
    if not isinstance(translation, str):
        add("invalid_field", "Field 'translation' must be a string; its value was not coerced.")
        return None
    if not translation.strip():
        add("empty_translation", "Translation is empty or contains only whitespace.")
        return None
    # A malformed CSV row has unreliable cell alignment, so its texts are not compared.
    if not source_valid or record.input_problems:
        return None
    return source, translation, locales_valid


def _check_markup(source_markup: MarkupScan, target_markup: MarkupScan, add: AddIssue) -> bool:
    """Report tag findings; return True when both visible texts can be trusted."""
    for kind, description, severity in compare_markup(source_markup, target_markup):
        add(kind, description, Severity(severity))
    return not (source_markup.errors or target_markup.errors
                or source_markup.unverified or target_markup.unverified)


def _check_placeholders(source: str, translation: str, add: AddIssue) -> bool:
    """Compare placeholder identities, counts, modifiers, and implicit order.

    Raw text is scanned so placeholders inside attributes are included.
    Returns False when the syntax could not be verified.
    """
    source_scan, target_scan = scan_placeholders(source), scan_placeholders(translation)
    if source_scan.unverified or target_scan.unverified:
        add("placeholder_syntax_unverified",
            "A placeholder expression is unsupported or unbalanced. Placeholder and numeric comparisons were skipped for this record.",
            Severity.INFORMATIONAL)
        return False
    source_tokens, target_tokens = Counter(source_scan.tokens), Counter(target_scan.tokens)
    missing = source_tokens - target_tokens
    additional = target_tokens - source_tokens
    if missing:
        add("missing_placeholder", "Translation is missing placeholder occurrences: " + describe_counts(missing) + ".")
    if additional:
        add("additional_placeholder", "Translation contains unexpected placeholder occurrences: " + describe_counts(additional) + ".")
    if not missing and not additional:
        if Counter(source_scan.formats) != Counter(target_scan.formats):
            add("placeholder_format_mismatch", "Placeholder identities/counts match but conversion, width, or format modifiers differ; review the intended formatting.", Severity.WARNING)
        if source_scan.implicit_printf != target_scan.implicit_printf:
            add("placeholder_order_mismatch", "Unnumbered printf argument types changed order, which can change argument binding. Use matching order or supported explicit positions.")
    return True


def _check_numbers(row: dict[str, Any], source_visible: PlaceholderScan,
                   target_visible: PlaceholderScan, add: AddIssue) -> None:
    """Compare the numeric values left in visible text once placeholders are masked."""
    if source_visible.unverified or target_visible.unverified:
        add("number_format_unverified", "Decoded visible text contains unsupported placeholder syntax; numeric comparison was skipped.", Severity.INFORMATIONAL)
        return
    source_numbers = scan_numbers(source_visible.literal_text, normalized_locale(row.get("source_locale")))
    target_numbers = scan_numbers(target_visible.literal_text, normalized_locale(row.get("target_locale")))
    if source_numbers.unverified or target_numbers.unverified:
        add("number_format_unverified",
            "Numeric formatting is outside the supported profile. Numeric comparison was skipped; review the values manually.",
            Severity.INFORMATIONAL)
    elif Counter(source_numbers.values) != Counter(target_numbers.values):
        add("numerical_inconsistency",
            "Numeric values or occurrence counts differ. Source: ["
            + describe_counts(Counter(source_numbers.values)) + "]; translation: ["
            + describe_counts(Counter(target_numbers.values))
            + "]. Review whether the change is intentional.", Severity.WARNING)


def _check_copied(row: dict[str, Any], source_markup: MarkupScan, target_markup: MarkupScan,
                  source_visible: PlaceholderScan, add: AddIssue) -> None:
    """Flag visible text that was left identical to the source."""
    source_locale = normalized_locale(row.get("source_locale"))
    same_locale = source_locale is not None and source_locale == normalized_locale(row.get("target_locale"))
    has_words = any(character.isalpha() for character in source_visible.literal_text)
    if (has_words and not same_locale
            and comparable_text(source_markup.visible_text) == comparable_text(target_markup.visible_text)):
        add("source_copied", "Visible translation matches the source after Unicode and whitespace normalization. Names, brands, and shared words may be valid exceptions.",
            Severity.WARNING)


def _check_content(row: dict[str, Any], source: str, translation: str,
                   locales_valid: bool, add: AddIssue) -> None:
    source_markup, target_markup = scan_markup(source), scan_markup(translation)
    visible_comparable = _check_markup(source_markup, target_markup, add)
    placeholders_verified = _check_placeholders(source, translation, add)
    if not visible_comparable:
        return  # Malformed or unverified markup: do not guess at numbers or copied text.
    source_visible = scan_placeholders(source_markup.visible_text)
    target_visible = scan_placeholders(target_markup.visible_text)
    if placeholders_verified and locales_valid:
        _check_numbers(row, source_visible, target_visible, add)
    _check_copied(row, source_markup, target_markup, source_visible, add)


def validate_record(record: InputRecord) -> list[Issue]:
    record_id = record_identifier(record)
    issues: list[Issue] = []

    def add(kind: str, description: str, severity: Severity = Severity.CRITICAL) -> None:
        issues.append(Issue(record_id, record.index, kind, description, severity))

    texts = _check_fields(record, add)
    if texts is not None:
        source, translation, locales_valid = texts
        _check_content(record.data, source, translation, locales_valid, add)
    return issues


def _validate_isolated(record: InputRecord) -> list[Issue]:
    """Validate one record, turning an unexpected failure into a finding.

    The rules are written not to raise, but one surprising record must not
    discard the findings for every other record in the file.
    """
    try:
        return validate_record(record)
    except Exception as exc:  # deliberate isolation boundary; the failure stays visible
        return [Issue(record_identifier(record), record.index, "validation_error",
                      f"Validation could not be completed for this record ({type(exc).__name__}). "
                      "Review it manually; the other records were still checked.", Severity.CRITICAL)]


def validate_dataset(dataset: LoadedDataset) -> list[Issue]:
    issues = [issue for record in dataset.records for issue in _validate_isolated(record)]
    issues.extend(cross_record_issues(dataset))
    return sorted(issues, key=lambda issue: issue.record_index)
