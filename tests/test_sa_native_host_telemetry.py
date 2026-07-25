from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest

import src.sa_native_host as host


_RUN_OUTCOMES = (
    Path(__file__).parent / "fixtures" / "sa_extension" / "run_outcomes.json"
)


def _extension_event(event_id: str) -> dict:
    fixture = json.loads(_RUN_OUTCOMES.read_text(encoding="utf-8"))
    result = next(
        entry["input"]
        for entry in fixture["protocol_cases"]
        if entry["name"] == "complete_market_sync"
    )
    return {
        "client_event_id": event_id,
        "started_at": "2026-07-25T01:00:00Z",
        "finished_at": "2026-07-25T01:00:30Z",
        "result": result,
    }


def test_import_has_no_script_side_effects(tmp_path):
    """Importing the host module must not chdir, mkdir, or configure logging.

    Tests and the health probe import this module at pytest collection time;
    its script-mode side effects created data/ in virgin environments and
    mutated whole-process cwd/root-logger state, changing OTHER tests'
    behavior (2026-07-06 full A/B diff in tests/test_agents.py).
    """
    repo_root = Path(__file__).resolve().parents[1]
    code = (
        "import os, logging\n"
        "start_cwd = os.getcwd()\n"
        "import src.sa_native_host\n"
        "assert os.getcwd() == start_cwd, 'import changed cwd'\n"
        "assert not logging.getLogger().handlers, 'import configured root logging'\n"
        "print('IMPORT_PURE')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(tmp_path),
        env={**os.environ, "PYTHONPATH": str(repo_root)},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    assert "IMPORT_PURE" in proc.stdout


_API_ENV_KEYS = [
    "ARKSCOPE_API_BASE_URL",
    "ARKSCOPE_API_HOST",
    "ARKSCOPE_API_PORT",
    "ARKSCOPE_API_TOKEN",
]


def _clear_api_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    for key in _API_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    cfg = tmp_path / "sa_native_host.json"
    monkeypatch.setenv("ARKSCOPE_SA_NATIVE_HOST_CONFIG", str(cfg))
    return cfg


def test_resolve_sidecar_target_defaults_to_8420(monkeypatch, tmp_path):
    _clear_api_env(monkeypatch, tmp_path)

    assert host._resolve_sidecar_target() == (
        "http://127.0.0.1:8420",
        None,
        "default",
    )


def test_resolve_sidecar_target_reads_config(monkeypatch, tmp_path):
    cfg = _clear_api_env(monkeypatch, tmp_path)
    cfg.write_text(
        json.dumps({"api_base": "http://127.0.0.1:45001", "api_token": "t1"}),
        encoding="utf-8",
    )

    assert host._resolve_sidecar_target() == (
        "http://127.0.0.1:45001",
        "t1",
        "config",
    )


def test_resolve_sidecar_target_env_wins_over_config(monkeypatch, tmp_path):
    cfg = _clear_api_env(monkeypatch, tmp_path)
    cfg.write_text(
        json.dumps({"api_base": "http://127.0.0.1:45001", "api_token": "t1"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("ARKSCOPE_API_PORT", "9999")

    assert host._resolve_sidecar_target() == (
        "http://127.0.0.1:9999",
        None,
        "env",
    )


def test_resolve_sidecar_target_malformed_config_falls_back(monkeypatch, tmp_path):
    cfg = _clear_api_env(monkeypatch, tmp_path)
    cfg.write_text("{not-json", encoding="utf-8")

    assert host._resolve_sidecar_target() == (
        "http://127.0.0.1:8420",
        None,
        "default",
    )


def test_post_extension_job_retries_default_after_config_refused(monkeypatch, tmp_path):
    cfg = _clear_api_env(monkeypatch, tmp_path)
    cfg.write_text(
        json.dumps({"api_base": "http://127.0.0.1:45001", "api_token": "t1"}),
        encoding="utf-8",
    )
    seen: list[str] = []

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"status":"ok","persisted":true}'

    def fake_urlopen(req, timeout):
        seen.append(req.full_url)
        if req.full_url.startswith("http://127.0.0.1:45001/"):
            raise urllib.error.URLError(ConnectionRefusedError("refused"))
        return _Resp()

    monkeypatch.setattr(host.urllib.request, "urlopen", fake_urlopen)

    assert host._post_extension_job_to_sidecar({"job_name": "x"}) == {
        "status": "ok",
        "persisted": True,
    }
    assert seen == [
        "http://127.0.0.1:45001/jobs/extension-record",
        "http://127.0.0.1:8420/jobs/extension-record",
    ]


@pytest.mark.parametrize(
    ("env_key", "env_value", "expected_url"),
    [
        ("ARKSCOPE_API_PORT", "9999", "http://127.0.0.1:9999/jobs/extension-record"),
        ("ARKSCOPE_API_BASE_URL", "http://127.0.0.1:9998", "http://127.0.0.1:9998/jobs/extension-record"),
    ],
)
def test_post_extension_job_does_not_retry_env_or_default_refused(
    monkeypatch,
    tmp_path,
    env_key,
    env_value,
    expected_url,
):
    _clear_api_env(monkeypatch, tmp_path)
    monkeypatch.setenv(env_key, env_value)
    seen: list[str] = []

    def fake_urlopen(req, timeout):
        seen.append(req.full_url)
        raise urllib.error.URLError(ConnectionRefusedError("refused"))

    monkeypatch.setattr(host.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(Exception):
        host._post_extension_job_to_sidecar({"job_name": "x"})
    assert seen == [expected_url]


def test_ping_reports_telemetry_target_without_token(monkeypatch, tmp_path):
    cfg = _clear_api_env(monkeypatch, tmp_path)
    cfg.write_text(
        json.dumps({"api_base": "http://127.0.0.1:45001", "api_token": "secret-token"}),
        encoding="utf-8",
    )

    result = host.handle_message({"action": "ping"})

    assert result["status"] == "ok"
    assert result["telemetry_target"] == "http://127.0.0.1:45001"
    assert result["telemetry_source"] == "config"
    assert "secret-token" not in json.dumps(result)


def test_ping_does_not_construct_dal(monkeypatch, tmp_path):
    _clear_api_env(monkeypatch, tmp_path)
    import src.tools.data_access as data_access

    def boom(*_args, **_kwargs):
        raise AssertionError("DAL should not be constructed for ping")

    monkeypatch.setattr(data_access, "DataAccessLayer", boom)

    result = host.handle_message({"action": "ping"})

    assert result["status"] == "ok"
    assert result["telemetry_target"] == "http://127.0.0.1:8420"
    assert result["telemetry_source"] == "default"


def test_native_host_rejects_extension_record_with_caller_status(monkeypatch):
    monkeypatch.setattr(
        host,
        "_post_extension_job_to_sidecar",
        lambda _payload: (_ for _ in ()).throw(
            AssertionError("caller-owned status must not reach the sidecar")
        ),
    )

    result = host._handle_record_extension_job(
        None,
        {**_extension_event("evt-caller-status"), "status": "succeeded"},
    )

    assert result == {
        "status": "error",
        "persisted": False,
        "run_id": None,
        "error_code": "caller_status_forbidden",
    }


def test_native_host_projects_numeric_action_limits_without_faking_defaults(
    monkeypatch,
):
    config = SimpleNamespace(
        sa_comments_backfill_per_full_scan=17,
        sa_comments_backfill_per_backfill_scan="not-a-number",
    )
    monkeypatch.setattr("src.agents.config.get_agent_config", lambda: config)

    result = host.handle_message({"action": "get_extension_action_limits"})

    assert result == {
        "status": "ok",
        "limits": {
            "alpha_picks_full_comment_recovery_batch": 17,
            "alpha_picks_deep_comment_recovery_batch": None,
        },
    }


def test_native_host_routes_recovery_actions_only_to_fixed_sidecar_paths(
    monkeypatch,
):
    calls: list[tuple[str, dict]] = []

    def fake_post(path, payload):
        calls.append((path, payload))
        return {"status": "ok", "path_seen": path}

    monkeypatch.setattr(host, "_post_recovery_action_to_sidecar", fake_post)

    preview = host.handle_message(
        {
            "action": "market_news_recovery_preview",
            "path": "/attacker-controlled",
            "kind": "recorded",
        }
    )
    cancel = host.handle_message(
        {
            "action": "market_news_recovery_cancel",
            "path": "/attacker-controlled",
            "run_id": 41,
        }
    )

    assert preview["path_seen"] == "/sa/market-news-recovery/preview"
    assert cancel["path_seen"] == "/sa/market-news-recovery/cancel"
    assert calls == [
        (
            "/sa/market-news-recovery/preview",
            {"kind": "recorded"},
        ),
        (
            "/sa/market-news-recovery/cancel",
            {"run_id": 41},
        ),
    ]


def test_native_host_returns_typed_sidecar_rejection_without_raw_detail(
    monkeypatch,
):
    monkeypatch.setattr(
        host,
        "_post_extension_job_to_sidecar",
        lambda _payload: {
            "status": "error",
            "persisted": False,
            "run_id": None,
            "error_code": "event_conflict",
            "detail": "/home/user/private.db sqlite3 traceback",
        },
    )

    result = host._handle_record_extension_job(None, _extension_event("evt-rejected"))

    assert result == {
        "status": "error",
        "persisted": False,
        "run_id": None,
        "error_code": "event_conflict",
    }
    assert "private.db" not in json.dumps(result)
