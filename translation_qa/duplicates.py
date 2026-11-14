"""Conservative cross-record checks with explicit locale boundaries."""

from collections import defaultdict

from .fields import normalized_locale, normalized_text, record_identifier, valid_identifier, valid_locale
from .markup import scan_markup
from .models import Issue, LoadedDataset, Severity
from .tokens import scan_placeholders


def cross_record_issues(dataset: LoadedDataset) -> list[Issue]:
    identifiers: dict[str, list] = defaultdict(list)
    translations: dict[tuple, list] = defaultdict(list)
    for record in dataset.records:
        row = record.data
        if not isinstance(row, dict):
            continue
        if valid_identifier(row.get("id")):
            identifiers[record_identifier(record)].append(record)
        if record.input_problems:
            continue
        source, target = row.get("source"), row.get("translation")
        if not isinstance(source, str) or not source.strip() or not isinstance(target, str) or not target.strip():
            continue
        if not valid_locale(row.get("source_locale")) or not valid_locale(row.get("target_locale")):
            continue
        target_locale = normalized_locale(row.get("target_locale"))
        if target_locale is None:
            continue
        source_scan, target_scan = scan_markup(source), scan_markup(target)
        if source_scan.errors or target_scan.errors or source_scan.unverified or target_scan.unverified:
            continue
        target_tokens = scan_placeholders(target_scan.visible_text)
        if target_tokens.unverified or sum(c.isalpha() for c in target_tokens.literal_text) < 4:
            continue
        normalized_target = " ".join(normalized_text(target_scan.visible_text).split())
        normalized_source = " ".join(normalized_text(source_scan.visible_text).split())
        key = (normalized_locale(row.get("source_locale")), target_locale, normalized_target)
        translations[key].append((record, normalized_source))

    issues: list[Issue] = []
    for record_id, records in identifiers.items():
        if len(records) > 1:
            for record in records:
                issues.append(Issue(record_id, record.index, "duplicate_record_id",
                                    f"Identifier is shared by {len(records)} input records; use record_index to locate each occurrence.",
                                    Severity.CRITICAL))
    for (_, target_locale, _), members in translations.items():
        if len(members) < 2:
            continue
        distinct_sources = {source for _, source in members}
        suspicious = len(distinct_sources) > 1
        kind = "suspicious_translation_reuse" if suspicious else "duplicate_translation"
        description = (
            f"The same visible translation is used for {len(distinct_sources)} distinct source texts in target locale '{target_locale}'. Review context; this may be valid."
            if suspicious else
            f"The same source/translation pair is repeated in {len(members)} records for target locale '{target_locale}'. This can be intentional."
        )
        for record, _ in members:
            issues.append(Issue(record_identifier(record), record.index, kind, description,
                                Severity.WARNING if suspicious else Severity.INFORMATIONAL))
    return issues
