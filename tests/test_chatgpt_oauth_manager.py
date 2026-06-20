"""S3 thin-transport — OAuthLoginManager (offline; the loopback server is faked).

The manager orchestrates: begin() (mint state+PKCE, return auth_url, spawn a loopback
thread) → the thread waits for the callback then completes the login → status() polling
→ complete_manual() for the copy-code fallback. The real LoopbackCallbackServer is
injected via a factory, so these tests hit NO port and NO network. The real two-store
split (CredentialStore + token-store) IS exercised so we prove the token lands there and
NEVER in a status/result payload.
"""

from __future__ import annotations

import base64
import json
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from src.auth_drivers.chatgpt_oauth_login import ChatGPTOAuthLoginError
from src.auth_drivers.chatgpt_oauth_manager import OAuthLoginManager
from src.auth_drivers.token_store import PlaintextTokenStore
from src.model_credentials import CredentialStore

_NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)


def _b64url(d: bytes) -> str:
    return base64.urlsafe_b64encode(d).rstrip(b"=").decode("ascii")


def _jwt(payload: dict) -> str:
    return f"h.{_b64url(json.dumps(payload).encode())}.s"


_ACCESS = _jwt({"exp": 4102444800})  # 2100-01-01
_IDTOK = _jwt({"https://api.openai.com/auth": {"chatgpt_account_id": "acct_1", "chatgpt_plan_type": "plus"},
               "email": "u@example.com"})


def _exchange_ok(*, code, code_verifier):
    return {"access_token": _ACCESS, "refresh_token": "refresh-XYZ", "id_token": _IDTOK}


@pytest.fixture()
def stores(tmp_path):
    return CredentialStore(tmp_path / "profile_state.db"), PlaintextTokenStore(tmp_path / "auth_tokens.json")


# --- fake loopback server -----------------------------------------------------
class _FakeServer:
    def __init__(self, on_wait):
        self._on_wait = on_wait
        self.started = self.closed = self.cancelled = False
        self.cancel_event = threading.Event()

    @property
    def port(self):
        return 1455

    def start(self):
        self.started = True

    def wait_for_code(self, timeout):
        return self._on_wait(self)

    def cancel(self):
        self.cancelled = True
        self.cancel_event.set()

    def close(self):
        self.closed = True


def _mgr(stores, factory, **kw):
    cred, tok = stores
    return OAuthLoginManager(credential_store=cred, token_store=tok, server_factory=factory,
                             exchange=_exchange_ok, clock=lambda: _NOW, timeout=2.0, **kw)


def _wait_status(mgr, state, want_not="pending", timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        st = mgr.status(state)
        if st["status"] != want_not:
            return st
        time.sleep(0.02)
    return mgr.status(state)


# --- begin() ------------------------------------------------------------------
def _no_callback(_s):
    raise ChatGPTOAuthLoginError("no callback")  # the loopback never receives a redirect


def test_begin_returns_auth_url_and_marks_pending(stores):
    mgr = _mgr(stores, lambda state: _FakeServer(_no_callback))
    out = mgr.begin()
    assert out["auth_url"].startswith("https://auth.openai.com/oauth/authorize?")
    assert out["state"] and out["manual_code_supported"] is True
    assert mgr.status(out["state"])["status"] in ("pending", "success", "error")


def test_loopback_delivers_code_then_status_success_no_token(stores):
    cred, tok = stores
    mgr = _mgr(stores, lambda state: _FakeServer(lambda s: ("AUTHCODE", state)))
    out = mgr.begin()
    st = _wait_status(mgr, out["state"])
    assert st["status"] == "success"
    c = st["credential"]
    assert c["credential_id"].startswith("local:")
    # token landed in the token-store, NEVER in the status payload
    rec = tok.load(provider="openai", auth_mode="chatgpt_oauth", credential_id=c["credential_id"])
    assert rec is not None and rec.access_token == _ACCESS
    blob = json.dumps(st)
    assert _ACCESS not in blob and "refresh-XYZ" not in blob and _IDTOK not in blob
    assert "u@example.com" not in blob  # no email PII


def test_loopback_start_port_in_use_yields_error_status(stores):
    class _FailStart(_FakeServer):
        def start(self):
            raise ChatGPTOAuthLoginError("loopback callback port 1455 is unavailable")

    mgr = _mgr(stores, lambda state: _FailStart(lambda s: ("x", state)))
    out = mgr.begin()
    st = _wait_status(mgr, out["state"])
    assert st["status"] == "error" and "1455" in st["detail"]
    assert cred_count(stores) == 0  # nothing persisted


def test_loopback_timeout_yields_error_status(stores):
    mgr = _mgr(stores, lambda state: _FakeServer(
        lambda s: (_ for _ in ()).throw(ChatGPTOAuthLoginError("timed out waiting for the OAuth callback"))))
    out = mgr.begin()
    st = _wait_status(mgr, out["state"])
    assert st["status"] == "error" and "timed out" in st["detail"]


# --- complete_manual() (copy-code fallback) -----------------------------------
def test_complete_manual_succeeds_and_is_sticky_over_late_loopback(stores):
    cred, tok = stores
    # the loopback blocks until cancelled, then raises (mirrors "callback never arrived")
    def on_wait(s):
        if not s.cancel_event.wait(2):
            raise ChatGPTOAuthLoginError("timed out")
        raise ChatGPTOAuthLoginError("cancelled")

    holder = {}
    mgr = _mgr(stores, lambda state: holder.setdefault("srv", _FakeServer(on_wait)))
    out = mgr.begin()
    time.sleep(0.05)  # let the loopback thread reach wait_for_code
    res = mgr.complete_manual(state=out["state"], code="PASTEDCODE")
    assert res["credential_id"].startswith("local:")
    # the late loopback (cancelled) must NOT clobber the success
    st = _wait_status(mgr, out["state"], want_not="x")
    assert st["status"] == "success"
    assert holder["srv"].cancelled is True  # manual completion cancelled the waiting loopback
    rec = tok.load(provider="openai", auth_mode="chatgpt_oauth", credential_id=res["credential_id"])
    assert rec is not None and rec.access_token == _ACCESS


def test_complete_manual_bad_state_raises_no_persist(stores):
    mgr = _mgr(stores, lambda state: _FakeServer(_no_callback))
    mgr.begin()
    with pytest.raises(ChatGPTOAuthLoginError):
        mgr.complete_manual(state="forged-state", code="c")
    assert cred_count(stores) == 0


def test_status_unknown_for_unseen_state(stores):
    mgr = _mgr(stores, lambda state: _FakeServer(lambda s: ("x", state)))
    assert mgr.status("never-started")["status"] == "unknown"


def cred_count(stores) -> int:
    cred, _ = stores
    return len(cred.list())


# --- lifecycle hardening (from the transport audit) ---------------------------
class _GatedStartServer:
    """Loopback whose start() blocks until released — to exercise the window between
    bind and registration where a manual completion could land."""

    def __init__(self):
        self.start_gate = threading.Event()
        self.closed = threading.Event()
        self.reached_wait = threading.Event()
        self.cancelled = False

    @property
    def port(self):
        return 1455

    def start(self):
        self.start_gate.wait(2)  # block inside start() until the test releases it

    def wait_for_code(self, timeout):
        self.reached_wait.set()
        raise ChatGPTOAuthLoginError("timed out")

    def cancel(self):
        self.cancelled = True

    def close(self):
        self.closed.set()


def test_manual_completion_during_server_start_frees_port_promptly(stores):
    # Manual completion lands while the loopback is still inside start() (before it is
    # registered). The loopback must be cancelled/closed promptly — never left to hold
    # :1455 for the full timeout — and must NOT proceed into wait_for_code.
    srv = _GatedStartServer()
    mgr = _mgr(stores, lambda state: srv)
    out = mgr.begin()
    res = mgr.complete_manual(state=out["state"], code="C")  # completes before registration
    assert res["credential_id"].startswith("local:")
    srv.start_gate.set()  # release start(); the thread must now see the cancellation
    assert srv.closed.wait(2) is True  # closed promptly (no 120s wait_for_code hold)
    assert srv.reached_wait.is_set() is False  # never entered wait_for_code


class _Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


def test_terminal_results_evicted_after_ttl(stores):
    cred, tok = stores
    clock = _Clock(_NOW)
    mgr = OAuthLoginManager(credential_store=cred, token_store=tok,
                            server_factory=lambda state: _FakeServer(lambda s: ("CODE", state)),
                            exchange=_exchange_ok, clock=clock, timeout=2.0,
                            result_ttl=timedelta(minutes=15))
    a = mgr.begin()
    assert _wait_status(mgr, a["state"])["status"] == "success"
    clock.t = _NOW + timedelta(minutes=16)  # past the result TTL
    b = mgr.begin()  # begin() prunes terminal results older than the TTL
    assert mgr.status(a["state"])["status"] == "unknown"  # evicted
    assert mgr.status(b["state"])["status"] in ("pending", "success")  # the fresh one survives


def test_results_capped_drops_oldest_terminal(stores):
    cred, tok = stores
    clock = _Clock(_NOW)
    mgr = OAuthLoginManager(credential_store=cred, token_store=tok,
                            server_factory=lambda state: _FakeServer(lambda s: ("CODE", state)),
                            exchange=_exchange_ok, clock=clock, timeout=2.0, result_cap=3)
    states = []
    for _ in range(5):
        out = mgr.begin()
        _wait_status(mgr, out["state"])
        states.append(out["state"])
    live = [s for s in states if mgr.status(s)["status"] != "unknown"]
    assert len(live) <= 3  # capped — oldest terminal results were dropped
