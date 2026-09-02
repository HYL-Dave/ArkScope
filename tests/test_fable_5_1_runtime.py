from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def test_anthropic_agent_rejects_fable_5_1_client_compaction_before_client(
    monkeypatch,
):
    from src.agents.anthropic_agent import agent

    provider_calls = []
    monkeypatch.setattr(
        agent,
        "get_agent_config",
        lambda: SimpleNamespace(
            anthropic_model="claude-fable-5-1",
            compaction_enabled=True,
        ),
    )
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.live_anthropic_client",
        lambda: provider_calls.append("client")
        or (_ for _ in ()).throw(AssertionError("client must not be built")),
    )

    stream = agent.run_query_stream(
        "question",
        model="claude-fable-5-1",
        dal=object(),
    )
    with pytest.raises(ValueError) as exc:
        asyncio.run(anext(stream))

    assert exc.value.args[0]["code"] == "model_client_compaction_incompatible"
    assert provider_calls == []


def test_anthropic_agent_rejects_history_only_fable_before_client(monkeypatch):
    from src.agents.anthropic_agent import agent

    provider_calls = []
    monkeypatch.setattr(
        agent,
        "get_agent_config",
        lambda: SimpleNamespace(
            anthropic_model="claude-fable-5",
            compaction_enabled=False,
        ),
    )
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.live_anthropic_client",
        lambda: provider_calls.append("client")
        or (_ for _ in ()).throw(AssertionError("client must not be built")),
    )

    stream = agent.run_query_stream(
        "question",
        model="claude-fable-5",
        dal=object(),
    )
    with pytest.raises(ValueError) as exc:
        asyncio.run(anext(stream))

    assert exc.value.args[0] == {"code": "model_retired", "field": "model"}
    assert provider_calls == []


def test_anthropic_subagent_rejects_history_only_model_before_client(monkeypatch):
    from src.agents.shared import subagent

    calls = []
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.live_anthropic_client",
        lambda: calls.append("client"),
    )

    with pytest.raises(ValueError) as exc:
        subagent._run_anthropic_subagent(
            SimpleNamespace(model="claude-fable-5"),
            "question",
            object(),
        )

    assert exc.value.args[0] == {"code": "model_retired", "field": "model"}
    assert calls == []


def test_anthropic_summary_rejects_history_only_model_before_client(monkeypatch):
    from src.agents.shared.compressor.summary_callers import AnthropicSummaryCaller

    caller = AnthropicSummaryCaller(model="claude-fable-5")
    calls = []
    monkeypatch.setattr(
        caller,
        "_get_client",
        lambda: calls.append("client"),
    )

    assert caller(system_prompt="system", user_prompt="user") is None
    assert calls == []


def test_fable_provider_side_compaction_stays_on_the_context_management_wire(
    monkeypatch,
):
    from src.agents.config import AgentConfig
    from src.agents.anthropic_agent import agent

    config = AgentConfig(
        anthropic_model="claude-fable-5-1",
        server_compaction=True,
        compaction_enabled=False,
        max_tool_calls=1,
    )
    response = SimpleNamespace(
        stop_reason="end_turn",
        stop_details=None,
        content=[SimpleNamespace(type="text", text="done")],
        usage=SimpleNamespace(input_tokens=1, output_tokens=1),
    )
    stream = MagicMock()
    stream.get_final_message.return_value = response
    stream_context = MagicMock()
    stream_context.__enter__.return_value = stream
    stream_context.__exit__.return_value = False
    client = MagicMock()
    client.beta.messages.stream.return_value = stream_context
    monkeypatch.setattr(agent, "get_agent_config", lambda: config)
    monkeypatch.setattr(
        "src.auth_drivers.live_resolver.live_anthropic_client", lambda: client
    )
    monkeypatch.setattr(
        "src.agents.anthropic_agent.tools.get_anthropic_tools", lambda: []
    )

    async def collect():
        return [
            event
            async for event in agent.run_query_stream(
                "question", model="claude-fable-5-1", dal=MagicMock()
            )
        ]

    events = asyncio.run(collect())
    kwargs = client.beta.messages.stream.call_args.kwargs

    assert events[-1].data["answer"] == "done"
    assert kwargs["context_management"] == {
        "edits": [{"type": "compact_20260112"}]
    }
    assert kwargs["betas"] == ["compact-2026-01-12"]
