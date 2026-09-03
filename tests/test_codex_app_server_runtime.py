from __future__ import annotations

import json

from tests.test_subscription_account_usage import (
    _token_record,
    _write_codex_fixture,
)


def test_default_runtime_is_inside_codex_bundle_and_never_uses_path(
    tmp_path, monkeypatch,
):
    from codex_cli_bin import bundled_codex_path

    from src.auth_drivers.codex_app_server_runtime import (
        resolve_codex_app_server_runtime,
    )

    external = tmp_path / "codex"
    external.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
    external.chmod(0o700)
    monkeypatch.setenv("PATH", str(tmp_path))

    runtime = resolve_codex_app_server_runtime()

    assert runtime.launcher == bundled_codex_path()
    assert runtime.target == bundled_codex_path().resolve()
    assert runtime.launcher != external


def test_authenticated_runtime_child_environment_excludes_parent_secrets(
    tmp_path, monkeypatch,
):
    from src.auth_drivers.codex_app_server_runtime import (
        run_authenticated_codex_operation,
    )

    monkeypatch.setenv("OPENAI_API_KEY", "openai-secret-sentinel")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-secret-sentinel")
    executable, transcript, _ = _write_codex_fixture(tmp_path)

    context, models = run_authenticated_codex_operation(
        record=_token_record(),
        client_name="runtime-test",
        timeout_seconds=2.0,
        executable=executable,
        allowed_notifications=frozenset(),
        operation=lambda session, _context: session.request(
            4,
            "model/list",
            {"cursor": None, "includeHidden": False, "limit": 1},
        ),
    )

    first = json.loads(transcript.read_text(encoding="utf-8").splitlines()[0])
    assert context.account_id == "acct_fixture_raw_identifier"
    assert models["data"][0]["model"] == "gpt-5.3-codex-spark"
    assert "OPENAI_API_KEY" not in first["environment_keys"]
    assert "ANTHROPIC_API_KEY" not in first["environment_keys"]


def test_authenticated_runtime_launches_app_server_with_closed_tool_surface(tmp_path):
    from src.auth_drivers.codex_app_server_runtime import (
        run_authenticated_codex_operation,
    )

    executable, transcript, _ = _write_codex_fixture(tmp_path)

    run_authenticated_codex_operation(
        record=_token_record(),
        client_name="runtime-test",
        timeout_seconds=2.0,
        executable=executable,
        allowed_notifications=frozenset(),
        operation=lambda session, _context: session.request(
            4,
            "model/list",
            {"cursor": None, "includeHidden": False, "limit": 1},
        ),
    )

    first = json.loads(transcript.read_text(encoding="utf-8").splitlines()[0])
    argv = first["argv"]
    assert argv[-3:] == ["app-server", "--strict-config", "--stdio"]
    pairs = argv[:-3]
    assert pairs[::2] == ["-c"] * (len(pairs) // 2)
    assert set(pairs[1::2]) == {
        "agents.enabled=false",
        "features.apps=false",
        "features.auth_elicitation=false",
        "features.browser_use=false",
        "features.browser_use_external=false",
        "features.browser_use_full_cdp_access=false",
        "features.code_mode=false",
        "features.code_mode_host=false",
        "features.computer_use=false",
        "features.enable_mcp_apps=false",
        "features.hooks=false",
        "features.image_generation=false",
        "features.in_app_browser=false",
        "features.multi_agent=false",
        "features.multi_agent_v2=false",
        "features.plugin_sharing=false",
        "features.plugins=false",
        "features.remote_plugin=false",
        "features.shell_tool=false",
        "features.skill_mcp_dependency_install=false",
        "features.skill_search=false",
        "features.standalone_web_search=false",
        "features.tool_call_mcp_elicitation=false",
        "features.tool_suggest=false",
        "features.unified_exec=false",
        "features.view_image=false",
        "include_apps_instructions=false",
        "include_collaboration_mode_instructions=false",
        "include_environment_context=false",
        "include_permissions_instructions=false",
        "tools.experimental_request_user_input.enabled=false",
        "tools.update_plan.enabled=false",
        'web_search="disabled"',
    }
