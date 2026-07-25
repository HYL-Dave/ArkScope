"""Bounded, idempotent browser telemetry outbox contract."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tests" / "js" / "run_sa_extension_telemetry_fixture.mjs"
PROTOCOL = ROOT / "extensions" / "sa_alpha_picks" / "extension_run_protocol.js"
TELEMETRY = ROOT / "extensions" / "sa_alpha_picks" / "extension_telemetry.js"
FIXTURE = ROOT / "tests" / "fixtures" / "sa_extension" / "run_outcomes.json"


def _run(scenario: str) -> dict:
    completed = subprocess.run(
        ["node", str(RUNNER), str(PROTOCOL), str(TELEMETRY), str(FIXTURE), scenario],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_outbox_commits_record_before_native_delivery():
    result = _run("commit_before_delivery")
    assert result["order"][0] == "set"
    assert result["order"].index("set") < result["order"].index("deliver")
    assert result["queueLengthAtDelivery"] == 1
    assert result["result"]["delivery"] == "persisted"
    assert result["queue"] == []


def test_persisted_delivery_removes_only_the_matching_event():
    result = _run("remove_matching_only")
    assert [row["client_event_id"] for row in result["queue"]] == ["evt-second"]
    assert result["summary"]["client_event_id"] == "evt-second"
    assert result["summary"]["audit_state"] == "pending"


def test_sidecar_unavailable_keeps_a_pending_record():
    result = _run("sidecar_unavailable")
    assert result["result"] == {
        "client_event_id": "evt-pending",
        "delivery": "pending",
        "reason_code": "sidecar_unavailable",
        "run_id": None,
    }
    assert [row["client_event_id"] for row in result["queue"]] == ["evt-pending"]
    assert result["summary"]["audit_state"] == "pending"


def test_duplicate_flush_reuses_the_same_client_event_id():
    result = _run("duplicate_retry")
    assert result["ids"] == ["evt-duplicate", "evt-duplicate"]
    assert result["queue"] == []


def test_startup_popup_open_and_next_job_share_one_serialized_flush():
    result = _run("serialized_flush")
    assert result == {"deliveries": 1, "queue": []}


def test_outbox_count_and_total_byte_bounds_evict_oldest_and_surface_loss():
    result = _run("count_and_bytes")
    assert [row["client_event_id"] for row in result["countQueue"]] == [
        "evt-count-2",
        "evt-count-3",
    ]
    assert result["countState"]["evicted_count"] == 1
    assert result["countState"]["reason_code"] == "count_limit"
    assert result["byteQueue"] == []
    assert result["byteState"]["evicted_count"] == 1
    assert result["byteState"]["reason_code"] == "total_byte_limit"


def test_outbox_age_bound_evicts_expired_and_surfaces_the_loss():
    result = _run("age_bound")
    assert [row["client_event_id"] for row in result["queue"]] == ["evt-current"]
    assert result["state"]["evicted_count"] == 1
    assert result["state"]["reason_code"] == "age_limit"


def test_oversize_storage_failure_or_event_conflict_is_visible_and_never_persisted():
    result = _run("unavailable_cases")
    assert result["oversize"]["delivery"] == "unavailable"
    assert result["oversize"]["reason_code"] == "record_too_large"
    assert result["oversizeQueue"] == []
    assert result["storageFailure"]["delivery"] == "unavailable"
    assert result["storageFailure"]["reason_code"] == "storage_unavailable"
    assert result["storageQueue"] == []
    assert result["conflict"]["delivery"] == "unavailable"
    assert result["conflict"]["reason_code"] == "event_conflict"
    assert [row["client_event_id"] for row in result["conflictQueue"]] == [
        "evt-conflict"
    ]
