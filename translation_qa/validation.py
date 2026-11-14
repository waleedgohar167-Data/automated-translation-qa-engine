"""Deterministic record and cross-record checks; no semantic quality scores."""

from collections import Counter
from .duplicates import cross_record_issues
from .fields import normalized_locale, normalized_text, record_identifier, valid_identifier, valid_locale
from .markup import compare_markup, scan_markup
from .models import InputRecord, Issue, LoadedDataset, Severity
from .tokens import describe_counts, scan_numbers, scan_placeholders


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
ALL_RULES = CORE_RULES + ADVANCED_RULES + ("placeholder_syntax_unverified", "number_format_unverified")


def validate_record(record: InputRecord) -> list[Issue]:
    row = record.data
    record_id = record_identifier(record)
    issues: list[Issue] = []

    def add(kind: str, description: str, severity: Severity = Severity.CRITICAL) -> None:
        issues.append(Issue(record_id, record.index, kind, description, severity))

    if not isinstance(row, dict):
        add("invalid_record", "Record must be an object containing id, source, and translation fields.")
        return issues
    for problem in record.input_problems:
        add("invalid_record", problem)
    if "id" not in row:
        add("missing_field", "Required field 'id' is absent; a row identifier was assigned.")
    elif not valid_identifier(row["id"]):
        add("invalid_field", "Field 'id' must be a non-blank string or an integer; a row identifier was assigned.")

    source = row.get("source")
    source_valid = isinstance(source, str) and bool(source.strip())
    if "source" not in row or source is None:
        add("missing_field", "Required field 'source' is absent or null.")
    elif not source_valid:
        add("invalid_field", "Field 'source' must be a non-blank string.")
    locales_valid = True
    for name in ("source_locale", "target_locale"):
        if not valid_locale(row.get(name)):
            locales_valid = False
            add("invalid_field", f"Optional field '{name}' must be a locale string such as en or fr-FR, or be unspecified. Numeric comparison was skipped.")
    if "translation" not in row or row["translation"] is None:
        add("missing_translation", "Translation field is absent or null.")
        return issues
    translation = row["translation"]
    if not isinstance(translation, str):
        add("invalid_field", "Field 'translation' must be a string; its value was not coerced.")
        return issues
    if not translation.strip():
        add("empty_translation", "Translation is empty or contains only whitespace.")
        return issues
    if not source_valid or record.input_problems:
        return issues

    source_markup, target_markup = scan_markup(source), scan_markup(translation)
    for kind, description, severity in compare_markup(source_markup, target_markup):
        add(kind, description, Severity(severity))
    visible_comparable = not (source_markup.errors or target_markup.errors
                              or source_markup.unverified or target_markup.unverified)
    source_scan = scan_placeholders(source)
    target_scan = scan_placeholders(translation)
    if source_scan.unverified or target_scan.unverified:
        add("placeholder_syntax_unverified",
            "A placeholder expression is unsupported or unbalanced. Placeholder and numeric comparisons were skipped for this record.",
            Severity.INFORMATIONAL)
    else:
        source_tokens = Counter(source_scan.tokens)
        target_tokens = Counter(target_scan.tokens)
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

        if visible_comparable and locales_valid:
            source_visible = scan_placeholders(source_markup.visible_text)
            target_visible = scan_placeholders(target_markup.visible_text)
            if source_visible.unverified or target_visible.unverified:
                add("number_format_unverified", "Decoded visible text contains unsupported placeholder syntax; numeric comparison was skipped.", Severity.INFORMATIONAL)
            else:
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

    same_locale = (normalized_locale(row.get("source_locale")) is not None
                   and normalized_locale(row.get("source_locale")) == normalized_locale(row.get("target_locale")))
    if visible_comparable:
        normalized_source = " ".join(normalized_text(source_markup.visible_text).split())
        normalized_target = " ".join(normalized_text(target_markup.visible_text).split())
        source_visible = scan_placeholders(source_markup.visible_text)
        has_words = any(c.isalpha() for c in source_visible.literal_text)
        if normalized_source == normalized_target and has_words and not same_locale:
            add("source_copied", "Visible translation matches the source after Unicode and whitespace normalization. Names, brands, and shared words may be valid exceptions.",
                Severity.WARNING)
    return issues


def validate_dataset(dataset: LoadedDataset) -> list[Issue]:
    issues = [issue for record in dataset.records for issue in validate_record(record)]
    issues.extend(cross_record_issues(dataset))
    return sorted(issues, key=lambda issue: issue.record_index)
