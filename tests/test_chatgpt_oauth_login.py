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
    def __init__(self, cid, alias, expires_at, account_label, make_active=True,
                 provider="openai", auth_type="chatgpt_oauth", active=False):
        self.id, self.alias, self.expires_at, self.account_label = cid, alias, expires_at, account_label
        self.make_active = make_active
        self.provider, self.auth_type, self.active = provider, auth_type, active


class _CredStore:
    def __init__(self, fail_update=False, vanish_on_update=False):
        self.added: list[_Cred] = []
        self.deleted: list[str] = []
        self.updated: list[dict] = []
        self.rows: dict[str, _Cred] = {}
        self.fail_update = fail_update
        self.vanish_on_update = vanish_on_update
        self._n = 0

    def add_oauth_credential(self, *, provider, auth_mode, alias, make_active=True,
                             expires_at=None, account_label=None):
        self._n += 1
        c = _Cred(self._n, (alias or "").strip() or f"{provider} {auth_mode}", expires_at, account_label, make_active,
                  provider=provider, auth_type=auth_mode, active=make_active)
        self.added.append(c)
        self.rows[f"local:{c.id}"] = c
        return c

    def get(self, credential_id):
        return self.rows.get(credential_id)

    def update(self, credential_id, *, alias=None, secret=None, active=None,
               expires_at=None, account_label=None):
        # Mirrors the REAL CredentialStore.update semantics for the fields the
        # re-login path uses: "" forces NULL, None means don't-touch.
        if self.fail_update:
            raise RuntimeError("update boom")
        row = self.rows.get(credential_id)
        if row is None or self.vanish_on_update:
            return None
        recorded = {}
        if alias is not None:
            recorded["alias"] = alias
            if alias.strip():
                row.alias = alias.strip()
        if active is not None:
            recorded["active"] = active
            row.active = bool(active)
        if expires_at is not None:
            recorded["expires_at"] = expires_at
            row.expires_at = expires_at.strip() or None
        if account_label is not None:
            recorded["account_label"] = account_label
            row.account_label = account_label.strip() or None
        self.updated.append(recorded)
        return row

    def delete(self, credential_id):
        self.deleted.append(credential_id)
        self.rows.pop(credential_id, None)
        return True


class _TokStore:
    def __init__(self, fail_save=False):
        self.saved: dict = {}
        self.deleted: list = []
        self.fail_save = fail_save

    def save(self, *, provider, auth_mode, credential_id, record):
        if self.fail_save:
            raise RuntimeError("disk full")
        self.saved[(provider, auth_mode, credential_id)] = record

    def load(self, *, provider, auth_mode, credential_id):
        return self.saved.get((provider, auth_mode, credential_id))

    def delete(self, *, provider, auth_mode, credential_id):
        self.deleted.append((provider, auth_mode, credential_id))
        return self.saved.pop((provider, auth_mode, credential_id), None) is not None


def _seed_cred(cs: _CredStore, *, cid="local:1", provider="openai", auth_type="chatgpt_oauth",
               alias="ChatGPT subscription Plus", active=False, expires_at=None):
    # Seed an EXISTING credential row without touching cs.added (which the
    # relogin tests assert stays empty — no new row is ever created in place).
    n = int(cid.split(":", 1)[1])
    cs._n = max(cs._n, n)
    row = _Cred(n, alias, expires_at, "ChatGPT plus", provider=provider, auth_type=auth_type, active=active)
    cs.rows[cid] = row
    return row


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


# --- re-login (S3 credential-lifecycle hotfix) ---------------------------------
def _relogin_complete(ss, cs, ts, state, *, exchange=None, invalidator=lambda _t: 0, now=None):
    return complete_login(
        state=state, code="c", credential_store=cs, token_store=ts, state_store=ss,
        exchange=exchange or _ok_exchange(), now=now or (_NOW + timedelta(minutes=1)),
        invalidate_relogin_cache=invalidator,
    )


_KEY = ("openai", "chatgpt_oauth", "local:1")


def test_relogin_replaces_token_in_place():
    ss, cs, ts = _StateStore(), _CredStore(), _TokStore()
    _seed_cred(cs, alias="My ChatGPT", active=True)
    _seed(ts, expires_at="2030-06-01T00:00:00+00:00")
    cleared: list = []
    s = start_login(state_store=ss, now=_NOW, relogin_credential_id="local:1")["state"]
    out = _relogin_complete(ss, cs, ts, s, invalidator=lambda t: cleared.append(t) or 3)
    assert out["credential_id"] == "local:1"
    assert out["relogin"] is True
    assert out["discovery_cache_cleared"] is True
    assert out["discovery_cache_rows_deleted"] == 3
    assert out["alias"] == "My ChatGPT"
    assert cleared == ["local:1"]
    assert cs.added == []                                   # NO new row
    rec = ts.saved[_KEY]
    assert rec.access_token == _access()                    # token replaced
    assert rec.refresh_token == "refresh-XYZ"
    upd = cs.updated[-1]
    assert upd["expires_at"] and upd["account_label"] == "ChatGPT plus"
    assert "alias" not in upd and "active" not in upd       # preserved fields never passed
    row = cs.get("local:1")
    assert row.alias == "My ChatGPT" and row.active is True


def test_relogin_token_save_failure_keeps_old_token():
    # Atomicity INVERSION vs the create path: a save failure must leave the OLD
    # token untouched (sibling of test_complete_login_token_store_write_fail_rolls_back).
    ss, cs = _StateStore(), _CredStore()
    ts = _TokStore(fail_save=True)
    _seed_cred(cs)
    _seed(ts, expires_at="2030-06-01T00:00:00+00:00")       # seeded directly, bypasses save()
    old = ts.saved[_KEY]
    s = start_login(state_store=ss, now=_NOW, relogin_credential_id="local:1")["state"]
    with pytest.raises(ChatGPTOAuthLoginError):
        _relogin_complete(ss, cs, ts, s)
    assert ts.saved[_KEY] is old                            # old token untouched
    assert cs.updated == [] and cs.added == [] and cs.deleted == []


def test_relogin_target_vanished_fails_no_new_credential():
    ss, cs, ts = _StateStore(), _CredStore(), _TokStore()   # target never seeded
    s = start_login(state_store=ss, now=_NOW, relogin_credential_id="local:1")["state"]
    with pytest.raises(ChatGPTOAuthLoginError):
        _relogin_complete(ss, cs, ts, s)
    assert cs.added == [] and cs.updated == [] and ts.saved == {}   # NEVER falls back to create


def test_relogin_wrong_target_type_rejected():
    for provider, auth_type in (("openai", "api_key"), ("anthropic", "claude_code_oauth")):
        ss, cs, ts = _StateStore(), _CredStore(), _TokStore()
        _seed_cred(cs, provider=provider, auth_type=auth_type)
        s = start_login(state_store=ss, now=_NOW, relogin_credential_id="local:1")["state"]
        with pytest.raises(ChatGPTOAuthLoginError):
            _relogin_complete(ss, cs, ts, s)
        assert cs.added == [] and cs.updated == [] and ts.saved == {}, (provider, auth_type)


def test_relogin_ignores_make_active():
    ss, cs, ts = _StateStore(), _CredStore(), _TokStore()
    _seed_cred(cs, active=False)
    _seed(ts, expires_at=None)
    s = start_login(state_store=ss, now=_NOW, make_active=True, relogin_credential_id="local:1")["state"]
    _relogin_complete(ss, cs, ts, s)
    assert cs.get("local:1").active is False                # untouched despite make_active=True
    assert all("active" not in u for u in cs.updated)
    assert cs.added == []


def test_relogin_clears_expiry_when_new_token_has_none():
    ss, cs, ts = _StateStore(), _CredStore(), _TokStore()
    _seed_cred(cs, expires_at="2030-06-01T00:00:00+00:00")
    _seed(ts, expires_at="2030-06-01T00:00:00+00:00")

    def _noexp_exchange(*, code, code_verifier):
        return {"access_token": _jwt({"sub": "x"}), "refresh_token": "r2", "id_token": _id_token()}

    s = start_login(state_store=ss, now=_NOW, relogin_credential_id="local:1")["state"]
    _relogin_complete(ss, cs, ts, s, exchange=_noexp_exchange)
    assert cs.updated[-1]["expires_at"] == ""               # the real store's explicit-NULL form
    assert cs.get("local:1").expires_at is None


def test_relogin_in_place_with_real_credential_store(tmp_path):
    # Seam-mock discipline: the fake's update() semantics must hold against the
    # REAL CredentialStore (row count / id / alias / active invariance).
    from src.model_credentials import CredentialStore

    real = CredentialStore(tmp_path / "creds.db")
    cred = real.add_oauth_credential(
        provider="openai", auth_mode="chatgpt_oauth", alias="Sub", make_active=False,
        expires_at="2030-06-01T00:00:00+00:00", account_label="ChatGPT plus",
    )
    cid = f"local:{cred.id}"
    ss, ts = _StateStore(), _TokStore()
    _seed(ts, expires_at="2030-06-01T00:00:00+00:00", cid=cid)
    s = start_login(state_store=ss, now=_NOW, relogin_credential_id=cid)["state"]
    out = complete_login(
        state=s, code="c", credential_store=real, token_store=ts, state_store=ss,
        exchange=_ok_exchange(), now=_NOW + timedelta(minutes=1),
        invalidate_relogin_cache=lambda _t: 0,
    )
    assert out["credential_id"] == cid and out["relogin"] is True
    row = real.get(cid)
    assert row is not None
    assert row.alias == "Sub" and row.active is False       # preserved
    assert row.expires_at and row.expires_at != "2030-06-01T00:00:00+00:00"  # refreshed from new JWT
    assert real.get(f"local:{cred.id + 1}") is None         # NO second row (AUTOINCREMENT next id)
    assert ts.saved[("openai", "chatgpt_oauth", cid)].refresh_token == "refresh-XYZ"


def test_refresh_failure_classification(monkeypatch):
    # (a) refresh HTTP 401 → reauth_required, status_code preserved
    ts = _TokStore()
    _seed(ts, expires_at=None)

    def _401(*, refresh_token):
        raise ChatGPTOAuthLoginError("ChatGPT OAuth refresh failed (401): x", status_code=401)

    with pytest.raises(ChatGPTOAuthLoginError) as ei:
        refresh_if_needed(credential_id="local:1", token_store=ts, force=True, refresh=_401)
    assert ei.value.reauth_required is True and ei.value.status_code == 401

    # (b) _http_post's wrapped network-error shape (status_code=None) stays transient
    def _net(*, refresh_token):
        raise ChatGPTOAuthLoginError("ChatGPT OAuth refresh failed: boom", status_code=None)

    with pytest.raises(ChatGPTOAuthLoginError) as ei:
        refresh_if_needed(credential_id="local:1", token_store=ts, force=True, refresh=_net)
    assert ei.value.reauth_required is False

    # (c) missing refresh_token → reauth (re-login is the only fix)
    ts2 = _TokStore()
    _seed(ts2, expires_at=None, refresh=None)
    with pytest.raises(ChatGPTOAuthLoginError) as ei:
        refresh_if_needed(credential_id="local:1", token_store=ts2, force=True)
    assert ei.value.reauth_required is True

    # (d) missing stored token → reauth
    with pytest.raises(ChatGPTOAuthLoginError) as ei:
        refresh_if_needed(credential_id="local:9", token_store=_TokStore(), force=True)
    assert ei.value.reauth_required is True

    # (e) _http_post wires the real HTTP status onto the raised error
    def _boom_401(req, timeout=None):
        raise HTTPError(OAUTH_TOKEN_URL_FOR_TEST, 401, "unauthorized", {}, io.BytesIO(b'{"error":"invalid_grant"}'))

    monkeypatch.setattr(mod.request, "urlopen", _boom_401)
    with pytest.raises(ChatGPTOAuthLoginError) as ei:
        mod._refresh_token_grant(refresh_token="r")
    assert ei.value.status_code == 401


def test_relogin_serializes_with_inflight_refresh():
    # An in-flight refresh holds the credential lifecycle lock; re-login
    # completion must WAIT, so the newly authorized token is written LAST and a
    # stale refreshed old-account token can never clobber it.
    ss, cs, ts = _StateStore(), _CredStore(), _TokStore()
    _seed_cred(cs)
    _seed(ts, expires_at=None)
    old_refreshed = _jwt({"exp": _FUTURE_EXP, "marker": "old-refreshed"})
    new_access = _jwt({"exp": _FUTURE_EXP, "marker": "new-login"})
    entered, release = threading.Event(), threading.Event()

    def slow_refresh(*, refresh_token):
        entered.set()
        assert release.wait(5)
        return {"access_token": old_refreshed, "refresh_token": "refresh-2"}

    t_refresh = threading.Thread(
        target=lambda: refresh_if_needed(credential_id="local:1", token_store=ts, force=True, refresh=slow_refresh),
    )
    t_refresh.start()
    assert entered.wait(5)

    def _new_exchange(*, code, code_verifier):
        return {"access_token": new_access, "refresh_token": "refresh-new", "id_token": _id_token()}

    s = start_login(state_store=ss, now=_NOW, relogin_credential_id="local:1")["state"]
    done = threading.Event()

    def _run_relogin():
        _relogin_complete(ss, cs, ts, s, exchange=_new_exchange)
        done.set()

    t_re = threading.Thread(target=_run_relogin)
    t_re.start()
    assert not done.wait(0.3)                               # blocked behind the in-flight refresh
    release.set()
    t_refresh.join(5)
    t_re.join(5)
    assert done.is_set()
    assert ts.saved[_KEY].access_token == new_access        # last write = the NEW login


def test_relogin_metadata_failure_restores_or_deletes_token():
    # arm 1: update raises, old token present → old token restored
    ss, ts = _StateStore(), _TokStore()
    cs = _CredStore(fail_update=True)
    _seed_cred(cs)
    _seed(ts, expires_at=None)
    old = ts.saved[_KEY]
    s = start_login(state_store=ss, now=_NOW, relogin_credential_id="local:1")["state"]
    with pytest.raises(ChatGPTOAuthLoginError):
        _relogin_complete(ss, cs, ts, s)
    assert ts.saved[_KEY].access_token == old.access_token  # restored

    # arm 2: row vanishes at update, NO old token → the new token is removed
    ss2, ts2 = _StateStore(), _TokStore()
    cs2 = _CredStore(vanish_on_update=True)
    _seed_cred(cs2)                                          # row exists at validation, no stored token
    s2 = start_login(state_store=ss2, now=_NOW, relogin_credential_id="local:1")["state"]
    with pytest.raises(ChatGPTOAuthLoginError):
        _relogin_complete(ss2, cs2, ts2, s2)
    assert _KEY not in ts2.saved                             # no orphan token for a gone row


def test_relogin_compensation_failure_preserves_original_error(caplog):
    import logging

    class _FlakyTok(_TokStore):
        def __init__(self):
            super().__init__()
            self._saves = 0

        def save(self, **kw):
            self._saves += 1
            if self._saves >= 2:                             # 1st = new token, 2nd = rollback
                raise RuntimeError("rollback save boom")
            super().save(**kw)

    ss, ts = _StateStore(), _FlakyTok()
    cs = _CredStore(fail_update=True)
    _seed_cred(cs)
    _seed(ts, expires_at=None)
    s = start_login(state_store=ss, now=_NOW, relogin_credential_id="local:1")["state"]
    with caplog.at_level(logging.WARNING):
        with pytest.raises(ChatGPTOAuthLoginError) as ei:
            _relogin_complete(ss, cs, ts, s)
    assert isinstance(ei.value.__cause__, RuntimeError)      # ORIGINAL metadata error is the cause
    assert "update boom" in str(ei.value.__cause__)
    assert any("rollback" in r.message.lower() for r in caplog.records)  # secondary failure logged
    # honest: NO claim about a clean token-store state after a double failure


def test_relogin_requires_cache_invalidator():
    ss, cs, ts = _StateStore(), _CredStore(), _TokStore()
    _seed_cred(cs)
    _seed(ts, expires_at=None)
    old = ts.saved[_KEY]
    s = start_login(state_store=ss, now=_NOW, relogin_credential_id="local:1")["state"]
    with pytest.raises(ChatGPTOAuthLoginError):
        complete_login(state=s, code="c", credential_store=cs, token_store=ts, state_store=ss,
                       exchange=_ok_exchange(), now=_NOW + timedelta(minutes=1))  # no invalidator
    assert ts.saved[_KEY] is old and cs.updated == [] and cs.added == []
    # the create path stays valid with the default None callback
    s2 = start_login(state_store=ss, now=_NOW)["state"]
    out = complete_login(state=s2, code="c", credential_store=cs, token_store=ts, state_store=ss,
                         exchange=_ok_exchange(), now=_NOW + timedelta(minutes=1))
    assert out["credential_id"] and cs.added
    assert "relogin" not in out                              # create payload unchanged


def test_relogin_vanished_row_message_honest_when_rollback_fails(caplog):
    # F2 (review round 4): when the row vanished AND removing the just-written
    # token ALSO fails, the message must not claim "the new token was removed".
    import logging

    class _NoDeleteTok(_TokStore):
        def delete(self, **kw):
            raise RuntimeError("keyring down")

    ss, ts = _StateStore(), _NoDeleteTok()
    cs = _CredStore(vanish_on_update=True)
    _seed_cred(cs)
    s = start_login(state_store=ss, now=_NOW, relogin_credential_id="local:1")["state"]
    with caplog.at_level(logging.WARNING):
        with pytest.raises(ChatGPTOAuthLoginError) as ei:
            _relogin_complete(ss, cs, ts, s)
    msg = str(ei.value)
    assert "was removed" not in msg
    assert "may still hold" in msg


def test_rollback_delete_false_with_token_present_reports_unproven():
    # Round-5 MF2: keyring-shaped stores collapse backend exceptions into
    # delete() -> False. With the new token still loadable, compensation is
    # UNPROVEN — the message must say "may still hold", never "was removed".
    class _NoRemoveTok(_TokStore):
        def delete(self, *, provider, auth_mode, credential_id):
            self.deleted.append((provider, auth_mode, credential_id))
            return False  # collapsed backend failure; nothing actually removed

    ss, ts = _StateStore(), _NoRemoveTok()
    cs = _CredStore(vanish_on_update=True)
    _seed_cred(cs)                                  # no OLD token → rollback = delete the new one
    s = start_login(state_store=ss, now=_NOW, relogin_credential_id="local:1")["state"]
    with pytest.raises(ChatGPTOAuthLoginError) as ei:
        _relogin_complete(ss, cs, ts, s)
    msg = str(ei.value)
    assert "was removed" not in msg
    assert "may still hold" in msg
    assert _KEY in ts.saved                          # the new token really is still there


def test_rollback_delete_false_with_nothing_stored_counts_as_removed():
    # Benign arm: delete() -> False but load() finds nothing → the terminal
    # state is clean, so compensation counts as landed.
    from src.auth_drivers.chatgpt_oauth_login import _rollback_relogin_token

    class _GoneTok(_TokStore):
        def delete(self, *, provider, auth_mode, credential_id):
            return False  # e.g. removed by another actor already

    ts = _GoneTok()                                  # nothing saved → load returns None
    assert _rollback_relogin_token(target="local:1", old_record=None, token_store=ts) is True
