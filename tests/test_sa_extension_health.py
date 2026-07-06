from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

from src.sa_capture_store import connect


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _make_paths(tmp_path: Path, *, api_base: str = "http://127.0.0.1:45678", api_token: str = "token-1"):
    from src.service.sa_extension_health import SAExtensionHealthPaths

    project_root = tmp_path / "repo"
    host_script = project_root / "src" / "sa_native_host.py"
    host_script.parent.mkdir(parents=True)
    host_script.write_text("# host\n", encoding="utf-8")
    launcher = tmp_path / "native-hosts" / "sa_alpha_picks_host.sh"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("#!/bin/sh\n", encoding="utf-8")
    launcher.chmod(0o755)
    firefox_manifest = tmp_path / "firefox" / "com.mindfulrl.sa_alpha_picks.json"
    chrome_manifest = tmp_path / "chrome" / "com.mindfulrl.sa_alpha_picks.json"
    _write_json(firefox_manifest, {"name": "com.mindfulrl.sa_alpha_picks", "path": str(launcher)})
    _write_json(chrome_manifest, {"name": "com.mindfulrl.sa_alpha_picks", "path": str(launcher)})
    config_path = tmp_path / "config" / "sa_native_host.json"
    _write_json(
        config_path,
        {
            "project_root": str(project_root),
            "python_path": sys.executable,
            "host_script": str(host_script),
            "api_base": api_base,
            "api_token": api_token,
        },
    )
    return SAExtensionHealthPaths(
        project_root=project_root,
        config_path=config_path,
        firefox_manifest_path=firefox_manifest,
        chrome_manifest_path=chrome_manifest,
        launcher_path=launcher,
        sa_db_path=tmp_path / "sa_capture.db",
        host_script=host_script,
    )


class _FakeJobStore:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def list_runs(self, **kwargs):
        self.calls.append(kwargs)
        rows = self.rows
        trigger = kwargs.get("trigger_source")
        if trigger:
            rows = [row for row in rows if row.get("trigger_source") == trigger]
        return rows[: kwargs.get("limit", len(rows))]


def _segment(report: dict, key: str) -> dict:
    return {segment["key"]: segment for segment in report["segments"]}[key]


def test_health_reports_all_segments_and_latest_extension_slug_row(tmp_path):
    from src.service.sa_extension_health import collect_sa_extension_health

    paths = _make_paths(tmp_path)
    rows = [
        {
            "job_name": "sa_market_news_refresh",
            "status": "succeeded",
            "trigger_source": "extension",
            "finished_at": "2026-07-05T16:05:00+00:00",
        },
        {
            "job_name": "sa_extension:alpha_picks_quick",
            "status": "succeeded",
            "trigger_source": "extension",
            "finished_at": "2026-07-06T02:12:00+00:00",
        },
        {
            "job_name": "collect.polygon_news",
            "status": "succeeded",
            "trigger_source": "api",
            "finished_at": "2026-07-06T03:00:00+00:00",
        },
    ]
    store = _FakeJobStore(rows)
    with connect(str(paths.sa_db_path)) as conn:
        conn.execute(
            """
            INSERT INTO sa_refresh_meta(scope,last_success_at,row_count,ok,updated_at)
            VALUES ('current','2026-07-06T02:07:56+00:00',50,1,'2026-07-06T02:07:56+00:00')
            """
        )
        conn.execute(
            """
            INSERT INTO sa_articles(article_id,url,title,fetched_at,updated_at)
            VALUES ('a1','https://example.test/a1','Article','2026-07-06T02:12:49+00:00','2026-07-06T02:12:49+00:00')
            """
        )

    report = collect_sa_extension_health(
        paths=paths,
        env={
            "ARKSCOPE_API_HOST": "127.0.0.1",
            "ARKSCOPE_API_PORT": "45678",
            "ARKSCOPE_API_TOKEN": "token-1",
        },
        job_store=store,
        spawn_ping=lambda _paths: {
            "status": "ok",
            "telemetry_target": "http://127.0.0.1:45678",
            "telemetry_source": "config",
        },
    )

    assert [segment["key"] for segment in report["segments"]] == [
        "config",
        "manifests",
        "launcher",
        "host_ping",
        "telemetry_binding",
        "telemetry_last",
        "capture_readback",
    ]
    assert report["ok"] is True
    assert _segment(report, "telemetry_last")["state"] == "ok"
    assert "sa_extension:alpha_picks_quick" in _segment(report, "telemetry_last")["detail"]
    assert _segment(report, "capture_readback")["state"] == "ok"
    assert store.calls and store.calls[0]["trigger_source"] == "extension"


def test_fresh_install_has_warn_for_missing_history_not_fail(tmp_path):
    from src.service.sa_extension_health import collect_sa_extension_health

    paths = _make_paths(tmp_path)

    report = collect_sa_extension_health(
        paths=paths,
        env={
            "ARKSCOPE_API_HOST": "127.0.0.1",
            "ARKSCOPE_API_PORT": "45678",
            "ARKSCOPE_API_TOKEN": "token-1",
        },
        job_store=_FakeJobStore([]),
        spawn_ping=lambda _paths: {
            "status": "ok",
            "telemetry_target": "http://127.0.0.1:45678",
            "telemetry_source": "config",
        },
    )

    assert report["ok"] is True
    assert _segment(report, "telemetry_last")["state"] == "warn"
    assert _segment(report, "capture_readback")["state"] == "warn"


def test_config_failure_does_not_hide_other_segments(tmp_path):
    from src.service.sa_extension_health import collect_sa_extension_health

    paths = _make_paths(tmp_path)
    paths.config_path.write_text("{bad-json", encoding="utf-8")

    report = collect_sa_extension_health(
        paths=paths,
        env={},
        job_store=_FakeJobStore([]),
        spawn_ping=lambda _paths: {"status": "ok", "telemetry_target": "http://127.0.0.1:8420"},
    )

    assert report["ok"] is False
    assert _segment(report, "config")["state"] == "fail"
    assert _segment(report, "host_ping")["state"] == "ok"
    assert _segment(report, "telemetry_last")["state"] == "warn"


def test_run_host_ping_uses_real_native_host_protocol(tmp_path, monkeypatch):
    from src.service.sa_extension_health import SAExtensionHealthPaths, run_host_ping

    config = tmp_path / "sa_native_host.json"
    _write_json(config, {"api_base": "http://127.0.0.1:45678", "api_token": "secret-token"})
    monkeypatch.setenv("ARKSCOPE_SA_NATIVE_HOST_CONFIG", str(config))

    project_root = Path(__file__).resolve().parents[1]
    paths = SAExtensionHealthPaths(
        project_root=project_root,
        config_path=config,
        firefox_manifest_path=tmp_path / "missing-firefox.json",
        chrome_manifest_path=tmp_path / "missing-chrome.json",
        launcher_path=tmp_path / "missing-launcher.sh",
        sa_db_path=tmp_path / "sa_capture.db",
        host_script=project_root / "src" / "sa_native_host.py",
    )

    reply = run_host_ping(paths, timeout_seconds=15)

    assert reply["status"] == "ok"
    assert reply["telemetry_target"] == "http://127.0.0.1:45678"
    assert "secret-token" not in json.dumps(reply)


def test_run_host_ping_simulates_browser_env_not_sidecar_env(tmp_path, monkeypatch):
    """The probe must report what a BROWSER-spawned host would resolve.

    Inside dev:desktop the sidecar's own env carries the Electron-injected
    ARKSCOPE_API_HOST/PORT/TOKEN; passing them through to the probed host
    makes it report source=env, which a real browser-spawned host never
    sees. The probe strips them so the panel shows the browser reality.
    """
    from src.service.sa_extension_health import SAExtensionHealthPaths, run_host_ping

    config = tmp_path / "sa_native_host.json"
    _write_json(config, {"api_base": "http://127.0.0.1:45678", "api_token": "secret-token"})
    monkeypatch.setenv("ARKSCOPE_SA_NATIVE_HOST_CONFIG", str(config))
    monkeypatch.setenv("ARKSCOPE_API_HOST", "127.0.0.1")
    monkeypatch.setenv("ARKSCOPE_API_PORT", "9999")
    monkeypatch.setenv("ARKSCOPE_API_TOKEN", "sidecar-run-token")

    project_root = Path(__file__).resolve().parents[1]
    paths = SAExtensionHealthPaths(
        project_root=project_root,
        config_path=config,
        firefox_manifest_path=tmp_path / "missing-firefox.json",
        chrome_manifest_path=tmp_path / "missing-chrome.json",
        launcher_path=tmp_path / "missing-launcher.sh",
        sa_db_path=tmp_path / "sa_capture.db",
        host_script=project_root / "src" / "sa_native_host.py",
    )

    reply = run_host_ping(paths, timeout_seconds=15)

    assert reply["status"] == "ok"
    assert reply["telemetry_source"] == "config"
    assert reply["telemetry_target"] == "http://127.0.0.1:45678"
    assert "sidecar-run-token" not in json.dumps(reply)


def test_sa_extension_health_route_returns_service_payload(monkeypatch):
    from src.api.routes import seeking_alpha

    payload = {"ok": True, "segments": [{"key": "config", "state": "ok", "detail": "ok"}]}
    monkeypatch.setattr(
        seeking_alpha,
        "collect_sa_extension_health",
        lambda *, dal: payload,
    )

    assert seeking_alpha.sa_extension_health(dal=object()) == payload


def test_sa_extension_health_route_raises_structured_503(monkeypatch):
    from fastapi import HTTPException
    from src.api.routes import seeking_alpha

    def boom(*, dal):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(seeking_alpha, "collect_sa_extension_health", boom)

    with pytest.raises(HTTPException) as exc:
        seeking_alpha.sa_extension_health(dal=object())

    assert exc.value.status_code == 503
    assert exc.value.detail["code"] == "sa_extension_health_unavailable"
