"""Product retirement must reject stale routes before any provider work."""

from pathlib import Path
import asyncio

import pytest
from fastapi import HTTPException

from src.model_capabilities import capability_for, model_execution_admission_detail
from src.model_discovery_cache import ModelDiscoveryCache
from src.model_effective import ActiveCredential, effective_model_view_v2
from src.model_routing import TASK_IDS, TaskRoute, catalog


MODEL = "gpt-5.3-codex-spark"


@pytest.mark.parametrize("task", TASK_IDS)
@pytest.mark.parametrize("auth_mode", ["api_key", "chatgpt_oauth"])
def test_retirement_overrides_task_auth_and_entitlement(task, auth_mode):
    assert model_execution_admission_detail(
        MODEL, task=task, auth_mode=auth_mode, plan_type="pro",
    ) == {"code": "model_retired", "field": "model"}


def test_spark_is_history_only_not_a_current_or_seed_option():
    cap = capability_for(MODEL)
    assert cap is not None
    assert cap.new_execution_allowed is False
    assert cap.runtime_ready is False
    assert cap.picker_visibility == "pinned_only"
    assert cap.task_route_status == "retired"
    assert cap.recommended_for == ()
    policy = catalog()
    assert MODEL not in policy.current_model_ids
    assert MODEL in policy.retired_model_ids
    assert MODEL not in {row.id for row in policy.models}


@pytest.mark.parametrize("saved_route", [False, True])
def test_stale_discovery_cannot_reintroduce_a_spark_option(tmp_path, saved_route):
    cache = ModelDiscoveryCache(tmp_path / "profile.db")
    cache.record_run(
        provider="openai", auth_mode="chatgpt_oauth", credential_id="local:1",
        secret_fingerprint="fixture", status="ok", models=[{
            "id": MODEL, "label": "Old subscription model", "source": "provider_api",
        }],
    )
    routes = {"card_synthesis": TaskRoute(
        task="card_synthesis", provider="openai",
        model=MODEL if saved_route else "gpt-5.6-luna", effort="high",
    )}
    view = effective_model_view_v2(
        cache=cache, routes=routes, credentials={"openai": ActiveCredential(
            provider="openai", credential_id="local:1", auth_mode="chatgpt_oauth",
            secret_fingerprint="fixture", plan_type="pro",
        )},
    )
    for task, value in view["tasks"].items():
        entries = [row for row in value["providers"]["openai"]["models"] if row["id"] == MODEL]
        if saved_route and task == "card_synthesis":
            assert len(entries) == 1
            assert entries[0]["status"] == "route"
            assert entries[0]["eligible"] is False
            assert entries[0]["reason_code"] == "model_retired"
        else:
            assert entries == []
    assert routes["card_synthesis"].model == (MODEL if saved_route else "gpt-5.6-luna")


def test_subscription_dispatch_refuses_spark_before_token_store_or_transport(monkeypatch):
    from src.auth_drivers import subscription_structured_output as output

    def forbidden(*args, **kwargs):
        pytest.fail("retired model reached credential or provider work")

    for name in ("get_token_store", "_openai_structured_output_async", "_claude_structured_output_async"):
        monkeypatch.setattr(output, name, forbidden)
    with pytest.raises(output.SubscriptionStructuredOutputError) as caught:
        output.run_subscription_structured_output(
            task="card_synthesis", provider="openai", auth_mode="chatgpt_oauth",
            credential_id="local:1", model=MODEL, system="Translate", user="Fixture",
            schema={"type": "object"}, output_name="emit_translation",
            output_description="Translation", effort="high", timeout_s=1,
        )
    assert caught.value.code == "model_retired"


@pytest.mark.parametrize("task", ['card_synthesis'])
def test_card_selection_refuses_spark_before_credential_capture(monkeypatch, task):
    from src import card_execution

    monkeypatch.setattr(
        card_execution, "capture_runtime_auth",
        lambda *args, **kwargs: pytest.fail("retired model reached credential capture"),
    )
    with pytest.raises(card_execution.CardExecutionAdmissionError) as caught:
        card_execution.capture_card_execution(task, TaskRoute(
            task=task, provider="openai", model=MODEL, effort="high",
        ))
    assert caught.value.detail == {"code": "model_retired", "field": "model"}


def test_route_save_rejects_spark_without_rewriting_existing_selection(tmp_path, monkeypatch):
    from src.api.routes import config_routes
    from src.model_credentials import CredentialStore
    from src.model_route_store import ModelRouteStore

    store = CredentialStore(tmp_path / "profile.db")
    routes = ModelRouteStore(store.db_path)
    previous = routes.set("card_synthesis", "openai", "gpt-5.6-luna", "high")
    monkeypatch.setattr(
        config_routes, "resolve_active_credential",
        lambda *args, **kwargs: pytest.fail("retirement requires no credential lookup"),
    )
    with pytest.raises(HTTPException) as caught:
        config_routes.update_model_routes(
            config_routes.ModelRoutesUpdate(routes={"card_synthesis": config_routes.RouteUpdate(
                provider="openai", model=MODEL, effort="high",
            )}), store=store,
        )
    assert caught.value.status_code == 400
    assert caught.value.detail["code"] == "model_retired"
    assert routes.get("card_synthesis") == previous


def test_translation_adapter_removed_but_live_web_contract_retained():
    root = Path(__file__).resolve().parents[1]
    assert not (root / "src/auth_drivers/codex_translation_adapter.py").exists()
    from src.auth_drivers import lifecycle_web_codex
    from src.auth_drivers.codex_event_contract import CodexEventError, _validate_event_identity

    with pytest.raises(CodexEventError) as caught:
        _validate_event_identity(
            {"threadId": "another-thread", "turnId": "turn"},
            thread_id="owned-thread", turn_id="turn",
        )
    assert caught.value.code == "protocol_incompatible"
    assert lifecycle_web_codex._validate_event_identity is _validate_event_identity


def test_openai_agent_refuses_retired_model_even_with_no_reasoning(monkeypatch):
    from src.agents.openai_agent.agent import _build_agent
    from src.auth_drivers import live_resolver

    monkeypatch.setattr(
        live_resolver, "live_openai_async_client",
        lambda: pytest.fail("retired model reached API client construction"),
    )
    with pytest.raises(ValueError) as caught:
        _build_agent(MODEL, [], reasoning_effort="none")
    assert caught.value.args == ({"code": "model_retired", "field": "model"},)


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_oauth_agent_refuses_spark_before_loading_tokens_or_starting_runtime(monkeypatch, provider):
    from src.agents.shared.events import EventType
    from src.auth_drivers.protocol import LLMRequest

    def forbidden(*args, **kwargs):
        pytest.fail("retired model reached token or runtime work")

    if provider == "openai":
        from src.auth_drivers.chatgpt_oauth_driver import OpenAIChatGPTOAuthDriver

        driver = object.__new__(OpenAIChatGPTOAuthDriver)
        driver._token_store = object()
        driver._credential_id = "local:1"
    else:
        from src.auth_drivers import claude_code_sdk_driver as module

        driver = object.__new__(module.AnthropicClaudeCodeSdkDriver)
        monkeypatch.setattr(module, "require_reviewed_claude_agent_runtime", forbidden)
    monkeypatch.setattr(driver, "_load_token", forbidden)

    async def collect():
        return [event async for event in driver.stream_llm(LLMRequest(model=MODEL))]

    events = asyncio.run(collect())
    assert len(events) == 1
    assert events[0].type == EventType.error
    assert events[0].data["code"] == "model_retired"


def test_task_canary_refuses_spark_before_credential_resolution(monkeypatch):
    from src import model_task_canary

    monkeypatch.setattr(
        model_task_canary, "resolve_active_credential",
        lambda *args, **kwargs: pytest.fail("retired canary reached credential resolution"),
    )
    result = asyncio.run(model_task_canary.dispatch_task_model_test(
        task="card_synthesis", provider="openai", model=MODEL, effort="high",
        store=object(), token_store=object(),
    ))
    assert result.status == "unsupported"
    assert result.error_code == "model_retired"
