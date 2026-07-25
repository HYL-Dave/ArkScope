"""Shared JS/Python contract for structured SA extension outcomes."""

from __future__ import annotations

import copy
import importlib
import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "sa_extension" / "run_outcomes.json"
RUNNER = ROOT / "tests" / "js" / "run_sa_extension_protocol_fixture.mjs"
JS_PROTOCOL = ROOT / "extensions" / "sa_alpha_picks" / "extension_run_protocol.js"


def _protocol():
    return importlib.import_module("src.sa.extension_run_protocol")


def _fixture():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _case(name: str):
    return next(entry for entry in _fixture()["protocol_cases"] if entry["name"] == name)


def _python_result(entry):
    protocol = _protocol()
    try:
        return {"name": entry["name"], "ok": True, "result": protocol.derive_run_result(entry["input"])}
    except protocol.ProtocolError as exc:
        return {"name": entry["name"], "ok": False, "error_code": exc.code}


def test_js_and_python_protocol_results_match_the_shared_fixture_corpus():
    expected = [_python_result(entry) for entry in _fixture()["protocol_cases"]]
    completed = subprocess.run(
        ["node", str(RUNNER), str(FIXTURE_PATH), str(JS_PROTOCOL)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout) == expected


def test_complete_market_sync_maps_to_succeeded_and_is_healthy_eligible():
    result = _protocol().derive_run_result(_case("complete_market_sync")["input"])
    assert result["derived_outcome"] == "complete"
    assert result["db_status"] == "succeeded"
    assert result["healthy_anchor_eligible"] is True


def test_top_level_ok_with_retryable_details_derives_degraded_and_failed_db_status():
    result = _protocol().derive_run_result(_case("top_level_ok_with_retryable_details")["input"])
    assert result["derived_outcome"] == "degraded"
    assert result["db_status"] == "failed"
    assert result["counts"]["failed_retryable"] == 18
    assert result["healthy_anchor_eligible"] is False


def test_fatal_list_or_save_phase_derives_failed():
    for name in ("fatal_list_navigation", "fatal_metadata_save"):
        result = _protocol().derive_run_result(_case(name)["input"])
        assert result["derived_outcome"] == "failed"
        assert result["db_status"] == "failed"


def test_alpha_detail_or_reconciliation_failure_cannot_derive_complete():
    for name in ("alpha_detail_failure", "alpha_reconciliation_failure"):
        result = _protocol().derive_run_result(_case(name)["input"])
        assert result["derived_outcome"] == "degraded"
        assert result["healthy_anchor_eligible"] is False


def test_skipped_not_due_maps_to_typed_succeeded_but_is_not_healthy_eligible():
    result = _protocol().derive_run_result(_case("skipped_not_due")["input"])
    assert result["derived_outcome"] == "skipped"
    assert result["db_status"] == "succeeded"
    assert result["healthy_anchor_eligible"] is False
    assert result["counts"]["phase_skipped"] == 5


def test_item_state_reason_matrix_rejects_incompatible_pairs():
    protocol = _protocol()
    template = copy.deepcopy(_case("explicit_source_unavailable")["input"])
    bad_pairs = (
        ("repaired", "source_http_404", None),
        ("already_present", "body_saved", None),
        ("unavailable_at_source", "access_restricted", None),
        ("failed_retryable", "source_removed_marker", "source_removed"),
    )
    for state, reason, evidence in bad_pairs:
        template["item_outcomes"] = [{
            "news_id": "opaque-invalid",
            "state": state,
            "reason_code": reason,
            "attempt_count": 1,
            "evidence_code": evidence,
        }]
        with pytest.raises(protocol.ProtocolError) as captured:
            protocol.derive_run_result(template)
        assert captured.value.code == "incompatible_state_reason"


def test_only_explicit_404_410_or_removed_marker_is_source_unavailable():
    protocol = _protocol()
    valid = protocol.derive_run_result(_case("explicit_source_unavailable")["input"])
    assert valid["counts"]["unavailable_at_source"] == 3
    retryable = protocol.derive_run_result(_case("access_restrictions_remain_retryable")["input"])
    assert retryable["counts"]["unavailable_at_source"] == 0
    assert retryable["counts"]["failed_retryable"] == 5


def test_unknown_operation_schema_phase_item_or_reason_fails_closed():
    protocol = _protocol()
    baseline = _case("complete_market_sync")["input"]
    mutations = []
    unknown_operation = copy.deepcopy(baseline)
    unknown_operation["operation"] = "market_news_magic"
    mutations.append(unknown_operation)
    unknown_schema = copy.deepcopy(baseline)
    unknown_schema["schema_version"] = 2
    mutations.append(unknown_schema)
    unknown_phase = copy.deepcopy(baseline)
    unknown_phase["phases"]["surprise"] = {"state": "complete", "reason_code": None}
    mutations.append(unknown_phase)
    unknown_item = copy.deepcopy(baseline)
    unknown_item["item_outcomes"] = [{
        "news_id": "opaque-invalid",
        "state": "maybe",
        "reason_code": "unknown_failure",
        "attempt_count": 1,
        "evidence_code": None,
    }]
    mutations.append(unknown_item)
    mutations.append(_case("unknown_reason")["input"])

    for payload in mutations:
        with pytest.raises(protocol.ProtocolError):
            protocol.derive_run_result(payload)


def test_declared_counts_must_equal_derived_phase_and_item_counts():
    protocol = _protocol()
    with pytest.raises(protocol.ProtocolError) as captured:
        protocol.derive_run_result(_case("declared_count_mismatch")["input"])
    assert captured.value.code == "count_mismatch"


def test_operation_mode_and_job_name_contracts_are_closed():
    protocol = _protocol()
    expected = {
        "alpha_picks_sync": ({"quick", "full", "backfill"}, "sa_alpha_picks_refresh"),
        "alpha_picks_manual_fetch": ({"manual"}, "sa_extension:manual_fetch"),
        "market_news_sync": ({"quick", "full", "catchup"}, "sa_market_news_refresh"),
        "market_news_retry_recorded": ({"recorded"}, "sa_market_news_retry_recorded"),
        "market_news_incident_recovery": ({"incident"}, "sa_market_news_incident_recovery"),
    }
    assert {
        operation: (set(contract["modes"]), contract["job_name"])
        for operation, contract in protocol.OPERATION_CONTRACTS.items()
    } == expected

    payload = copy.deepcopy(_case("complete_market_sync")["input"])
    payload["mode"] = "backfill"
    with pytest.raises(protocol.ProtocolError):
        protocol.derive_run_result(payload)


def test_legacy_unstructured_success_and_raw_prose_are_not_protocol_truth():
    protocol = _protocol()
    with pytest.raises(protocol.ProtocolError) as captured:
        protocol.derive_run_result(_case("legacy_unstructured_success")["input"])
    assert captured.value.code == "legacy_unstructured"

    payload = copy.deepcopy(_case("top_level_ok_with_retryable_details")["input"])
    payload["item_outcomes"][0]["error"] = "Paywall says subscribe now"
    with pytest.raises(protocol.ProtocolError):
        protocol.derive_run_result(payload)
