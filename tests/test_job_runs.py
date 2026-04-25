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

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.service import jobs as jobs_module
from src.service.job_runs_store import JobRunsStore, _serialize_row


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db_dal():
    """DAL whose backend looks like DatabaseBackend (has _get_conn)."""
    dal = MagicMock()
    backend = MagicMock()
    backend._get_conn = MagicMock()
    dal._backend = backend
    return dal, backend


def _make_file_dal():
    """DAL whose backend looks like FileBackend (no _get_conn)."""
    dal = MagicMock()
    backend = object()  # bare object, no _get_conn
    dal._backend = backend
    return dal


def _mock_cursor(conn, *, fetchone=None, fetchall=None, rowcount=1):
    cur = MagicMock()
    cur.fetchone.return_value = fetchone
    cur.fetchall.return_value = fetchall or []
    cur.rowcount = rowcount
    cur.__enter__ = MagicMock(return_value=cur)
    cur.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value = cur
    return cur


# ---------------------------------------------------------------------------
# Availability gating
# ---------------------------------------------------------------------------


def test_store_unavailable_with_no_backend():
    dal = MagicMock()
    dal._backend = None
    store = JobRunsStore(dal)
    assert store.is_available() is False
    assert store.create_run("any") is None
    assert store.finish_run(1, status="succeeded") is False
    assert store.list_runs() == []
    assert store.latest_runs_by_name() == {}


def test_store_unavailable_with_filebackend():
    dal = _make_file_dal()
    store = JobRunsStore(dal)
    assert store.is_available() is False
    assert store.create_run("any") is None


def test_store_available_with_database_backend():
    dal, _ = _make_db_dal()
    store = JobRunsStore(dal)
    assert store.is_available() is True


# ---------------------------------------------------------------------------
# create_run
# ---------------------------------------------------------------------------


def test_create_run_returns_inserted_id():
    dal, backend = _make_db_dal()
    conn = MagicMock()
    backend._get_conn.return_value = conn
    _mock_cursor(conn, fetchone=(42,))

    store = JobRunsStore(dal)
    run_id = store.create_run("foo", trigger_source="cli", payload={"x": 1})

    assert run_id == 42


def test_create_run_swallows_db_error():
    dal, backend = _make_db_dal()
    backend._get_conn.side_effect = RuntimeError("conn down")

    store = JobRunsStore(dal)
    assert store.create_run("foo") is None  # no exception


# ---------------------------------------------------------------------------
# finish_run
# ---------------------------------------------------------------------------


def test_finish_run_rejects_running_status():
    dal, _ = _make_db_dal()
    store = JobRunsStore(dal)
    with pytest.raises(ValueError, match="terminal"):
        store.finish_run(1, status="running")


def test_finish_run_rejects_unknown_status():
    dal, _ = _make_db_dal()
    store = JobRunsStore(dal)
    with pytest.raises(ValueError, match="invalid"):
        store.finish_run(1, status="bogus")


def test_finish_run_returns_false_when_run_id_none():
    dal, _ = _make_db_dal()
    store = JobRunsStore(dal)
    assert store.finish_run(None, status="succeeded") is False


def test_finish_run_updates_row():
    dal, backend = _make_db_dal()
    conn = MagicMock()
    backend._get_conn.return_value = conn
    cur = _mock_cursor(conn, rowcount=1)

    store = JobRunsStore(dal)
    ok = store.finish_run(
        7, status="succeeded", message="42 articles", result={"count": 42}
    )
    assert ok is True
    # Verify the parameters threaded through
    args = cur.execute.call_args[0]
    assert "UPDATE job_runs" in args[0]
    assert args[1][0] == "succeeded"  # status param
    assert args[1][1] == "42 articles"  # message param


def test_finish_run_swallows_db_error():
    dal, backend = _make_db_dal()
    backend._get_conn.side_effect = RuntimeError("conn down")

    store = JobRunsStore(dal)
    assert store.finish_run(1, status="failed", error="boom") is False


# ---------------------------------------------------------------------------
# list_runs / latest_runs_by_name
# ---------------------------------------------------------------------------


def test_list_runs_returns_serialized_rows():
    dal, backend = _make_db_dal()
    conn = MagicMock()
    backend._get_conn.return_value = conn
    _mock_cursor(
        conn,
        fetchall=[
            {
                "id": 1,
                "job_name": "foo",
                "status": "succeeded",
                "trigger_source": "api",
                "payload": {},
                "result": {"count": 1},
                "message": "ok",
                "error": None,
                "started_at": datetime(2026, 4, 25, 10, 0, tzinfo=timezone.utc),
                "finished_at": datetime(2026, 4, 25, 10, 1, tzinfo=timezone.utc),
                "duration_ms": 60000,
                "created_at": datetime(2026, 4, 25, 10, 0, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 4, 25, 10, 1, tzinfo=timezone.utc),
            }
        ],
    )

    store = JobRunsStore(dal)
    rows = store.list_runs(job_name="foo", limit=10, offset=0)

    assert len(rows) == 1
    row = rows[0]
    assert row["job_name"] == "foo"
    assert row["status"] == "succeeded"
    assert row["started_at"] == "2026-04-25T10:00:00+00:00"


def test_list_runs_clamps_limit_and_offset():
    dal, backend = _make_db_dal()
    conn = MagicMock()
    backend._get_conn.return_value = conn
    cur = _mock_cursor(conn, fetchall=[])

    store = JobRunsStore(dal)
    store.list_runs(limit=5000, offset=-3)

    sql_params = cur.execute.call_args[0][1]
    assert sql_params == (200, 0)  # clamped


def test_latest_runs_by_name_keys_by_job_name():
    dal, backend = _make_db_dal()
    conn = MagicMock()
    backend._get_conn.return_value = conn
    _mock_cursor(
        conn,
        fetchall=[
            {
                "id": 1, "job_name": "a", "status": "succeeded",
                "trigger_source": "api", "payload": {}, "result": None,
                "message": None, "error": None,
                "started_at": datetime(2026, 4, 25, tzinfo=timezone.utc),
                "finished_at": None, "duration_ms": None,
                "created_at": datetime(2026, 4, 25, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 4, 25, tzinfo=timezone.utc),
            },
            {
                "id": 2, "job_name": "b", "status": "running",
                "trigger_source": "scheduler", "payload": {}, "result": None,
                "message": None, "error": None,
                "started_at": datetime(2026, 4, 25, tzinfo=timezone.utc),
                "finished_at": None, "duration_ms": None,
                "created_at": datetime(2026, 4, 25, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 4, 25, tzinfo=timezone.utc),
            },
        ],
    )
    store = JobRunsStore(dal)
    out = store.latest_runs_by_name()
    assert set(out.keys()) == {"a", "b"}
    assert out["a"]["status"] == "succeeded"
    assert out["b"]["status"] == "running"


def test_latest_runs_by_name_swallows_db_error():
    dal, backend = _make_db_dal()
    backend._get_conn.side_effect = RuntimeError("down")
    assert JobRunsStore(dal).latest_runs_by_name() == {}


def test_serialize_row_converts_datetimes():
    row = {
        "started_at": datetime(2026, 4, 25, 10, 0, tzinfo=timezone.utc),
        "finished_at": None,
        "created_at": datetime(2026, 4, 25, 10, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 4, 25, 10, 0, tzinfo=timezone.utc),
        "other": "kept",
    }
    out = _serialize_row(row)
    assert out["started_at"] == "2026-04-25T10:00:00+00:00"
    assert out["finished_at"] is None
    assert out["other"] == "kept"


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
        "message": "Analysis pipeline ok=3/3",
        "result": {"success_count": 3},
        "error": None,
    }

    with patch.object(
        JobRunsStore, "is_available", return_value=True,
    ), patch.object(
        JobRunsStore,
        "latest_runs_by_name",
        return_value={"analysis_watchlist_batch": db_row},
    ):
        out = jobs_module.list_jobs_status(dal)

    by_name = {j["name"]: j for j in out}
    pipeline = by_name["analysis_watchlist_batch"]
    assert pipeline["last_status"] == "succeeded"
    assert pipeline["last_message"] == "Analysis pipeline ok=3/3"
    assert pipeline["last_started_at"] == "2026-04-25T10:00:00+00:00"


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
    dal, backend = _make_db_dal()
    dal.get_watchlist.return_value = MagicMock(tickers=[])
    backend._get_conn.side_effect = RuntimeError("conn down")

    out = jobs_module.list_jobs_status(dal)
    # All jobs should appear with at least the never_run default
    statuses = {j["name"]: j["last_status"] for j in out}
    assert "analysis_watchlist_batch" in statuses
    # Either process-local cached value or "never_run" — both acceptable
    assert statuses["analysis_watchlist_batch"] in {"never_run", "succeeded", "failed", "running"}


# ---------------------------------------------------------------------------
# _summarize_result heuristics
# ---------------------------------------------------------------------------


def test_summarize_analysis_pipeline_result():
    msg = jobs_module._summarize_result(
        "analysis_watchlist_batch",
        {"success_count": 5, "processed_count": 6, "persisted_count": 2},
    )
    assert "ok=5/6" in msg
    assert "2 report" in msg


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
    msg = jobs_module._summarize_result("analysis_watchlist_batch", "not a dict")
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

    fake_result = {"success_count": 1, "processed_count": 1, "persisted_count": 0, "items": []}

    with patch.object(JobRunsStore, "create_run", fake_create_run), \
         patch.object(JobRunsStore, "finish_run", fake_finish_run), \
         patch.object(jobs_module, "_run_analysis_watchlist_batch", return_value=fake_result):
        result = jobs_module.run_job(
            "analysis_watchlist_batch", dal=dal, trigger_source="cli",
        )

    assert result.status == "succeeded"
    assert len(create_calls) == 1
    assert create_calls[0][0] == "analysis_watchlist_batch"
    assert create_calls[0][1]["trigger_source"] == "cli"
    assert len(finish_calls) == 1
    assert finish_calls[0][0] == 99
    assert finish_calls[0][1]["status"] == "succeeded"
    assert "ok=1/1" in finish_calls[0][1]["message"]


def test_run_job_persists_failure():
    dal, backend = _make_db_dal()
    dal.get_watchlist.return_value = MagicMock(tickers=["NVDA"])

    finish_calls: list = []

    def fake_create_run(self, name, **kwargs):
        return 100

    def fake_finish_run(self, run_id, **kwargs):
        finish_calls.append((run_id, kwargs))
        return True

    with patch.object(JobRunsStore, "create_run", fake_create_run), \
         patch.object(JobRunsStore, "finish_run", fake_finish_run), \
         patch.object(
             jobs_module, "_run_analysis_watchlist_batch",
             side_effect=RuntimeError("boom"),
         ):
        with pytest.raises(RuntimeError, match="boom"):
            jobs_module.run_job("analysis_watchlist_batch", dal=dal)

    assert len(finish_calls) == 1
    assert finish_calls[0][0] == 100
    assert finish_calls[0][1]["status"] == "failed"
    assert finish_calls[0][1]["error"] == "boom"


def test_run_job_continues_when_create_run_returns_none():
    """Persistence failure must not block the job."""
    dal = _make_file_dal()  # store unavailable → create_run returns None
    dal.get_watchlist.return_value = MagicMock(tickers=["NVDA"])

    fake_result = {"success_count": 1, "processed_count": 1, "persisted_count": 0, "items": []}
    with patch.object(jobs_module, "_run_analysis_watchlist_batch", return_value=fake_result):
        result = jobs_module.run_job("analysis_watchlist_batch", dal=dal)
    assert result.status == "succeeded"


# ---------------------------------------------------------------------------
# /jobs/history endpoint
# ---------------------------------------------------------------------------


def test_jobs_history_endpoint_returns_rows_from_store():
    from fastapi.testclient import TestClient
    from src.api.app import create_app
    from src.api.dependencies import get_dal

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

    app = create_app()
    app.dependency_overrides[get_dal] = lambda: MagicMock()
    try:
        with patch.object(JobRunsStore, "list_runs", return_value=fake_rows):
            with TestClient(app) as client:
                r = client.get("/jobs/history?name=foo&limit=10&offset=0")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 1
        assert data["limit"] == 10
        assert data["offset"] == 0
        assert data["runs"][0]["job_name"] == "foo"
    finally:
        app.dependency_overrides.clear()


def test_jobs_history_endpoint_returns_empty_when_unavailable():
    from fastapi.testclient import TestClient
    from src.api.app import create_app
    from src.api.dependencies import get_dal

    app = create_app()
    app.dependency_overrides[get_dal] = lambda: MagicMock(_backend=None)
    try:
        with TestClient(app) as client:
            r = client.get("/jobs/history")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] == 0
        assert data["runs"] == []
    finally:
        app.dependency_overrides.clear()