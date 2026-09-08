"""Real HTTP framing over local socket pairs; no DNS, TCP or TLS service calls."""

import hashlib
import http.client
import socket
from threading import Event, Thread

import pytest

from tests.test_lifecycle_public_sources import NOW, PUBLIC_IP, deny_real_network


class LocalSocket:
    def __init__(self, stream):
        self.stream = stream

    def connect(self, endpoint):
        assert endpoint == (PUBLIC_IP, 443)

    def do_handshake(self):
        pass

    def __getattr__(self, name):
        return getattr(self.stream, name)


@pytest.fixture
def wire_contexts():
    return None


@pytest.fixture
def wire(monkeypatch, wire_contexts):
    from src import lifecycle_public_sources as mod

    client, server = socket.socketpair()
    client.settimeout(3)
    server.settimeout(3)
    stream = LocalSocket(client)
    state = {
        "release_body": Event(), "response_returned": Event(), "read_entered": Event(),
        "responses": [], "requests": [], "server_errors": [], "client": client,
    }

    class Context:
        verify_mode = mod.ssl.CERT_REQUIRED
        check_hostname = True

        def wrap_socket(self, actual, *, server_hostname, do_handshake_on_connect):
            assert actual is stream and server_hostname == "ir.example.com"
            assert do_handshake_on_connect is False
            return actual

    class ObservedResponse(http.client.HTTPResponse):
        def read(self, amt=None):
            state["read_entered"].set()
            return super().read(amt)

    class ObservedConnection(mod._PinnedHTTPSConnection):
        response_class = ObservedResponse

        def getresponse(self):
            response = super().getresponse()
            state["responses"].append(response)
            state["response_returned"].set()
            if not state.get("stall_body"):
                state["release_body"].set()
            return response

    monkeypatch.setattr(mod.socket, "socket", lambda family, kind: stream)
    monkeypatch.setattr(mod.ssl, "create_default_context", lambda: wire_contexts[0] if wire_contexts else Context())
    monkeypatch.setattr(mod, "_PinnedHTTPSConnection", ObservedConnection)
    monkeypatch.setattr(mod.socket, "getaddrinfo", lambda host, port, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (PUBLIC_IP, port)),
    ])
    workers = []

    def start(*, body, framing="fixed", keep_alive=False, status=200, length=None,
              stall_body=False, timeout_seconds=5):
        state["stall_body"] = stall_body
        headers = [f"HTTP/1.1 {status} Test", "Content-Type: text/plain; charset=utf-8",
                   "Connection: keep-alive" if keep_alive else "Connection: close"]
        payload = body
        if framing == "fixed":
            headers.append(f"Content-Length: {len(body) if length is None else length}")
        elif framing == "chunked":
            headers.append("Transfer-Encoding: chunked")
            payload = f"{len(body):x}\r\n".encode() + body + b"\r\n0\r\n\r\n"
        else:
            assert framing == "eof"
        encoded_headers = ("\r\n".join(headers) + "\r\n\r\n").encode()

        def serve():
            connection = server
            try:
                if wire_contexts:
                    connection = wire_contexts[1].wrap_socket(server, server_side=True)
                request = b""
                while not request.endswith(b"\r\n\r\n"):
                    part = connection.recv(4096)
                    if not part:
                        return
                    request += part
                state["requests"].append(request)
                connection.sendall(encoded_headers)
                # The body cannot be buffered before getresponse transfers socket ownership.
                assert state["release_body"].wait(3)
                connection.sendall(payload)
            except (OSError, AssertionError) as exc:
                state["server_errors"].append(type(exc).__name__)
            finally:
                connection.close()

        worker = Thread(target=serve)
        workers.append(worker)
        worker.start()
        return mod.PublicSourceReader(mod.SourceReadLimits(
            max_requests=1, max_redirects=0, max_response_bytes=65536,
            timeout_seconds=timeout_seconds,
        ), now=lambda: NOW)

    yield start, state
    state["release_body"].set()
    for response in state["responses"]:
        response.close()
    client.close()
    server.close()
    for worker in workers:
        worker.join(3)
        assert not worker.is_alive()


@pytest.mark.parametrize("framing,keep_alive", [
    ("fixed", False), ("chunked", False), ("eof", False), ("fixed", True),
])
def test_response_owned_body_survives_connection_close(wire, framing, keep_alive):
    start, state = wire
    body = ("A public common-stock notice. " * 600 + "Complete final sentence.").encode()
    reader = start(body=body, framing=framing, keep_alive=keep_alive)
    page = reader.read("https://ir.example.com/notice")
    assert page.text == body.decode()
    assert page.body_sha256 == hashlib.sha256(body).hexdigest()
    assert len(state["requests"]) == reader.request_count == 1
    assert state["server_errors"] == []
    assert state["responses"][0].isclosed()
    assert state["client"].fileno() == -1


def test_real_truncated_response_remains_rejected(wire):
    from src.lifecycle_public_sources import SourceReadError

    start, state = wire
    reader = start(body=b"Incomplete notice", length=1000)
    with pytest.raises(SourceReadError, match="^source_body_incomplete$"):
        reader.read("https://ir.example.com/notice")
    assert reader.request_count == len(state["requests"]) == 1
    assert state["responses"][0].isclosed()
    assert state["client"].fileno() == -1


@pytest.mark.parametrize("cancel", [False, True])
@pytest.mark.parametrize("framing", ["fixed", "chunked"])
def test_stop_interrupts_response_after_connection_ownership_transfer(wire, cancel, framing):
    from src.lifecycle_public_sources import SourceReadError

    start, state = wire
    reader = start(body=b"A delayed notice", framing=framing, stall_body=True,
                   timeout_seconds=5 if cancel else 0.15)
    errors = []

    def run():
        try:
            reader.read("https://ir.example.com/notice")
        except Exception as exc:
            errors.append(exc)

    worker = Thread(target=run)
    worker.start()
    try:
        assert state["response_returned"].wait(1)
        assert state["read_entered"].wait(1)
        if cancel:
            assert worker.is_alive()
            reader.request_stop()
        worker.join(1)
        assert not worker.is_alive(), "response-owned socket outlived cancellation/deadline"
        assert len(errors) == 1 and isinstance(errors[0], SourceReadError)
        assert str(errors[0]) == ("source_read_cancelled" if cancel else "source_read_timeout")
        assert reader.request_count == 1
        assert state["responses"][0].isclosed()
        assert state["client"].fileno() == -1
    finally:
        state["release_body"].set()
        worker.join(3)
        assert not worker.is_alive()


@pytest.mark.parametrize("status,code", [
    (429, "source_rate_limited"), (503, "source_unavailable"), (302, "source_redirect_limit"),
])
def test_response_stream_is_closed_when_headers_reject_source(wire, status, code):
    from src.lifecycle_public_sources import SourceReadError

    start, state = wire
    reader = start(body=b"Unused body", status=status)
    with pytest.raises(SourceReadError, match=f"^{code}$"):
        reader.read("https://ir.example.com/notice")
    assert reader.request_count == 1
    assert state["responses"][0].isclosed()
    assert state["client"].fileno() == -1
