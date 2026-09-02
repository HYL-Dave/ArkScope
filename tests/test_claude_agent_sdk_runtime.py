from __future__ import annotations

import asyncio
from pathlib import Path

import pytest


def _clear_runtime_cache(mod) -> None:
    mod.require_reviewed_claude_agent_runtime.cache_clear()


def test_reviewed_claude_runtime_matches_requirement_and_installed_bundle():
    from src.auth_drivers import claude_agent_sdk_runtime as mod

    _clear_runtime_cache(mod)
    runtime = mod.require_reviewed_claude_agent_runtime()

    requirement = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text()
    assert f"claude-agent-sdk=={mod.REVIEWED_CLAUDE_AGENT_SDK_VERSION}" in requirement
    assert runtime.sdk_version == mod.REVIEWED_CLAUDE_AGENT_SDK_VERSION
    assert runtime.sdk_module_version == mod.REVIEWED_CLAUDE_AGENT_SDK_VERSION
    assert runtime.cli_metadata_version == mod.REVIEWED_CLAUDE_CLI_VERSION
    assert runtime.cli_binary_version == mod.REVIEWED_CLAUDE_CLI_VERSION
    assert runtime.cli_path.is_file()
    assert runtime.cli_path.parent.name == "_bundled"


@pytest.mark.parametrize(
    ("seam", "value"),
    (
        ("_distribution_version", "0.2.152"),
        ("_sdk_module_version", "0.2.152"),
        ("_cli_metadata_version", "2.1.259"),
        ("_probe_cli_version", "2.1.259"),
    ),
)
def test_reviewed_claude_runtime_rejects_each_version_drift(
    monkeypatch, seam, value
):
    from src.auth_drivers import claude_agent_sdk_runtime as mod

    if seam == "_probe_cli_version":
        monkeypatch.setattr(mod, seam, lambda _path: value)
    else:
        monkeypatch.setattr(mod, seam, lambda: value)
    _clear_runtime_cache(mod)

    with pytest.raises(mod.ClaudeAgentSdkRuntimeIncompatible, match="not reviewed"):
        mod.require_reviewed_claude_agent_runtime()

    _clear_runtime_cache(mod)


def test_reviewed_claude_runtime_rejects_missing_bundled_binary(
    tmp_path, monkeypatch
):
    from src.auth_drivers import claude_agent_sdk_runtime as mod

    monkeypatch.setattr(mod, "_bundled_cli_path", lambda: tmp_path / "missing-claude")
    _clear_runtime_cache(mod)

    with pytest.raises(
        mod.ClaudeAgentSdkRuntimeIncompatible, match="bundled Claude Code CLI"
    ):
        mod.require_reviewed_claude_agent_runtime()

    _clear_runtime_cache(mod)


def test_claude_child_environment_blanks_every_unapproved_parent_value():
    from src.auth_drivers import claude_agent_sdk_runtime as mod

    child = mod.build_claude_child_environment(
        token="setup-token",
        config_dir="/tmp/isolated-claude",
        source={
            "HOME": "/tmp/home",
            "PATH": "/usr/bin",
            "LANG": "C.UTF-8",
            "OPENAI_API_KEY": "must-not-cross",
            "AWS_SECRET_ACCESS_KEY": "must-not-cross",
            "CLAUDE_CODE_OAUTH_TOKEN": "ambient-token",
            "ANTHROPIC_API_KEY": "ambient-key",
            "CLAUDE_CONFIG_DIR": "/tmp/ambient-claude",
        },
    )

    assert child["HOME"] == "/tmp/home"
    assert child["PATH"] == "/usr/bin"
    assert child["LANG"] == "C.UTF-8"
    assert child["OPENAI_API_KEY"] == ""
    assert child["AWS_SECRET_ACCESS_KEY"] == ""
    assert child["ANTHROPIC_API_KEY"] == ""
    assert child["CLAUDE_CODE_ENTRYPOINT"] == "sdk-py"
    assert child["TRACEPARENT"] == ""
    assert child["TRACESTATE"] == ""
    assert child["BAGGAGE"] == ""
    assert child["CLAUDE_CODE_OAUTH_TOKEN"] == "setup-token"
    assert child["CLAUDE_CONFIG_DIR"] == "/tmp/isolated-claude"
    assert "must-not-cross" not in child.values()
    assert "ambient-token" not in child.values()


def test_installed_sdk_transport_receives_the_closed_child_environment(monkeypatch):
    from claude_agent_sdk import ClaudeAgentOptions
    from claude_agent_sdk._internal.transport import subprocess_cli
    from src.auth_drivers import claude_agent_sdk_runtime as mod

    monkeypatch.setenv("OPENAI_API_KEY", "must-not-cross")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "must-not-cross")
    captured = {}

    class Process:
        stdin = None
        stdout = None
        stderr = None

    async def fake_open_process(*command, **kwargs):
        captured.update(command=command, **kwargs)
        return Process()

    async def skip_duplicate_version_probe():
        return None

    monkeypatch.setattr(subprocess_cli.anyio, "open_process", fake_open_process)
    options = ClaudeAgentOptions(
        cli_path=str(mod.require_reviewed_claude_agent_runtime().cli_path),
        cwd="/tmp",
        env=mod.build_claude_child_environment(
            token="setup-token",
            config_dir="/tmp/isolated-claude",
        ),
    )
    transport = subprocess_cli.SubprocessCLITransport(prompt="probe", options=options)
    monkeypatch.setattr(transport, "_check_claude_version", skip_duplicate_version_probe)

    asyncio.run(transport.connect())

    process_env = captured["env"]
    assert process_env["HOME"] == options.env["HOME"]
    assert process_env["OPENAI_API_KEY"] == ""
    assert process_env["AWS_SECRET_ACCESS_KEY"] == ""
    assert process_env["ANTHROPIC_API_KEY"] == ""
    assert process_env["CLAUDE_CODE_OAUTH_TOKEN"] == "setup-token"
    assert process_env["CLAUDE_CODE_ENTRYPOINT"] == "sdk-py"
    assert process_env["TRACEPARENT"] == ""
    assert process_env["TRACESTATE"] == ""
    assert process_env["BAGGAGE"] == ""


def test_current_runtime_admission_and_publication_boundary_are_documented():
    root = Path(__file__).resolve().parents[1]
    admission = (
        root / "docs/design/CLAUDE_AGENT_SDK_RUNTIME_ADMISSION.md"
    ).read_text()
    priority_map = (root / "docs/design/PROJECT_PRIORITY_MAP.md").read_text()

    assert "claude-agent-sdk==0.2.151" in admission
    assert "Claude Code CLI 2.1.258" in admission
    assert "apiKeySource == \"none\"" in admission
    assert "PreToolUse" in admission and "not part of the shipped path" in admission
    assert "operator-local self-use" in admission
    assert "does not constitute an OS sandbox" in admission
    assert "operator-local self-use" in priority_map
