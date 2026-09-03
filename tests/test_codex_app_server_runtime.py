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
