"""S3 Option 2 — in-app ChatGPT OAuth login skeleton (offline TDD).

The CORE login logic (PKCE/state generation, state store, authorize-URL build,
code->token exchange, store-write + rollback, refresh) is fully exercised here with
FAKE credential/token stores, monkeypatchable exchange/refresh seams, and an injected
clock — NO browser, NO network. The loopback HTTP server + FastAPI routes + Settings UI
are thin transport on top of this tested core.

Fallback boundaries asserted (per the design doc): exchange errors, incomplete tokens,
state mismatch/expiry, and token-store write failure all FAIL (with rollback) — they are
never masked by a fallback. Tokens never appear in any returned payload.
"""

from __future__ import annotations

import base64
import io
import json
import threading
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError

import pytest

from src.auth_drivers import chatgpt_oauth_login as mod
from src.auth_drivers.chatgpt_oauth_login import (
    ChatGPTOAuthLoginError,
    _StateStore,
    complete_login,
    extract_code_from_redirect_url,
    refresh_if_needed,
    start_login,
)
from src.auth_drivers.token_store import StoredTokenRecord

_NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)
_FUTURE_EXP = 4102444800  # 2100-01-01 UTC (epoch, for a JWT exp claim)


def _b64url(d: bytes) -> str:
    return base64.urlsafe_b64encode(d).rstrip(b"=").decode("ascii")


def _jwt(payload: dict) -> str:
    seg = _b64url(json.dumps(payload).encode())
    return f"h.{seg}.s"  # header.payload.sig — only the payload segment is decoded


def _access(exp: int = _FUTURE_EXP) -> str:
    return _jwt({"exp": exp})


def _id_token(account: str = "acct_123", plan: str = "plus", email: str = "u@example.com") -> str:
    return _jwt({
        "https://api.openai.com/auth": {"chatgpt_account_id": account, "chatgpt_plan_type": plan},
        "email": email,
    })


def _ok_exchange(captured: dict | None = None, *, refresh: str | None = "refresh-XYZ",
                 id_token: str | None = None):
    def _x(*, code, code_verifier):
        if captured is not None:
            captured["code"] = code
            captured["code_verifier"] = code_verifier
        out = {"access_token": _access()}
        if refresh is not None:
            out["refresh_token"] = refresh
        out["id_token"] = id_token if id_token is not None else _id_token()
        return out
    return _x


class _Cred:
    def __init__(self, cid, alias, expires_at, account_label, make_active=True):
        self.id, self.alias, self.expires_at, self.account_label = cid, alias, expires_at, account_label
        self.make_active = make_active


class _CredStore:
    def __init__(self):
        self.added: list[_Cred] = []
        self.deleted: list[str] = []
        self._n = 0

    def add_oauth_credential(self, *, provider, auth_mode, alias, make_active=True,
                             expires_at=None, account_label=None):
        self._n += 1
        c = _Cred(self._n, (alias or "").strip() or f"{provider} {auth_mode}", expires_at, account_label, make_active)
        self.added.append(c)
        return c

    def delete(self, credential_id):
        self.deleted.append(credential_id)
        return True


class _TokStore:
    def __init__(self, fail_save=False):
        self.saved: dict = {}
        self.fail_save = fail_save

    def save(self, *, provider, auth_mode, credential_id, record):
        if self.fail_save:
            raise RuntimeError("disk full")
        self.saved[(provider, auth_mode, credential_id)] = record

    def load(self, *, provider, auth_mode, credential_id):
        return self.saved.get((provider, auth_mode, credential_id))


def _seed(ts: _TokStore, *, expires_at, refresh="refresh-1", cid="local:1"):
    ts.saved[("openai", "chatgpt_oauth", cid)] = StoredTokenRecord(
        access_token=_access(), refresh_token=refresh, expires_at=expires_at,
        plan_type="plus", account_label="ChatGPT plus", metadata={"account_id": "acct_123"},
    )


# --- start_login --------------------------------------------------------------
def test_start_login_returns_auth_url_and_stores_verifier():
    ss = _StateStore()
    out = start_login(state_store=ss, now=_NOW)
    assert out["manual_code_supported"] is True
    assert out["state"] and out["expires_at"]
    url = out["auth_url"]
    for frag in (
        "response_type=code",
        "client_id=app_EMoamEEZ73f0CkXaXp7hrann",
        "code_challenge_method=S256",
        "originator=arkscope",
        "codex_cli_simplified_flow=true",
        "code_challenge=",
    ):
        assert frag in url, frag
    assert out["state"] in url
    pending = ss._d[out["state"]]
    assert pending.code_verifier
    assert pending.code_verifier not in url  # the VERIFIER must never be in the URL (only the challenge)


def test_start_login_records_make_active_in_pending():
    # make_active is chosen at START and stashed in the pending state, so the
    # server-side loopback callback completion honors it (not a client cosmetic).
    ss = _StateStore()
    assert ss._d[start_login(state_store=ss, now=_NOW, make_active=False)["state"]].make_active is False
    assert ss._d[start_login(state_store=ss, now=_NOW, make_active=True)["state"]].make_active is True
    assert ss._d[start_login(state_store=ss, now=_NOW)["state"]].make_active is False  # default OFF (policy)


def test_complete_login_uses_pending_make_active_not_an_arg():
    # complete_login takes NO make_active arg — it uses the value stashed at start.
    ss, cs, ts = _StateStore(), _CredStore(), _TokStore()
    s = start_login(state_store=ss, now=_NOW, make_active=False)["state"]
    complete_login(state=s, code="c", credential_store=cs, token_store=ts, state_store=ss,
                   exchange=_ok_exchange(), now=_NOW + timedelta(minutes=1))
    assert cs.added[0].make_active is False  # honored the start-time choice (no silent activate)


# --- complete_login happy path ------------------------------------------------
def test_complete_login_writes_credential_and_token_no_echo():
    ss, cs, ts = _StateStore(), _CredStore(), _TokStore()
    started = start_login(state_store=ss, now=_NOW)
    verifier = ss._d[started["state"]].code_verifier
    cap: dict = {}
    res = complete_login(
        state=started["state"], code="auth-CODE", credential_store=cs, token_store=ts,
        state_store=ss, exchange=_ok_exchange(cap), now=_NOW + timedelta(minutes=1),
    )
    assert cap["code"] == "auth-CODE" and cap["code_verifier"] == verifier  # PKCE verifier threaded
    assert res["credential_id"] == "local:1"
    saved = ts.saved[("openai", "chatgpt_oauth", "local:1")]
    assert saved.access_token == _access() and saved.refresh_token == "refresh-XYZ"
    # the response carries NO token material
    assert "access_token" not in res and "refresh_token" not in res
    assert _access() not in json.dumps(res) and "refresh-XYZ" not in json.dumps(res)


def test_complete_login_does_not_leak_email_pii():
    ss, cs, ts = _StateStore(), _CredStore(), _TokStore()
    s = start_login(state_store=ss, now=_NOW)["state"]
    res = complete_login(
        state=s, code="c", credential_store=cs, token_store=ts, state_store=ss,
        exchange=_ok_exchange(id_token=_id_token(email="secret@private.com")),
        now=_NOW + timedelta(minutes=1),
    )
    assert "secret@private.com" not in json.dumps(res)
    assert "secret@private.com" not in (cs.added[0].account_label or "")


def test_complete_login_state_is_single_use():
    ss, cs, ts = _StateStore(), _CredStore(), _TokStore()
    s = start_login(state_store=ss, now=_NOW)["state"]
    complete_login(state=s, code="c", credential_store=cs, token_store=ts, state_store=ss,
                   exchange=_ok_exchange(), now=_NOW + timedelta(minutes=1))
    with pytest.raises(ChatGPTOAuthLoginError):
        complete_login(state=s, code="c", credential_store=cs, token_store=ts, state_store=ss,
                       exchange=_ok_exchange(), now=_NOW + timedelta(minutes=2))


def test_complete_login_unknown_state_fails_nothing_written():
    cs, ts = _CredStore(), _TokStore()
    with pytest.raises(ChatGPTOAuthLoginError):
        complete_login(state="nope", code="c", credential_store=cs, token_store=ts,
                       state_store=_StateStore(), exchange=_ok_exchange(), now=_NOW)
    assert cs.added == [] and ts.saved == {}


def test_complete_login_expired_state_fails():
    ss, cs, ts = _StateStore(), _CredStore(), _TokStore()
    s = start_login(state_store=ss, now=_NOW)["state"]
    with pytest.raises(ChatGPTOAuthLoginError):
        complete_login(state=s, code="c", credential_store=cs, token_store=ts, state_store=ss,
                       exchange=_ok_exchange(), now=_NOW + timedelta(hours=1))  # past TTL
    assert cs.added == []


def test_complete_login_exchange_error_fails_no_fallback():
    ss, cs, ts = _StateStore(), _CredStore(), _TokStore()
    s = start_login(state_store=ss, now=_NOW)["state"]

    def boom(*, code, code_verifier):
        raise ChatGPTOAuthLoginError("token exchange failed (400)")

    with pytest.raises(ChatGPTOAuthLoginError):
        complete_login(state=s, code="c", credential_store=cs, token_store=ts, state_store=ss,
                       exchange=boom, now=_NOW + timedelta(minutes=1))
    assert cs.added == [] and ts.saved == {}  # no credential, no token, no fallback


def test_complete_login_incomplete_token_fails():
    ss, cs, ts = _StateStore(), _CredStore(), _TokStore()
    s = start_login(state_store=ss, now=_NOW)["state"]
    with pytest.raises(ChatGPTOAuthLoginError):
        complete_login(state=s, code="c", credential_store=cs, token_store=ts, state_store=ss,
                       exchange=_ok_exchange(refresh=None), now=_NOW + timedelta(minutes=1))
    assert cs.added == []


def test_complete_login_token_store_write_fail_rolls_back():
    ss, cs, ts = _StateStore(), _CredStore(), _TokStore(fail_save=True)
    s = start_login(state_store=ss, now=_NOW)["state"]
    with pytest.raises(ChatGPTOAuthLoginError):
        complete_login(state=s, code="c", credential_store=cs, token_store=ts, state_store=ss,
                       exchange=_ok_exchange(), now=_NOW + timedelta(minutes=1))
    assert len(cs.added) == 1 and cs.deleted == ["local:1"] and ts.saved == {}  # row rolled back


def test_complete_login_rollback_severs_exception_cause():
    # The store-write failure must not chain the token_store.save exception (which for
    # keyring wraps the full serialized record) onto the raised error.
    ss, cs, ts = _StateStore(), _CredStore(), _TokStore(fail_save=True)
    s = start_login(state_store=ss, now=_NOW)["state"]
    with pytest.raises(ChatGPTOAuthLoginError) as ei:
        complete_login(state=s, code="c", credential_store=cs, token_store=ts, state_store=ss,
                       exchange=_ok_exchange(), now=_NOW + timedelta(minutes=1))
    assert ei.value.__cause__ is None and ei.value.__suppress_context__ is True


def test_pending_login_repr_masks_verifier():
    # _PendingLogin must never render the PKCE code_verifier in its repr — a future
    # loopback handler doing logger.debug(pending) / f"{pending}" would otherwise leak it.
    pending = mod._PendingLogin(code_verifier="SECRET-VERIFIER-VALUE", expires_at=_NOW)
    assert "SECRET-VERIFIER-VALUE" not in repr(pending)


# --- extract_code_from_redirect_url -------------------------------------------
def test_extract_code_from_redirect_url_ok():
    out = extract_code_from_redirect_url("http://localhost:1455/auth/callback?code=AC&state=ST")
    assert out["code"] == "AC" and out["state"] == "ST"


def test_extract_code_from_redirect_url_error_param():
    with pytest.raises(ChatGPTOAuthLoginError):
        extract_code_from_redirect_url("http://localhost:1455/auth/callback?error=access_denied")


def test_extract_code_from_redirect_url_missing_code():
    with pytest.raises(ChatGPTOAuthLoginError):
        extract_code_from_redirect_url("http://localhost:1455/auth/callback?state=ST")


# --- refresh_if_needed --------------------------------------------------------
def test_refresh_if_needed_skips_when_not_expired():
    ts = _TokStore()
    _seed(ts, expires_at="2100-01-01T00:00:00+00:00")
    calls = {"n": 0}

    def refresh(*, refresh_token):
        calls["n"] += 1
        return {}

    rec = refresh_if_needed(credential_id="local:1", token_store=ts, now=_NOW, refresh=refresh)
    assert calls["n"] == 0 and rec.refresh_token == "refresh-1"


def test_refresh_if_needed_refreshes_when_expired():
    ts = _TokStore()
    _seed(ts, expires_at="2001-01-01T00:00:00+00:00")  # past

    def refresh(*, refresh_token):
        assert refresh_token == "refresh-1"
        return {"access_token": _access(), "refresh_token": "refresh-2", "id_token": _id_token()}

    rec = refresh_if_needed(credential_id="local:1", token_store=ts, now=_NOW, refresh=refresh)
    assert rec.refresh_token == "refresh-2"
    assert ts.saved[("openai", "chatgpt_oauth", "local:1")].refresh_token == "refresh-2"


def test_refresh_if_needed_treats_near_expiry_as_expired_with_buffer():
    ts = _TokStore()
    _seed(ts, expires_at=(_NOW + timedelta(minutes=2)).isoformat())  # within the 5-min buffer

    def refresh(*, refresh_token):
        return {"access_token": _access(), "refresh_token": "refresh-buf", "id_token": _id_token()}

    rec = refresh_if_needed(credential_id="local:1", token_store=ts, now=_NOW, refresh=refresh)
    assert rec.refresh_token == "refresh-buf"


def test_refresh_if_needed_force_refreshes_even_if_fresh():
    ts = _TokStore()
    _seed(ts, expires_at="2100-01-01T00:00:00+00:00")

    def refresh(*, refresh_token):
        return {"access_token": _access(), "refresh_token": "refresh-9", "id_token": _id_token()}

    rec = refresh_if_needed(credential_id="local:1", token_store=ts, now=_NOW, force=True, refresh=refresh)
    assert rec.refresh_token == "refresh-9"


def test_refresh_if_needed_raises_on_failure_no_silent_fallback():
    ts = _TokStore()
    _seed(ts, expires_at="2001-01-01T00:00:00+00:00")

    def refresh(*, refresh_token):
        raise ChatGPTOAuthLoginError("refresh failed (401)")

    with pytest.raises(ChatGPTOAuthLoginError):
        refresh_if_needed(credential_id="local:1", token_store=ts, now=_NOW, refresh=refresh)
    # the stale token is NOT silently overwritten or swallowed
    assert ts.saved[("openai", "chatgpt_oauth", "local:1")].refresh_token == "refresh-1"


def test_refresh_if_needed_no_refresh_token_fails():
    ts = _TokStore()
    _seed(ts, expires_at="2001-01-01T00:00:00+00:00", refresh=None)
    with pytest.raises(ChatGPTOAuthLoginError):
        refresh_if_needed(credential_id="local:1", token_store=ts, now=_NOW, force=True)


def test_refresh_if_needed_missing_credential_fails():
    with pytest.raises(ChatGPTOAuthLoginError):
        refresh_if_needed(credential_id="local:999", token_store=_TokStore(), now=_NOW)


# --- HTTP error redaction (must-fix: a backend/proxy could echo the secret) -----
_LEAKY_BODY = ('{"error":"invalid_grant","refresh_token":"refresh-SECRET-LEAK",'
               '"code_verifier":"VERIFIER-LEAK-9","code":"AUTHCODE-LEAK"}')


def _fake_http_error(body: str):
    def _urlopen(req, timeout=None):
        raise HTTPError(OAUTH_TOKEN_URL_FOR_TEST, 400, "Bad Request", {}, io.BytesIO(body.encode()))
    return _urlopen


OAUTH_TOKEN_URL_FOR_TEST = "https://auth.openai.com/oauth/token"


def test_token_exchange_http_error_body_is_redacted(monkeypatch):
    monkeypatch.setattr(mod.request, "urlopen", _fake_http_error(_LEAKY_BODY))
    with pytest.raises(ChatGPTOAuthLoginError) as ei:
        mod._exchange_authorization_code(code="AUTHCODE-LEAK", code_verifier="VERIFIER-LEAK-9")
    msg = str(ei.value)
    assert "400" in msg  # the status is still useful
    for secret in ("refresh-SECRET-LEAK", "VERIFIER-LEAK-9", "AUTHCODE-LEAK"):
        assert secret not in msg


def test_refresh_grant_http_error_body_is_redacted(monkeypatch):
    monkeypatch.setattr(mod.request, "urlopen", _fake_http_error(_LEAKY_BODY))
    with pytest.raises(ChatGPTOAuthLoginError) as ei:
        mod._refresh_token_grant(refresh_token="refresh-SECRET-LEAK")
    assert "refresh-SECRET-LEAK" not in str(ei.value)


def test_refresh_if_needed_propagates_redacted_http_error(monkeypatch):
    # End-to-end: the live refresh path (no injected seam) must not leak the token
    # body into the raised error a route/UI/log would see.
    ts = _TokStore()
    _seed(ts, expires_at="2001-01-01T00:00:00+00:00", refresh="refresh-SECRET-LEAK")
    monkeypatch.setattr(mod.request, "urlopen", _fake_http_error(_LEAKY_BODY))
    with pytest.raises(ChatGPTOAuthLoginError) as ei:
        refresh_if_needed(credential_id="local:1", token_store=ts, now=_NOW, force=True)
    assert "refresh-SECRET-LEAK" not in str(ei.value)


def test_exchange_jwt_in_error_body_is_redacted(monkeypatch):
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJsZWFrIn0.QWxhZGRpbnNlY3JldA"
    monkeypatch.setattr(mod.request, "urlopen", _fake_http_error(f'{{"detail":"{jwt}"}}'))
    with pytest.raises(ChatGPTOAuthLoginError) as ei:
        mod._refresh_token_grant(refresh_token="r")
    assert jwt not in str(ei.value)


# --- _StateStore thread-safety (single-use under concurrency) ------------------
def test_state_store_pop_is_single_use_under_threads():
    ss = _StateStore()
    ss.put("s", "verifier", expires_at=_NOW + timedelta(minutes=5))
    results: list = []
    barrier = threading.Barrier(8)

    def worker():
        barrier.wait()  # maximize contention
        results.append(ss.pop("s", now=_NOW))

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    non_none = [r for r in results if r is not None]
    assert len(non_none) == 1  # exactly one caller gets the pending login
