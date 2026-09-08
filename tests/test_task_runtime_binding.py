"""Task 1: selection authority at persistence, scheduling and SDK boundaries."""

import asyncio
import json
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
