"""S3 — OpenAIChatGPTOAuthDriver: per-auth-mode discovery + subscription stream.

The driver surfaces the ChatGPT/Codex backend's actual model list (the P2c shape:
plain models.list may 400, extra_query client_version returns ids) as a
ModelDiscoveryResult — so an openai chatgpt_oauth credential shows ITS models, not
the api_key seed catalog.

Execution is NOT the normal OpenAI API-key Agents SDK path: the ChatGPT backend
rejects max_output_tokens and does not support the SDK's previous_response_id loop.
The driver owns a raw Responses stream loop: stream=True, store=False, no
max_output_tokens, explicit function_call_output items.

Offline: the OpenAI client is built behind a monkeypatchable seam (_discovery_client)
+ the token is loaded from an injected token-store, so no network/token is needed.
"""

from __future__ import annotations

import asyncio
import time

import pytest

import src.auth_drivers.chatgpt_oauth_driver as mod
from src.agents.shared.events import EventType
from src.auth_drivers.chatgpt_oauth_driver import OpenAIChatGPTOAuthDriver
from src.auth_drivers.chatgpt_oauth_login import ChatGPTOAuthLoginError
from src.auth_drivers.protocol import LLMRequest
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


class _Responses:
    def __init__(self, streams):
        self.streams = list(streams)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self.streams:
            raise AssertionError("unexpected responses.create call")
        return self.streams.pop(0)


class _ExecClient:
    def __init__(self, streams):
        self.responses = _Responses(streams)


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


def _req(**kw):
    base = dict(
        model="gpt-5.4-mini",
        instructions="You are ArkScope.",
        input_messages=[{"role": "user", "content": "hi"}],
        reasoning_effort="low",
        max_output_tokens=128000,
    )
    base.update(kw)
    return LLMRequest(**base)


class _ToolDef:
    name = "get_price_change"
    description = "Get price change."
    parameters = []
    requires_dal = True

    @staticmethod
    def function(dal, **kwargs):
        return {"ok": True, "ticker": kwargs.get("ticker"), "change": 1.23}


class _Registry:
    def get(self, name):
        return _ToolDef() if name == "get_price_change" else None


class _SlowNewsBriefToolDef:
    name = "get_news_brief"
    description = "Slow news brief."
    parameters = []
    requires_dal = True

    @staticmethod
    def function(dal, **kwargs):
        time.sleep(0.05)
        return {"ok": True}


class _SlowNewsRegistry:
    def get(self, name):
        return _SlowNewsBriefToolDef() if name == "get_news_brief" else None


def _run(coro):
    return asyncio.run(coro)


async def _collect(agen):
    out = []
    async for ev in agen:
        out.append(ev)
    return out


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


def test_discover_drops_token_or_pii_shaped_ids(monkeypatch):
    # Defense-in-depth: a hostile/odd backend could reflect a token-/JWT-/email-shaped
    # string as a "model id". Those must be DROPPED (never surfaced into a picker),
    # keeping only well-formed model ids.
    bad = [
        {"id": "gpt-5.4-mini"},                                   # good
        {"id": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJsZWFrIn0.SIG"},   # JWT-shaped
        {"id": "user@example.com"},                               # email
        {"id": "sk-proj-" + "A" * 90},                            # long token
        {"id": "claude-opus-4-8"},                                # good (cross-provider id still well-formed)
    ]
    monkeypatch.setattr(mod, "_discovery_client", lambda token: _FakeClient(lambda kw: _FakePage(bad)))
    res = _run(_driver().discover_models())
    ids = [m.id for m in res.models]
    assert ids == ["gpt-5.4-mini", "claude-opus-4-8"]  # bad shapes dropped, good kept
    assert all(m.label == m.id for m in res.models)


def test_discover_all_ids_garbage_is_error_seed(monkeypatch):
    monkeypatch.setattr(mod, "_discovery_client",
                        lambda token: _FakeClient(lambda kw: _FakePage([{"id": "a@b.com"}, {"id": "x" * 200}])))
    res = _run(_driver().discover_models())
    assert res.status == "error" and all(m.source == "seed" for m in res.models)  # nothing well-formed → seed


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


# --- execution (S3 step 4) ---------------------------------------------------
def test_call_llm_collects_done_text(monkeypatch):
    client = _ExecClient([[
        {"type": "response.completed", "response": {"output": [
            {"type": "message", "content": [{"type": "output_text", "text": "OK"}]},
        ], "usage": {"input_tokens": 2, "output_tokens": 1, "total_tokens": 3}}},
    ]])
    monkeypatch.setattr(mod, "_execution_client", lambda token: client)
    res = _run(_driver().call_llm(_req()))
    assert res.text == "OK"
    assert res.usage.total_tokens == 3


def test_stream_llm_streams_text_done_and_strips_max_output_tokens(monkeypatch):
    client = _ExecClient([[
        {"type": "response.output_text.delta", "delta": "OK"},
        {"type": "response.completed", "response": {"output": [
            {"type": "message", "content": [{"type": "output_text", "text": "OK"}]},
        ], "usage": {"input_tokens": 3, "output_tokens": 1}}},
    ]])
    monkeypatch.setattr(mod, "_execution_client", lambda token: client)

    events = _run(_collect(_driver().stream_llm(_req())))

    assert [e.type for e in events] == [EventType.thinking, EventType.text, EventType.done]
    assert events[-1].data["answer"] == "OK"
    sent = client.responses.calls[0]
    assert sent["stream"] is True and sent["store"] is False
    assert sent["reasoning"] == {"effort": "low"}
    assert "max_output_tokens" not in sent
    assert "previous_response_id" not in sent


def test_stream_llm_runs_allowed_tool_and_continues_without_previous_response_id(monkeypatch):
    first = [
        {"type": "response.output_item.added",
         "item": {"type": "function_call", "name": "get_price_change", "call_id": "call_1"}},
        {"type": "response.function_call_arguments.done", "arguments": "{\"ticker\":\"AAPL\"}"},
        {"type": "response.completed", "response": {"output": [
            {"type": "function_call", "name": "get_price_change", "call_id": "call_1",
             "arguments": "{\"ticker\":\"AAPL\"}"},
        ]}},
    ]
    second = [
        {"type": "response.output_text.delta", "delta": "AAPL is up."},
        {"type": "response.completed", "response": {"output": [
            {"type": "message", "content": [{"type": "output_text", "text": "AAPL is up."}]},
        ]}},
    ]
    client = _ExecClient([first, second])
    monkeypatch.setattr(mod, "_execution_client", lambda token: client)

    d = OpenAIChatGPTOAuthDriver(credential=_Cred(7), token_store=_TokStore(), registry=_Registry(), dal=object())
    events = _run(_collect(d.stream_llm(_req())))

    assert [e.type for e in events] == [
        EventType.thinking, EventType.tool_start, EventType.tool_end, EventType.text, EventType.done,
    ]
    assert events[1].data == {"tool": "get_price_change", "input": {"ticker": "AAPL"}}
    assert events[2].data["tool"] == "get_price_change" and "AAPL" in events[2].data["summary"]
    followup = client.responses.calls[1]
    assert followup["stream"] is True and followup["store"] is False
    assert "previous_response_id" not in followup
    assert {"type": "function_call_output", "call_id": "call_1", "output": events[2].data["summary"]} in followup["input"]


def test_stream_llm_returns_tool_timeout_to_model_instead_of_terminal_error(monkeypatch):
    first = [
        {"type": "response.completed", "response": {"output": [
            {"type": "function_call", "name": "get_news_brief", "call_id": "call_1",
             "arguments": "{\"tickers\":[\"SNEX\"]}"},
        ]}},
    ]
    second = [
        {"type": "response.output_text.delta", "delta": "I could not read the news brief in time."},
        {"type": "response.completed", "response": {"output": [
            {"type": "message", "content": [{"type": "output_text", "text": "I could not read the news brief in time."}]},
        ]}},
    ]
    client = _ExecClient([first, second])
    monkeypatch.setattr(mod, "_execution_client", lambda token: client)
    d = OpenAIChatGPTOAuthDriver(
        credential=_Cred(7),
        token_store=_TokStore(),
        registry=_SlowNewsRegistry(),
        dal=object(),
        per_tool_timeout_s=0.001,
    )

    events = _run(_collect(d.stream_llm(_req())))

    assert [e.type for e in events] == [
        EventType.thinking, EventType.tool_start, EventType.tool_end, EventType.text, EventType.done,
    ]
    assert events[2].data["is_error"] is True
    assert "tool 'get_news_brief' timed out after 0.001s" in events[2].data["summary"]
    followup = client.responses.calls[1]
    assert {"type": "function_call_output", "call_id": "call_1", "output": events[2].data["summary"]} in followup["input"]


def test_stream_llm_uses_last_call_id_when_arguments_done_omits_id(monkeypatch):
    # Live P2b shape: function_call_arguments.done can omit call_id/item_id while
    # output_item.added carries the call_id. Use the most recent call item.
    first = [
        {"type": "response.output_item.added",
         "item": {"type": "function_call", "name": "get_price_change", "call_id": "call_1"}},
        {"type": "response.function_call_arguments.done", "arguments": "{\"ticker\":\"MSFT\"}"},
        {"type": "response.completed"},
    ]
    second = [
        {"type": "response.completed", "response": {"output": [
            {"type": "message", "content": [{"type": "output_text", "text": "done"}]},
        ]}},
    ]
    client = _ExecClient([first, second])
    monkeypatch.setattr(mod, "_execution_client", lambda token: client)
    d = OpenAIChatGPTOAuthDriver(credential=_Cred(7), token_store=_TokStore(), registry=_Registry(), dal=object())

    events = _run(_collect(d.stream_llm(_req())))

    assert events[1].data == {"tool": "get_price_change", "input": {"ticker": "MSFT"}}


def test_stream_llm_off_allowlist_tool_errors_without_calling_registry(monkeypatch):
    client = _ExecClient([[
        {"type": "response.completed", "response": {"output": [
            {"type": "function_call", "name": "delete_files", "call_id": "call_9", "arguments": "{}"},
        ]}},
    ]])
    monkeypatch.setattr(mod, "_execution_client", lambda token: client)

    class BoomRegistry:
        def get(self, name):
            if name == "delete_files":  # pragma: no cover - allowlist veto should fire first
                raise AssertionError("off-allowlist tool must not be looked up")
            return None

    d = OpenAIChatGPTOAuthDriver(credential=_Cred(7), token_store=_TokStore(), registry=BoomRegistry(), dal=object())
    events = _run(_collect(d.stream_llm(_req())))
    assert events[-1].type == EventType.error
    assert "not allowed" in events[-1].data["error"]


def test_test_defers_to_probe_when_token_present():
    res = _run(_driver().test())
    # honest: NOT a fake "ok"; points at the probe route for the real P1/P2 check.
    assert res.status in ("error", "missing_credential")
