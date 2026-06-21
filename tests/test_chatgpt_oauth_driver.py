"""S3 step 1 — OpenAIChatGPTOAuthDriver: per-auth-mode READ-ONLY model discovery.

The driver surfaces the ChatGPT/Codex backend's actual model list (the P2c shape:
plain models.list may 400, extra_query client_version returns ids) as a
ModelDiscoveryResult — so an openai chatgpt_oauth credential shows ITS models, not
the api_key seed catalog. Execution (call_llm/stream_llm) stays gated (S3 step 4).

Offline: the OpenAI client is built behind a monkeypatchable seam (_discovery_client)
+ the token is loaded from an injected token-store, so no network/token is needed.
"""

from __future__ import annotations

import asyncio

import pytest

import src.auth_drivers.chatgpt_oauth_driver as mod
from src.auth_drivers.chatgpt_oauth_driver import OpenAIChatGPTOAuthDriver
from src.auth_drivers.chatgpt_oauth_login import ChatGPTOAuthLoginError
from src.auth_drivers.token_store import StoredTokenRecord


class _Boom(Exception):
    pass


class _ApiErr(Exception):
    def __init__(self, status_code, msg=""):
        super().__init__(msg or f"HTTP {status_code}")
        self.status_code = status_code


class _FakePage:
    def __init__(self, models):
        self.models = models  # nonstandard `models` field (no `data`)


class _Models:
    def __init__(self, on_list):
        self._on_list = on_list

    def list(self, **kwargs):
        return self._on_list(kwargs)


class _FakeClient:
    def __init__(self, on_list):
        self.models = _Models(on_list)


class _Cred:
    def __init__(self, cid=7):
        self.id = cid


class _TokStore:
    def __init__(self, token="cg-FAKE-TOKEN"):
        self._token = token

    def load(self, *, provider, auth_mode, credential_id):
        if not self._token:
            return None
        assert provider == "openai" and auth_mode == "chatgpt_oauth"
        return StoredTokenRecord(access_token=self._token)


def _driver(token="cg-FAKE-TOKEN"):
    return OpenAIChatGPTOAuthDriver(credential=_Cred(7), token_store=_TokStore(token))


def _run(coro):
    return asyncio.run(coro)


# --- identity ----------------------------------------------------------------
def test_identity():
    d = _driver()
    assert d.provider == "openai" and d.auth_mode == "chatgpt_oauth"
    assert d.is_authenticated is True


def test_unauthenticated_without_token():
    assert _driver(token="").is_authenticated is False


# --- discover_models ---------------------------------------------------------
def test_discover_returns_live_ids_as_provider_api(monkeypatch):
    def on_list(kw):
        eq = kw.get("extra_query") or {}
        if "client_version" not in eq:
            raise _ApiErr(400, "missing client_version")
        return _FakePage([{"id": "gpt-5.4-mini"}, {"id": "gpt-5.5"}])

    monkeypatch.setattr(mod, "_discovery_client", lambda token: _FakeClient(on_list))
    res = _run(_driver().discover_models())
    assert res.status == "ok" and res.provider == "openai" and res.credential_id == "local:7"
    assert [m.id for m in res.models] == ["gpt-5.4-mini", "gpt-5.5"]
    assert all(m.source == "provider_api" for m in res.models)  # LIVE, not seed


def test_discover_no_token_is_missing_credential_seed(monkeypatch):
    # never reach the network without a token; fall back to the seed candidate list.
    called = {"n": 0}
    monkeypatch.setattr(mod, "_discovery_client", lambda token: called.__setitem__("n", called["n"] + 1))
    res = _run(_driver(token="").discover_models())
    assert res.status == "missing_credential" and called["n"] == 0
    assert len(res.models) > 0 and all(m.source == "seed" for m in res.models)


def test_discover_backend_error_falls_back_to_seed_redacted(monkeypatch):
    tok = "cg-SECRET-TOKEN-abc123"

    def on_list(kw):
        raise _Boom(f"500 backend boom leaking {tok}")

    monkeypatch.setattr(mod, "_discovery_client", lambda token: _FakeClient(on_list))
    res = _run(OpenAIChatGPTOAuthDriver(credential=_Cred(7), token_store=_TokStore(tok)).discover_models())
    assert res.status == "error" and all(m.source == "seed" for m in res.models)  # honest fallback
    assert res.error and tok not in res.error  # the token must never leak into the surfaced error


def test_discover_empty_ids_is_error_with_seed(monkeypatch):
    monkeypatch.setattr(mod, "_discovery_client", lambda token: _FakeClient(lambda kw: _FakePage([])))
    res = _run(_driver().discover_models())
    assert res.status == "error" and all(m.source == "seed" for m in res.models)


def test_discover_plain_list_succeeds_without_extra_query(monkeypatch):
    # if the backend serves a plain models.list (no 400), use it directly.
    monkeypatch.setattr(mod, "_discovery_client",
                        lambda token: _FakeClient(lambda kw: _FakePage([{"id": "gpt-5.5"}])))
    res = _run(_driver().discover_models())
    assert res.status == "ok" and [m.id for m in res.models] == ["gpt-5.5"]


# --- Step 1.1: refresh-before-discovery (access tokens rotate) ----------------
def test_discover_uses_refreshed_token(monkeypatch):
    # discovery refreshes the (possibly expired) token FIRST, then queries with the
    # fresh access_token — so "available models" doesn't intermittently degrade.
    monkeypatch.setattr(mod, "_refresh_login",
                        lambda *, credential_id, token_store, **kw: StoredTokenRecord(access_token="cg-FRESH"))
    used = {}

    def client(token):
        used["token"] = token
        return _FakeClient(lambda kw: _FakePage([{"id": "gpt-5.5"}]))

    monkeypatch.setattr(mod, "_discovery_client", client)
    res = _run(_driver().discover_models())
    assert res.status == "ok" and used["token"] == "cg-FRESH"  # the refreshed token was used


def test_discover_refresh_failure_returns_relogin_error_redacted(monkeypatch):
    tok = "cg-SECRET-TOKEN-xyz789"

    def boom(*, credential_id, token_store, **kw):
        raise ChatGPTOAuthLoginError(f"refresh failed (401) {tok}")

    monkeypatch.setattr(mod, "_refresh_login", boom)
    res = _run(OpenAIChatGPTOAuthDriver(credential=_Cred(7), token_store=_TokStore(tok)).discover_models())
    assert res.status == "error" and all(m.source == "seed" for m in res.models)  # honest fallback
    assert res.error and tok not in res.error  # token never leaks
    assert "login" in res.error.lower() or "auth" in res.error.lower()  # actionable re-login hint


def test_refresh_if_needed_delegates_to_login(monkeypatch):
    seen = {}
    monkeypatch.setattr(mod, "_refresh_login",
                        lambda *, credential_id, token_store, **kw: seen.update(cid=credential_id) or StoredTokenRecord(access_token="x"))
    _run(_driver().refresh_if_needed())
    assert seen.get("cid") == "local:7"


# --- execution stays gated (S3 step 4) ---------------------------------------
def test_call_llm_raises_not_wired():
    with pytest.raises(NotImplementedError):
        _run(_driver().call_llm(object()))


def test_stream_llm_raises_not_wired():
    with pytest.raises(NotImplementedError):
        _driver().stream_llm(object())


def test_test_defers_to_probe_when_token_present():
    res = _run(_driver().test())
    # honest: NOT a fake "ok"; points at the probe route for the real P1/P2 check.
    assert res.status in ("error", "missing_credential")
