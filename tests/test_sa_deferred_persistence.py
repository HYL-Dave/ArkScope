"""Deferred extension receipts across protocol, SQLite, history, and health."""

from __future__ import annotations

import copy
import hashlib
import json
import sqlite3

import pytest

from src.api.routes import jobs as jobs_route
from src.sa.extension_run_protocol import derive_run_result
from src.service.job_runs_store import JobRunsLocalStore
from src.service.sa_extension_health import _telemetry_last_segment


def _event():
    return {
        "client_event_id": "deferred-receipt",
        "started_at": "2026-08-14T01:00:00Z",
        "finished_at": "2026-08-14T01:00:30Z",
        "result": {
            "schema_version": 2,
            "operation": "market_news_sync",
            "mode": "quick",
            "phases": {
                name: {"state": "deferred", "reason_code": "capacity_exhausted"}
                for name in ("list_navigation", "list_scrape", "metadata_save", "detail_fetch", "capture_readback")
            },
            "item_outcomes": [],
        },
    }


@pytest.fixture
def store(tmp_path, monkeypatch):
    store = JobRunsLocalStore(tmp_path / "profile_state.db")
    monkeypatch.setattr(jobs_route, "get_job_runs_store", lambda dal: store)
    return store


def _record(event):
    return jobs_route.record_extension_job(jobs_route.ExtensionJobRecordRequest(**event), dal=None)


def test_new_deferred_receipt_persists_distinct_status_and_warns_in_health(store):
    response = _record(_event())
    assert response.persisted is True
    row = store.list_runs(limit=1)[0]
    assert row["status"] == "deferred"
    assert row["result"]["db_status"] == "deferred"
    assert row["result"]["derived_outcome"] == "deferred"
    assert row["result"]["healthy_anchor_eligible"] is False
    assert store.structured_extension_summary_by_name([row["job_name"]])[row["job_name"]]["latest_derived_complete"] is None
    assert [entry["id"] for entry in store.completed_extension_runs_by_name()] == [response.run_id]
    segment = _telemetry_last_segment(store)
    assert (segment["state"], segment["code"]) == ("warn", "capture_deferred")
    assert jobs_route.jobs_history(name=None, limit=10, offset=0, dal=None).runs[0].status == "deferred"
    duplicate = _record(_event())
    assert duplicate.persisted is True
    assert duplicate.run_id == response.run_id
    assert store.list_runs(limit=10) == [row]


@pytest.mark.parametrize("diagnostics_present", [False, True])
def test_historical_succeeded_deferred_receipt_replays_without_rewriting_or_masking_conflicts(store, diagnostics_present):
    event = _event()
    document = {
        "client_event_id": event["client_event_id"],
        "started_at": "2026-08-14T01:00:00.000+00:00",
        "finished_at": "2026-08-14T01:00:30.000+00:00",
        "result": {**derive_run_result(event["result"]), "db_status": "succeeded"},
    }
    diagnostics = None
    if diagnostics_present:
        event["extension_diagnostics"] = {"schema_version": 1, "entries": [], "omitted_count": 0}
        diagnostics = {"status": "recorded", **event["extension_diagnostics"]}
        document["extension_diagnostics"] = diagnostics
    old_id = store.record_extension_event_once(
        client_event_id=event["client_event_id"],
        event_hash=hashlib.sha256(json.dumps(document, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        job_name="sa_market_news_refresh",
        status="succeeded",
        started_at=document["started_at"],
        finished_at=document["finished_at"],
        result=document["result"],
        duration_ms=30000,
        extension_diagnostics=diagnostics,
    )
    original = store.list_runs(limit=1)[0]

    duplicate = _record(event)

    assert duplicate.persisted is True
    assert duplicate.run_id == old_id
    assert store.list_runs(limit=10) == [original]
    segment = _telemetry_last_segment(store)
    assert (segment["state"], segment["code"]) == ("warn", "capture_deferred")
    for field in ("reason", "finished_at", "diagnostics"):
        changed = copy.deepcopy(event)
        if field == "reason":
            changed["result"]["phases"]["detail_fetch"]["reason_code"] = "site_pacing"
        elif field == "finished_at":
            changed["finished_at"] = "2026-08-14T01:00:31Z"
        else:
            changed["extension_diagnostics"] = {"schema_version": 1, "entries": [], "omitted_count": 1}
        conflict = _record(changed)
        assert conflict.persisted is False
        assert conflict.error_code == "event_conflict"
        assert store.list_runs(limit=10) == [original]


def test_ordinary_job_writers_do_not_gain_deferred_status(store):
    run_id = store.create_run("ordinary_job")
    with pytest.raises(ValueError, match="invalid job status"):
        store.finish_run(run_id, status="deferred")
    with pytest.raises(ValueError, match="terminal status"):
        store.record_completed_run("ordinary_job", status="deferred", started_at="2026-08-14T01:00:00Z")
    assert store.list_runs(limit=1)[0]["status"] == "running"


@pytest.mark.parametrize("mutation", ["job_name", "schema_version", "derived_outcome"])
def test_deferred_status_is_only_admitted_for_v2_sa_deferred_results(store, mutation):
    result = derive_run_result(_event()["result"])
    result[mutation] = {"job_name": "ordinary_job", "schema_version": 1, "derived_outcome": "complete"}[mutation]
    with pytest.raises(ValueError, match="invalid_extension_event"):
        store.record_extension_event_once(
            client_event_id="invalid-deferred", event_hash="a" * 64,
            job_name=result["job_name"], status="deferred", result=result,
            started_at="2026-08-14T01:00:00Z", finished_at="2026-08-14T01:00:30Z",
            duration_ms=30000,
        )
    assert store.list_runs(limit=10) == []


# Independent prior-version schema, including locally added schema objects.
_PRIOR_SCHEMA = """
CREATE TABLE job_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    trigger_source TEXT NOT NULL DEFAULT 'api',
    payload TEXT NOT NULL DEFAULT '{}', result TEXT, message TEXT, error TEXT,
    started_at TEXT NOT NULL, finished_at TEXT, duration_ms INTEGER,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    extra TEXT NOT NULL DEFAULT 'kept' CHECK(length(extra) > 0),
    extra_length INTEGER GENERATED ALWAYS AS (length(extra)) VIRTUAL,
    UNIQUE(job_name, started_at)
);
CREATE INDEX idx_job_runs_name_started_at ON job_runs(job_name, started_at DESC);
CREATE INDEX idx_job_runs_status_started_at ON job_runs(status, started_at DESC);
CREATE INDEX custom_job_index ON job_runs(extra) WHERE status = 'failed';
CREATE TABLE audit (run_id INTEGER);
CREATE TRIGGER job_audit AFTER INSERT ON job_runs
BEGIN INSERT INTO audit VALUES (new.id); END;
CREATE VIEW job_view AS SELECT id, extra FROM job_runs;
CREATE TABLE child (run_id INTEGER REFERENCES job_runs(id));
INSERT INTO job_runs(id, job_name, status, started_at, created_at, updated_at)
VALUES (7, 'prior', 'succeeded', '2026-08-01', '2026-08-01', '2026-08-01');
INSERT INTO child VALUES (7);
INSERT INTO job_runs(id, job_name, status, started_at, created_at, updated_at)
VALUES (100, 'deleted', 'failed', '2026-08-01', '2026-08-01', '2026-08-01');
DELETE FROM job_runs WHERE id = 100;
"""


def _prior_db(tmp_path):
    path = tmp_path / "prior.db"
    with sqlite3.connect(path) as conn:
        conn.executescript(_PRIOR_SCHEMA)
    return path


def _snapshot(path):
    with sqlite3.connect(path) as conn:
        return {
            "schema": conn.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name").fetchall(),
            "rows": conn.execute("SELECT * FROM job_runs ORDER BY id").fetchall(),
            "audit": conn.execute("SELECT * FROM audit").fetchall(),
            "child": conn.execute("SELECT * FROM child").fetchall(),
            "sequence": conn.execute("SELECT * FROM sqlite_sequence ORDER BY name").fetchall(),
        }


def test_prior_schema_upgrade_preserves_data_constraints_indexes_triggers_and_references(tmp_path, monkeypatch):
    path = _prior_db(tmp_path)
    before = _snapshot(path)
    upgraded = JobRunsLocalStore(path)
    after = _snapshot(path)
    assert after["rows"] == before["rows"]
    assert after["audit"] == before["audit"]
    assert after["child"] == before["child"]
    assert after["sequence"] == before["sequence"]
    assert [row for row in after["schema"] if row[1] != "job_runs"] == [row for row in before["schema"] if row[1] != "job_runs"]
    monkeypatch.setattr(jobs_route, "get_job_runs_store", lambda dal: upgraded)
    response = _record(_event())
    assert response.persisted is True
    assert response.run_id == 101
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT status, extra, extra_length FROM job_runs WHERE id=101").fetchone() == ("deferred", "kept", 4)
        assert conn.execute("SELECT * FROM audit").fetchall() == [(7,), (100,), (101,)]
        assert conn.execute("SELECT * FROM job_view WHERE id=7").fetchone() == (7, "kept")
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        for sql in (
            "UPDATE job_runs SET status='invented' WHERE id=101",
            "UPDATE job_runs SET job_name=NULL WHERE id=101",
            "UPDATE job_runs SET extra='' WHERE id=101",
            "UPDATE job_runs SET job_name='prior', started_at='2026-08-01' WHERE id=101",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(sql)
    stable = _snapshot(path)
    JobRunsLocalStore(path)
    assert _snapshot(path) == stable


@pytest.mark.parametrize("denied_action", [sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_CREATE_TRIGGER])
def test_prior_schema_upgrade_rolls_back_on_failure(tmp_path, monkeypatch, denied_action):
    path = _prior_db(tmp_path)
    before = _snapshot(path)
    original_connect = JobRunsLocalStore._connect

    def faulting_connect(self):
        conn = original_connect(self)
        conn.set_authorizer(lambda action, *args: sqlite3.SQLITE_DENY if action == denied_action else sqlite3.SQLITE_OK)
        return conn

    with monkeypatch.context() as patch:
        patch.setattr(JobRunsLocalStore, "_connect", faulting_connect)
        with pytest.raises(sqlite3.DatabaseError):
            JobRunsLocalStore(path)
    assert _snapshot(path) == before
    upgraded = JobRunsLocalStore(path)
    monkeypatch.setattr(jobs_route, "get_job_runs_store", lambda dal: upgraded)
    assert _record(_event()).persisted is True
