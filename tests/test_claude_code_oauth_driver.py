"""Slice 7A-1 — AnthropicClaudeCodeOAuthDriver (fake-subprocess TDD, NO live claude).

The driver runs `claude -p --bare --output-format stream-json --verbose` with the
subscription token injected from the token-store, and maps the NDJSON stream to
the EXISTING AgentEvent vocab. All tests inject a FAKE subprocess (canned
stream-json captured by the live probe) — the real `claude` is never spawned.
"""

from __future__ import annotations

import asyncio
import json
import logging

import pytest

from src.auth_drivers.claude_code_oauth_driver import AnthropicClaudeCodeOAuthDriver
from src.auth_drivers.protocol import AuthDriver, LLMRequest
from src.agents.shared.events import EventType

FAKE_TOKEN = "claude-oauth-FAKE-zzz-DO-NOT-LOG"

# --- probe-captured stream-json fixtures (one NDJSON object per line) ---------
FIX_INIT = {"type": "system", "subtype": "init", "cwd": "/tmp", "session_id": "s1",
            "tools": ["Bash", "Edit", "Read"], "model": "claude-sonnet-4-6"}
FIX_TEXT = {"type": "assistant", "message": {"id": "m1", "role": "assistant", "type": "message",
            "content": [{"type": "text", "text": "42"}]}}
FIX_TOOL_USE = {"type": "assistant", "message": {"id": "m2", "role": "assistant", "type": "message",
                "content": [{"type": "tool_use", "id": "toolu_01", "name": "Read", "input": {"file_path": "/x"}}]}}
FIX_TOOL_RESULT = {"type": "user", "message": {"role": "user",
                   "content": [{"type": "tool_result", "tool_use_id": "toolu_01", "content": "file contents here", "is_error": False}]}}
FIX_RESULT_OK = {"type": "result", "subtype": "success", "is_error": False, "num_turns": 2,
                 "result": "The answer is 42.", "session_id": "s1", "total_cost_usd": 0.003,
                 "usage": {"input_tokens": 10, "output_tokens": 5}}
# REAL gotcha captured live: subtype 'success' BUT is_error true → must be error, NOT done.
FIX_RESULT_AUTHFAIL = {"type": "result", "subtype": "success", "is_error": True, "num_turns": 1,
                       "result": "authentication_failed", "session_id": "s1"}
FIX_RESULT_ERR = {"type": "result", "subtype": "error", "is_error": True, "result": "max turns exceeded", "num_turns": 3}


def _lines(*objs) -> list[bytes]:
    return [(json.dumps(o) + "\n").encode() for o in objs]


class _FakeStdout:
    def __init__(self, lines: list[bytes]):
        self._lines = list(lines)

    async def readline(self) -> bytes:
        return self._lines.pop(0) if self._lines else b""  # b'' == EOF

    async def read(self) -> bytes:
        out = b"".join(self._lines); self._lines = []; return out


class _FakeStderr:
    def __init__(self, data: bytes = b""):
        self._data = data

    async def read(self) -> bytes:
        return self._data


class _FakeProc:
    def __init__(self, lines, *, returncode=0, stderr=b"", hang=False):
        self.stdout = _FakeStdout(lines)
        self.stderr = _FakeStderr(stderr)
        self._returncode = returncode
        self._hang = hang
        self.terminated = False
        self.killed = False

    @property
    def returncode(self):
        return self._returncode

    async def wait(self):
        return self._returncode

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


def _driver(lines=None, *, proc=None, capture=None, which="/usr/bin/claude", token=FAKE_TOKEN, **kw):
    """Build a driver with a fake spawn seam. `capture` (dict) records argv+env."""
    class _Store:
        def load(self, *, provider, auth_mode, credential_id):
            if token is None:
                return None
            from src.auth_drivers.token_store import StoredTokenRecord
            return StoredTokenRecord(access_token=token)

    class _Cred:
        id = 1

    async def fake_spawn(argv, env):
        if capture is not None:
            capture["argv"] = argv
            capture["env"] = env
        return proc if proc is not None else _FakeProc(_lines(*(lines or [FIX_RESULT_OK])))

    return AnthropicClaudeCodeOAuthDriver(
        credential=_Cred(), token_store=_Store(), spawn=fake_spawn,
        which=lambda _name: which, **kw,
    )


async def _collect(driver, request=None):
    request = request or LLMRequest(model="claude-sonnet-4-6", instructions="SYS", input_messages=[{"role": "user", "content": "q"}])
    return [ev async for ev in driver.stream_llm(request)]


# --- invocation + auth injection ---------------------------------------------
def test_invocation_argv_and_bare_and_model():
    cap = {}
    d = _driver(capture=cap)
    asyncio.run(_collect(d, LLMRequest(model="claude-sonnet-4-6", instructions="RESEARCH SYS", input_messages=[{"role": "user", "content": "what is 6*7?"}])))
    argv = cap["argv"]
    assert argv[:3] == ["claude", "-p", "--bare"]                  # isolated from dev .claude/ config
    # drop the global `user` setting source (the superpowers SessionStart hook
    # lives there — 7A-2 found --bare alone doesn't strip it)
    assert "--setting-sources" in argv and argv[argv.index("--setting-sources") + 1] == "project,local"
    assert "--model" in argv and argv[argv.index("--model") + 1] == "claude-sonnet-4-6"
    assert "--system-prompt" in argv and argv[argv.index("--system-prompt") + 1] == "RESEARCH SYS"
    assert "--output-format" in argv and argv[argv.index("--output-format") + 1] == "stream-json"
    assert "--verbose" in argv
    assert argv[-1] == "what is 6*7?"                              # composed input is the last positional arg


def test_auth_env_injection():
    cap = {}
    d = _driver(capture=cap)
    asyncio.run(_collect(d))
    assert cap["env"]["CLAUDE_CODE_OAUTH_TOKEN"] == FAKE_TOKEN     # subscription token injected
    assert "ANTHROPIC_API_KEY" not in cap["env"]                  # API key popped → no API billing


def test_token_never_in_argv_or_logs(caplog):
    cap = {}
    d = _driver(capture=cap)
    with caplog.at_level(logging.DEBUG):
        asyncio.run(_collect(d))
    assert FAKE_TOKEN not in " ".join(cap["argv"])                # token via env, never argv
    assert all(FAKE_TOKEN not in r.getMessage() for r in caplog.records)  # never logged


def test_missing_token_raises_before_spawn():
    spawned = {"called": False}
    class _Store:
        def load(self, **k): return None
    class _Cred: id = 1
    async def fake_spawn(argv, env):
        spawned["called"] = True
        return _FakeProc(_lines(FIX_RESULT_OK))
    d = AnthropicClaudeCodeOAuthDriver(credential=_Cred(), token_store=_Store(), spawn=fake_spawn, which=lambda _n: "/usr/bin/claude")
    with pytest.raises(Exception):
        asyncio.run(_collect(d))
    assert spawned["called"] is False                             # never spawn without a token


# --- NDJSON → AgentEvent mapper ----------------------------------------------
def test_map_init_swallowed():
    assert asyncio.run(_collect(_driver(lines=[FIX_INIT, FIX_RESULT_OK])))[:-1] == []  # init yields nothing


def test_map_text():
    evs = asyncio.run(_collect(_driver(lines=[FIX_TEXT, FIX_RESULT_OK])))
    assert evs[0].type == EventType.text and evs[0].data["content"] == "42"


def test_map_tool_use_to_tool_start():
    evs = asyncio.run(_collect(_driver(lines=[FIX_TOOL_USE, FIX_RESULT_OK])))
    assert evs[0].type == EventType.tool_start and evs[0].data["tool"] == "Read" and evs[0].data["input"] == {"file_path": "/x"}


def test_map_tool_result_to_tool_end():
    evs = asyncio.run(_collect(_driver(lines=[FIX_TOOL_USE, FIX_TOOL_RESULT, FIX_RESULT_OK])))
    te = next(e for e in evs if e.type == EventType.tool_end)
    assert te.data["tool"] == "Read" and "file contents here" in te.data["summary"]


def test_map_result_success_to_done():
    evs = asyncio.run(_collect(_driver(lines=[FIX_RESULT_OK])))
    assert evs[-1].type == EventType.done
    assert evs[-1].data["answer"] == "The answer is 42." and evs[-1].data["provider"] == "anthropic"
    assert evs[-1].data["token_usage"]["input_tokens"] == 10


def test_result_is_error_true_maps_to_error_not_done():  # THE GOTCHA
    evs = asyncio.run(_collect(_driver(lines=[FIX_RESULT_AUTHFAIL])))
    assert evs[-1].type == EventType.error
    assert all(e.type != EventType.done for e in evs)
    assert "error" in evs[-1].data  # C-2 reducer reads data['error'] first


def test_map_result_subtype_error_to_error():
    evs = asyncio.run(_collect(_driver(lines=[FIX_RESULT_ERR])))
    assert evs[-1].type == EventType.error and "error" in evs[-1].data


def test_full_sequence_event_order():
    evs = asyncio.run(_collect(_driver(lines=[FIX_INIT, FIX_TEXT, FIX_TOOL_USE, FIX_TOOL_RESULT, FIX_RESULT_OK])))
    assert [e.type for e in evs] == [EventType.text, EventType.tool_start, EventType.tool_end, EventType.done]


def test_malformed_line_skipped_not_fatal():
    proc = _FakeProc([b"not json at all\n", b"\n", b'{"partial":\n'] + _lines(FIX_TEXT, FIX_RESULT_OK))
    evs = asyncio.run(_collect(_driver(proc=proc)))
    assert [e.type for e in evs] == [EventType.text, EventType.done]  # garbage skipped, valid terminal still emitted


def test_exactly_one_terminal():
    for fix in (FIX_RESULT_OK, FIX_RESULT_AUTHFAIL, FIX_RESULT_ERR):
        evs = asyncio.run(_collect(_driver(lines=[FIX_TEXT, fix])))
        terminals = [e for e in evs if e.type in (EventType.done, EventType.error)]
        assert len(terminals) == 1 and evs[-1].type in (EventType.done, EventType.error)


# --- lifecycle ----------------------------------------------------------------
def test_stream_ended_without_result():
    proc = _FakeProc(_lines(FIX_INIT, FIX_TEXT))  # no result line, rc 0
    evs = asyncio.run(_collect(_driver(proc=proc)))
    assert evs[-1].type == EventType.error and all(e.type != EventType.done for e in evs)


def test_nonzero_exit_emits_one_error_with_stderr_no_token():
    proc = _FakeProc(_lines(FIX_INIT), returncode=1, stderr=("boom " + FAKE_TOKEN).encode())
    evs = asyncio.run(_collect(_driver(proc=proc)))
    terminals = [e for e in evs if e.type in (EventType.done, EventType.error)]
    assert len(terminals) == 1 and terminals[0].type == EventType.error
    assert FAKE_TOKEN not in json.dumps(terminals[0].data)  # token never leaks into the error


def test_timeout_terminates_and_errors():
    class _HangStdout:
        async def readline(self):
            await asyncio.sleep(10)  # never returns a line
            return b""
        async def read(self): return b""
    proc = _FakeProc([]); proc.stdout = _HangStdout()
    d = _driver(proc=proc, timeout_s=0.2)
    evs = asyncio.run(_collect(d))
    assert evs[-1].type == EventType.error and "tim" in evs[-1].data["error"].lower()
    assert proc.terminated is True


def test_cli_missing_raises_clear_error():
    d = _driver(which=None)
    with pytest.raises(RuntimeError) as ei:
        asyncio.run(_collect(d))
    assert "not installed" in str(ei.value).lower()


# --- conformance + factory ----------------------------------------------------
def test_conforms_to_authdriver_and_identity():
    d = _driver()
    assert isinstance(d, AuthDriver)
    assert d.provider == "anthropic" and d.auth_mode == "claude_code_oauth"


# NOTE: the factory→driver wiring for (anthropic, claude_code_oauth) is asserted in
# test_auth_factory.py::test_claude_code_oauth_is_the_sdk_driver_not_placeholder — it
# now builds the 7B AnthropicClaudeCodeSdkDriver, NOT this experimental --bare driver
# (which stays importable for diagnostics only, 7B-5 e52d38f). The stale assertion
# that the factory builds AnthropicClaudeCodeOAuthDriver was removed here.


def test_factory_openai_chatgpt_oauth_is_the_discovery_driver():
    # S3 step 1: openai+chatgpt_oauth is now a real (discovery) driver, not a
    # placeholder. (The factory→driver assertion lives in test_auth_factory.py too.)
    from src.auth_drivers.factory import build_driver, NotImplementedDriver
    from src.auth_drivers.chatgpt_oauth_driver import OpenAIChatGPTOAuthDriver
    drv = build_driver(provider="openai", auth_mode="chatgpt_oauth", credential=None, token_store=object())
    assert isinstance(drv, OpenAIChatGPTOAuthDriver) and not isinstance(drv, NotImplementedDriver)


def test_discover_models_returns_seed_catalog():
    res = asyncio.run(_driver().discover_models())
    assert res.provider == "anthropic" and len(res.models) > 0 and all(m.source == "seed" for m in res.models)
