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
EXTRACTION_VERSION = "sec-document-text-v4"
_CHUNK = 65536


class Section(TypedDict):
    section_id: str
    label: str
    start_byte: int
    end_byte: int


class SectionGap(TypedDict):
    code: str
    section_id: str | None


class TocRange(TypedDict):
    start_byte: int
    end_byte: int


class DocumentStructure(TypedDict):
    toc_ranges: list[TocRange]
    structure_gaps: list[SectionGap]


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
        self.content_start = None

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
        self.content_start = None
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
                if self.content_start is None:
                    self.content_start = self.size_bytes
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


class _TOCStructure:
    """Observe display events without changing text or inferring missing end tags."""

    def __init__(self, budget, output):
        self.budget, self.output = budget, output
        self.stack, self.closed, self.gaps = [], [], []
        self.previous_title = None

    def gap(self, code):
        gap = SectionGap(code=code, section_id=None)
        if gap not in self.gaps:
            self.gaps.append(gap)

    def start(self, tag, local, attrs, *, hidden, html):
        self.budget.tick()
        attributes = dict(attrs)
        role = "doc-toc" in (attributes.get("role") or "").lower().split()
        labelled = (attributes.get("aria-label") or "").strip().lower() == "table of contents"
        candidate = html and not hidden and (role or local in {"nav", "table"})
        title = self.previous_title
        adjacent = (candidate and local == "table" and title is not None
                    and title[2] == len(self.stack) and title[1] == self.output.size_bytes)
        frame = {"tag": tag, "local": local, "candidate": candidate, "role": role,
                 "title": labelled if local == "nav" else adjacent, "links": set(),
                 "start": title[0] if adjacent else None, "text": "", "hidden": hidden,
                 "html": html, "href": attributes.get("href") or "", "linked": None,
                 "pending_heading": None,
                 "invalid": len(attributes) != len(attrs) or local in {"html", "body"}}
        self.stack.append(frame)

    def data(self, data):
        if self.output.content_start is None:
            return
        self.previous_title = None
        for frame in self.stack:
            self.budget.tick()
            if frame["hidden"]:
                continue
            if frame["start"] is None:
                frame["start"] = self.output.content_start
            if frame["local"] in {"h1", "h2", "h3", "h4", "h5", "h6", "caption", "a"}:
                if frame["text"] is not None:
                    frame["text"] = frame["text"] + data if len(frame["text"]) + len(data) <= 240 else None

    def end(self, tag, depth):
        self.budget.tick()
        exact = bool(self.stack and self.stack[-1]["tag"] == tag)
        if not exact:
            for frame in self.stack:
                self.budget.tick()
                frame["invalid"] = True
        while len(self.stack) > depth:
            frame = self.stack.pop()
            self.budget.tick()
            label = " ".join((frame["text"] or "").split())
            heading = frame["html"] and frame["local"] in {"h1", "h2", "h3", "h4", "h5", "h6", "caption"}
            title = heading and label.lower() == "table of contents"
            match = _HEADING.fullmatch(label)
            heading_link = (exact and not frame["invalid"] and frame["html"]
                            and frame["local"] == "a" and match is not None
                            and frame["href"].startswith("#") and len(frame["href"]) > 1
                            and frame["pending_heading"] in {None, label})
            if frame["pending_heading"] is not None and not heading_link:
                frame["invalid"] = True
            item_link = heading_link and match.group(1).upper() == "ITEM"
            if not frame["hidden"]:
                if heading and match and frame["linked"] != label:
                    # An enclosing anchor is evidence only after its complete close.
                    anchor = None
                    for ancestor in reversed(self.stack):
                        self.budget.tick()
                        if ancestor["local"] == "a":
                            anchor = ancestor
                            break
                    if anchor is None:
                        frame["invalid"] = True
                    elif anchor["pending_heading"] is not None:
                        anchor["invalid"] = True
                    else:
                        anchor["pending_heading"] = label
                for parent in self.stack:
                    self.budget.tick()
                    if title:
                        parent["title"] = True
                    if frame["invalid"]:
                        parent["invalid"] = True
                    if heading_link:
                        parent["linked"] = label
                    if item_link:
                        if len(parent["links"]) < 2:
                            parent["links"].add(frame["href"])
            if title and exact and not frame["invalid"] and frame["start"] is not None:
                self.previous_title = (frame["start"], self.output.size_bytes, len(self.stack))
            if frame["candidate"] and (frame["role"] or frame["title"]):
                valid = (exact and not frame["invalid"] and frame["start"] is not None
                         and (frame["role"] or frame["local"] == "nav"
                              or frame["local"] == "table" and len(frame["links"]) >= 2))
                if valid:
                    self.closed.append(TocRange(start_byte=frame["start"], end_byte=self.output.size_bytes))
                else:
                    self.gap("toc_structure_ambiguous")

    def finish(self):
        for frame in self.stack:
            self.budget.tick()
            if frame["candidate"] and (frame["role"] or frame["title"]):
                self.gap("toc_structure_unclosed")
        ranges = []
        for region in sorted(self.closed, key=lambda r: (r["start_byte"], -r["end_byte"])):
            self.budget.tick()
            if region["start_byte"] == 0 and region["end_byte"] == self.output.size_bytes:
                self.gap("toc_structure_overbroad")
            elif region["start_byte"] < region["end_byte"]:
                if ranges and region["start_byte"] < ranges[-1]["end_byte"]:
                    ranges[-1]["end_byte"] = max(ranges[-1]["end_byte"], region["end_byte"])
                else:
                    ranges.append(region)
        return DocumentStructure(toc_ranges=ranges, structure_gaps=self.gaps)


class _DocumentHTMLParser(_SourceTextParser):
    _INLINE_NAMESPACES = frozenset({
        "http://www.xbrl.org/2013/inlineXBRL", "http://www.xbrl.org/2008/inlineXBRL",
    })
    _INLINE_HIDDEN = frozenset({"header", "hidden", "references", "resources"})

    def __init__(self, budget, output, structure=None):
        super().__init__(budget.tick)
        self.parts = output
        self.namespaces: dict[str, str] = {}
        self.namespace_scopes: list[dict[str, str | None]] = []
        self.structure = structure

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
            if self.structure is not None:
                self.structure.start(tag, local.lower(), attrs, hidden=self.stack[-1][1],
                    html=namespace == "http://www.w3.org/1999/xhtml" or not separator and namespace in {None, ""})

    def handle_endtag(self, tag):
        super().handle_endtag(tag)
        if self.structure is not None and tag not in self._VOID:
            self.structure.end(tag, len(self.stack))
        # Follow the existing tolerant stack, including closing unclosed descendants.
        while len(self.namespace_scopes) > len(self.stack):
            self._restore_namespaces(self.namespace_scopes.pop())

    def handle_data(self, data):
        visible = not self.stack or not self.stack[-1][1]
        super().handle_data(data)
        if visible and self.structure is not None:
            self.structure.data(data)

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

    def __init__(self, budget, output, structure=None):
        super().__init__(budget, output, structure)
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
    body: bytes, content_type: str, *, check: Callable[[], object],
    structure_observer: Callable[[DocumentStructure], object] | None = None,
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
    structure = None
    if xml:
        _extract_xml(body, charset, budget, output)
    elif mime == "text/plain":
        for chunk in _decoded_chunks(body, charset, budget):
            output.append(chunk)
    else:
        parser_type = _DocumentXHTMLParser if mime == "application/xhtml+xml" else _DocumentHTMLParser
        structure = _TOCStructure(budget, output) if structure_observer is not None else None
        parser = parser_type(budget, output, structure)
        try:
            for chunk in _decoded_chunks(body, charset, budget):
                parser.feed(chunk)
            parser.close()
        except SourceReadError:
            raise
        except (AssertionError, ValueError, RecursionError):
            raise SourceReadError("source_document_invalid") from None
    text = output.finish()
    if structure_observer is not None:
        observation = structure.finish() if structure else DocumentStructure(toc_ranges=[], structure_gaps=[])
        check()
        structure_observer(observation)
    return text, mime


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
    text: str, form: str, *, check: Callable[[], object], toc_ranges: list[TocRange] | None = None,
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
    region_index = 0
    regions = toc_ranges or []
    for label, start_byte, end_byte in _lines(text, budget):
        if label is None:
            continue
        while region_index < len(regions) and regions[region_index]["end_byte"] <= start_byte:
            budget.tick()
            region_index += 1
        if region_index < len(regions):
            region = regions[region_index]
            if region["start_byte"] <= start_byte and start_byte + len(label.encode("utf-8")) <= region["end_byte"]:
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
