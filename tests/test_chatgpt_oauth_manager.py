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


def test_begin_waits_until_loopback_is_started_before_returning(stores):
    # The browser can redirect to localhost immediately after login. Returning the
    # auth_url before the loopback has actually bound the callback port creates a
    # race: the redirect can hit :1455 first and get ERR_CONNECTION_REFUSED.
    class _SlowStartServer(_FakeServer):
        def __init__(self):
            super().__init__(_no_callback)
            self.entered_start = threading.Event()
            self.release_start = threading.Event()

        def start(self):
            self.entered_start.set()
            self.release_start.wait(2)
            self.started = True

    srv = _SlowStartServer()
    mgr = _mgr(stores, lambda state: srv)
    returned = []
    t = threading.Thread(target=lambda: returned.append(mgr.begin()))
    t.start()
    assert srv.entered_start.wait(1) is True
    assert returned == []  # begin() must not return until start() finishes
    srv.release_start.set()
    t.join(1)
    assert returned and returned[0]["state"]


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


def test_begin_make_active_false_creates_inactive_credential(stores):
    # The activation choice flows start→callback: begin(make_active=False) → the
    # server-side completion creates the credential WITHOUT switching the active one.
    cred, tok = stores
    mgr = _mgr(stores, lambda state: _FakeServer(lambda s: ("AUTHCODE", state)))
    out = mgr.begin(make_active=False)
    st = _wait_status(mgr, out["state"])
    assert st["status"] == "success"
    row = cred.get(st["credential"]["credential_id"])
    assert row is not None and row.active is False  # logging in did NOT hijack the active credential


def test_cancel_login_evicts_pending_so_a_late_callback_creates_nothing(stores):
    # 取消 must close the gap: after cancel, a late browser callback (loopback still
    # waiting) must NOT create a credential. cancel_login evicts the pending state, so
    # the late complete_login pops None → raises → nothing persisted; the server is cancelled.
    cred, tok = stores
    gate = threading.Event()
    captured = {}

    def factory(state):
        srv = _FakeServer(lambda s: (gate.wait(2.0), ("LATECODE", state))[1])
        captured["srv"] = srv
        return srv

    mgr = _mgr(stores, factory)
    out = mgr.begin()
    time.sleep(0.05)  # let the loopback thread reach wait_for_code
    mgr.cancel_login(out["state"])  # evict pending + cancel the server
    gate.set()  # release the (late) callback delivery
    st = _wait_status(mgr, out["state"], want_not="pending")
    assert st["status"] == "error"  # the late completion did not succeed
    assert cred_count(stores) == 0  # NO credential created after cancel
    assert captured["srv"].cancelled is True  # loopback torn down (frees :1455)


def test_cancel_login_unknown_state_is_noop(stores):
    mgr = _mgr(stores, lambda state: _FakeServer(_no_callback))
    mgr.cancel_login("never-started")  # no raise
    # a TRUE no-op: an unknown state must NOT fabricate a terminal result entry.
    assert mgr.status("never-started")["status"] == "unknown"
    assert cred_count(stores) == 0


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


# --- re-login (S3 credential-lifecycle hotfix) ---------------------------------
def _seed_relogin_target(stores, *, access="OLD-ACCESS"):
    from src.auth_drivers.token_store import StoredTokenRecord
    cred_store, tok_store = stores
    target = cred_store.add_oauth_credential(
        provider="openai", auth_mode="chatgpt_oauth", alias="Sub", make_active=False,
        expires_at="2030-06-01T00:00:00+00:00", account_label="ChatGPT plus",
    )
    cid = f"local:{target.id}"
    tok_store.save(provider="openai", auth_mode="chatgpt_oauth", credential_id=cid,
                   record=StoredTokenRecord(access_token=access, refresh_token="r-old"))
    return cid


def test_begin_threads_relogin_target_to_completion(stores):
    from src.model_discovery_cache import ModelDiscoveryCache

    cred_store, tok_store = stores
    cid = _seed_relogin_target(stores)
    cache = ModelDiscoveryCache(cred_store.db_path)
    cache.record_run(provider="openai", auth_mode="chatgpt_oauth", credential_id=cid,
                     secret_fingerprint="oauth", status="ok",
                     models=[{"id": "old-model", "label": "Old", "source": "provider_api"}])
    mgr = _mgr(stores, lambda s: _FakeServer(lambda _srv: ("code-1", None)))
    out = mgr.begin(relogin_credential_id=cid)
    st = _wait_status(mgr, out["state"])
    assert st["status"] == "success"
    assert st["credential"]["credential_id"] == cid
    assert st["credential"]["relogin"] is True
    assert st["credential"]["discovery_cache_cleared"] is True
    assert cred_store.get(f"local:{int(cid.split(':')[1]) + 1}") is None       # NO new row
    scope = cache.get(provider="openai", auth_mode="chatgpt_oauth", credential_id=cid,
                      secret_fingerprint="oauth")
    assert scope.status == "never_discovered"                                   # stale entitlement gone
    rec = tok_store.load(provider="openai", auth_mode="chatgpt_oauth", credential_id=cid)
    assert rec.access_token == _ACCESS                                          # token replaced in place
    row = cred_store.get(cid)
    assert row.alias == "Sub" and row.active is False                           # preserved


def test_relogin_cache_clear_failure_aborts_before_token_replace(stores, monkeypatch):
    from src.auth_drivers import chatgpt_oauth_manager as mgr_mod

    cred_store, tok_store = stores
    cid = _seed_relogin_target(stores)

    class _BoomCache:
        def __init__(self, _path):
            pass

        def delete_scope(self, **_kw):
            raise RuntimeError("cache locked")

    monkeypatch.setattr(mgr_mod, "ModelDiscoveryCache", _BoomCache)
    mgr = _mgr(stores, lambda s: _FakeServer(lambda _srv: ("code-1", None)))
    out = mgr.begin(relogin_credential_id=cid)
    st = _wait_status(mgr, out["state"])
    assert st["status"] == "error"                                              # terminal, no success result
    rec = tok_store.load(provider="openai", auth_mode="chatgpt_oauth", credential_id=cid)
    assert rec.access_token == "OLD-ACCESS"                                     # token untouched
    row = cred_store.get(cid)
    assert row.expires_at == "2030-06-01T00:00:00+00:00"                        # metadata untouched


def test_completion_failure_is_not_manual_completable(stores):
    # F4 (review round 4): the loopback DELIVERED a code but completion failed →
    # the single-use state is consumed; a manual paste can never succeed, and the
    # result must say so (so the UI doesn't offer a dead-end fallback).
    def bad_exchange(*, code, code_verifier):
        raise ChatGPTOAuthLoginError("token exchange failed (400)")

    cred_store, tok_store = stores
    mgr = OAuthLoginManager(
        credential_store=cred_store, token_store=tok_store,
        server_factory=lambda s: _FakeServer(lambda _srv: ("code-1", None)),
        exchange=bad_exchange, clock=lambda: _NOW, timeout=2.0,
    )
    out = mgr.begin()
    st = _wait_status(mgr, out["state"])
    assert st["status"] == "error"
    assert st["manual_completable"] is False


def test_callback_never_arrived_stays_manual_completable(stores):
    # timeout/no-callback errors leave the pending state alive → manual CAN work.
    mgr = _mgr(stores, lambda s: _FakeServer(_no_callback))
    out = mgr.begin()
    st = _wait_status(mgr, out["state"])
    assert st["status"] == "error"
    assert st.get("manual_completable", True) is True
