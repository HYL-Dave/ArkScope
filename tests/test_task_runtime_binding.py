"""Task 1: selection authority at persistence, scheduling and SDK boundaries."""

import asyncio
import json
from contextlib import nullcontext
from types import SimpleNamespace

import httpx
import httpx2
import pytest
from fastapi import HTTPException

from src.agents import config as cfg
from src.api.routes import query, research
from src.auth_drivers import live_resolver as live
from src.model_credentials import CredentialStore
from src.research_run_manager import execute_research_run, schedule_research_run
from src.research_runs import ResearchRunStore
from src.research_threads import ResearchThreadStore


@pytest.fixture
def isolated(monkeypatch, tmp_path):
    import agents
    from src.agents.shared import scratchpad

    monkeypatch.setattr(cfg, "ensure_env_loaded", lambda: None)
    monkeypatch.setattr(cfg, "get_agent_config", lambda: cfg.AgentConfig(web_openai_search=False))
    monkeypatch.setattr("src.model_credentials.ensure_env_loaded", lambda: None)
    monkeypatch.setattr(scratchpad, "_DEFAULT_BASE_DIR", tmp_path / "scratchpad")
    monkeypatch.setattr(scratchpad, "_CHAT_HISTORY_DIR", tmp_path / "chat_history")
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile.db"))
    monkeypatch.setenv("ARKSCOPE_TOKEN_STORE", "plaintext")
    monkeypatch.setenv("ARKSCOPE_TOKEN_STORE_PATH", str(tmp_path / "tokens.json"))
    monkeypatch.delenv("ARKSCOPE_REPLAY_CAPTURE", raising=False)
    monkeypatch.setattr("src.agents.openai_agent.tools.create_openai_tools", lambda dal: [])
    monkeypatch.setattr("src.agents.anthropic_agent.agent._build_anthropic_tools_list", lambda config: [])
    monkeypatch.setattr(research, "resolve_research_route", lambda provider: (
        ("gpt-5.6-luna", "xhigh") if provider == "openai" else ("claude-sonnet-5", "high")
    ))
    agents.set_tracing_disabled(True)
    yield SimpleNamespace(
        credentials=CredentialStore(tmp_path / "profile.db"),
        runs=ResearchRunStore(tmp_path / "profile.db"),
        threads=ResearchThreadStore(tmp_path / "profile.db"),
        path=tmp_path,
    )
    agents.set_tracing_disabled(False)


def add_key(store, provider, key):
    return store.add(provider=provider, auth_type="api_key", alias="synthetic", secret=key)


def response_json(model):
    return {"id": "resp_fixture", "object": "response", "created_at": 1,
            "model": model, "status": "completed", "error": None,
            "output": [{"type": "message", "id": "msg_fixture", "role": "assistant",
                        "status": "completed", "content": [{"type": "output_text",
                        "text": "OK", "annotations": []}]}],
            "usage": {"input_tokens": 2, "output_tokens": 1, "total_tokens": 3}}


@pytest.fixture
def openai_wire(monkeypatch, isolated):
    from openai import AsyncOpenAI

    requests, clients = [], []

    async def handler(request):
        requests.append(request)
        await asyncio.sleep(0)
        return httpx.Response(200, json=response_json(json.loads(request.content)["model"]))

    def construct(**kwargs):
        client = AsyncOpenAI(**kwargs, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        clients.append(client)
        return client

    monkeypatch.setattr("openai.AsyncOpenAI", construct)
    yield requests
    for client in clients:
        asyncio.run(client.close())


@pytest.fixture
def anthropic_wire(monkeypatch, isolated):
    from anthropic import Anthropic

    requests, clients = [], []

    def handler(request):
        requests.append(request)
        return httpx2.Response(200, text=anthropic_sse(json.loads(request.content)["model"]),
                               headers={"content-type": "text/event-stream"})

    def construct(**kwargs):
        client = Anthropic(**kwargs, http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))
        clients.append(client)
        return client

    monkeypatch.setattr("anthropic.Anthropic", construct)
    yield requests
    for client in clients:
        client.close()


@pytest.mark.parametrize("task,expected", [
    ("card_synthesis", ("anthropic", "claude-opus-5", "high")),
    ("card_translation", ("anthropic", "claude-sonnet-5", "medium")),
    ("ai_research", ("openai", "gpt-5.6-luna", "xhigh")),
    ("lifecycle_investigation", ("anthropic", "claude-sonnet-5", "high")),
])
def test_absent_route_still_uses_exact_defaults(isolated, task, expected):
    route = cfg.task_route(task, route_store=SimpleNamespace(get=lambda task: None))
    assert (route.provider, route.model, route.effort) == expected
    assert route.source == "default"


@pytest.mark.parametrize("switch_at", ["persist", "schedule", "dispatch"])
@pytest.mark.parametrize("provider,model,effort", [
    ("openai", "gpt-5.6-luna", "xhigh"), ("anthropic", "claude-sonnet-5", "high"),
])
def test_research_captures_key_before_persistence_and_scheduling(
    isolated, monkeypatch, openai_wire, anthropic_wire, switch_at, provider, model, effort,
):
    from src.model_route_store import ModelRouteStore

    routes = ModelRouteStore(isolated.path / "profile.db")
    routes.set("ai_research", provider, model, effort)
    monkeypatch.setattr(research, "resolve_research_route", cfg.resolve_research_route)
    first = add_key(isolated.credentials, provider, "test-original-key")
    scheduled = {}

    def replace_key():
        isolated.credentials.update(f"local:{first.id}", secret="test-mutated-key")
        add_key(isolated.credentials, provider, "test-replacement-key")
        routes.set("ai_research", "openai", "gpt-5.6-sol", "low")

    original_create = isolated.runs.create_run_with_user_message

    def persist(**kwargs):
        if switch_at == "persist":
            replace_key()
        return original_create(**kwargs)

    def schedule(**kwargs):
        if switch_at == "schedule":
            replace_key()
        scheduled.update(kwargs)

    monkeypatch.setattr(isolated.runs, "create_run_with_user_message", persist)
    monkeypatch.setattr(research, "schedule_research_run", schedule)

    async def drive():
        result = await research.create_research_run(
            research.ResearchRunCreate(question="research", provider=provider), dal=object(),
            thread_store=isolated.threads, run_store=isolated.runs,
        )
        if switch_at == "dispatch":
            replace_key()
        # Exercise the real task scheduler as well as the real native agent.
        await schedule_research_run(**scheduled)
        return result["run"]

    created = asyncio.run(drive())
    run = isolated.runs.get_run(created["id"])
    assert run.status == "succeeded"
    requests = openai_wire if provider == "openai" else anthropic_wire
    assert len(requests) == 1
    wire = json.loads(requests[0].content)
    if provider == "openai":
        assert requests[0].headers["authorization"] == "Bearer test-original-key"
        assert wire["reasoning"] == {"effort": "xhigh"}
    else:
        assert requests[0].headers["x-api-key"] == "test-original-key"
        assert wire["output_config"] == {"effort": "high"}
    assert (created["provider"], created["model"], created["effort"], created["auth_mode"], created["credential_id"]) == (
        provider, model, effort, "api_key", f"local:{first.id}",
    )
    assert (run.model, run.effort, wire["model"]) == (model, effort, model)
    assert "auth_binding" in scheduled
    assert "test-original-key" not in repr(scheduled["auth_binding"])
    with isolated.runs._connect() as conn:
        persisted = "\n".join(conn.iterdump())
    assert "test-original-key" not in json.dumps(created)
    # The credential table intentionally owns API keys; execution tables must not.
    for line in persisted.splitlines():
        if "INSERT INTO \"research_" in line:
            assert "test-original-key" not in line and "RuntimeAuthBinding" not in line


def test_concurrent_openai_agents_never_exchange_clients(isolated, openai_wire):
    from agents import Runner, RunConfig
    from src.agents.openai_agent.agent import _build_agent

    add_key(isolated.credentials, "openai", "test-first-key")
    first = _build_agent("gpt-5.6-luna", [], reasoning_effort="low")
    add_key(isolated.credentials, "openai", "test-second-key")
    second = _build_agent("gpt-5.6-sol", [], reasoning_effort="max")

    async def drive():
        return await asyncio.gather(*[
            Runner.run(agent, "OK", run_config=RunConfig(tracing_disabled=True))
            for agent in (first, second)
        ])

    assert [r.final_output for r in asyncio.run(drive())] == ["OK", "OK"]
    assert {json.loads(r.content)["model"]: r.headers["authorization"] for r in openai_wire} == {
        "gpt-5.6-luna": "Bearer test-first-key", "gpt-5.6-sol": "Bearer test-second-key",
    }


def test_queued_run_missing_binding_cannot_capture_replacement(isolated, monkeypatch):
    isolated.threads.ensure_thread(id="queued", title="queued")
    isolated.runs.create_run(id="queued", thread_id="queued", question="q", ticker=None,
                            provider="openai", model="gpt-5.6-luna", effort="high",
                            auth_mode="api_key", credential_id="local:1")
    calls = []

    async def forbidden(**kwargs):
        calls.append(kwargs)
        yield None

    monkeypatch.setattr(query, "_research_provider_stream", forbidden)
    asyncio.run(execute_research_run(run_id="queued", run_store=isolated.runs,
                                    thread_store=isolated.threads, dal=object(), history=[]))
    assert calls == []
    run = isolated.runs.get_run("queued")
    assert run.status == "failed"
    assert run.error == "runtime_auth_binding_missing"


def test_legacy_stream_captures_before_lazy_iteration(isolated, monkeypatch, openai_wire):
    add_key(isolated.credentials, "openai", "test-legacy-original")

    async def drive():
        response = await query.query_agent_stream(
            query.QueryRequest(question="q", provider="openai", model="gpt-5.6-luna", effort="high"),
            dal=object(), store=isolated.threads,
        )
        add_key(isolated.credentials, "openai", "test-legacy-replacement")
        return [chunk async for chunk in response.body_iterator]

    assert '"type": "done"' in "".join(asyncio.run(drive()))
    assert [r.headers["authorization"] for r in openai_wire] == ["Bearer test-legacy-original"]


@pytest.mark.parametrize("provider,auth_mode,model", [
    ("openai", "chatgpt_oauth", "gpt-5.6-luna"),
    ("anthropic", "claude_code_oauth", "claude-sonnet-5"),
])
def test_research_oauth_switch_keeps_original_id_and_refresh_authority(
    isolated, monkeypatch, provider, auth_mode, model,
):
    from src.auth_drivers.token_store import get_token_store, StoredTokenRecord
    from src.agents.shared.events import AgentEvent, EventType

    first = isolated.credentials.add_oauth_credential(provider=provider, auth_mode=auth_mode, alias="original")
    token_store = get_token_store()
    scope = dict(provider=provider, auth_mode=auth_mode, credential_id=f"local:{first.id}")
    token_store.save(**scope, record=StoredTokenRecord(access_token="test-original-oauth"))
    calls, scheduled = [], {}

    def build_driver(**kwargs):
        # Boundary fake stands in for the provider process/HTTP driver only.
        async def stream(request):
            cid = f"local:{kwargs['credential'].id}"
            token = kwargs["token_store"].load(provider=provider, auth_mode=auth_mode, credential_id=cid)
            calls.append((kwargs["auth_mode"], cid, token.access_token, request.model, request.reasoning_effort))
            yield AgentEvent(EventType.error, {"code": "reauth_required", "error": "fixture OAuth rejection"})
        return SimpleNamespace(stream_llm=stream)

    monkeypatch.setattr("src.auth_drivers.factory.build_driver", build_driver)
    monkeypatch.setattr(research, "schedule_research_run", lambda **kw: scheduled.update(kw))
    monkeypatch.setattr("src.agents.openai_agent.agent.run_query_stream", lambda **kw: pytest.fail("API fallback"))
    monkeypatch.setattr("src.agents.anthropic_agent.agent.run_query_stream", lambda **kw: pytest.fail("API fallback"))

    async def drive():
        result = await research.create_research_run(
            research.ResearchRunCreate(question="q", provider=provider, model=model, effort="high"),
            dal=object(), thread_store=isolated.threads, run_store=isolated.runs,
        )
        replacement = isolated.credentials.add_oauth_credential(provider=provider, auth_mode=auth_mode, alias="replacement")
        token_store.save(provider=provider, auth_mode=auth_mode, credential_id=f"local:{replacement.id}",
                         record=StoredTokenRecord(access_token="test-replacement-oauth"))
        # A legitimate refresh of the ORIGINAL id remains visible through its authority.
        token_store.save(**scope, record=StoredTokenRecord(access_token="test-refreshed-original"))
        await schedule_research_run(**scheduled)
        return result["run"]

    created = asyncio.run(drive())
    assert calls == [(auth_mode, f"local:{first.id}", "test-refreshed-original", model, "high")]
    assert (created["auth_mode"], created["credential_id"]) == (auth_mode, f"local:{first.id}")
    run = isolated.runs.get_run(created["id"])
    assert run.status == "failed" and run.error_code == "reauth_required"
    assert not any(e.type == "done" for e in isolated.runs.list_events(run.id))


def anthropic_sse(model):
    events = [
        {"type": "message_start", "message": {"id": "msg_fixture", "type": "message",
         "role": "assistant", "model": model, "content": [], "stop_reason": None,
         "stop_sequence": None, "usage": {"input_tokens": 2, "output_tokens": 0}}},
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "OK"}},
        {"type": "content_block_stop", "index": 0},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
         "usage": {"output_tokens": 1}},
        {"type": "message_stop"},
    ]
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events)


@pytest.mark.parametrize("model", ["claude-custom-research", "claude-sonnet-5"])
def test_anthropic_custom_and_supported_effort_reaches_messages_wire(isolated, monkeypatch, model):
    from anthropic import Anthropic

    add_key(isolated.credentials, "anthropic", "test-anthropic-key")
    requests = []

    def handler(request):
        requests.append(request)
        return httpx2.Response(200, text=anthropic_sse(model), headers={"content-type": "text/event-stream"})

    with Anthropic(api_key="test-anthropic-key", http_client=httpx2.Client(transport=httpx2.MockTransport(handler))) as client:
        monkeypatch.setattr(live, "live_anthropic_client", lambda: client)

        async def drive():
            return [event async for event in query._research_provider_stream(
                provider="anthropic", question="q", model=model, effort="max", dal=object(), history=[],
            )]

        events = asyncio.run(drive())
    assert events[-1].type.value == "done"
    assert len(requests) == 1
    body = json.loads(requests[0].content)
    assert (body["model"], body.get("output_config")) == (model, {"effort": "max"})


@pytest.mark.parametrize("status", [400, 429, 500])
def test_anthropic_probe_rejection_is_one_request_no_substituted_success(isolated, monkeypatch, status):
    from anthropic import Anthropic
    from src.api.routes.config_routes import ModelTestRequest, run_provider_model_test

    cred = add_key(isolated.credentials, "anthropic", "test-probe-key")
    requests = []

    def handler(request):
        requests.append(request)
        if "output_config" not in json.loads(request.content):
            return httpx2.Response(200, json={"id": "msg_substituted", "type": "message", "role": "assistant",
                                 "model": "claude-sonnet-5", "content": [{"type": "text", "text": "OK"}],
                                 "stop_reason": "end_turn", "usage": {"input_tokens": 1, "output_tokens": 1}})
        return httpx2.Response(status, json={"type": "error", "error": {"type": "invalid_request_error",
                                                                    "message": "effort is not supported"}})

    clients = []

    def construct(**kwargs):
        client = Anthropic(**kwargs, http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))
        clients.append(client)
        return client

    monkeypatch.setattr("anthropic.Anthropic", construct)
    try:
        result = run_provider_model_test(ModelTestRequest(provider="anthropic", model="claude-sonnet-5",
                                        effort="max", credential_id=f"local:{cred.id}"), store=isolated.credentials)
    finally:
        for client in clients:
            client.close()
    assert len(requests) == 1
    assert result["status"] == "error" and result["fallback_effort"] is None
    assert result["effort"] == "max"


@pytest.mark.parametrize("effort", ["bogus", "", "   "])
def test_model_probe_invalid_explicit_effort_cannot_normalize(isolated, monkeypatch, effort):
    from src.api.routes import config_routes as cr

    calls = []
    monkeypatch.setattr(cr, "test_model", lambda *a, **kw: calls.append(kw) or SimpleNamespace(model_dump=lambda: {}))
    with pytest.raises(HTTPException) as exc:
        cr.run_provider_model_test(cr.ModelTestRequest(provider="anthropic", model="claude-sonnet-5",
                                                      effort=effort), store=isolated.credentials)
    assert exc.value.detail == {"code": "effort_not_supported", "field": "effort"}
    assert calls == []


@pytest.mark.parametrize("parent_provider,child_provider", [
    ("openai", "openai"), ("openai", "anthropic"),
    ("anthropic", "openai"), ("anthropic", "anthropic"),
])
def test_delegation_has_explicit_child_auth_and_preserves_parent(
    isolated, monkeypatch, openai_wire, parent_provider, child_provider,
):
    from anthropic import Anthropic
    from src.agents.shared import subagent
    from src.auth_drivers.runtime_binding import capture_runtime_auth, activate_runtime_auth, current_runtime_auth

    add_key(isolated.credentials, "openai", "test-openai-original")
    add_key(isolated.credentials, "anthropic", "test-anthropic-original")
    parent = capture_runtime_auth(parent_provider)
    add_key(isolated.credentials, parent_provider, "test-parent-replacement")
    model = "gpt-5.6-terra" if child_provider == "openai" else "claude-sonnet-5"
    monkeypatch.setattr(cfg, "get_agent_config", lambda: cfg.AgentConfig(
        web_openai_search=False, subagent_models={"code_analyst": model},
    ))
    anthropic_requests, clients = [], []

    def handler(request):
        anthropic_requests.append(request)
        return httpx2.Response(200, text=anthropic_sse(model), headers={"content-type": "text/event-stream"})

    def construct(**kwargs):
        client = Anthropic(**kwargs, http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))
        clients.append(client)
        return client

    monkeypatch.setattr("anthropic.Anthropic", construct)
    try:
        with activate_runtime_auth(parent):
            result = subagent.dispatch_subagent("code_analyst", "q", dal=object())
            assert current_runtime_auth(parent_provider) is parent
        assert current_runtime_auth(parent_provider) is None
    finally:
        for client in clients:
            client.close()
    assert (result["error"], result["answer"], result["provider"], result["model"]) == (None, "OK", child_provider, model)
    if child_provider == "openai":
        assert len(openai_wire) == 1
        assert openai_wire[0].headers["authorization"] == "Bearer test-openai-original"
        assert json.loads(openai_wire[0].content)["model"] == "gpt-5.6-terra"
    else:
        assert len(anthropic_requests) == 1
        assert anthropic_requests[0].headers["x-api-key"] == "test-anthropic-original"
        assert json.loads(anthropic_requests[0].content)["model"] == "claude-sonnet-5"


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_binding_snapshot_survives_secret_mutation_and_nested_activation(isolated, provider):
    from dataclasses import FrozenInstanceError
    from src.auth_drivers.runtime_binding import capture_runtime_auth, activate_runtime_auth, current_runtime_auth

    first = add_key(isolated.credentials, provider, "test-original-key")
    binding = capture_runtime_auth(provider)
    isolated.credentials.update(f"local:{first.id}", secret="test-mutated-key")
    with activate_runtime_auth(binding):
        assert capture_runtime_auth(provider) is binding
        with pytest.raises(FrozenInstanceError):
            binding.credential_id = "local:replacement"
        with pytest.raises(ValueError, match="runtime_auth_binding_mismatch"):
            current_runtime_auth("anthropic" if provider == "openai" else "openai")
        client = live.live_openai_client() if provider == "openai" else live.live_anthropic_client()
        try:
            assert client.api_key == "test-original-key"
        finally:
            client.close()
    assert current_runtime_auth(provider) is None


@pytest.mark.parametrize("provider,env_key", [("openai", "OPENAI_API_KEY"), ("anthropic", "ANTHROPIC_API_KEY")])
def test_genuine_env_fallback_is_snapshotted_not_reselected(isolated, monkeypatch, provider, env_key):
    from src.auth_drivers.runtime_binding import capture_runtime_auth, activate_runtime_auth

    monkeypatch.setenv(env_key, "test-env-original")
    binding = capture_runtime_auth(provider)
    monkeypatch.setenv(env_key, "test-env-replacement")
    add_key(isolated.credentials, provider, "test-db-replacement")
    with activate_runtime_auth(binding):
        client = binding.api_client()
        try:
            assert client.api_key == "test-env-original"
            assert (binding.source, binding.auth_mode, binding.credential_id) == ("env_fallback", "api_key", None)
        finally:
            client.close()


def test_missing_or_unreadable_selected_key_never_uses_env(isolated, monkeypatch):
    from src.auth_drivers.runtime_binding import capture_runtime_auth

    monkeypatch.setenv("OPENAI_API_KEY", "test-env-not-selected")
    bad_row = SimpleNamespace(provider="openai", auth_type="api_key", id=1, active=True, secret=None)
    with pytest.raises(ValueError, match="^runtime_auth_unavailable$"):
        capture_runtime_auth("openai", store=SimpleNamespace(list=lambda provider: [bad_row]))

    def unavailable(provider):
        raise RuntimeError("test-secret-diagnostic")

    with pytest.raises(ValueError, match="^runtime_auth_unavailable$") as exc:
        capture_runtime_auth("openai", store=SimpleNamespace(list=unavailable))
    assert "test-secret-diagnostic" not in str(exc.value)


def test_api_binding_cannot_export_a_driver_credential_for_reresolution(isolated):
    from src.auth_drivers.runtime_binding import capture_runtime_auth

    add_key(isolated.credentials, "openai", "test-private-api-key")
    binding = capture_runtime_auth("openai")
    with pytest.raises(ValueError, match="runtime_auth_mode_unsupported"):
        binding.credential()


@pytest.mark.parametrize("provider,auth_mode", [
    ("openai", "chatgpt_oauth"), ("anthropic", "claude_code_oauth"),
])
def test_bound_oauth_direct_client_rejection_stays_actionable(isolated, provider, auth_mode):
    from src.auth_drivers.runtime_binding import capture_runtime_auth, activate_runtime_auth

    isolated.credentials.add_oauth_credential(provider=provider, auth_mode=auth_mode, alias="synthetic")
    binding = capture_runtime_auth(provider)
    with activate_runtime_auth(binding):
        with pytest.raises(live.SubscriptionDriverNotWiredError, match="silently billing"):
            if provider == "openai":
                live.live_openai_async_client()
            else:
                live.live_anthropic_client()


@pytest.mark.parametrize("parent_provider,child_provider,mode", [
    ("openai", "openai", "chatgpt_oauth"), ("anthropic", "openai", "chatgpt_oauth"),
    ("anthropic", "anthropic", "claude_code_oauth"), ("openai", "anthropic", "claude_code_oauth"),
])
def test_delegated_oauth_cannot_fall_back_to_api(isolated, monkeypatch, parent_provider, child_provider, mode):
    from src.agents.shared.subagent import dispatch_subagent
    from src.auth_drivers.runtime_binding import capture_runtime_auth, activate_runtime_auth, current_runtime_auth

    add_key(isolated.credentials, parent_provider, "test-parent-api")
    isolated.credentials.add_oauth_credential(provider=child_provider, auth_mode=mode, alias="child")
    model = "gpt-5.6-luna" if child_provider == "openai" else "claude-sonnet-5"
    monkeypatch.setattr(cfg, "get_agent_config", lambda: cfg.AgentConfig(subagent_models={"code_analyst": model}))
    parent = capture_runtime_auth(parent_provider)
    monkeypatch.setattr("openai.AsyncOpenAI", lambda **kw: pytest.fail("OAuth child used API"))
    monkeypatch.setattr("anthropic.Anthropic", lambda **kw: pytest.fail("OAuth child used API"))
    with activate_runtime_auth(parent):
        result = dispatch_subagent("code_analyst", "q", dal=object())
        assert current_runtime_auth(parent_provider) is parent
    assert result["answer"] == "" and result["error"]
    assert result["model"] == model


def test_failed_queued_handoff_cannot_be_rescheduled_with_current_settings(isolated, monkeypatch):
    add_key(isolated.credentials, "openai", "test-original-key")
    scheduled = {}

    def fail_schedule(**kwargs):
        scheduled.update(kwargs)
        raise RuntimeError("fixture handoff failure")

    monkeypatch.setattr(research, "schedule_research_run", fail_schedule)

    async def drive():
        with pytest.raises(HTTPException) as exc:
            await research.create_research_run(research.ResearchRunCreate(question="q", provider="openai"),
                                              dal=object(), thread_store=isolated.threads, run_store=isolated.runs)
        assert exc.value.status_code == 503
        add_key(isolated.credentials, "openai", "test-replacement-key")
        scheduled.pop("auth_binding")
        await schedule_research_run(**scheduled)

    monkeypatch.setattr(query, "_research_provider_stream", lambda **kw: pytest.fail("failed handoff dispatched"))
    asyncio.run(drive())
    assert isolated.runs.get_run(scheduled["run_id"]).status == "failed"


def test_binding_is_not_pickleable_and_never_logs_its_api_key(isolated, caplog):
    import pickle
    import logging
    from src.auth_drivers.runtime_binding import capture_runtime_auth

    add_key(isolated.credentials, "openai", "test-private-api-key")
    binding = capture_runtime_auth("openai")
    logging.getLogger(__name__).warning("binding=%r", binding)
    assert "test-private-api-key" not in caplog.text
    with pytest.raises(TypeError):
        pickle.dumps(binding)


def test_unbound_openai_constructor_does_not_reread_captured_env(isolated, monkeypatch):
    from src.auth_drivers import runtime_binding

    original_capture = runtime_binding.capture_runtime_auth
    monkeypatch.setenv("OPENAI_API_KEY", "test-env-captured")

    def capture_then_switch(*args, **kwargs):
        result = original_capture(*args, **kwargs)
        monkeypatch.setenv("OPENAI_API_KEY", "test-env-replacement")
        return result

    monkeypatch.setattr(runtime_binding, "capture_runtime_auth", capture_then_switch)
    client = live.live_openai_async_client()
    try:
        assert client.api_key == "test-env-captured"
    finally:
        asyncio.run(client.close())


@pytest.fixture
def bound_sdk_wire(monkeypatch, isolated):
    """Real sync/async SDK clients, with only the HTTP boundary replaced."""
    import anthropic
    import openai

    requests, clients = [], []
    state = SimpleNamespace(error=None, requests=requests)

    def reply(request):
        requests.append(request)
        body = json.loads(request.content)
        if state.error:
            return httpx2.Response(400, json={"type": "error", "error": {
                "type": "invalid_request_error", "message": state.error,
            }})
        if "responses" in request.url.path:
            return httpx2.Response(200, json=response_json(body["model"]))
        if body.get("stream"):
            return httpx2.Response(200, text=anthropic_sse(body["model"]),
                                   headers={"content-type": "text/event-stream"})
        return httpx2.Response(200, json={"id": "msg_fixture", "type": "message", "role": "assistant",
            "model": body["model"], "content": [{"type": "text", "text": "OK"}],
            "stop_reason": "end_turn", "usage": {"input_tokens": 1, "output_tokens": 1}})

    def factory(cls, asynchronous):
        def construct(**kwargs):
            transport = httpx2.MockTransport(reply)
            http_client = httpx2.AsyncClient(transport=transport) if asynchronous else httpx2.Client(transport=transport)
            kwargs.setdefault("max_retries", 0)
            client = cls(**kwargs, http_client=http_client)
            clients.append((client, asynchronous))
            return client
        return construct

    for module, name in [(openai, "OpenAI"), (anthropic, "Anthropic")]:
        for asynchronous in (False, True):
            attr = f"Async{name}" if asynchronous else name
            monkeypatch.setattr(module, attr, factory(getattr(module, attr), asynchronous))
    yield state
    for client, asynchronous in clients:
        if asynchronous:
            asyncio.run(client.close())
        else:
            client.close()


@pytest.mark.parametrize("provider,model,host", [
    ("openai", "gpt-5.6-luna", "api.openai.com"),
    ("anthropic", "claude-sonnet-5", "api.anthropic.com"),
])
@pytest.mark.parametrize("consumer", ["sync", "async", "model_probe"])
def test_bound_wire_ignores_late_auth_headers_and_host(
    isolated, monkeypatch, bound_sdk_wire, provider, model, host, consumer,
):
    from src.auth_drivers.runtime_binding import capture_runtime_auth
    from src.api.routes import config_routes as cr

    cred = add_key(isolated.credentials, provider, "fixture-selected-alpha")
    binding = capture_runtime_auth(provider)
    monkeypatch.setenv(f"{provider.upper()}_BASE_URL", "https://alternate.invalid/v1")
    monkeypatch.setenv(f"{provider.upper()}_CUSTOM_HEADERS", "\n".join([
        "Authorization: Bearer fixture-alternate-bravo", "aUtHoRiZaTiOn: Bearer fixture-alternate-charlie",
        "X-Api-Key: fixture-alternate-bravo", "x-api-KEY: fixture-alternate-charlie", "X-Fixture: retained",
    ]))
    if consumer == "model_probe":
        result = cr.run_provider_model_test(cr.ModelTestRequest(provider=provider, model=model,
            effort="high", credential_id=f"local:{cred.id}"), store=isolated.credentials)
        assert result["status"] == "ok"
    else:
        client = binding.api_client(asynchronous=consumer == "async")
        kwargs = dict(model=model)
        if provider == "openai":
            call = client.responses.create
            kwargs.update(input="OK", max_output_tokens=16)
        else:
            call = client.messages.create
            kwargs.update(messages=[{"role": "user", "content": "OK"}], max_tokens=16)
        result = call(**kwargs)
        if consumer == "async":
            asyncio.run(result)
    assert len(bound_sdk_wire.requests) == 1
    request = bound_sdk_wire.requests[0]
    expected_auth = ("Bearer fixture-selected-alpha" if provider == "openai" else None)
    expected_key = "fixture-selected-alpha" if provider == "anthropic" else None
    assert (request.url.host, request.headers.get("authorization"), request.headers.get("x-api-key")) == (
        host, expected_auth, expected_key,
    )
    assert request.headers["x-fixture"] == "retained"
    assert json.loads(request.content)["model"] == model


def assert_private_failures(isolated, caplog, public, secret="fixture-selected-alpha"):
    scratchpad = "\n".join(path.read_text() for path in (isolated.path / "scratchpad").rglob("*.jsonl"))
    history = "\n".join(path.read_text() for path in (isolated.path / "chat_history").rglob("*.jsonl"))
    assert secret not in public
    assert secret not in caplog.text
    assert secret not in scratchpad + history
    assert all(not record.exc_info for record in caplog.records if record.name.startswith("src."))
    assert "[REDACTED]" in public


@pytest.mark.parametrize("provider,model", [("openai", "gpt-5.6-luna"), ("anthropic", "claude-sonnet-5")])
def test_model_probe_key_echo_is_redacted_before_api_serialization(
    isolated, bound_sdk_wire, caplog, provider, model,
):
    from src.api.routes import config_routes as cr

    cred = add_key(isolated.credentials, provider, "fixture-selected-alpha")
    bound_sdk_wire.error = "rejected fixture-selected-alpha " + "detail " * 300
    result = cr.run_provider_model_test(cr.ModelTestRequest(provider=provider, model=model,
        effort="high", credential_id=f"local:{cred.id}"), store=isolated.credentials)
    assert result["status"] == "error" and result["fallback_effort"] is None
    assert len(bound_sdk_wire.requests) == 1
    assert_private_failures(isolated, caplog, json.dumps(result))
    assert len(result["error"]) <= 500


@pytest.mark.parametrize("entrypoint", ["openai_stream", "openai_async", "openai_sync", "anthropic_stream", "anthropic_sync"])
@pytest.mark.parametrize("bound", [True, False])
def test_native_key_echo_is_redacted_before_logs_scratchpad_and_public_errors(
    isolated, bound_sdk_wire, caplog, entrypoint, bound,
):
    from src.agents.openai_agent import agent as oa
    from src.agents.anthropic_agent import agent as aa
    from src.auth_drivers.runtime_binding import capture_runtime_auth, activate_runtime_auth

    provider = entrypoint.split("_")[0]
    add_key(isolated.credentials, provider, "fixture-selected-alpha")
    binding = capture_runtime_auth(provider)
    if bound:
        add_key(isolated.credentials, provider, "fixture-replacement-bravo")
    bound_sdk_wire.error = "rejected fixture-selected-alpha " + "detail " * 300

    async def collect():
        stream = (oa.run_query_stream("q", model="gpt-5.6-luna", dal=object()) if provider == "openai"
                  else aa.run_query_stream("q", model="claude-sonnet-5", dal=object()))
        return [event async for event in stream]

    with activate_runtime_auth(binding) if bound else nullcontext():
        if entrypoint.endswith("stream"):
            events = asyncio.run(collect())
            error = next(event for event in events if event.type.value == "error")
            public = error.to_sse()
            detail = error.data["error"]
        else:
            with pytest.raises(Exception) as caught:
                if entrypoint == "openai_async":
                    asyncio.run(oa.run_query("q", model="gpt-5.6-luna", dal=object()))
                elif entrypoint == "openai_sync":
                    oa.run_query_sync("q", model="gpt-5.6-luna", dal=object())
                else:
                    aa.run_query("q", model="claude-sonnet-5", dal=object())
            public = detail = str(caught.value)
            assert caught.value.__suppress_context__ or caught.value.__context__ is None
    assert len(bound_sdk_wire.requests) == 1
    assert_private_failures(isolated, caplog, public)
    assert len(detail) <= 500


@pytest.mark.parametrize("parent_provider,child_provider", [
    ("openai", "openai"), ("anthropic", "openai"), ("openai", "anthropic"), ("anthropic", "anthropic"),
])
def test_child_key_echo_is_redacted_after_parent_context_restoration(
    isolated, monkeypatch, bound_sdk_wire, caplog, parent_provider, child_provider,
):
    from src.agents.shared.subagent import dispatch_subagent
    from src.auth_drivers.runtime_binding import capture_runtime_auth, activate_runtime_auth, current_runtime_auth

    add_key(isolated.credentials, parent_provider, "fixture-parent-bravo")
    add_key(isolated.credentials, child_provider, "fixture-selected-alpha")
    parent = capture_runtime_auth(parent_provider)
    model = "gpt-5.6-terra" if child_provider == "openai" else "claude-sonnet-5"
    monkeypatch.setattr(cfg, "get_agent_config", lambda: cfg.AgentConfig(
        web_openai_search=False, subagent_models={"code_analyst": model}))
    bound_sdk_wire.error = "rejected fixture-selected-alpha " + "detail " * 300
    with activate_runtime_auth(parent):
        result = dispatch_subagent("code_analyst", "q", dal=object())
        assert current_runtime_auth(parent_provider) is parent
    assert len(bound_sdk_wire.requests) == 1
    assert result["answer"] == "" and result["model"] == model
    assert_private_failures(isolated, caplog, json.dumps(result))
    assert len(result["error"]) <= 500


@pytest.mark.parametrize("boundary", ["legacy", "managed"])
@pytest.mark.parametrize("failure_kind", ["event", "exception"])
def test_research_key_echo_redacted_before_sse_and_persistence(
    isolated, monkeypatch, caplog, boundary, failure_kind,
):
    from src.agents.shared.events import AgentEvent, EventType

    add_key(isolated.credentials, "openai", "fixture-selected-alpha")
    scheduled = {}
    monkeypatch.setattr(research, "schedule_research_run", lambda **kw: scheduled.update(kw))

    async def stream(**kwargs):
        detail = "rejected fixture-selected-alpha " + "detail " * 300
        if failure_kind == "exception":
            raise TimeoutError(detail)
        yield AgentEvent(EventType.error, {"error": detail, "message": detail, "code": "model_timeout"})

    monkeypatch.setattr(query, "_research_provider_stream", stream)

    async def drive():
        if boundary == "legacy":
            response = await query.query_agent_stream(query.QueryRequest(question="q", provider="openai",
                model="gpt-5.6-luna", effort="high", thread_id="private-errors"), dal=object(), store=isolated.threads)
            add_key(isolated.credentials, "openai", "fixture-replacement-bravo")
            return "".join([chunk async for chunk in response.body_iterator])
        await research.create_research_run(research.ResearchRunCreate(question="q", provider="openai"),
            dal=object(), thread_store=isolated.threads, run_store=isolated.runs)
        add_key(isolated.credentials, "openai", "fixture-replacement-bravo")
        await execute_research_run(**scheduled)
        run = isolated.runs.get_run(scheduled["run_id"])
        assert run.error_code == "model_timeout"
        return json.dumps(research._run_dict(run))

    public = asyncio.run(drive())
    assert_private_failures(isolated, caplog, public)
    with isolated.runs._connect() as conn:
        persisted = "\n".join(line for line in conn.iterdump() if 'INSERT INTO "research_' in line)
    assert "fixture-selected-alpha" not in persisted


def test_runtime_error_redacts_exact_key_before_length_bound(isolated):
    from src.auth_drivers.runtime_binding import capture_runtime_auth, activate_runtime_auth
    from src.research_errors import sanitize_research_detail

    add_key(isolated.credentials, "openai", "fixture-selected-alpha")
    with activate_runtime_auth(capture_runtime_auth("openai")):
        detail = sanitize_research_detail("x " * 246 + "fixture-selected-alpha" + " tail" * 100)
    assert detail == "x " * 246 + "[REDACTE"


@pytest.mark.parametrize("provider,model", [("openai", "gpt-5.6-luna"), ("anthropic", "claude-sonnet-5")])
@pytest.mark.parametrize("consumer", ["sync", "async", "model_probe"])
def test_client_construction_key_echo_is_private(isolated, monkeypatch, caplog, provider, model, consumer):
    from src.auth_drivers.runtime_binding import capture_runtime_auth
    from src.api.routes import config_routes as cr

    cred = add_key(isolated.credentials, provider, "fixture-selected-alpha")
    binding = capture_runtime_auth(provider)

    def reject(**kwargs):
        raise ValueError("rejected fixture-selected-alpha " + "detail " * 300)

    name = "OpenAI" if provider == "openai" else "Anthropic"
    monkeypatch.setattr(f"{provider}.{name}", reject)
    monkeypatch.setattr(f"{provider}.Async{name}", reject)
    if consumer == "model_probe":
        result = cr.run_provider_model_test(cr.ModelTestRequest(provider=provider, model=model,
            effort="high", credential_id=f"local:{cred.id}"), store=isolated.credentials)
        assert result["status"] == "error"
        detail = result["error"]
    else:
        with pytest.raises(ValueError) as caught:
            binding.api_client(asynchronous=consumer == "async")
        detail = str(caught.value)
        assert caught.value.__suppress_context__ or caught.value.__context__ is None
    assert_private_failures(isolated, caplog, detail)
    assert len(detail) <= 500


@pytest.mark.parametrize("entrypoint", ["stream", "async", "sync"])
def test_openai_retry_key_echo_is_private_without_changing_retry_policy(
    isolated, monkeypatch, bound_sdk_wire, caplog, entrypoint,
):
    from src.agents.openai_agent import agent as oa
    from src.auth_drivers.runtime_binding import capture_runtime_auth, activate_runtime_auth

    add_key(isolated.credentials, "openai", "fixture-selected-alpha")
    calls = []

    def run(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("No tool output found: fixture-selected-alpha " + "detail " * 300)

    async def run_async(*args, **kwargs):
        return run(*args, **kwargs)

    monkeypatch.setattr("agents.Runner.run", run_async)
    monkeypatch.setattr("agents.Runner.run_sync", run)

    async def collect():
        return [event async for event in oa.run_query_stream("q", model="gpt-5.6-luna", dal=object())]

    with activate_runtime_auth(capture_runtime_auth("openai")):
        if entrypoint == "stream":
            public = asyncio.run(collect())[-1].data["error"]
        else:
            with pytest.raises(Exception) as caught:
                if entrypoint == "async":
                    asyncio.run(oa.run_query("q", model="gpt-5.6-luna", dal=object()))
                else:
                    oa.run_query_sync("q", model="gpt-5.6-luna", dal=object())
            public = str(caught.value)
    assert calls == [1, 1]
    assert_private_failures(isolated, caplog, public)


@pytest.mark.parametrize("persistence_fails", [False, True])
def test_schedule_key_echo_never_logs_raw_exception_context(isolated, monkeypatch, caplog, persistence_fails):
    add_key(isolated.credentials, "openai", "fixture-selected-alpha")

    def reject(**kwargs):
        raise RuntimeError("handoff rejected fixture-selected-alpha " + "detail " * 300)

    monkeypatch.setattr(research, "schedule_research_run", reject)
    if persistence_fails:
        monkeypatch.setattr(isolated.runs, "fail_queued_run_handoff", reject)

    async def drive():
        with pytest.raises(HTTPException) as caught:
            await research.create_research_run(research.ResearchRunCreate(question="q", provider="openai"),
                dal=object(), thread_store=isolated.threads, run_store=isolated.runs)
        assert caught.value.status_code == 503
        assert "fixture-selected-alpha" not in str(caught.value.detail)

    asyncio.run(drive())
    assert "fixture-selected-alpha" not in caplog.text
    assert "[REDACTED]" in caplog.text
    assert all(not record.exc_info for record in caplog.records if record.name.startswith("src."))


@pytest.fixture
def enabled_local_sdk_tracing(isolated, monkeypatch):
    from agents.tracing import TracingProcessor, get_trace_provider, set_trace_provider
    from agents.tracing.processors import BackendSpanExporter
    from agents.tracing.provider import DefaultTraceProvider

    class MemoryProcessor(TracingProcessor):
        def __init__(self):
            self.traces = []
            self.spans = []

        def on_trace_start(self, trace):
            pass

        def on_trace_end(self, trace):
            self.traces.append(trace.export())

        def on_span_start(self, span):
            pass

        def on_span_end(self, span):
            record = span.export()
            if span.span_data.type == "response":
                # ResponseSpanData.export() omits these fields even when they
                # contain sensitive data. Inspect the live processor boundary.
                record["input"] = span.span_data.input
                response = span.span_data.response
                record["response"] = response.model_dump(mode="json") if response is not None else None
            # Snapshot before ArkScope's outer exception handlers can run.
            self.spans.append(json.loads(json.dumps(record)))

        def shutdown(self):
            pass

        def force_flush(self):
            pass

    export_attempts = []
    monkeypatch.setattr(BackendSpanExporter, "export", lambda *args, **kwargs: export_attempts.append(1))
    monkeypatch.delenv("OPENAI_AGENTS_TRACE_INCLUDE_SENSITIVE_DATA", raising=False)
    previous = get_trace_provider()
    provider = DefaultTraceProvider()
    memory = MemoryProcessor()
    provider.set_processors([memory])
    provider.set_disabled(False)
    set_trace_provider(provider)
    try:
        yield memory
    finally:
        provider.shutdown()
        set_trace_provider(previous)
        assert export_attempts == []


@pytest.mark.parametrize("entrypoint", ["async", "sync", "stream", "child", "cross_provider_child"])
@pytest.mark.parametrize("outcome", ["key_echo", "success"])
def test_enabled_sdk_tracing_excludes_sensitive_data_preserves_metadata(
    isolated, monkeypatch, bound_sdk_wire, enabled_local_sdk_tracing, caplog, entrypoint, outcome,
):
    from agents.tracing import trace
    from src.agents.openai_agent import agent as oa
    from src.agents.shared.subagent import dispatch_subagent
    from src.auth_drivers.runtime_binding import capture_runtime_auth, activate_runtime_auth, current_runtime_auth

    add_key(isolated.credentials, "openai", "fixture-selected-alpha")
    parent_provider = "anthropic" if entrypoint == "cross_provider_child" else "openai"
    if parent_provider == "anthropic":
        add_key(isolated.credentials, "anthropic", "fixture-parent-bravo")
    parent = capture_runtime_auth(parent_provider)
    is_child = entrypoint in ("child", "cross_provider_child")
    model = "gpt-5.6-terra" if is_child else "gpt-5.6-luna"
    monkeypatch.setattr(cfg, "get_agent_config", lambda: cfg.AgentConfig(
        web_openai_search=False, subagent_models={"code_analyst": "gpt-5.6-terra"}))
    if outcome == "key_echo":
        bound_sdk_wire.error = "rejected fixture-selected-alpha"

    async def collect():
        return [event async for event in oa.run_query_stream("q", model=model, dal=object())]

    with activate_runtime_auth(parent), trace(
        "task1-native-runtime", group_id="fixture-group", metadata={"owner": "task-1"},
    ):
        if is_child:
            result = dispatch_subagent("code_analyst", "q", dal=object())
            assert current_runtime_auth(parent_provider) is parent
            detail = result["error"]
        elif entrypoint == "stream":
            terminal = asyncio.run(collect())[-1]
            result = terminal.data
            detail = result.get("error")
        else:
            try:
                result = (asyncio.run(oa.run_query("q", model=model, dal=object())) if entrypoint == "async"
                          else oa.run_query_sync("q", model=model, dal=object()))
                detail = None
            except RuntimeError as exc:
                assert outcome == "key_echo"
                detail = str(exc)

    assert len(bound_sdk_wire.requests) == 1
    request = bound_sdk_wire.requests[0]
    assert request.headers["authorization"] == "Bearer fixture-selected-alpha"
    assert json.loads(request.content)["model"] == model
    memory = enabled_local_sdk_tracing
    assert len(memory.traces) == 1
    recorded_trace = memory.traces[0]
    assert recorded_trace["workflow_name"] == "task1-native-runtime"
    assert recorded_trace["metadata"] == {"owner": "task-1"}
    assert recorded_trace["group_id"] == "fixture-group"
    assert recorded_trace["id"].startswith("trace_")
    assert memory.spans
    assert all(span["trace_id"] == recorded_trace["id"] for span in memory.spans)
    assert all(span["started_at"] and span["ended_at"] for span in memory.spans)
    response_spans = [span for span in memory.spans if span["span_data"]["type"] == "response"]
    agent_spans = [span for span in memory.spans if span["span_data"]["type"] == "agent"]
    assert len(response_spans) == len(agent_spans) == 1
    response = response_spans[0]
    agent = agent_spans[0]
    assert agent["span_data"]["name"] == ("ArkScope Subagent: code_analyst" if is_child else "ArkScope Assistant")
    assert response["parent_id"] is not None
    assert "fixture-selected-alpha" not in json.dumps({"traces": memory.traces, "spans": memory.spans})
    assert response["input"] is None and response["response"] is None
    if outcome == "key_echo":
        assert response["error"] == {
            "message": "Error getting response", "data": {"error": "Error details are redacted."},
        }
        assert_private_failures(isolated, caplog, detail)
    else:
        assert detail is None
        assert (result["answer"], result["model"], result["provider"]) == ("OK", model, "openai")
        assert result["token_usage"]["total_tokens"] == 3
        assert response["error"] is None
        usage = response["span_data"]["usage"]
        assert (usage["input_tokens"], usage["output_tokens"], usage["total_tokens"]) == (2, 1, 3)
