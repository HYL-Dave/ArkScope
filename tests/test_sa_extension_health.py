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
    def __init__(self, rows, *, summary=None, completed=None):
        self.rows = rows
        self.summary = {} if summary is None else summary
        self.completed = [] if completed is None else completed
        self.calls = []
        self.summary_calls = []
        self.completed_calls = []

    def list_runs(self, **kwargs):
        self.calls.append(kwargs)
        rows = self.rows
        job_name = kwargs.get("job_name")
        if job_name:
            rows = [row for row in rows if row.get("job_name") == job_name]
        trigger = kwargs.get("trigger_source")
        if trigger:
            rows = [row for row in rows if row.get("trigger_source") == trigger]
        return rows[: kwargs.get("limit", len(rows))]

    def structured_extension_summary_by_name(self, job_names):
        self.summary_calls.append(job_names)
        return self.summary

    def completed_extension_runs_by_name(self, job_names=None):
        self.completed_calls.append(job_names)
        return self.completed


def _structured_row(
    *,
    run_id: int,
    job_name: str,
    outcome: str,
    finished_at: str,
    counts: dict | None = None,
    status: str | None = None,
    healthy: bool | None = None,
    started_at: str | None = None,
    diagnostics: dict | None = None,
) -> dict:
    payload = {
        "extension_event": {
            "client_event_id": f"event-{run_id}",
            "event_hash": str(run_id).zfill(64),
        }
    }
    if diagnostics is not None:
        payload["extension_diagnostics"] = diagnostics
    return {
        "id": run_id,
        "job_name": job_name,
        "status": status or ("succeeded" if outcome == "complete" else "failed"),
        "trigger_source": "extension",
        "started_at": started_at or finished_at,
        "finished_at": finished_at,
        "payload": payload,
        "result": {
            "schema_version": 1,
            "derived_outcome": outcome,
            "healthy_anchor_eligible": outcome == "complete"
            if healthy is None
            else healthy,
            "counts": counts or {},
        },
    }


def _segment(report: dict, key: str) -> dict:
    return {segment["key"]: segment for segment in report["segments"]}[key]


def _diagnostic_entry(
    *,
    occurred_at: str,
    stage: str = "page_readiness",
    reason_code: str = "detail_timeout",
    target_kind: str = "article_detail",
    target_ref: str = "opaque-1",
) -> dict:
    return {
        "occurred_at": occurred_at,
        "stage": stage,
        "reason_code": reason_code,
        "target_kind": target_kind,
        "target_ref": target_ref,
        "retryable": True,
        "attempt_count": 1,
    }


def _recorded_diagnostics(*entries: dict, omitted_count: int = 0) -> dict:
    return {
        "status": "recorded",
        "schema_version": 1,
        "entries": list(entries),
        "omitted_count": omitted_count,
    }


def _structural_segments(state: str = "ok") -> list[dict]:
    return [
        {"key": key, "state": state}
        for key in (
            "config",
            "manifests",
            "launcher",
            "host_ping",
            "telemetry_binding",
            "capture_readback",
        )
    ]


def test_each_structural_failure_independently_interrupts_chain():
    from src.service.sa_extension_health import _derive_chain_state

    for failed_key in [segment["key"] for segment in _structural_segments()]:
        segments = [dict(segment) for segment in _structural_segments()]
        next(segment for segment in segments if segment["key"] == failed_key)[
            "state"
        ] = "fail"
        assert _derive_chain_state(segments) == "interrupted"


def test_structural_warning_degrades_chain_without_interrupting_it():
    from src.service.sa_extension_health import _derive_chain_state

    segments = _structural_segments()
    segments[3]["state"] = "warn"

    assert _derive_chain_state(segments) == "degraded"


def test_capture_and_repair_failures_never_change_chain_state():
    from src.service.sa_extension_health import _derive_chain_state

    segments = _structural_segments() + [
        {"key": "telemetry_last", "state": "fail"},
        {"key": "market_news_repair", "state": "fail"},
    ]

    assert _derive_chain_state(segments) == "available"


def test_latest_capture_projects_allowlisted_workload_and_diagnostics():
    from src.service.sa_extension_health import _telemetry_last_segment

    row = _structured_row(
        run_id=81,
        job_name="sa_alpha_picks_refresh",
        outcome="degraded",
        started_at="2026-08-14T01:00:00+00:00",
        finished_at="2026-08-14T01:01:00+00:00",
        counts={"item_total": 2, "failed_retryable": 1},
        diagnostics=_recorded_diagnostics(
            _diagnostic_entry(
                occurred_at="2026-08-14T01:00:40+00:00",
                target_ref="opaque-2",
            ),
            _diagnostic_entry(
                occurred_at="2026-08-14T01:00:20+00:00",
                stage="local_persistence",
                reason_code="database_write_failed",
            ),
            omitted_count=3,
        ),
    )
    store = _FakeJobStore(
        [],
        summary={
            "sa_alpha_picks_refresh": {
                "latest_attempt": row,
                "latest_derived_complete": None,
            }
        },
        completed=[row],
    )

    segment = _telemetry_last_segment(store)

    assert segment["state"] == "warn"
    assert segment["code"] == "capture_degraded"
    assert segment["job_name"] == "sa_alpha_picks_refresh"
    assert segment["outcome"] == "degraded"
    assert segment["diagnostics_status"] == "recorded"
    assert segment["diagnostics_error_code"] is None
    assert segment["diagnostics_omitted_count"] == 3
    assert [entry["occurred_at"] for entry in segment["diagnostics"]] == [
        "2026-08-14T01:00:20.000+00:00",
        "2026-08-14T01:00:40.000+00:00",
    ]
    assert {entry["stage"] for entry in segment["diagnostics"]} == {
        "page_readiness",
        "local_persistence",
    }


def test_legacy_failed_capture_reports_cause_absent_without_inference():
    from src.service.sa_extension_health import _telemetry_last_segment

    row = _structured_row(
        run_id=82,
        job_name="sa_market_news_refresh",
        outcome="failed",
        finished_at="2026-08-14T02:00:00+00:00",
    )
    store = _FakeJobStore(
        [],
        summary={"sa_market_news_refresh": {"latest_attempt": row}},
        completed=[row],
    )

    segment = _telemetry_last_segment(store)

    assert segment["state"] == "fail"
    assert segment["code"] == "capture_failed"
    assert segment["job_name"] == "sa_market_news_refresh"
    assert segment["diagnostics_status"] == "absent"
    assert segment["diagnostics_error_code"] is None
    assert "diagnostics" not in segment
    assert "reason_code" not in segment


def test_diagnostic_recurrence_is_bounded_to_latest_twenty_allowlisted_completed_runs():
    from src.service.sa_extension_health import _telemetry_last_segment

    rows = []
    for day in range(25, 0, -1):
        occurred = f"2026-07-{day:02d}T01:00:10+00:00"
        rows.append(
            _structured_row(
                run_id=100 + day,
                job_name="sa_market_news_refresh",
                outcome="degraded",
                started_at=f"2026-07-{day:02d}T01:00:00+00:00",
                finished_at=f"2026-07-{day:02d}T01:00:30+00:00",
                diagnostics=_recorded_diagnostics(
                    _diagnostic_entry(occurred_at=occurred)
                ),
            )
        )
    latest = rows[0]
    store = _FakeJobStore(
        [],
        summary={"sa_market_news_refresh": {"latest_attempt": latest}},
        completed=rows,
    )

    recurrence = _telemetry_last_segment(store)["diagnostic_recurrence"]

    assert recurrence == [
        {
            "job_name": "sa_market_news_refresh",
            "stage": "page_readiness",
            "reason_code": "detail_timeout",
            "affected_run_count": 20,
            "latest_occurred_at": "2026-07-25T01:00:10.000+00:00",
        }
    ]
    assert store.completed_calls == [
        ["sa_alpha_picks_refresh", "sa_market_news_refresh"]
    ]


def test_diagnostic_recurrence_groups_by_job_stage_and_reason_deterministically():
    from src.service.sa_extension_health import _telemetry_last_segment

    market_older = _structured_row(
        run_id=201,
        job_name="sa_market_news_refresh",
        outcome="degraded",
        started_at="2026-08-14T03:00:00+00:00",
        finished_at="2026-08-14T03:01:00+00:00",
        diagnostics=_recorded_diagnostics(
            _diagnostic_entry(
                occurred_at="2026-08-14T03:00:10+00:00",
                stage="local_persistence",
                reason_code="database_busy",
            ),
            _diagnostic_entry(
                occurred_at="2026-08-14T03:00:20+00:00",
                stage="local_persistence",
                reason_code="database_busy",
                target_ref="opaque-2",
            ),
            _diagnostic_entry(
                occurred_at="2026-08-14T03:00:30+00:00",
                stage="page_readiness",
                reason_code="detail_timeout",
            ),
        ),
    )
    market_newer = _structured_row(
        run_id=202,
        job_name="sa_market_news_refresh",
        outcome="degraded",
        started_at="2026-08-14T03:02:00+00:00",
        finished_at="2026-08-14T03:03:00+00:00",
        diagnostics=_recorded_diagnostics(
            _diagnostic_entry(
                occurred_at="2026-08-14T03:02:40+00:00",
                stage="local_persistence",
                reason_code="database_busy",
            )
        ),
    )
    alpha = _structured_row(
        run_id=203,
        job_name="sa_alpha_picks_refresh",
        outcome="degraded",
        started_at="2026-08-14T03:04:00+00:00",
        finished_at="2026-08-14T03:05:00+00:00",
        diagnostics=_recorded_diagnostics(
            _diagnostic_entry(
                occurred_at="2026-08-14T03:04:50+00:00",
                stage="local_persistence",
                reason_code="database_busy",
            )
        ),
    )
    store = _FakeJobStore(
        [],
        summary={"sa_alpha_picks_refresh": {"latest_attempt": alpha}},
        completed=[market_older, alpha, market_newer],
    )

    recurrence = _telemetry_last_segment(store)["diagnostic_recurrence"]

    assert recurrence == [
        {
            "job_name": "sa_alpha_picks_refresh",
            "stage": "local_persistence",
            "reason_code": "database_busy",
            "affected_run_count": 1,
            "latest_occurred_at": "2026-08-14T03:04:50.000+00:00",
        },
        {
            "job_name": "sa_market_news_refresh",
            "stage": "local_persistence",
            "reason_code": "database_busy",
            "affected_run_count": 2,
            "latest_occurred_at": "2026-08-14T03:02:40.000+00:00",
        },
        {
            "job_name": "sa_market_news_refresh",
            "stage": "page_readiness",
            "reason_code": "detail_timeout",
            "affected_run_count": 1,
            "latest_occurred_at": "2026-08-14T03:00:30.000+00:00",
        },
    ]


def test_detail_failures_recorded_has_no_health_producer():
    from src.service import sa_extension_health

    row = _structured_row(
        run_id=83,
        job_name="sa_alpha_picks_refresh",
        outcome="degraded",
        finished_at="2026-08-14T04:00:00+00:00",
        counts={"failed_retryable": 3},
    )
    segment = sa_extension_health._telemetry_last_segment(
        _FakeJobStore(
            [],
            summary={"sa_alpha_picks_refresh": {"latest_attempt": row}},
            completed=[row],
        )
    )

    assert segment["state"] == "warn"
    assert segment["code"] == "capture_degraded"
    assert "detail_failures_recorded" not in Path(
        sa_extension_health.__file__
    ).read_text(encoding="utf-8")


def test_health_reports_all_segments_and_latest_extension_slug_row(tmp_path):
    from src.service.sa_extension_health import collect_sa_extension_health

    paths = _make_paths(tmp_path)
    latest = _structured_row(
        run_id=17,
        job_name="sa_alpha_picks_refresh",
        outcome="complete",
        finished_at="2026-07-06T02:12:00+00:00",
    )
    store = _FakeJobStore(
        [],
        summary={
            "sa_alpha_picks_refresh": {
                "latest_attempt": latest,
                "latest_derived_complete": latest,
            }
        },
    )
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
    assert report["chain_state"] == "available"
    assert "ok" not in report
    assert _segment(report, "telemetry_last")["state"] == "ok"
    assert _segment(report, "telemetry_last")["code"] == "capture_complete"
    assert _segment(report, "telemetry_last")["run_id"] == 17
    assert "detail" not in _segment(report, "telemetry_last")
    assert _segment(report, "capture_readback")["state"] == "ok"
    assert store.summary_calls == [["sa_alpha_picks_refresh", "sa_market_news_refresh"]]


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

    assert report["chain_state"] == "degraded"
    assert "ok" not in report
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
        spawn_ping=lambda _paths: {
            "status": "ok",
            "telemetry_target": "http://127.0.0.1:8420",
        },
    )

    assert report["chain_state"] == "interrupted"
    assert "ok" not in report
    assert _segment(report, "config")["state"] == "fail"
    assert _segment(report, "host_ping")["state"] == "ok"
    assert _segment(report, "telemetry_last")["state"] == "warn"


def test_latest_structured_degraded_run_reports_stable_code_and_counts(tmp_path):
    from src.service.sa_extension_health import collect_sa_extension_health

    paths = _make_paths(tmp_path)
    degraded = _structured_row(
        run_id=31,
        job_name="sa_market_news_refresh",
        outcome="degraded",
        finished_at="2026-07-25T03:00:00+00:00",
        counts={"item_total": 18, "failed_retryable": 18},
    )
    with connect(str(paths.sa_db_path)) as conn:
        conn.execute(
            """
            INSERT INTO sa_refresh_meta(scope,last_success_at,row_count,ok,updated_at)
            VALUES ('current','2026-07-25T02:59:00+00:00',18,1,'2026-07-25T02:59:00+00:00')
            """
        )
    report = collect_sa_extension_health(
        paths=paths,
        env={
            "ARKSCOPE_API_HOST": "127.0.0.1",
            "ARKSCOPE_API_PORT": "45678",
            "ARKSCOPE_API_TOKEN": "token-1",
        },
        job_store=_FakeJobStore(
            [],
            summary={
                "sa_market_news_refresh": {
                    "latest_attempt": degraded,
                    "latest_derived_complete": None,
                }
            },
        ),
        spawn_ping=lambda _paths: {
            "status": "ok",
            "telemetry_target": "http://127.0.0.1:45678",
            "telemetry_source": "config",
        },
    )

    telemetry = _segment(report, "telemetry_last")
    assert telemetry == {
        "key": "telemetry_last",
        "state": "warn",
        "code": "capture_degraded",
        "job_name": "sa_market_news_refresh",
        "outcome": "degraded",
        "diagnostics_status": "absent",
        "diagnostics_error_code": None,
        "diagnostic_recurrence": [],
        "counts": {"item_total": 18, "failed_retryable": 18},
        "run_id": 31,
        "occurred_at": "2026-07-25T03:00:00+00:00",
    }
    assert report["chain_state"] == "available"


def test_legacy_succeeded_run_is_unverified_not_healthy(tmp_path):
    from src.service.sa_extension_health import collect_sa_extension_health

    paths = _make_paths(tmp_path)
    legacy = {
        "id": 41,
        "job_name": "sa_market_news_refresh",
        "status": "succeeded",
        "trigger_source": "extension",
        "finished_at": "2026-07-20T01:00:00+00:00",
        "payload": {},
        "result": {"detail_failed": 18},
    }
    report = collect_sa_extension_health(
        paths=paths,
        env={},
        job_store=_FakeJobStore([legacy], summary={}),
        spawn_ping=lambda _paths: {"status": "ok"},
    )

    telemetry = _segment(report, "telemetry_last")
    assert telemetry["state"] == "warn"
    assert telemetry["code"] == "legacy_unverified"
    assert telemetry["run_id"] == 41
    assert "detail" not in telemetry


def test_repair_segment_reports_active_and_terminal_structured_state(tmp_path):
    from src.service.sa_extension_health import collect_sa_extension_health

    paths = _make_paths(tmp_path)
    active_store = _FakeJobStore(
        [
            {
                "id": 51,
                "job_name": "sa_market_news_repair",
                "status": "running",
                "trigger_source": "extension",
                "started_at": "2026-07-25T04:00:00+00:00",
                "payload": {"manifest_hash": "a" * 64},
                "result": None,
            }
        ]
    )
    active = collect_sa_extension_health(
        paths=paths,
        env={},
        job_store=active_store,
        spawn_ping=lambda _paths: {"status": "ok"},
    )
    assert _segment(active, "market_news_repair") == {
        "key": "market_news_repair",
        "state": "warn",
        "code": "repair_active",
        "run_id": 51,
        "manifest_hash_prefix": "aaaaaaaaaaaa",
        "occurred_at": "2026-07-25T04:00:00+00:00",
    }

    terminal_store = _FakeJobStore(
        [
            {
                "id": 52,
                "job_name": "sa_market_news_repair",
                "status": "failed",
                "trigger_source": "extension",
                "started_at": "2026-07-25T04:00:00+00:00",
                "finished_at": "2026-07-25T04:05:00+00:00",
                "payload": {"manifest_hash": "b" * 64},
                "result": {
                    "derived_outcome": "degraded",
                    "counts": {"repaired": 6, "failed_retryable": 2},
                },
            }
        ]
    )
    terminal = collect_sa_extension_health(
        paths=paths,
        env={},
        job_store=terminal_store,
        spawn_ping=lambda _paths: {"status": "ok"},
    )
    repair = _segment(terminal, "market_news_repair")
    assert repair["state"] == "fail"
    assert repair["code"] == "repair_retryable"
    assert repair["counts"] == {"repaired": 6, "failed_retryable": 2}
    assert repair["run_id"] == 52


def test_new_telemetry_segments_never_expose_raw_backend_detail(tmp_path):
    from src.service.sa_extension_health import collect_sa_extension_health

    paths = _make_paths(tmp_path)
    planted = "PLANTED_RAW_TRACEBACK /home/operator/.secrets/token"
    degraded = _structured_row(
        run_id=61,
        job_name="sa_market_news_refresh",
        outcome="failed",
        finished_at="2026-07-25T05:00:00+00:00",
    )
    degraded["error"] = planted
    degraded["message"] = planted
    report = collect_sa_extension_health(
        paths=paths,
        env={},
        job_store=_FakeJobStore(
            [
                {
                    "id": 62,
                    "job_name": "sa_market_news_repair",
                    "status": "failed",
                    "trigger_source": "extension",
                    "started_at": "2026-07-25T05:00:00+00:00",
                    "finished_at": "2026-07-25T05:01:00+00:00",
                    "payload": {"manifest_hash": "c" * 64, "detail": planted},
                    "result": {
                        "derived_outcome": "degraded",
                        "counts": {"failed_retryable": 1},
                    },
                    "error": planted,
                    "message": planted,
                }
            ],
            summary={
                "sa_market_news_refresh": {
                    "latest_attempt": degraded,
                    "latest_derived_complete": None,
                }
            },
        ),
        spawn_ping=lambda _paths: {"status": "ok"},
    )

    serialized = json.dumps(
        [
            _segment(report, "telemetry_last"),
            _segment(report, "market_news_repair"),
        ]
    )
    assert planted not in serialized
    assert "detail" not in _segment(report, "telemetry_last")
    assert "detail" not in _segment(report, "market_news_repair")


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
