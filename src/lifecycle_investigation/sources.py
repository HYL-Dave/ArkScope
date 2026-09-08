"""Exact captured text and inspectable passages, not model-reconstructed quotes."""

import hashlib
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlsplit

from src.lifecycle_public_sources import PublicSourceReader, SourceReadError, canonical_source_url


def capture_text(text, *, url, retrieved_at, coverage, title=None, publisher=None, published_at=None,
                 captured_at=None, corpus="web", mime_type="text/plain", references=(), syndication_key=None):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("source_integrity")
    return {"text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "url": url, "retrieved_at": retrieved_at, "captured_at": captured_at, "published_at": published_at,
        "coverage": coverage, "title": title, "publisher": publisher, "corpus": corpus, "mime_type": mime_type,
        "references": list(references), "syndication_key": syndication_key}


def source_passages(source_id, source):
    text = source["text"]
    if hashlib.sha256(text.encode()).hexdigest() != source["text_sha256"]:
        raise ValueError("source_integrity")
    result = []
    for match in re.finditer(r"[^\n]+", text):
        start, end = match.span()
        while start < end:
            stop = min(start + 2000, end)
            if stop < end:
                boundary = text.rfind(" ", start + 1000, stop)
                if boundary > start:
                    stop = boundary
            part = text[start:stop]
            if part.strip():
                digest = hashlib.sha256(part.encode()).hexdigest()
                result.append({"passage_id": f"{source_id}:p{len(result) + 1}", "source_id": source_id,
                    "start_char": start, "end_char": stop, "text_sha256": digest, "text": part})
            start = stop
    return result


def select_passages(source_id, source, *, ticker, issuer_name=None, query=None, offset=0, limit=None):
    passages = source_passages(source_id, source)
    # A short HTML notice can have hundreds of tiny lines. Keep its complete text
    # within the existing 12 x 2000 character selection envelope, not 12 fragments.
    complete = limit is None and offset == 0 and len(source["text"]) <= 12 * 2000
    limit = len(passages) if complete else (12 if limit is None else limit)
    def has(text, term):
        return bool(term and re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text, re.I))
    event = re.compile(r"delist|ceased|effective|common\s+(?:stock|share)|ordinary\s+shares|notes|bond|remain|continu|cancel|pending|acquisit|merger", re.I)
    scores = {i: 8 * has(item["text"], ticker) + 12 * has(item["text"], issuer_name)
        + 3 * bool(event.search(item["text"])) + sum(20 * has(item["text"], term) for term in (query.split() if query else []))
        for i, item in enumerate(passages)}
    # Rank exact target/query matches ahead of site navigation; every remainder remains pageable.
    ranked = {i: max(score, max((scores.get(j, 0) - 1 for j in (i - 1, i + 1)), default=0)) for i, score in scores.items()}
    indices = list(range(len(passages))) if complete and not query else sorted(ranked, key=lambda i: (-ranked[i], i))
    selected = [passages[i] for i in indices[offset:offset + limit]]
    return {"passages": selected, "total_passages": len(passages), "matching_passages": len(indices),
        "next_offset": offset + limit if len(indices) > offset + limit else None,
        "input_coverage": "full_text" if len(selected) == len(passages) else "selected_passages"}


def same_source(left, right):
    return (left["text_sha256"] == right["text_sha256"] or
        (left.get("url") is not None and left["url"] == right.get("url")) or
        (left.get("syndication_key") is not None and left["syndication_key"] == right.get("syndication_key")))


def select_references(source, *, ticker, issuer_name=None, query=None, offset=0, limit=16):
    terms = [ticker, issuer_name, *(query.split() if query else [])]
    def score(item):
        text = item["label"] + " " + item["url"]
        return sum(5 for term in terms if term and term.lower() in text.lower()) + (3 if re.search(r"(?:edgar|archive|original|filing|press-release|item.?3.01|8-k)", text, re.I) else 0)
    items = sorted(source["references"], key=lambda item: -score(item))
    return {"references": items[offset:offset + limit], "total_references": len(items),
        "next_reference_offset": offset + limit if len(items) > offset + limit else None}


def public_references(body, content_type, url):
    if "html" not in content_type:
        return []
    class Links(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.values = []
            self.href = None
            self.label = []

        def handle_starttag(self, tag, attrs):
            if tag == "a":
                self.href, self.label = dict(attrs).get("href"), []

        def handle_data(self, data):
            if self.href:
                self.label.append(data)

        def handle_endtag(self, tag):
            if tag == "a" and self.href:
                try:
                    value = canonical_source_url(urljoin(url, self.href))
                except SourceReadError:
                    value = None
                if value and value != url:
                    self.values.append({"url": value, "label": " ".join(" ".join(self.label).split())})
                self.href = None
    from email.message import Message
    header = Message()
    header["Content-Type"] = content_type
    parser = Links()
    parser.feed(body.decode(header.get_content_charset() or "utf-8-sig", errors="strict"))
    parser.close()
    seen, result = set(), []
    for item in parser.values:
        if item["url"] not in seen:
            seen.add(item["url"])
            result.append(item)
    return result


class InvestigationSourceReader(PublicSourceReader):
    def __init__(self, limits, **kwargs):
        self.references = {}
        super().__init__(limits, document_observer=self._document, **kwargs)

    def _document(self, url, body, content_type):
        self.references[url] = public_references(body, content_type, url)
