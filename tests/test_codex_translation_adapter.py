from __future__ import annotations

import asyncio
from dataclasses import replace
import json
import os
from pathlib import Path
import stat
import sys
import time

import pytest

from tests.test_subscription_account_usage import _token_record


_MODEL = "gpt-5.3-codex-spark"
_SCHEMA = {
    "type": "object",
    "properties": {"translated_text": {"type": "string", "minLength": 1}},
    "required": ["translated_text"],
    "additionalProperties": False,
}


def _record(plan_type: str | None = "pro"):
    return replace(_token_record(), plan_type=plan_type)


def _write_fixture(tmp_path: Path, **overrides) -> tuple[Path, Path, Path]:
    scenario = {
        "live_plan": "pro",
        "startup_notification": None,
        "turn_notification": None,
        "turn_telemetry": [],
        "turn_control_events": [],
        "control_thread_id": None,
        "control_turn_id": None,
        "control_model": None,
        "model_verifications": [],
        "error_info": "usageLimitExceeded",
        "error_will_retry": False,
        "turn_settings_mutation": None,
        "models": [_MODEL],
        "model_pages": None,
        "thread_mutation": None,
        "mcp_startup_status": None,
        "deprecation_notice": False,
        "item_type": None,
        "server_request": False,
        "wrong_thread": False,
        "wrong_turn": False,
        "duplicate_final": False,
        "missing_final": False,
        "output": json.dumps({"translated_text": "營收成長 12%。"}, ensure_ascii=False),
        "turn_status": "completed",
        "turn_error": None,
        "hang_method": None,
        "stdout_bloat": 0,
    }
    scenario.update(overrides)
    executable = tmp_path / "codex-translation-fixture"
    transcript = tmp_path / "translation-methods.jsonl"
    pid_path = tmp_path / "translation.pid"
    source = r'''#!%s
import json
import os
from pathlib import Path
import sys
import time

SCENARIO = json.loads(%r)
TRANSCRIPT = Path(%r)
PID_PATH = Path(%r)

if sys.argv[1:] == ["--version"]:
    print("codex-cli 0.147.0", flush=True)
    raise SystemExit(0)

PID_PATH.write_text(str(os.getpid()), encoding="utf-8")

def emit(value):
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")), flush=True)

def thread_value(params):
    return {
        "id": "thread-1",
        "cliVersion": "0.147.0",
        "createdAt": 1,
        "updatedAt": 1,
        "cwd": params["cwd"],
        "ephemeral": True,
        "modelProvider": "openai",
        "parentThreadId": None,
        "preview": "",
        "sessionId": "session-1",
        "source": "appServer",
        "status": {"type": "idle"},
        "turns": [],
    }

for raw in sys.stdin:
    message = json.loads(raw)
    method = message.get("method")
    with TRANSCRIPT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"method": method, "params": message.get("params")}, ensure_ascii=False) + "\n")
    if method == "initialized":
        if SCENARIO["startup_notification"]:
            emit({
                "method": SCENARIO["startup_notification"],
                "params": {
                    "status": "connected",
                    "serverName": "reviewed-startup",
                    "installationId": "reviewed-startup",
                    "environmentId": None,
                },
            })
        continue
    if method == SCENARIO["hang_method"]:
        while True:
            time.sleep(1)
    request_id = message["id"]
    params = message.get("params") or {}
    if method == "initialize":
        emit({"id": request_id, "result": {"codexHome": os.environ["CODEX_HOME"]}})
    elif method == "account/login/start":
        emit({"id": request_id, "result": {"type": "chatgptAuthTokens"}})
    elif method == "account/read":
        emit({"id": request_id, "result": {"account": {"type": "chatgpt", "planType": SCENARIO["live_plan"]}, "requiresOpenaiAuth": True}})
    elif method == "model/list":
        pages = SCENARIO["model_pages"]
        if pages is None:
            values = SCENARIO["models"]
            next_cursor = None
        else:
            cursor = params.get("cursor")
            page_index = 0 if cursor is None else int(cursor.removeprefix("page-"))
            values = pages[page_index]
            next_cursor = f"page-{page_index + 1}" if page_index + 1 < len(pages) else None
        emit({"id": request_id, "result": {"data": [{"model": value} for value in values], "nextCursor": next_cursor}})
    elif method == "thread/start":
        thread_cwd = params["cwd"]
        thread = thread_value(params)
        result = {
            "approvalPolicy": params["approvalPolicy"],
            "approvalsReviewer": params["approvalsReviewer"],
            "cwd": params["cwd"],
            "instructionSources": [],
            "model": params["model"],
            "modelProvider": "openai",
            "reasoningEffort": "medium",
            "runtimeWorkspaceRoots": [],
            "sandbox": {"type": "readOnly", "networkAccess": False},
            "thread": thread,
        }
        mutation = SCENARIO["thread_mutation"]
        if mutation == "model":
            result["model"] = "gpt-5.3-codex"
        elif mutation == "instructions":
            result["instructionSources"] = ["/ambient/CLAUDE.md"]
        elif mutation == "workspace":
            result["runtimeWorkspaceRoots"] = ["/ambient/workspace"]
        elif mutation == "sandbox":
            result["sandbox"] = {"type": "workspaceWrite", "networkAccess": False, "writableRoots": []}
        emit({"method": "thread/started", "params": {"thread": thread}})
        if SCENARIO["mcp_startup_status"]:
            emit({
                "method": "mcpServer/startupStatus/updated",
                "params": {
                    "threadId": "thread-1",
                    "name": "codex_apps",
                    "status": SCENARIO["mcp_startup_status"],
                    "error": None,
                    "failureReason": None,
                },
            })
        if SCENARIO["deprecation_notice"]:
            emit({
                "method": "deprecationNotice",
                "params": {
                    "summary": "A reviewed runtime setting is deprecated.",
                    "details": "Use its current replacement.",
                },
            })
        emit({"id": request_id, "result": result})
    elif method == "turn/start":
        turn_id = "turn-1"
        emit({"id": request_id, "result": {"turn": {"id": turn_id, "items": [], "status": "inProgress"}}})
        thread_id = "wrong-thread" if SCENARIO["wrong_thread"] else "thread-1"
        event_turn_id = "wrong-turn" if SCENARIO["wrong_turn"] else turn_id
        emit({"method": "turn/started", "params": {"threadId": thread_id, "turn": {"id": event_turn_id, "items": [], "status": "inProgress"}}})
        if SCENARIO["turn_notification"]:
            emit({
                "method": SCENARIO["turn_notification"],
                "params": {"authMode": "chatgpt", "planType": SCENARIO["live_plan"]},
            })
        for telemetry_method in SCENARIO["turn_telemetry"]:
            if telemetry_method == "thread/settings/updated":
                settings = {
                    "approvalPolicy": "never",
                    "approvalsReviewer": "user",
                    "cwd": thread_cwd,
                    "effort": params["effort"],
                    "model": %r,
                    "modelProvider": "openai",
                    "sandboxPolicy": params["sandboxPolicy"],
                }
                mutation = SCENARIO["turn_settings_mutation"]
                if mutation == "model":
                    settings["model"] = "gpt-5.3-codex"
                elif mutation == "effort":
                    settings["effort"] = "low"
                elif mutation == "sandbox":
                    settings["sandboxPolicy"] = {"type": "workspaceWrite"}
                telemetry_params = {"threadId": thread_id, "threadSettings": settings}
            elif telemetry_method == "thread/status/changed":
                telemetry_params = {
                    "threadId": thread_id,
                    "status": {"type": "active", "activeFlags": []},
                }
            elif telemetry_method == "thread/tokenUsage/updated":
                telemetry_params = {
                    "threadId": thread_id,
                    "turnId": event_turn_id,
                    "tokenUsage": {},
                }
            elif telemetry_method == "item/reasoning/summaryPartAdded":
                telemetry_params = {
                    "threadId": thread_id,
                    "turnId": event_turn_id,
                    "itemId": "reasoning-1",
                    "summaryIndex": 0,
                }
            elif telemetry_method == "item/reasoning/summaryTextDelta":
                telemetry_params = {
                    "threadId": thread_id,
                    "turnId": event_turn_id,
                    "itemId": "reasoning-1",
                    "summaryIndex": 0,
                    "delta": "private reasoning summary",
                }
            elif telemetry_method == "item/reasoning/textDelta":
                telemetry_params = {
                    "threadId": thread_id,
                    "turnId": event_turn_id,
                    "itemId": "reasoning-1",
                    "contentIndex": 0,
                    "delta": "private reasoning text",
                }
            else:
                raise AssertionError(telemetry_method)
            emit({"method": telemetry_method, "params": telemetry_params})
        for control_method in SCENARIO["turn_control_events"]:
            control_thread_id = SCENARIO["control_thread_id"] or thread_id
            control_turn_id = SCENARIO["control_turn_id"] or event_turn_id
            if control_method == "turn/moderationMetadata":
                control_params = {
                    "threadId": control_thread_id,
                    "turnId": control_turn_id,
                    "metadata": {"classification": "reviewed-fixture"},
                }
            elif control_method == "model/safetyBuffering/updated":
                control_params = {
                    "threadId": control_thread_id,
                    "turnId": control_turn_id,
                    "model": SCENARIO["control_model"] or %r,
                    "reasons": ["reviewed-fixture"],
                    "showBufferingUi": True,
                    "useCases": ["translation"],
                    "fasterModel": None,
                }
            elif control_method == "model/verification":
                control_params = {
                    "threadId": control_thread_id,
                    "turnId": control_turn_id,
                    "verifications": SCENARIO["model_verifications"],
                }
            elif control_method == "thread/name/updated":
                control_params = {
                    "threadId": control_thread_id,
                    "threadName": "Content translation",
                }
            elif control_method == "model/rerouted":
                control_params = {
                    "threadId": control_thread_id,
                    "turnId": control_turn_id,
                    "fromModel": %r,
                    "toModel": "gpt-5.3-codex",
                    "reason": "highRiskCyberActivity",
                }
            elif control_method == "error":
                control_params = {
                    "threadId": control_thread_id,
                    "turnId": control_turn_id,
                    "willRetry": SCENARIO["error_will_retry"],
                    "error": {
                        "message": "raw provider detail must not escape",
                        "codexErrorInfo": SCENARIO["error_info"],
                    },
                }
            else:
                raise AssertionError(control_method)
            emit({"method": control_method, "params": control_params})
        if SCENARIO["server_request"]:
            emit({"id": 99, "method": "item/commandExecution/requestApproval", "params": {}})
        item_type = SCENARIO["item_type"]
        if item_type:
            emit({"method": "item/completed", "params": {"threadId": thread_id, "turnId": event_turn_id, "completedAtMs": 1, "item": {"id": "unsafe-1", "type": item_type}}})
        if SCENARIO["stdout_bloat"]:
            emit({"method": "item/completed", "params": {"threadId": thread_id, "turnId": event_turn_id, "completedAtMs": 1, "item": {"id": "reasoning-1", "type": "reasoning", "content": ["x" * SCENARIO["stdout_bloat"]]}}})
        if not SCENARIO["missing_final"]:
            count = 2 if SCENARIO["duplicate_final"] else 1
            for index in range(count):
                emit({"method": "item/completed", "params": {"threadId": thread_id, "turnId": event_turn_id, "completedAtMs": 1, "item": {"id": f"answer-{index}", "type": "agentMessage", "text": SCENARIO["output"]}}})
        turn = {"id": event_turn_id, "items": [], "status": SCENARIO["turn_status"], "error": SCENARIO["turn_error"]}
        emit({"method": "turn/completed", "params": {"threadId": thread_id, "turn": turn}})
    else:
        emit({"id": request_id, "error": {"code": -32601, "message": "unknown"}})
''' % (
        sys.executable,
        json.dumps(scenario, ensure_ascii=False),
        str(transcript),
        str(pid_path),
        _MODEL,
        _MODEL,
        _MODEL,
    )
    executable.write_text(source, encoding="utf-8")
    executable.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    return executable, transcript, pid_path


def _run(executable: Path, *, record=None, user="Revenue grew 12%."):
    from src.auth_drivers.codex_translation_adapter import run_codex_translation

    return run_codex_translation(
        credential_id="local:1",
        record=record or _record(),
        model=_MODEL,
        effort="medium",
        system="Translate the supplied content and emit only the requested object.",
        user=user,
        schema=_SCHEMA,
        timeout_s=2.0,
        executable=executable,
    )


def _methods(transcript: Path) -> list[str]:
    if not transcript.exists():
        return []
    return [json.loads(line)["method"] for line in transcript.read_text(encoding="utf-8").splitlines()]


def _wait_for_exit(pid_path: Path) -> None:
    assert pid_path.exists()
    pid = int(pid_path.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.02)
    pytest.fail(f"fixture app-server process {pid} remained alive")


def _assert_error(executable: Path, code: str, **kwargs) -> None:
    from src.auth_drivers.codex_translation_adapter import CodexTranslationError

    with pytest.raises(CodexTranslationError) as exc_info:
        _run(executable, **kwargs)
    assert exc_info.value.code == code


def test_reviewed_0147_contract_projection_matches_adapter_constants():
    from src.auth_drivers.codex_app_server_runtime import ALLOWED_CODEX_APP_SERVER_VERSIONS
    from src.auth_drivers.codex_translation_adapter import PROTOCOL_PROJECTION

    artifact = json.loads(
        (Path(__file__).parent / "fixtures/codex_translation/codex-app-server-0.147.0-contract.json").read_text(encoding="utf-8")
    )
    assert artifact["codex_cli_version"] in ALLOWED_CODEX_APP_SERVER_VERSIONS
    assert artifact["projection"] == PROTOCOL_PROJECTION


def test_translation_runs_one_exact_isolated_thread_and_turn(tmp_path):
    executable, transcript, pid_path = _write_fixture(tmp_path)

    result = _run(executable)

    assert result == {"translated_text": "營收成長 12%。"}
    rows = [json.loads(line) for line in transcript.read_text(encoding="utf-8").splitlines()]
    assert [row["method"] for row in rows] == [
        "initialize", "initialized", "account/login/start", "account/read",
        "model/list", "thread/start", "turn/start",
    ]
    thread = next(row["params"] for row in rows if row["method"] == "thread/start")
    assert thread["model"] == _MODEL
    assert thread["approvalPolicy"] == "never"
    assert thread["approvalsReviewer"] == "user"
    assert thread["sandbox"] == "read-only"
    assert thread["ephemeral"] is True
    assert thread["dynamicTools"] == []
    assert thread["environments"] == []
    assert thread["runtimeWorkspaceRoots"] == []
    assert thread["selectedCapabilityRoots"] == []
    assert thread["allowProviderModelFallback"] is False
    assert thread["config"] == {
        "agents.enabled": False,
        "features.apps": False,
        "features.auth_elicitation": False,
        "features.browser_use": False,
        "features.browser_use_external": False,
        "features.browser_use_full_cdp_access": False,
        "features.code_mode": False,
        "features.code_mode_host": False,
        "features.computer_use": False,
        "features.enable_mcp_apps": False,
        "features.hooks": False,
        "features.image_generation": False,
        "features.in_app_browser": False,
        "features.multi_agent": False,
        "features.multi_agent_v2": False,
        "features.plugin_sharing": False,
        "features.plugins": False,
        "features.remote_plugin": False,
        "features.shell_tool": False,
        "features.skill_mcp_dependency_install": False,
        "features.skill_search": False,
        "features.standalone_web_search": False,
        "features.tool_call_mcp_elicitation": False,
        "features.tool_suggest": False,
        "features.unified_exec": False,
        "features.view_image": False,
        "include_apps_instructions": False,
        "include_collaboration_mode_instructions": False,
        "include_environment_context": False,
        "include_permissions_instructions": False,
        "tools.experimental_request_user_input.enabled": False,
        "tools.update_plan.enabled": False,
        "web_search": "disabled",
    }
    cwd = Path(thread["cwd"])
    assert not cwd.exists()
    turn = next(row["params"] for row in rows if row["method"] == "turn/start")
    assert turn["threadId"] == "thread-1"
    assert turn["effort"] == "medium"
    assert turn["input"] == [{"type": "text", "text": "Revenue grew 12%."}]
    assert turn["outputSchema"] == _SCHEMA
    assert turn["sandboxPolicy"] == {"type": "readOnly", "networkAccess": False}
    _wait_for_exit(pid_path)


def test_mcp_startup_is_rejected_before_translation_turn(tmp_path):
    executable, transcript, pid_path = _write_fixture(
        tmp_path,
        mcp_startup_status="starting",
    )

    _assert_error(executable, "unexpected_tool_activity")

    assert "turn/start" not in _methods(transcript)
    _wait_for_exit(pid_path)


def test_deprecation_notice_is_rejected_before_translation_turn(tmp_path):
    executable, transcript, pid_path = _write_fixture(
        tmp_path,
        deprecation_notice=True,
    )

    _assert_error(executable, "protocol_incompatible")

    assert "turn/start" not in _methods(transcript)
    _wait_for_exit(pid_path)


@pytest.mark.parametrize(
    "notification",
    [
        "account/login/completed",
        "account/rateLimits/updated",
        "account/updated",
        "remoteControl/status/changed",
    ],
)
def test_reviewed_startup_notification_is_drained_before_translation_events(
    tmp_path, notification
):
    executable, transcript, pid_path = _write_fixture(
        tmp_path,
        startup_notification=notification,
    )

    result = _run(executable)

    assert result == {"translated_text": "營收成長 12%。"}
    assert "thread/start" in _methods(transcript)
    assert "turn/start" in _methods(transcript)
    _wait_for_exit(pid_path)


def test_reviewed_account_notification_is_drained_during_translation_turn(tmp_path):
    executable, transcript, pid_path = _write_fixture(
        tmp_path,
        turn_notification="account/updated",
    )

    result = _run(executable)

    assert result == {"translated_text": "營收成長 12%。"}
    assert "turn/start" in _methods(transcript)
    _wait_for_exit(pid_path)


@pytest.mark.parametrize(
    "notification",
    [
        "thread/settings/updated",
        "thread/status/changed",
        "thread/tokenUsage/updated",
        "item/reasoning/summaryPartAdded",
        "item/reasoning/summaryTextDelta",
        "item/reasoning/textDelta",
    ],
)
def test_reviewed_turn_telemetry_does_not_replace_translation_events(
    tmp_path, notification
):
    executable, transcript, pid_path = _write_fixture(
        tmp_path,
        turn_telemetry=[notification],
    )

    result = _run(executable)

    assert result == {"translated_text": "營收成長 12%。"}
    assert "turn/start" in _methods(transcript)
    _wait_for_exit(pid_path)


@pytest.mark.parametrize(
    "notification",
    [
        "turn/moderationMetadata",
        "model/safetyBuffering/updated",
        "model/verification",
        "thread/name/updated",
    ],
)
def test_reviewed_turn_control_telemetry_does_not_replace_translation_events(
    tmp_path, notification
):
    executable, transcript, pid_path = _write_fixture(
        tmp_path,
        turn_control_events=[notification],
    )

    result = _run(executable)

    assert result == {"translated_text": "營收成長 12%。"}
    assert "turn/start" in _methods(transcript)
    _wait_for_exit(pid_path)


@pytest.mark.parametrize(
    "notification",
    [
        "turn/moderationMetadata",
        "model/safetyBuffering/updated",
        "model/verification",
        "thread/name/updated",
        "model/rerouted",
        "error",
    ],
)
def test_turn_control_telemetry_must_match_the_active_thread(
    tmp_path, notification
):
    executable, _, pid_path = _write_fixture(
        tmp_path,
        turn_control_events=[notification],
        control_thread_id="other-thread",
    )

    _assert_error(executable, "protocol_incompatible")

    _wait_for_exit(pid_path)


@pytest.mark.parametrize(
    "notification",
    [
        "turn/moderationMetadata",
        "model/safetyBuffering/updated",
        "model/verification",
        "model/rerouted",
        "error",
    ],
)
def test_turn_control_telemetry_must_match_the_active_turn(
    tmp_path, notification
):
    executable, _, pid_path = _write_fixture(
        tmp_path,
        turn_control_events=[notification],
        control_turn_id="other-turn",
    )

    _assert_error(executable, "protocol_incompatible")

    _wait_for_exit(pid_path)


def test_safety_buffering_must_echo_the_exact_selected_model(tmp_path):
    executable, _, pid_path = _write_fixture(
        tmp_path,
        turn_control_events=["model/safetyBuffering/updated"],
        control_model="gpt-5.3-codex",
    )

    _assert_error(executable, "protocol_incompatible")

    _wait_for_exit(pid_path)


def test_nonempty_model_verification_never_becomes_translation_success(tmp_path):
    executable, _, pid_path = _write_fixture(
        tmp_path,
        turn_control_events=["model/verification"],
        model_verifications=["trustedAccessForCyber"],
    )

    _assert_error(executable, "model_unavailable")

    _wait_for_exit(pid_path)


def test_model_reroute_is_rejected_instead_of_accepting_fallback(tmp_path):
    executable, _, pid_path = _write_fixture(
        tmp_path,
        turn_control_events=["model/rerouted"],
    )

    _assert_error(executable, "model_unavailable")

    _wait_for_exit(pid_path)


@pytest.mark.parametrize("will_retry", [False, True])
def test_error_notification_maps_usage_limit_and_reaps_before_retry(
    tmp_path, will_retry
):
    executable, transcript, pid_path = _write_fixture(
        tmp_path,
        turn_control_events=["error"],
        error_info="usageLimitExceeded",
        error_will_retry=will_retry,
    )

    _assert_error(executable, "subscription_usage_unavailable")

    assert _methods(transcript).count("turn/start") == 1
    _wait_for_exit(pid_path)


@pytest.mark.parametrize(
    ("error_info", "expected_code"),
    [
        ("contextWindowExceeded", "context_window_exceeded"),
        ("unauthorized", "reauth_required"),
        ("serverOverloaded", "provider_call_failed"),
        ({"responseStreamDisconnected": {"httpStatusCode": 503}}, "provider_call_failed"),
    ],
)
def test_error_notification_uses_closed_codes_without_exposing_provider_text(
    tmp_path, error_info, expected_code
):
    from src.auth_drivers.codex_translation_adapter import CodexTranslationError

    executable, _, pid_path = _write_fixture(
        tmp_path,
        turn_control_events=["error"],
        error_info=error_info,
    )

    with pytest.raises(CodexTranslationError) as exc_info:
        _run(executable)
    assert exc_info.value.code == expected_code
    assert str(exc_info.value) == expected_code
    assert "raw provider detail" not in str(exc_info.value)
    _wait_for_exit(pid_path)


@pytest.mark.parametrize("mutation", ["model", "effort", "sandbox"])
def test_turn_settings_telemetry_must_echo_the_selected_execution_boundary(
    tmp_path, mutation
):
    executable, transcript, pid_path = _write_fixture(
        tmp_path,
        turn_telemetry=["thread/settings/updated"],
        turn_settings_mutation=mutation,
    )

    _assert_error(executable, "protocol_incompatible")

    assert "turn/start" in _methods(transcript)
    _wait_for_exit(pid_path)


def test_unreviewed_startup_notification_remains_fail_closed(tmp_path):
    executable, transcript, pid_path = _write_fixture(
        tmp_path,
        startup_notification="configWarning",
    )

    _assert_error(executable, "protocol_incompatible")

    assert "thread/start" not in _methods(transcript)
    assert "turn/start" not in _methods(transcript)
    _wait_for_exit(pid_path)


def test_translation_finds_the_exact_model_on_a_bounded_second_page(tmp_path):
    executable, transcript, pid_path = _write_fixture(
        tmp_path,
        model_pages=[["gpt-5.6-luna"], [_MODEL]],
    )

    result = _run(executable)

    assert result == {"translated_text": "營收成長 12%。"}
    rows = [json.loads(line) for line in transcript.read_text().splitlines()]
    model_requests = [row for row in rows if row["method"] == "model/list"]
    assert [row["params"]["cursor"] for row in model_requests] == [None, "page-1"]
    assert [row["method"] for row in rows].count("thread/start") == 1
    assert [row["method"] for row in rows].count("turn/start") == 1
    _wait_for_exit(pid_path)


@pytest.mark.parametrize("stored_plan", ["plus", "prolite", "team"])
def test_token_store_plan_name_is_diagnostic_not_admission(tmp_path, stored_plan):
    executable, transcript, pid_path = _write_fixture(tmp_path)

    result = _run(executable, record=_record(stored_plan))

    assert result == {"translated_text": "營收成長 12%。"}
    assert "model/list" in _methods(transcript)
    assert "thread/start" in _methods(transcript)
    _wait_for_exit(pid_path)


def test_unknown_stored_plan_reaches_account_read_and_uses_live_plan(tmp_path):
    executable, transcript, pid_path = _write_fixture(tmp_path, live_plan="pro")
    observed = []
    from src.auth_drivers.codex_translation_adapter import run_codex_translation

    result = run_codex_translation(
        credential_id="local:1",
        record=_record(None),
        model=_MODEL,
        effort="medium",
        system="Translate the supplied content and emit only the requested object.",
        user="Revenue grew 12%.",
        schema=_SCHEMA,
        timeout_s=2.0,
        executable=executable,
        plan_observer=observed.append,
    )

    assert result == {"translated_text": "營收成長 12%。"}
    assert observed == ["pro"]
    assert "account/read" in _methods(transcript)
    _wait_for_exit(pid_path)


def test_unknown_stored_plan_does_not_block_exact_live_entitlement(tmp_path):
    executable, transcript, pid_path = _write_fixture(tmp_path, live_plan="pro")

    result = _run(executable, record=_record(None))

    assert result == {"translated_text": "營收成長 12%。"}
    assert "model/list" in _methods(transcript)
    _wait_for_exit(pid_path)


@pytest.mark.parametrize("live_plan", ["pro", "prolite", "plus", "team"])
def test_live_account_plan_name_is_diagnostic_not_admission(tmp_path, live_plan):
    executable, transcript, pid_path = _write_fixture(tmp_path, live_plan=live_plan)

    result = _run(executable)

    assert result == {"translated_text": "營收成長 12%。"}
    assert "model/list" in _methods(transcript)
    assert "thread/start" in _methods(transcript)
    _wait_for_exit(pid_path)


@pytest.mark.parametrize("live_plan", [None, ""])
def test_missing_live_account_plan_does_not_override_exact_model_entitlement(
    tmp_path,
    live_plan,
):
    executable, transcript, pid_path = _write_fixture(tmp_path, live_plan=live_plan)

    result = _run(executable, record=_record(None))

    assert result == {"translated_text": "營收成長 12%。"}
    assert "model/list" in _methods(transcript)
    assert "thread/start" in _methods(transcript)
    _wait_for_exit(pid_path)


@pytest.mark.parametrize("live_plan", [7, "x" * 81])
def test_malformed_live_account_plan_remains_protocol_incompatible(
    tmp_path,
    live_plan,
):
    executable, transcript, pid_path = _write_fixture(tmp_path, live_plan=live_plan)

    _assert_error(executable, "protocol_incompatible", record=_record(None))

    assert "model/list" not in _methods(transcript)
    _wait_for_exit(pid_path)


def test_exact_spark_model_must_be_discovered_before_thread_start(tmp_path):
    executable, transcript, pid_path = _write_fixture(tmp_path, models=["gpt-5.3-codex"])

    _assert_error(executable, "model_unavailable")

    assert "thread/start" not in _methods(transcript)
    _wait_for_exit(pid_path)


@pytest.mark.parametrize("mutation", ["model", "instructions", "workspace", "sandbox"])
def test_thread_echo_mismatch_aborts_before_turn(tmp_path, mutation):
    executable, transcript, pid_path = _write_fixture(tmp_path, thread_mutation=mutation)

    _assert_error(executable, "protocol_incompatible")

    assert "thread/start" in _methods(transcript)
    assert "turn/start" not in _methods(transcript)
    _wait_for_exit(pid_path)


@pytest.mark.parametrize(
    "item_type",
    [
        "commandExecution", "fileChange", "mcpToolCall", "webSearch", "imageView",
        "imageGeneration", "dynamicToolCall", "collabAgentToolCall", "subAgentActivity",
    ],
)
def test_any_tool_or_external_activity_is_rejected(tmp_path, item_type):
    executable, _, pid_path = _write_fixture(tmp_path, item_type=item_type)

    _assert_error(executable, "unexpected_tool_activity")

    _wait_for_exit(pid_path)


def test_server_request_is_rejected_and_child_is_reaped(tmp_path):
    executable, _, pid_path = _write_fixture(tmp_path, server_request=True)
    _assert_error(executable, "protocol_incompatible")
    _wait_for_exit(pid_path)


@pytest.mark.parametrize("override", [{"wrong_thread": True}, {"wrong_turn": True}])
def test_notification_identity_mismatch_is_rejected(tmp_path, override):
    executable, _, pid_path = _write_fixture(tmp_path, **override)
    _assert_error(executable, "protocol_incompatible")
    _wait_for_exit(pid_path)


@pytest.mark.parametrize(
    ("override", "code"),
    [
        ({"duplicate_final": True}, "structured_output_invalid"),
        ({"missing_final": True}, "structured_output_missing"),
        ({"output": "```json\n{}\n```"}, "structured_output_invalid"),
        ({"output": "not json"}, "structured_output_invalid"),
        ({"output": '{"translated_text":"ok","extra":true}'}, "structured_output_invalid"),
    ],
)
def test_output_must_be_one_bare_schema_valid_object(tmp_path, override, code):
    executable, _, pid_path = _write_fixture(tmp_path, **override)
    _assert_error(executable, code)
    _wait_for_exit(pid_path)


def test_non_completed_turn_maps_context_limit_without_raw_message(tmp_path):
    executable, _, pid_path = _write_fixture(
        tmp_path,
        turn_status="failed",
        turn_error={
            "message": "raw provider detail must not escape",
            "codexErrorInfo": "contextWindowExceeded",
        },
    )
    _assert_error(executable, "context_window_exceeded")
    _wait_for_exit(pid_path)


def test_protocol_stdout_budget_is_enforced_and_child_is_reaped(tmp_path, monkeypatch):
    import src.auth_drivers.codex_translation_adapter as adapter

    executable, _, pid_path = _write_fixture(tmp_path, stdout_bloat=4096)
    monkeypatch.setattr(adapter, "_MAX_STDOUT_BYTES", 1024)
    _assert_error(executable, "protocol_resource_exhausted")
    _wait_for_exit(pid_path)


def test_timeout_reaps_hung_child(tmp_path):
    from src.auth_drivers.codex_translation_adapter import CodexTranslationError, run_codex_translation

    executable, _, pid_path = _write_fixture(tmp_path, hang_method="turn/start")
    with pytest.raises(CodexTranslationError) as exc_info:
        run_codex_translation(
            credential_id="local:1", record=_record(), model=_MODEL, effort="medium",
            system="Translate.", user="Revenue.", schema=_SCHEMA,
            timeout_s=0.2, executable=executable,
        )
    assert exc_info.value.code == "timeout"
    _wait_for_exit(pid_path)


def test_cancellation_during_validation_reaps_child(tmp_path, monkeypatch):
    import src.auth_drivers.codex_translation_adapter as adapter

    executable, _, pid_path = _write_fixture(tmp_path)

    def cancel(_payload, _schema):
        raise asyncio.CancelledError

    monkeypatch.setattr(adapter, "_validate_output", cancel)
    with pytest.raises(asyncio.CancelledError):
        _run(executable)
    _wait_for_exit(pid_path)


def test_large_translation_input_is_not_rejected_by_local_model_limit(tmp_path):
    executable, transcript, pid_path = _write_fixture(tmp_path)
    source = "x" * 600_000

    assert _run(executable, user=source)["translated_text"]

    row = next(
        json.loads(line)
        for line in transcript.read_text(encoding="utf-8").splitlines()
        if json.loads(line)["method"] == "turn/start"
    )
    assert row["params"]["input"][0]["text"] == source
    _wait_for_exit(pid_path)
