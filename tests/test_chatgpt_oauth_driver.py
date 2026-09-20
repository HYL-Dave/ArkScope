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
    def __init__(self):
        from src.tools.registry import ToolRegistry
        self.sec = ToolRegistry()
        self.sec._register_sec_research_tools()

    def get(self, name):
        return _ToolDef() if name == "get_price_change" else self.sec.get(name)


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


class _VerboseRegistry(_Registry):
    def get(self, name):
        return _VerboseToolDef() if name == "get_price_change" else self.sec.get(name)


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


class _SlowNewsRegistry(_Registry):
    def get(self, name):
        return _SlowNewsBriefToolDef() if name == "get_news_brief" else self.sec.get(name)


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
    assert spark.task_route_tasks == []


@pytest.mark.parametrize("plan_type", ["pro", "prolite", "plus", None])
def test_spark_discovery_never_advertises_a_task_regardless_of_plan(
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
    assert result.models[0].task_route_tasks == []


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
    assert result.models[0].task_route_tasks == []
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
    assert result.models[0].task_route_tasks == []


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
    assert result.models[0].task_route_tasks == []


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


def test_tool_free_driver_call_preserves_calibration_and_canary_contract(monkeypatch):
    client = _ExecClient([[
        {"type": "response.completed", "response": {"output": [
            {"type": "message", "content": [{"type": "output_text", "text": "OK"}]},
        ]}},
    ]])
    monkeypatch.setattr(mod, "_execution_client", lambda token: client)
    driver = OpenAIChatGPTOAuthDriver(credential=_Cred(7), token_store=_TokStore(),
                                    registry=None, max_turns=1)
    result = _run(driver.call_llm(_req(tools=[])))
    assert result.text == "OK"
    assert client.responses.calls[0].get("tools", []) == []


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
    assert events[1].data == {"tool": "get_price_change", "input": {"ticker": "AAPL"}, "call_id": "call_1"}
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


def test_stream_llm_uses_single_call_when_arguments_done_omits_identity(monkeypatch):
    # Live P2b shape: function_call_arguments.done can omit call_id/item_id while
    # output_item.added carries the call_id. Only one call is unambiguous.
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

    assert events[1].data == {"tool": "get_price_change", "input": {"ticker": "MSFT"}, "call_id": "call_1"}
    assert [event.type for event in events if event.type in (EventType.done, EventType.error)] == [EventType.done]
    assert len(client.responses.calls) == 2
    assert client.closed is True


def _function_item(*, item_id="fc_1", call_id="call_1", arguments="", status="in_progress"):
    return {
        "type": "function_call", "id": item_id, "call_id": call_id,
        "name": "get_price_change", "arguments": arguments, "status": status,
    }


def _completed_event(output=()):
    return {"type": "response.completed", "response": {"status": "completed", "output": list(output)}}


def _function_stream(monkeypatch, first):
    invocations = []
    function = _ToolDef.function

    def record(dal, **kwargs):
        invocations.append(kwargs.copy())
        return function(dal, **kwargs)

    client = _ExecClient([first, [_completed_event([
        {"type": "message", "content": [{"type": "output_text", "text": "done"}]},
    ])]])
    monkeypatch.setattr(_ToolDef, "function", staticmethod(record))
    monkeypatch.setattr(mod, "_execution_client", lambda token: client)
    driver = OpenAIChatGPTOAuthDriver(
        credential=_Cred(7), token_store=_TokStore(), registry=_Registry(), dal=object(),
    )
    return driver, client, invocations


def _run_function_stream(monkeypatch, first):
    driver, client, invocations = _function_stream(monkeypatch, first)
    events = _run(_collect(driver.stream_llm(_req())))
    return events, client, invocations


def test_stream_llm_completed_empty_output_executes_once_without_duplicate_followup(monkeypatch):
    events, client, invocations = _run_function_stream(monkeypatch, [
        {"type": "response.output_item.added", "output_index": 0, "item": _function_item()},
        {"type": "response.function_call_arguments.done", "output_index": 0,
         "item_id": "fc_1", "arguments": '{"ticker":"AAPL"}'},
        {"type": "response.output_item.done", "output_index": 0,
         "item": _function_item(arguments='{"ticker":"AAPL"}', status="completed")},
        _completed_event(),
    ])

    assert invocations == [{"ticker": "AAPL"}]
    assert [event.type for event in events] == [
        EventType.thinking, EventType.tool_start, EventType.tool_end, EventType.done,
    ]
    assert events[1].data == {"tool": "get_price_change", "call_id": "call_1", "input": {"ticker": "AAPL"}}
    assert events[-1].data["answer"] == "done"
    assert len(client.responses.calls) == 2
    assert client.responses.calls[1]["input"] == [
        {"role": "user", "content": "hi"},
        {"type": "function_call", "name": "get_price_change", "call_id": "call_1",
         "arguments": '{"ticker":"AAPL"}'},
        {"type": "function_call_output", "call_id": "call_1", "output": events[2].data["summary"]},
    ]
    assert client.closed is True


def test_stream_llm_interleaved_calls_keep_identity_and_first_seen_order(monkeypatch):
    first = _function_item(item_id="fc_a", call_id="call_a")
    second = _function_item(item_id="fc_b", call_id="call_b")
    events, client, invocations = _run_function_stream(monkeypatch, [
        {"type": "response.output_item.added", "output_index": 0, "item": first},
        {"type": "response.output_item.added", "output_index": 1, "item": second},
        {"type": "response.function_call_arguments.done", "output_index": 1,
         "item_id": "fc_b", "arguments": '{"ticker":"MSFT"}'},
        {"type": "response.output_item.done", "output_index": 1, "item": dict(second, status="completed")},
        {"type": "response.function_call_arguments.done", "output_index": 0,
         "item_id": "fc_a", "arguments": '{"ticker":"AAPL"}'},
        {"type": "response.output_item.done", "output_index": 0, "item": dict(first, status="completed")},
        _completed_event(),
    ])

    assert invocations == [{"ticker": "AAPL"}, {"ticker": "MSFT"}]
    assert [event.data["call_id"] for event in events if event.type == EventType.tool_start] == ["call_a", "call_b"]
    assert [event.data["call_id"] for event in events if event.type == EventType.tool_end] == ["call_a", "call_b"]
    assert len(client.responses.calls) == 2
    assert [(item["type"], item["call_id"]) for item in client.responses.calls[1]["input"][1:]] == [
        ("function_call", "call_a"), ("function_call_output", "call_a"),
        ("function_call", "call_b"), ("function_call_output", "call_b"),
    ]


@pytest.mark.parametrize("completion_order", [(0, 1), (1, 0)], ids=["wire-order", "reverse-completion"])
def test_stream_llm_idless_interleaved_arguments_use_output_index(monkeypatch, completion_order):
    arguments = ['{"ticker":"AAPL"}', '{"ticker":"MSFT"}']
    events, client, invocations = _run_function_stream(monkeypatch, [
        {"type": "response.output_item.added", "output_index": 0,
         "item": _function_item(item_id="fc_a", call_id="call_a")},
        {"type": "response.output_item.added", "output_index": 1,
         "item": _function_item(item_id="fc_b", call_id="call_b")},
        *[{"type": "response.function_call_arguments.done", "output_index": index,
           "arguments": arguments[index]} for index in completion_order],
        _completed_event(),
    ])

    assert invocations == [{"ticker": "AAPL"}, {"ticker": "MSFT"}]
    assert [event.data for event in events if event.type == EventType.tool_start] == [
        {"tool": "get_price_change", "call_id": "call_a", "input": {"ticker": "AAPL"}},
        {"tool": "get_price_change", "call_id": "call_b", "input": {"ticker": "MSFT"}},
    ]
    assert [event.type for event in events] == [
        EventType.thinking, EventType.tool_start, EventType.tool_end,
        EventType.tool_start, EventType.tool_end, EventType.done,
    ]
    assert events[-1].data["answer"] == "done"
    assert len(client.responses.calls) == 2
    assert [(item["call_id"], item["arguments"]) for item in client.responses.calls[1]["input"]
            if item.get("type") == "function_call"] == [
        ("call_a", '{"ticker":"AAPL"}'), ("call_b", '{"ticker":"MSFT"}'),
    ]
    assert [item["call_id"] for item in client.responses.calls[1]["input"]
            if item.get("type") == "function_call_output"] == ["call_a", "call_b"]
    assert client.closed is True


def test_stream_llm_idless_completed_items_resolve_by_output_index(monkeypatch):
    events, client, invocations = _run_function_stream(monkeypatch, [
        {"type": "response.output_item.added", "output_index": 0,
         "item": _function_item(item_id="fc_a", call_id="call_a")},
        {"type": "response.output_item.added", "output_index": 1,
         "item": _function_item(item_id="fc_b", call_id="call_b")},
        {"type": "response.output_item.done", "output_index": 1,
         "item": {"type": "function_call", "arguments": '{"ticker":"MSFT"}', "status": "completed"}},
        {"type": "response.output_item.done", "output_index": 0,
         "item": {"type": "function_call", "arguments": '{"ticker":"AAPL"}', "status": "completed"}},
        _completed_event(),
    ])

    assert invocations == [{"ticker": "AAPL"}, {"ticker": "MSFT"}]
    assert [event.data["call_id"] for event in events if event.type == EventType.tool_start] == ["call_a", "call_b"]
    assert [event.type for event in events if event.type in (EventType.done, EventType.error)] == [EventType.done]
    assert len(client.responses.calls) == 2
    assert client.closed is True


@pytest.mark.parametrize("complete_first", [False, True], ids=["both-pending", "one-pending"])
def test_stream_llm_idless_unindexed_arguments_reject_ambiguous_calls(monkeypatch, complete_first):
    first = [
        {"type": "response.output_item.added", "output_index": 0,
         "item": _function_item(item_id="fc_a", call_id="call_a")},
        {"type": "response.output_item.added", "output_index": 1,
         "item": _function_item(item_id="fc_b", call_id="call_b")},
    ]
    if complete_first:
        first.append({"type": "response.function_call_arguments.done", "item_id": "fc_a", "arguments": '{"ticker":"AAPL"}'})
    first.extend([
        {"type": "response.function_call_arguments.done", "arguments": '{"ticker":"MSFT"}'},
        _completed_event(),
    ])
    events, client, invocations = _run_function_stream(monkeypatch, first)

    assert [event.type for event in events] == [EventType.thinking, EventType.error]
    assert events[-1].data["code"] == "invalid_tool_call_identity"
    assert invocations == []
    assert len(client.responses.calls) == 1
    assert client.closed is True


@pytest.mark.parametrize("identity", [
    {"item_id": "fc_a", "output_index": 1},
    {"call_id": "call_a", "output_index": 1},
    {"item_id": "fc_a", "call_id": "call_b", "output_index": 0},
    {"item_id": "fc_unknown", "output_index": 0},
    {"call_id": "call_a", "output_index": 2},
    {"output_index": 2},
    {"output_index": False},
    {"output_index": -1},
    {"output_index": "0"},
], ids=["item-index", "call-index", "call-item", "unknown-item", "rebound-index",
        "unknown-index", "boolean-index", "negative-index", "string-index"])
def test_stream_llm_arguments_done_rejects_conflicting_identifiers(monkeypatch, identity):
    events, client, invocations = _run_function_stream(monkeypatch, [
        {"type": "response.output_item.added", "output_index": 0,
         "item": _function_item(item_id="fc_a", call_id="call_a")},
        {"type": "response.output_item.added", "output_index": 1,
         "item": _function_item(item_id="fc_b", call_id="call_b")},
        {"type": "response.function_call_arguments.done", **identity, "arguments": '{"ticker":"AAPL"}'},
        _completed_event(),
    ])

    assert [event.type for event in events] == [EventType.thinking, EventType.error]
    assert events[-1].data["code"] == "invalid_tool_call_identity"
    assert invocations == []
    assert len(client.responses.calls) == 1
    assert client.closed is True


@pytest.mark.parametrize("event_type", ["response.output_item.added", "response.output_item.done"])
@pytest.mark.parametrize(("index", "item_id", "call_id"), [
    (1, "fc_a", "call_a"), (0, "fc_other", "call_other"), (2, "fc_a", "call_a"),
], ids=["conflicting-index", "conflicting-ids", "rebound-index"])
def test_stream_llm_output_items_reject_conflicting_identity(monkeypatch, event_type, index, item_id, call_id):
    events, client, invocations = _run_function_stream(monkeypatch, [
        {"type": "response.output_item.added", "output_index": 0,
         "item": _function_item(item_id="fc_a", call_id="call_a")},
        {"type": "response.output_item.added", "output_index": 1,
         "item": _function_item(item_id="fc_b", call_id="call_b")},
        {"type": event_type, "output_index": index,
         "item": _function_item(item_id=item_id, call_id=call_id, arguments='{"ticker":"AAPL"}', status="completed")},
        _completed_event(),
    ])

    assert [event.type for event in events] == [EventType.thinking, EventType.error]
    assert events[-1].data["code"] == "invalid_tool_call_identity"
    assert invocations == []
    assert len(client.responses.calls) == 1
    assert client.closed is True


@pytest.mark.parametrize("identity", [{"item_id": "fc_1"}, {"call_id": "call_1"}, {}], ids=["item-id", "call-id", "implicit-id"])
@pytest.mark.parametrize("provisional_args", ["", '{"ticker":"STALE"}'], ids=["empty", "provisional-json"])
def test_stream_llm_arguments_done_fallback_replaces_provisional_arguments(monkeypatch, identity, provisional_args):
    events, client, invocations = _run_function_stream(monkeypatch, [
        {"type": "response.output_item.added", "item": _function_item(arguments=provisional_args)},
        {"type": "response.function_call_arguments.done", **identity, "arguments": '{"ticker":"AAPL"}'},
        _completed_event(),
    ])

    assert invocations == [{"ticker": "AAPL"}]
    assert [event.data["call_id"] for event in events if event.type == EventType.tool_start] == ["call_1"]
    assert len(client.responses.calls) == 2
    assert client.responses.calls[1]["input"][1] == {
        "type": "function_call", "name": "get_price_change", "call_id": "call_1", "arguments": '{"ticker":"AAPL"}',
    }


@pytest.mark.parametrize("identity", [{"id": "fc_1"}, {"call_id": "call_1"}], ids=["item-id", "call-id"])
def test_stream_llm_completed_snapshot_merges_by_either_identity(monkeypatch, identity):
    events, client, invocations = _run_function_stream(monkeypatch, [
        {"type": "response.output_item.added", "item": _function_item()},
        {"type": "response.output_item.done", "item": {
            "type": "function_call", **identity, "arguments": '{"ticker":"AAPL"}', "status": "completed",
        }},
        _completed_event(),
    ])

    assert invocations == [{"ticker": "AAPL"}]
    assert [event.data["call_id"] for event in events if event.type == EventType.tool_start] == ["call_1"]
    assert len(client.responses.calls[1]["input"]) == 3


@pytest.mark.parametrize("final_kind", ["tool", "message"])
def test_stream_llm_final_output_resolves_ambiguous_provisional_identity(monkeypatch, final_kind):
    final = (_function_item(arguments='{"ticker":"AAPL"}', status="completed")
             if final_kind == "tool" else
             {"type": "message", "content": [{"type": "output_text", "text": "No tool needed."}]})
    events, client, invocations = _run_function_stream(monkeypatch, [
        {"type": "response.output_item.added", "output_index": 0, "item": _function_item()},
        {"type": "response.output_item.added", "output_index": 1,
         "item": _function_item(item_id="fc_other", call_id="call_other")},
        {"type": "response.function_call_arguments.done", "arguments": '{"ticker":"WRONG"}'},
        _completed_event([final]),
    ])

    assert invocations == ([{"ticker": "AAPL"}] if final_kind == "tool" else [])
    assert [event.type for event in events if event.type in (EventType.done, EventType.error)] == [EventType.done]
    assert len(client.responses.calls) == (2 if final_kind == "tool" else 1)
    assert client.closed is True


def test_stream_llm_ambiguous_fallback_cannot_supply_missing_final_arguments(monkeypatch):
    events, client, invocations = _run_function_stream(monkeypatch, [
        {"type": "response.output_item.added", "output_index": 0, "item": _function_item()},
        {"type": "response.function_call_arguments.done", "item_id": "fc_1", "arguments": '{"ticker":"STALE"}'},
        {"type": "response.output_item.added", "output_index": 1,
         "item": _function_item(item_id="fc_other", call_id="call_other")},
        {"type": "response.function_call_arguments.done", "arguments": '{"ticker":"WRONG"}'},
        _completed_event([_function_item(arguments="", status="completed")]),
    ])

    assert invocations == []
    assert [event.type for event in events] == [EventType.thinking, EventType.error]
    assert events[-1].data["code"] == "invalid_tool_arguments"
    assert len(client.responses.calls) == 1
    assert client.closed is True


@pytest.mark.parametrize("null_ids", [{"id": None}, {"call_id": None}, {"id": None, "call_id": None}])
def test_stream_llm_null_snapshot_ids_preserve_resolved_identity(monkeypatch, null_ids):
    events, client, invocations = _run_function_stream(monkeypatch, [
        {"type": "response.output_item.added", "output_index": 0, "item": _function_item()},
        {"type": "response.output_item.done", "output_index": 0,
         "item": {"type": "function_call", **null_ids, "arguments": '{"ticker":"AAPL"}', "status": "completed"}},
        _completed_event(),
    ])

    assert invocations == [{"ticker": "AAPL"}]
    assert [event.data["call_id"] for event in events if event.type == EventType.tool_start] == ["call_1"]
    assert [item["call_id"] for item in client.responses.calls[1]["input"]
            if item.get("type") == "function_call"] == ["call_1"]
    assert events[-1].type == EventType.done
    assert client.closed is True


def test_stream_llm_final_output_is_authoritative_over_streamed_calls(monkeypatch):
    events, client, invocations = _run_function_stream(monkeypatch, [
        {"type": "response.output_item.added", "item": _function_item()},
        {"type": "response.function_call_arguments.done", "item_id": "fc_1", "arguments": '{"ticker":"STALE"}'},
        {"type": "response.output_item.done", "item": _function_item(arguments='{"ticker":"STALE"}', status="completed")},
        {"type": "response.output_item.done", "item": _function_item(item_id="fc_other", call_id="call_other",
                                                                      arguments='{"ticker":"MSFT"}', status="completed")},
        _completed_event([_function_item(arguments='{"ticker":"AAPL"}', status="completed")]),
    ])

    assert invocations == [{"ticker": "AAPL"}]
    assert [event.data["call_id"] for event in events if event.type == EventType.tool_start] == ["call_1"]
    assert len(client.responses.calls) == 2
    assert len(client.responses.calls[1]["input"]) == 3
    assert client.responses.calls[1]["input"][1]["arguments"] == '{"ticker":"AAPL"}'


def test_stream_llm_final_message_suppresses_streamed_calls(monkeypatch):
    events, client, invocations = _run_function_stream(monkeypatch, [
        {"type": "response.output_item.done", "item": _function_item(arguments='{"ticker":"AAPL"}', status="completed")},
        _completed_event([{"type": "message", "content": [{"type": "output_text", "text": "No tool needed."}]}]),
    ])

    assert invocations == []
    assert [event.type for event in events] == [EventType.thinking, EventType.done]
    assert events[-1].data["answer"] == "No tool needed."
    assert len(client.responses.calls) == 1


@pytest.mark.parametrize("arguments", ["", " ", None, '{"ticker":', "[]", "null", '"AAPL"', {}])
@pytest.mark.parametrize("source", ["final-output", "item-done", "arguments-done"])
def test_stream_llm_invalid_arguments_never_execute_as_empty_object(monkeypatch, source, arguments):
    item = _function_item(arguments=arguments, status="completed")
    if source == "final-output":
        first = [_completed_event([item])]
    elif source == "item-done":
        first = [{"type": "response.output_item.done", "item": item}, _completed_event()]
    else:
        first = [
            {"type": "response.output_item.added", "item": _function_item()},
            {"type": "response.function_call_arguments.done", "item_id": "fc_1", "arguments": arguments},
            _completed_event(),
        ]
    events, client, invocations = _run_function_stream(monkeypatch, first)

    assert [event.type for event in events] == [EventType.thinking, EventType.error]
    assert events[-1].data["code"] == "invalid_tool_arguments"
    assert invocations == []
    assert not any(event.type in (EventType.tool_start, EventType.tool_end) for event in events)
    assert len(client.responses.calls) == 1
    assert client.responses.calls[0]["input"] == [{"role": "user", "content": "hi"}]


def test_stream_llm_malformed_completed_call_aborts_before_valid_sibling_executes(monkeypatch):
    events, client, invocations = _run_function_stream(monkeypatch, [_completed_event([
        _function_item(arguments='{"ticker":"AAPL"}', status="completed"),
        _function_item(item_id="fc_bad", call_id="call_bad", arguments="[]", status="completed"),
    ])])

    assert [event.type for event in events] == [EventType.thinking, EventType.error]
    assert events[-1].data["code"] == "invalid_tool_arguments"
    assert invocations == []
    assert len(client.responses.calls) == 1
    assert client.closed is True


@pytest.mark.parametrize("ending", ["added-only", "delta-only", "unknown-identity", "incomplete-item", "eof", "failed", "incomplete"])
def test_stream_llm_unfinished_calls_never_execute(monkeypatch, ending):
    first = [{"type": "response.output_item.added", "item": _function_item(arguments='{"ticker":"STALE"}')}]
    if ending == "delta-only":
        first.append({"type": "response.function_call_arguments.delta", "item_id": "fc_1", "delta": '{"ticker":"AAPL"}'})
    elif ending == "unknown-identity":
        first.append({"type": "response.function_call_arguments.done", "item_id": "fc_unknown", "arguments": '{"ticker":"AAPL"}'})
    elif ending == "incomplete-item":
        first.append({"type": "response.output_item.done", "item": _function_item(arguments='{"ticker":"AAPL"}', status="incomplete")})
    elif ending in ("eof", "failed", "incomplete"):
        first.append({"type": "response.output_item.done", "item": _function_item(arguments='{"ticker":"AAPL"}', status="completed")})
    if ending in ("failed", "incomplete"):
        first.append({"type": f"response.{ending}"})
    elif ending != "eof":
        first.append(_completed_event())
    events, client, invocations = _run_function_stream(monkeypatch, first)

    assert invocations == []
    assert not any(event.type in (EventType.tool_start, EventType.tool_end) for event in events)
    assert len(client.responses.calls) == 1
    assert client.closed is True
    terminal_types = [event.type for event in events if event.type in (EventType.done, EventType.error)]
    if ending in ("eof", "failed", "incomplete", "unknown-identity"):
        assert terminal_types == [EventType.error]
        if ending == "eof":
            assert events[-1].data["code"] == "incomplete_response"
    else:
        assert terminal_types == [EventType.done]


@pytest.mark.parametrize("prefix", ["empty", "plain-text", "provisional-call", "arguments-done"])
def test_stream_llm_eof_without_completed_is_terminal_error(monkeypatch, prefix):
    first = []
    if prefix == "plain-text":
        first.append({"type": "response.output_text.delta", "delta": "Partial answer."})
    elif prefix in ("provisional-call", "arguments-done"):
        first.append({"type": "response.output_item.added", "output_index": 0, "item": _function_item()})
        if prefix == "arguments-done":
            first.append({"type": "response.function_call_arguments.done", "output_index": 0,
                          "item_id": "fc_1", "arguments": '{"ticker":"AAPL"}'})
    events, client, invocations = _run_function_stream(monkeypatch, first)

    assert events[-1].type == EventType.error
    assert events[-1].data["code"] == "incomplete_response"
    assert [event.type for event in events if event.type in (EventType.done, EventType.error)] == [EventType.error]
    assert not any(event.type in (EventType.tool_start, EventType.tool_end) for event in events)
    assert invocations == []
    assert len(client.responses.calls) == 1
    assert client.closed is True


def test_call_llm_does_not_succeed_on_text_only_eof(monkeypatch):
    driver, client, invocations = _function_stream(monkeypatch, [
        {"type": "response.output_text.delta", "delta": "Partial answer."},
    ])

    with pytest.raises(RuntimeError, match="before response.completed"):
        _run(driver.call_llm(_req()))

    assert invocations == []
    assert len(client.responses.calls) == 1
    assert client.closed is True


def test_stream_llm_followup_eof_does_not_report_success(monkeypatch):
    driver, client, invocations = _function_stream(monkeypatch, [
        {"type": "response.output_item.done", "output_index": 0,
         "item": _function_item(arguments='{"ticker":"AAPL"}', status="completed")},
        _completed_event(),
    ])
    client.responses.streams[1] = [{"type": "response.output_text.delta", "delta": "Partial answer."}]

    events = _run(_collect(driver.stream_llm(_req())))

    assert invocations == [{"ticker": "AAPL"}]
    assert events[-1].type == EventType.error
    assert events[-1].data["code"] == "incomplete_response"
    assert [event.type for event in events if event.type in (EventType.done, EventType.error)] == [EventType.error]
    assert [event.data["call_id"] for event in events if event.type == EventType.tool_start] == ["call_1"]
    assert len(client.responses.calls) == 2
    assert client.closed is True


def test_stream_llm_explicit_completed_empty_object_is_valid(monkeypatch):
    events, client, invocations = _run_function_stream(monkeypatch, [
        {"type": "response.output_item.done", "item": _function_item(arguments="{}", status="completed")},
        _completed_event(),
    ])

    assert invocations == [{}]
    assert events[1].data["input"] == {}
    assert len(client.responses.calls) == 2
    assert client.responses.calls[1]["input"][1]["arguments"] == "{}"


def test_stream_llm_completed_fallback_keeps_output_boundary_before_tool_invocation(monkeypatch):
    from src.agents.shared.output_boundary import OutputBoundaryError

    driver, client, invocations = _function_stream(monkeypatch, [
        {"type": "response.output_item.added", "item": _function_item()},
        {"type": "response.function_call_arguments.done", "item_id": "fc_1", "arguments": '{"ticker":"cg-FAKE-TOKEN"}'},
        _completed_event(),
    ])
    events = []

    async def collect_rejected():
        async for event in driver.stream_llm(_req()):
            events.append(event)

    with pytest.raises(OutputBoundaryError, match="known_secret"):
        _run(collect_rejected())

    assert invocations == []
    assert [event.type for event in events] == [EventType.thinking]
    assert "cg-FAKE-TOKEN" not in repr([event.data for event in events])
    assert not any(event.type in (EventType.tool_start, EventType.tool_end) for event in events)
    assert len(client.responses.calls) == 1
    assert client.closed is True


def test_stream_llm_outgoing_registry_tools_explicitly_keep_optional_parameters(monkeypatch):
    events, client, invocations = _run_function_stream(monkeypatch, [_completed_event()])

    tools = {tool["name"]: tool for tool in client.responses.calls[0]["tools"]}
    assert set(tools) == {"get_price_change", "list_sec_filings", "get_sec_financial_facts", "read_sec_filing"}
    for name in ("list_sec_filings", "get_sec_financial_facts"):
        parameters = tools[name]["parameters"]
        assert parameters["required"] == ["issuer"]
        assert parameters["properties"]["issuer"]["type"] == "string"
        assert parameters["properties"]["cursor"]["type"] == "string"
        assert "cursor" not in parameters["required"]
        assert parameters["additionalProperties"] is False
    assert all(tool.get("strict") is False for tool in tools.values())
    assert invocations == []
    assert events[-1].type == EventType.done


def test_stream_llm_off_allowlist_tool_errors_without_calling_registry(monkeypatch):
    client = _ExecClient([[
        {"type": "response.completed", "response": {"output": [
            {"type": "function_call", "name": "delete_files", "call_id": "call_9", "arguments": "{}"},
        ]}},
    ]])
    monkeypatch.setattr(mod, "_execution_client", lambda token: client)

    class BoomRegistry(_Registry):
        def get(self, name):
            if name == "delete_files":  # pragma: no cover - allowlist veto should fire first
                raise AssertionError("off-allowlist tool must not be looked up")
            return self.sec.get(name)

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
