"""P0.1 full-v1 commit 1: OpenAI-side replay-capture wiring.

These tests pin the contract of two private helpers in
``src.agents.openai_agent.agent``:

  - ``_install_capture`` — gated by the env flag, builds a ``ReplayCapture``,
    swallows every exception so the agent path stays alive.
  - ``_replay_tools_available_openai`` — converts the OpenAI tool list
    (function-tool wrappers + provider-native server tools) into canonical
    replay names; bridge prefix stripped, ``WebSearchTool`` mapped to
    ``server:web_search``.

The tests deliberately avoid running the SDK ``Runner`` — that path is
covered by integration fixtures in commit 2.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.agents.openai_agent.agent import (
    _install_capture,
    _replay_tools_available_openai,
)
from src.agents.shared.replay import ENV_FLAG, ReplayCapture


# ---------------------------------------------------------------------------
# _install_capture
# ---------------------------------------------------------------------------


def test_install_capture_returns_none_when_flag_off(monkeypatch):
    monkeypatch.delenv(ENV_FLAG, raising=False)
    cap = _install_capture(
        question="hi",
        system_prompt="sys",
        all_tools=[],
        model_name="gpt-5.4",
        entrypoint="api",
    )
    assert cap is None


def test_install_capture_arms_capture_when_flag_on(monkeypatch):
    monkeypatch.setenv(ENV_FLAG, "1")
    fake_tool = SimpleNamespace(name="tool_get_ticker_news")
    cap = _install_capture(
        question="news on NVDA",
        system_prompt="You are an assistant.",
        all_tools=[fake_tool],
        model_name="gpt-5.4",
        entrypoint="api",
    )
    assert isinstance(cap, ReplayCapture)
    assert cap.provider == "openai"
    assert cap.model == "gpt-5.4"
    assert cap.entrypoint == "api"
    # set_initial canonicalised the bridge name and persisted user input.
    trace = cap.to_trace()
    assert trace.user_input == "news on NVDA"
    assert "get_ticker_news" in trace.tools_available  # canonical, no tool_ prefix


def test_install_capture_swallows_init_exception(monkeypatch):
    monkeypatch.setenv(ENV_FLAG, "1")

    class Boom:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("synthetic init failure")

    # Patch the ReplayCapture symbol used inside the openai_agent module
    # — the agent imports it at module load, so monkeypatch the local
    # binding, not the source module.
    import src.agents.openai_agent.agent as oa_mod
    monkeypatch.setattr(oa_mod, "ReplayCapture", Boom)

    cap = _install_capture(
        question="q",
        system_prompt="sys",
        all_tools=[],
        model_name="gpt-5.4",
        entrypoint="api",
    )
    # Agent path must stay alive — capture failures are best-effort.
    assert cap is None


# ---------------------------------------------------------------------------
# _replay_tools_available_openai
# ---------------------------------------------------------------------------


def test_replay_tools_available_strips_bridge_prefix():
    fake_tools = [
        SimpleNamespace(name="tool_get_ticker_news"),
        SimpleNamespace(name="tool_get_news_brief"),
        SimpleNamespace(name="get_already_canonical"),  # pass-through
    ]
    out = _replay_tools_available_openai(fake_tools)
    assert "get_ticker_news" in out
    assert "get_news_brief" in out
    assert "get_already_canonical" in out
    assert all(not n.startswith("tool_") for n in out)


def test_replay_tools_available_maps_websearchtool():
    pytest.importorskip("agents")
    from agents import WebSearchTool

    fake_tools = [
        WebSearchTool(),
        SimpleNamespace(name="tool_get_ticker_news"),
    ]
    out = _replay_tools_available_openai(fake_tools)
    assert "server:web_search" in out
    assert "get_ticker_news" in out


def test_replay_tools_available_skips_unrecognized_objects():
    # Object with neither known class name nor `name` attr → skipped (best-effort).
    weird = object()
    fake_tools = [weird, SimpleNamespace(name="tool_foo")]
    out = _replay_tools_available_openai(fake_tools)
    assert out == ["foo"]