"""OpenAI Responses transport policy.

This covers ONLY the OpenAI Agents SDK Responses transport global. It does not
cover frontend SSE, Anthropic streaming, market-data websockets, or native-host
capture. WebSocket transport can still be appropriate for selected long/tool
heavy runs, but ArkScope defaults to the SDK's HTTP transport and keeps
websocket as an explicit opt-in.
"""

from __future__ import annotations


def test_openai_responses_transport_defaults_to_http(monkeypatch):
    from src.agents.openai_agent.agent import _openai_responses_transport_from_env

    monkeypatch.delenv("ARKSCOPE_OPENAI_RESPONSES_TRANSPORT", raising=False)

    assert _openai_responses_transport_from_env() == "http"


def test_openai_responses_transport_websocket_is_explicit_opt_in(monkeypatch):
    from src.agents.openai_agent.agent import _openai_responses_transport_from_env

    monkeypatch.setenv("ARKSCOPE_OPENAI_RESPONSES_TRANSPORT", " websocket ")

    assert _openai_responses_transport_from_env() == "websocket"


def test_openai_responses_transport_invalid_value_falls_back_to_http(monkeypatch):
    from src.agents.openai_agent.agent import _openai_responses_transport_from_env

    monkeypatch.setenv("ARKSCOPE_OPENAI_RESPONSES_TRANSPORT", "fast")

    assert _openai_responses_transport_from_env() == "http"


def test_configure_openai_responses_transport_calls_sdk_with_resolved_value(monkeypatch):
    import src.agents.openai_agent.agent as oa

    calls: list[str] = []
    monkeypatch.setenv("ARKSCOPE_OPENAI_RESPONSES_TRANSPORT", "websocket")

    oa._configure_openai_responses_transport(set_transport=calls.append)

    assert calls == ["websocket"]
