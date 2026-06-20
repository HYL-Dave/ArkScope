"""S3 thin-transport — ephemeral loopback OAuth callback server.

The borrowed Codex client_id fixes the redirect_uri at
``http://localhost:1455/auth/callback`` (see chatgpt_oauth_login.OAUTH_REDIRECT_URI),
so ArkScope stands up a tiny one-shot HTTP server on that port for the duration of a
login, captures the single ``GET /auth/callback?code=…&state=…`` redirect, and tears
it down. It is NOT the FastAPI sidecar (which runs elsewhere) and serves only that one
path.

Port-in-use is an EXPLICIT failure (a silent fallback port would just break the fixed
redirect). The server only CAPTURES the code+state; the manager validates state (CSRF)
and does the token exchange — this server never touches a token.
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .chatgpt_oauth_login import ChatGPTOAuthLoginError

_DEFAULT_PORT = 1455
_CALLBACK_PATH = "/auth/callback"


class LoopbackCallbackServer:
    """One-shot localhost server that captures a single OAuth redirect. Usage:
    ``start()`` → ``wait_for_code(timeout)`` → (always) ``close()``."""

    def __init__(self, port: int = _DEFAULT_PORT, path: str = _CALLBACK_PATH) -> None:
        self._want_port = port
        self._path = path
        self._httpd: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._event = threading.Event()
        self._code: str | None = None
        self._state: str | None = None
        self._error: str | None = None
        self._cancelled = False

    @property
    def port(self) -> int:
        return self._httpd.server_address[1] if self._httpd else self._want_port

    def start(self) -> None:
        """Bind the port and start serving. Raises (no fallback port) if it is in use."""
        try:
            self._httpd = HTTPServer(("127.0.0.1", self._want_port), self._make_handler())
        except OSError as exc:
            raise ChatGPTOAuthLoginError(
                f"loopback callback port {self._want_port} is unavailable ({type(exc).__name__}); "
                "the OAuth redirect URI is fixed to this port — close whatever is using it, "
                "or complete the login by pasting the redirect URL manually"
            ) from None
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def wait_for_code(self, timeout: float = 120) -> tuple[str, str]:
        """Block until the callback arrives (or timeout/cancel). Returns (code, state)."""
        if not self._event.wait(timeout):
            raise ChatGPTOAuthLoginError(f"timed out after {timeout:g}s waiting for the OAuth callback")
        if self._cancelled:
            raise ChatGPTOAuthLoginError("OAuth callback wait was cancelled")
        if self._error or not self._code or not self._state:
            raise ChatGPTOAuthLoginError(f"OAuth callback did not deliver a code+state ({self._error or 'missing'})")
        return self._code, self._state

    def cancel(self) -> None:
        """Unblock a pending wait_for_code (e.g. the user completed via manual paste)."""
        self._cancelled = True
        self._event.set()

    def close(self) -> None:
        if self._httpd is not None:
            try:
                self._httpd.shutdown()
            except Exception:  # noqa: BLE001
                pass
            self._httpd.server_close()
            self._httpd = None

    def _make_handler(self) -> type[BaseHTTPRequestHandler]:
        server = self

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                if parsed.path != server._path:
                    self.send_response(404)
                    self.end_headers()
                    return
                params = parse_qs(parsed.query)
                if "error" in params:
                    server._error = "error"  # never echo the raw error param into server state
                    self._page("Authentication failed. You can close this tab and return to ArkScope.")
                else:
                    code = params.get("code", [None])[0]
                    state = params.get("state", [None])[0]
                    if not code or not state:
                        server._error = "missing"
                        self._page("Missing OAuth parameters. You can close this tab.")
                    else:
                        server._code, server._state = code, state
                        self._page("Authentication received. You can close this tab and return to ArkScope.")
                server._event.set()

            def _page(self, message: str) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(f"<html><body><h2>{message}</h2></body></html>".encode("utf-8"))

            def log_message(self, *_args: Any) -> None:  # silence default stderr logging
                return None

        return _Handler
