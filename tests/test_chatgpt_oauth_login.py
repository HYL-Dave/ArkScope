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
import json
from datetime import datetime, timedelta, timezone

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
    def __init__(self, cid, alias, expires_at, account_label):
        self.id, self.alias, self.expires_at, self.account_label = cid, alias, expires_at, account_label


class _CredStore:
    def __init__(self):
        self.added: list[_Cred] = []
        self.deleted: list[str] = []
        self._n = 0

    def add_oauth_credential(self, *, provider, auth_mode, alias, make_active=True,
                             expires_at=None, account_label=None):
        self._n += 1
        c = _Cred(self._n, (alias or "").strip() or f"{provider} {auth_mode}", expires_at, account_label)
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
