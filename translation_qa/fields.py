"""Small shared schema/normalization helpers; no value coercion."""

import re
import unicodedata

from .models import InputRecord


_LOCALE = re.compile(r"[A-Za-z]{2,8}(?:[-_][A-Za-z0-9]{1,8})*\Z")


def valid_identifier(value: object) -> bool:
    return ((isinstance(value, str) and bool(value.strip()))
            or (isinstance(value, int) and not isinstance(value, bool)))


def record_identifier(record: InputRecord) -> str:
    value = record.data.get("id") if isinstance(record.data, dict) else None
    return str(value) if valid_identifier(value) else f"row:{record.index}"


def valid_locale(value: object) -> bool:
    """Absent/null/blank locale is unspecified; supplied values use a simple syntax profile."""
    return (value is None or (isinstance(value, str)
            and (not value.strip() or bool(_LOCALE.fullmatch(value.strip())))))


def normalized_locale(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip() or not valid_locale(value):
        return None
    return value.strip().lower().replace("_", "-")


def normalized_text(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip()


def comparable_text(value: str) -> str:
    """Unicode-normalize and collapse whitespace so two visible texts can be compared."""
    return " ".join(normalized_text(value).split())
