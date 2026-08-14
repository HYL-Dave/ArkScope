"""Browser-side SA diagnostics collection and delivery contracts."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tests" / "js" / "run_sa_extension_diagnostics_fixture.mjs"
PROTOCOL = ROOT / "extensions" / "sa_alpha_picks" / "extension_run_protocol.js"
DIAGNOSTICS = ROOT / "extensions" / "sa_alpha_picks" / "extension_diagnostics.js"
TELEMETRY = ROOT / "extensions" / "sa_alpha_picks" / "extension_telemetry.js"
BACKGROUND = ROOT / "extensions" / "sa_alpha_picks" / "background.js"


def _run(scenario: str) -> dict:
    completed = subprocess.run(
        [
            "node",
            str(RUNNER),
            str(PROTOCOL),
            str(DIAGNOSTICS),
            str(TELEMETRY),
            str(BACKGROUND),
            scenario,
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_diagnostic_collector_accepts_closed_entries_and_caps_at_thirty_two():
    result = _run("collector_cap")

    assert result["accepted_count"] == 32
    assert result["rejected_count"] == 0
    assert result["timestamp_reads"] == 32
    assert result["envelope"]["schema_version"] == 1
    assert len(result["envelope"]["entries"]) == 32
    assert result["envelope"]["omitted_count"] == 2
    assert result["deep_frozen"] is True
    assert set(result["envelope"]["entries"][0]) == {
        "occurred_at",
        "stage",
        "reason_code",
        "target_kind",
        "target_ref",
        "retryable",
        "attempt_count",
        "message",
    }


def test_diagnostic_collector_rejects_secret_or_unbounded_fields_before_transport():
    result = _run("collector_rejection")

    assert result["accepted"] == [False, False, False, False, False]
    assert result["envelope"] == {
        "schema_version": 1,
        "entries": [],
        "omitted_count": 0,
    }
    serialized = json.dumps(result, sort_keys=True)
    for sentinel in (
        "secret@example.com",
        "https://seekingalpha.com/private",
        "Bearer secret-token",
        "/home/operator/private.db",
    ):
        assert sentinel not in serialized


def test_alpha_detail_failure_branches_record_exactly_one_diagnostic_before_increment():
    result = _run("alpha_failure_branches")

    assert result["raw_increment_sites"] == []
    assert result["recording_increment_sites"] >= 17
    for branch in result["branches"]:
        assert branch["failed"] == 1
        assert len(branch["diagnostics"]["entries"]) == 1
        assert branch["recorded_before_increment"] is True
        assert branch["diagnostics"]["entries"][0]["target_ref"] == "alpha-opaque-1"


def test_market_news_failures_preserve_target_and_stable_reason_without_url_or_body():
    result = _run("market_news_failures")

    assert result["detail_failed"] == 2
    assert [entry["target_ref"] for entry in result["diagnostics"]["entries"]] == [
        "news-opaque-1",
        "news-opaque-2",
    ]
    assert [entry["reason_code"] for entry in result["diagnostics"]["entries"]] == [
        "access_restricted",
        "unknown_failure",
    ]
    serialized = json.dumps(result["diagnostics"], sort_keys=True)
    assert "https://" not in serialized
    assert "private article body" not in serialized


def test_comment_scan_and_unknown_exception_reuse_existing_reason_codes():
    result = _run("comment_and_unknown")

    assert result["comment"] == {
        "stage": "content_parse",
        "reason_code": "comment_scan_failed",
        "target_kind": "article_comments",
        "target_ref": "alpha-opaque-1",
        "retryable": True,
    }
    assert result["unknown"] == {
        "stage": "extension_runtime",
        "reason_code": "unknown_failure",
        "target_kind": "article_detail",
        "target_ref": "alpha-opaque-1",
        "retryable": True,
    }


def test_native_failure_envelope_keeps_transport_and_local_persistence_distinct():
    result = _run("native_failure_mapping")

    assert result == {
        "transport": {
            "stage": "native_transport",
            "reason_code": "native_host_unavailable",
            "retryable": True,
        },
        "invalid": {
            "stage": "native_transport",
            "reason_code": "native_response_invalid",
            "retryable": True,
        },
        "busy": {
            "stage": "local_persistence",
            "reason_code": "database_busy",
            "retryable": True,
        },
        "integrity": {
            "stage": "local_persistence",
            "reason_code": "database_integrity_failed",
            "retryable": False,
        },
        "write": {
            "stage": "local_persistence",
            "reason_code": "database_write_failed",
            "retryable": True,
        },
    }


def test_successful_saves_submit_an_explicit_empty_diagnostics_envelope():
    result = _run("successful_job")

    assert result["job_result"]["extension_run"]["derived_outcome"] == "complete"
    assert result["submitted"]["extension_diagnostics"] == {
        "schema_version": 1,
        "entries": [],
        "omitted_count": 0,
    }
    assert result["submitted"]["started_at"] <= result["submitted"]["finished_at"]
    assert result["thrown"] is True
    assert result["failed_submitted"]["result"]["derived_outcome"] == "failed"
    assert result["failed_submitted"]["extension_diagnostics"]["entries"] == [
        {
            "occurred_at": result["failed_submitted"]["extension_diagnostics"][
                "entries"
            ][0]["occurred_at"],
            "stage": "extension_runtime",
            "reason_code": "unknown_failure",
            "target_kind": "phase",
            "retryable": True,
            "attempt_count": 1,
        }
    ]
    assert "private article body" not in json.dumps(
        result["failed_submitted"], sort_keys=True
    )


def test_telemetry_outbox_freezes_diagnostics_into_the_immutable_record():
    result = _run("telemetry_freeze")

    assert result["queued_diagnostics"] == result["delivered_diagnostics"]
    assert result["queued_diagnostics"]["entries"][0]["reason_code"] == "parser_empty"
    assert result["mutation_changed_record"] is False
    assert result["immutable_includes_diagnostics"] is True
