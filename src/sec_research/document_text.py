"""Pure bounded document extraction and conservative section indexing."""

import codecs
from email.message import Message
from html.parser import attrfind_tolerant, tagfind_tolerant
import re
from typing import Callable, TypedDict
from xml.etree.ElementTree import C14NWriterTarget

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import DefusedXMLParser, ParseError

from src.lifecycle_public_sources import SourceReadError, _SourceTextParser, _normalize_text


MAX_MARKUP_BYTES = 1024 * 1024
MAX_NESTING = 512
MAX_PARSER_EVENTS = 2_000_000
MAX_TEXT_BYTES = 128 * 1024 * 1024
MAX_DOCUMENT_BYTES = 128 * 1024 * 1024
EXTRACTION_VERSION = "sec-document-text-v3"
_CHUNK = 65536


class Section(TypedDict):
    section_id: str
    label: str
    start_byte: int
    end_byte: int


class SectionGap(TypedDict):
    code: str
    section_id: str | None


class _Budget:
    def __init__(self, check):
        self.check = check
        self.events = 0

    def tick(self):
        self.check()
        self.events += 1
        if self.events > MAX_PARSER_EVENTS:
            raise SourceReadError("source_document_complexity")


class _TextParts:
    """Coalesce small fragments and normalize without a document-sized scratch copy."""

    def __init__(self, budget, *, normalize):
        self.budget = budget
        self.normalize = normalize
        self.size_bytes = 0
        self.pending_space = ""
        self.fragments = []
        self.fragment_chars = 0
        self.chunks = []

    def _emit(self, value):
        self.size_bytes += len(value.encode("utf-8"))
        if self.size_bytes > MAX_TEXT_BYTES:
            raise SourceReadError("source_text_too_large")
        self.fragments.append(value)
        self.fragment_chars += len(value)
        if self.fragment_chars >= _CHUNK:
            self.chunks.append("".join(self.fragments))
            self.fragments.clear()
            self.fragment_chars = 0

    def _space(self, value):
        if "\n" in value or "\r" in value:
            self.pending_space = "\n"
        elif value and not self.pending_space:
            self.pending_space = " "

    def append(self, value):
        self.budget.tick()
        for offset in range(0, len(value), _CHUNK):
            self.budget.check()
            chunk = value[offset:offset + _CHUNK]
            if not self.normalize:
                self._emit(chunk)
                continue
            leading = len(chunk) - len(chunk.lstrip())
            self._space(chunk[:leading])
            normalized = _normalize_text(chunk)
            if normalized:
                if self.size_bytes and self.pending_space:
                    self._emit(self.pending_space)
                self.pending_space = ""
                self._emit(normalized)
            self._space(chunk[len(chunk.rstrip()):])

    def finish(self):
        self.budget.check()
        self.chunks.append("".join(self.fragments))
        text = "".join(self.chunks)
        self.budget.check()
        if not text:
            raise SourceReadError("source_text_empty")
        return text


class _DocumentHTMLParser(_SourceTextParser):
    _INLINE_NAMESPACES = frozenset({
        "http://www.xbrl.org/2013/inlineXBRL", "http://www.xbrl.org/2008/inlineXBRL",
    })
    _INLINE_HIDDEN = frozenset({"header", "hidden", "references", "resources"})

    def __init__(self, budget, output):
        super().__init__(budget.tick)
        self.parts = output
        self.namespaces: dict[str, str] = {}
        self.namespace_scopes: list[dict[str, str | None]] = []

    def _bind_namespaces(self, attrs):
        previous = {}
        for name, value in attrs:
            if name == "xmlns":
                prefix = ""
            elif name.startswith("xmlns:"):
                prefix = name.removeprefix("xmlns:")
            else:
                continue
            self.check()
            namespace = value or ""
            if prefix in previous:
                if self.namespaces[prefix] != namespace:
                    raise SourceReadError("source_document_invalid")
            else:
                previous[prefix] = self.namespaces.get(prefix)
                self.namespaces[prefix] = namespace
        return previous

    def _restore_namespaces(self, previous):
        for prefix, namespace in previous.items():
            self.check()
            if namespace is None:
                self.namespaces.pop(prefix, None)
            else:
                self.namespaces[prefix] = namespace

    def handle_starttag(self, tag, attrs, *, namespace_attrs=None):
        if tag not in self._VOID and len(self.stack) >= MAX_NESTING:
            raise SourceReadError("source_document_complexity")
        previous = self._bind_namespaces(attrs if namespace_attrs is None else namespace_attrs)
        prefix, separator, local = tag.partition(":")
        if not separator:
            prefix, local = "", tag
        namespace = self.namespaces.get(prefix)
        # Retain literal ix compatibility only when no declaration binds that prefix.
        undeclared_ix = prefix == "ix" and prefix not in self.namespaces
        if (namespace in self._INLINE_NAMESPACES or undeclared_ix) and local in self._INLINE_HIDDEN:
            attrs = [*attrs, ("hidden", None)]
        super().handle_starttag(tag, attrs)
        if tag in self._VOID:
            self._restore_namespaces(previous)
        else:
            self.namespace_scopes.append(previous)

    def handle_endtag(self, tag):
        super().handle_endtag(tag)
        # Follow the existing tolerant stack, including closing unclosed descendants.
        while len(self.namespace_scopes) > len(self.stack):
            self._restore_namespaces(self.namespace_scopes.pop())

    def handle_comment(self, data):
        self.check()

    def handle_decl(self, decl):
        self.check()

    def unknown_decl(self, data):
        self.check()

    def handle_pi(self, data):
        self.check()

    def feed(self, data):
        offset = 0
        while offset < len(data):
            self.check()
            room = MAX_MARKUP_BYTES - len(self.rawdata.encode("utf-8"))
            if room <= 0:
                raise SourceReadError("source_document_complexity")
            count = min(_CHUNK, len(data) - offset, max(1, room // 4))
            part = data[offset:offset + count]
            if len(part.encode("utf-8")) > room:
                raise SourceReadError("source_document_complexity")
            super().feed(part)
            offset += count


class _HTMLDisplayNames(frozenset):
    """Keep tolerant HTML display rules separate from case-sensitive XML identity."""

    def __contains__(self, name):
        return super().__contains__(name.lower())


class _DocumentXHTMLParser(_DocumentHTMLParser):
    _SKIP = _HTMLDisplayNames(_SourceTextParser._SKIP)
    _VOID = _HTMLDisplayNames(_SourceTextParser._VOID)
    _BREAK = _HTMLDisplayNames(_SourceTextParser._BREAK)

    def __init__(self, budget, output):
        super().__init__(budget, output)
        self._end_qname = None

    def _source_starttag(self, attrs):
        # Use the parser's original token and lexical matchers, not its folded names.
        self.check()
        source = self.get_starttag_text()
        match = tagfind_tolerant.match(source, 1)
        assert match
        qname, offset = match.group(1), match.end()
        declarations = []
        for _, value in attrs:
            self.check()
            match = attrfind_tolerant.match(source, offset)
            assert match
            name, offset = match.group(1), match.end()
            if name == "xmlns" or name.startswith("xmlns:"):
                declarations.append((name, value))
        return qname, declarations

    def handle_starttag(self, tag, attrs):
        qname, declarations = self._source_starttag(attrs)
        super().handle_starttag(qname, attrs, namespace_attrs=declarations)

    def handle_startendtag(self, tag, attrs):
        qname, declarations = self._source_starttag(attrs)
        super().handle_starttag(qname, attrs, namespace_attrs=declarations)
        if qname not in self._VOID:
            super().handle_endtag(qname)

    def parse_endtag(self, offset):
        self.check()
        match = tagfind_tolerant.match(self.rawdata, offset + 2)
        self._end_qname = match.group(1) if match else None
        try:
            return super().parse_endtag(offset)
        finally:
            self._end_qname = None

    def handle_endtag(self, tag):
        assert self._end_qname is not None
        super().handle_endtag(self._end_qname)


class _DocumentXMLTarget(C14NWriterTarget):
    def __init__(self, budget, output):
        super().__init__(output.append)
        self.budget = budget
        self.depth = 0

    def start(self, tag, attrs):
        self.budget.tick()
        self.depth += 1
        if self.depth > MAX_NESTING:
            raise SourceReadError("source_document_complexity")
        super().start(tag, attrs)

    def end(self, tag):
        self.budget.tick()
        super().end(tag)
        self.depth -= 1

    def data(self, value):
        self.budget.tick()
        super().data(value)
        # Default C14N has no text stripping or QName-aware text to buffer.
        self._flush()

    def start_ns(self, prefix, uri):
        self.budget.tick()
        super().start_ns(prefix, uri)

    def comment(self, text):
        self.budget.tick()
        super().comment(text)

    def pi(self, target, text=None):
        self.budget.tick()
        super().pi(target, text)


def _extract_xml(body, charset, budget, output):
    parser = DefusedXMLParser(
        target=_DocumentXMLTarget(budget, output), encoding=charset,
        forbid_dtd=True, forbid_entities=True, forbid_external=True,
    )
    offset = 0
    try:
        while offset < len(body):
            budget.tick()
            # Expat's byte index stops at the start of an incomplete token.
            room = MAX_MARKUP_BYTES - (offset - parser.parser.CurrentByteIndex)
            if room <= 0:
                raise SourceReadError("source_document_complexity")
            count = min(_CHUNK, room, len(body) - offset)
            parser.feed(body[offset:offset + count])
            offset += count
        parser.close()
    except SourceReadError:
        raise
    except LookupError:
        raise SourceReadError("source_encoding_unsupported") from None
    except (ParseError, DefusedXmlException, ValueError, RecursionError):
        raise SourceReadError("source_document_invalid") from None


def _decoded_chunks(body, charset, budget):
    try:
        charset = charset or "utf-8-sig"
        # Match bytes.decode's text-only gate before a binary codec can expand data.
        if not codecs.lookup(charset)._is_text_encoding:
            raise LookupError
        decoder = codecs.getincrementaldecoder(charset)(errors="strict")
        for offset in range(0, len(body), _CHUNK):
            budget.tick()
            value = decoder.decode(body[offset:offset + _CHUNK])
            value.encode("utf-8")
            yield value
        value = decoder.decode(b"", final=True)
        value.encode("utf-8")
        yield value
    except (LookupError, UnicodeError):
        raise SourceReadError("source_encoding_unsupported") from None


def extract_document_text(
    body: bytes, content_type: str, *, check: Callable[[], object]
) -> tuple[str, str]:
    check()
    if not isinstance(body, bytes) or not isinstance(content_type, str):
        raise SourceReadError("source_document_invalid")
    if len(body) > MAX_DOCUMENT_BYTES:
        raise SourceReadError("source_decoded_body_too_large")
    header = Message()
    header["Content-Type"] = content_type
    mime = header.get_content_type()
    if mime not in {"text/plain", "text/html", "application/xhtml+xml", "application/xml", "text/xml"}:
        raise SourceReadError("source_format_unsupported")
    budget = _Budget(check)
    xml = mime in {"application/xml", "text/xml"}
    output = _TextParts(budget, normalize=not xml)
    charset = header.get_content_charset()
    if xml:
        _extract_xml(body, charset, budget, output)
    elif mime == "text/plain":
        for chunk in _decoded_chunks(body, charset, budget):
            output.append(chunk)
    else:
        parser_type = _DocumentXHTMLParser if mime == "application/xhtml+xml" else _DocumentHTMLParser
        parser = parser_type(budget, output)
        try:
            for chunk in _decoded_chunks(body, charset, budget):
                parser.feed(chunk)
            parser.close()
        except SourceReadError:
            raise
        except (AssertionError, ValueError, RecursionError):
            raise SourceReadError("source_document_invalid") from None
    return output.finish(), mime


_ANNUAL_PARTS = {
    "I": frozenset({"1", "1A", "1B", "1C", "2", "3", "4"}),
    "II": frozenset({"5", "6", "7", "7A", "8", "9", "9A", "9B", "9C"}),
    "III": frozenset({"10", "11", "12", "13", "14"}),
    "IV": frozenset({"15", "16"}),
}
_QUARTERLY_PARTS = {
    "I": frozenset({"1", "2", "3", "4"}),
    "II": frozenset({"1", "1A", "2", "3", "4", "5", "6"}),
}
_CURRENT_ITEMS = frozenset({
    "1.01", "1.02", "1.03", "1.04", "1.05", "2.01", "2.02", "2.03", "2.04", "2.05", "2.06",
    "3.01", "3.02", "3.03", "4.01", "4.02", "5.01", "5.02", "5.03", "5.04", "5.05", "5.06",
    "5.07", "5.08", "6.01", "6.02", "6.03", "6.04", "6.05", "7.01", "8.01", "9.01",
})
_HEADING = re.compile(r"^(PART|ITEM)\s+(IV|III|II|I|[0-9]{1,2}(?:[A-C]|\.[0-9]{2})?)(?:[.:\-]?\s+.*|[.:-]?)$", re.I)


def _lines(text, budget):
    offset = byte_offset = start_byte = 0
    label = ""
    while offset < len(text):
        budget.tick()
        end = min(offset + _CHUNK, len(text))
        newline = text.find("\n", offset, end)
        if newline >= 0:
            end = newline + 1
        part = text[offset:end]
        try:
            byte_offset += len(part.encode("utf-8"))
        except UnicodeError:
            raise SourceReadError("source_encoding_unsupported") from None
        if byte_offset > MAX_TEXT_BYTES:
            raise SourceReadError("source_text_too_large")
        label = label + part if label is not None and len(label) + len(part) <= 240 else None
        if newline >= 0 or end == len(text):
            yield label.strip() if label is not None else None, start_byte, byte_offset
            start_byte, label = byte_offset, ""
        offset = end


def index_sections(
    text: str, form: str, *, check: Callable[[], object]
) -> tuple[list[Section], list[SectionGap]]:
    check()
    if not isinstance(text, str) or not isinstance(form, str):
        raise SourceReadError("source_document_invalid")
    form = form.upper().removesuffix("/A")
    if form not in {"10-K", "10-Q", "8-K"}:
        return [], [{"code": "section_index_unsupported", "section_id": None}]
    parts = _QUARTERLY_PARTS if form == "10-Q" else _ANNUAL_PARTS if form == "10-K" else {}
    items = frozenset().union(*parts.values()) if parts else _CURRENT_ITEMS
    budget = _Budget(check)
    rows, ambiguous, parents = {}, set(), {}
    current_part = pending_item = pending_part = None
    in_toc = False
    end_byte = 0
    for label, start_byte, end_byte in _lines(text, budget):
        if label is None:
            continue
        if label.upper() == "TABLE OF CONTENTS":
            # Repeated headings alone cannot establish a transition into body text.
            in_toc = True
        match = _HEADING.fullmatch(label)
        if match is None:
            continue
        kind, number = (value.upper() for value in match.groups())
        if kind == "PART":
            if number not in parts:
                continue
            current_part = number
            section_id = "part_" + number.lower()
        else:
            if number not in items:
                continue
            section_id = "item_" + number.lower().replace(".", "_")
            if form == "10-Q" and current_part is not None:
                section_id = "part_" + current_part.lower() + "_" + section_id
        if pending_item is not None:
            pending_item["end_byte"] = start_byte
            pending_item = None
        if kind == "PART" and pending_part is not None:
            pending_part["end_byte"] = start_byte
        if section_id in rows:
            ambiguous.add(section_id)
        row = Section(section_id=section_id, label=label, start_byte=start_byte, end_byte=end_byte)
        rows.setdefault(section_id, row)
        if in_toc or re.search(r"\.{2,}\s*\d+\s*$", label):
            ambiguous.add(section_id)
        if kind == "PART":
            pending_part = row
        else:
            pending_item = row
            if form == "10-Q" and current_part is None:
                ambiguous.add(section_id)
            if current_part is not None:
                parents[section_id] = "part_" + current_part.lower()
                if number not in parts[current_part]:
                    ambiguous.add(section_id)
    for row in (pending_item, pending_part):
        if row is not None:
            row["end_byte"] = end_byte
    ambiguous.update(key for key, parent in parents.items() if parent in ambiguous)
    sections = [row for key, row in rows.items() if key not in ambiguous]
    gaps = [SectionGap(code="section_ambiguous", section_id=key) for key in sorted(ambiguous)]
    if not sections and not gaps:
        gaps.append(SectionGap(code="section_index_unavailable", section_id=None))
    check()
    return sections, gaps
