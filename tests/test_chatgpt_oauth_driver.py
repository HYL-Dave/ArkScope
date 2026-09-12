"""S3 — OpenAIChatGPTOAuthDriver: per-auth-mode discovery + subscription stream.

The driver surfaces the Codex app-server's credential-bound ``model/list`` catalog
as a ModelDiscoveryResult, so an openai chatgpt_oauth credential shows ITS models,
efforts, and modalities rather than the api_key seed catalog.

Execution is NOT the normal OpenAI API-key Agents SDK path: the ChatGPT backend
rejects max_output_tokens and does not support the SDK's previous_response_id loop.
The driver owns a raw Responses stream loop: stream=True, store=False, no
max_output_tokens, explicit function_call_output items.

Offline: the catalog adapter and execution client are monkeypatchable seams, and the
token is loaded from an injected token-store, so no network/token is needed.
"""

from __future__ import annotations

import asyncio
import time

import pytest

import src.auth_drivers.chatgpt_oauth_driver as mod
from src.agents.shared.events import EventType
from src.auth_drivers.codex_account_usage import CodexSubscriptionModel
from src.auth_drivers.chatgpt_oauth_driver import OpenAIChatGPTOAuthDriver
from src.auth_drivers.chatgpt_oauth_login import ChatGPTOAuthLoginError
from src.auth_drivers.protocol import LLMRequest
from src.auth_drivers.token_store import StoredTokenRecord
from src.tools.result_policy import PUBLIC_JSON


class _Boom(Exception):
    pass


class _ApiErr(Exception):
    def __init__(self, status_code, msg=""):
        super().__init__(msg or f"HTTP {status_code}")
        self.status_code = status_code


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
        self.closed = False

    async def close(self):
        self.closed = True


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


def _catalog_model(model: str, *, label: str | None = None) -> CodexSubscriptionModel:
    return CodexSubscriptionModel(
        catalog_id=f"catalog-{model}",
        model=model,
        display_name=label or model,
        description="Subscription model fixture.",
        hidden=False,
        default_reasoning_effort="medium",
        supported_reasoning_efforts=("low", "medium", "high"),
        input_modalities=("text",),
        supports_personality=False,
        is_default=False,
    )


def _install_catalog(monkeypatch, *, models=(), error: Exception | None = None, seen=None):
    class CatalogAdapter:
        def read_model_catalog(self, *, record):
            if seen is not None:
                seen["token"] = record.access_token
            if error is not None:
                raise error
            return list(models)

    monkeypatch.setattr(mod, "_subscription_catalog_adapter", CatalogAdapter)


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
    result_policy = PUBLIC_JSON
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


class _VerboseToolDef:
    result_policy = PUBLIC_JSON
    name = "get_price_change"
    description = "Get price change."
    parameters = []
    requires_dal = True

    @staticmethod
    def function(dal, **kwargs):
        return {
            "ok": True,
            "ticker": kwargs.get("ticker"),
            "analysis": "AAPL detailed local result " + ("abcdefghi " * 50),
        }


class _VerboseRegistry:
    def get(self, name):
        return _VerboseToolDef() if name == "get_price_change" else None


class _SlowNewsBriefToolDef:
    result_policy = PUBLIC_JSON
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
def test_discover_uses_app_server_catalog_and_keeps_subscription_only_model_metadata(monkeypatch):
    class CatalogAdapter:
        def read_model_catalog(self, *, record):
            assert record.access_token == "cg-FRESH"
            return [
                CodexSubscriptionModel(
                    catalog_id="catalog-entry-spark",
                    model="gpt-5.3-codex-spark",
                    display_name="GPT-5.3-Codex-Spark",
                    description="Ultra-fast coding model.",
                    hidden=False,
                    default_reasoning_effort="medium",
                    supported_reasoning_efforts=("low", "medium", "high", "xhigh"),
                    input_modalities=("text",),
                    supports_personality=False,
                    is_default=False,
                )
            ]

    monkeypatch.setattr(
        mod,
        "_refresh_login",
        lambda **_: StoredTokenRecord(access_token="cg-FRESH", plan_type="pro"),
    )
    monkeypatch.setattr(mod, "_subscription_catalog_adapter", CatalogAdapter, raising=False)

    result = _run(_driver().discover_models())

    assert result.status == "ok"
    assert [model.id for model in result.models] == ["gpt-5.3-codex-spark"]
    spark = result.models[0]
    assert spark.label == "GPT-5.3-Codex-Spark"
    assert spark.effort_options == ["low", "medium", "high", "xhigh"]
    assert spark.default_effort == "medium"
    assert spark.input_modalities == ["text"]
    assert spark.task_route_tasks == ["card_translation"]


@pytest.mark.parametrize("plan_type", ["pro", "prolite", "plus", None])
def test_spark_discovery_advertises_translation_from_exact_model_not_plan_name(
    monkeypatch,
    plan_type,
):
    _install_catalog(monkeypatch, models=(_catalog_model("gpt-5.3-codex-spark"),))
    monkeypatch.setattr(
        mod,
        "_refresh_login",
        lambda **_: StoredTokenRecord(access_token="cg-FRESH", plan_type=plan_type),
    )

    result = _run(_driver().discover_models())

    assert result.status == "ok"
    assert result.models[0].task_route_tasks == ["card_translation"]


def test_spark_discovery_does_not_advertise_a_case_variant_as_the_exact_model(
    monkeypatch,
):
    _install_catalog(monkeypatch, models=(_catalog_model("GPT-5.3-CODEX-SPARK"),))
    monkeypatch.setattr(
        mod,
        "_refresh_login",
        lambda **_: StoredTokenRecord(access_token="cg-FRESH", plan_type="prolite"),
    )

    result = _run(_driver().discover_models())

    assert result.status == "ok"
    assert result.models[0].id == "GPT-5.3-CODEX-SPARK"
    assert result.models[0].task_route_tasks == []


def test_discovery_persists_live_plan_without_changing_token_material(
    monkeypatch,
    tmp_path,
):
    class TokenStore:
        def __init__(self):
            self.record = StoredTokenRecord(
                access_token="cg-ORIGINAL",
                refresh_token="cg-REFRESH",
                plan_type=None,
                metadata={"account_id": "acct_123"},
            )

        def load(self, *, provider, auth_mode, credential_id):
            assert (provider, auth_mode, credential_id) == (
                "openai",
                "chatgpt_oauth",
                "local:7",
            )
            return self.record

        def save(self, *, provider, auth_mode, credential_id, record):
            assert (provider, auth_mode, credential_id) == (
                "openai",
                "chatgpt_oauth",
                "local:7",
            )
            self.record = record

    class CatalogAdapter:
        def read_model_catalog_with_plan(self, *, record):
            assert record.access_token == "cg-ORIGINAL"
            return [_catalog_model("gpt-5.3-codex-spark")], "pro"

    token_store = TokenStore()
    original = token_store.record
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setattr(mod, "_refresh_login", lambda **_: original)
    monkeypatch.setattr(mod, "_subscription_catalog_adapter", CatalogAdapter)

    result = _run(
        OpenAIChatGPTOAuthDriver(
            credential=_Cred(7),
            token_store=token_store,
        ).discover_models()
    )

    assert result.status == "ok"
    assert result.models[0].task_route_tasks == ["card_translation"]
    assert token_store.record.plan_type == "pro"
    assert token_store.record.plan_observed_at is not None
    assert token_store.record.access_token == original.access_token
    assert token_store.record.refresh_token == original.refresh_token
    assert token_store.record.metadata == original.metadata


def test_discovery_keeps_exact_catalog_when_plan_diagnostic_save_fails(
    monkeypatch,
):
    original = StoredTokenRecord(access_token="cg-ORIGINAL", plan_type=None)

    class CatalogAdapter:
        def read_model_catalog_with_plan(self, *, record):
            assert record is original
            return [_catalog_model("gpt-5.3-codex-spark")], "prolite"

    def fail_diagnostic_write(**_kwargs):
        raise ChatGPTOAuthLoginError(
            "diagnostic write failed",
            error_code="plan_observation_store_failed",
        )

    monkeypatch.setattr(mod, "_refresh_login", lambda **_: original)
    monkeypatch.setattr(mod, "_subscription_catalog_adapter", CatalogAdapter)
    monkeypatch.setattr(mod, "persist_chatgpt_plan_observation", fail_diagnostic_write)

    result = _run(_driver().discover_models())

    assert result.status == "ok"
    assert result.models[0].id == "gpt-5.3-codex-spark"
    assert result.models[0].task_route_tasks == ["card_translation"]


def test_discovery_rejects_catalog_when_token_generation_changed(monkeypatch):
    original = StoredTokenRecord(access_token="cg-ORIGINAL", plan_type=None)

    class CatalogAdapter:
        def read_model_catalog_with_plan(self, *, record):
            assert record is original
            return [_catalog_model("gpt-5.3-codex-spark")], "prolite"

    def reject_stale_generation(**_kwargs):
        raise ChatGPTOAuthLoginError(
            "credential changed",
            error_code="credential_changed_during_sync",
        )

    monkeypatch.setattr(mod, "_refresh_login", lambda **_: original)
    monkeypatch.setattr(mod, "_subscription_catalog_adapter", CatalogAdapter)
    monkeypatch.setattr(mod, "persist_chatgpt_plan_observation", reject_stale_generation)

    result = _run(_driver().discover_models())

    assert result.status == "error"
    assert all(model.id != "gpt-5.3-codex-spark" for model in result.models)


def test_discovery_accepts_exact_catalog_when_live_plan_is_absent(
    monkeypatch,
):
    original = StoredTokenRecord(access_token="cg-ORIGINAL", plan_type=None)

    class CatalogAdapter:
        def read_model_catalog_with_plan(self, *, record):
            assert record is original
            return [_catalog_model("gpt-5.3-codex-spark")], None

    monkeypatch.setattr(mod, "_refresh_login", lambda **_: original)
    monkeypatch.setattr(mod, "_subscription_catalog_adapter", CatalogAdapter)

    result = _run(_driver().discover_models())

    assert result.status == "ok"
    assert result.models[0].task_route_tasks == ["card_translation"]


def test_discover_keeps_reviewed_current_models_available_to_existing_task_routes(monkeypatch):
    _install_catalog(monkeypatch, models=(_catalog_model("gpt-5.6-sol"),))

    result = _run(_driver().discover_models())

    assert result.status == "ok"
    assert result.models[0].task_route_tasks == [
        "card_synthesis",
        "card_translation",
        "ai_research",
        "lifecycle_investigation",
    ]


def test_discover_returns_live_ids_as_provider_api(monkeypatch):
    _install_catalog(
        monkeypatch,
        models=(_catalog_model("gpt-5.4-mini"), _catalog_model("gpt-5.5")),
    )
    res = _run(_driver().discover_models())
    assert res.status == "ok" and res.provider == "openai" and res.credential_id == "local:7"
    assert [m.id for m in res.models] == ["gpt-5.4-mini", "gpt-5.5"]
    assert all(m.source == "provider_api" for m in res.models)  # LIVE, not seed


def test_discover_no_token_is_missing_credential_seed(monkeypatch):
    # never reach the network without a token; fall back to the seed candidate list.
    called = {"n": 0}
    monkeypatch.setattr(
        mod,
        "_subscription_catalog_adapter",
        lambda: called.__setitem__("n", called["n"] + 1),
    )
    res = _run(_driver(token="").discover_models())
    assert res.status == "missing_credential" and called["n"] == 0
    assert len(res.models) > 0 and all(m.source == "seed" for m in res.models)


def test_discover_backend_error_falls_back_to_seed_redacted(monkeypatch):
    tok = "cg-SECRET-TOKEN-abc123"
    _install_catalog(monkeypatch, error=_Boom(f"500 backend boom leaking {tok}"))
    res = _run(OpenAIChatGPTOAuthDriver(credential=_Cred(7), token_store=_TokStore(tok)).discover_models())
    assert res.status == "error" and all(m.source == "seed" for m in res.models)  # honest fallback
    assert res.error and tok not in res.error  # the token must never leak into the surfaced error


def test_discover_empty_ids_is_error_with_seed(monkeypatch):
    _install_catalog(monkeypatch)
    res = _run(_driver().discover_models())
    assert res.status == "error" and all(m.source == "seed" for m in res.models)


# --- Step 1.1: refresh-before-discovery (access tokens rotate) ----------------
def test_discover_uses_refreshed_token(monkeypatch):
    # discovery refreshes the (possibly expired) token FIRST, then queries with the
    # fresh access_token — so "available models" doesn't intermittently degrade.
    monkeypatch.setattr(mod, "_refresh_login",
                        lambda *, credential_id, token_store, **kw: StoredTokenRecord(access_token="cg-FRESH"))
    used = {}

    _install_catalog(monkeypatch, models=(_catalog_model("gpt-5.5"),), seen=used)
    res = _run(_driver().discover_models())
    assert res.status == "ok" and used["token"] == "cg-FRESH"  # the refreshed token was used


def test_discover_refresh_failure_returns_relogin_error_redacted(monkeypatch):
    # This emulates a 401 refresh rejection — since S3's classification (round 4)
    # the fake raises the CLASSIFIED shape refresh_if_needed actually produces,
    # and the re-login hint is only promised on that arm.
    tok = "cg-SECRET-TOKEN-xyz789"

    def boom(*, credential_id, token_store, **kw):
        raise ChatGPTOAuthLoginError(f"refresh failed (401) {tok}", status_code=401, reauth_required=True)

    monkeypatch.setattr(mod, "_refresh_login", boom)
    res = _run(OpenAIChatGPTOAuthDriver(credential=_Cred(7), token_store=_TokStore(tok)).discover_models())
    assert res.status == "error" and all(m.source == "seed" for m in res.models)  # honest fallback
    assert res.error and tok not in res.error  # token never leaks
    assert "re-login" in res.error  # actionable re-login hint (classified arm only)


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


@pytest.mark.parametrize(
    ("effort", "expected"),
    [
        ("default", None),
        ("none", {"effort": "none"}),
        ("low", {"effort": "low"}),
        ("xhigh", {"effort": "xhigh"}),
        ("max", {"effort": "max"}),
    ],
)
def test_stream_llm_sends_selected_effort_without_silent_coercion(monkeypatch, effort, expected):
    client = _ExecClient([[
        {"type": "response.completed", "response": {"output": [
            {"type": "message", "content": [{"type": "output_text", "text": "OK"}]},
        ]}},
    ]])
    monkeypatch.setattr(mod, "_execution_client", lambda token: client)

    _run(_collect(_driver().stream_llm(_req(reasoning_effort=effort))))

    assert client.responses.calls[0].get("reasoning") == expected


def test_stream_llm_closes_execution_client_when_consumer_stops_early(monkeypatch):
    client = _ExecClient([[
        {"type": "response.completed", "response": {"output": [
            {"type": "message", "content": [{"type": "output_text", "text": "OK"}]},
        ]}},
    ]])
    monkeypatch.setattr(mod, "_execution_client", lambda token: client)

    async def stop_after_first_event():
        stream = _driver().stream_llm(_req())
        await stream.__anext__()
        await stream.aclose()

    _run(stop_after_first_event())

    assert client.closed is True


def test_stream_llm_preserves_openai_cached_token_usage(monkeypatch):
    client = _ExecClient([[
        {"type": "response.output_text.delta", "delta": "OK"},
        {"type": "response.completed", "response": {"output": [
            {"type": "message", "content": [{"type": "output_text", "text": "OK"}]},
        ], "usage": {
            "input_tokens": 9000,
            "output_tokens": 20,
            "total_tokens": 9020,
            "prompt_tokens_details": {"cached_tokens": 8192},
        }}},
    ]])
    monkeypatch.setattr(mod, "_execution_client", lambda token: client)

    events = _run(_collect(_driver().stream_llm(_req())))

    usage = events[-1].data["token_usage"]
    assert usage["input_tokens"] == 9000
    assert usage["output_tokens"] == 20
    assert usage["total_tokens"] == 9020
    assert usage["cache_read_tokens"] == 8192


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


def test_stream_llm_sends_full_reduced_tool_result_to_model_not_ui_preview(monkeypatch):
    first = [
        {"type": "response.completed", "response": {"output": [
            {"type": "function_call", "name": "get_price_change", "call_id": "call_1",
             "arguments": "{\"ticker\":\"AAPL\"}"},
        ]}},
    ]
    second = [
        {"type": "response.output_text.delta", "delta": "I used the detailed result."},
        {"type": "response.completed", "response": {"output": [
            {"type": "message", "content": [{"type": "output_text", "text": "I used the detailed result."}]},
        ]}},
    ]
    client = _ExecClient([first, second])
    monkeypatch.setattr(mod, "_execution_client", lambda token: client)
    d = OpenAIChatGPTOAuthDriver(
        credential=_Cred(7),
        token_store=_TokStore(),
        registry=_VerboseRegistry(),
        dal=object(),
    )

    events = _run(_collect(d.stream_llm(_req())))

    tool_end = events[2].data
    assert len(tool_end["summary"]) == 200
    assert tool_end["chars"] > len(tool_end["summary"])
    followup = client.responses.calls[1]
    outputs = [item["output"] for item in followup["input"] if item.get("type") == "function_call_output"]
    assert len(outputs) == 1
    assert outputs[0] != tool_end["summary"]
    assert "abcdefghi " * 20 in outputs[0]


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

    assert [e.type for e in events if e.type != EventType.text] == [
        EventType.thinking, EventType.tool_start, EventType.tool_end, EventType.done,
    ]
    assert events[-1].type == EventType.done
    text = "".join(e.data["content"] for e in events if e.type == EventType.text)
    assert text == events[-1].data["answer"] == "I could not read the news brief in time."
    assert events[2].data["is_error"] is True
    assert "tool 'get_news_brief' timed out after 0.001s" in events[2].data["summary"]
    assert len(client.responses.calls) == 2
    followup = client.responses.calls[1]
    assert {"type": "function_call_output", "call_id": "call_1", "output": events[2].data["summary"]} in followup["input"]


def test_stream_llm_overall_timeout_errors(monkeypatch):
    async def slow_stream():
        await asyncio.sleep(0.05)
        yield {"type": "response.completed", "response": {"output": [
            {"type": "message", "content": [{"type": "output_text", "text": "late"}]},
        ]}}

    client = _ExecClient([slow_stream()])
    monkeypatch.setattr(mod, "_execution_client", lambda token: client)
    d = OpenAIChatGPTOAuthDriver(credential=_Cred(7), token_store=_TokStore(), timeout_s=0.001)

    events = _run(_collect(d.stream_llm(_req())))

    assert events[-1].type == EventType.error
    assert "timed out after 0.001s" in events[-1].data["error"]


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


# --- reauth classification (S3 credential-lifecycle hotfix) ---------------------
def test_discover_models_refresh_401_sets_reauth_error_code(monkeypatch):
    def boom(*, credential_id, token_store, **kw):
        raise ChatGPTOAuthLoginError("refresh failed (401)", status_code=401, reauth_required=True)

    monkeypatch.setattr(mod, "_refresh_login", boom)
    res = _run(_driver().discover_models())
    assert res.status == "error"
    assert res.error_code == "reauth_required"
    assert all(m.source == "seed" for m in res.models)      # seeds stay candidates


def test_discover_models_transient_failure_has_no_error_code(monkeypatch):
    def boom(*, credential_id, token_store, **kw):
        raise ChatGPTOAuthLoginError("refresh failed: network unreachable", status_code=None)

    monkeypatch.setattr(mod, "_refresh_login", boom)
    res = _run(_driver().discover_models())
    assert res.status == "error" and res.error_code is None


def test_stream_refresh_401_event_carries_code(monkeypatch):
    def boom(*, credential_id, token_store, **kw):
        raise ChatGPTOAuthLoginError("refresh failed (401)", status_code=401, reauth_required=True)

    monkeypatch.setattr(mod, "_refresh_login", boom)
    events = _run(_collect(_driver().stream_llm(_req())))
    errs = [e for e in events if e.type == EventType.error]
    assert len(errs) == 1 and errs[0].data.get("code") == "reauth_required"


@pytest.mark.parametrize(
    ("status_code", "expected_code"),
    [(401, "reauth_required"), (404, None)],
)
def test_stream_backend_error_only_classifies_auth_rejection_as_reauth(
    monkeypatch, status_code, expected_code
):
    class FailingResponses:
        def create(self, **kwargs):
            raise _ApiErr(status_code, f"backend rejected request ({status_code})")

    class FailingClient:
        responses = FailingResponses()

        async def close(self):
            return None

    monkeypatch.setattr(mod, "_execution_client", lambda token: FailingClient())

    events = _run(_collect(_driver().stream_llm(_req())))

    errors = [event for event in events if event.type == EventType.error]
    assert len(errors) == 1
    assert errors[0].data.get("code") == expected_code


def test_discover_missing_token_requires_reauth():
    # token-store dependency + credential id PRESENT, stored token absent →
    # the OAuth row is repairable ONLY by re-login.
    res = _run(_driver(token="").discover_models())
    assert res.status == "missing_credential"
    assert res.error_code == "reauth_required"
    assert all(m.source == "seed" for m in res.models)


def test_stream_missing_token_yields_reauth_event(monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(mod, "_execution_client",
                        lambda token: called.__setitem__("n", called["n"] + 1))
    events = _run(_collect(_driver(token="").stream_llm(_req())))
    errs = [e for e in events if e.type == EventType.error]
    assert len(errs) == 1 and errs[0].data.get("code") == "reauth_required"
    assert called["n"] == 0                                  # classified event, no backend call


def test_discover_missing_driver_wiring_is_not_reauth():
    # wiring/config arms — re-login cannot repair these; NO re-login affordance.
    no_store = OpenAIChatGPTOAuthDriver(credential=_Cred(7), token_store=None)
    res = _run(no_store.discover_models())
    assert res.status == "missing_credential" and res.error_code == "missing_credential"
    no_cid = _driver()
    no_cid._credential_id = ""
    res2 = _run(no_cid.discover_models())
    assert res2.status == "missing_credential" and res2.error_code == "missing_credential"


def test_stream_missing_driver_wiring_yields_non_reauth_event(monkeypatch):
    called = {"n": 0}
    monkeypatch.setattr(mod, "_execution_client",
                        lambda token: called.__setitem__("n", called["n"] + 1))
    no_store = OpenAIChatGPTOAuthDriver(credential=_Cred(7), token_store=None)
    events = _run(_collect(no_store.stream_llm(_req())))
    errs = [e for e in events if e.type == EventType.error]
    assert len(errs) == 1 and errs[0].data.get("code") == "missing_credential"
    no_cid = _driver()
    no_cid._credential_id = ""
    events2 = _run(_collect(no_cid.stream_llm(_req())))
    errs2 = [e for e in events2 if e.type == EventType.error]
    assert len(errs2) == 1 and errs2[0].data.get("code") == "missing_credential"
    assert called["n"] == 0                                  # never a bare exception, never a call


def test_refresh_failure_message_split_by_reauth(monkeypatch):
    # F3 (review round 4): the human-readable error must not demand re-login for
    # a transient failure — the message splits with the code.
    def transient(*, credential_id, token_store, **kw):
        raise ChatGPTOAuthLoginError("refresh failed: network unreachable", status_code=None)

    monkeypatch.setattr(mod, "_refresh_login", transient)
    res = _run(_driver().discover_models())
    assert res.error_code is None
    assert "re-login" not in (res.error or "")
    assert "temporary" in (res.error or "").lower()

    def reauth(*, credential_id, token_store, **kw):
        raise ChatGPTOAuthLoginError("refresh failed (401)", status_code=401, reauth_required=True)

    monkeypatch.setattr(mod, "_refresh_login", reauth)
    res2 = _run(_driver().discover_models())
    assert res2.error_code == "reauth_required"
    assert "re-login needed" in (res2.error or "")
