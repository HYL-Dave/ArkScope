"""Closed, bounded diagnostics for completed SA extension runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock

from src.api.routes import jobs as jobs_route
from src.sa.extension_run_protocol import derive_run_result
from src.service.job_runs_store import JobRunsLocalStore


_RUN_OUTCOMES = (
    Path(__file__).parent / "fixtures" / "sa_extension" / "run_outcomes.json"
)


def _protocol_result() -> dict:
    fixture = json.loads(_RUN_OUTCOMES.read_text(encoding="utf-8"))
    case = next(
        item for item in fixture["protocol_cases"]
        if item["name"] == "complete_market_sync"
    )
    return json.loads(json.dumps(case["input"]))


def _event(event_id: str, *, diagnostics=...) -> dict:
    event = {
        "client_event_id": event_id,
        "started_at": "2026-08-14T01:00:00Z",
        "finished_at": "2026-08-14T01:00:30Z",
        "result": _protocol_result(),
    }
    if diagnostics is not ...:
        event["extension_diagnostics"] = diagnostics
    return event


def _diagnostics(
    *,
    reason_code: str = "navigation_timeout",
    entries: list[dict] | None = None,
) -> dict:
    return {
        "schema_version": 1,
        "entries": entries if entries is not None else [
            {
                "occurred_at": "2026-08-14T01:00:10Z",
                "stage": "page_readiness",
                "reason_code": reason_code,
                "target_kind": "phase",
                "target_ref": "market-news-list",
                "retryable": True,
                "attempt_count": 2,
                "message": "Page readiness timed out.",
            }
        ],
        "omitted_count": 0,
    }


def _record(tmp_path, monkeypatch, event: dict):
    store = JobRunsLocalStore(tmp_path / "profile_state.db")
    monkeypatch.setattr(jobs_route, "get_job_runs_store", lambda dal: store)
    request = jobs_route.ExtensionJobRecordRequest(**event)
    response = jobs_route.record_extension_job(request, dal=MagicMock())
    return store, response


def _canonical_hash(document: dict) -> str:
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def test_valid_diagnostics_round_trip_into_payload_and_extended_hash(
    tmp_path, monkeypatch
):
    raw = _diagnostics()
    store, response = _record(tmp_path, monkeypatch, _event("evt-valid", diagnostics=raw))

    assert response.status == "ok"
    row = store.list_runs(limit=1)[0]
    projection = row["payload"]["extension_diagnostics"]
    assert projection == {
        "status": "recorded",
        "schema_version": 1,
        "entries": [
            {
                **raw["entries"][0],
                "occurred_at": "2026-08-14T01:00:10.000+00:00",
            }
        ],
        "omitted_count": 0,
    }
    expected_document = {
        "client_event_id": "evt-valid",
        "started_at": "2026-08-14T01:00:00.000+00:00",
        "finished_at": "2026-08-14T01:00:30.000+00:00",
        "result": derive_run_result(_protocol_result()),
        "extension_diagnostics": projection,
    }
    assert row["payload"]["extension_event"]["event_hash"] == _canonical_hash(
        expected_document
    )


def test_valid_empty_diagnostics_records_explicit_recorded_status(tmp_path, monkeypatch):
    store, response = _record(
        tmp_path,
        monkeypatch,
        _event("evt-empty", diagnostics=_diagnostics(entries=[])),
    )

    assert response.persisted is True
    assert store.list_runs(limit=1)[0]["payload"]["extension_diagnostics"] == {
        "status": "recorded",
        "schema_version": 1,
        "entries": [],
        "omitted_count": 0,
    }


def test_invalid_diagnostics_persist_terminal_result_with_fixed_rejection_marker(
    tmp_path, monkeypatch
):
    invalid = {**_diagnostics(), "unexpected": "must not persist"}
    store, response = _record(
        tmp_path,
        monkeypatch,
        _event("evt-invalid", diagnostics=invalid),
    )

    assert response.persisted is True
    row = store.list_runs(limit=1)[0]
    assert row["status"] == "succeeded"
    assert row["result"]["derived_outcome"] == "complete"
    assert row["payload"]["extension_diagnostics"] == {
        "status": "rejected",
        "error_code": "invalid_extension_diagnostics",
    }
    assert "must not persist" not in json.dumps(row, sort_keys=True)


def test_rejected_diagnostics_retry_deduplicates_without_raw_bytes(tmp_path, monkeypatch):
    store = JobRunsLocalStore(tmp_path / "profile_state.db")
    monkeypatch.setattr(jobs_route, "get_job_runs_store", lambda dal: store)
    first = _event(
        "evt-rejected-retry",
        diagnostics={**_diagnostics(), "raw_body": "FIRST-RAW-SENTINEL"},
    )
    second = _event(
        "evt-rejected-retry",
        diagnostics={**_diagnostics(), "authorization": "Bearer SECOND-SECRET"},
    )

    response1 = jobs_route.record_extension_job(
        jobs_route.ExtensionJobRecordRequest(**first), dal=MagicMock()
    )
    response2 = jobs_route.record_extension_job(
        jobs_route.ExtensionJobRecordRequest(**second), dal=MagicMock()
    )

    assert response2.run_id == response1.run_id
    rows = store.list_runs(limit=10)
    assert len(rows) == 1
    serialized = json.dumps(rows, sort_keys=True)
    assert "FIRST-RAW-SENTINEL" not in serialized
    assert "SECOND-SECRET" not in serialized


def test_changed_admitted_diagnostics_for_same_event_conflicts(tmp_path, monkeypatch):
    store = JobRunsLocalStore(tmp_path / "profile_state.db")
    monkeypatch.setattr(jobs_route, "get_job_runs_store", lambda dal: store)
    first = jobs_route.ExtensionJobRecordRequest(
        **_event("evt-changed", diagnostics=_diagnostics())
    )
    changed = jobs_route.ExtensionJobRecordRequest(
        **_event(
            "evt-changed",
            diagnostics=_diagnostics(reason_code="dom_not_ready"),
        )
    )

    assert jobs_route.record_extension_job(first, dal=MagicMock()).persisted is True
    response = jobs_route.record_extension_job(changed, dal=MagicMock())

    assert response.status == "error"
    assert response.error_code == "event_conflict"
    assert len(store.list_runs(limit=10)) == 1


def test_legacy_request_preserves_pre_diagnostics_hash_and_deduplicates(
    tmp_path, monkeypatch
):
    store = JobRunsLocalStore(tmp_path / "profile_state.db")
    event = _event("evt-legacy")
    result = derive_run_result(event["result"])
    legacy_document = {
        "client_event_id": event["client_event_id"],
        "started_at": "2026-08-14T01:00:00.000+00:00",
        "finished_at": "2026-08-14T01:00:30.000+00:00",
        "result": result,
    }
    old_run_id = store.record_extension_event_once(
        client_event_id=event["client_event_id"],
        event_hash=_canonical_hash(legacy_document),
        job_name=result["job_name"],
        status=result["db_status"],
        started_at=legacy_document["started_at"],
        finished_at=legacy_document["finished_at"],
        result=result,
        duration_ms=30000,
    )
    monkeypatch.setattr(jobs_route, "get_job_runs_store", lambda dal: store)

    duplicate = jobs_route.record_extension_job(
        jobs_route.ExtensionJobRecordRequest(**event), dal=MagicMock()
    )
    new_legacy = jobs_route.record_extension_job(
        jobs_route.ExtensionJobRecordRequest(**_event("evt-new-legacy")),
        dal=MagicMock(),
    )

    assert duplicate.run_id == old_run_id
    rows = store.list_runs(limit=10)
    old_row = next(row for row in rows if row["id"] == old_run_id)
    new_row = next(row for row in rows if row["id"] == new_legacy.run_id)
    assert "extension_diagnostics" not in old_row["payload"]
    assert new_row["payload"]["extension_diagnostics"] == {"status": "absent"}


def test_diagnostic_validator_rejects_unknown_fields_enums_and_time_bounds():
    from src.sa.extension_diagnostics import project_extension_diagnostics

    invalid_envelopes = [
        {**_diagnostics(), "unknown": 1},
        _diagnostics(entries=[{**_diagnostics()["entries"][0], "stage": "network"}]),
        _diagnostics(
            entries=[{**_diagnostics()["entries"][0], "reason_code": "free_text"}]
        ),
        _diagnostics(
            entries=[
                {
                    **_diagnostics()["entries"][0],
                    "occurred_at": "2026-08-14T01:01:00Z",
                }
            ]
        ),
        _diagnostics(
            entries=[
                {
                    **_diagnostics()["entries"][0],
                    "occurred_at": "2026-08-14T01:00:10",
                }
            ]
        ),
    ]

    for raw in invalid_envelopes:
        assert project_extension_diagnostics(
            raw,
            started_at="2026-08-14T01:00:00Z",
            finished_at="2026-08-14T01:00:30Z",
        ) == {
            "status": "rejected",
            "error_code": "invalid_extension_diagnostics",
        }


def test_diagnostic_validator_rejects_identifiers_sizes_and_secret_sentinels_atomically():
    from src.sa.extension_diagnostics import project_extension_diagnostics

    base = _diagnostics()["entries"][0]
    invalid_envelopes = [
        _diagnostics(entries=[{**base, "target_ref": "https://example.test/raw"}]),
        _diagnostics(entries=[{**base, "attempt_count": 0}]),
        _diagnostics(entries=[{**base, "message": "x" * 241}]),
        _diagnostics(entries=[dict(base) for _ in range(33)]),
        {**_diagnostics(), "omitted_count": 10001},
        _diagnostics(entries=[{**base, "message": "Bearer SECRET-TOKEN"}]),
        _diagnostics(entries=[{**base, "message": "user@example.test"}]),
        _diagnostics(entries=[{**base, "message": "/home/user/private.db"}]),
        _diagnostics(entries=[{**base, "message": "SELECT secret FROM credentials"}]),
        _diagnostics(entries=[{**base, "message": "<html>raw body</html>"}]),
    ]

    for raw in invalid_envelopes:
        projection = project_extension_diagnostics(
            raw,
            started_at="2026-08-14T01:00:00Z",
            finished_at="2026-08-14T01:00:30Z",
        )
        assert projection == {
            "status": "rejected",
            "error_code": "invalid_extension_diagnostics",
        }
        assert "Page readiness timed out" not in json.dumps(projection)


def test_completed_extension_reader_returns_latest_twenty_allowlisted_rows(tmp_path):
    store = JobRunsLocalStore(tmp_path / "profile_state.db")
    inserted = []
    for day in range(1, 26):
        inserted.append(
            store.record_completed_run(
                "sa_market_news_refresh",
                status="succeeded",
                trigger_source="extension",
                started_at=f"2026-07-{day:02d}T01:00:00Z",
                finished_at=f"2026-07-{day:02d}T01:00:30Z",
                payload={"extension_diagnostics": {"status": "absent"}},
                result={"derived_outcome": "complete"},
            )
        )

    rows = store.completed_extension_runs_by_name()

    assert len(rows) == 20
    assert [row["id"] for row in rows] == list(reversed(inserted[-20:]))


def test_completed_extension_reader_excludes_running_repair_and_unknown_jobs(tmp_path):
    store = JobRunsLocalStore(tmp_path / "profile_state.db")
    expected = store.record_completed_run(
        "sa_alpha_picks_refresh",
        status="failed",
        trigger_source="extension",
        started_at="2026-08-14T01:00:00Z",
        finished_at="2026-08-14T01:00:30Z",
        result={"derived_outcome": "degraded"},
    )
    store.create_run("sa_market_news_repair", trigger_source="extension")
    store.record_completed_run(
        "unknown_extension_job",
        status="failed",
        trigger_source="extension",
        started_at="2026-08-14T02:00:00Z",
        finished_at="2026-08-14T02:00:30Z",
        result={"derived_outcome": "failed"},
    )
    store.record_completed_run(
        "sa_market_news_refresh",
        status="succeeded",
        trigger_source="api",
        started_at="2026-08-14T03:00:00Z",
        finished_at="2026-08-14T03:00:30Z",
        result={"derived_outcome": "complete"},
    )

    rows = store.completed_extension_runs_by_name()

    assert [row["id"] for row in rows] == [expected]
    missing = object.__new__(JobRunsLocalStore)
    missing.db_path = str(tmp_path / "missing" / "profile_state.db")
    assert missing.completed_extension_runs_by_name() == []
    assert not Path(missing.db_path).parent.exists()


def test_extension_record_route_passes_only_admitted_or_marker_projection_to_store(
    monkeypatch,
):
    fake_store = MagicMock()
    fake_store.record_extension_event_once.return_value = 901
    monkeypatch.setattr(jobs_route, "get_job_runs_store", lambda dal: fake_store)

    jobs_route.record_extension_job(
        jobs_route.ExtensionJobRecordRequest(
            **_event("evt-projection", diagnostics=_diagnostics())
        ),
        dal=MagicMock(),
    )
    admitted = fake_store.record_extension_event_once.call_args.kwargs
    assert set(admitted) == {
        "client_event_id",
        "event_hash",
        "job_name",
        "status",
        "started_at",
        "finished_at",
        "result",
        "duration_ms",
        "extension_diagnostics",
    }
    assert admitted["extension_diagnostics"]["status"] == "recorded"

    jobs_route.record_extension_job(
        jobs_route.ExtensionJobRecordRequest(
            **_event("evt-marker", diagnostics=None)
        ),
        dal=MagicMock(),
    )
    rejected = fake_store.record_extension_event_once.call_args.kwargs
    assert rejected["extension_diagnostics"] == {
        "status": "rejected",
        "error_code": "invalid_extension_diagnostics",
    }
