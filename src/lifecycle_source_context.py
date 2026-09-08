"""Traceable source selection, independent of download and model token budgets.

Every matching passage and its neighbours are retained, including contrary and
future/conditional statements. There is no first-N or top-K clipping. A source
with no recognised relevance is supplied whole, not treated as an empty result.
These are model inputs, never a new authority for listing status.
"""

from collections import deque
from dataclasses import dataclass
import hashlib
import re

from src.lifecycle_public_sources import PublicSourcePage, SourceReadError, _capture_digest


_BOUNDARY = re.compile(r"\n+|(?<=[.!?])\s+(?=[A-Z0-9])|(?<=[\u3002\uff01\uff1f])")
_RELEVANCE = re.compile(
    r"\b(?:delist\w*|de-list\w*|list\w*|trad\w*|ticker\w*|symbol\w*|stock\w*|share\w*|"
    r"securit\w*|exchange\w*|nasdaq|nyse|otc\w*|merg\w*|acquir\w*|acquisition\w*|"
    r"tender\w*|cusip|figi|cik|effective\w*|suspend\w*|halt\w*|cessation|ceased?|"
    r"renam\w*|name\s+change|reorganiz\w*|convert\w*|conversion\w*|bankrupt\w*|"
    r"deregister\w*|registration|form\s+25|item\s+[235]\.01|"
    r"not|no|never|remain\w*|continu\w*|however|except\w*|cancel\w*|withdraw\w*|"
    r"pending|propos\w*|subject|expected|may|will|unable|"
    r"january|february|march|april|may|june|july|august|september|october|november|december)\b"
    r"|\b(?:19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2}\b"
    r"|\u4e0b\u5e02|\u6539\u540d|\u66f4\u540d|\u4ea4\u6613|\u80a1\u7968|\u666e\u901a\u80a1"
    r"|\u6536\u8cfc|\u4f75\u8cfc|\u751f\u6548|\u66ab\u505c|\u4ecd|\u5c1a\u672a|\u672a\u65bc",
    re.IGNORECASE,
)


def _source_bytes(page):
    if not isinstance(page, PublicSourcePage) or page.capture_sha256 != _capture_digest(page):
        raise SourceReadError("source_integrity")
    encoded = page.text.encode("utf-8")
    if hashlib.sha256(encoded).hexdigest() != page.text_sha256:
        raise SourceReadError("source_integrity")
    return encoded


@dataclass(frozen=True)
class SourceContext:
    source_text_sha256: str
    source_bytes: int
    ranges: tuple[tuple[int, int], ...]

    def to_material(self):
        return {"version": 1, "source_text_sha256": self.source_text_sha256,
                "source_bytes": self.source_bytes, "ranges": [list(pair) for pair in self.ranges]}

    @classmethod
    def from_material(cls, value, page):
        encoded = _source_bytes(page)
        if (type(value) is not dict or set(value) != {"version", "source_text_sha256", "source_bytes", "ranges"}
                or type(value["version"]) is not int or value["version"] != 1
                or value["source_text_sha256"] != page.text_sha256
                or type(value["source_bytes"]) is not int or value["source_bytes"] != len(encoded)
                or type(value["ranges"]) is not list or not value["ranges"]):
            raise SourceReadError("source_context_invalid")
        previous_end, ranges = -1, []
        for pair in value["ranges"]:
            if (type(pair) is not list or len(pair) != 2 or any(type(item) is not int for item in pair)
                    or not 0 <= pair[0] < pair[1] <= len(encoded) or pair[0] <= previous_end):
                raise SourceReadError("source_context_invalid")
            try:
                text = page.text if pair == [0, len(encoded)] else encoded[pair[0]:pair[1]].decode("utf-8")
                if not text.strip():
                    raise SourceReadError("source_context_invalid")
            except UnicodeError:
                raise SourceReadError("source_context_invalid") from None
            ranges.append(tuple(pair))
            previous_end = pair[1]
        return cls(page.text_sha256, len(encoded), tuple(ranges))

    def contains(self, start, end):
        return any(left <= start < end <= right for left, right in self.ranges)

    def prompt_material(self, page):
        self.from_material(self.to_material(), page)
        full_text = self.ranges == ((0, self.source_bytes),)
        encoded = None if full_text else page.text.encode("utf-8")
        return {
            "coverage": "full_text" if full_text else "selected_passages",
            "passages": [{"start_byte": start, "end_byte": end,
                          "text": page.text if full_text else encoded[start:end].decode("utf-8")}
                         for start, end in self.ranges],
        }


def parse_source_context(value, pages):
    if type(value) is not dict or set(value) != set(pages):
        raise SourceReadError("source_context_invalid")
    return {identity: SourceContext.from_material(material, pages[identity]) for identity, material in value.items()}


def _units(text):
    start = 0
    for boundary in _BOUNDARY.finditer(text):
        if boundary.end() > start:
            yield start, boundary.end()
            start = boundary.end()
    if start < len(text):
        yield start, len(text)


def select_source_context(request, page, *, check=lambda: None):
    encoded = _source_bytes(page)
    if not encoded:
        raise SourceReadError("source_text_empty")
    if page.mime_type in {"application/json", "application/xml", "text/xml"}:
        # Structured records must keep their keys/classes and record boundaries.
        return SourceContext(page.text_sha256, len(encoded), ((0, len(encoded)),))
    identities = [re.compile(r"(?<!\w)" + re.escape(value) + r"(?!\w)", re.IGNORECASE)
                  for value in (request.ticker, request.issuer_name, request.issuer_cik) if value]
    history, ranges = deque(maxlen=2), []
    follow, matched = 0, False

    def include(start, end):
        if ranges and start <= ranges[-1][1]:
            ranges[-1] = (ranges[-1][0], max(end, ranges[-1][1]))
        else:
            ranges.append((start, end))

    for index, (start, end) in enumerate(_units(page.text)):
        check()
        hit = _RELEVANCE.search(page.text, start, end) or any(pattern.search(page.text, start, end) for pattern in identities)
        if hit:
            include(history[0][0] if history else start, end)
            follow, matched = 2, True
        elif follow:
            include(start, end)
            follow -= 1
        elif index < 2:
            include(start, end)
        history.append((start, end))
    if not matched:
        return SourceContext(page.text_sha256, len(encoded), ((0, len(encoded)),))
    if history:
        include(history[0][0], history[-1][1])
    byte_ranges, previous_char, previous_byte = [], 0, 0
    for start, end in ranges:
        check()
        left = previous_byte + len(page.text[previous_char:start].encode("utf-8"))
        right = left + len(page.text[start:end].encode("utf-8"))
        byte_ranges.append((left, right))
        previous_char, previous_byte = end, right
    return SourceContext(page.text_sha256, len(encoded), tuple(byte_ranges))
