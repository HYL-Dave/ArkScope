from dataclasses import replace
import json
from pathlib import Path
import sys
import threading
import time

import pytest

from tests.test_subscription_account_usage import _token_record, _wait_for_process_exit, _write_codex_fixture


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.parametrize("purpose,web", [("lifecycle_web_search", "live"), ("lifecycle_web_analysis", "disabled")])
def test_only_explicit_web_runtime_purposes_change_codex_command(tmp_path, purpose, web):
    from src.auth_drivers.codex_app_server_runtime import run_authenticated_codex_operation

    executable, transcript, pid_path = _write_codex_fixture(tmp_path)
    run_authenticated_codex_operation(
        record=_token_record(), client_name="web-runtime-test", timeout_seconds=3, executable=executable,
        purpose=purpose, allowed_notifications=frozenset(),
        operation=lambda session, context: session.request(4, "model/list", {"cursor": None, "limit": 1}),
    )
    args = json.loads(transcript.read_text().splitlines()[0])["argv"]
    assert f'web_search="{web}"' in args
    assert "model_providers.openai.request_max_retries=0" in args
    assert "model_providers.openai.stream_max_retries=0" in args
    assert "features.shell_tool=false" in args and "features.multi_agent=false" in args
    _wait_for_process_exit(int(pid_path.read_text()))


def test_codex_unknown_purpose_fails_before_starting_binary(tmp_path):
    from src.auth_drivers.codex_app_server_runtime import run_authenticated_codex_operation

    executable, _, pid_path = _write_codex_fixture(tmp_path)
    with pytest.raises(ValueError, match="codex_purpose_unsupported"):
        run_authenticated_codex_operation(
            record=_token_record(), client_name="web-runtime-test", timeout_seconds=3, executable=executable,
            purpose="unrestricted", allowed_notifications=frozenset(), operation=lambda session, context: None,
        )
    assert not pid_path.exists() and not (tmp_path / "version-ran.marker").exists()


def test_codex_poll_checks_stop_while_peer_is_silent_and_reaps_process(tmp_path):
    from src.auth_drivers.codex_app_server_runtime import run_authenticated_codex_operation

    executable, _, pid_path = _write_codex_fixture(tmp_path, hang_method="model/list")
    entered = None

    class StopRequested(Exception):
        pass

    def poll():
        if entered is not None and time.monotonic() - entered > 0.1:
            raise StopRequested

    def operation(session, context):
        nonlocal entered
        entered = time.monotonic()
        return session.request(4, "model/list", {})

    started = time.monotonic()
    with pytest.raises(StopRequested):
        run_authenticated_codex_operation(
            record=_token_record(), client_name="web-runtime-test", timeout_seconds=5, executable=executable,
            purpose="lifecycle_web_search", poll_check=poll, allowed_notifications=frozenset(), operation=operation,
        )
    assert time.monotonic() - started < 3
    _wait_for_process_exit(int(pid_path.read_text()))


def test_codex_poll_checks_stop_while_peer_does_not_read_stdin(tmp_path):
    from src.auth_drivers.codex_app_server_runtime import run_authenticated_codex_operation, terminate_process_group

    executable, _, pid_path = _write_codex_fixture(tmp_path, hang_method="model/list")
    entered, cleanup = threading.Event(), threading.Event()
    processes = []
    started_at = None

    class StopRequested(Exception):
        pass

    def operation(session, context):
        nonlocal started_at
        processes.append(session.process)
        session._write({"id": 4, "method": "model/list", "params": {}})
        started_at = time.monotonic()
        entered.set()
        return session.request(5, "turn/start", {"text": "x" * 2_000_000})

    def poll():
        if started_at is not None and time.monotonic() - started_at > 0.1:
            raise StopRequested

    # A regression must fail, not leave the test process waiting on a full pipe.
    def watchdog():
        if entered.wait(3) and not cleanup.wait(2):
            for process in processes:
                terminate_process_group(process)

    guard = threading.Thread(target=watchdog)
    guard.start()
    try:
        with pytest.raises(StopRequested):
            run_authenticated_codex_operation(
                record=_token_record(), client_name="web-runtime-test", timeout_seconds=5, executable=executable,
                purpose="lifecycle_web_search", poll_check=poll, max_request_bytes=3_000_000,
                allowed_notifications=frozenset(), operation=operation,
            )
    finally:
        cleanup.set()
        entered.set()
        guard.join(4)
    _wait_for_process_exit(int(pid_path.read_text()))


@pytest.mark.anyio
@pytest.mark.parametrize("phase", ["search", "analysis"])
async def test_codex_web_real_jsonl_transport_uses_selected_auth_and_closed_child(tmp_path, monkeypatch, phase):
    from src.auth_drivers import codex_app_server_runtime as runtime
    from src.auth_drivers.lifecycle_web_codex import call_codex_web
    from src.auth_drivers.lifecycle_web_models import ModelCall, WebCredential
    from src.security_lifecycle_web_contract import RunControl, validate_selection

    executable = tmp_path / "web-peer"
    fixture = Path(__file__).parent / "fixtures" / "lifecycle_web_codex_process.py"
    executable.write_text(f"#!{sys.executable}\n" + fixture.read_text())
    executable.chmod(0o700)
    monkeypatch.setattr(runtime, "_default_codex_executable", lambda: executable)
    monkeypatch.setenv("OPENAI_API_KEY", "ambient-key-not-used")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "ambient-token-not-used")
    selection = validate_selection("openai", "chatgpt_oauth", "gpt-5.6-luna", "local:7")
    schema = {"type": "object", "properties": {"sources": {"type": "array", "items": {"type": "string"}}},
              "required": ["sources"], "additionalProperties": False}
    call = ModelCall(selection, "call-1", phase, "Public issuer question", schema, "high", None, 2, 5)
    control = RunControl(selection=selection, max_model_requests=1)
    result = await call_codex_web(call, WebCredential(selection, token_record=_token_record()), control)
    assert result.output == {"sources": ["https://ir.example.com/notice"]}
    entries = [json.loads(line) for line in (tmp_path / "web-peer.jsonl").read_text().splitlines()]
    assert [entry["method"] for entry in entries].count("turn/start") == 1
    assert "OPENAI_API_KEY" not in entries[0]["environment_keys"]
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in entries[0]["environment_keys"]
    assert not Path(entries[0]["home"]).exists()
    _wait_for_process_exit(int((tmp_path / "web-peer.pid").read_text()))
