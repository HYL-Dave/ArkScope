"""Durable, resumable Market News repair domain contracts."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from src.sa.market_news_recovery import (
    MarketNewsRecoveryError,
    MarketNewsRecoveryService,
    build_repair_manifest,
    canonical_manifest_json,
    manifest_hash,
)
from src.service.job_runs_store import JobRunsLocalStore


NOW = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)


def _row(
    news_id: str,
    *,
    published_at: str = "2026-07-24T12:00:00+00:00",
    body_present: bool = False,
) -> dict:
    return {
        "news_id": news_id,
        "pathname": f"/news/{news_id}",
        "published_at": published_at,
        "body_present": body_present,
    }


class _RecoveryDal:
    def __init__(self, rows: list[dict] = ()) -> None:
        self.rows = {row["news_id"]: dict(row) for row in rows}

    def get_sa_market_news_recovery_rows(self, news_ids):
        return [dict(self.rows[news_id]) for news_id in news_ids if news_id in self.rows]

    def get_sa_market_news_body_presence(self, news_ids):
        return {
            news_id: bool(self.rows[news_id]["body_present"])
            for news_id in news_ids
            if news_id in self.rows
        }

    def get_sa_market_news_missing_detail_interval(self, start_at, end_at):
        return [
            dict(row)
            for row in self.rows.values()
            if start_at <= row["published_at"] <= end_at and not row["body_present"]
        ]


def _service(tmp_path, rows=(), *, now=NOW):
    store = JobRunsLocalStore(tmp_path / "profile_state.db")
    return MarketNewsRecoveryService(_RecoveryDal(rows), store, now=lambda: now), store


def _manifest(*rows: dict, kind: str = "recorded_failures") -> dict:
    return build_repair_manifest(
        kind=kind,
        targets=list(rows),
        source_run_ids=[19, 7] if kind == "recorded_failures" else [],
        interval=(
            {
                "start_at": "2026-07-24T12:00:00+00:00",
                "end_at": "2026-07-25T12:00:00+00:00",
                "anchor_verified": True,
            }
            if kind == "incident_window"
            else None
        ),
    )


def _record_extension_run(store, result: dict, *, finished_at: str) -> int:
    run_id = store.record_completed_run(
        "sa_market_news_refresh",
        status="failed" if result.get("derived_outcome") == "degraded" else "succeeded",
        trigger_source="extension",
        started_at=finished_at,
        finished_at=finished_at,
        payload={
            "extension_event": {
                "client_event_id": f"event-{finished_at}",
                "event_hash": "a" * 64,
            }
        },
        result=result,
    )
    assert run_id is not None
    return run_id


def test_manifest_json_and_hash_are_canonical_and_order_independent():
    first = _manifest(_row("n2"), _row("n1"))
    second = build_repair_manifest(
        kind="recorded_failures",
        targets=[_row("n1"), _row("n2")],
        source_run_ids=[7, 19],
    )

    assert canonical_manifest_json(first) == canonical_manifest_json(second)
    assert manifest_hash(first) == manifest_hash(second)
    assert [item["news_id"] for item in first["targets"]] == ["n1", "n2"]
    assert first["source_run_ids"] == [7, 19]


def test_manifest_accepts_only_canonical_sa_pathnames_without_query_or_fragment():
    assert _manifest(_row("valid"))["targets"][0]["pathname"] == "/news/valid"

    invalid = (
        "https://seekingalpha.com/news/n1",
        "//seekingalpha.com/news/n1",
        "/news/n1?q=secret",
        "/news/n1#comments",
        "/news/../account",
        "/news/%2e%2e/account",
        "/article/n1",
    )
    for pathname in invalid:
        with pytest.raises(MarketNewsRecoveryError, match="manifest_invalid"):
            _manifest({**_row("n1"), "pathname": pathname})


def test_recorded_failure_preview_has_no_age_cutoff_and_does_not_classify_legacy_prose(
    tmp_path,
):
    service, store = _service(
        tmp_path,
        [_row("legacy-old", published_at="2025-01-01T00:00:00+00:00")],
    )
    run_id = _record_extension_run(
        store,
        {
            "detail_failures": [
                {"news_id": "legacy-old", "error": "404 removed paywall maybe"}
            ]
        },
        finished_at="2025-01-02T00:00:00+00:00",
    )

    preview = service.preview_recorded_failures(source_run_ids=[run_id])

    assert preview["target_count"] == 1
    assert preview["manifest"]["targets"][0]["news_id"] == "legacy-old"
    assert "state" not in preview["manifest"]["targets"][0]
    assert "reason_code" not in preview["manifest"]["targets"][0]
    assert "404" not in canonical_manifest_json(preview["manifest"])


def test_latest_structured_retryable_ids_can_be_previewed_contextually(tmp_path):
    service, store = _service(tmp_path, [_row("retry-me"), _row("done")])
    _record_extension_run(
        store,
        {
            "schema_version": 1,
            "derived_outcome": "degraded",
            "healthy_anchor_eligible": False,
            "item_outcomes": [
                {
                    "news_id": "retry-me",
                    "state": "failed_retryable",
                    "reason_code": "detail_timeout",
                    "attempt_count": 1,
                    "evidence_code": None,
                },
                {
                    "news_id": "done",
                    "state": "repaired",
                    "reason_code": "body_saved",
                    "attempt_count": 1,
                    "evidence_code": None,
                },
            ],
        },
        finished_at="2026-07-25T10:00:00+00:00",
    )

    preview = service.preview_recorded_failures()

    assert preview["target_count"] == 1
    assert preview["manifest"]["targets"][0]["news_id"] == "retry-me"
    assert preview["source"] == "latest_structured_retryable"


def test_incident_preview_uses_latest_derived_complete_anchor(tmp_path):
    service, store = _service(tmp_path, [_row("n1")])
    _record_extension_run(
        store,
        {
            "schema_version": 1,
            "derived_outcome": "complete",
            "healthy_anchor_eligible": True,
            "item_outcomes": [],
        },
        finished_at="2026-07-24T12:00:00+00:00",
    )

    preview = service.preview_incident()

    assert preview["manifest"]["interval"] == {
        "start_at": "2026-07-24T12:00:00+00:00",
        "end_at": "2026-07-25T12:00:00+00:00",
        "anchor_verified": True,
    }
    assert preview["source_run_id"] is not None


def test_incident_preview_caps_at_168_hours_or_marks_missing_anchor_unverified(tmp_path):
    service, store = _service(tmp_path)
    _record_extension_run(
        store,
        {
            "schema_version": 1,
            "derived_outcome": "complete",
            "healthy_anchor_eligible": True,
            "item_outcomes": [],
        },
        finished_at="2026-07-01T00:00:00+00:00",
    )
    capped = service.preview_incident()
    assert capped["manifest"]["interval"]["start_at"] == "2026-07-18T12:00:00+00:00"
    assert capped["manifest"]["interval"]["anchor_verified"] is True

    empty_service, _ = _service(tmp_path / "empty")
    unverified = empty_service.preview_incident()
    assert unverified["manifest"]["interval"]["start_at"] == "2026-07-18T12:00:00+00:00"
    assert unverified["manifest"]["interval"]["anchor_verified"] is False


def test_preview_separates_known_detail_targets_from_unknown_metadata_gap(tmp_path):
    service, _ = _service(tmp_path, [_row("known")])

    preview = service.preview_incident()

    assert preview["target_count"] == 1
    assert preview["discovery"]["missing_metadata_count"] is None
    assert preview["discovery"]["enabled"] is True
    assert preview["discovery"]["max_list_scroll_rounds"] == 60


def test_zero_target_rules_distinguish_no_work_from_real_discovery_scope(tmp_path):
    service, _ = _service(tmp_path)

    recorded = service.preview_recorded_failures(source_run_ids=[])
    incident = service.preview_incident()

    assert recorded["target_count"] == 0
    assert recorded["can_start"] is False
    assert recorded["status"] == "no_work"
    assert incident["target_count"] == 0
    assert incident["can_start"] is True
    assert incident["status"] == "discovery_only"


def test_atomic_start_returns_one_running_run_and_manifest_under_concurrency(tmp_path):
    service, store = _service(tmp_path, [_row("a"), _row("b")])
    manifests = [_manifest(_row("a")), _manifest(_row("b"))]

    def start(index: int):
        manifest = manifests[index]
        return service.start(manifest, manifest_hash(manifest))

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(start, [0, 1, 0, 1, 0, 1, 0, 1]))

    assert len({result["run_id"] for result in results}) == 1
    assert len(store.list_runs(job_name="sa_market_news_repair")) == 1
    winning_hash = results[0]["manifest_hash"]
    assert all(result["manifest_hash"] == winning_hash for result in results)
    assert all(result["manifest"] == results[0]["manifest"] for result in results)


def test_resume_preserves_run_id_manifest_hash_and_baseline(tmp_path):
    service, store = _service(tmp_path, [_row("n1")])
    manifest = _manifest(_row("n1"))
    started = service.start(manifest, manifest_hash(manifest))
    service.checkpoint(
        started["run_id"],
        started["manifest_hash"],
        news_id="n1",
        attempt_id="attempt-1",
        state="failed_retryable",
        reason_code="detail_timeout",
    )

    resumed = service.start(manifest, manifest_hash(manifest))
    row = store.list_runs(job_name="sa_market_news_repair")[0]

    assert resumed["created"] is False
    assert resumed["run_id"] == started["run_id"]
    assert resumed["manifest_hash"] == started["manifest_hash"]
    assert row["payload"]["manifest"]["targets"][0]["body_present"] is False


def test_progress_checkpoint_is_idempotent_by_news_id_and_attempt_id(tmp_path):
    service, _ = _service(tmp_path, [_row("n1")])
    manifest = _manifest(_row("n1"))
    started = service.start(manifest, manifest_hash(manifest))
    kwargs = {
        "news_id": "n1",
        "attempt_id": "same-attempt",
        "state": "failed_retryable",
        "reason_code": "detail_timeout",
    }

    first = service.checkpoint(started["run_id"], started["manifest_hash"], **kwargs)
    second = service.checkpoint(started["run_id"], started["manifest_hash"], **kwargs)

    assert first == second
    assert len(second["progress"]["attempts"]) == 1


def test_conflicting_or_incompatible_progress_is_rejected_without_write(tmp_path):
    service, _ = _service(tmp_path, [_row("n1")])
    manifest = _manifest(_row("n1"))
    started = service.start(manifest, manifest_hash(manifest))
    service.checkpoint(
        started["run_id"],
        started["manifest_hash"],
        news_id="n1",
        attempt_id="attempt-1",
        state="failed_retryable",
        reason_code="detail_timeout",
    )

    with pytest.raises(MarketNewsRecoveryError, match="checkpoint_conflict"):
        service.checkpoint(
            started["run_id"],
            started["manifest_hash"],
            news_id="n1",
            attempt_id="attempt-1",
            state="failed_retryable",
            reason_code="parser_empty",
        )
    with pytest.raises(MarketNewsRecoveryError, match="incompatible_state_reason"):
        service.checkpoint(
            started["run_id"],
            started["manifest_hash"],
            news_id="n1",
            attempt_id="attempt-2",
            state="unavailable_at_source",
            reason_code="access_restricted",
        )

    state = service.state(started["run_id"])
    assert len(state["progress"]["attempts"]) == 1


def test_finalize_reconciles_already_present_repaired_and_source_unavailable(tmp_path):
    rows = [
        _row("baseline", body_present=True),
        _row("repaired", body_present=False),
        _row("gone", body_present=False),
    ]
    service, _ = _service(tmp_path, rows)
    manifest = _manifest(*rows)
    started = service.start(manifest, manifest_hash(manifest))
    service.dal.rows["repaired"]["body_present"] = True
    service.checkpoint(
        started["run_id"],
        started["manifest_hash"],
        news_id="gone",
        attempt_id="gone-1",
        state="unavailable_at_source",
        reason_code="source_http_410",
        evidence_code="http_410",
    )

    final = service.finalize(started["run_id"], started["manifest_hash"])
    outcomes = {item["news_id"]: item["state"] for item in final["item_outcomes"]}

    assert outcomes == {
        "baseline": "already_present",
        "gone": "unavailable_at_source",
        "repaired": "repaired",
    }
    assert final["derived_outcome"] == "complete"
    assert final["db_status"] == "succeeded"


def test_finalize_marks_missing_or_omitted_targets_failed_retryable(tmp_path):
    service, _ = _service(tmp_path, [_row("explicit"), _row("omitted")])
    manifest = _manifest(_row("explicit"), _row("omitted"), _row("missing-row"))
    started = service.start(manifest, manifest_hash(manifest))
    service.checkpoint(
        started["run_id"],
        started["manifest_hash"],
        news_id="explicit",
        attempt_id="explicit-1",
        state="failed_retryable",
        reason_code="login_required",
    )

    final = service.finalize(started["run_id"], started["manifest_hash"])
    outcomes = {item["news_id"]: item for item in final["item_outcomes"]}

    assert outcomes["explicit"]["reason_code"] == "login_required"
    assert outcomes["omitted"]["reason_code"] == "interrupted"
    assert outcomes["missing-row"]["reason_code"] == "interrupted"
    assert final["counts"]["failed_retryable"] == 3
    assert final["derived_outcome"] == "degraded"
    assert final["db_status"] == "failed"


def test_cancel_and_stale_interruption_preserve_resumable_manifest_truth(tmp_path):
    service, store = _service(tmp_path, [_row("n1")])
    manifest = _manifest(_row("n1"))
    started = service.start(manifest, manifest_hash(manifest))

    interrupted = service.interrupt_stale(started["run_id"], started["manifest_hash"])
    assert interrupted["status"] == "running"
    assert interrupted["lifecycle_state"] == "interrupted"
    assert interrupted["resumable"] is True
    assert service.start(manifest, manifest_hash(manifest))["run_id"] == started["run_id"]

    cancelled = service.cancel(started["run_id"], started["manifest_hash"])
    row = store.list_runs(job_name="sa_market_news_repair")[0]
    assert cancelled["status"] == "failed"
    assert cancelled["reason_code"] == "operator_cancelled"
    assert row["payload"]["manifest"] == manifest
    assert row["payload"]["manifest_hash"] == started["manifest_hash"]


def test_terminal_status_counts_and_result_hash_are_derived_and_idempotent(tmp_path):
    service, store = _service(tmp_path, [_row("n1", body_present=True)])
    manifest = _manifest(_row("n1", body_present=True))
    started = service.start(manifest, manifest_hash(manifest))

    first = service.finalize(started["run_id"], started["manifest_hash"])
    second = service.finalize(started["run_id"], started["manifest_hash"])
    row = store.list_runs(job_name="sa_market_news_repair")[0]

    assert first == second
    assert first["counts"] == {
        "target_total": 1,
        "repaired": 0,
        "already_present": 1,
        "unavailable_at_source": 0,
        "failed_retryable": 0,
    }
    assert len(first["result_hash"]) == 64
    assert row["status"] == "succeeded"
    assert row["result"]["result_hash"] == first["result_hash"]
