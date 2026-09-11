"""Isolated, single-attempt public HTTPS evidence retrieval for Lifecycle.

This is not a browser or a general Research tool. DNS is resolved once per hop;
the actual connection is pinned to an admitted address while TLS verifies the
original hostname. It sends no profile, model credential, cookies or proxy auth.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
from datetime import datetime, timezone
from email.message import Message
from html.parser import HTMLParser
import hashlib
import http.client
import ipaddress
import json
import math
import re
import socket
import ssl
from threading import BoundedSemaphore, Event, Lock, Thread, Timer
import time
import zlib
from typing import Callable
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit


class SourceReadError(ValueError):
    """Typed, content-free retrieval or citation failure."""


# A stalled system resolver cannot accumulate unbounded abandoned workers.
_DNS_SLOTS = BoundedSemaphore(4)


def _public_address(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    if not address.is_global or address.is_multicast or address.is_unspecified:
        return False
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None or address.sixtofour is not None or address.teredo is not None:
            return False
    return True


def canonical_source_url(value: str) -> str:
    if (type(value) is not str or not value
            or "\\" in value or any(ord(ch) <= 32 or ord(ch) == 127 for ch in value)):
        raise SourceReadError("unsafe_source_url")
    try:
        encoded = value.encode("utf-8")
    except UnicodeError:
        raise SourceReadError("unsafe_source_url") from None
    if len(encoded) > 1000:
        raise SourceReadError("unsafe_source_url")
    decoded = unquote(value)
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in decoded):
        raise SourceReadError("unsafe_source_url")
    try:
        parts = urlsplit(value)
        host, port = parts.hostname, parts.port
    except ValueError:
        raise SourceReadError("unsafe_source_url") from None
    if (parts.scheme != "https" or not host or port not in (None, 443)
            or parts.username is not None or parts.password is not None):
        raise SourceReadError("unsafe_source_url")
    host = host.rstrip(".").lower()
    if not host.isascii() or "%" in host:
        raise SourceReadError("unsafe_source_url")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
        if (host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost")
                or len(host) > 253 or "." not in host
                or any(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) is None
                       for label in host.split("."))):
            raise SourceReadError("unsafe_source_url")
    if address is not None and not _public_address(host):
        raise SourceReadError("unsafe_source_url")
    authority = f"[{host}]" if ":" in host else host
    path = quote(parts.path or "/", safe="/%:@!$&'()*+,;=-._~")
    query = quote(parts.query, safe="/%?:@!$&'()*+,;=-._~")
    result = urlunsplit(("https", authority, path, query, ""))
    if len(result) > 1000:
        raise SourceReadError("unsafe_source_url")
    return result


@dataclass(frozen=True)
class SourceReadLimits:
    max_requests: int
    max_redirects: int
    max_response_bytes: int
    timeout_seconds: float
    max_decoded_bytes: int | None = None

    def __post_init__(self) -> None:
        if (type(self.max_requests) is not int or self.max_requests <= 0
                or type(self.max_redirects) is not int or self.max_redirects < 0
                or type(self.max_response_bytes) is not int or self.max_response_bytes <= 0
                or (self.max_decoded_bytes is not None and
                    (type(self.max_decoded_bytes) is not int or self.max_decoded_bytes <= 0))
                or type(self.timeout_seconds) not in (float, int)
                or not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0):
            raise SourceReadError("source_read_limits")

    @property
    def decoded_byte_limit(self) -> int:
        return self.max_response_bytes if self.max_decoded_bytes is None else self.max_decoded_bytes


@dataclass(frozen=True)
class SourceReadObservation:
    request_index: int
    status: int | None
    framing: str | None
    content_encoding: str | None
    declared_body_bytes: int | None
    received_body_bytes: int
    decoded_body_bytes: int
    result_code: str


def validate_source_read_report(value, *, max_requests):
    if (type(value) is not dict or set(value) != {"requests", "observations"}
            or type(value["requests"]) is not int or not 0 <= value["requests"] <= max_requests
            or type(value["observations"]) is not list or len(value["observations"]) > value["requests"]):
        raise SourceReadError("source_read_report_invalid")
    expected = {field.name for field in fields(SourceReadObservation)}
    previous, observations = 0, []
    for item in value["observations"]:
        if (type(item) is not dict or set(item) != expected
                or type(item["request_index"]) is not int or not previous < item["request_index"] <= value["requests"]
                or (item["status"] is not None and (type(item["status"]) is not int or not 100 <= item["status"] <= 599))
                or item["framing"] not in (None, "chunked", "content_length", "close_delimited")
                or item["content_encoding"] not in (None, "identity", "gzip", "unsupported")
                or any(type(item[key]) is not int or not 0 <= item[key] < 2 ** 53
                       for key in ("received_body_bytes", "decoded_body_bytes"))
                or (item["declared_body_bytes"] is not None and
                    (type(item["declared_body_bytes"]) is not int or not 0 <= item["declared_body_bytes"] < 2 ** 53))
                or type(item["result_code"]) is not str or re.fullmatch(r"[a-z_]{1,100}", item["result_code"]) is None):
            raise SourceReadError("source_read_report_invalid")
        observations.append(asdict(SourceReadObservation(**item)))
        previous = item["request_index"]
    return {"requests": value["requests"], "observations": observations}


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, address: tuple, *, timeout: float):
        super().__init__(host, 443, timeout=timeout, context=ssl.create_default_context())
        self._address = address
        self._socket_lock = Lock()
        self._aborted = Event()
        # HTTPResponse may own the stream after getresponse clears self.sock.
        self._transport_socket = None

    def connect(self) -> None:
        family, endpoint = self._address
        raw = socket.socket(family, socket.SOCK_STREAM)
        try:
            with self._socket_lock:
                if self._aborted.is_set():
                    raise OSError("source transport closed")
                self._transport_socket = raw
            raw.settimeout(self.timeout)
            raw.connect(endpoint)
            wrapped = self._context.wrap_socket(raw, server_hostname=self.host, do_handshake_on_connect=False)
            with self._socket_lock:
                if self._aborted.is_set():
                    wrapped.close()
                    raise OSError("source transport closed")
                self.sock = wrapped
                self._transport_socket = wrapped
            wrapped.do_handshake()
        except BaseException:
            raw.close()
            raise

    def abort(self) -> None:
        self._aborted.set()
        with self._socket_lock:
            stream = self._transport_socket
            self._transport_socket = None
            if stream is not None:
                try:
                    stream.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                stream.close()


class _SourceTextParser(HTMLParser):
    _SKIP = frozenset({"head", "script", "style", "template", "noscript", "svg", "canvas"})
    _VOID = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"})
    _BREAK = frozenset({"p", "div", "br", "li", "tr", "td", "h1", "h2", "h3", "h4", "section", "article"})

    def __init__(self, check=lambda: None):
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool]] = []
        self.positions: dict[str, list[int]] = {}
        self.parts: list[str] = []
        self.check = check

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.check()
        attributes = dict(attrs)
        hidden = (bool(self.stack and self.stack[-1][1]) or tag in self._SKIP
                  or "hidden" in attributes or (attributes.get("aria-hidden") or "").lower() == "true")
        if tag in self._BREAK and not hidden:
            self.parts.append("\n")
        if tag not in self._VOID:
            self.positions.setdefault(tag, []).append(len(self.stack))
            self.stack.append((tag, hidden))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in self._VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        self.check()
        # Missing closing tags must not turn a large, malformed document quadratic.
        positions = self.positions.get(tag)
        if positions:
            index = positions[-1]
            for open_tag, _ in self.stack[index:]:
                self.positions[open_tag].pop()
            del self.stack[index:]
        if tag in self._BREAK and not (self.stack and self.stack[-1][1]):
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.check()
        if not self.stack or not self.stack[-1][1]:
            self.parts.append(data)


@dataclass(frozen=True)
class PublicSourcePage:
    url: str
    redirect_chain: tuple[str, ...]
    body_sha256: str
    text_sha256: str
    text: str
    mime_type: str
    retrieved_at: str
    capture_sha256: str = ""


def _page_material_digest(material: dict) -> str:
    """Keep legacy canonical JSON hashes without a source-sized escaped copy."""
    digest = hashlib.sha256()
    digest.update(b"{")
    for index, key in enumerate(sorted(material)):
        if index:
            digest.update(b",")
        digest.update(json.dumps(key, ensure_ascii=True).encode("ascii"))
        digest.update(b":")
        value = material[key]
        if isinstance(value, str):
            digest.update(b'"')
            for offset in range(0, len(value), 65536):
                # JSON string escaping is composable at Python character boundaries.
                escaped = json.dumps(value[offset:offset + 65536], ensure_ascii=True)[1:-1]
                digest.update(escaped.encode("ascii"))
            digest.update(b'"')
        else:
            digest.update(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True, allow_nan=False).encode("ascii"))
    digest.update(b"}")
    return digest.hexdigest()


def _capture_digest(page: PublicSourcePage) -> str:
    material = asdict(page)
    material.pop("capture_sha256")
    return _page_material_digest(material)


def _normalize_text(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[^\S\n]+", " ", text)
    return re.sub(r" *\n[ \n]*", "\n", text).strip()


def _json_document(text: str) -> None:
    def object_pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError("duplicate key")
            value[key] = item
        return value

    def invalid_constant(value):
        raise ValueError("non-JSON constant")

    try:
        # Validate, but retain the original number and string representations.
        json.loads(text, object_pairs_hook=object_pairs, parse_constant=invalid_constant,
                   parse_float=str, parse_int=str)
    except (ValueError, RecursionError):
        raise SourceReadError("source_document_invalid") from None


def _xml_text(body: bytes, check) -> str:
    from defusedxml.ElementTree import DefusedXMLParser, ParseError
    from defusedxml.common import DefusedXmlException
    from xml.etree.ElementTree import C14NWriterTarget

    parts = []

    def write(value):
        check()
        parts.append(value)

    # Keep namespaces, record boundaries and mixed content without building a
    # DOM or repeating a parent field name for every child/attribute.
    parser = DefusedXMLParser(target=C14NWriterTarget(write), forbid_dtd=True, forbid_entities=True, forbid_external=True)
    try:
        for offset in range(0, len(body), 65536):
            check()
            parser.feed(body[offset:offset + 65536])
        parser.close()
        return "".join(parts)
    except SourceReadError:
        raise
    except (ParseError, DefusedXmlException, ValueError, RecursionError):
        raise SourceReadError("source_document_invalid") from None


def _page_text(body: bytes, content_type: str, *, check=lambda: None) -> tuple[str, str]:
    header = Message()
    header["Content-Type"] = content_type
    mime = header.get_content_type()
    if mime not in {"text/plain", "text/html", "application/xhtml+xml", "application/xml", "text/xml", "application/json"}:
        raise SourceReadError("source_format_unsupported")
    if mime in {"application/xml", "text/xml"}:
        text = _xml_text(body, check)
    else:
        charset = header.get_content_charset() or "utf-8-sig"
        try:
            text = body.decode(charset, errors="strict")
        except (LookupError, UnicodeError):
            raise SourceReadError("source_encoding_unsupported") from None
        if mime == "application/json":
            _json_document(text)
        elif mime != "text/plain":
            parser = _SourceTextParser(check)
            for offset in range(0, len(text), 65536):
                check()
                parser.feed(text[offset:offset + 65536])
            parser.close()
            text = "".join(parser.parts)
    text = text.strip() if mime in {"application/json", "application/xml", "text/xml"} else _normalize_text(text)
    check()
    if not text:
        raise SourceReadError("source_text_empty")
    return text, mime


class PublicSourceReader:
    """One operation's bounded reader; never retries a failed hop or address.

    DNS may finish after cancellation, but its bounded worker cannot dispatch an
    HTTP request. The caller stops waiting at its deadline or stop request.
    """

    def __init__(self, limits: SourceReadLimits, *, now: Callable[[], datetime] | None = None, sec_policy=None,
                 document_observer=None, text_extractor=None):
        self.limits = limits
        self.deadline = time.monotonic() + limits.timeout_seconds
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._stop = Event()
        self._lock = Lock()
        self._request_count = 0
        self._active_connection: _PinnedHTTPSConnection | None = None
        self._read_lock = Lock()
        self.sec_policy = sec_policy
        self.document_observer = document_observer
        self.text_extractor = text_extractor
        self._observations: list[SourceReadObservation] = []

    @property
    def observations(self) -> tuple[SourceReadObservation, ...]:
        with self._lock:
            return tuple(self._observations)

    @property
    def request_count(self) -> int:
        with self._lock:
            return self._request_count

    def request_stop(self) -> None:
        self._stop.set()
        with self._lock:
            if self._active_connection is not None:
                self._active_connection.abort()

    def _remaining(self) -> float:
        if self._stop.is_set():
            raise SourceReadError("source_read_cancelled")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise SourceReadError("source_read_timeout")
        return remaining

    def _address(self, host: str) -> tuple:
        self._remaining()
        slots = _DNS_SLOTS
        if not slots.acquire(blocking=False):
            raise SourceReadError("source_dns_busy")
        completed = Event()
        result = []
        failure = []

        def resolve() -> None:
            try:
                result.extend(socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP))
            except Exception as exc:
                failure.append(exc)
            finally:
                slots.release()
                completed.set()

        worker = Thread(target=resolve, name="lifecycle-public-dns", daemon=True)
        try:
            worker.start()
        except RuntimeError:
            slots.release()
            raise SourceReadError("source_dns_unavailable") from None
        while not completed.wait(min(0.05, self._remaining())):
            self._remaining()
        self._remaining()
        if failure:
            raise SourceReadError("source_dns_unavailable") from None
        addresses = []
        for family, kind, proto, _, endpoint in result:
            if (family not in {socket.AF_INET, socket.AF_INET6} or kind != socket.SOCK_STREAM
                    or proto != socket.IPPROTO_TCP or not _public_address(endpoint[0])
                    or endpoint[1] != 443 or (family == socket.AF_INET6 and endpoint[3] != 0)):
                raise SourceReadError("unsafe_source_address")
            addresses.append((family, endpoint))
        if not addresses:
            raise SourceReadError("source_dns_unavailable")
        return addresses[0]

    def read(self, url: str) -> PublicSourcePage:
        if not self._read_lock.acquire(blocking=False):
            raise SourceReadError("source_read_pending")
        try:
            return self._read(url)
        finally:
            self._read_lock.release()

    def _read(self, url: str) -> PublicSourcePage:
        current = canonical_source_url(url)
        redirects: list[str] = []
        while True:
            self._remaining()
            with self._lock:
                if self._request_count >= self.limits.max_requests:
                    raise SourceReadError("source_request_budget_exhausted")
            parts = urlsplit(current)
            user_agent = "ArkScope-Lifecycle/1.0"
            if parts.hostname == "sec.gov" or parts.hostname.endswith(".sec.gov"):
                if self.sec_policy is None:
                    from src.lifecycle_web_sec_sources import SecSourcePolicy
                    self.sec_policy = SecSourcePolicy()
                user_agent = self.sec_policy.prepare(current, check=self._remaining)
            address = self._address(parts.hostname)
            with self._lock:
                remaining = self._remaining()
                if self._request_count >= self.limits.max_requests:
                    raise SourceReadError("source_request_budget_exhausted")
                self._request_count += 1
            connection = _PinnedHTTPSConnection(parts.hostname, address, timeout=remaining)
            timer = Timer(remaining, connection.abort)
            timer.daemon = True
            response = None
            observed = dict(request_index=self.request_count, status=None, framing=None, content_encoding=None,
                            declared_body_bytes=None, received_body_bytes=0, decoded_body_bytes=0,
                            result_code="source_transport_unavailable")
            try:
                with self._lock:
                    self._active_connection = connection
                self._remaining()
                timer.start()
                connection.request("GET", parts.path + ("?" + parts.query if parts.query else ""), headers={
                    "Accept": "text/html,application/xhtml+xml,text/plain,application/xml,text/xml,application/json",
                    "Accept-Encoding": "gzip, identity", "User-Agent": user_agent,
                    "Connection": "close",
                })
                response = connection.getresponse()
                observed["status"] = response.status
                self._remaining()
                if response.status in {301, 302, 303, 307, 308}:
                    if len(redirects) >= self.limits.max_redirects:
                        raise SourceReadError("source_redirect_limit")
                    location = response.getheader("Location")
                    if not isinstance(location, str) or not location:
                        raise SourceReadError("source_response_invalid")
                    destination = canonical_source_url(urljoin(current, location))
                    if destination == current or destination in redirects:
                        raise SourceReadError("source_redirect_limit")
                    redirects.append(current)
                    current = destination
                    observed["result_code"] = "redirect"
                    continue
                if response.status == 429:
                    raise SourceReadError("source_rate_limited")
                if response.status != 200:
                    raise SourceReadError("source_unavailable")
                body = self._body(response, observed)
                extractor = _page_text if self.text_extractor is None else self.text_extractor
                text, mime = extractor(body, response.getheader("Content-Type", "application/octet-stream"), check=self._remaining)
                if self.document_observer is not None:
                    self.document_observer(current, body, response.getheader("Content-Type", "application/octet-stream"))
                    self._remaining()
                observed_at = self._now()
                if observed_at.tzinfo is None or observed_at.utcoffset() is None:
                    raise SourceReadError("source_observation_time")
                self._remaining()
                page = PublicSourcePage(
                    current, tuple(redirects), hashlib.sha256(body).hexdigest(),
                    hashlib.sha256(text.encode()).hexdigest(), text, mime, observed_at.isoformat(),
                )
                page = replace(page, capture_sha256=_capture_digest(page))
                self._remaining()
                observed["result_code"] = "complete"
                return page
            except SourceReadError as exc:
                observed["result_code"] = str(exc)
                raise
            except (TimeoutError, socket.timeout):
                observed["result_code"] = "source_read_timeout"
                raise SourceReadError("source_read_timeout") from None
            except (OSError, http.client.HTTPException):
                try:
                    self._remaining()
                except SourceReadError as exc:
                    observed["result_code"] = str(exc)
                    raise
                raise SourceReadError("source_transport_unavailable") from None
            finally:
                timer.cancel()
                if timer.ident is not None:
                    timer.join()
                connection.abort()
                if response is not None:
                    response.close()
                connection.close()
                with self._lock:
                    self._active_connection = None
                    self._observations.append(SourceReadObservation(**observed))

    def _body(self, response, observed) -> bytes:
        transfer = response.getheader("Transfer-Encoding")
        length_header = response.getheader("Content-Length")
        if transfer is not None and (transfer.strip().lower() != "chunked" or length_header is not None):
            raise SourceReadError("source_framing_invalid")
        observed["framing"] = "chunked" if transfer is not None else "close_delimited"
        if transfer is not None and isinstance(response, http.client.HTTPResponse) and not response.chunked:
            # The stdlib does not strip trailing OWS when recognising chunked.
            response.chunked, response.chunk_left, response.length = True, None, None
        length = None
        if length_header is not None:
            parts = [part.strip() for part in length_header.split(",")]
            if any(not part.isascii() or not part.isdecimal() for part in parts):
                raise SourceReadError("source_response_invalid")
            normalized = {part.lstrip("0") or "0" for part in parts}
            if len(normalized) != 1:
                raise SourceReadError("source_framing_invalid")
            value = normalized.pop()
            if len(value) > 20:
                raise SourceReadError("source_body_too_large")
            length = int(value)
            observed.update(framing="content_length", declared_body_bytes=length if length < 2 ** 53 else None)
            if length > self.limits.max_response_bytes:
                raise SourceReadError("source_body_too_large")
        encoding = response.getheader("Content-Encoding", "identity").strip().lower()
        observed["content_encoding"] = encoding if encoding in {"identity", "gzip"} else "unsupported"
        if encoding not in {"identity", "gzip"}:
            raise SourceReadError("source_encoding_unsupported")
        body = bytearray()
        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS) if encoding == "gzip" else None
        decoded_limit = self.limits.decoded_byte_limit
        while True:
            self._remaining()
            if length is not None and observed["received_body_bytes"] == length:
                break
            try:
                remaining = self.limits.max_response_bytes + 1 - observed["received_body_bytes"]
                if length is not None:
                    remaining = min(remaining, length - observed["received_body_bytes"])
                chunk = response.read(min(65536, remaining))
            except http.client.IncompleteRead as exc:
                self._remaining()
                observed["received_body_bytes"] += len(exc.partial)
                raise SourceReadError("source_body_incomplete") from None
            self._remaining()
            observed["received_body_bytes"] += len(chunk)
            if observed["received_body_bytes"] > self.limits.max_response_bytes:
                raise SourceReadError("source_body_too_large")
            if not chunk:
                break
            while chunk:
                self._remaining()
                if decoder is None:
                    decoded, chunk = chunk, b""
                else:
                    if decoder.eof:
                        decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
                    try:
                        decoded = decoder.decompress(chunk, min(65536, decoded_limit + 1 - len(body)))
                    except zlib.error:
                        raise SourceReadError("source_compression_invalid") from None
                    chunk = decoder.unused_data if decoder.eof else decoder.unconsumed_tail
                observed["decoded_body_bytes"] += len(decoded)
                if observed["decoded_body_bytes"] > decoded_limit:
                    raise SourceReadError("source_decoded_body_too_large")
                body.extend(decoded)
        if length is not None and observed["received_body_bytes"] != length:
            raise SourceReadError("source_body_incomplete")
        if decoder is not None and not decoder.eof:
            raise SourceReadError("source_compression_incomplete")
        return bytes(body)


@dataclass(frozen=True)
class SourcePassage:
    source_url: str
    source_document_sha256: str
    source_text_sha256: str
    start_byte: int
    end_byte: int
    excerpt: str
    cited_text_sha256: str
    retrieved_at: str


def cite_passage(page: PublicSourcePage, start_byte: int, end_byte: int, expected_text: str) -> SourcePassage:
    if not isinstance(page, PublicSourcePage) or page.capture_sha256 != _capture_digest(page):
        raise SourceReadError("source_integrity")
    encoded = page.text.encode("utf-8")
    if hashlib.sha256(encoded).hexdigest() != page.text_sha256:
        raise SourceReadError("source_integrity")
    if (type(start_byte) is not int or type(end_byte) is not int
            or start_byte < 0 or end_byte <= start_byte or end_byte > len(encoded)):
        raise SourceReadError("source_citation_mismatch")
    try:
        excerpt = encoded[start_byte:end_byte].decode("utf-8")
    except UnicodeError:
        raise SourceReadError("source_citation_mismatch") from None
    if not excerpt.strip() or excerpt != expected_text:
        raise SourceReadError("source_citation_mismatch")
    if len(encoded[start_byte:end_byte]) > 16000:
        raise SourceReadError("source_excerpt_too_large")
    return SourcePassage(
        page.url, page.body_sha256, page.text_sha256, start_byte, end_byte,
        excerpt, hashlib.sha256(excerpt.encode()).hexdigest(), page.retrieved_at,
    )
