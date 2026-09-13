"""The child uses actual SDK aggregation without monopolizing its parent's loop."""

import asyncio
from contextlib import nullcontext
import threading

import httpx2
import pytest

from src.agents.shared.output_boundary import output_scope
from src.agents.shared.subagent import SubagentConfig, _run_anthropic_subagent
from src.auth_drivers.runtime_binding import RuntimeAuthBinding, activate_runtime_auth
from tests.test_research_output_events import anthropic_frames


@pytest.mark.parametrize("model,extended", [
    ("claude-sonnet-4-6", False), ("claude-sonnet-4-5", True),
])
def test_anthropic_child_model_io_allows_parent_heartbeat(model, extended, monkeypatch):
    from anthropic import Anthropic, AsyncAnthropic
    from src.agents import config

    settings = config.AgentConfig(web_openai_search=False, web_playwright=False)
    monkeypatch.setattr(config, "get_agent_config", lambda: settings)
    observations, clients, requests = [], [], []
    body = anthropic_frames(model, [{"type": "text", "text": "Completed."}], stop="end_turn").encode()

    class SyncBody(httpx2.SyncByteStream):
        def __iter__(self):
            heartbeat = threading.Event()
            asyncio.get_running_loop().call_soon(heartbeat.set)
            heartbeat.wait(0.05)
            observations.append(heartbeat.is_set())
            yield body

    class AsyncBody(httpx2.AsyncByteStream):
        async def __aiter__(self):
            heartbeat = asyncio.Event()
            asyncio.get_running_loop().call_soon(heartbeat.set)
            await heartbeat.wait()
            observations.append(heartbeat.is_set())
            yield body

    def construct(cls, http_cls, body_cls, **kwargs):
        def reply(request):
            requests.append(request)
            return httpx2.Response(200, headers={"content-type": "text/event-stream"}, stream=body_cls())
        client = cls(**kwargs, http_client=http_cls(transport=httpx2.MockTransport(reply)))
        clients.append(client)
        return client

    monkeypatch.setattr("anthropic.Anthropic", lambda **kw: construct(Anthropic, httpx2.Client, SyncBody, **kw))
    monkeypatch.setattr("anthropic.AsyncAnthropic", lambda **kw: construct(AsyncAnthropic, httpx2.AsyncClient, AsyncBody, **kw))
    binding = RuntimeAuthBinding("anthropic", "db_api_key", "api_key", "local:fixture", "fixture-child-key")
    child = SubagentConfig(name="test", description="", model=model, system_prompt="Read.",
                           extended_context=extended)

    async def exercise():
        with output_scope(), activate_runtime_auth(binding):
            result = await _run_anthropic_subagent(child, "Question", None)
        assert result["answer"] == "Completed."
        assert len(requests) == 1
        assert observations == [True], "Anthropic child model stream blocked the parent heartbeat"
        assert clients[0].is_closed()
        if extended:
            assert "context-1m-2025-08-07" in requests[0].headers["anthropic-beta"]

    asyncio.run(exercise())


@pytest.mark.parametrize("stop", ["cancel", "timeout"])
def test_anthropic_child_cancels_pending_response_headers(stop, monkeypatch):
    from anthropic import AsyncAnthropic
    from src.agents import config

    monkeypatch.setattr(config, "get_agent_config", lambda: config.AgentConfig(
        web_openai_search=False, web_playwright=False))
    clients, requests = [], []

    async def exercise():
        entered = asyncio.Event()

        async def reply(request):
            requests.append(request)
            entered.set()
            await asyncio.Event().wait()

        def construct(**kwargs):
            client = AsyncAnthropic(**kwargs, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(reply)))
            clients.append(client)
            return client

        monkeypatch.setattr("anthropic.AsyncAnthropic", construct)
        binding = RuntimeAuthBinding("anthropic", "db_api_key", "api_key", "local:fixture", "fixture-child-key")
        child = SubagentConfig(name="test", description="", model="claude-sonnet-4-6", system_prompt="Read.")
        with output_scope(), activate_runtime_auth(binding):
            task = asyncio.create_task(_run_anthropic_subagent(child, "Question", None))
            try:
                await asyncio.wait_for(entered.wait(), 5)
                if stop == "cancel":
                    task.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await task
                else:
                    with pytest.raises(asyncio.TimeoutError):
                        await asyncio.wait_for(task, 0.01)
                assert clients[0].is_closed()
                assert len(requests) == 1
            finally:
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())


@pytest.mark.parametrize("authority", ["captured", "active", "env", "captured-oauth", "active-oauth"])
def test_async_anthropic_resolution_keeps_selected_authority(authority, tmp_path, monkeypatch):
    from anthropic import AsyncAnthropic
    from src.auth_drivers import live_resolver
    from src.auth_drivers.runtime_binding import capture_runtime_auth
    from src.model_credentials import CredentialStore

    store = CredentialStore(tmp_path / "profile.db")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fixture-env-key")
    requests, clients = [], []
    if authority in {"captured", "active"}:
        store.add(provider="anthropic", auth_type="api_key", alias="fixture",
                  secret="fixture-selected-key", make_active=True)
    elif authority.endswith("oauth"):
        store.add_oauth_credential(provider="anthropic", auth_mode="claude_code_oauth",
                                   alias="fixture", make_active=True)
    binding = capture_runtime_auth("anthropic", store=store) if authority.startswith("captured") else None
    if authority == "captured":
        store.add(provider="anthropic", auth_type="api_key", alias="replacement",
                  secret="fixture-replacement-key", make_active=True)
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://unselected.invalid")
        monkeypatch.setenv("ANTHROPIC_CUSTOM_HEADERS", "X-Api-Key: fixture-injected\nAuthorization: Bearer fixture-other")

    def construct(**kwargs):
        async def reply(request):
            requests.append(request)
            return httpx2.Response(200, headers={"content-type": "text/event-stream"}, text=anthropic_frames(
                "claude-sonnet-4-6", [{"type": "text", "text": "Completed."}], stop="end_turn"))
        client = AsyncAnthropic(**kwargs, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(reply)))
        clients.append(client)
        return client

    monkeypatch.setattr("anthropic.AsyncAnthropic", construct)

    async def exercise():
        with output_scope(), activate_runtime_auth(binding) if binding else nullcontext():
            if authority.endswith("oauth"):
                with pytest.raises(live_resolver.SubscriptionDriverNotWiredError, match="silently billing"):
                    live_resolver.live_anthropic_async_client(store=store)
                assert clients == requests == []
                return
            client = live_resolver.live_anthropic_async_client(store=store)
            try:
                async with client.messages.stream(model="claude-sonnet-4-6", max_tokens=16,
                        messages=[{"role": "user", "content": "Question"}]) as stream:
                    assert (await stream.get_final_message()).content[0].text == "Completed."
            finally:
                await client.close()
            assert client.is_closed() and len(requests) == 1
            expected = "fixture-env-key" if authority == "env" else "fixture-selected-key"
            assert requests[0].headers["x-api-key"] == expected
            assert requests[0].url.host == "api.anthropic.com"
            assert "authorization" not in requests[0].headers

    asyncio.run(exercise())
