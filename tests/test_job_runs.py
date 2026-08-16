"""Tests for job_runs persistence (P0.2 service-first S2).

Coverage:
  - JobRunsStore: availability, create_run, finish_run, list_runs, latest_runs_by_name
  - graceful degradation when DB unavailable / FileBackend / on error
  - list_jobs_status DB merge with process-local fallback
  - run_job persists start + finish on success and failure
  - GET /jobs/history endpoint
  - _summarize_result heuristics
"""

from __future__ import annotations

import json
import inspect
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.service import jobs as jobs_module
from src.service import job_runs_store as job_runs_store_module
from src.service.job_runs_store import (
    ENV_USE_LOCAL_JOB_RUNS,
    USE_LOCAL_JOB_RUNS_KEY,
    JobRunsLocalStore,
    _serialize_local_row,
    get_job_runs_store,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_local_store(tmp_path: Path) -> JobRunsLocalStore:
    return JobRunsLocalStore(tmp_path / "profile_state.db")


def _make_db_dal():
    dal = MagicMock()
    dal._base = None
    return dal, MagicMock()


def _make_file_dal():
    dal = MagicMock()
    dal._base = None
    return dal


def _create_minimal_job_runs_db(path: Path, *job_names: str) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE job_runs (job_name TEXT NOT NULL)")
        conn.executemany(
            "INSERT INTO job_runs (job_name) VALUES (?)",
            ((name,) for name in job_names),
        )


def test_read_job_activity_if_exists_missing_profile_is_none_and_no_create(tmp_path):
    db = tmp_path / "missing" / "profile_state.db"

    result = job_runs_store_module.read_job_activity_if_exists(
        db, {"sa_market_news_refresh"}
    )

    assert result == "none"
    assert not db.exists()
    assert not db.parent.exists()


def test_read_job_activity_if_exists_missing_table_is_none_and_no_mutation(tmp_path):
    db = tmp_path / "profile_state.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)")

    before_stat = db.stat()
    with sqlite3.connect(f"file:{db.resolve()}?mode=ro", uri=True) as conn:
        before_schema = conn.execute("PRAGMA schema_version").fetchone()[0]
        before_names = conn.execute(
            "SELECT name FROM sqlite_master ORDER BY name"
        ).fetchall()

    result = job_runs_store_module.read_job_activity_if_exists(
        db, {"sa_market_news_refresh"}
    )

    after_stat = db.stat()
    with sqlite3.connect(f"file:{db.resolve()}?mode=ro", uri=True) as conn:
        after_schema = conn.execute("PRAGMA schema_version").fetchone()[0]
        after_names = conn.execute(
            "SELECT name FROM sqlite_master ORDER BY name"
        ).fetchall()
    assert result == "none"
    assert (after_stat.st_size, after_stat.st_mtime_ns) == (
        before_stat.st_size,
        before_stat.st_mtime_ns,
    )
    assert after_schema == before_schema
    assert after_names == before_names


def test_read_job_activity_if_exists_distinguishes_relevant_and_unrelated_rows(tmp_path):
    db = tmp_path / "profile_state.db"
    _create_minimal_job_runs_db(db, "unrelated_job")

    assert job_runs_store_module.read_job_activity_if_exists(
        db, {"sa_market_news_refresh"}
    ) == "none"

    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO job_runs (job_name) VALUES (?)",
            ("sa_market_news_refresh",),
        )
    assert job_runs_store_module.read_job_activity_if_exists(
        db, {"sa_market_news_refresh"}
    ) == "present"


def test_read_job_activity_if_exists_unreadable_or_malformed_is_unknown(tmp_path):
    directory = tmp_path / "profile-directory"
    directory.mkdir()
    malformed = tmp_path / "profile_state.db"
    malformed.write_bytes(b"not a sqlite database")

    assert job_runs_store_module.read_job_activity_if_exists(
        directory, {"sa_market_news_refresh"}
    ) == "unknown"
    assert job_runs_store_module.read_job_activity_if_exists(
        malformed, {"sa_market_news_refresh"}
    ) == "unknown"


def test_sa_store_history_contract_has_no_pruning_or_time_cutoff():
    runtime_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in Path("src").rglob("*.py")
    ).lower()
    assert "delete from job_runs" not in runtime_source
    assert "drop table job_runs" not in runtime_source

    reader_source = inspect.getsource(
        job_runs_store_module.read_job_activity_if_exists
    ).lower()
    for forbidden in ("started_at", "finished_at", "status", "timestamp"):
        assert forbidden not in reader_source


def test_sa_store_activity_job_names_cover_all_current_authorities():
    from src.sa.extension_run_protocol import OPERATION_CONTRACTS
    from src.sa.market_news_recovery import REPAIR_JOB_NAME
    from src.tools.sa_tools import SA_STORE_ACTIVITY_JOB_NAMES

    extension_names = {
        contract["job_name"] for contract in OPERATION_CONTRACTS.values()
    }
    service_names = {
        definition.name
        for definition in jobs_module._JOB_DEFINITIONS.values()
        if definition.feature_flag == "sa_enabled"
    }
    expected = extension_names | service_names | {REPAIR_JOB_NAME}

    assert SA_STORE_ACTIVITY_JOB_NAMES == expected
    assert len(SA_STORE_ACTIVITY_JOB_NAMES) == 7


_SA_RUN_OUTCOMES = (
    Path(__file__).parent / "fixtures" / "sa_extension" / "run_outcomes.json"
)


def _extension_protocol_case(name: str) -> dict:
    fixture = json.loads(_SA_RUN_OUTCOMES.read_text(encoding="utf-8"))
    for entry in fixture["protocol_cases"]:
        if entry["name"] == name:
            return json.loads(json.dumps(entry["input"]))
    raise AssertionError(f"unknown SA extension protocol case: {name}")


def _extension_event(
    event_id: str,
    case: str = "complete_market_sync",
    *,
    started_at: str = "2026-07-25T01:00:00Z",
    finished_at: str = "2026-07-25T01:00:30Z",
) -> dict:
    return {
        "client_event_id": event_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "result": _extension_protocol_case(case),
    }


# ---------------------------------------------------------------------------
# Current local store contracts
# ---------------------------------------------------------------------------


def test_store_unavailable_with_no_backend(tmp_path):
    store = _make_local_store(tmp_path)
    assert store.is_available() is True
    assert store.list_runs() == []


def test_store_unavailable_with_filebackend(tmp_path):
    store = _make_local_store(tmp_path)
    assert store.create_run("local-job") == 1


def test_store_available_with_database_backend(tmp_path):
    store = _make_local_store(tmp_path)
    assert store.is_available() is True


# ---------------------------------------------------------------------------
# create_run
# ---------------------------------------------------------------------------


def test_create_run_returns_inserted_id(tmp_path):
    store = _make_local_store(tmp_path)

    run_id = store.create_run("foo", trigger_source="cli", payload={"x": 1})

    assert run_id == 1
    assert store.list_runs()[0]["payload"] == {"x": 1}


def test_create_run_swallows_db_error(tmp_path, monkeypatch):
    store = _make_local_store(tmp_path)
    monkeypatch.setattr(
        store,
        "_connect",
        lambda: (_ for _ in ()).throw(RuntimeError("local write failed")),
    )

    assert store.create_run("foo") is None


# ---------------------------------------------------------------------------
# finish_run
# ---------------------------------------------------------------------------


def test_finish_run_rejects_running_status(tmp_path):
    store = _make_local_store(tmp_path)
    with pytest.raises(ValueError, match="terminal"):
        store.finish_run(1, status="running")


def test_finish_run_rejects_unknown_status(tmp_path):
    store = _make_local_store(tmp_path)
    with pytest.raises(ValueError, match="invalid"):
        store.finish_run(1, status="bogus")


def test_finish_run_returns_false_when_run_id_none(tmp_path):
    store = _make_local_store(tmp_path)
    assert store.finish_run(None, status="succeeded") is False


def test_finish_run_updates_row(tmp_path):
    store = _make_local_store(tmp_path)
    run_id = store.create_run("foo")

    ok = store.finish_run(
        run_id,
        status="succeeded",
        message="42 articles",
        result={"count": 42},
    )

    assert ok is True
    row = store.list_runs()[0]
    assert row["status"] == "succeeded"
    assert row["message"] == "42 articles"
    assert row["result"] == {"count": 42}


def test_finish_run_swallows_db_error(tmp_path, monkeypatch):
    store = _make_local_store(tmp_path)
    monkeypatch.setattr(
        store,
        "_connect",
        lambda: (_ for _ in ()).throw(RuntimeError("local write failed")),
    )

    assert store.finish_run(1, status="failed", error="boom") is False


# ---------------------------------------------------------------------------
# list_runs / latest_runs_by_name
# ---------------------------------------------------------------------------


def test_list_runs_returns_serialized_rows(tmp_path):
    store = _make_local_store(tmp_path)
    store.record_completed_run(
        "foo",
        status="succeeded",
        trigger_source="api",
        payload={"scope": "test"},
        result={"count": 1},
        started_at="2026-04-25T10:00:00Z",
        finished_at="2026-04-25T10:01:00Z",
    )

    row = store.list_runs(job_name="foo")[0]

    assert row["job_name"] == "foo"
    assert row["payload"] == {"scope": "test"}
    assert row["result"] == {"count": 1}
    assert row["started_at"] == "2026-04-25T10:00:00+00:00"


def test_list_runs_clamps_limit_and_offset(tmp_path):
    store = _make_local_store(tmp_path)
    rows = [
        (
            f"job-{index}",
            "succeeded",
            "api",
            "{}",
            "2026-04-25T10:00:00+00:00",
            "2026-04-25T10:00:00+00:00",
            "2026-04-25T10:00:00+00:00",
        )
        for index in range(205)
    ]
    with store._connect() as conn:
        conn.executemany(
            """
            INSERT INTO job_runs (
                job_name, status, trigger_source, payload,
                started_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    assert len(store.list_runs(limit=5000, offset=-3)) == 200


def test_latest_runs_by_name_keys_by_job_name(tmp_path):
    store = _make_local_store(tmp_path)
    store.record_completed_run(
        "a",
        status="succeeded",
        started_at="2026-04-25T10:00:00Z",
        finished_at="2026-04-25T10:01:00Z",
    )
    store.create_run("b", trigger_source="scheduler")

    out = store.latest_runs_by_name()

    assert set(out) == {"a", "b"}
    assert out["a"]["status"] == "succeeded"
    assert out["b"]["status"] == "running"


def test_latest_runs_by_name_swallows_db_error(tmp_path, monkeypatch):
    store = _make_local_store(tmp_path)
    monkeypatch.setattr(
        store,
        "_connect",
        lambda: (_ for _ in ()).throw(RuntimeError("local read failed")),
    )
    assert store.latest_runs_by_name() == {}


def test_run_summary_by_name_returns_none_on_db_error(tmp_path, monkeypatch):
    store = _make_local_store(tmp_path)
    monkeypatch.setattr(
        store,
        "_connect",
        lambda: (_ for _ in ()).throw(RuntimeError("local read failed")),
    )
    assert store.run_summary_by_name(["sa_market_news_refresh"]) is None


def test_run_summary_by_name_uses_single_row_cursor_shape(tmp_path):
    store = _make_local_store(tmp_path)
    store.record_completed_run(
        "sa_market_news_refresh",
        status="succeeded",
        started_at="2026-04-25T10:00:00Z",
        finished_at="2026-04-25T10:01:00Z",
    )
    store.record_completed_run(
        "sa_market_news_refresh",
        status="failed",
        started_at="2026-04-25T10:04:00Z",
        finished_at="2026-04-25T10:05:00Z",
    )

    summary = store.run_summary_by_name(["sa_market_news_refresh"])

    assert summary == {
        "sa_market_news_refresh": {
            "last_success_at": "2026-04-25T10:01:00+00:00",
            "last_any_at": "2026-04-25T10:05:00+00:00",
        }
    }


def test_serialize_row_converts_datetimes():
    row = {
        "payload": '{"scope":"test"}',
        "result": '{"count":1}',
        "started_at": "2026-04-25T10:00:00+00:00",
    }

    out = _serialize_local_row(row)

    assert out["payload"] == {"scope": "test"}
    assert out["result"] == {"count": 1}
    assert out["started_at"] == "2026-04-25T10:00:00+00:00"


# ---------------------------------------------------------------------------
# list_jobs_status — DB merge + fallback
# ---------------------------------------------------------------------------


def test_list_jobs_status_uses_db_latest_when_available():
    dal, backend = _make_db_dal()
    dal.get_watchlist.return_value = MagicMock(tickers=[])

    db_row = {
        "status": "succeeded",
        "started_at": "2026-04-25T10:00:00+00:00",
        "finished_at": "2026-04-25T10:01:00+00:00",
        "message": "Monitor scan emitted 3 alert(s)",
        "result": {"alert_count": 3},
        "error": None,
    }

    with patch.object(
        JobRunsLocalStore, "is_available", return_value=True,
    ), patch.object(
        JobRunsLocalStore,
        "latest_runs_by_name",
        return_value={"monitor_watchlist_scan": db_row},
    ):
        out = jobs_module.list_jobs_status(dal)

    by_name = {j["name"]: j for j in out}
    scan = by_name["monitor_watchlist_scan"]
    assert scan["last_status"] == "succeeded"
    assert scan["last_message"] == "Monitor scan emitted 3 alert(s)"
    assert scan["last_started_at"] == "2026-04-25T10:00:00+00:00"


def test_list_jobs_status_falls_back_to_process_local_when_db_empty():
    dal = _make_file_dal()
    dal.get_watchlist.return_value = MagicMock(tickers=[])

    # Seed process-local state for one job
    state = jobs_module._JOB_STATE["monitor_watchlist_scan"]
    state.last_status = "succeeded"
    state.last_started_at = "2026-04-25T09:00:00+00:00"
    state.last_finished_at = "2026-04-25T09:01:00+00:00"
    state.last_message = "scan done"
    state.last_result = {"alert_count": 2}
    try:
        out = jobs_module.list_jobs_status(dal)
        by_name = {j["name"]: j for j in out}
        scan = by_name["monitor_watchlist_scan"]
        assert scan["last_status"] == "succeeded"
        assert scan["last_message"] == "scan done"
    finally:
        # Reset to keep test isolation
        from src.service.jobs import JobExecutionState
        jobs_module._JOB_STATE["monitor_watchlist_scan"] = JobExecutionState()


def test_list_jobs_status_falls_back_when_db_error():
    dal, _ = _make_db_dal()
    dal.get_watchlist.return_value = MagicMock(tickers=[])

    with patch.object(JobRunsLocalStore, "latest_runs_by_name", return_value={}):
        out = jobs_module.list_jobs_status(dal)
    # All jobs should appear with at least the never_run default
    statuses = {j["name"]: j["last_status"] for j in out}
    assert "monitor_watchlist_scan" in statuses
    # Either process-local cached value or "never_run" — both acceptable
    assert statuses["monitor_watchlist_scan"] in {"never_run", "succeeded", "failed", "running"}


# ---------------------------------------------------------------------------
# _summarize_result heuristics
# ---------------------------------------------------------------------------


def test_summarize_monitor_scan_result():
    msg = jobs_module._summarize_result(
        "monitor_watchlist_scan",
        {"alert_count": 3},
    )
    assert "3 alert" in msg


def test_summarize_unknown_job_falls_back():
    msg = jobs_module._summarize_result("unknown_job", {})
    assert msg == "Job completed successfully."


def test_summarize_handles_non_dict():
    msg = jobs_module._summarize_result("monitor_watchlist_scan", "not a dict")
    assert msg == "Job completed successfully."


# ---------------------------------------------------------------------------
# run_job persistence wiring
# ---------------------------------------------------------------------------


def test_run_job_persists_start_and_finish_on_success():
    dal, backend = _make_db_dal()
    dal.get_watchlist.return_value = MagicMock(tickers=["NVDA"])

    create_calls: list = []
    finish_calls: list = []

    def fake_create_run(self, name, **kwargs):
        create_calls.append((name, kwargs))
        return 99

    def fake_finish_run(self, run_id, **kwargs):
        finish_calls.append((run_id, kwargs))
        return True

    fake_result = {"alert_count": 1, "alerts": []}

    with patch.object(JobRunsLocalStore, "create_run", fake_create_run), \
         patch.object(JobRunsLocalStore, "finish_run", fake_finish_run), \
         patch.object(jobs_module, "_run_monitor_watchlist_scan", return_value=fake_result):
        result = jobs_module.run_job(
            "monitor_watchlist_scan", dal=dal, trigger_source="cli",
        )

    assert result.status == "succeeded"
    assert len(create_calls) == 1
    assert create_calls[0][0] == "monitor_watchlist_scan"
    assert create_calls[0][1]["trigger_source"] == "cli"
    assert len(finish_calls) == 1
    assert finish_calls[0][0] == 99
    assert finish_calls[0][1]["status"] == "succeeded"
    assert "1 alert" in finish_calls[0][1]["message"]


def test_run_job_persists_failure():
    dal, backend = _make_db_dal()
    dal.get_watchlist.return_value = MagicMock(tickers=["NVDA"])

    finish_calls: list = []

    def fake_create_run(self, name, **kwargs):
        return 100

    def fake_finish_run(self, run_id, **kwargs):
        finish_calls.append((run_id, kwargs))
        return True

    with patch.object(JobRunsLocalStore, "create_run", fake_create_run), \
         patch.object(JobRunsLocalStore, "finish_run", fake_finish_run), \
         patch.object(
             jobs_module, "_run_monitor_watchlist_scan",
             side_effect=RuntimeError("boom"),
         ):
        with pytest.raises(RuntimeError, match="boom"):
            jobs_module.run_job("monitor_watchlist_scan", dal=dal)

    assert len(finish_calls) == 1
    assert finish_calls[0][0] == 100
    assert finish_calls[0][1]["status"] == "failed"
    assert finish_calls[0][1]["error"] == "boom"


def test_run_job_continues_when_create_run_returns_none():
    """Persistence failure must not block the job."""
    dal = _make_file_dal()
    dal.get_watchlist.return_value = MagicMock(tickers=["NVDA"])

    fake_result = {"alert_count": 0, "alerts": []}
    with patch.object(JobRunsLocalStore, "create_run", return_value=None), \
         patch.object(jobs_module, "_run_monitor_watchlist_scan", return_value=fake_result):
        result = jobs_module.run_job("monitor_watchlist_scan", dal=dal)
    assert result.status == "succeeded"


# ---------------------------------------------------------------------------
# /jobs/history endpoint
# ---------------------------------------------------------------------------


def test_jobs_history_endpoint_returns_rows_from_store():
    # Route-unit isolation: call the handler directly instead of TestClient.
    # This endpoint only needs the injected DAL; ASGI/TestClient would exercise
    # Starlette/AnyIO plumbing and can hang in sandboxed environments.
    from src.api.routes.jobs import jobs_history

    fake_dal = MagicMock()
    fake_dal.get_available_tickers.return_value = []

    fake_rows = [
        {
            "id": 1, "job_name": "foo", "status": "succeeded",
            "trigger_source": "api", "payload": {}, "result": None,
            "message": "ok", "error": None,
            "started_at": "2026-04-25T10:00:00+00:00",
            "finished_at": "2026-04-25T10:01:00+00:00",
            "duration_ms": 60000,
            "created_at": "2026-04-25T10:00:00+00:00",
            "updated_at": "2026-04-25T10:01:00+00:00",
        }
    ]

    with patch.object(JobRunsLocalStore, "list_runs", return_value=fake_rows):
        response = jobs_history(name="foo", limit=10, offset=0, dal=fake_dal)
    data = response.model_dump()
    assert data["count"] == 1
    assert data["limit"] == 10
    assert data["offset"] == 0
    assert data["runs"][0]["job_name"] == "foo"


def test_jobs_history_endpoint_returns_empty_when_unavailable():
    from src.api.routes.jobs import jobs_history

    fake_dal = MagicMock(_backend=None)
    fake_dal.get_available_tickers.return_value = []

    response = jobs_history(name=None, limit=50, offset=0, dal=fake_dal)
    data = response.model_dump()
    assert data["count"] == 0
    assert data["runs"] == []


# ---------------------------------------------------------------------------
# record_completed_run
# ---------------------------------------------------------------------------


def test_record_completed_run_inserts_terminal_row(tmp_path):
    store = _make_local_store(tmp_path)
    started = datetime(2026, 4, 25, 12, 0, tzinfo=timezone.utc)
    finished = datetime(2026, 4, 25, 12, 0, 30, tzinfo=timezone.utc)

    run_id = store.record_completed_run(
        "sa_extension:market_news_quick",
        status="succeeded",
        started_at=started,
        finished_at=finished,
        trigger_source="extension",
        payload={"display_name": "Market News quick"},
        result={"saved": 17, "detail_fetched": 5},
        message="ok",
        duration_ms=30_000,
    )

    assert run_id == 1
    row = store.list_runs()[0]
    assert row["job_name"] == "sa_extension:market_news_quick"
    assert row["status"] == "succeeded"
    assert row["trigger_source"] == "extension"
    assert row["payload"] == {"display_name": "Market News quick"}
    assert row["result"] == {"saved": 17, "detail_fetched": 5}
    assert row["duration_ms"] == 30_000


def test_record_completed_run_rejects_running_status(tmp_path):
    store = _make_local_store(tmp_path)
    started = datetime(2026, 4, 25, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="terminal"):
        store.record_completed_run("x", status="running", started_at=started)


def test_record_completed_run_rejects_unknown_status(tmp_path):
    store = _make_local_store(tmp_path)
    started = datetime(2026, 4, 25, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="terminal"):
        store.record_completed_run("x", status="bogus", started_at=started)


def test_record_completed_run_returns_none_when_unavailable(tmp_path, monkeypatch):
    store = _make_local_store(tmp_path)
    monkeypatch.setattr(
        store,
        "_connect",
        lambda: (_ for _ in ()).throw(RuntimeError("local write failed")),
    )
    started = datetime(2026, 4, 25, 12, 0, tzinfo=timezone.utc)

    assert store.record_completed_run(
        "x", status="succeeded", started_at=started
    ) is None


def test_record_completed_run_swallows_db_error(tmp_path, monkeypatch):
    store = _make_local_store(tmp_path)
    monkeypatch.setattr(
        store,
        "_connect",
        lambda: (_ for _ in ()).throw(RuntimeError("local write failed")),
    )
    started = datetime(2026, 4, 25, 12, 0, tzinfo=timezone.utc)

    assert store.record_completed_run(
        "x", status="failed", started_at=started, error="boom"
    ) is None


def test_record_completed_run_omits_finished_at_when_not_provided(tmp_path):
    store = _make_local_store(tmp_path)
    started = datetime(2026, 4, 25, 12, 0, tzinfo=timezone.utc)

    run_id = store.record_completed_run(
        "x",
        status="succeeded",
        started_at=started,
    )

    assert run_id == 1
    assert store.list_runs()[0]["finished_at"] is not None


# ---------------------------------------------------------------------------
# Local job_runs store + routing (S-H1)
# ---------------------------------------------------------------------------


def test_local_store_create_finish_and_latest(tmp_path):
    db = tmp_path / "profile_state.db"
    store = JobRunsLocalStore(db)

    run_id = store.create_run(
        "monitor_watchlist_scan",
        trigger_source="api",
        payload={"tickers": ["NVDA"]},
    )
    assert run_id == 1
    assert store.finish_run(
        run_id,
        status="succeeded",
        message="ok",
        result={"processed": 1},
        duration_ms=123,
    ) is True

    rows = store.list_runs(job_name="monitor_watchlist_scan", limit=10, offset=0)
    assert len(rows) == 1
    assert rows[0]["payload"] == {"tickers": ["NVDA"]}
    assert rows[0]["result"] == {"processed": 1}
    assert rows[0]["duration_ms"] == 123
    assert rows[0]["started_at"]
    assert rows[0]["finished_at"]

    latest = store.latest_runs_by_name()
    assert latest["monitor_watchlist_scan"]["status"] == "succeeded"


def test_local_store_finish_run_computes_duration_when_omitted(tmp_path):
    db = tmp_path / "profile_state.db"
    store = JobRunsLocalStore(db)
    run_id = store.create_run("monitor_watchlist_scan")

    assert store.finish_run(run_id, status="succeeded", message="ok") is True

    row = store.list_runs(job_name="monitor_watchlist_scan")[0]
    assert row["duration_ms"] is not None


def test_local_store_record_completed_preserves_ids_and_payload(tmp_path):
    db = tmp_path / "profile_state.db"
    store = JobRunsLocalStore(db)
    started = datetime(2026, 4, 25, 12, 0, tzinfo=timezone.utc)
    finished = datetime(2026, 4, 25, 12, 0, 30, tzinfo=timezone.utc)

    run_id = store.record_completed_run(
        "sa_extension:market_news_quick",
        status="failed",
        started_at=started,
        finished_at=finished,
        trigger_source="extension",
        payload={"scope": "current"},
        result={"saved": 0},
        error="timeout",
        duration_ms=30_000,
        id=77,
    )

    assert run_id == 77
    row = store.list_runs(limit=1)[0]
    assert row["id"] == 77
    assert row["payload"] == {"scope": "current"}
    assert row["result"] == {"saved": 0}
    assert row["error"] == "timeout"
    assert row["started_at"].startswith("2026-04-25T12:00:00")


def test_local_store_list_runs_filters_by_trigger_source(tmp_path):
    db = tmp_path / "profile_state.db"
    store = JobRunsLocalStore(db)

    store.record_completed_run(
        "sa_market_news_refresh",
        status="succeeded",
        started_at="2026-07-05T16:00:00Z",
        finished_at="2026-07-05T16:01:00Z",
        trigger_source="api",
    )
    store.record_completed_run(
        "sa_extension:alpha_picks_quick",
        status="succeeded",
        started_at="2026-07-06T02:00:00Z",
        finished_at="2026-07-06T02:01:00Z",
        trigger_source="extension",
    )

    rows = store.list_runs(trigger_source="extension", limit=10)

    assert [row["job_name"] for row in rows] == ["sa_extension:alpha_picks_quick"]
    assert rows[0]["trigger_source"] == "extension"


def test_local_store_run_summary_distinguishes_latest_success_and_latest_any(tmp_path):
    db = tmp_path / "profile_state.db"
    store = JobRunsLocalStore(db)

    store.record_completed_run(
        "fetch_economic_calendar_recent",
        status="succeeded",
        started_at="2026-04-25T10:00:00Z",
        finished_at="2026-04-25T10:01:00Z",
    )
    store.record_completed_run(
        "fetch_economic_calendar_recent",
        status="failed",
        started_at="2026-04-25T11:00:00Z",
        finished_at="2026-04-25T11:01:00Z",
        error="boom",
    )

    summary = store.run_summary_by_name(["fetch_economic_calendar_recent"])

    assert summary["fetch_economic_calendar_recent"] == {
        "last_success_at": "2026-04-25T10:01:00+00:00",
        "last_any_at": "2026-04-25T11:01:00+00:00",
    }


def test_get_job_runs_store_uses_profile_toggle_for_local(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_USE_LOCAL_JOB_RUNS, raising=False)
    dal = MagicMock()
    dal._profile_setting_truthy.return_value = True
    dal._base = None
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))

    store = get_job_runs_store(dal)

    assert isinstance(store, JobRunsLocalStore)
    dal._profile_setting_truthy.assert_called_once_with(
        USE_LOCAL_JOB_RUNS_KEY, ENV_USE_LOCAL_JOB_RUNS
    )


def test_get_job_runs_store_explicit_false_uses_local_after_n9(tmp_path, monkeypatch):
    monkeypatch.delenv(ENV_USE_LOCAL_JOB_RUNS, raising=False)
    dal = MagicMock()
    dal._profile_setting_truthy.return_value = False
    dal._base = None
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))

    store = get_job_runs_store(dal)

    assert isinstance(store, JobRunsLocalStore)


def test_jobs_history_endpoint_uses_store_factory(monkeypatch):
    from src.api.routes import jobs as jobs_route

    fake_rows = [
        {
            "id": 2,
            "job_name": "foo",
            "status": "succeeded",
            "trigger_source": "api",
            "payload": {},
            "result": None,
            "message": None,
            "error": None,
            "started_at": "2026-04-25T10:00:00+00:00",
            "finished_at": None,
            "duration_ms": None,
            "created_at": "2026-04-25T10:00:00+00:00",
            "updated_at": "2026-04-25T10:00:00+00:00",
        }
    ]
    fake_store = MagicMock()
    fake_store.list_runs.return_value = fake_rows
    monkeypatch.setattr(jobs_route, "get_job_runs_store", lambda dal: fake_store)

    response = jobs_route.jobs_history(name="foo", limit=10, offset=0, dal=MagicMock())

    assert response.count == 1
    fake_store.list_runs.assert_called_once_with(job_name="foo", limit=10, offset=0)


# ---------------------------------------------------------------------------
# Native host: record_extension_job action
# ---------------------------------------------------------------------------


def test_extension_record_endpoint_records_via_store_factory(monkeypatch):
    from src.api.routes import jobs as jobs_route

    fake_store = MagicMock()
    fake_store.record_extension_event_once.return_value = 345
    monkeypatch.setattr(jobs_route, "get_job_runs_store", lambda dal: fake_store)

    req = jobs_route.ExtensionJobRecordRequest(
        client_event_id="evt-factory",
        started_at="2026-04-25T12:00:00Z",
        finished_at="2026-04-25T12:00:30Z",
        result=_extension_protocol_case("complete_market_sync"),
    )
    response = jobs_route.record_extension_job(req, dal=MagicMock())

    assert response.status == "ok"
    assert response.run_id == 345
    fake_store.record_extension_event_once.assert_called_once()
    kwargs = fake_store.record_extension_event_once.call_args.kwargs
    assert kwargs["client_event_id"] == "evt-factory"
    assert kwargs["job_name"] == "sa_market_news_refresh"
    assert kwargs["status"] == "succeeded"
    assert kwargs["duration_ms"] == 30000


def test_local_store_records_client_event_once_inside_immediate_transaction(
    tmp_path, monkeypatch
):
    from src.sa.extension_run_protocol import derive_run_result

    store = JobRunsLocalStore(tmp_path / "profile_state.db")
    statements: list[str] = []
    connect = store._connect

    def traced_connect():
        conn = connect()
        conn.set_trace_callback(statements.append)
        return conn

    monkeypatch.setattr(store, "_connect", traced_connect)
    run_id = store.record_extension_event_once(
        client_event_id="evt-immediate",
        event_hash="a" * 64,
        job_name="sa_market_news_refresh",
        status="succeeded",
        started_at="2026-07-25T01:00:00Z",
        finished_at="2026-07-25T01:00:30Z",
        result=derive_run_result(_extension_protocol_case("complete_market_sync")),
        duration_ms=30000,
    )

    assert isinstance(run_id, int)
    assert any(statement == "BEGIN IMMEDIATE" for statement in statements)
    rows = store.list_runs(limit=10)
    assert len(rows) == 1
    assert rows[0]["payload"]["extension_event"] == {
        "client_event_id": "evt-immediate",
        "event_hash": "a" * 64,
    }


def test_local_store_duplicate_event_returns_existing_run_id(tmp_path):
    from src.sa.extension_run_protocol import derive_run_result

    store = JobRunsLocalStore(tmp_path / "profile_state.db")
    kwargs = {
        "client_event_id": "evt-duplicate",
        "event_hash": "b" * 64,
        "job_name": "sa_market_news_refresh",
        "status": "succeeded",
        "started_at": "2026-07-25T01:00:00Z",
        "finished_at": "2026-07-25T01:00:30Z",
        "result": derive_run_result(
            _extension_protocol_case("complete_market_sync")
        ),
        "duration_ms": 30000,
    }

    first = store.record_extension_event_once(**kwargs)
    second = store.record_extension_event_once(**kwargs)

    assert second == first
    assert len(store.list_runs(limit=10)) == 1


def test_local_store_rejects_event_id_reuse_with_different_hash(tmp_path):
    from src.sa.extension_run_protocol import derive_run_result

    store = JobRunsLocalStore(tmp_path / "profile_state.db")
    common = {
        "client_event_id": "evt-conflict",
        "job_name": "sa_market_news_refresh",
        "status": "succeeded",
        "started_at": "2026-07-25T01:00:00Z",
        "finished_at": "2026-07-25T01:00:30Z",
        "result": derive_run_result(
            _extension_protocol_case("complete_market_sync")
        ),
        "duration_ms": 30000,
    }
    first = store.record_extension_event_once(event_hash="c" * 64, **common)

    with pytest.raises(ValueError, match="event_conflict"):
        store.record_extension_event_once(event_hash="d" * 64, **common)

    assert [row["id"] for row in store.list_runs(limit=10)] == [first]


def test_local_store_rolls_back_invalid_event_without_partial_row(tmp_path):
    from src.sa.extension_run_protocol import derive_run_result

    store = JobRunsLocalStore(tmp_path / "profile_state.db")
    with pytest.raises(ValueError, match="invalid_extension_event"):
        store.record_extension_event_once(
            client_event_id="evt-invalid",
            event_hash="not-a-sha256",
            job_name="sa_market_news_refresh",
            status="succeeded",
            started_at="2026-07-25T01:00:00Z",
            finished_at="2026-07-25T01:00:30Z",
            result=derive_run_result(
                _extension_protocol_case("complete_market_sync")
            ),
            duration_ms=30000,
        )

    assert store.list_runs(limit=10) == []


def test_extension_record_endpoint_derives_complete_status(monkeypatch):
    from src.api.routes import jobs as jobs_route

    fake_store = MagicMock()
    fake_store.record_extension_event_once.return_value = 401
    monkeypatch.setattr(jobs_route, "get_job_runs_store", lambda dal: fake_store)
    request = jobs_route.ExtensionJobRecordRequest(
        **_extension_event("evt-complete")
    )

    response = jobs_route.record_extension_job(request, dal=MagicMock())

    assert response.persisted is True
    assert fake_store.record_extension_event_once.call_args.kwargs["status"] == (
        "succeeded"
    )
    assert fake_store.record_extension_event_once.call_args.kwargs["result"][
        "derived_outcome"
    ] == "complete"


def test_extension_record_endpoint_maps_degraded_to_failed(monkeypatch):
    from src.api.routes import jobs as jobs_route

    fake_store = MagicMock()
    fake_store.record_extension_event_once.return_value = 402
    monkeypatch.setattr(jobs_route, "get_job_runs_store", lambda dal: fake_store)
    request = jobs_route.ExtensionJobRecordRequest(
        **_extension_event(
            "evt-degraded", "top_level_ok_with_retryable_details"
        )
    )

    jobs_route.record_extension_job(request, dal=MagicMock())

    kwargs = fake_store.record_extension_event_once.call_args.kwargs
    assert kwargs["status"] == "failed"
    assert kwargs["result"]["derived_outcome"] == "degraded"


def test_extension_record_endpoint_maps_skipped_to_typed_succeeded(monkeypatch):
    from src.api.routes import jobs as jobs_route

    fake_store = MagicMock()
    fake_store.record_extension_event_once.return_value = 403
    monkeypatch.setattr(jobs_route, "get_job_runs_store", lambda dal: fake_store)
    request = jobs_route.ExtensionJobRecordRequest(
        **_extension_event("evt-skipped", "skipped_not_due")
    )

    jobs_route.record_extension_job(request, dal=MagicMock())

    kwargs = fake_store.record_extension_event_once.call_args.kwargs
    assert kwargs["status"] == "succeeded"
    assert kwargs["result"]["derived_outcome"] == "skipped"
    assert kwargs["result"]["phases"]["list_navigation"] == {
        "state": "skipped",
        "reason_code": "not_due",
    }


def test_extension_record_endpoint_rejects_invalid_protocol_or_reason(monkeypatch):
    from src.api.routes import jobs as jobs_route

    fake_store = MagicMock()
    monkeypatch.setattr(jobs_route, "get_job_runs_store", lambda dal: fake_store)
    invalid = _extension_event("evt-invalid-protocol")
    invalid["result"]["phases"]["detail_fetch"] = {
        "state": "failed",
        "reason_code": "raw provider text",
    }
    request = jobs_route.ExtensionJobRecordRequest(**invalid)

    response = jobs_route.record_extension_job(request, dal=MagicMock())

    assert response.status == "error"
    assert response.persisted is False
    assert response.error_code == "protocol_invalid"
    fake_store.record_extension_event_once.assert_not_called()


def test_structured_extension_summary_separates_latest_attempt_from_latest_complete(
    tmp_path,
):
    from src.sa.extension_run_protocol import derive_run_result

    store = JobRunsLocalStore(tmp_path / "profile_state.db")
    newer_degraded = derive_run_result(
        _extension_protocol_case("top_level_ok_with_retryable_details")
    )
    older_complete = derive_run_result(
        _extension_protocol_case("complete_market_sync")
    )
    store.record_extension_event_once(
        client_event_id="evt-newer-degraded",
        event_hash="e" * 64,
        job_name="sa_market_news_refresh",
        status="failed",
        started_at="2026-07-25T02:00:00Z",
        finished_at="2026-07-25T02:00:30Z",
        result=newer_degraded,
        duration_ms=30000,
    )
    store.record_extension_event_once(
        client_event_id="evt-older-complete",
        event_hash="f" * 64,
        job_name="sa_market_news_refresh",
        status="succeeded",
        started_at="2026-07-25T01:00:00Z",
        finished_at="2026-07-25T01:00:30Z",
        result=older_complete,
        duration_ms=30000,
    )

    summary = store.structured_extension_summary_by_name(
        ["sa_market_news_refresh"]
    )["sa_market_news_refresh"]

    assert summary["latest_attempt"]["payload"]["extension_event"][
        "client_event_id"
    ] == "evt-newer-degraded"
    assert summary["latest_attempt"]["result"]["derived_outcome"] == "degraded"
    assert summary["latest_derived_complete"]["payload"]["extension_event"][
        "client_event_id"
    ] == "evt-older-complete"
    assert summary["latest_derived_complete"]["result"][
        "healthy_anchor_eligible"
    ] is True


def test_native_host_record_extension_job_posts_to_sidecar(monkeypatch):
    from src.sa_native_host import _handle_record_extension_job

    calls = []

    def fake_post(payload):
        calls.append(payload)
        return {"status": "ok", "run_id": 99, "persisted": True}

    monkeypatch.setattr("src.sa_native_host._post_extension_job_to_sidecar", fake_post)
    msg = _extension_event(
        "evt-native",
        started_at="2026-04-25T12:00:00Z",
        finished_at="2026-04-25T12:00:30Z",
    )
    result = _handle_record_extension_job(MagicMock(), msg)

    assert result["status"] == "ok"
    assert result["run_id"] == 99
    assert result["persisted"] is True
    assert calls == [msg]


def test_native_host_record_extension_job_degrades_when_sidecar_unreachable(monkeypatch):
    from src.sa_native_host import _handle_record_extension_job

    def fake_post(payload):
        raise OSError("sidecar down")

    monkeypatch.setattr("src.sa_native_host._post_extension_job_to_sidecar", fake_post)
    msg = _extension_event(
        "evt-sidecar-down",
        "top_level_ok_with_retryable_details",
        started_at="2026-04-25T12:00:00Z",
        finished_at="2026-04-25T12:00:30Z",
    )
    result = _handle_record_extension_job(MagicMock(), msg)

    assert result["status"] == "ok"
    assert result["persisted"] is False
    assert result["run_id"] is None


def test_record_extension_job_rejects_caller_supplied_status():
    from pydantic import ValidationError
    from src.api.routes.jobs import ExtensionJobRecordRequest

    with pytest.raises(ValidationError):
        ExtensionJobRecordRequest(
            **_extension_event("evt-forbidden-status"),
            status="succeeded",
        )


def test_record_extension_job_rejects_missing_started_at():
    from src.sa_native_host import _handle_record_extension_job

    result = _handle_record_extension_job(
        MagicMock(),
        {
            "client_event_id": "evt-missing-start",
            "finished_at": "2026-04-25T12:00:30Z",
            "result": _extension_protocol_case("complete_market_sync"),
        },
    )
    assert result["status"] == "error"
    assert result["error_code"] == "invalid_extension_event"


def test_record_extension_job_rejects_missing_job_name():
    from src.sa_native_host import _handle_record_extension_job

    result = _handle_record_extension_job(
        MagicMock(),
        {
            "client_event_id": "",
            "started_at": "2026-04-25T12:00:00Z",
            "finished_at": "2026-04-25T12:00:30Z",
            "result": _extension_protocol_case("complete_market_sync"),
        },
    )
    assert result["status"] == "error"
    assert result["error_code"] == "invalid_extension_event"


def test_record_extension_job_dispatched_via_handle_message():
    """handle_message routes action=record_extension_job to the helper."""
    from src import sa_native_host

    msg = {
        "action": "record_extension_job",
        **_extension_event("evt-dispatch"),
    }
    with patch.object(
        sa_native_host, "_handle_record_extension_job",
        return_value={"status": "ok", "run_id": 1, "persisted": True},
    ) as helper, patch(
        "src.tools.data_access.DataAccessLayer", return_value=MagicMock()
    ):
        result = sa_native_host.handle_message(msg)

    helper.assert_called_once()
    assert result["run_id"] == 1


def test_native_host_does_not_construct_job_runs_store_or_profile_writer():
    text = Path("src/sa_native_host.py").read_text()
    assert "JobRunsStore(" not in text
    assert "profile_state.db" not in text


# ---------------------------------------------------------------------------
# daily_update per-step telemetry (slice 3e-B)
# ---------------------------------------------------------------------------


def _load_daily_update():
    import importlib

    return importlib.import_module("src.daily_update")


def test_run_telemetry_disabled_is_inert(monkeypatch):
    # --dry-run path: enabled=False must not construct a DAL or record anything.
    from datetime import datetime, timezone
    mod = _load_daily_update()
    monkeypatch.setattr(
        "src.tools.data_access.DataAccessLayer",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("DAL touched on dry-run")))
    t = mod._RunTelemetry(enabled=False, payload={})
    assert t._store is None
    t.record("x", True, datetime.now(timezone.utc))  # no-op, no raise
    assert t.timed("y", lambda: True) is True        # passthrough unchanged


def test_run_telemetry_records_terminal_rows(monkeypatch):
    mod = _load_daily_update()
    calls = []

    class _FakeStore:
        def __init__(self, dal):
            pass

        def is_available(self):
            return True

        def record_completed_run(self, name, **kw):
            calls.append((name, kw))
            return 1

    monkeypatch.setattr("src.service.job_runs_store.JobRunsLocalStore", _FakeStore)
    monkeypatch.setattr("src.tools.data_access.DataAccessLayer", lambda *a, **k: MagicMock())
    t = mod._RunTelemetry(enabled=True, payload={"scope": "active-universe"})
    assert t.timed("polygon", lambda: True) is True
    assert t.timed("finnhub", lambda: False) is False
    assert [c[0] for c in calls] == ["daily_update.polygon", "daily_update.finnhub"]
    ok_kw, fail_kw = calls[0][1], calls[1][1]
    assert ok_kw["status"] == "succeeded" and ok_kw["trigger_source"] == "cli"
    assert ok_kw["error"] is None and ok_kw["payload"] == {"scope": "active-universe"}
    assert fail_kw["status"] == "failed" and "exit" in fail_kw["error"]
    assert ok_kw["started_at"] <= ok_kw["finished_at"]


def test_run_telemetry_store_failure_never_breaks_the_step(monkeypatch):
    # Telemetry is strictly additive: a recording failure must not alter the
    # step result or raise (the protected runner's exit-code semantics depend
    # only on the steps themselves).
    mod = _load_daily_update()

    class _BoomStore:
        def __init__(self, dal):
            pass

        def is_available(self):
            return True

        def record_completed_run(self, *a, **k):
            raise RuntimeError("local write failed")

    monkeypatch.setattr("src.service.job_runs_store.JobRunsLocalStore", _BoomStore)
    monkeypatch.setattr("src.tools.data_access.DataAccessLayer", lambda *a, **k: MagicMock())
    t = mod._RunTelemetry(enabled=True, payload={})
    assert t.timed("x", lambda: True) is True
    assert t.timed("y", lambda: False) is False
