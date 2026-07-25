(function (root) {
  "use strict";

  var SCHEMA_VERSION = 1;
  var REASON_CODES = Object.freeze([
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
  ]);

  var SKIPPED_REASONS = Object.freeze(["not_due", "already_pending", "operator_cancelled"]);
  var FAILED_PHASE_REASONS = REASON_CODES.filter(function (reason) {
    return [
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
    ].indexOf(reason) === -1;
  });
  var OUTCOME_FATAL_REASONS = Object.freeze(["protocol_invalid", "manifest_invalid"]);

  var ITEM_REASON_MATRIX = Object.freeze({
    repaired: Object.freeze(["body_saved", "body_present_during_run"]),
    already_present: Object.freeze(["body_present_at_freeze"]),
    unavailable_at_source: Object.freeze([
      "source_http_404",
      "source_http_410",
      "source_removed_marker",
    ]),
    failed_retryable: Object.freeze([
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
    ]),
  });

  var EVIDENCE_BY_UNAVAILABLE_REASON = Object.freeze({
    source_http_404: "http_404",
    source_http_410: "http_410",
    source_removed_marker: "source_removed",
  });

  var OPERATION_CONTRACTS = Object.freeze({
    alpha_picks_sync: Object.freeze({
      modes: Object.freeze(["quick", "full", "backfill"]),
      job_name: "sa_alpha_picks_refresh",
      phases: Object.freeze(["current_picks", "closed_picks", "article_details", "reconciliation"]),
      fatal_phases: Object.freeze(["current_picks", "closed_picks"]),
      allows_items: false,
    }),
    alpha_picks_manual_fetch: Object.freeze({
      modes: Object.freeze(["manual"]),
      job_name: "sa_extension:manual_fetch",
      phases: Object.freeze(["manual_fetch", "reconciliation"]),
      fatal_phases: Object.freeze(["manual_fetch"]),
      allows_items: false,
    }),
    market_news_sync: Object.freeze({
      modes: Object.freeze(["quick", "full", "catchup"]),
      job_name: "sa_market_news_refresh",
      phases: Object.freeze([
        "list_navigation",
        "list_scrape",
        "metadata_save",
        "detail_fetch",
        "capture_readback",
      ]),
      fatal_phases: Object.freeze(["list_navigation", "list_scrape", "metadata_save"]),
      allows_items: true,
    }),
    market_news_retry_recorded: Object.freeze({
      modes: Object.freeze(["recorded"]),
      job_name: "sa_market_news_retry_recorded",
      phases: Object.freeze(["manifest", "detail_fetch", "capture_readback"]),
      fatal_phases: Object.freeze(["manifest"]),
      allows_items: true,
    }),
    market_news_incident_recovery: Object.freeze({
      modes: Object.freeze(["incident"]),
      job_name: "sa_market_news_incident_recovery",
      phases: Object.freeze(["manifest", "metadata_rediscovery", "detail_fetch", "capture_readback"]),
      fatal_phases: Object.freeze(["manifest"]),
      allows_items: true,
    }),
  });

  var TOP_LEVEL_KEYS = Object.freeze([
    "schema_version",
    "operation",
    "mode",
    "phases",
    "item_outcomes",
    "counts",
    "derived_outcome",
    "healthy_anchor_eligible",
  ]);
  var PHASE_KEYS = Object.freeze(["state", "reason_code"]);
  var ITEM_KEYS = Object.freeze([
    "news_id",
    "state",
    "reason_code",
    "attempt_count",
    "evidence_code",
  ]);
  var COUNT_KEYS = Object.freeze([
    "phase_complete",
    "phase_failed",
    "phase_skipped",
    "item_total",
    "repaired",
    "already_present",
    "unavailable_at_source",
    "failed_retryable",
  ]);

  class ProtocolError extends Error {
    constructor(code, message) {
      super(message || code);
      this.name = "ProtocolError";
      this.code = code;
    }
  }

  function fail(code, message) {
    throw new ProtocolError(code || "protocol_invalid", message || "");
  }

  function isObject(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }

  function sortedKeys(value) {
    return Object.keys(value).sort();
  }

  function hasExactKeys(value, expected) {
    if (!isObject(value)) return false;
    var actual = sortedKeys(value);
    var wanted = expected.slice().sort();
    if (actual.length !== wanted.length) return false;
    for (var i = 0; i < actual.length; i++) {
      if (actual[i] !== wanted[i]) return false;
    }
    return true;
  }

  function includes(values, value) {
    return values.indexOf(value) !== -1;
  }

  function validatePhase(name, value) {
    if (!hasExactKeys(value, PHASE_KEYS)) {
      fail("protocol_invalid", "invalid phase payload: " + name);
    }
    var state = value.state;
    var reason = value.reason_code;
    if (state === "complete") {
      if (reason !== null) fail("protocol_invalid", "complete phase has a reason: " + name);
    } else if (state === "failed") {
      if (!includes(FAILED_PHASE_REASONS, reason)) {
        fail("protocol_invalid", "invalid failed-phase reason: " + name);
      }
    } else if (state === "skipped") {
      if (!includes(SKIPPED_REASONS, reason)) {
        fail("protocol_invalid", "invalid skipped-phase reason: " + name);
      }
    } else {
      fail("protocol_invalid", "invalid phase state: " + name);
    }
    return {state: state, reason_code: reason};
  }

  function validateItem(value, seenIds) {
    if (!hasExactKeys(value, ITEM_KEYS)) {
      fail("protocol_invalid", "invalid item payload");
    }
    var newsId = value.news_id;
    var state = value.state;
    var reason = value.reason_code;
    var attempts = value.attempt_count;
    var evidence = value.evidence_code;
    if (typeof newsId !== "string" || !newsId.trim() || seenIds[newsId]) {
      fail("protocol_invalid", "invalid or duplicate news_id");
    }
    seenIds[newsId] = true;

    var allowedReasons = ITEM_REASON_MATRIX[state];
    if (!allowedReasons) fail("protocol_invalid", "invalid item state");
    if (!includes(allowedReasons, reason)) fail("incompatible_state_reason");
    if (!Number.isInteger(attempts) || attempts < 0) {
      fail("protocol_invalid", "invalid attempt_count");
    }
    if (state !== "already_present" && attempts < 1) {
      fail("protocol_invalid", "attempt_count must record an attempt");
    }

    if (state === "unavailable_at_source") {
      if (evidence !== EVIDENCE_BY_UNAVAILABLE_REASON[reason]) {
        fail("incompatible_state_reason");
      }
    } else if (evidence !== null) {
      fail("incompatible_state_reason");
    }
    return {
      news_id: newsId,
      state: state,
      reason_code: reason,
      attempt_count: attempts,
      evidence_code: evidence,
    };
  }

  function deriveCounts(phases, items) {
    var counts = {
      phase_complete: 0,
      phase_failed: 0,
      phase_skipped: 0,
      item_total: items.length,
      repaired: 0,
      already_present: 0,
      unavailable_at_source: 0,
      failed_retryable: 0,
    };
    Object.keys(phases).forEach(function (name) {
      counts["phase_" + phases[name].state] += 1;
    });
    items.forEach(function (item) {
      counts[item.state] += 1;
    });
    return counts;
  }

  function deriveOutcome(contract, phases, counts) {
    var phaseValues = contract.phases.map(function (name) { return phases[name]; });
    if (phaseValues.every(function (phase) { return phase.state === "skipped"; })) {
      if (counts.item_total !== 0) fail("protocol_invalid", "skipped run cannot contain items");
      return "skipped";
    }

    var fatalFailure = contract.fatal_phases.some(function (name) {
      return phases[name].state === "failed"
        || includes(OUTCOME_FATAL_REASONS, phases[name].reason_code);
    });
    if (fatalFailure) return "failed";
    if (phaseValues.some(function (phase) {
      return phase.state === "failed" && includes(OUTCOME_FATAL_REASONS, phase.reason_code);
    })) return "failed";

    if (phaseValues.some(function (phase) { return phase.state === "skipped"; })) {
      fail("protocol_invalid", "partially skipped run lacks a fatal failure");
    }
    if (phaseValues.some(function (phase) { return phase.state === "failed"; })) return "degraded";
    if (counts.failed_retryable > 0) return "degraded";
    return "complete";
  }

  function deriveRunResult(payload) {
    if (!isObject(payload) || !("schema_version" in payload)) fail("legacy_unstructured");
    if (Object.keys(payload).some(function (key) { return !includes(TOP_LEVEL_KEYS, key); })) {
      fail("protocol_invalid", "unknown top-level field");
    }
    if (payload.schema_version !== SCHEMA_VERSION) {
      fail("protocol_invalid", "unsupported schema version");
    }

    var operation = payload.operation;
    var contract = OPERATION_CONTRACTS[operation];
    if (!contract || !includes(contract.modes, payload.mode)) {
      fail("protocol_invalid", "unknown operation or mode");
    }
    if (!isObject(payload.phases)) fail("protocol_invalid", "phases must be an object");
    var actualPhaseNames = sortedKeys(payload.phases);
    var expectedPhaseNames = contract.phases.slice().sort();
    if (actualPhaseNames.length !== expectedPhaseNames.length
        || actualPhaseNames.some(function (name, index) { return name !== expectedPhaseNames[index]; })) {
      fail("protocol_invalid", "phase set does not match operation");
    }
    var phases = {};
    contract.phases.forEach(function (name) {
      phases[name] = validatePhase(name, payload.phases[name]);
    });

    if (!Array.isArray(payload.item_outcomes)) {
      fail("protocol_invalid", "item_outcomes must be a list");
    }
    var seenIds = Object.create(null);
    var items = payload.item_outcomes.map(function (item) {
      return validateItem(item, seenIds);
    });
    if (items.length && !contract.allows_items) {
      fail("protocol_invalid", "operation does not allow item outcomes");
    }

    var counts = deriveCounts(phases, items);
    if (payload.counts !== undefined) {
      if (!hasExactKeys(payload.counts, COUNT_KEYS)) fail("count_mismatch");
      if (COUNT_KEYS.some(function (key) { return payload.counts[key] !== counts[key]; })) {
        fail("count_mismatch");
      }
    }

    var derivedOutcome = deriveOutcome(contract, phases, counts);
    if (payload.derived_outcome !== undefined && payload.derived_outcome !== derivedOutcome) {
      fail("protocol_invalid", "derived outcome mismatch");
    }
    var dbStatus = includes(["complete", "skipped"], derivedOutcome) ? "succeeded" : "failed";
    var healthy = derivedOutcome === "complete"
      && includes(["alpha_picks_sync", "market_news_sync"], operation);
    if (payload.healthy_anchor_eligible !== undefined
        && payload.healthy_anchor_eligible !== healthy) {
      fail("protocol_invalid", "healthy anchor mismatch");
    }

    return {
      schema_version: SCHEMA_VERSION,
      operation: operation,
      mode: payload.mode,
      job_name: contract.job_name,
      derived_outcome: derivedOutcome,
      db_status: dbStatus,
      healthy_anchor_eligible: healthy,
      phases: phases,
      counts: counts,
      item_outcomes: items,
    };
  }

  root.SAExtensionRunProtocol = Object.freeze({
    OPERATION_CONTRACTS: OPERATION_CONTRACTS,
    ProtocolError: ProtocolError,
    REASON_CODES: REASON_CODES,
    SCHEMA_VERSION: SCHEMA_VERSION,
    deriveRunResult: deriveRunResult,
  });
}(globalThis));
