import hashlib
import socket
from datetime import datetime, timezone

import pytest


PUBLIC_IP = "93.184.216.34"
NOW = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)


class Response:
    def __init__(self, body=b"A complete public notice.", status=200, headers=None):
        self.body = body
        self.status = status
        self.headers = {"Content-Type": "text/plain; charset=utf-8", **(headers or {})}

    def getheader(self, name, default=None):
        return self.headers.get(name, default)

    def read(self, size):
        part, self.body = self.body[:size], self.body[size:]
        return part

    def close(self):
        self.body = b""


class Connection:
    def __init__(self, response):
        self.response = response
        self.requests = []
        self.closed = False
        self.sock = None

    def request(self, method, path, *, headers):
        self.requests.append((method, path, headers))

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True

    def abort(self):
        self.close()


@pytest.fixture(autouse=True)
def deny_real_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("test attempted a real network connection")
    monkeypatch.setattr(socket, "getaddrinfo", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket.socket, "connect", denied)


def _reader(monkeypatch, responses=None, addresses=None, **limit_overrides):
    from src import lifecycle_public_sources as mod

    queue = list(responses or [Response()])
    connections, resolutions, destinations = [], [], []

    def resolve(host, port, **kwargs):
        resolutions.append((host, port))
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, port))
                for ip in (addresses or [PUBLIC_IP])]

    def connect(host, address, *, timeout):
        destinations.append((host, address, timeout))
        connection = Connection(queue.pop(0))
        connections.append(connection)
        return connection

    monkeypatch.setattr(mod.socket, "getaddrinfo", resolve)
    monkeypatch.setattr(mod, "_PinnedHTTPSConnection", connect)
    limits = mod.SourceReadLimits(**{
        "max_requests": 4, "max_redirects": 2, "max_response_bytes": 65536,
        "timeout_seconds": 10.0, **limit_overrides,
    })
    reader = mod.PublicSourceReader(limits, now=lambda: NOW)
    return reader, connections, resolutions, destinations


def test_public_source_preserves_complete_unicode_and_document_digest(monkeypatch):
    body = "Issuer Old Ltd. announces 更名, effective September 6, 2026.".encode()
    reader, connections, resolutions, destinations = _reader(monkeypatch, [Response(body)])
    result = reader.read("https://ir.example.com/notice#details")
    assert result.url == "https://ir.example.com/notice"
    assert result.body_sha256 == hashlib.sha256(body).hexdigest()
    assert result.text == body.decode()
    assert result.text_sha256 == hashlib.sha256(result.text.encode()).hexdigest()
    assert result.retrieved_at == NOW.isoformat()
    assert resolutions == [("ir.example.com", 443)]
    assert destinations[0][0] == "ir.example.com"
    assert destinations[0][1][1] == (PUBLIC_IP, 443)
    assert connections[0].closed
    assert reader.request_count == 1


def test_source_request_does_not_inherit_cookies_auth_or_proxies(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://private-proxy:8080")
    monkeypatch.setenv("OPENAI_API_KEY", "secret-not-for-pages")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret-not-for-pages")
    reader, connections, _, _ = _reader(monkeypatch)
    reader.read("https://ir.example.com/a?q=notice")
    method, path, headers = connections[0].requests[0]
    assert (method, path) == ("GET", "/a?q=notice")
    assert set(headers) == {"Accept", "Accept-Encoding", "User-Agent", "Connection"}
    assert headers["Accept-Encoding"] == "gzip, identity"
    assert "secret" not in repr(headers) and "private-proxy" not in repr(headers)


@pytest.mark.parametrize("url", [
    "http://example.com", "file:///etc/passwd", "https://u:p@example.com",
    "https://example.com:8443/a", "https://localhost/a", "https://127.0.0.1",
    "https://[::1]", "https://169.254.169.254/latest/meta-data",
    "https://example.com\\@127.0.0.1/", "https://example.com/\nnotice",
    "https://example.com/\tnotice", "https://exa mple.com",
    "https://example.com/%0d%0aInjected:yes", "https://[::ffff:127.0.0.1]",
    "https://example.com/\ud800",
])
def test_unsafe_url_is_rejected_before_dns_and_transport(monkeypatch, url):
    from src.lifecycle_public_sources import SourceReadError

    reader, connections, resolutions, _ = _reader(monkeypatch)
    with pytest.raises(SourceReadError, match="unsafe_source_url"):
        reader.read(url)
    assert connections == [] and resolutions == [] and reader.request_count == 0


@pytest.mark.parametrize("addresses", [
    ["10.0.0.1"], [PUBLIC_IP, "192.168.1.1"], ["100.64.0.1"], ["0.0.0.0"],
    ["192.0.2.1"], ["224.0.0.1"],
])
def test_dns_with_any_nonpublic_address_cannot_connect(monkeypatch, addresses):
    from src.lifecycle_public_sources import SourceReadError

    reader, connections, resolutions, _ = _reader(monkeypatch, addresses=addresses)
    with pytest.raises(SourceReadError, match="unsafe_source_address"):
        reader.read("https://ir.example.com/notice")
    assert resolutions == [("ir.example.com", 443)] and connections == []


def test_redirect_to_private_destination_does_not_fetch_it(monkeypatch):
    from src.lifecycle_public_sources import SourceReadError

    reader, connections, _, destinations = _reader(monkeypatch, [
        Response(status=302, headers={"Location": "https://127.0.0.1/private"}),
    ])
    with pytest.raises(SourceReadError, match="unsafe_source_url"):
        reader.read("https://ir.example.com/start")
    assert len(destinations) == 1 and connections[0].closed
    assert reader.request_count == 1


def test_relative_redirect_is_resolved_and_each_request_counted(monkeypatch):
    reader, connections, _, _ = _reader(monkeypatch, [
        Response(status=302, headers={"Location": "../final"}), Response(),
    ])
    result = reader.read("https://ir.example.com/news/start")
    assert result.url == "https://ir.example.com/final"
    assert result.redirect_chain == ("https://ir.example.com/news/start",)
    assert reader.request_count == 2 and all(c.closed for c in connections)


def test_redirect_limit_rejects_instead_of_returning_partial_source(monkeypatch):
    from src.lifecycle_public_sources import SourceReadError

    reader, connections, _, _ = _reader(monkeypatch, [
        Response(status=302, headers={"Location": "/next"}),
    ], max_redirects=0)
    with pytest.raises(SourceReadError, match="source_redirect_limit"):
        reader.read("https://ir.example.com/start")
    assert reader.request_count == 1 and connections[0].closed


def test_byte_limit_never_silently_truncates_even_without_content_length(monkeypatch):
    from src.lifecycle_public_sources import SourceReadError

    reader, connections, _, _ = _reader(monkeypatch, [Response(b"123456789")], max_response_bytes=8)
    with pytest.raises(SourceReadError, match="source_body_too_large"):
        reader.read("https://ir.example.com/notice")
    assert connections[0].closed


@pytest.mark.parametrize("headers,body,code", [
    ({"Content-Type": "application/pdf"}, b"%PDF", "source_format_unsupported"),
    ({"Content-Encoding": "gzip"}, b"compressed", "source_compression_invalid"),
    ({"Content-Length": "9"}, b"short", "source_body_incomplete"),
    ({"Content-Length": "bad"}, b"text", "source_response_invalid"),
    ({"Content-Type": "text/plain; charset=not-a-codec"}, b"text", "source_encoding_unsupported"),
    ({}, b"\xff", "source_encoding_unsupported"),
    ({}, b"", "source_text_empty"),
])
def test_invalid_source_response_is_not_usable_evidence(monkeypatch, headers, body, code):
    from src.lifecycle_public_sources import SourceReadError

    reader, connections, _, _ = _reader(monkeypatch, [Response(body, headers=headers)])
    with pytest.raises(SourceReadError, match=code):
        reader.read("https://ir.example.com/notice")
    assert connections[0].closed


def test_failed_request_consumes_budget_and_has_no_retry(monkeypatch):
    from src.lifecycle_public_sources import SourceReadError

    reader, connections, _, _ = _reader(monkeypatch, [Response(status=429)], max_requests=1)
    with pytest.raises(SourceReadError, match="source_rate_limited"):
        reader.read("https://ir.example.com/notice")
    with pytest.raises(SourceReadError, match="source_request_budget_exhausted"):
        reader.read("https://ir.example.com/notice")
    assert len(connections) == 1 and reader.request_count == 1


@pytest.mark.parametrize("cancel", [False, True])
def test_blocked_dns_releases_caller_without_late_http(monkeypatch, cancel):
    from threading import Event, Thread
    from src import lifecycle_public_sources as mod

    reader, connections, _, _ = _reader(monkeypatch, timeout_seconds=0.1 if not cancel else 5)
    entered, release, exited = Event(), Event(), Event()
    result = []

    def resolve(*args, **kwargs):
        entered.set()
        release.wait(3)
        exited.set()
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (PUBLIC_IP, 443))]

    def read():
        try:
            reader.read("https://ir.example.com/notice")
        except Exception as exc:
            result.append(exc)

    monkeypatch.setattr(mod.socket, "getaddrinfo", resolve)
    worker = Thread(target=read)
    worker.start()
    try:
        assert entered.wait(1)
        if cancel:
            reader.request_stop()
        worker.join(1)
        assert not worker.is_alive(), "DNS prevented cancellation/deadline from releasing the caller"
        assert len(result) == 1 and isinstance(result[0], mod.SourceReadError)
        assert str(result[0]) == ("source_read_cancelled" if cancel else "source_read_timeout")
    finally:
        release.set()
        worker.join(3)
        assert exited.wait(1)
    assert connections == [] and reader.request_count == 0


def test_dns_saturation_refuses_new_resolution_without_waiting(monkeypatch):
    from threading import BoundedSemaphore
    from src import lifecycle_public_sources as mod

    reader, connections, resolutions, _ = _reader(monkeypatch)
    slots = BoundedSemaphore(1)
    slots.acquire()
    monkeypatch.setattr(mod, "_DNS_SLOTS", slots, raising=False)
    with pytest.raises(mod.SourceReadError, match="source_dns_busy"):
        reader.read("https://ir.example.com/notice")
    assert connections == [] and resolutions == []


def test_stop_during_dns_prevents_late_http_dispatch(monkeypatch):
    from src import lifecycle_public_sources as mod

    reader, connections, _, _ = _reader(monkeypatch)
    original = mod.socket.getaddrinfo

    def resolve(*args, **kwargs):
        result = original(*args, **kwargs)
        reader.request_stop()
        return result

    monkeypatch.setattr(mod.socket, "getaddrinfo", resolve)
    with pytest.raises(mod.SourceReadError, match="source_read_cancelled"):
        reader.read("https://ir.example.com/notice")
    assert connections == [] and reader.request_count == 0


def test_deadline_is_checked_after_dns_before_any_connection(monkeypatch):
    from src import lifecycle_public_sources as mod

    reader, connections, _, _ = _reader(monkeypatch)
    original = mod.socket.getaddrinfo

    def resolve(*args, **kwargs):
        result = original(*args, **kwargs)
        monkeypatch.setattr(mod.time, "monotonic", lambda: reader.deadline + 1)
        return result

    monkeypatch.setattr(mod.socket, "getaddrinfo", resolve)
    with pytest.raises(mod.SourceReadError, match="source_read_timeout"):
        reader.read("https://ir.example.com/notice")
    assert connections == []


def test_html_source_excludes_noncontent_without_truncating_notice(monkeypatch):
    body = b'''<html><head><title>Notice</title><script>fake delisting</script></head>
    <body><p>Common stock OLD remains active.</p><style>not evidence</style>
    <template>stale fact</template><span hidden>not visible</span>
    <span aria-hidden="true">hidden statement</span><p>Acquisition announced only.</p></body></html>'''
    reader, _, _, _ = _reader(monkeypatch, [Response(body, headers={"Content-Type": "text/html"})])
    page = reader.read("https://ir.example.com/notice")
    assert "Common stock OLD remains active." in page.text
    assert "Acquisition announced only." in page.text
    for omitted in ("fake delisting", "not evidence", "stale fact", "not visible", "hidden statement"):
        assert omitted not in page.text
    assert page.body_sha256 == hashlib.sha256(body).hexdigest()


def test_exact_passage_requires_real_source_and_byte_aligned_unicode(monkeypatch):
    from src.lifecycle_public_sources import cite_passage, SourceReadError

    text = "The company 更名 to NEW, effective 2026-09-06."
    reader, _, _, _ = _reader(monkeypatch, [Response(text.encode())])
    page = reader.read("https://ir.example.com/notice")
    start = len("The company ".encode())
    end = len("The company 更名 to NEW".encode())
    citation = cite_passage(page, start, end, "更名 to NEW")
    assert citation.source_url == page.url
    assert citation.source_document_sha256 == page.body_sha256
    assert citation.source_text_sha256 == page.text_sha256
    assert citation.excerpt == "更名 to NEW"
    assert citation.start_byte == start and citation.end_byte == end
    assert citation.cited_text_sha256 == hashlib.sha256(citation.excerpt.encode()).hexdigest()
    with pytest.raises(SourceReadError, match="source_citation_mismatch"):
        cite_passage(page, start + 1, end, "更名 to NEW")
    with pytest.raises(SourceReadError, match="source_citation_mismatch"):
        cite_passage(page, start, end, "delisted permanently")


def test_modified_page_text_cannot_reuse_source_hash(monkeypatch):
    from dataclasses import replace
    from src.lifecycle_public_sources import cite_passage, SourceReadError

    reader, _, _, _ = _reader(monkeypatch)
    page = reader.read("https://ir.example.com/notice")
    altered = replace(page, text="Invented delisting")
    with pytest.raises(SourceReadError, match="source_integrity"):
        cite_passage(altered, 0, len(altered.text), altered.text)


def test_pinned_https_transport_does_not_resolve_host_again(monkeypatch):
    from src import lifecycle_public_sources as mod

    observed = {}

    class Sock:
        def settimeout(self, value):
            observed["timeout"] = value
        def connect(self, address):
            observed["address"] = address
        def close(self):
            observed["closed"] = True
        def shutdown(self, how):
            assert how == socket.SHUT_RDWR
        def do_handshake(self):
            observed["handshake"] = True

    sock = Sock()
    monkeypatch.setattr(mod.socket, "socket", lambda family, kind: sock)

    class Context:
        verify_mode = mod.ssl.CERT_REQUIRED
        check_hostname = True

        def wrap_socket(self, actual, *, server_hostname, do_handshake_on_connect):
            assert actual is sock
            assert do_handshake_on_connect is False
            observed["tls_hostname"] = server_hostname
            return actual

    monkeypatch.setattr(mod.ssl, "create_default_context", lambda: Context())
    conn = mod._PinnedHTTPSConnection("ir.example.com", (socket.AF_INET, (PUBLIC_IP, 443)), timeout=3)
    conn.connect()
    conn.close()
    assert observed == {"timeout": 3, "address": (PUBLIC_IP, 443),
                        "tls_hostname": "ir.example.com", "closed": True, "handshake": True}


@pytest.mark.parametrize("change", [
    {"url": "https://other.example.com/false"}, {"body_sha256": "0" * 64},
    {"retrieved_at": "2030-01-01T00:00:00+00:00"},
    {"redirect_chain": ("https://elsewhere.example.com",)},
    {"mime_type": "text/html"},
])
def test_citation_cannot_rebind_captured_source_metadata(monkeypatch, change):
    from dataclasses import replace
    from src.lifecycle_public_sources import cite_passage, SourceReadError

    reader, _, _, _ = _reader(monkeypatch)
    page = reader.read("https://ir.example.com/notice")
    with pytest.raises(SourceReadError, match="source_integrity"):
        cite_passage(replace(page, **change), 0, len(page.text.encode()), page.text)


@pytest.mark.parametrize("limits", [
    {"max_requests": True}, {"max_requests": 0}, {"max_requests": "2"},
    {"max_redirects": -1}, {"max_redirects": 1.5}, {"max_response_bytes": 0},
    {"timeout_seconds": 0}, {"timeout_seconds": float("inf")},
    {"timeout_seconds": float("nan")}, {"timeout_seconds": True},
])
def test_source_limits_cannot_silently_become_unbounded(limits):
    from src.lifecycle_public_sources import SourceReadLimits, SourceReadError

    with pytest.raises(SourceReadError, match="source_read_limits"):
        SourceReadLimits(**{
            "max_requests": 3, "max_redirects": 1,
            "max_response_bytes": 1000, "timeout_seconds": 10, **limits,
        })


def test_deadline_interrupts_an_inflight_read_not_only_its_return(monkeypatch):
    from threading import Event
    from src import lifecycle_public_sources as mod

    interrupted = Event()

    class SlowResponse(Response):
        def read(self, size):
            assert interrupted.wait(1), "in-flight read was not interrupted"
            raise OSError("socket closed")

    class SlowConnection(Connection):
        def abort(self):
            interrupted.set()
            self.close()

    reader, _, _, _ = _reader(monkeypatch, timeout_seconds=0.05)
    connection = SlowConnection(SlowResponse())
    monkeypatch.setattr(mod, "_PinnedHTTPSConnection", lambda *a, **kw: connection)
    with pytest.raises(mod.SourceReadError, match="source_read_timeout"):
        reader.read("https://ir.example.com/notice")
    assert interrupted.is_set() and connection.closed


def test_cancel_interrupts_an_inflight_read_and_refuses_next_hop(monkeypatch):
    from threading import Event
    from src import lifecycle_public_sources as mod

    interrupted = Event()
    reader, _, _, _ = _reader(monkeypatch)

    class PendingResponse(Response):
        def read(self, size):
            reader.request_stop()
            assert interrupted.is_set(), "cancellation did not close the active transport"
            raise OSError("socket closed")

    class PendingConnection(Connection):
        def abort(self):
            interrupted.set()
            self.close()

    monkeypatch.setattr(mod, "_PinnedHTTPSConnection", lambda *a, **kw: PendingConnection(PendingResponse()))
    with pytest.raises(mod.SourceReadError, match="source_read_cancelled"):
        reader.read("https://ir.example.com/notice")
    with pytest.raises(mod.SourceReadError, match="source_read_cancelled"):
        reader.read("https://ir.example.com/next")
    assert reader.request_count == 1
