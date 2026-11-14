"""Strict, balanced HTML-fragment checks; not a browser or security sanitizer."""

from collections import Counter
from dataclasses import dataclass
from html.parser import HTMLParser
import re


_VOID_TAGS = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input",
                       "link", "meta", "param", "source", "track", "wbr"})
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9:_-]*\Z")
_TAG_START = re.compile(r"<(?:/?[A-Za-z]|[!?])")


def _lexical_errors(text: str) -> list[str]:
    """Check raw delimiters without mistaking decoded entities for markup.

    HTMLParser intentionally tolerates incomplete markup, so its callbacks alone
    do not establish a complete fragment. Quoted '>' characters must be skipped.
    """
    errors: list[str] = []
    cursor = 0
    while cursor < len(text):
        start = text.find("<", cursor)
        if start == -1:
            break
        if text.startswith("<!--", start):
            end = text.find("-->", start + 4)
            if end == -1:
                errors.append("Unterminated HTML comment.")
                break
            cursor = end + 3
            continue
        if not _TAG_START.match(text, start):
            cursor = start + 1
            continue
        quote = None
        end = start + 1
        while end < len(text):
            char = text[end]
            if quote is not None:
                if char == quote:
                    quote = None
            elif char in {"'", '"'}:
                quote = char
            elif char == ">":
                break
            end += 1
        if end == len(text):
            errors.append("Unterminated HTML tag or quoted attribute.")
            break
        cursor = end + 1
        name = re.match(r"<([A-Za-z][A-Za-z0-9:_-]*)\b", text[start:end + 1])
        if name and name.group(1).lower() in {"script", "style"}:
            # Contents are explicitly outside the profile; a '<' in script text
            # must not be interpreted as a translation tag.
            closing = re.search(r"</" + name.group(1) + r"\s*>", text[cursor:], re.IGNORECASE)
            cursor = cursor + closing.end() if closing else len(text)
    return errors


@dataclass(frozen=True)
class MarkupScan:
    tags: tuple[str, ...]
    paths: tuple[tuple[str, ...], ...]
    visible_text: str
    errors: tuple[str, ...] = ()
    unverified: bool = False


class _FragmentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.tags: list[str] = []
        self.paths: list[tuple[str, ...]] = []
        self.text: list[str] = []
        self.errors: list[str] = []
        self.unverified = False

    def _open(self, tag: str, closed: bool) -> None:
        if not _NAME.fullmatch(tag):
            self.errors.append(f"Unsupported tag name <{tag}>.")
            return
        self.tags.append(tag)
        self.paths.append(tuple(self.stack + [tag]))
        if tag in {"script", "style"}:
            self.unverified = True
        # Separate visible runs so removing markup cannot join two quantities.
        self.text.append(" ")
        if not closed and tag not in _VOID_TAGS:
            self.stack.append(tag)

    def handle_starttag(self, tag: str, attrs: list) -> None:
        self._open(tag, closed=False)

    def handle_startendtag(self, tag: str, attrs: list) -> None:
        self._open(tag, closed=True)

    def handle_endtag(self, tag: str) -> None:
        self.text.append(" ")
        if tag in _VOID_TAGS:
            self.errors.append(f"Void tag <{tag}> must not have a closing tag.")
        elif not self.stack:
            self.errors.append(f"Unexpected closing tag </{tag}>.")
        elif self.stack[-1] != tag:
            self.errors.append(f"Closing tag </{tag}> does not match <{self.stack[-1]}>.")
            if tag in self.stack:
                while self.stack and self.stack[-1] != tag:
                    self.stack.pop()
                self.stack.pop()
        else:
            self.stack.pop()

    def handle_data(self, data: str) -> None:
        if "script" not in self.stack and "style" not in self.stack:
            self.text.append(data)

    def handle_comment(self, data: str) -> None:
        self.text.append(" ")

    def handle_decl(self, decl: str) -> None:
        self.unverified = True

    def handle_pi(self, data: str) -> None:
        self.unverified = True

    def unknown_decl(self, data: str) -> None:
        self.unverified = True


def scan_markup(text: str) -> MarkupScan:
    parser = _FragmentParser()
    parser.errors.extend(_lexical_errors(text))
    try:
        parser.feed(text)
        parser.close()
    except (ValueError, AssertionError) as exc:
        parser.errors.append(f"Markup could not be parsed: {type(exc).__name__}.")
    if parser.stack:
        parser.errors.append("Unclosed tags: " + ", ".join(parser.stack) + ".")
    return MarkupScan(tuple(parser.tags), tuple(parser.paths), "".join(parser.text),
                      tuple(dict.fromkeys(parser.errors)), parser.unverified)


def compare_markup(source: MarkupScan, target: MarkupScan) -> list[tuple[str, str, str]]:
    """Return (category, description, severity) findings."""
    findings: list[tuple[str, str, str]] = []
    for label, scan in (("Source", source), ("Translation", target)):
        if scan.errors:
            findings.append(("html_tag_mismatch", label + " fragment: " + " ".join(scan.errors), "critical"))
        if scan.unverified:
            findings.append(("html_content_unverified", label + " contains script/style content or a declaration outside the visible-text profile.", "informational"))
    # A malformed reference does not justify guessing which translated tags to change.
    if source.errors or target.errors:
        return findings
    missing = Counter(source.tags) - Counter(target.tags)
    additional = Counter(target.tags) - Counter(source.tags)
    if missing:
        description = ", ".join(f"<{tag}> (count {count})" for tag, count in sorted(missing.items()))
        findings.append(("missing_html_tag", "Translation is missing tag occurrences: " + description + ".", "critical"))
    if additional:
        description = ", ".join(f"<{tag}> (count {count})" for tag, count in sorted(additional.items()))
        findings.append(("unexpected_html_tag", "Translation adds tag occurrences: " + description + ".", "critical"))
    if not missing and not additional and Counter(source.paths) != Counter(target.paths):
        findings.append(("html_structure_changed", "Tag counts match but nesting differs; review whether the formatting change is intentional.", "warning"))
    return findings
