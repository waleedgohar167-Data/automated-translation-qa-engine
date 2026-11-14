"""Core deterministic checks. Findings are not semantic quality scores."""

from collections import Counter
import unicodedata

from .models import InputRecord, Issue, LoadedDataset, Severity
from .tokens import describe_counts, scan_numbers, scan_placeholders


CORE_RULES = (
    "empty_translation", "missing_translation", "missing_placeholder",
    "additional_placeholder", "numerical_inconsistency", "source_copied",
)


def _locale(value: object) -> str | None:
    return value.lower().replace("_", "-") if isinstance(value, str) and value else None


def validate_record(record: InputRecord) -> list[Issue]:
    row = record.data
    identifier = row.get("id") if isinstance(row, dict) else None
    valid_id = ((isinstance(identifier, str) and bool(identifier.strip()))
                or (isinstance(identifier, int) and not isinstance(identifier, bool)))
    record_id = str(identifier) if valid_id else f"row:{record.index}"
    issues: list[Issue] = []

    def add(kind: str, description: str, severity: Severity = Severity.CRITICAL) -> None:
        issues.append(Issue(record_id, record.index, kind, description, severity))

    if not isinstance(row, dict):
        add("invalid_record", "Record must be an object containing id, source, and translation fields.")
        return issues
    for problem in record.input_problems:
        add("invalid_record", problem)
    if not valid_id:
        add("invalid_field", "Field 'id' must be a non-blank string or an integer; a row identifier was assigned.")

    source = row.get("source")
    source_valid = isinstance(source, str) and bool(source.strip())
    if not source_valid:
        add("invalid_field", "Field 'source' must be a non-blank string.")
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
    if not source_valid:
        return issues

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

        source_numbers = scan_numbers(source_scan.literal_text, _locale(row.get("source_locale")))
        target_numbers = scan_numbers(target_scan.literal_text, _locale(row.get("target_locale")))
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

    normalized_source = unicodedata.normalize("NFC", source).strip()
    normalized_target = unicodedata.normalize("NFC", translation).strip()
    same_locale = (_locale(row.get("source_locale")) is not None
                   and _locale(row.get("source_locale")) == _locale(row.get("target_locale")))
    has_words = any(c.isalpha() for c in source_scan.literal_text)
    if normalized_source == normalized_target and has_words and not same_locale:
        add("source_copied", "Translation matches the source after Unicode normalization and outer-whitespace trimming. Names, brands, and shared words may be valid exceptions.",
            Severity.WARNING)
    return issues


def validate_dataset(dataset: LoadedDataset) -> list[Issue]:
    return [issue for record in dataset.records for issue in validate_record(record)]
