import sqlite3
from pathlib import Path

import pytest

from src.service import job_runs_cutover
from src.service.job_runs_store import USE_LOCAL_JOB_RUNS_KEY


def _source_rows():
    return (
        {
            "id": 7,
            "job_name": "collect.polygon_news",
            "status": "succeeded",
            "trigger_source": "scheduler",
            "payload": {"source": "polygon_news"},
            "result": {"updated": 3},
            "message": "ok",
            "error": None,
            "started_at": "2026-07-01T10:00:00+00:00",
            "finished_at": "2026-07-01T10:00:05+00:00",
            "duration_ms": 5000,
            "created_at": "2026-07-01T10:00:00+00:00",
            "updated_at": "2026-07-01T10:00:05+00:00",
        },
        {
            "id": 8,
            "job_name": "fetch_fred_series",
            "status": "failed",
            "trigger_source": "api",
            "payload": {},
            "result": None,
            "message": None,
            "error": "rate limited",
            "started_at": "2026-07-01T11:00:00+00:00",
            "finished_at": "2026-07-01T11:00:02+00:00",
            "duration_ms": 2000,
            "created_at": "2026-07-01T11:00:00+00:00",
            "updated_at": "2026-07-01T11:00:02+00:00",
        },
    )


def _seed_profile_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS profile_settings "
            "(key TEXT PRIMARY KEY, value TEXT, updated_at TEXT NOT NULL)"
        )
        conn.commit()
    finally:
        conn.close()


def test_preview_is_read_only_and_deterministic(tmp_path, monkeypatch):
    profile = tmp_path / "profile_state.db"
    _seed_profile_db(profile)
    monkeypatch.setattr(job_runs_cutover, "read_pg_job_runs", lambda dsn: _source_rows())

    first = job_runs_cutover.preview_job_runs_cutover(profile, "pg://source")
    second = job_runs_cutover.preview_job_runs_cutover(profile, "pg://source")

    assert first.to_json_dict() == second.to_json_dict()
    assert first.pg_rows == 2
    assert first.local_rows == 0
    assert first.status_counts == {"failed": 1, "succeeded": 1}
    assert first.job_name_counts == {"collect.polygon_news": 1, "fetch_fred_series": 1}
    assert first.latest_started_at == "2026-07-01T11:00:00+00:00"
    assert first.would_apply is True
    conn = sqlite3.connect(profile)
    try:
        assert (
            conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='job_runs'"
            ).fetchone()
            is None
        )
    finally:
        conn.close()


def test_preview_blocks_conflicting_local_rows(tmp_path, monkeypatch):
    profile = tmp_path / "profile_state.db"
    _seed_profile_db(profile)
    monkeypatch.setattr(job_runs_cutover, "read_pg_job_runs", lambda dsn: _source_rows())

    conn = sqlite3.connect(profile)
    try:
        conn.executescript(job_runs_cutover.SQLITE_JOB_RUNS_SCHEMA)
        conn.execute(
            "INSERT INTO job_runs "
            "(id,job_name,status,trigger_source,payload,started_at,created_at,updated_at) "
            "VALUES (7,'collect.polygon_news','failed','scheduler','{}',"
            "'2026-07-01T10:00:00+00:00','now','now')"
        )
        conn.commit()
    finally:
        conn.close()

    report = job_runs_cutover.preview_job_runs_cutover(profile, "pg://source")

    assert report.would_apply is False
    assert any("local row differs" in blocker for blocker in report.blockers)


def test_apply_writes_rows_audit_setting_and_is_idempotent(tmp_path, monkeypatch):
    profile = tmp_path / "profile_state.db"
    backup = tmp_path / "profile_state.bak"
    _seed_profile_db(profile)
    monkeypatch.setattr(job_runs_cutover, "read_pg_job_runs", lambda dsn: _source_rows())
    expected = job_runs_cutover.preview_job_runs_cutover(profile, "pg://source").fingerprint

    result = job_runs_cutover.apply_job_runs_cutover(
        profile,
        pg_dsn="pg://source",
        expected_fingerprint=expected,
        backup_path=backup,
    )
    second = job_runs_cutover.apply_job_runs_cutover(
        profile,
        pg_dsn="pg://source",
        expected_fingerprint=expected,
        backup_path=tmp_path / "profile_state_second.bak",
    )

    assert result.inserted == 2
    assert result.already_applied is False
    assert second.inserted == 0
    assert second.already_applied is True
    assert backup.exists()
    conn = sqlite3.connect(profile)
    try:
        assert conn.execute("SELECT COUNT(*) FROM job_runs").fetchone()[0] == 2
        assert conn.execute("SELECT MAX(id) FROM job_runs").fetchone()[0] == 8
        assert conn.execute("SELECT COUNT(*) FROM job_runs_migration_runs").fetchone()[0] == 1
        assert (
            conn.execute(
                "SELECT value FROM profile_settings WHERE key=?",
                (USE_LOCAL_JOB_RUNS_KEY,),
            ).fetchone()[0]
            == "true"
        )
    finally:
        conn.close()


def test_apply_refuses_fingerprint_drift_before_backup(tmp_path, monkeypatch):
    profile = tmp_path / "profile_state.db"
    backup = tmp_path / "profile_state.bak"
    _seed_profile_db(profile)
    monkeypatch.setattr(job_runs_cutover, "read_pg_job_runs", lambda dsn: _source_rows())

    with pytest.raises(job_runs_cutover.JobRunsCutoverBlocked):
        job_runs_cutover.apply_job_runs_cutover(
            profile,
            pg_dsn="pg://source",
            expected_fingerprint="wrong",
            backup_path=backup,
        )

    assert not backup.exists()


def test_apply_refuses_post_backup_pg_drift_before_writing(tmp_path, monkeypatch):
    profile = tmp_path / "profile_state.db"
    backup = tmp_path / "profile_state.bak"
    _seed_profile_db(profile)
    base_rows = _source_rows()
    drifted_rows = base_rows + (
        {
            **base_rows[-1],
            "id": 9,
            "job_name": "fetch_ipo_calendar",
            "started_at": "2026-07-01T12:00:00+00:00",
            "finished_at": "2026-07-01T12:00:01+00:00",
            "created_at": "2026-07-01T12:00:00+00:00",
            "updated_at": "2026-07-01T12:00:01+00:00",
        },
    )
    monkeypatch.setattr(job_runs_cutover, "read_pg_job_runs", lambda dsn: base_rows)
    expected = job_runs_cutover.preview_job_runs_cutover(profile, "pg://source").fingerprint

    reads = iter([base_rows, base_rows, drifted_rows, drifted_rows])
    monkeypatch.setattr(job_runs_cutover, "read_pg_job_runs", lambda dsn: next(reads))

    with pytest.raises(job_runs_cutover.JobRunsCutoverBlocked):
        job_runs_cutover.apply_job_runs_cutover(
            profile,
            pg_dsn="pg://source",
            expected_fingerprint=expected,
            backup_path=backup,
        )

    conn = sqlite3.connect(profile)
    try:
        assert (
            conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='job_runs'"
            ).fetchone()
            is None
        )
    finally:
        conn.close()


def test_cli_accepts_subcommand_market_db_alias(tmp_path):
    from scripts.migration.job_runs_local_cutover import build_parser

    parsed = build_parser().parse_args(
        [
            "preview",
            "--market-db",
            str(tmp_path / "profile_state.db"),
            "--pg-dsn",
            "pg://source",
            "--output",
            str(tmp_path / "out.json"),
        ]
    )

    assert parsed.profile_db == tmp_path / "profile_state.db"
