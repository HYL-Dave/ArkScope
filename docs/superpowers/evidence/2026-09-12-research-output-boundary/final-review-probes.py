"""Independent final-review probes. Synthetic inputs, no live transports."""

import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile

import httpx2
import pytest


SCRATCH = Path(__file__).resolve().parent


def _review_audit(event, args):
    if event in {"socket.connect", "socket.sendto", "socket.getaddrinfo", "subprocess.Popen"}:
        raise PermissionError("final review forbids network and subprocesses")
    if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(args[0])).resolve()
        mode, flags = args[1:3]
        write = (isinstance(mode, str) and any(flag in mode for flag in "wax+")) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        )
        if write and not path.is_relative_to(SCRATCH):
            raise PermissionError("final review forbids writes outside plan scratch")
        if path.name == ".env":
            raise PermissionError("final review forbids dotenv reads")


sys.addaudithook(_review_audit)


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    from src.agents.shared import scratchpad

    monkeypatch.setattr(scratchpad, "_DEFAULT_BASE_DIR", tmp_path / "scratchpad")
    monkeypatch.delenv("ARKSCOPE_REPLAY_CAPTURE", raising=False)


def _frames(model, blocks, stop):
    frames = [{"type": "message_start", "message": {
        "id": "msg_review", "type": "message", "role": "assistant", "model": model,
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


@pytest.mark.parametrize("echo_credential", [False, True])
def test_native_compaction_error_log(monkeypatch, tmp_path, caplog, echo_credential):
    from anthropic import Anthropic
    from src.agents import config
    from src.agents.anthropic_agent import agent
    from src.agents.shared.output_boundary import OutputBoundaryError, current_output_guard
    from src.auth_drivers import live_resolver
    from src.tools import news_tools

    secret = "review-fixture-access-K4w2-Y9p6"
    summary_model = "claude-sonnet-5"
    main_model = "claude-sonnet-4-6"
    settings = config.AgentConfig(
        compaction_enabled=True, compaction_layer_5_enabled=True,
        compaction_layer_5_threshold_chars=1,
        compaction_layer_5_model_anthropic=summary_model,
        compaction_overflow_dir=str(tmp_path / "overflow"),
        context_keep_recent_turns=1,
        web_openai_search=False, web_playwright=False,
    )
    monkeypatch.setattr(config, "get_agent_config", lambda: settings)
    monkeypatch.setattr(agent, "get_agent_config", lambda: settings)
    monkeypatch.setattr(agent, "_build_anthropic_tools_list", lambda config: [])
    monkeypatch.setattr(news_tools, "get_news_brief", lambda *args, **kwargs: {"count": 0})
    calls = []

    def reply(request):
        body = json.loads(request.content)
        calls.append(body["model"])
        with pytest.raises(OutputBoundaryError, match="^known_secret$"):
            current_output_guard().check(secret)
        if body["model"] == summary_model:
            detail = secret if echo_credential else "synthetic public error"
            return httpx2.Response(400, json={"type": "error", "error": {
                "type": "invalid_request_error", "message": detail,
            }})
        first = calls.count(main_model) == 1
        blocks = [{"type": "tool_use", "id": "call_review", "name": "get_news_brief",
                   "input": {"days": 7}}] if first else [{"type": "text", "text": "OK"}]
        return httpx2.Response(200, text=_frames(main_model, blocks, "tool_use" if first else "end_turn"),
                               headers={"content-type": "text/event-stream"})

    client = Anthropic(api_key=secret, max_retries=0,
                       http_client=httpx2.Client(transport=httpx2.MockTransport(reply)))
    monkeypatch.setattr(live_resolver, "live_anthropic_client", lambda: client)

    async def drive():
        stream = agent.run_query_stream(
            "Public question", model=main_model, dal=object(), effort="low",
            history=[{"role": "user", "content": "Prior public question"},
                     {"role": "assistant", "content": "Prior public answer"}],
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
    assert secret not in json.dumps([event.data for event in events])
    logs = [row.getMessage() for row in caplog.records if row.name.endswith("summary_callers")]
    assert len(logs) == 1
    assert (secret in logs[0]) is echo_credential
    print(json.dumps({"probe": "compaction_log", "echo_credential": echo_credential,
                      "credential_in_log": secret in logs[0], "public_answer": events[-1].data["answer"]}))
