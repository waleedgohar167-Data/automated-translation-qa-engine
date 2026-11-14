"""Conservative placeholder and numeric token extraction, without evaluating text."""

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from string import Formatter
import unicodedata


_FIELD_NAME = re.compile(r"(?:[A-Za-z_][A-Za-z0-9_]*|[0-9]+)\Z")
_PRINTF = re.compile(
    r"%%|%(?:\((?P<name>[A-Za-z_][A-Za-z0-9_]*)\)|(?P<position>[1-9][0-9]*)\$)?"
    r"[-+#0]*(?:[0-9]+)?(?:\.[0-9]+)?(?P<kind>[sdif])(?=$|[^A-Za-z0-9_])"
)
_UNSUPPORTED_PRINTF = re.compile(r"%(?:\([^)]*\))?(?:[1-9][0-9]*\$)?[-+#0-9.*]*[A-Za-z]")
_NUMBERS = re.compile(r"[+\-\u2212]?\d+(?:[.,\u066b\u066c]\d+)*")
_SCIENTIFIC = re.compile(r"\d(?:[.,]\d+)?[eE][+\-]?\d")


@dataclass(frozen=True)
class PlaceholderScan:
    tokens: tuple[str, ...]
    literal_text: str
    unverified: bool = False


@dataclass(frozen=True)
class NumberScan:
    values: tuple[Decimal, ...]
    unverified: bool = False


def scan_placeholders(text: str) -> PlaceholderScan:
    """Extract brace identities and supported printf arguments.

    Brace modifiers are removed with their field so their numbers are never
    mistaken for translated quantities. Unsupported brace expressions make
    the comparison unverified rather than silently passing it.
    """
    try:
        parts = list(Formatter().parse(text))
    except ValueError:
        return PlaceholderScan((), "", unverified=True)

    tokens: list[str] = []
    literals: list[str] = []
    unverified = False
    for literal, field, format_spec, conversion in parts:
        literals.append(literal)
        if field is None:
            continue
        literals.append(" ")
        if (not _FIELD_NAME.fullmatch(field)
                or "{" in format_spec or "}" in format_spec
                or conversion not in (None, "s", "r", "a")):
            unverified = True
        else:
            tokens.append("{" + field + "}")

    def mask_printf(match: re.Match[str]) -> str:
        if match.group() == "%%":
            return " "
        name, position, kind = match.group("name", "position", "kind")
        if name is not None:
            tokens.append(f"%({name}){kind}")
        elif position is not None:
            tokens.append(f"%{position}${kind}")
        else:
            tokens.append(f"%{kind}")
        return " "

    literal_text = _PRINTF.sub(mask_printf, "".join(literals))
    if _UNSUPPORTED_PRINTF.search(literal_text):
        unverified = True
    return PlaceholderScan(tuple(tokens), literal_text, unverified)


def _ascii_digits(text: str) -> str:
    return "".join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in text)


def _numeric_value(raw: str, locale: str | None) -> Decimal:
    raw = _ascii_digits(raw).replace("\u2212", "-")
    language = locale.lower().replace("_", "-").split("-")[0] if locale else ""
    if "\u066b" in raw or "\u066c" in raw:
        decimal_separator, group_separator = "\u066b", "\u066c"
    elif language in {"de", "es"}:
        decimal_separator, group_separator = ",", "."
    elif language == "fr":
        decimal_separator, group_separator = ",", None
    elif language in {"en", "bn"}:
        decimal_separator, group_separator = ".", ","
    else:
        # Without a supported declared locale, only plain integers and dot
        # decimals are interpreted. A comma is never guessed as a separator.
        decimal_separator, group_separator = ".", None
    if raw.count(decimal_separator) > 1:
        raise ValueError("Multiple decimal separators")
    integer, found, fraction = raw.partition(decimal_separator)
    if found and not fraction.isascii():
        raise ValueError("Unexpected fractional notation")
    if found and not fraction.isdecimal():
        raise ValueError("Invalid fractional digits")
    if group_separator and group_separator in integer:
        unsigned = integer.lstrip("+-")
        groups = unsigned.split(group_separator)
        if (not 1 <= len(groups[0]) <= 3 or not groups[0].isdigit()
                or any(len(g) != 3 or not g.isdigit() for g in groups[1:])):
            raise ValueError("Unsupported digit grouping")
        integer = integer.replace(group_separator, "")
    if not integer.lstrip("+-").isascii() or not integer.lstrip("+-").isdecimal():
        raise ValueError("Unsupported integer notation for the declared profile")
    normalized = integer + ("." + fraction if found else "")
    if not re.fullmatch(r"[+-]?[0-9]+(?:\.[0-9]+)?", normalized):
        raise ValueError("Unsupported numeric format")
    return Decimal(normalized)


def scan_numbers(text: str, locale: str | None = None) -> NumberScan:
    # Space grouping and scientific notation require an explicit richer grammar.
    if (re.search(r"\d[ \u00a0\u202f]\d", text) or _SCIENTIFIC.search(text)
            or re.search(r"(?<!\d)[.,\u066b]\d", text)):
        return NumberScan((), unverified=True)
    values: list[Decimal] = []
    for match in _NUMBERS.finditer(text):
        try:
            values.append(_numeric_value(match.group(), locale))
        except (ValueError, InvalidOperation):
            return NumberScan((), unverified=True)
    return NumberScan(tuple(values))


def describe_counts(values: Counter) -> str:
    return ", ".join(f"{value!s} (count {count})" for value, count in sorted(values.items(), key=lambda p: str(p[0])))
