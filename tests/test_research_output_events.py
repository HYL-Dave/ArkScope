"""Task 3 RED owners at real producer, callback and durable-output boundaries."""

from __future__ import annotations

import asyncio
import base64
import json
from types import SimpleNamespace
from urllib.parse import quote

import httpx
import httpx2
import pytest

from src.agents.openai_agent.tools import create_openai_tools as _NATIVE_OPENAI_TOOLS
from src.agents.shared.events import AgentEvent, EventType
from src.agents.shared.output_boundary import (
    OutputBoundaryError, current_output_guard, output_scope,
)
from src.auth_drivers.runtime_binding import RuntimeAuthBinding, current_runtime_auth
from tests.test_task_runtime_binding import (
    enabled_local_sdk_tracing, isolated, response_json,
)


SECRET = 'q7"/v2!'
SECRET_JSON = json.dumps(SECRET)[1:-1]
OLD_BEARER = "old-synthetic-bearer-not-selected"
PUBLIC = (
    "internationalization counterrevolutionaries\n"
    "1234567890123456789.123 -1.234567890123456789E+123\n"
    "0000320193-26-000123 0123456789abcdef0123456789abcdef\n"
    "https://example.test/report?cursor=eyJvZmZzZXQiOjEyMzQ1Njc4OTB9"
)
CHANNELS = ("openai", "anthropic", "chatgpt", "claude")
INCREMENTAL_CHANNELS = ("anthropic", "chatgpt", "claude")
REPRESENTATIONS = {
    "raw": SECRET,
    "json": json.dumps(SECRET)[1:-1],
    "url": quote(SECRET, safe=""),
    "base64": base64.b64encode(SECRET.encode()).decode(),
}
SPLITS = [
    pytest.param(value, split, id=f"{name}-{split}")
    for name, value in REPRESENTATIONS.items()
    for split in range(len(value) + 1)
]


async def collect(stream):
    try:
        return [event async for event in stream]
    finally:
        await stream.aclose()


def terminal(events):
    endings = [event for event in events if event.type in (EventType.done, EventType.error)]
    assert len(endings) == 1, "producer must emit exactly one terminal event"
    assert endings[0].type == EventType.done, endings[0].data
    return endings[0].data


def event_text(events, kind=EventType.text):
    field = "thinking" if kind == EventType.thinking_content else "content"
    return "".join(event.data[field] for event in events if event.type == kind)


def sink_records(path, directory):
    files = list((path / directory).rglob("*.json*"))
    assert files, f"real {directory} sink did not execute"
    if directory == "scratchpad":
        return [json.loads(line) for file in files for line in file.read_text().splitlines()]
    return [json.loads(file.read_text()) for file in files]


def anthropic_frames(model, blocks, *, stop="end_turn"):
    frames = [{"type": "message_start", "message": {
        "id": "msg_boundary", "type": "message", "role": "assistant", "model": model,
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
    return "".join(f"event: {frame['type']}\ndata: {json.dumps(frame)}\n\n" for frame in frames)


@pytest.fixture
def make_producer(monkeypatch, isolated):
    """Keep SDK parsing, agent loops and sinks real; replace HTTP/subprocess only."""
    from src.agents import config
    from src.agents.anthropic_agent import agent as anthropic_agent
    from src.agents.openai_agent import agent as openai_agent
    from src.agents.shared import replay
    from src.auth_drivers import live_resolver

    settings = config.AgentConfig(web_openai_search=False, web_playwright=False)
    monkeypatch.setattr(openai_agent, "get_agent_config", lambda: settings)
    monkeypatch.setattr(anthropic_agent, "get_agent_config", lambda: settings)
    monkeypatch.setattr(replay, "DEFAULT_OUTPUT_DIR", isolated.path / "replay")
    clients = []

    def make(channel, *, chunks=(), answer="Public answer", thinking=(), secret=SECRET, pause=None):
        state = SimpleNamespace(
            requests=[], guards=[], registration_codes=[], closed=False, input_chars=0, config_dir=None,
            channel=channel, secret=secret,
        )

        def record_request(request):
            state.requests.append(request)
            guard = current_output_guard()
            state.guards.append(guard)
            code = None
            if guard is not None:
                try:
                    guard.check(secret)
                except OutputBoundaryError as exc:
                    code = exc.code
            state.registration_codes.append(code)

        if channel == "openai":
            from openai import AsyncOpenAI

            async def reply(request):
                record_request(request)
                payload = response_json(json.loads(request.content)["model"])
                payload["output"][0]["content"][0]["text"] = answer
                return httpx.Response(200, json=payload)

            client = AsyncOpenAI(
                api_key=secret, http_client=httpx.AsyncClient(transport=httpx.MockTransport(reply)),
            )
            clients.append(client)
            monkeypatch.setattr(live_resolver, "live_openai_async_client", lambda: client)
            state.stream = lambda: openai_agent.run_query_stream(
                "Public question", model="gpt-5.4-mini", reasoning_effort="low", dal=object(),
            )
            state.call = lambda: openai_agent.run_query(
                "Public question", model="gpt-5.4-mini", reasoning_effort="low", dal=object(),
            )
        elif channel == "anthropic":
            from anthropic import Anthropic, AsyncAnthropic
            from src.tools import news_tools

            monkeypatch.setattr(news_tools, "get_news_brief", lambda *a, **kw: {"count": 0})

            def reply(request):
                record_request(request)
                first = len(state.requests) == 1
                blocks = [{"type": "thinking", "thinking": text, "signature": "fixture"}
                          for text in thinking] if first else []
                intermediate = bool(chunks) and first
                if intermediate:
                    blocks.extend({"type": "text", "text": text} for text in chunks if text)
                    blocks.append({"type": "tool_use", "id": "call_public", "name": "get_news_brief",
                                   "input": {"tickers": ["AAPL"], "days": 7}})
                else:
                    blocks.append({"type": "text", "text": answer})
                return httpx2.Response(
                    200, text=anthropic_frames(json.loads(request.content)["model"], blocks,
                                               stop="tool_use" if intermediate else "end_turn"),
                    headers={"content-type": "text/event-stream"},
                )

            client = Anthropic(api_key=secret, http_client=httpx2.Client(transport=httpx2.MockTransport(reply)))
            async_client = AsyncAnthropic(
                api_key=secret, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(reply)),
            )
            clients.extend((client, async_client))
            monkeypatch.setattr(live_resolver, "live_anthropic_client", lambda: client)
            monkeypatch.setattr(live_resolver, "live_anthropic_async_client", lambda: async_client)
            state.stream = lambda: anthropic_agent.run_query_stream(
                "Public question", model="claude-sonnet-4-6", effort="low", dal=object(),
            )
        elif channel == "chatgpt":
            from src.auth_drivers import chatgpt_oauth_driver as driver_module
            from src.auth_drivers.protocol import LLMRequest
            from src.auth_drivers.token_store import StoredTokenRecord
            from tests.test_chatgpt_oauth_driver import _Cred, _TokStore

            async def wire():
                try:
                    for text in chunks:
                        state.input_chars += len(text)
                        yield {"type": "response.output_text.delta", "delta": text}
                    if pause is not None:
                        pause[0].set()
                        await pause[1].wait()
                    yield {"type": "response.completed", "response": {
                        "output": [{"type": "message", "content": [{"type": "output_text", "text": answer}]}],
                        "usage": {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5},
                    }}
                finally:
                    state.wire_closed = True

            def create(**kwargs):
                record_request(kwargs)
                return wire()

            async def close():
                state.closed = True

            def execution_client(token):
                state.selected_bearer = token
                return SimpleNamespace(responses=SimpleNamespace(create=create), close=close)

            monkeypatch.setattr(driver_module, "_execution_client", execution_client)
            monkeypatch.setattr(driver_module, "_refresh_login", lambda **kw: StoredTokenRecord(access_token=secret))
            driver = driver_module.OpenAIChatGPTOAuthDriver(
                credential=_Cred(), token_store=_TokStore(OLD_BEARER), timeout_s=0,
            )
            request = LLMRequest(model="gpt-5.4-mini", instructions="Research.",
                                 input_messages=[{"role": "user", "content": "Public question"}], reasoning_effort="low")
            state.stream = lambda: driver.stream_llm(request)
        else:
            assert channel == "claude"
            from pathlib import Path
            from claude_agent_sdk import AssistantMessage, SystemMessage, TextBlock, ThinkingBlock
            from src.auth_drivers import claude_code_sdk_driver as driver_module
            from tests.test_claude_code_sdk_driver import _REQ, _make_driver, _result_msg

            async def query(*, prompt, options):
                record_request(options)
                state.config_dir = Path(options.cwd)
                try:
                    yield SystemMessage(subtype="init", data={"apiKeySource": "none"})
                    for text in thinking:
                        yield AssistantMessage(content=[ThinkingBlock(thinking=text, signature="fixture")], model=_REQ.model)
                    for text in chunks:
                        state.input_chars += len(text)
                        yield AssistantMessage(content=[TextBlock(text=text)], model=_REQ.model)
                    if pause is not None:
                        pause[0].set()
                        await pause[1].wait()
                    yield _result_msg(result=answer)
                finally:
                    state.closed = True

            monkeypatch.setattr(driver_module, "query", query)
            driver = _make_driver(token=secret, timeout_s=0)
            state.stream = lambda: driver.stream_llm(_REQ)
        return state

    yield make
    for client in clients:
        if asyncio.iscoroutinefunction(client.close):
            asyncio.run(client.close())
        else:
            client.close()


@pytest.mark.parametrize("channel", INCREMENTAL_CHANNELS)
@pytest.mark.parametrize("encoded,split", SPLITS)
def test_incremental_producers_protect_known_secret_at_every_split(make_producer, channel, encoded, split):
    chunks = ["Before|" + encoded[:split], encoded[split:] + "|After"]
    producer = make_producer(channel, chunks=chunks, answer="".join(chunks))
    events = asyncio.run(collect(producer.stream()))
    assert event_text(events) == "Before|[REDACTED]|After", "fragment-local protection leaked or damaged prose"
    assert terminal(events)["answer"] == "Before|[REDACTED]|After"


@pytest.mark.parametrize("channel", INCREMENTAL_CHANNELS)
@pytest.mark.parametrize("encoding", REPRESENTATIONS)
@pytest.mark.parametrize("width", [1, 2, 3])
def test_incremental_producers_protect_small_chunks(make_producer, channel, encoding, width):
    text = "Before|" + REPRESENTATIONS[encoding] + "|After"
    producer = make_producer(channel, chunks=[text[i:i + width] for i in range(0, len(text), width)], answer=text)
    events = asyncio.run(collect(producer.stream()))
    assert event_text(events) == "Before|[REDACTED]|After"
    assert terminal(events)["answer"] == "Before|[REDACTED]|After"


@pytest.mark.parametrize("channel", CHANNELS)
@pytest.mark.parametrize("encoding", REPRESENTATIONS)
def test_four_producers_protect_final_only_credentials(make_producer, channel, encoding):
    # Native OpenAI is final-only; OAuth can also finish from result/output_items
    # without deltas. Do not require a change to SDK streaming/session semantics.
    producer = make_producer(channel, answer="Before|" + REPRESENTATIONS[encoding] + "|After")
    events = asyncio.run(collect(producer.stream()))
    assert terminal(events)["answer"] == "Before|[REDACTED]|After"


@pytest.mark.parametrize("channel", CHANNELS)
def test_four_producers_preserve_public_prose_and_final(make_producer, channel):
    producer = make_producer(channel, chunks=[PUBLIC], answer=PUBLIC)
    events = asyncio.run(collect(producer.stream()))
    if channel != "openai":
        assert event_text(events) == PUBLIC
    assert terminal(events)["answer"] == PUBLIC


@pytest.mark.parametrize("channel", INCREMENTAL_CHANNELS)
@pytest.mark.parametrize("width", [1, 3])
def test_public_text_small_chunks_preserve_words_numbers_urls_and_whitespace(make_producer, channel, width):
    producer = make_producer(channel, chunks=[PUBLIC[i:i + width] for i in range(0, len(PUBLIC), width)], answer=PUBLIC)
    events = asyncio.run(collect(producer.stream()))
    assert event_text(events) == PUBLIC
    assert terminal(events)["answer"] == PUBLIC


@pytest.mark.parametrize("channel", ["anthropic", "claude"])
@pytest.mark.parametrize("encoded,split", SPLITS)
def test_thinking_blocks_protect_every_split(make_producer, channel, encoded, split):
    producer = make_producer(channel, thinking=["Before|" + encoded[:split], encoded[split:] + "|After"])
    events = asyncio.run(collect(producer.stream()))
    assert event_text(events, EventType.thinking_content) == "Before|[REDACTED]|After"
    assert terminal(events)["answer"] == "Public answer"


@pytest.mark.parametrize("channel", ["anthropic", "claude"])
def test_thinking_preserves_public_text_in_small_chunks(make_producer, channel):
    producer = make_producer(channel, thinking=[PUBLIC[i:i + 3] for i in range(0, len(PUBLIC), 3)])
    events = asyncio.run(collect(producer.stream()))
    assert event_text(events, EventType.thinking_content) == PUBLIC


@pytest.mark.parametrize("channel", ["anthropic", "claude"])
@pytest.mark.parametrize("encoding", REPRESENTATIONS)
@pytest.mark.parametrize("width", [1, 3])
def test_thinking_protects_known_credentials_in_small_chunks(make_producer, channel, encoding, width):
    text = "Before|" + REPRESENTATIONS[encoding] + "|After"
    producer = make_producer(channel, thinking=[text[i:i + width] for i in range(0, len(text), width)])
    events = asyncio.run(collect(producer.stream()))
    assert event_text(events, EventType.thinking_content) == "Before|[REDACTED]|After"


@pytest.mark.parametrize("channel", ["openai", "anthropic"])
def test_unbound_api_entry_registers_only_selected_client_before_response(make_producer, channel, monkeypatch):
    unselected = "unused-synthetic-ambient-key"
    monkeypatch.setenv("OPENAI_API_KEY", unselected)
    monkeypatch.setenv("ANTHROPIC_API_KEY", unselected)
    producer = make_producer(channel, answer=SECRET + "|" + unselected)
    assert current_runtime_auth(channel) is None
    assert current_output_guard() is None
    events = asyncio.run(collect(producer.stream()))
    assert producer.guards and all(guard is not None for guard in producer.guards), "selected client has no execution output guard"
    assert set(producer.registration_codes) == {"known_secret"}, "selected client was registered only after response consumption"
    for guard in producer.guards:
        with pytest.raises(OutputBoundaryError, match="^known_secret$"):
            guard.check(SECRET)
        guard.check(unselected)
    assert terminal(events)["answer"] == "[REDACTED]|" + unselected
    assert current_output_guard() is None


def test_refreshed_bearer_is_registered_before_chatgpt_response_consumption(make_producer):
    producer = make_producer("chatgpt", chunks=[SECRET[:3], SECRET[3:]], answer=SECRET)
    events = asyncio.run(collect(producer.stream()))
    assert producer.selected_bearer == SECRET
    assert producer.guards and producer.guards[0] is not None, "refreshed bearer was used without an output guard"
    assert producer.registration_codes == ["known_secret"], "fresh bearer registration was too late"
    with pytest.raises(OutputBoundaryError, match="^known_secret$"):
        producer.guards[0].check(SECRET)
    assert event_text(events) == "[REDACTED]"
    assert terminal(events)["answer"] == "[REDACTED]"
    assert producer.closed


def test_chatgpt_cleanup_failure_logs_no_raw_exception_and_preserves_answer(make_producer, monkeypatch, caplog):
    from src.auth_drivers import chatgpt_oauth_driver as driver_module

    producer = make_producer("chatgpt", answer="Public answer")
    execution_client = driver_module._execution_client
    close_guards = []

    def client_factory(token):
        client = execution_client(token)
        close = client.close

        async def failed_close():
            close_guards.append(current_output_guard())
            await close()
            raise RuntimeError("synthetic cleanup error: " + SECRET)

        client.close = failed_close
        return client

    monkeypatch.setattr(driver_module, "_execution_client", client_factory)
    stream = producer.stream()
    with caplog.at_level("WARNING", logger=driver_module.__name__):
        events = asyncio.run(collect(stream))
    assert terminal(events)["answer"] == "Public answer"
    assert producer.closed
    assert close_guards == [stream.guard]
    assert current_output_guard() is None
    assert SECRET not in caplog.text
    assert SECRET_JSON not in caplog.text
    records = [record for record in caplog.records if record.name == driver_module.__name__]
    assert len(records) == 1
    assert records[0].getMessage() == "failed to close ChatGPT OAuth execution client"
    assert records[0].exc_info is None
    assert records[0].exc_text is None


@pytest.mark.parametrize("channel", ["openai", "anthropic"])
def test_native_final_is_protected_before_real_scratchpad_and_replay(make_producer, isolated, monkeypatch, channel):
    monkeypatch.setenv("ARKSCOPE_REPLAY_CAPTURE", "1")
    producer = make_producer(channel, answer="Before|" + SECRET + "|After")
    events = asyncio.run(collect(producer.stream()))
    for directory in ("scratchpad", "replay"):
        serialized = json.dumps(sink_records(isolated.path, directory))
        assert SECRET_JSON not in serialized, f"raw selected credential reached {directory} before public protection"
        assert "Before|[REDACTED]|After" in serialized
    assert terminal(events)["answer"] == "Before|[REDACTED]|After"


def test_openai_nonstream_final_uses_same_pre_persistence_boundary(make_producer, isolated, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_REPLAY_CAPTURE", "1")
    producer = make_producer("openai", answer="Before|" + SECRET + "|After")
    result = asyncio.run(producer.call())
    assert result["answer"] == "Before|[REDACTED]|After"
    for directory in ("scratchpad", "replay"):
        assert SECRET_JSON not in json.dumps(sink_records(isolated.path, directory))


def test_thinking_is_protected_before_scratchpad_preview_splits_credential(make_producer, isolated):
    text = "x" * 498 + SECRET + "|After"
    producer = make_producer("anthropic", thinking=[text])
    events = asyncio.run(collect(producer.stream()))
    records = [json.loads(line) for path in (isolated.path / "scratchpad").rglob("*.jsonl") for line in path.read_text().splitlines()]
    previews = [record["data"]["preview"] for record in records if record["type"] == "thinking"]
    assert previews, "actual thinking scratchpad path was not exercised"
    assert all(SECRET[:2] not in preview for preview in previews), "raw credential prefix persisted before preview truncation"
    assert event_text(events, EventType.thinking_content) == "x" * 498 + "[REDACTED]|After"


def test_fragmented_thinking_never_reconstructs_secret_in_scratchpad(make_producer, isolated):
    producer = make_producer("anthropic", thinking=[SECRET[:3], SECRET[3:]])
    asyncio.run(collect(producer.stream()))
    records = sink_records(isolated.path, "scratchpad")
    previews = [record["data"]["preview"] for record in records if record["type"] == "thinking"]
    assert previews
    assert "".join(previews) == "[REDACTED]", "public redaction did not protect fragmented durable thinking"


@pytest.mark.parametrize("field", ["input", "output"])
def test_openai_tool_trace_checks_full_value_before_scratchpad_replay_or_preview(isolated, field):
    from src.agents.openai_agent.agent import _extract_tool_info
    from src.agents.shared.replay import ReplayCapture
    from src.agents.shared.scratchpad import Scratchpad
    from src.agents.shared.token_tracker import TokenTracker

    args = {"query": SECRET if field == "input" else "Public query"}
    raw_result = json.dumps({"rows": "Public. " * 700 + (SECRET if field == "output" else "Public tail")})
    result = SimpleNamespace(raw_responses=[SimpleNamespace(usage=None, output=[
        SimpleNamespace(type="function_call", name="tool_search_news_advanced", call_id="call_fixture", arguments=json.dumps(args)),
        SimpleNamespace(type="function_call_output", call_id="call_fixture", output=raw_result),
    ])])
    pad = Scratchpad(query="Public", provider="openai", model="gpt-5.6-luna")
    capture = ReplayCapture(provider="openai", model="gpt-5.6-luna", entrypoint="api", output_dir=isolated.path / "replay")
    try:
        with output_scope(SECRET), pytest.raises(OutputBoundaryError, match="^known_secret$"):
            _extract_tool_info(result, pad, TokenTracker(), "gpt-5.6-luna", capture=capture)
    finally:
        pad.close()
        capture.save()
    for directory in ("scratchpad", "replay"):
        assert SECRET_JSON not in json.dumps(sink_records(isolated.path, directory))


def test_claude_tool_result_is_protected_before_preview_splits_credential(isolated):
    from claude_agent_sdk import ToolResultBlock, UserMessage
    from tests.test_claude_code_sdk_driver import _REQ, _make_driver

    prefix = "Public. " * 24 + "......"
    assert len(prefix) == 198
    message = UserMessage(content=[ToolResultBlock(tool_use_id="call_public", content=prefix + SECRET + "|After", is_error=False)])
    with output_scope(SECRET):
        try:
            events = _make_driver(token=SECRET)._map(message, _REQ, SECRET, {"call_public": "get_news_brief"})
        except OutputBoundaryError as exc:
            assert exc.code == "known_secret"
            return
    assert len(events) == 1 and events[0].type == EventType.tool_end
    preview = events[0].data["summary"]
    assert preview.startswith(prefix), "tool preview rewrote unrelated public prose"
    assert SECRET[:2] not in preview, "raw credential prefix reached the preview before protection"


def test_successful_openai_answer_keeps_sdk_trace_content_disabled(make_producer, enabled_local_sdk_tracing):
    producer = make_producer("openai", answer=SECRET)
    asyncio.run(collect(producer.stream()))
    memory = enabled_local_sdk_tracing
    assert memory.spans, "real SDK trace processor was not reached"
    assert SECRET_JSON not in json.dumps(memory.spans)
    assert any(span.get("span_data", {}).get("type") == "response" for span in memory.spans)


@pytest.mark.parametrize("channel", ["openai", "anthropic", "chatgpt", "claude"])
@pytest.mark.parametrize("private", [False, True], ids=["public-input", "credential-input"])
def test_tool_arguments_are_checked_before_write_or_acquisition_callback(monkeypatch, isolated, caplog, channel, private):
    from src.tools import news_tools, registry as registry_module, report_tools

    calls = []
    name = "save_report" if channel in ("openai", "anthropic") else "search_news_advanced"
    content = SECRET if private else PUBLIC

    def handler(*args, **kwargs):
        calls.append(kwargs)
        return {"saved": True}

    # Native write tools must reject before persistence. OAuth keeps its existing
    # readonly allowlist and must reject before even an acquisition callback.
    source = report_tools if name == "save_report" else news_tools
    monkeypatch.setattr(source, name, handler)
    registry = registry_module.create_default_registry()
    registry.get(name).function = handler
    monkeypatch.setattr(registry_module, "create_default_registry", lambda: registry)
    args = ({"title": "Public", "tickers": ["AAPL"], "report_type": "custom", "summary": "Public",
             "content": content, "conclusion": None, "confidence": None} if name == "save_report" else
            {"query": content, "days": 7, "tickers": None, "limit": 20})

    async def invoke():
        if channel == "openai":
            from agents import _debug
            from agents.tool_context import ToolContext

            monkeypatch.setattr(_debug, "DONT_LOG_TOOL_DATA", False)
            caplog.set_level("DEBUG", logger="openai.agents")
            tool = next(tool for tool in _NATIVE_OPENAI_TOOLS(object()) if tool.name == "tool_save_report")
            encoded = json.dumps(args)
            context = ToolContext(context=None, tool_name=tool.name, tool_call_id="call_boundary", tool_arguments=encoded)
            return await tool.on_invoke_tool(context, encoded)
        if channel == "anthropic":
            from src.agents.anthropic_agent.tools import execute_tool
            return execute_tool(name, args, object())
        if channel == "chatgpt":
            from src.auth_drivers.chatgpt_oauth_driver import OpenAIChatGPTOAuthDriver
            return await OpenAIChatGPTOAuthDriver(registry=registry, dal=object())._invoke_tool(name=name, args=args, token=SECRET)
        from src.auth_drivers.claude_code_sdk_driver import _invoke_bridged_tool
        return await _invoke_bridged_tool(name=name, args=args, registry=registry, dal=object(), token=SECRET, per_tool_timeout_s=5)

    with output_scope(SECRET):
        try:
            result = asyncio.run(invoke())
        except OutputBoundaryError as exc:
            result = exc.code
    if private:
        assert calls == [], "credential-bearing arguments reached a handler before admission"
        assert "known_secret" in str(result)
        assert SECRET not in str(result)
        assert SECRET not in caplog.text and SECRET_JSON not in caplog.text
    else:
        assert len(calls) == 1
        assert calls[0]["content" if name == "save_report" else "query"] == PUBLIC
        if channel == "chatgpt":
            assert result[0] is True
        elif channel == "claude":
            assert result["is_error"] is False
        else:
            assert result.startswith('<tool_output tool="save_report">')


@pytest.fixture
def managed_run(isolated):
    from tests.test_research_runs import _seed_run

    _seed_run(isolated.runs, isolated.threads, thread_id="boundary-thread", run_id="boundary-run", model="gpt-5.6-luna")
    return dict(run_id="boundary-run", run_store=isolated.runs, thread_store=isolated.threads,
                dal=object(), history=[], auth_binding=RuntimeAuthBinding(
                    "openai", "fixture", "api_key", "local:test", _api_key=SECRET,
                ))


@pytest.mark.parametrize("width", [1, 2, 3])
def test_managed_injected_stream_is_protected_before_event_append_and_replay(managed_run, isolated, monkeypatch, width):
    from src.api.routes.research import list_research_run_events
    from src.research_run_manager import execute_research_run

    text = "Before|" + SECRET + "|After"
    appended = []
    append = isolated.runs.append_event

    def observe(run_id, kind, data):
        appended.append((kind, dict(data)))
        return append(run_id, kind, data)

    monkeypatch.setattr(isolated.runs, "append_event", observe)

    async def raw(**kwargs):
        for offset in range(0, len(text), width):
            yield AgentEvent(EventType.text, {"content": text[offset:offset + width]})
        yield AgentEvent(EventType.done, {"answer": "Safe final", "provider": "openai", "model": "gpt-5.4-mini", "tools_used": []})

    asyncio.run(execute_research_run(**managed_run, stream_factory=raw))
    assert "".join(data["content"] for kind, data in appended if kind == "text") == "Before|[REDACTED]|After", "final-only protection left unsafe pre-append text"
    durable = isolated.runs.list_events("boundary-run")
    assert "".join(event.data["content"] for event in durable if event.type == "text") == "Before|[REDACTED]|After"
    replay = list_research_run_events("boundary-run", after=0, run_store=isolated.runs)
    assert SECRET_JSON not in json.dumps(replay)
    assert len([event for event in durable if event.type in ("done", "error")]) == 1
    assert isolated.threads.list_messages("boundary-thread")[-1].content == "Safe final"


@pytest.mark.parametrize("sink", ["managed", "legacy"])
@pytest.mark.parametrize("field", ["tool-input", "call-id", "extra-key"])
def test_raw_injected_metadata_is_typed_failure_before_public_or_durable_sink(managed_run, isolated, monkeypatch, sink, field):
    from src.api.routes import query
    from src.research_run_manager import execute_research_run

    data = {"tool": "save_report", "input": {"content": "Public"}}
    if field == "tool-input":
        data["input"]["content"] = SECRET
    elif field == "call-id":
        data["call_id"] = SECRET
    else:
        data[SECRET] = "Public"
    closed = []

    async def raw(**kwargs):
        try:
            yield AgentEvent(EventType.tool_start, data)
            yield AgentEvent(EventType.done, {"answer": "must not succeed"})
        finally:
            closed.append(True)

    async def drive():
        if sink == "managed":
            await execute_research_run(**managed_run, stream_factory=raw)
            return [{"type": event.type, "data": event.data} for event in isolated.runs.list_events("boundary-run")]
        monkeypatch.setattr(query, "capture_runtime_auth", lambda provider: managed_run["auth_binding"])
        monkeypatch.setattr(query, "_research_provider_stream", raw)
        response = await query.query_agent_stream(query.QueryRequest(
            question="Public question", provider="openai", model="gpt-5.6-luna", effort="low", thread_id="boundary-thread",
        ), dal=object(), store=isolated.threads)
        return [json.loads(frame.removeprefix("data: ").strip()) async for frame in response.body_iterator]

    events = asyncio.run(drive())
    assert [event["type"] for event in events] == ["error"], "unsafe metadata reached a sink as successful trace data"
    assert events[0]["data"]["code"] == "provider_call_failed"
    reason = events[0]["data"]["error"]
    if field == "extra-key":
        assert reason in {"known_secret", "invalid_value"}
    else:
        assert reason == "known_secret"
    assert SECRET_JSON not in json.dumps(events)
    assert closed == [True]
    message = isolated.threads.list_messages("boundary-thread")[-1]
    assert message.is_error and SECRET not in message.content
    if sink == "managed":
        assert isolated.runs.get_run("boundary-run").status == "failed"
