"""Macro scheduler outcomes with synthetic providers and real temporary telemetry."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.macro_calendar.finnhub_ingestion import FinnhubIngestionStats
from src.macro_calendar.fred_ingestion import IngestionStats


MACRO_JOBS = (
    ("fred_series", "fetch_fred_series", "observations_upserted"),
    ("fred_release_dates", "fetch_fred_release_dates", "release_dates_upserted"),
    ("finnhub_economic_calendar", "fetch_economic_calendar_recent", "events_inserted"),
    ("finnhub_earnings_calendar", "fetch_earnings_calendar", "events_inserted"),
    ("finnhub_ipo_calendar", "fetch_ipo_calendar", "events_inserted"),
)
SOURCE_IDS = [source for source, _, _ in MACRO_JOBS]
NAMED_MACRO_JOBS = MACRO_JOBS + (
    ("finnhub_economic_calendar", "fetch_economic_calendar_backfill", "events_inserted"),
)
COMPLETED_COUNTERS = [
    (source, counter)
    for source, _, first_counter in MACRO_JOBS
    for counter in (
        (first_counter,) if source.startswith("fred_")
        else ("events_inserted", "events_mutated", "events_unchanged")
    )
]
CANARY = "synthetic-only-provider-secret"
RAW_ERROR = f"GET https://provider.invalid/?api_key={CANARY}&token={CANARY} failed"


def _stats(source, **updates):
    stats = (
        IngestionStats().to_dict() if source.startswith("fred_")
        else FinnhubIngestionStats().to_dict()
    )
    stats.update(updates)
    return stats


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    import src.macro_calendar.execution as execution
    import src.service.data_scheduler as scheduler
    import src.service.jobs as jobs
    from src.api.routes import jobs as job_routes, schedule as schedule_routes
    from src.profile_state import ProfileStateStore
    from src.scheduler_state import SchedulerStateStore
    from src.service.job_runs_store import JobRunsLocalStore

    profile_db = tmp_path / "profile_state.db"
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_db))
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    state = SchedulerStateStore(profile_db)
    runs = JobRunsLocalStore(profile_db)
    profile = ProfileStateStore(profile_db)
    dal = SimpleNamespace(get_watchlist=lambda **kwargs: SimpleNamespace(tickers=[]))
    monkeypatch.setattr(scheduler, "_state_store", lambda: state)
    monkeypatch.setattr(scheduler, "_store", lambda: profile)
    monkeypatch.setattr(scheduler, "_LAST_ATTEMPT", {})
    monkeypatch.setattr(scheduler, "_LAST_RESULT", {})
    monkeypatch.setattr(scheduler, "logger", Mock())
    for source in SOURCE_IDS:
        monkeypatch.setitem(scheduler._SOURCE_LOCKS, source, threading.Lock())
        monkeypatch.setitem(
            scheduler._SOURCE_FLOCKS, source, scheduler._FileLock(f"source_{source}")
        )
    monkeypatch.setattr(scheduler, "_provider_config_missing_for_source", lambda source: None)
    monkeypatch.setattr(
        "src.provider_config_runtime.provider_config_setup_state",
        lambda: SimpleNamespace(required=False, code=None, reason=None),
    )
    monkeypatch.setattr("src.api.dependencies.get_dal", lambda: dal)
    monkeypatch.setattr("src.service.job_runs_store.get_job_runs_store", lambda dal: runs)
    monkeypatch.setattr(jobs, "get_job_runs_store", lambda dal: runs)
    monkeypatch.setattr(jobs, "_JOB_STATE", {
        name: jobs.JobExecutionState() for name in jobs._JOB_DEFINITIONS
    })
    monkeypatch.setattr(job_routes, "get_job_runs_store", lambda dal: runs)
    monkeypatch.setattr(
        jobs, "get_agent_config",
        lambda: SimpleNamespace(macro_calendar_enabled=True, sa_enabled=False),
    )

    def run(source, raw, trigger_source="scheduler"):
        executor = Mock(side_effect=raw) if isinstance(raw, Exception) else Mock(return_value=raw)
        monkeypatch.setattr(execution, "execute_macro_job", executor)
        result = scheduler.run_source(source, trigger_source=trigger_source)
        expected_job = next(job for src, job, _ in MACRO_JOBS if src == source)
        executor.assert_called_once()
        assert executor.call_args.args == (
            expected_job, dal, {"full_refresh": False} if source == "fred_series" else {},
        )
        assert executor.call_args.kwargs["writer_lease"] is not None
        assert not scheduler._SOURCE_LOCKS[source].locked()
        return result

    return SimpleNamespace(
        run=run, scheduler=scheduler, state=state, runs=runs, dal=dal,
        job_routes=job_routes, schedule_routes=schedule_routes, jobs=jobs,
    )


def _assert_outcome(runtime, source, result, status, error_code=None):
    assert result["status"] == status
    assert result["collect"]["status"] == status
    assert result.get("error") == error_code
    assert "continuation" not in result
    durable = runtime.state.get(source)
    assert durable["last_status"] == status
    assert durable["last_error"] == error_code
    assert durable["last_result"] == result
    assert durable["last_attempt"] is not None
    assert durable["continuation"] is None
    job = next(job for src, job, _ in MACRO_JOBS if src == source)
    history = runtime.job_routes.jobs_history(name=job, limit=50, offset=0, dal=runtime.dal)
    assert history.count == 1
    row = history.runs[0]
    assert row.status == ("succeeded" if status == "succeeded" else "failed")
    assert row.result == result
    assert row.error == row.message == error_code
    public = runtime.schedule_routes.get_schedule()["sources"][source]
    assert public["last_result"]["status"] == status
    assert public["durable_state"]["last_result"] == result
    jobs = runtime.job_routes.jobs_status(dal=runtime.dal).jobs
    job_status = next(item for item in jobs if item.name == job)
    assert job_status.last_status == row.status
    assert job_status.last_result == result
    return row


@pytest.mark.parametrize("source", SOURCE_IDS)
@pytest.mark.parametrize("trigger", ["scheduler", "api"])
def test_macro_returned_errors_without_completed_work_fail(runtime, source, trigger):
    raw = _stats(source, errors=[RAW_ERROR, "another synthetic provider error"])
    result = runtime.run(source, raw, trigger)
    row = _assert_outcome(runtime, source, result, "failed", "macro_collection_failed")
    assert row.trigger_source == trigger
    assert result["collect"]["error_count"] == 2
    assert result["collect"]["errors"] == ["macro_collection_error"] * 2
    assert runtime.runs.run_summary_by_name([row.job_name])[row.job_name]["last_success_at"] is None


@pytest.mark.parametrize("source,counter", COMPLETED_COUNTERS)
@pytest.mark.parametrize("trigger", ["scheduler", "api"])
def test_macro_returned_errors_with_completed_work_are_partial(runtime, source, counter, trigger):
    raw = _stats(source, **{counter: 3, "errors": [RAW_ERROR]})
    result = runtime.run(source, raw, trigger)
    row = _assert_outcome(runtime, source, result, "partial", "macro_collection_partial")
    assert row.trigger_source == trigger
    assert result["collect"][counter] == 3
    assert result["collect"]["error_count"] == 1
    assert runtime.runs.run_summary_by_name([row.job_name])[row.job_name]["last_success_at"] is None


@pytest.mark.parametrize("source", SOURCE_IDS)
def test_macro_empty_success_remains_succeeded(runtime, source):
    result = runtime.run(source, _stats(source))
    assert result["status"] == "succeeded"
    row = runtime.runs.latest_runs_by_name()[runtime.scheduler.job_name(source)]
    assert row["status"] == "succeeded"
    assert runtime.state.get(source)["last_status"] == "succeeded"
    assert result.get("error") is None


@pytest.mark.parametrize("source,counter", COMPLETED_COUNTERS)
def test_macro_success_preserves_upsert_and_unchanged_counts(runtime, source, counter):
    result = runtime.run(source, _stats(source, **{counter: 3}))
    _assert_outcome(runtime, source, result, "succeeded")
    assert result["collect"][counter] == 3
    assert result["collect"]["error_count"] == 0
    assert result["collect"]["errors"] == []


def test_fred_incremental_no_updates_remains_succeeded(runtime):
    result = runtime.run("fred_series", _stats("fred_series", series_processed=2))
    assert result["status"] == "succeeded"
    assert result["collect"]["series_processed"] == 2
    assert result["collect"]["observations_upserted"] == 0


@pytest.mark.parametrize("source", SOURCE_IDS)
def test_macro_processed_and_skipped_counts_are_not_completed_work(runtime, source):
    counts = (
        {"series_processed": 2, "series_skipped": 1, "observations_skipped_no_release": 1}
        if source.startswith("fred_") else {"events_skipped": 2}
    )
    result = runtime.run(source, _stats(source, **counts, errors=[RAW_ERROR]))
    _assert_outcome(runtime, source, result, "failed", "macro_collection_failed")
    for name, value in counts.items():
        assert result["collect"][name] == value


@pytest.mark.parametrize("source,wrong_counter", [
    ("fred_series", "release_dates_upserted"),
    ("fred_release_dates", "observations_upserted"),
])
def test_fred_completion_uses_only_the_job_owned_counter(runtime, source, wrong_counter):
    result = runtime.run(source, _stats(source, **{wrong_counter: 3}, errors=[RAW_ERROR]))
    _assert_outcome(runtime, source, result, "failed", "macro_collection_failed")


@pytest.mark.parametrize("source", SOURCE_IDS)
@pytest.mark.parametrize("raw", [None, {}, []], ids=["none", "empty-mapping", "list"])
def test_macro_missing_result_fails_closed(runtime, source, raw):
    result = runtime.run(source, raw)
    _assert_outcome(runtime, source, result, "failed", "macro_result_invalid")


@pytest.mark.parametrize("source,field", [
    (source, field) for source in SOURCE_IDS for field in _stats(source)
])
def test_macro_missing_required_stats_field_fails_closed(runtime, source, field):
    raw = _stats(source)
    del raw[field]
    result = runtime.run(source, raw)
    _assert_outcome(runtime, source, result, "failed", "macro_result_invalid")


@pytest.mark.parametrize("source,counter", [
    ("fred_series", "observations_upserted"),
    ("finnhub_ipo_calendar", "events_skipped"),
])
@pytest.mark.parametrize("bad_count", [None, -1, True, 0.5, "1", [], {}])
def test_macro_malformed_counter_fails_closed(runtime, source, counter, bad_count):
    result = runtime.run(source, _stats(source, **{counter: bad_count}))
    _assert_outcome(runtime, source, result, "failed", "macro_result_invalid")


@pytest.mark.parametrize("source", ["fred_series", "finnhub_ipo_calendar"])
@pytest.mark.parametrize("errors", [None, RAW_ERROR, {}, (), [None], [{"error": RAW_ERROR}]])
def test_macro_malformed_errors_fail_closed(runtime, source, errors):
    result = runtime.run(source, _stats(source, errors=errors))
    _assert_outcome(runtime, source, result, "failed", "macro_result_invalid")


@pytest.mark.parametrize("source,job,counter", MACRO_JOBS)
def test_macro_error_details_are_absent_from_all_projections(runtime, source, job, counter):
    raw = _stats(source, **{counter: 1}, errors=[RAW_ERROR])
    raw.update(status="succeeded", error_count=0, debug=RAW_ERROR, error=RAW_ERROR)
    result = runtime.run(source, raw)
    history = runtime.job_routes.jobs_history(name=job, limit=50, offset=0, dal=runtime.dal)
    projections = [
        result, runtime.state.get(source), runtime.scheduler._LAST_RESULT,
        runtime.schedule_routes.get_schedule(), history.model_dump(),
        runtime.job_routes.jobs_status(dal=runtime.dal).model_dump(),
        runtime.runs.latest_runs_by_name(),
    ]
    assert CANARY not in json.dumps(projections)
    assert CANARY not in str(runtime.scheduler.logger.mock_calls)
    _assert_outcome(runtime, source, result, "partial", "macro_collection_partial")
    assert result["collect"]["error_count"] == 1
    assert result["collect"]["errors"] == ["macro_collection_error"]
    assert "debug" not in result["collect"]
    assert "error" not in result["collect"]
    assert raw["errors"] == [RAW_ERROR]


@pytest.mark.parametrize("source", SOURCE_IDS)
def test_macro_raised_exception_uses_safe_error_code(runtime, source):
    result = runtime.run(source, RuntimeError(RAW_ERROR))
    assert result["status"] == "failed"
    assert result["error"] == "macro_collection_failed"
    assert runtime.state.get(source)["last_error"] == "macro_collection_failed"
    assert CANARY not in json.dumps(runtime.runs.latest_runs_by_name())
    assert CANARY not in json.dumps(runtime.schedule_routes.get_schedule())
    assert CANARY not in str(runtime.scheduler.logger.mock_calls)


def test_macro_partial_roundtrips_failed_audit_and_recovers(runtime):
    source, job = "fred_series", "fetch_fred_series"
    runtime.runs.record_completed_run(
        job, status="succeeded", started_at="2020-01-01T00:00:00Z",
        finished_at="2020-01-01T00:01:00Z",
    )
    prior_success = runtime.runs.run_summary_by_name([job])[job]["last_success_at"]
    partial = runtime.run(source, _stats(source, observations_upserted=2, errors=[RAW_ERROR]))
    assert partial["status"] == "partial"
    assert runtime.runs.run_summary_by_name([job])[job]["last_success_at"] == prior_success
    attempt = runtime.state.get(source)["last_attempt"]
    runtime.scheduler._LAST_RESULT.clear()
    runtime.scheduler._LAST_ATTEMPT.clear()
    restored = runtime.schedule_routes.get_schedule()["sources"][source]
    assert restored["last_result"] is None
    assert restored["durable_state"]["last_result"] == partial
    assert restored["durable_state"]["last_attempt"] == attempt
    assert restored["durable_state"]["last_status"] == "partial"
    assert restored["durable_state"]["continuation"] is None

    succeeded = runtime.run(source, _stats(source, series_processed=1))
    assert succeeded["status"] == succeeded["collect"]["status"] == "succeeded"
    assert succeeded["collect"]["error_count"] == 0
    assert runtime.state.get(source)["last_error"] is None
    assert runtime.state.get(source)["last_status"] == "succeeded"
    history = runtime.runs.list_runs(job_name=job, limit=50, offset=0)
    assert [row["status"] for row in history] == ["succeeded", "failed", "succeeded"]
    assert history[1]["result"] == partial
    assert history[1]["error"] == "macro_collection_partial"
    assert runtime.runs.run_summary_by_name([job])[job]["last_success_at"] == history[0]["finished_at"]


@pytest.mark.parametrize("source,job,counter", NAMED_MACRO_JOBS)
@pytest.mark.parametrize("count,has_error,status,error_code", [
    (0, True, "failed", "macro_collection_failed"),
    (2, True, "partial", "macro_collection_partial"),
    (0, False, "succeeded", None),
    (2, False, "succeeded", None),
])
def test_named_macro_api_normalizes_before_persistence(
    runtime, monkeypatch, source, job, counter, count, has_error, status, error_code,
):
    from src.macro_calendar import execution

    raw = _stats(source, **{counter: count}, errors=[RAW_ERROR] if has_error else [])
    raw.update(debug=RAW_ERROR, error=RAW_ERROR, status="succeeded", error_count=0)
    monkeypatch.setitem(execution._DISPATCH, job, lambda dal, params: raw)

    response = runtime.job_routes.run_named_job(job, dal=runtime.dal)

    audit_status = "succeeded" if status == "succeeded" else "failed"
    assert response.status == audit_status
    assert response.result["status"] == status
    assert response.result[counter] == count
    assert response.result["error_count"] == int(has_error)
    assert response.result["errors"] == (["macro_collection_error"] if has_error else [])
    assert response.result.get("error_code") == error_code
    history = runtime.job_routes.jobs_history(name=job, limit=50, offset=0, dal=runtime.dal)
    assert history.count == 1
    row = history.runs[0]
    assert row.status == audit_status
    assert row.result == response.result
    assert row.error == error_code
    assert row.message == response.message
    if has_error:
        assert row.message == error_code
        assert runtime.runs.run_summary_by_name([job])[job]["last_success_at"] is None
    projections = [
        response.model_dump(), history.model_dump(),
        runtime.job_routes.jobs_status(dal=runtime.dal).model_dump(),
        vars(runtime.jobs._JOB_STATE[job]),
    ]
    assert CANARY not in json.dumps(projections)
    assert raw["debug"] == RAW_ERROR


@pytest.mark.parametrize("source,job,counter", NAMED_MACRO_JOBS)
@pytest.mark.parametrize("raw", [None, {}, {"errors": [RAW_ERROR]}])
def test_named_macro_api_rejects_malformed_results(runtime, monkeypatch, source, job, counter, raw):
    from src.macro_calendar import execution

    monkeypatch.setitem(execution._DISPATCH, job, lambda dal, params: raw)
    response = runtime.job_routes.run_named_job(job, dal=runtime.dal)
    assert response.status == "failed"
    assert response.result == {"status": "failed", "error_code": "macro_result_invalid"}
    row = runtime.runs.latest_runs_by_name()[job]
    assert row["status"] == "failed"
    assert row["error"] == "macro_result_invalid"
    assert CANARY not in json.dumps(row)


@pytest.mark.parametrize("source,job,counter", NAMED_MACRO_JOBS)
@pytest.mark.parametrize("exception_type", [RuntimeError, ValueError])
def test_named_macro_api_sanitizes_raised_errors(
    runtime, monkeypatch, caplog, source, job, counter, exception_type,
):
    from fastapi import HTTPException
    from src.macro_calendar import execution

    def fail(dal, params):
        raise exception_type(RAW_ERROR)

    monkeypatch.setitem(execution._DISPATCH, job, fail)
    expected_exception = HTTPException if exception_type is ValueError else RuntimeError
    with pytest.raises(expected_exception) as caught:
        runtime.job_routes.run_named_job(job, dal=runtime.dal)
    if exception_type is ValueError:
        assert caught.value.status_code == 400
        assert caught.value.detail == "macro_collection_failed"
    else:
        assert str(caught.value) == "macro_collection_failed"
    row = runtime.runs.latest_runs_by_name()[job]
    assert row["status"] == "failed"
    assert row["error"] == row["message"] == "macro_collection_failed"
    assert CANARY not in json.dumps([
        row, vars(runtime.jobs._JOB_STATE[job]),
        runtime.job_routes.jobs_status(dal=runtime.dal).model_dump(),
    ])
    assert CANARY not in str(caught.value)
    assert CANARY not in caplog.text


def test_named_macro_partial_preserves_prior_success_and_recovers(runtime, monkeypatch):
    from src.macro_calendar import execution

    job = "fetch_fred_series"
    runtime.runs.record_completed_run(
        job, status="succeeded", started_at="2020-01-01T00:00:00Z",
        finished_at="2020-01-01T00:01:00Z",
    )
    prior = runtime.runs.run_summary_by_name([job])[job]["last_success_at"]
    raw = IngestionStats(observations_upserted=1, errors=[RAW_ERROR]).to_dict()
    monkeypatch.setitem(execution._DISPATCH, job, lambda dal, params: raw)
    response = runtime.job_routes.run_named_job(job, dal=runtime.dal)
    assert response.status == "failed"
    assert response.result["status"] == "partial"
    assert runtime.runs.run_summary_by_name([job])[job]["last_success_at"] == prior

    raw = IngestionStats(series_processed=1).to_dict()
    recovered = runtime.job_routes.run_named_job(job, dal=runtime.dal)
    assert recovered.status == recovered.result["status"] == "succeeded"
    assert recovered.result["errors"] == []
    rows = runtime.runs.list_runs(job_name=job, limit=50, offset=0)
    assert [row["status"] for row in rows] == ["succeeded", "failed", "succeeded"]
    assert rows[0]["error"] is None
    assert runtime.runs.run_summary_by_name([job])[job]["last_success_at"] == rows[0]["finished_at"]


class _SyntheticFRED:
    def __init__(self):
        self.empty = False
        self.observation_error = False

    def get_series_metadata(self, series_id):
        from data_sources.fred_client import FREDSeriesMetadata

        return FREDSeriesMetadata(series_id, "Synthetic series", "m", "percent", None, None)

    def get_observations(self, series_id, **kwargs):
        from data_sources.fred_client import FREDError, FREDObservation

        if self.observation_error:
            raise FREDError(RAW_ERROR)
        if self.empty:
            return []
        return [FREDObservation(date(2026, 9, 1), 1.0, date(2026, 9, 2), date(9999, 12, 31))]

    def get_release_dates(self, release_id, **kwargs):
        from data_sources.fred_client import FREDReleaseDate

        return [] if self.empty else [FREDReleaseDate(release_id, date(2026, 9, 2))]


@pytest.fixture
def fred_producer(runtime, tmp_path, monkeypatch):
    from src.macro_calendar import fred_ingestion as ingestion
    from src.macro_calendar.local_store import MacroCalendarLocalStore

    db = tmp_path / "macro_calendar.db"
    monkeypatch.setenv("ARKSCOPE_MACRO_CALENDAR_DB", str(db))
    store = MacroCalendarLocalStore(db)
    client = _SyntheticFRED()
    entries = []
    monkeypatch.setattr(ingestion, "FREDClient", lambda: client)
    monkeypatch.setattr(ingestion, "load_catalog", lambda *args: ingestion.Catalog(
        entries=entries, observation_start=date(2026, 1, 1), release_date_lookback_years=1,
    ))
    return SimpleNamespace(db=db, store=store, client=client, entries=entries)


FRED_WRITE_CASES = (
    ("macro_series", "latest_only", "fred_series", "observations_upserted"),
    ("macro_series", "full_vintages", "fred_series", "observations_upserted"),
    ("macro_observations", "latest_only", "fred_series", "observations_upserted"),
    ("macro_observations", "full_vintages", "fred_series", "observations_upserted"),
    ("macro_release_dates", "latest_only", "fred_release_dates", "release_dates_upserted"),
)


def _run_real_fred(runtime, source, entrypoint):
    job = "fetch_fred_series" if source == "fred_series" else "fetch_fred_release_dates"
    if entrypoint == "scheduler":
        result = runtime.scheduler.run_source(source)
        return result["collect"], runtime.runs.latest_runs_by_name()[job]
    response = runtime.job_routes.run_named_job(job, dal=runtime.dal)
    return response.result, runtime.runs.latest_runs_by_name()[job]


@pytest.mark.parametrize("table,strategy,source,counter", FRED_WRITE_CASES)
@pytest.mark.parametrize("completed", [0, 1])
@pytest.mark.parametrize("entrypoint", ["scheduler", "named"])
def test_real_fred_rejected_writes_are_not_empty_success(
    runtime, fred_producer, table, strategy, source, counter, completed, entrypoint,
):
    from src.macro_calendar.fred_ingestion import CatalogEntry

    fred_producer.entries.append(CatalogEntry("REJECT", strategy, 10))
    if completed:
        fred_producer.entries.append(CatalogEntry("ACCEPT", strategy, 20))
    predicate = "NEW.release_id = 10" if table == "macro_release_dates" else "NEW.series_id = 'REJECT'"
    with sqlite3.connect(fred_producer.db) as conn:
        conn.execute(f"""
            CREATE TRIGGER reject_synthetic BEFORE INSERT ON {table}
            WHEN {predicate} BEGIN SELECT RAISE(ABORT, 'synthetic write rejection'); END
        """)

    result, audit = _run_real_fred(runtime, source, entrypoint)

    assert audit["status"] == "failed"
    assert result["status"] == ("partial" if completed else "failed")
    assert result[counter] == completed
    assert result["error_count"] == 1
    with sqlite3.connect(fred_producer.db) as conn:
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == completed
    assert runtime.runs.run_summary_by_name([audit["job_name"]])[audit["job_name"]]["last_success_at"] is None


@pytest.mark.parametrize("source,strategy", [
    ("fred_series", "latest_only"), ("fred_series", "full_vintages"),
    ("fred_release_dates", "latest_only"),
])
@pytest.mark.parametrize("entrypoint", ["scheduler", "named"])
def test_real_fred_valid_empty_responses_remain_successful(
    runtime, fred_producer, source, strategy, entrypoint,
):
    from src.macro_calendar.fred_ingestion import CatalogEntry

    fred_producer.entries.append(CatalogEntry("ACCEPT", strategy, 20))
    fred_producer.client.empty = True
    result, audit = _run_real_fred(runtime, source, entrypoint)
    assert audit["status"] == "succeeded"
    assert result["errors"] == []
    assert result["observations_upserted"] == result["release_dates_upserted"] == 0


def test_real_fred_observation_failure_keeps_committed_metadata(runtime, fred_producer):
    from src.macro_calendar.fred_ingestion import CatalogEntry

    fred_producer.entries.append(CatalogEntry("ACCEPT", "latest_only", 20))
    fred_producer.client.observation_error = True
    result, audit = _run_real_fred(runtime, "fred_series", "scheduler")
    assert result["status"] == audit["status"] == "failed"
    assert result["observations_upserted"] == 0
    assert fred_producer.store.get_macro_series("ACCEPT")["units"] == "percent"
    assert CANARY not in json.dumps(audit)
