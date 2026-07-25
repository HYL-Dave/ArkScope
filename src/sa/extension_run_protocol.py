"""Pure validation and derivation for SA extension run outcomes."""

from __future__ import annotations

from typing import Any, Mapping


SCHEMA_VERSION = 1

REASON_CODES = frozenset(
    {
        "body_saved",
        "body_present_at_freeze",
        "body_present_during_run",
        "source_http_404",
        "source_http_410",
        "source_removed_marker",
        "access_restricted",
        "login_required",
        "modal_blocked",
        "navigation_timeout",
        "detail_timeout",
        "dom_not_ready",
        "parser_empty",
        "native_host_unavailable",
        "detail_save_failed",
        "extension_dependency_missing",
        "interrupted",
        "unknown_failure",
        "not_due",
        "already_pending",
        "operator_cancelled",
        "protocol_invalid",
        "manifest_invalid",
        "telemetry_unavailable",
        "current_scope_failed",
        "closed_scope_failed",
        "article_metadata_failed",
        "article_detail_failed",
        "comment_scan_failed",
        "reconciliation_failed",
        "list_navigation_failed",
        "list_scrape_failed",
        "metadata_save_failed",
        "detail_queue_failed",
        "capture_readback_failed",
    }
)

_SKIPPED_REASONS = frozenset({"not_due", "already_pending", "operator_cancelled"})
_FAILED_PHASE_REASONS = REASON_CODES - {
    "body_saved",
    "body_present_at_freeze",
    "body_present_during_run",
    "source_http_404",
    "source_http_410",
    "source_removed_marker",
    "not_due",
    "already_pending",
    "operator_cancelled",
    "telemetry_unavailable",
}
_OUTCOME_FATAL_REASONS = frozenset({"protocol_invalid", "manifest_invalid"})

_ITEM_REASON_MATRIX = {
    "repaired": frozenset({"body_saved", "body_present_during_run"}),
    "already_present": frozenset({"body_present_at_freeze"}),
    "unavailable_at_source": frozenset(
        {"source_http_404", "source_http_410", "source_removed_marker"}
    ),
    "failed_retryable": frozenset(
        {
            "access_restricted",
            "login_required",
            "modal_blocked",
            "navigation_timeout",
            "detail_timeout",
            "dom_not_ready",
            "parser_empty",
            "native_host_unavailable",
            "detail_save_failed",
            "extension_dependency_missing",
            "interrupted",
            "unknown_failure",
        }
    ),
}

_EVIDENCE_BY_UNAVAILABLE_REASON = {
    "source_http_404": "http_404",
    "source_http_410": "http_410",
    "source_removed_marker": "source_removed",
}

OPERATION_CONTRACTS = {
    "alpha_picks_sync": {
        "modes": ("quick", "full", "backfill"),
        "job_name": "sa_alpha_picks_refresh",
        "phases": (
            "current_picks",
            "closed_picks",
            "article_details",
            "reconciliation",
        ),
        "fatal_phases": ("current_picks", "closed_picks"),
        "allows_items": False,
    },
    "alpha_picks_manual_fetch": {
        "modes": ("manual",),
        "job_name": "sa_extension:manual_fetch",
        "phases": ("manual_fetch", "reconciliation"),
        "fatal_phases": ("manual_fetch",),
        "allows_items": False,
    },
    "market_news_sync": {
        "modes": ("quick", "full", "catchup"),
        "job_name": "sa_market_news_refresh",
        "phases": (
            "list_navigation",
            "list_scrape",
            "metadata_save",
            "detail_fetch",
            "capture_readback",
        ),
        "fatal_phases": ("list_navigation", "list_scrape", "metadata_save"),
        "allows_items": True,
    },
    "market_news_retry_recorded": {
        "modes": ("recorded",),
        "job_name": "sa_market_news_retry_recorded",
        "phases": ("manifest", "detail_fetch", "capture_readback"),
        "fatal_phases": ("manifest",),
        "allows_items": True,
    },
    "market_news_incident_recovery": {
        "modes": ("incident",),
        "job_name": "sa_market_news_incident_recovery",
        "phases": (
            "manifest",
            "metadata_rediscovery",
            "detail_fetch",
            "capture_readback",
        ),
        "fatal_phases": ("manifest",),
        "allows_items": True,
    },
}

_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "operation",
        "mode",
        "phases",
        "item_outcomes",
        "counts",
        "derived_outcome",
        "healthy_anchor_eligible",
    }
)
_PHASE_KEYS = frozenset({"state", "reason_code"})
_ITEM_KEYS = frozenset(
    {"news_id", "state", "reason_code", "attempt_count", "evidence_code"}
)
_COUNT_KEYS = (
    "phase_complete",
    "phase_failed",
    "phase_skipped",
    "item_total",
    "repaired",
    "already_present",
    "unavailable_at_source",
    "failed_retryable",
)


class ProtocolError(ValueError):
    """A stable protocol validation failure."""

    def __init__(self, code: str, message: str = "") -> None:
        self.code = code
        super().__init__(message or code)


def _fail(code: str = "protocol_invalid", message: str = "") -> None:
    raise ProtocolError(code, message)


def _exact_keys(value: Mapping[str, Any], expected: frozenset[str]) -> bool:
    return set(value) == expected


def _validate_phase(name: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not _exact_keys(value, _PHASE_KEYS):
        _fail(message=f"invalid phase payload: {name}")

    state = value.get("state")
    reason = value.get("reason_code")
    if state == "complete":
        if reason is not None:
            _fail(message=f"complete phase has a reason: {name}")
    elif state == "failed":
        if reason not in _FAILED_PHASE_REASONS:
            _fail(message=f"invalid failed-phase reason: {name}")
    elif state == "skipped":
        if reason not in _SKIPPED_REASONS:
            _fail(message=f"invalid skipped-phase reason: {name}")
    else:
        _fail(message=f"invalid phase state: {name}")
    return {"state": state, "reason_code": reason}


def _validate_item(value: Any, seen_ids: set[str]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not _exact_keys(value, _ITEM_KEYS):
        _fail(message="invalid item payload")

    news_id = value.get("news_id")
    state = value.get("state")
    reason = value.get("reason_code")
    attempts = value.get("attempt_count")
    evidence = value.get("evidence_code")

    if not isinstance(news_id, str) or not news_id.strip() or news_id in seen_ids:
        _fail(message="invalid or duplicate news_id")
    seen_ids.add(news_id)

    allowed_reasons = _ITEM_REASON_MATRIX.get(state)
    if allowed_reasons is None:
        _fail(message="invalid item state")
    if reason not in allowed_reasons:
        _fail("incompatible_state_reason")
    if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 0:
        _fail(message="invalid attempt_count")
    if state != "already_present" and attempts < 1:
        _fail(message="attempt_count must record an attempt")

    if state == "unavailable_at_source":
        if evidence != _EVIDENCE_BY_UNAVAILABLE_REASON[reason]:
            _fail("incompatible_state_reason")
    elif evidence is not None:
        _fail("incompatible_state_reason")

    return {
        "news_id": news_id,
        "state": state,
        "reason_code": reason,
        "attempt_count": attempts,
        "evidence_code": evidence,
    }


def _derive_counts(phases: Mapping[str, Mapping[str, Any]], items: list[dict[str, Any]]):
    counts = {key: 0 for key in _COUNT_KEYS}
    for phase in phases.values():
        counts[f"phase_{phase['state']}"] += 1
    counts["item_total"] = len(items)
    for item in items:
        counts[item["state"]] += 1
    return counts


def _derive_outcome(contract: Mapping[str, Any], phases, counts) -> str:
    phase_values = list(phases.values())
    if all(phase["state"] == "skipped" for phase in phase_values):
        if counts["item_total"] != 0:
            _fail(message="skipped run cannot contain item outcomes")
        return "skipped"

    fatal_phases = set(contract["fatal_phases"])
    if any(
        phases[name]["state"] == "failed"
        or phases[name]["reason_code"] in _OUTCOME_FATAL_REASONS
        for name in fatal_phases
    ):
        return "failed"
    if any(
        phase["state"] == "failed"
        and phase["reason_code"] in _OUTCOME_FATAL_REASONS
        for phase in phase_values
    ):
        return "failed"

    if any(phase["state"] == "skipped" for phase in phase_values):
        _fail(message="partially skipped run lacks a fatal failure")
    if any(phase["state"] == "failed" for phase in phase_values):
        return "degraded"
    if counts["failed_retryable"]:
        return "degraded"
    return "complete"


def derive_run_result(payload: Any) -> dict[str, Any]:
    """Validate a versioned result and derive its canonical aggregate truth."""

    if not isinstance(payload, Mapping) or "schema_version" not in payload:
        _fail("legacy_unstructured")
    if set(payload) - _TOP_LEVEL_KEYS:
        _fail(message="unknown top-level field")
    if payload.get("schema_version") != SCHEMA_VERSION:
        _fail(message="unsupported schema version")

    operation = payload.get("operation")
    contract = OPERATION_CONTRACTS.get(operation)
    if contract is None or payload.get("mode") not in contract["modes"]:
        _fail(message="unknown operation or mode")

    raw_phases = payload.get("phases")
    expected_phases = tuple(contract["phases"])
    if not isinstance(raw_phases, Mapping) or set(raw_phases) != set(expected_phases):
        _fail(message="phase set does not match operation")
    phases = {
        name: _validate_phase(name, raw_phases[name])
        for name in expected_phases
    }

    raw_items = payload.get("item_outcomes")
    if not isinstance(raw_items, list):
        _fail(message="item_outcomes must be a list")
    seen_ids: set[str] = set()
    items = [_validate_item(item, seen_ids) for item in raw_items]
    if items and not contract["allows_items"]:
        _fail(message="operation does not allow item outcomes")

    counts = _derive_counts(phases, items)
    declared_counts = payload.get("counts")
    if declared_counts is not None:
        if not isinstance(declared_counts, Mapping):
            _fail("count_mismatch")
        if set(declared_counts) != set(_COUNT_KEYS):
            _fail("count_mismatch")
        if any(declared_counts[key] != counts[key] for key in _COUNT_KEYS):
            _fail("count_mismatch")

    derived_outcome = _derive_outcome(contract, phases, counts)
    claimed_outcome = payload.get("derived_outcome")
    if claimed_outcome is not None and claimed_outcome != derived_outcome:
        _fail(message="derived outcome mismatch")

    db_status = "succeeded" if derived_outcome in {"complete", "skipped"} else "failed"
    healthy = derived_outcome == "complete" and operation in {
        "alpha_picks_sync",
        "market_news_sync",
    }
    claimed_healthy = payload.get("healthy_anchor_eligible")
    if claimed_healthy is not None and claimed_healthy is not healthy:
        _fail(message="healthy anchor mismatch")

    return {
        "schema_version": SCHEMA_VERSION,
        "operation": operation,
        "mode": payload["mode"],
        "job_name": contract["job_name"],
        "derived_outcome": derived_outcome,
        "db_status": db_status,
        "healthy_anchor_eligible": healthy,
        "phases": phases,
        "counts": counts,
        "item_outcomes": items,
    }


__all__ = [
    "OPERATION_CONTRACTS",
    "ProtocolError",
    "REASON_CODES",
    "SCHEMA_VERSION",
    "derive_run_result",
]
