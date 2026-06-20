"""S3 thin-transport — the ephemeral loopback callback server (localhost only).

This is the ONE piece that binds a real port (the OAuth redirect_uri is fixed at
http://localhost:1455/auth/callback by the borrowed Codex client_id), so these tests
drive it over 127.0.0.1 — no external network. Port-in-use must FAIL explicitly (the
redirect URI is fixed; a silent fallback port would just break the redirect).
"""

from __future__ import annotations

import socket
import threading
import time
import urllib.request

import pytest

from src.auth_drivers.chatgpt_oauth_callback_server import LoopbackCallbackServer
from src.auth_drivers.chatgpt_oauth_login import ChatGPTOAuthLoginError


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _hit(port: int, query: str) -> None:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{port}/auth/callback?{query}", timeout=5).read()
    except Exception:  # noqa: BLE001 — the response page content is irrelevant to the capture
        pass


def test_captures_code_and_state():
    srv = LoopbackCallbackServer(port=0)
    srv.start()
    try:
        threading.Thread(target=_hit, args=(srv.port, "code=AUTHCODE&state=STATE123"), daemon=True).start()
        code, state = srv.wait_for_code(timeout=5)
        assert code == "AUTHCODE" and state == "STATE123"
    finally:
        srv.close()


def test_port_in_use_raises_explicitly_no_fallback():
    port = _free_port()
    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(("127.0.0.1", port))
    blocker.listen(1)
    try:
        srv = LoopbackCallbackServer(port=port)
        with pytest.raises(ChatGPTOAuthLoginError) as ei:
            srv.start()
        assert str(port) in str(ei.value)  # the error names the occupied port
    finally:
        blocker.close()


def test_error_param_surfaces_as_failure():
    srv = LoopbackCallbackServer(port=0)
    srv.start()
    try:
        threading.Thread(target=_hit, args=(srv.port, "error=access_denied"), daemon=True).start()
        with pytest.raises(ChatGPTOAuthLoginError):
            srv.wait_for_code(timeout=5)
    finally:
        srv.close()


def test_missing_code_surfaces_as_failure():
    srv = LoopbackCallbackServer(port=0)
    srv.start()
    try:
        threading.Thread(target=_hit, args=(srv.port, "state=onlystate"), daemon=True).start()
        with pytest.raises(ChatGPTOAuthLoginError):
            srv.wait_for_code(timeout=5)
    finally:
        srv.close()


def test_timeout_raises():
    srv = LoopbackCallbackServer(port=0)
    srv.start()
    try:
        with pytest.raises(ChatGPTOAuthLoginError):
            srv.wait_for_code(timeout=0.3)
    finally:
        srv.close()


def test_cancel_unblocks_wait():
    srv = LoopbackCallbackServer(port=0)
    srv.start()
    try:
        def _cancel():
            time.sleep(0.1)
            srv.cancel()
        threading.Thread(target=_cancel, daemon=True).start()
        with pytest.raises(ChatGPTOAuthLoginError):
            srv.wait_for_code(timeout=5)
    finally:
        srv.close()
