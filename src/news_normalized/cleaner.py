"""Deterministic, non-rendering conversion of provider bodies to search text."""

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
import re

CLEANER_VERSION = "news-clean-v1"

_BLOCK_TAGS = {
    "article",
    "blockquote",
    "br",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "p",
    "pre",
    "section",
    "table",
    "tr",
}
_DROP_TAGS = {"head", "script", "style", "noscript", "svg"}
_HTML_TAG_RE = re.compile(r"</?[a-z][a-z0-9:-]*(?:\s[^<>]*)?>", re.IGNORECASE)


@dataclass(frozen=True)
class CleanBody:
    text: str
    version: str = CLEANER_VERSION


class _BodyTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.drop_depth = 0
        self.row_cell_count = 0

    def handle_starttag(self, tag, attrs) -> None:
        del attrs
        normalized = tag.casefold()
        if normalized in _DROP_TAGS:
            self.drop_depth += 1
            return
        if self.drop_depth:
            return
        if normalized == "tr":
            self.parts.append("\n")
            self.row_cell_count = 0
        elif normalized in {"td", "th"}:
            if self.row_cell_count:
                self.parts.append(" | ")
            self.row_cell_count += 1
        elif normalized in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_startendtag(self, tag, attrs) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag) -> None:
        normalized = tag.casefold()
        if normalized in _DROP_TAGS:
            if self.drop_depth:
                self.drop_depth -= 1
            return
        if self.drop_depth:
            return
        if normalized in _BLOCK_TAGS:
            self.parts.append("\n")
        if normalized == "tr":
            self.row_cell_count = 0

    def handle_data(self, data) -> None:
        if not self.drop_depth:
            self.parts.append(data)


def _normalize_blocks(text: str) -> str:
    lines = [
        re.sub(r"[^\S\n]+", " ", line).strip()
        for line in unescape(text).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ]
    return "\n\n".join(line for line in lines if line)


def looks_like_html(value: str | None) -> bool:
    return bool(value and _HTML_TAG_RE.search(value))


def clean_news_body(
    raw_body: str,
    *,
    raw_format: str | None,
    source: str,
) -> CleanBody:
    """Return plain deterministic text; never execute or return provider markup."""
    del source  # Reserved for narrow, fixture-backed provider rules.
    raw = raw_body or ""
    format_name = (raw_format or "").strip().casefold()
    if format_name in {"html", "xml"} or looks_like_html(raw):
        parser = _BodyTextParser()
        parser.feed(raw)
        parser.close()
        raw = "".join(parser.parts)
    return CleanBody(_normalize_blocks(raw))
