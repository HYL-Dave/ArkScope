"""Compaction observes the same execution-owned output boundary as research."""

import asyncio
from contextlib import contextmanager, nullcontext
import json
from types import SimpleNamespace

import pytest

from src.agents.shared.compressor.layers import apply_layer_5
from src.agents.shared.compressor.summary_callers import AnthropicSummaryCaller
from src.agents.shared.output_boundary import (
    OutputBoundaryError, current_output_guard, output_scope,
)


MAIN_KEY = "fixture-main-access-K4w2-Y9p6"
SUMMARY_KEY = "fixture-summary-access-X8p3-R2t9"
PUBLIC = "Consolidated Stockholders Manufacturing 1234567890123456789.123"


def _messages():
    return [
        {"role": "user", "content": "Prior public question"},
        {"role": "assistant", "content": "Prior public answer"},
        {"role": "user", "content": "Current public question"},
    ]


def _client(*, text=PUBLIC, error=None, before_call=None):
    calls = []

    @contextmanager
    def stream(**kwargs):
        calls.append(kwargs)
        if before_call is not None:
            before_call()
        if error is not None:
            raise RuntimeError(error)
        yield SimpleNamespace(get_final_message=lambda: SimpleNamespace(
            content=[SimpleNamespace(text=text)],
        ))

    return SimpleNamespace(api_key=SUMMARY_KEY, messages=SimpleNamespace(stream=stream)), calls


@pytest.mark.parametrize("nested", [False, True])
def test_summary_registers_actual_secondary_key_before_use_and_restores_scope(nested):
    observed = []

    def before_call():
        guard = current_output_guard()
        if guard is None:
            observed.append(False)
            return
        try:
            guard.check(SUMMARY_KEY)
        except OutputBoundaryError as exc:
            observed.append(exc.code == "known_secret")
        else:
            observed.append(False)

    client, calls = _client(before_call=before_call)
    original = current_output_guard()
    with output_scope(MAIN_KEY) if nested else nullcontext() as parent:
        assert AnthropicSummaryCaller(client=client)(system_prompt="sys", user_prompt="usr") == PUBLIC
        assert observed == [True]
        if nested:
            assert current_output_guard() is parent
            with pytest.raises(OutputBoundaryError, match="^known_secret$"):
                parent.check(SUMMARY_KEY)
    assert current_output_guard() is original
    assert calls == [{"model": "claude-sonnet-5", "max_tokens": 8000,
                      "system": "sys", "messages": [{"role": "user", "content": "usr"}]}]


@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("echo", [False, True])
def test_summary_failure_log_never_contains_secondary_key(caplog, nested, echo):
    client, calls = _client(error=SUMMARY_KEY if echo else "public error")
    with output_scope(MAIN_KEY) if nested else nullcontext():
        with caplog.at_level("WARNING"):
            assert AnthropicSummaryCaller(client=client)(system_prompt="s", user_prompt="u") is None
    assert len(calls) == 1
    assert len(caplog.records) == 1
    assert SUMMARY_KEY not in caplog.text
    assert MAIN_KEY not in caplog.text
    assert "[REDACTED]" in caplog.text if echo else "public error" in caplog.text
    assert caplog.records[0].exc_info is None


@pytest.mark.parametrize("nested", [False, True])
@pytest.mark.parametrize("echo", [False, True])
def test_summary_text_is_admitted_without_damaging_public_content(caplog, nested, echo):
    client, calls = _client(text=PUBLIC + SUMMARY_KEY if echo else PUBLIC)
    with output_scope(MAIN_KEY) if nested else nullcontext():
        result = AnthropicSummaryCaller(client=client)(system_prompt="s", user_prompt="u")
    assert result == (None if echo else PUBLIC)
    assert len(calls) == 1
    assert SUMMARY_KEY not in caplog.text
    if echo:
        assert "known_secret" in caplog.text


@pytest.mark.parametrize("echo", [False, True])
def test_layer_caller_exception_uses_diagnostic_boundary(caplog, echo):
    def caller(**kwargs):
        raise RuntimeError(MAIN_KEY if echo else "public error")

    messages = _messages()
    with output_scope(MAIN_KEY):
        result = apply_layer_5(messages, keep_recent_turns=1, summary_caller=caller)
    assert result == (messages, 0, "failed")
    assert len(caplog.records) == 1
    assert MAIN_KEY not in caplog.text
    assert "[REDACTED]" in caplog.text if echo else "public error" in caplog.text
    assert caplog.records[0].exc_info is None


@pytest.mark.parametrize("location", ["prefix", "past-cap"])
def test_layer_rejects_entire_credential_summary_before_cap(monkeypatch, caplog, location):
    from src.agents.shared.compressor import summary_prompt

    cap_calls = []
    monkeypatch.setattr(summary_prompt, "cap_summary", lambda text: cap_calls.append(text) or PUBLIC)
    text = MAIN_KEY + PUBLIC if location == "prefix" else PUBLIC * 1000 + MAIN_KEY
    messages = _messages()
    with output_scope(MAIN_KEY):
        result = apply_layer_5(messages, keep_recent_turns=1, summary_caller=lambda **kwargs: text)
    assert result == (messages, 0, "failed")
    assert cap_calls == []
    assert MAIN_KEY not in caplog.text
    assert "known_secret" in caplog.text


def test_layer_public_summary_retains_exact_content():
    messages = _messages()
    with output_scope(MAIN_KEY):
        result, boundary, outcome = apply_layer_5(
            messages, keep_recent_turns=1, summary_caller=lambda **kwargs: PUBLIC,
        )
    assert outcome == "success"
    assert boundary == 2
    assert result[1:] == messages[2:]
    assert PUBLIC in result[0]["content"]
    assert "[REDACTED]" not in result[0]["content"]


def _frames(model, blocks, stop):
    frames = [{"type": "message_start", "message": {
        "id": "msg_fixture", "type": "message", "role": "assistant", "model": model,
        "content": [], "stop_reason": None, "stop_sequence": None,
        "usage": {"input_tokens": 2, "output_tokens": 0},
    }}]
    for index, block in enumerate(blocks):
        frames.extend([
            {"type": "content_block_start", "index": index, "content_block": block},
            {"type": "content_block_stop", "index": index},
        ])
    frames.extend([
        {"type": "message_delta", "delta": {"stop_reason": stop, "stop_sequence": None},
         "usage": {"output_tokens": 3}},
        {"type": "message_stop"},
    ])
    return "".join(f"event: {row['type']}\ndata: {json.dumps(row)}\n\n" for row in frames)


@pytest.mark.parametrize("echo", [False, True])
def test_native_compaction_error_log_and_public_events_do_not_echo_key(monkeypatch, tmp_path, caplog, echo):
    import httpx2
    from anthropic import Anthropic
    from src.agents import config
    from src.agents.anthropic_agent import agent
    from src.agents.shared import scratchpad
    from src.auth_drivers import live_resolver
    from src.tools import news_tools

    main_model, summary_model = "claude-sonnet-4-6", "claude-sonnet-5"
    settings = config.AgentConfig(
        compaction_enabled=True, compaction_layer_5_enabled=True,
        compaction_layer_5_threshold_chars=1,
        compaction_layer_5_model_anthropic=summary_model,
        compaction_overflow_dir=str(tmp_path / "overflow"), context_keep_recent_turns=1,
        web_openai_search=False, web_playwright=False,
    )
    monkeypatch.setattr(config, "get_agent_config", lambda: settings)
    monkeypatch.setattr(agent, "get_agent_config", lambda: settings)
    monkeypatch.setattr(agent, "_build_anthropic_tools_list", lambda config: [])
    monkeypatch.setattr(news_tools, "get_news_brief", lambda *args, **kwargs: {"count": 0})
    monkeypatch.setattr(scratchpad, "_DEFAULT_BASE_DIR", tmp_path / "scratchpad")
    monkeypatch.delenv("ARKSCOPE_REPLAY_CAPTURE", raising=False)
    calls = []

    def reply(request):
        body = json.loads(request.content)
        calls.append(body["model"])
        if body["model"] == summary_model:
            return httpx2.Response(400, json={"type": "error", "error": {
                "type": "invalid_request_error", "message": MAIN_KEY if echo else "public error",
            }})
        first = calls.count(main_model) == 1
        blocks = [{"type": "tool_use", "id": "call_fixture", "name": "get_news_brief",
                   "input": {"days": 7}}] if first else [{"type": "text", "text": "OK"}]
        return httpx2.Response(200, text=_frames(main_model, blocks, "tool_use" if first else "end_turn"),
                               headers={"content-type": "text/event-stream"})

    client = Anthropic(api_key=MAIN_KEY, max_retries=0,
                       http_client=httpx2.Client(transport=httpx2.MockTransport(reply)))
    monkeypatch.setattr(live_resolver, "live_anthropic_client", lambda: client)

    async def drive():
        stream = agent.run_query_stream(
            "Public question", model=main_model, dal=object(), effort="low", history=_messages()[:2],
        )
        try:
            return [event async for event in stream]
        finally:
            await stream.aclose()

    try:
        with caplog.at_level("WARNING"):
            events = asyncio.run(drive())
    finally:
        client.close()
    assert calls == [main_model, summary_model, main_model]
    assert events[-1].data["answer"] == "OK"
    assert MAIN_KEY not in json.dumps([event.data for event in events])
    logs = [row for row in caplog.records if row.name.endswith("summary_callers")]
    assert len(logs) == 1
    assert MAIN_KEY not in caplog.text
    assert all(row.exc_info is None for row in logs)
