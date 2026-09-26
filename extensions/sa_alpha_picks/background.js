// background.js — Service worker for SA Alpha Picks extension
// Orchestrates: open tab → wait for DOM → scrape current → switch to closed → scrape → native messaging → close tab

"use strict";

if (typeof SAExtensionRunProtocol === "undefined" && typeof importScripts === "function") {
  importScripts("extension_run_protocol.js");
}
if (typeof SAExtensionDiagnostics === "undefined" && typeof importScripts === "function") {
  importScripts("extension_diagnostics.js");
}
if (typeof SAExtensionTelemetry === "undefined" && typeof importScripts === "function") {
  importScripts("extension_telemetry.js");
}
if (typeof SACompanyRefresh === "undefined" && typeof importScripts === "function") {
  importScripts("company_refresh.js");
}
if (typeof SAQueue === "undefined" && typeof importScripts === "function") {
  importScripts("acquisition_queue.js");
}
if (typeof SAAcquisition === "undefined" && typeof importScripts === "function") {
  importScripts("acquisition_client.js");
}
if (typeof SACommentCapture === "undefined" && typeof importScripts === "function") {
  importScripts("comment_capture.js");
}

const SA_CURRENT_URL = "https://seekingalpha.com/alpha-picks/picks/current";
const SA_CLOSED_URL = "https://seekingalpha.com/alpha-picks/picks/removed";
const SA_ARTICLES_URL = "https://seekingalpha.com/alpha-picks/articles";
const SA_MARKET_NEWS_URL = "https://seekingalpha.com/market-news";
const NATIVE_HOST = "com.mindfulrl.sa_alpha_picks";
const TABLE_SELECTOR = "table tbody tr";
const ALPHA_PICKS_PAGE_TIMEOUT_MS = 90 * 1000;
const ALPHA_PICKS_ROW_SELECTORS = [
  "table tbody tr",
  '[role="row"]',
  'div[role="row"]',
];
const PAYWALL_MARKERS = ["Subscribe to unlock", "Upgrade your plan", "Premium required"];
const ALPHA_PICKS_AUTO_SYNC_ALARM = "alpha-picks-auto-sync";
const ALPHA_PICKS_AUTO_SYNC_DEFAULT_PERIOD_MINUTES = 30;
const ALPHA_PICKS_AUTO_SYNC_ALLOWED_PERIODS = [15, 30, 60];
const MARKET_NEWS_AUTO_SYNC_ALARM = "market-news-auto-sync";
const SA_ACQUISITION_COOLDOWN_ALARM = "sa-acquisition-cooldown";
const MARKET_NEWS_AUTO_SYNC_DEFAULT_PERIOD_MINUTES = 60;
const MARKET_NEWS_AUTO_SYNC_AUTO_VALUE = "auto";
const MARKET_NEWS_AUTO_SYNC_HEARTBEAT_MINUTES = 5;
const MARKET_NEWS_AUTO_SYNC_ALLOWED_PERIODS = [5, 15, 60];
const MARKET_NEWS_AUTO_SYNC_WINDOWS_ET = {
  weekday: [
    { start: 0, end: 4 * 60, interval: 15 },
    { start: 4 * 60, end: 5 * 60, interval: 5 },
    { start: 5 * 60, end: 6 * 60, interval: 15 },
    { start: 6 * 60, end: 12 * 60, interval: 60 },
    { start: 12 * 60, end: 19 * 60, interval: 15 },
    { start: 19 * 60, end: 24 * 60, interval: 5 },
  ],
  weekend: [
    { start: 0, end: 1 * 60, interval: 60 },
    { start: 1 * 60, end: 2 * 60, interval: 15 },
    { start: 2 * 60, end: 12 * 60, interval: 60 },
    { start: 12 * 60, end: 13 * 60, interval: 15 },
    { start: 13 * 60, end: 15 * 60, interval: 60 },
    { start: 15 * 60, end: 16 * 60, interval: 15 },
    { start: 16 * 60, end: 18 * 60, interval: 60 },
    { start: 18 * 60, end: 20 * 60, interval: 15 },
    { start: 20 * 60, end: 22 * 60, interval: 5 },
    { start: 22 * 60, end: 24 * 60, interval: 15 },
  ],
};
const MARKET_NEWS_DETAIL_BACKFILL_LIMITS = {
  quick: 0,
  catchup: 6,
  full: 20,
  backfill: 60,
  manual: 0,
};
const MARKET_NEWS_DETAIL_CURRENT_LIMITS = {
  quick: 18,
  catchup: 12,
  full: 30,
  backfill: 20,
  manual: 20,
};
const MARKET_NEWS_DETAIL_TOTAL_LIMITS = {
  quick: 18,
  catchup: 18,
  full: 30,
  backfill: 80,
  manual: 20,
};
const MARKET_NEWS_INCIDENT_RECOVERY_MAX_HOURS = 168;
const MARKET_NEWS_INCIDENT_MAX_LIST_SCROLL_ROUNDS = 60;
const MARKET_NEWS_INCIDENT_MAX_LIST_ELAPSED_MS = 600000;
const MARKET_NEWS_INCIDENT_STABLE_ROUNDS = 5;
const MARKET_NEWS_REPAIR_DETAIL_ATTEMPTS_PER_PASS = 80;
const MARKET_NEWS_ROUTINE_CATCHUP_HOURS = 24;
const ALPHA_PICKS_ARTICLE_LIST_ROUNDS = Object.freeze({
  quick: 5,
  full: 200,
  backfill: 200,
});

function createExtensionTelemetryEventId() {
  if (globalThis.crypto && typeof globalThis.crypto.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  if (globalThis.crypto && typeof globalThis.crypto.getRandomValues === "function") {
    var bytes = new Uint8Array(16);
    globalThis.crypto.getRandomValues(bytes);
    bytes[6] = (bytes[6] & 15) | 64;
    bytes[8] = (bytes[8] & 63) | 128;
    var hex = Array.from(bytes, function (value) {
      return value.toString(16).padStart(2, "0");
    }).join("");
    return [hex.slice(0, 8), hex.slice(8, 12), hex.slice(12, 16),
      hex.slice(16, 20), hex.slice(20)].join("-");
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (char) {
    var value = Math.floor(Math.random() * 16);
    return (char === "x" ? value : ((value & 3) | 8)).toString(16);
  });
}

function deliverExtensionTelemetry(record) {
  return new Promise(function (resolve, reject) {
    var settled = false;
    var settle = function (callback, value) {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      callback(value);
    };
    var timer = setTimeout(function () {
      settle(reject, new Error("telemetry_timeout"));
    }, 2000);
    chrome.runtime.sendNativeMessage(
      NATIVE_HOST,
      Object.assign({action: "record_extension_job"}, record),
      function (response) {
        if (chrome.runtime.lastError) {
          settle(reject, new Error("native_host_unavailable"));
          return;
        }
        settle(resolve, response || {
          status: "error",
          persisted: false,
          error_code: "invalid_native_response",
        });
      }
    );
  });
}

var extensionTelemetryController = SAExtensionTelemetry.createController({
  storage: chrome.storage.local,
  now: Date.now,
  uuid: createExtensionTelemetryEventId,
  deliver: deliverExtensionTelemetry,
});
const COLLECTOR_TABS_STORAGE_KEY = "saCollectorTabs";
const COLLECTOR_TAB_STALE_MS = 10 * 60 * 1000;
const DEFAULT_TAB_LOAD_TIMEOUT_MS = 30 * 1000;
const MARKET_NEWS_INITIAL_TAB_LOAD_TIMEOUT_MS = 45 * 1000;
const MARKET_NEWS_RETRY_TAB_LOAD_TIMEOUT_MS = 45 * 1000;
const MARKET_NEWS_DETAIL_TAB_LOAD_TIMEOUT_MS = 45 * 1000;
const MARKET_NEWS_DETAIL_ITEM_TIMEOUT_MS = 90 * 1000;
const MARKET_NEWS_PROFILES = {
  quick: {
    name: "quick",
    maxDetailFetches: 18,
    recentKnownIdsLimit: 250,
    knownTailStopCount: 8,
    listStartMinMs: 700,
    listStartMaxMs: 1300,
    listScrolls: 3,
    listScrollSettleMinMs: 1400,
    listScrollSettleMaxMs: 2200,
    detailReadyDwellMinMs: 1200,
    detailReadyDwellMaxMs: 2200,
    detailGapMinMs: 3500,
    detailGapMaxMs: 6000,
    retryDelayMinMs: 2500,
    retryDelayMaxMs: 4000,
  },
  catchup: {
    name: "catchup",
    maxDetailFetches: 18,
    recentKnownIdsLimit: 250,
    knownTailStopCount: 8,
    listStartMinMs: 700,
    listStartMaxMs: 1300,
    listScrolls: 3,
    listScrollSettleMinMs: 1400,
    listScrollSettleMaxMs: 2200,
    detailReadyDwellMinMs: 1200,
    detailReadyDwellMaxMs: 2200,
    detailGapMinMs: 3500,
    detailGapMaxMs: 6000,
    retryDelayMinMs: 2500,
    retryDelayMaxMs: 4000,
  },
  full: {
    name: "full",
    maxDetailFetches: 30,
    recentKnownIdsLimit: 400,
    knownTailStopCount: 10,
    listStartMinMs: 900,
    listStartMaxMs: 1600,
    listScrolls: 8,
    listScrollSettleMinMs: 1800,
    listScrollSettleMaxMs: 2800,
    detailReadyDwellMinMs: 1500,
    detailReadyDwellMaxMs: 2600,
    detailGapMinMs: 4500,
    detailGapMaxMs: 7500,
    retryDelayMinMs: 3000,
    retryDelayMaxMs: 5000,
  },
  backfill: {
    name: "backfill",
    maxDetailFetches: 80,
    recentKnownIdsLimit: 600,
    knownTailStopCount: 12,
    listStartMinMs: 1200,
    listStartMaxMs: 2200,
    listScrolls: 8,
    listScrollSettleMinMs: 2200,
    listScrollSettleMaxMs: 3600,
    detailReadyDwellMinMs: 1800,
    detailReadyDwellMaxMs: 3200,
    detailGapMinMs: 6000,
    detailGapMaxMs: 10000,
    retryDelayMinMs: 4000,
    retryDelayMaxMs: 6500,
  },
  manual: {
    name: "manual",
    maxDetailFetches: 20,
    recentKnownIdsLimit: 300,
    knownTailStopCount: 8,
    listStartMinMs: 1000,
    listStartMaxMs: 1800,
    listScrolls: 4,
    listScrollSettleMinMs: 1800,
    listScrollSettleMaxMs: 2800,
    detailReadyDwellMinMs: 1500,
    detailReadyDwellMaxMs: 2600,
    detailGapMinMs: 4000,
    detailGapMaxMs: 6500,
    retryDelayMinMs: 3000,
    retryDelayMaxMs: 5000,
  },
};
const COMMENT_SCROLL_PROFILES = {
  quick: {
    name: "quick",
    maxScrolls: 12,
    maxDurationMs: 12000,
    staleRounds: 2,
    settleMs: 900,
  },
  full: {
    name: "full",
    maxScrolls: 80,
    maxDurationMs: 60000,
    staleRounds: 4,
    settleMs: 1400,
  },
  backfill: {
    name: "backfill",
    maxScrolls: 140,
    maxDurationMs: 120000,
    staleRounds: 5,
    settleMs: 1600,
  },
  manual: {
    name: "manual",
    maxScrolls: 60,
    maxDurationMs: 45000,
    staleRounds: 4,
    settleMs: 1200,
  },
};
const ARTICLE_INITIAL_SETTLE_MS = 2500;
const RECONCILIATION_ENRICHMENT_LIMITS = { quick: 4, full: 12, backfill: 20 };
var marketNewsRefreshInFlight = false;
var saAcquisitionQueue = SAQueue.create({now:Date.now});
var saAcquisitionTask = null;
var saSyncJobInFlight = false;
var saAutoJobPending = Object.create(null);

var EXTENSION_ITEM_RETRYABLE_REASONS = [
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
];

var EXTENSION_PHASE_FAILURE_REASONS = SAExtensionRunProtocol.REASON_CODES.filter(function (reason) {
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

function extensionPhase(state, reasonCode) {
  return { state: state, reason_code: reasonCode == null ? null : reasonCode };
}

function stableExtensionReason(reasonCode, allowed, fallback) {
  return allowed.indexOf(reasonCode) === -1 ? fallback : reasonCode;
}

function recordExtensionFailure(diagnostics, entry) {
  if (diagnostics && typeof diagnostics.record === "function") {
    diagnostics.record(entry);
  }
  return 1;
}

function extensionNativeFailure(response) {
  var errorCode = response && typeof response.error_code === "string"
    ? response.error_code
    : null;
  if ([
    "database_busy",
    "database_integrity_failed",
    "database_write_failed",
  ].indexOf(errorCode) !== -1) {
    return {
      stage: "local_persistence",
      reason_code: errorCode,
      retryable: errorCode !== "database_integrity_failed",
    };
  }
  if (errorCode === "invalid_native_response" || errorCode === "invalid_sidecar_response") {
    return {
      stage: "native_transport",
      reason_code: "native_response_invalid",
      retryable: true,
    };
  }
  if (response && errorCode !== "native_host_unavailable") {
    return {
      stage: "native_transport",
      reason_code: "native_response_invalid",
      retryable: true,
    };
  }
  return {
    stage: "native_transport",
    reason_code: "native_host_unavailable",
    retryable: true,
  };
}

function recordNativeExtensionFailure(diagnostics, response, targetKind, targetRef) {
  var mapped = extensionNativeFailure(response);
  var entry = {
    stage: mapped.stage,
    reason_code: mapped.reason_code,
    target_kind: targetKind,
    retryable: mapped.retryable,
    attempt_count: 1,
  };
  if (targetRef) entry.target_ref = String(targetRef);
  return recordExtensionFailure(diagnostics, entry);
}

function legacyResultIsOk(value) {
  return !!value && typeof value === "object" && value.recorded_failure !== true &&
    (value.status === "ok" || value.ok === true);
}

function skippedProtocolPhases(operation, reasonCode) {
  var contract = SAExtensionRunProtocol.OPERATION_CONTRACTS[operation];
  var phases = {};
  contract.phases.forEach(function (name) {
    phases[name] = extensionPhase("skipped", reasonCode);
  });
  return phases;
}

function failedProtocolPhases(operation, failedPhase, reasonCode) {
  var contract = SAExtensionRunProtocol.OPERATION_CONTRACTS[operation];
  var failedIndex = contract.phases.indexOf(failedPhase);
  if (failedIndex < 0) failedIndex = 0;
  var phases = {};
  contract.phases.forEach(function (name, index) {
    if (index < failedIndex) phases[name] = extensionPhase("complete", null);
    else if (index === failedIndex) phases[name] = extensionPhase("failed", reasonCode);
    else phases[name] = extensionPhase("skipped", "operator_cancelled");
  });
  return phases;
}

function buildAlphaPicksProtocolResult(mode, legacyResult) {
  legacyResult = legacyResult || {};
  var details = legacyResult.details || {};
  var currentOk = legacyResultIsOk(legacyResult.current);
  var closedOk = legacyResultIsOk(legacyResult.closed);
  var upstreamFailure = !legacyResult.details && (!currentOk || !closedOk)
    ? (!currentOk ? "current_scope_failed" : "closed_scope_failed") : null;
  var detailFailed = !!upstreamFailure || Number(details.failed || 0) > 0 || !!details.error;
  var detailReason = upstreamFailure || (details.error
    ? stableExtensionReason(details.reason_code, EXTENSION_PHASE_FAILURE_REASONS, "article_metadata_failed")
    : stableExtensionReason(details.reason_code, EXTENSION_PHASE_FAILURE_REASONS, "detail_save_failed"));
  var reconciliationBlocked = !!upstreamFailure || !!details.error;
  var reconciliationFailed = reconciliationBlocked || Number(details.reconciliation_failed || 0) > 0;

  return SAExtensionRunProtocol.deriveRunResult({
    schema_version: 1,
    operation: "alpha_picks_sync",
    mode: mode,
    phases: {
      current_picks: currentOk
        ? extensionPhase("complete", null)
        : extensionPhase("failed", "current_scope_failed"),
      closed_picks: closedOk
        ? extensionPhase("complete", null)
        : extensionPhase("failed", "closed_scope_failed"),
      article_details: detailFailed
        ? extensionPhase("failed", detailReason)
        : extensionPhase("complete", null),
      reconciliation: reconciliationFailed
        ? extensionPhase("failed", reconciliationBlocked ? detailReason : "reconciliation_failed")
        : extensionPhase("complete", null),
    },
    item_outcomes: [],
  });
}

function buildAlphaPicksManualProtocolResult(legacyResult) {
  legacyResult = legacyResult || {};
  var failed = Number(legacyResult.failed || 0) > 0 || legacyResult.status === "error";
  var reconciliationFailed = Number(legacyResult.reconciliation_failed || 0) > 0;
  return SAExtensionRunProtocol.deriveRunResult({
    schema_version: 1,
    operation: "alpha_picks_manual_fetch",
    mode: "manual",
    phases: {
      manual_fetch: failed
        ? extensionPhase("failed", "article_detail_failed")
        : extensionPhase("complete", null),
      reconciliation: reconciliationFailed
        ? extensionPhase("failed", "reconciliation_failed")
        : extensionPhase("complete", null),
    },
    item_outcomes: [],
  });
}

function marketNewsFailureReason(result, fallback) {
  return stableExtensionReason(
    result && result.reason_code,
    EXTENSION_PHASE_FAILURE_REASONS,
    fallback
  );
}

function buildMarketNewsProtocolResult(mode, legacyResult) {
  legacyResult = legacyResult || {};
  var operation = "market_news_sync";
  var phases;
  var detailFailures = Array.isArray(legacyResult.detail_failures)
    ? legacyResult.detail_failures
    : [];
  var itemOutcomes = detailFailures.map(function (failure) {
    return {
      news_id: String(failure && failure.news_id || ""),
      state: "failed_retryable",
      reason_code: stableExtensionReason(
        failure && failure.reason_code,
        EXTENSION_ITEM_RETRYABLE_REASONS,
        "unknown_failure"
      ),
      attempt_count: Number.isInteger(failure && failure.attempt_count)
        && failure.attempt_count > 0 ? failure.attempt_count : 1,
      evidence_code: null,
    };
  });

  if (legacyResult.status === "skipped" || legacyResult.status === "busy") {
    var skippedReason = legacyResult.status === "busy" || legacyResult.reason === "already_pending"
      ? "already_pending"
      : (legacyResult.reason === "not_due" ? "not_due" : "operator_cancelled");
    phases = skippedProtocolPhases(operation, skippedReason);
    itemOutcomes = [];
  } else if (legacyResult.status === "error") {
    var failurePhase = legacyResult.failure_phase || "list_navigation";
    var fallbackByPhase = {
      list_navigation: "list_navigation_failed",
      list_scrape: "list_scrape_failed",
      metadata_save: "metadata_save_failed",
      detail_fetch: "detail_queue_failed",
      capture_readback: "capture_readback_failed",
    };
    phases = failedProtocolPhases(
      operation,
      failurePhase,
      marketNewsFailureReason(legacyResult, fallbackByPhase[failurePhase] || "unknown_failure")
    );
    itemOutcomes = [];
  } else if (legacyResult.status !== "ok") {
    phases = failedProtocolPhases(
      operation,
      "list_navigation",
      "protocol_invalid"
    );
    itemOutcomes = [];
  } else {
    var hasDetailFailures = Number(legacyResult.detail_failed || 0) > 0
      || itemOutcomes.length > 0;
    var detailReason = itemOutcomes.length > 0
      ? itemOutcomes[0].reason_code
      : marketNewsFailureReason(legacyResult, "detail_queue_failed");
    phases = {
      list_navigation: extensionPhase("complete", null),
      list_scrape: extensionPhase("complete", null),
      metadata_save: extensionPhase("complete", null),
      detail_fetch: hasDetailFailures
        ? extensionPhase("failed", detailReason)
        : extensionPhase("complete", null),
      capture_readback: legacyResult.capture_readback_failed
        ? extensionPhase("failed", "capture_readback_failed")
        : extensionPhase("complete", null),
    };
  }

  return SAExtensionRunProtocol.deriveRunResult({
    schema_version: 1,
    operation: operation,
    mode: mode,
    phases: phases,
    item_outcomes: itemOutcomes,
  });
}

function buildFailedExtensionProtocolResult(operation, mode) {
  var contract = SAExtensionRunProtocol.OPERATION_CONTRACTS[operation];
  if (!contract) return null;
  return SAExtensionRunProtocol.deriveRunResult({
    schema_version: 1,
    operation: operation,
    mode: mode,
    phases: failedProtocolPhases(operation, contract.phases[0], "unknown_failure"),
    item_outcomes: [],
  });
}

function attachExtensionRunProtocol(operation, mode, legacyResult) {
  if (!operation) return legacyResult;
  var result = legacyResult && typeof legacyResult === "object" ? legacyResult : {};
  var stop = result.acquisition_stop;
  if (result.status === "deferred" || result.status === "skipped" || result.status === "cancelled" || result.acquisition_outcome === "reused" || stop) {
    var contract = SAExtensionRunProtocol.OPERATION_CONTRACTS[operation];
    var phases = {};
    var complete = result.completed_phases || [];
    var skipped = !stop && result.status !== "deferred";
    var reason = stop && stop.reason || result.reason || "collector_unavailable";
    if (["capacity_exhausted","site_pacing","waiting_for_priority_work","collector_unavailable","collector_other_installation","site_paused"].indexOf(reason) === -1) reason = "collector_unavailable";
    var failed = stop && stop.status === "error";
    var failureSet = false;
    var prior = operation === "market_news_sync" ? buildMarketNewsProtocolResult(mode,Object.assign({},result,{status:"ok"}))
      : operation === "alpha_picks_sync" && result.details ? buildAlphaPicksProtocolResult(mode,result) : null;
    contract.phases.forEach(function (name) {
      if (complete.indexOf(name) !== -1) phases[name] = extensionPhase("complete",null);
      else if (failed && !failureSet) {
        failureSet = true;
        phases[name] = extensionPhase("failed",stop.error_code);
      } else phases[name] = skipped ? extensionPhase("skipped",result.acquisition_outcome === "reused" ? "not_due" : "operator_cancelled") : extensionPhase("deferred",reason);
    });
    if (prior) Object.keys(prior.phases).forEach(function (name) {
      if (prior.phases[name].state === "failed" && (operation === "market_news_sync" || name === "article_details" || name === "reconciliation")) phases[name] = prior.phases[name];
    });
    return Object.assign({},result,{extension_run:SAExtensionRunProtocol.deriveRunResult({schema_version:2,operation:operation,mode:mode,
      phases:phases,item_outcomes:result.item_outcomes || prior && prior.item_outcomes || []})});
  }
  var structured;
  if (operation === "alpha_picks_sync") {
    structured = buildAlphaPicksProtocolResult(mode, result);
  } else if (operation === "alpha_picks_manual_fetch") {
    structured = buildAlphaPicksManualProtocolResult(result);
  } else if (operation === "alpha_picks_body_repair") {
    structured = SAExtensionRunProtocol.deriveRunResult({
      schema_version: 2, operation: operation, mode: mode, item_outcomes: [],
      phases: result.status === "ok" && result.body_saved === true
        ? {extraction:extensionPhase("complete",null), persistence:extensionPhase("complete",null)}
        : failedProtocolPhases(operation, result.failure_phase || "persistence",
          stableExtensionReason(result.reason_code, EXTENSION_PHASE_FAILURE_REASONS, "detail_save_failed")),
    });
  } else if (operation === "market_news_sync") {
    structured = buildMarketNewsProtocolResult(mode, result);
  } else if (operation === "company_financial_capture") {
    var skipReason = result.acquisition_outcome === "reused" ? "not_due"
      : result.status === "cancelled" ? "operator_cancelled"
      : result.status === "deferred" && (result.error_code === "sa_company_pacing" || result.deferral_kind === "scope") ? "not_due"
      : result.status === "deferred" && /sa_company_collector_(busy|other_browser|unselected)/.test(result.error_code || "") ? "already_pending" : null;
    structured = SAExtensionRunProtocol.deriveRunResult({
      schema_version: 1, operation: operation, mode: mode, item_outcomes: [],
      phases: skipReason ? {extraction:extensionPhase("skipped",skipReason), persistence:extensionPhase("skipped",skipReason)} : result.status === "ok"
        ? { extraction: extensionPhase("complete", null), persistence: extensionPhase("complete", null) }
        : failedProtocolPhases(operation, result.failure_phase || "extraction", result.reason_code || "company_capture_rejected"),
    });
  } else if (operation === "market_news_retry_recorded" || operation === "market_news_incident_recovery") {
    var recoveryPhases = {};
    SAExtensionRunProtocol.OPERATION_CONTRACTS[operation].phases.forEach(function (name) {
      recoveryPhases[name] = result.status === "succeeded" ? extensionPhase("complete",null)
        : result.status === "running" ? extensionPhase("deferred","waiting_for_priority_work")
        : extensionPhase("failed","unknown_failure");
    });
    structured = SAExtensionRunProtocol.deriveRunResult({schema_version:2,operation:operation,mode:mode,phases:recoveryPhases,item_outcomes:[]});
  } else {
    throw new Error("unsupported extension operation");
  }
  // Upgrade new producers only; validators still preserve delayed v1 evidence.
  var projection = {schema_version:2,operation:operation,mode:mode,phases:structured.phases,item_outcomes:structured.item_outcomes};
  return Object.assign({}, result, { extension_run: SAExtensionRunProtocol.deriveRunResult(projection) });
}

// --- Message listener (from popup) ---

async function forwardReconciliationNative(payload, sender) {
  if (!sender || sender.id !== chrome.runtime.id || sender.url !== chrome.runtime.getURL("popup.html")
      || !payload || typeof payload !== "object" || Array.isArray(payload)
      || !["get_reconciliation_queue", "accept_reconciliation_link", "reject_reconciliation_candidate"].includes(payload.action)) {
    return {status:"error", error_code:"extension_request_rejected"};
  }
  return sendNativeMessage2(payload);
}

var companyCollectorIdentity = null;
async function companyCollectorControl(operation, extra) {
  if (!companyCollectorIdentity) companyCollectorIdentity = (async function () {
    var existing = (await chrome.storage.local.get("companyCollectorIdentity")).companyCollectorIdentity;
    if (existing) return existing;
    var client = {client_id:crypto.randomUUID(), browser:
      typeof navigator !== "undefined" && /Firefox\//.test(navigator.userAgent) ? "firefox" : "chrome"};
    await chrome.storage.local.set({companyCollectorIdentity:client});
    return client;
  })();
  return sendNativeMessage2(Object.assign({}, extra || {}, {
    action:"sa_acquisition_control", operation:operation, client:await companyCollectorIdentity,
  }));
}

async function syncAcquisitionBadge(state, persistStatus) {
  var cached = await chrome.storage.local.get(["saAcquisitionRestriction","saAcquisitionPending"]);
  var reason = state && (state.paused_reason || state.rate_limited && "rate_limited"
    || Object.keys(state.capability_pauses || {}).length && "access_restricted");
  if (!reason && cached.saAcquisitionPending && cached.saAcquisitionRestriction) reason = cached.saAcquisitionRestriction.reason;
  if (!reason && !saSyncJobInFlight && (cached.saAcquisitionPending || state && state.is_owner && state.active)) reason = "recovery_required";
  if (state && persistStatus !== false) await chrome.storage.local.set({saAcquisitionStatus:state});
  if (state && state.rate_limited && Date.parse(state.rate_limit_until) > Date.now()) {
    await chrome.alarms.create(SA_ACQUISITION_COOLDOWN_ALARM,{when:Date.parse(state.rate_limit_until)});
  }
  if (chrome.action) {
    await chrome.action.setBadgeText({text:reason ? "!" : ""});
    if (reason) await chrome.action.setBadgeBackgroundColor({color:"#be2535"});
    await chrome.action.setTitle({title:reason === "login_required" ? "Seeking Alpha: sign in required"
      : reason === "access_restricted" ? "Seeking Alpha: check subscription access"
      : reason === "recovery_required" ? "Seeking Alpha: stopped capture needs recovery"
      : reason ? "Seeking Alpha: acquisition paused" : "SA Alpha Picks"});
  }
}

var saAcquisition = SAAcquisition.create({control:function (operation,extra) {return companyCollectorControl(operation,extra);},storage:chrome.storage.local,now:Date.now,
  onStatus:function (state) {return syncAcquisitionBadge(state).catch(function () {});}});

async function acquisitionPaused(capability) {
  var saved = await chrome.storage.local.get(["saAcquisitionRestriction","saAcquisitionStatus"]);
  var local = saved.saAcquisitionRestriction, shared = saved.saAcquisitionStatus || {};
  return !!(shared.paused_reason || shared.rate_limited || shared.capability_pauses && shared.capability_pauses[capability]
    || local && local.reason !== "rate_limited" && (local.reason !== "access_restricted" || local.capability === capability));
}

function requireAcquisitionTask() {
  if (!saAcquisitionTask) throw new SAAcquisition.Stop({status:"deferred",reason:"collector_unavailable"});
  if (saAcquisitionTask.stop) throw new SAAcquisition.Stop(saAcquisitionTask.stop);
  return saAcquisitionTask;
}

function saDestination(url) {
  var parsed = new URL(url);
  if (parsed.origin !== "https://seekingalpha.com" || parsed.username || parsed.password) throw new Error("sa_acquisition_url_rejected");
  return parsed.pathname.indexOf("/alpha-picks/picks/") === 0 ? "picks"
    : parsed.pathname.indexOf("/alpha-picks/") === 0 ? "article"
    : parsed.pathname.indexOf("/symbol/") === 0 ? "financials" : "news";
}

var managedSaTabs = {
  create:function (options) {
    return requireAcquisitionTask().navigate({kind:"create",destinationClass:saDestination(options.url)},function () {return chrome.tabs.create(options);});
  },
  update:function (tabId, options) {
    if (!options.url) return chrome.tabs.update(tabId,options);
    return requireAcquisitionTask().navigate({kind:"update",destinationClass:saDestination(options.url)},function () {return chrome.tabs.update(tabId,options);});
  },
  reload:async function (tabId) {
    var task = requireAcquisitionTask();
    var tab = await chrome.tabs.get(tabId);
    return task.navigate({kind:"reload",destinationClass:saDestination(tab.url)},function () {return chrome.tabs.reload(tabId);});
  },
};

async function observeSaRestriction(code) {
  var reason = String(code || "").replace(/^sa_company_/,"");
  if (["login_required","human_verification_required","rate_limited","access_restricted"].indexOf(reason) === -1) return false;
  if (saAcquisitionTask) {
    var sharedState;
    try { sharedState = await saAcquisitionTask.observeRestriction(reason); }
    finally {
      var capability = SAAcquisition.capability(saAcquisitionTask.operation || "alpha_picks_sync");
      var pauseAll = reason !== "access_restricted";
      if (pauseAll || capability === "alpha_picks") await chrome.alarms.clear(ALPHA_PICKS_AUTO_SYNC_ALARM).catch(function () {});
      if (pauseAll || capability === "news") await chrome.alarms.clear(MARKET_NEWS_AUTO_SYNC_ALARM).catch(function () {});
      if (pauseAll || capability === "financials") await chrome.alarms.clear(SACompanyRefresh.alarm).catch(function () {});
      var localState = {paused_reason:pauseAll && reason !== "rate_limited" ? reason : null,capability_pauses:{},rate_limited:reason === "rate_limited"};
      if (!pauseAll) localState.capability_pauses[capability] = reason;
      await syncAcquisitionBadge(sharedState || localState).catch(function () {});
    }
  }
  return true;
}

function isAcquisitionStop(error) {return !!error && error.name === "SAAcquisitionStop";}

function readSaAccessMarkers() {
  function visible(node) {
    if (!node) return false;
    for (var item=node; item; item=item.parentElement) {
      var style=getComputedStyle(item);
      if (item.hidden || item.getAttribute("aria-hidden") === "true" || style.display === "none" || style.visibility === "hidden") return false;
    }
    return true;
  }
  var headline = document.querySelector("h1");
  var heading = visible(headline) ? headline.innerText || "" : "";
  var title = document.title || "";
  if (/verify you are human|human verification|just a moment|are you a robot/i.test(title + " " + heading)) return "human_verification_required";
  var challenge = document.querySelector('iframe[src*="captcha"],iframe[src*="challenge"],[data-testid="captcha"]');
  if (visible(challenge)) return "human_verification_required";
  if (/^\/(?:login|sign_in|signin)(?:\/|$)/.test(location.pathname)) return "login_required";
  if (/too many requests|rate limit exceeded/i.test(title + " " + heading)) return "rate_limited";
  return null;
}

async function inspectSaAccess(tabId) {
  if (!saAcquisitionTask) return;
  requireAcquisitionTask();
  var result = await chrome.scripting.executeScript({target:{tabId:tabId},func:readSaAccessMarkers});
  var reason = result[0] && result[0].result;
  if (typeof reason === "string" && await observeSaRestriction(reason)) throw new SAAcquisition.Stop(saAcquisitionTask.stop);
}

async function runCoordinatedCompanyScope(scope, mode, admitted, observeFailure, intervalDays, diagnostics, requestedAt) {
  if (!await admitted()) return {status:"cancelled"};
  requireAcquisitionTask();
  return refreshCompanyFinancialScope(scope,diagnostics,admitted,async function (code) {
    await observeSaRestriction(code);
    if (observeFailure) await observeFailure(code);
  },true);
}

const companyFinancialRefresh = SACompanyRefresh.create({
  storage: chrome.storage.local,
  alarms: chrome.alarms,
  control:companyCollectorControl,
  shouldPause:function () {return acquisitionPaused("financials");},
  setTimer:setTimeout,clearTimer:clearTimeout,
  resolveWatchlist:function () { return sendNativeMessage2({action:"get_company_watchlist"}); },
  runScope: function (scope, mode, admitted, observeFailure, intervalDays, requestedAt, force) {
    scope = Object.assign({}, scope, {ticker:SACompanyRefresh.providerSymbol(scope.ticker)});
    return enqueueSaSyncJob({displayName: scope.ticker + " " + scope.view + " financials",
      operation: "company_financial_capture", mode: mode,eligible:admitted,
      acquisition:{scope:scope,force:force === true,interval_days:intervalDays,requested_at:requestedAt || null}}, function (diagnostics) {
      return runCoordinatedCompanyScope(scope, mode, admitted, observeFailure, intervalDays, diagnostics, requestedAt);
    });
  },
});

var saActivationChain = Promise.resolve();
function activateSaUpdates(request) {
  var work = saActivationChain.then(async function () {
    var step = "confirmation", disabled = false;
    try {
      if (!request || request.confirm_activation !== true || request.confirm_schedules !== true) throw new Error("sa_acquisition_confirmation_required");
      var config = SACompanyRefresh.normalize(request.config);
      var policy = request.policy;
      var keys = ["hour_limit","day_limit","hour_reserve","day_reserve"];
      var uncapped = policy && policy.hour_limit === null && policy.day_limit === null
        && policy.hour_reserve === 0 && policy.day_reserve === 0;
      var capped = policy && keys.every(function(key) {return Number.isSafeInteger(policy[key]);})
        && policy.hour_limit>0 && policy.day_limit>0 && policy.hour_reserve>=0 && policy.day_reserve>=0
        && policy.hour_reserve<=policy.hour_limit && policy.day_reserve<=policy.day_limit;
      if (!policy || Object.keys(policy).length !== keys.length || (!uncapped && !capped)) throw new Error("sa_acquisition_policy_invalid");
      step = "status";
      var state = await companyCollectorControl("status");
      var upgrade = state && state.error_code === "sa_acquisition_upgrade_required" && request.confirm_stopped === true;
      if (!upgrade && (!state || state.status !== "ok")) throw new Error(state && state.error_code || "sa_company_collector_unavailable");
      if (!upgrade && state.generation !== request.expected_generation) throw new Error("sa_acquisition_generation_stale");
      if (!upgrade && state.active) throw new Error("sa_company_collector_busy");
      var routine = await chrome.storage.local.get(["alphaPicksAutoSyncEnabled","alphaPicksAutoSyncIntervalMinutes","alphaPicksAutoSyncRevision",
        "marketNewsAutoSyncEnabled","marketNewsAutoSyncIntervalMinutes","marketNewsAutoSyncRevision"]);
      step = "disable";
      disabled = true;
      var alphaSuspension = await setAlphaPicksAutoSyncEnabled(false,routine.alphaPicksAutoSyncIntervalMinutes,
        routine.alphaPicksAutoSyncRevision == null ? 0 : routine.alphaPicksAutoSyncRevision);
      var newsSuspension = await setMarketNewsAutoSyncEnabled(false,routine.marketNewsAutoSyncIntervalMinutes,
        routine.marketNewsAutoSyncRevision == null ? 0 : routine.marketNewsAutoSyncRevision);
      await companyFinancialRefresh.configure(Object.assign({},config,{enabled:false}));
      if (!upgrade && state.policy && !state.is_owner) {
        step = "select";
        state = await companyCollectorControl("select",{expected_generation:request.expected_generation,confirm_schedules:true});
        if (!state || state.status !== "ok" || !state.is_owner) throw new Error(state && state.error_code || "sa_company_collector_unavailable");
      }
      step = "configure";
      state = await companyCollectorControl("configure",{policy:policy,financial_gap_seconds:config.financial_gap_seconds,
        expected_generation:upgrade ? 0 : state.generation,confirm_activation:true,require_idle:true,
        upgrade:upgrade,confirm_stopped:request.confirm_stopped === true});
      if (!state || state.status !== "ok") throw new Error(state && state.error_code || "sa_company_collector_unavailable");
      if (!state.is_owner || state.generation === 0) {
        step = "select";
        state = await companyCollectorControl("select",{expected_generation:state.generation,confirm_schedules:true});
        if (!state || state.status !== "ok" || !state.is_owner) throw new Error(state && state.error_code || "sa_company_collector_unavailable");
      }
      step = "persist";
      await chrome.storage.local.set({saAcquisitionLedger:state.ledger_id,saAcquisitionStatus:state});
      step = "enable";
      await companyFinancialRefresh.configure(config);
      // Restore only this activation's suspension, never a newer operator choice.
      if (alphaSuspension.status === "ok") await setAlphaPicksAutoSyncEnabled(
        routine.alphaPicksAutoSyncEnabled === true,routine.alphaPicksAutoSyncIntervalMinutes,alphaSuspension.revision);
      if (newsSuspension.status === "ok") await setMarketNewsAutoSyncEnabled(
        routine.marketNewsAutoSyncEnabled === true,routine.marketNewsAutoSyncIntervalMinutes,newsSuspension.revision);
      await syncAcquisitionBadge(state);
      return companyFinancialRefresh.status();
    } catch (error) {
      if (disabled) {
        await setAlphaPicksAutoSyncEnabled(false).catch(function () {});
        await setMarketNewsAutoSyncEnabled(false).catch(function () {});
        if (config) await companyFinancialRefresh.configure(Object.assign({},config,{enabled:false})).catch(function () {});
      }
      return {status:"error",error_code:error.message || "sa_acquisition_activation_failed",activation_step:step};
    }
  });
  saActivationChain = work.catch(function () {});
  return work;
}

const ARTICLE_BODY_RECOVERY_STORAGE_KEY = "saArticleBodyRecovery";
const ARTICLE_BODY_RECOVERY_LIMIT = 5;
const ARTICLE_BODY_RECOVERY_MAX_MS = 30 * 60 * 1000;
var articleBodyRecoveryPreview = null;
var articleBodyRecoveryPreviewRevision = 0;
var articleBodyRecoveryActive = null;
var articleBodyRecoveryWrites = Promise.resolve();

function bodyRecoveryTarget(value) {
  if (!value || typeof value.article_id !== "string" || !/^\d+$/.test(value.article_id)
      || typeof value.body_sha256 !== "string" || !/^[a-f0-9]{64}$/.test(value.body_sha256)) return null;
  try {
    var url = new URL(value.url);
    var match = url.pathname.match(/^\/(?:alpha-picks\/articles|article)\/(\d+)(?:-[^/]+)?\/?$/);
    if (url.origin !== "https://seekingalpha.com" || url.username || url.password || url.search || url.hash
        || !match || match[1] !== value.article_id) return null;
    return {article_id:value.article_id, url:url.href, body_sha256:value.body_sha256,
      title:typeof value.title === "string" ? value.title.slice(0,500) : value.article_id,
      published_date:typeof value.published_date === "string" ? value.published_date.slice(0,32) : null};
  } catch (_) {return null;}
}

function bodyRecoveryReason(value, fallback) {
  return ["already_present", "out_of_scope", "source_changed", "operator_cancelled", "interrupted",
    "article_context_changed", "parser_empty", "detail_timeout", "navigation_timeout", "dom_not_ready",
    "detail_save_failed", "native_host_unavailable", "unknown_failure", "manifest_invalid",
    "login_required", "access_restricted", "human_verification_required", "rate_limited",
    "site_paused", "site_pacing", "capacity_exhausted", "waiting_for_priority_work", "collector_unavailable",
    "collector_other_installation", "cleanup_unconfirmed", "batch_timeout",
    "sa_article_body_missing", "sa_article_body_comment_thread",
    "sa_article_body_disclosure_only", "sa_article_body_metadata_only"].includes(value) ? value : fallback;
}

function holdSaAcquisitionLifetime(run, maxMilliseconds) {
  // Timers and one-shot native calls do not keep Firefox event pages alive.
  // Hold a native port for one finite task, never while an idle queue waits.
  function open() {
    if (run.cancelled) return false;
    return new Promise(function (resolve) {
      var port, closed = false, ready = false, handshakeTimer, deadlineTimer;
      function cancelSetup() {
        clearTimeout(handshakeTimer);
        if (run.wake === cancelSetup) run.wake = null;
        resolve(false);
      }
      run.wake = cancelSetup;
      function interrupt(reason) {
        if (closed) return;
        if (!run.cancelled) {
          run.interruption = reason;
          run.cancelled = true;
          if (run.onInterrupted) run.onInterrupted(reason);
        }
        if (run.wake) run.wake();
        clearTimeout(handshakeTimer);
        resolve(false);
      }
      function received(message) {
        if (ready || closed) return;
        if (!message || message.status !== "ok") {interrupt("native_host_unavailable"); return;}
        ready = true;
        clearTimeout(handshakeTimer);
        if (run.wake === cancelSetup) run.wake = null;
        resolve(true);
      }
      function disconnected() {
        // Reading lastError acknowledges Chrome's port error; never expose its
        // native diagnostic text or reconnect automatically.
        void chrome.runtime.lastError;
        interrupt("native_host_unavailable");
      }
      run.closeLifetime = function () {
        closed = true;
        clearTimeout(handshakeTimer);
        clearTimeout(deadlineTimer);
        if (run.wake === cancelSetup) run.wake = null;
        if (port && port.onMessage && port.onDisconnect) {
          port.onMessage.removeListener(received);
          port.onDisconnect.removeListener(disconnected);
          try {port.disconnect();} catch (_) {}
        }
      };
      try {
        port = chrome.runtime.connectNative(NATIVE_HOST);
        if (!port || !port.onMessage || !port.onDisconnect || typeof port.postMessage !== "function") {
          if (port && typeof port.catch === "function") port.catch(function () {});
          interrupt("native_host_unavailable"); return;
        }
        port.onMessage.addListener(received);
        port.onDisconnect.addListener(disconnected);
        handshakeTimer = setTimeout(function () {interrupt("native_host_unavailable");}, 15000);
        if (maxMilliseconds) deadlineTimer = setTimeout(function () {interrupt("batch_timeout");}, maxMilliseconds);
        port.postMessage({action:"ping"});
      } catch (_) {interrupt("native_host_unavailable");}
    });
  }
  // Share Firefox's native-launch lock until consent/handshake completes, not
  // for the lifetime of the port (normal acquisition calls need the same lock).
  return globalThis.navigator && navigator.locks && typeof navigator.locks.request === "function"
    ? navigator.locks.request("arkscope-native-messaging:" + NATIVE_HOST, open) : Promise.resolve(open());
}

function holdArticleBodyRecoveryLifetime(run) {
  run.onInterrupted = function (reason) {
    run.batch.status = "cancelling";
    run.batch.stop_reason = reason;
    persistArticleBodyRecovery(run.batch).catch(function () {});
  };
  return holdSaAcquisitionLifetime(run, ARTICLE_BODY_RECOVERY_MAX_MS);
}

function persistArticleBodyRecovery(batch) {
  batch.counts = {saved:0, failed:0, skipped:0, deferred:0, cancelled:0, pending:0};
  batch.items.forEach(function (item) {
    var name = Object.prototype.hasOwnProperty.call(batch.counts,item.state) ? item.state : "pending";
    batch.counts[name]++;
  });
  var snapshot = JSON.parse(JSON.stringify(batch));
  var write = articleBodyRecoveryWrites.then(function () {
    return chrome.storage.local.set({[ARTICLE_BODY_RECOVERY_STORAGE_KEY]:snapshot});
  });
  articleBodyRecoveryWrites = write.catch(function () {});
  return write;
}

async function articleBodyRecoveryState() {
  if (articleBodyRecoveryActive) return {status:"ok",batch:articleBodyRecoveryActive.batch};
  var saved = await chrome.storage.local.get(ARTICLE_BODY_RECOVERY_STORAGE_KEY);
  var batch = saved[ARTICLE_BODY_RECOVERY_STORAGE_KEY] || null;
  // A suspended worker never resumes a preview or automatically retries a page.
  if (batch && ["running","cancelling"].includes(batch.status)) {
    batch.status = "interrupted";
    batch.items.forEach(function (item) {
      if (item.state === "running") {item.state = "failed"; item.reason = "interrupted";}
      else if (item.state === "queued") {item.state = "cancelled"; item.reason = "interrupted";}
    });
    await persistArticleBodyRecovery(batch);
  }
  return {status:"ok",batch:batch};
}

async function handleArticleBodyRecovery(msg) {
  if (msg.action === "get_article_body_recovery_state") return articleBodyRecoveryState();
  if (msg.action === "cancel_article_body_recovery") {
    var active = articleBodyRecoveryActive;
    if (!active || active.batch.batch_id !== msg.batch_id) return {status:"skipped",reason:"not_running"};
    active.cancelled = true;
    if (active.wake) active.wake();
    active.batch.status = "cancelling";
    await persistArticleBodyRecovery(active.batch);
    return {status:"ok",batch:active.batch};
  }
  if (articleBodyRecoveryActive) return {status:"error",error_code:"already_pending"};
  if (msg.action === "preview_article_body_recovery") {
    articleBodyRecoveryPreview = null;
    var revision = ++articleBodyRecoveryPreviewRevision;
    var response = await sendNativeMessage2({action:"preview_article_body_recovery"});
    if (revision !== articleBodyRecoveryPreviewRevision || articleBodyRecoveryActive) {
      return {status:"error",error_code:"preview_stale"};
    }
    if (!response || response.status !== "ok" || typeof response.manifest_id !== "string"
        || !response.manifest_id || typeof response.as_of !== "string"
        || !/^\d{4}-\d{2}-\d{2}$/.test(response.as_of) || !Array.isArray(response.targets)) {
      return {status:"error",error_code:"body_recovery_preview_unavailable"};
    }
    var targets = response.targets.slice(0,ARTICLE_BODY_RECOVERY_LIMIT).map(bodyRecoveryTarget);
    if (targets.some(function (item) {return !item;})
        || new Set(targets.map(function (item) {return item.article_id;})).size !== targets.length) {
      return {status:"error",error_code:"manifest_invalid"};
    }
    var remaining = response.counts && response.counts.targets;
    articleBodyRecoveryPreview = {status:"ok",manifest_id:response.manifest_id,as_of:response.as_of,
      targets:targets,remaining_count:Number.isSafeInteger(remaining) && remaining >= response.targets.length
        ? remaining : response.targets.length};
    return articleBodyRecoveryPreview;
  }
  var preview = articleBodyRecoveryPreview;
  if (!preview || msg.manifest_id !== preview.manifest_id || !preview.targets.length) {
    return {status:"error",error_code:"preview_required"};
  }
  articleBodyRecoveryPreview = null;
  articleBodyRecoveryPreviewRevision++;
  var batch = {batch_id:crypto.randomUUID(),manifest_id:preview.manifest_id,as_of:preview.as_of,
    status:"running",started_at:new Date().toISOString(),items:preview.targets.map(function (item) {
      return {article_id:item.article_id,title:item.title,state:"queued",reason:null,attempt_count:0};
    })};
  var run = {batch:batch,cancelled:false};
  articleBodyRecoveryActive = run;
  try {await persistArticleBodyRecovery(batch);}
  catch (error) {articleBodyRecoveryActive = null; throw error;}
  run.promise = holdArticleBodyRecoveryLifetime(run).then(function () {
    return runArticleBodyRecovery(run,preview.targets);
  }).catch(async function () {
    batch.status = run.cancelled && !run.interruption ? "cancelled" : "interrupted";
    batch.stop_reason = run.interruption || (run.cancelled ? "operator_cancelled" : "interrupted");
    batch.items.forEach(function (item) {
      if (item.state === "running") {item.state = "failed"; item.reason = "interrupted";}
      else if (item.state === "queued") {item.state = "cancelled"; item.reason = "interrupted";}
    });
    await persistArticleBodyRecovery(batch).catch(function () {});
  }).finally(function () {
    if (run.closeLifetime) run.closeLifetime();
    if (articleBodyRecoveryActive === run) articleBodyRecoveryActive = null;
  });
  return {status:"ok",batch:batch};
}

async function runArticleBodyRecovery(run, targets) {
  var batch = run.batch, stopped = false;
  for (var index = 0; index < targets.length && !run.cancelled && !stopped; index++) {
    await waitForArticleBodyRecoveryGap(run);
    if (run.cancelled) break;
    var item = batch.items[index], target = targets[index];
    var result = await enqueueSaSyncJob({key:batch.batch_id + ":" + target.article_id,
      displayName:"Article body repair",operation:"alpha_picks_body_repair",mode:"manual",
      eligible:function () {return !run.cancelled;}}, async function (diagnostics) {
      if (run.cancelled) return run.interruption
        ? {status:"error",failure_phase:"extraction",reason:run.interruption,reason_code:"interrupted"}
        : {status:"cancelled",reason:"operator_cancelled"};
      item.state = "running";
      item.attempt_count = 1;
      item.phase = "opening";
      await persistArticleBodyRecovery(batch);
      return captureArticleBodyRecovery(target,run,diagnostics);
    });
    var stop = result.acquisition_stop;
    var pacingUntil = result.retry_after || stop && stop.retry_after;
    if (result.status === "deferred" && result.reason === "site_pacing"
        && !result.acquisition_uncertain && (!result.acquisition || result.acquisition.navigation_attempt_count === 0)
        && Date.parse(pacingUntil) > Date.now() && !run.cancelled) {
      // Admission was denied before any page request. Wait for the same item;
      // never retry a page that was opened or had an uncertain outcome.
      run.waitUntil = pacingUntil;
      item.state = "queued"; item.attempt_count = 0; delete item.phase;
      await persistArticleBodyRecovery(batch);
      index--;
      continue;
    }
    if (result.status === "ok" && result.body_saved === true) {
      item.state = "saved"; item.reason = null;
      item.references = result.body_references || null;
    } else if (result.status === "cancelled" || result.reason === "operator_cancelled") {
      item.state = "cancelled"; item.reason = run.interruption || "operator_cancelled";
    } else if (result.status === "skipped") {
      item.state = "skipped"; item.reason = bodyRecoveryReason(result.reason,"unknown_failure");
    } else if (result.status === "deferred") {
      item.state = "deferred"; item.reason = bodyRecoveryReason(result.reason,"collector_unavailable");
    } else {
      item.state = "failed";
      item.reason = bodyRecoveryReason(stop && stop.error_code || result.reason || result.reason_code,"unknown_failure");
    }
    stopped = !!stop || !!result.acquisition_uncertain || result.status === "deferred";
    if (result.acquisition_uncertain) batch.stop_reason = "cleanup_unconfirmed";
    else if (stopped) batch.stop_reason = bodyRecoveryReason(stop && stop.error_code || result.reason,"collector_unavailable");
    delete item.phase;
    await persistArticleBodyRecovery(batch);
  }
  batch.items.forEach(function (item) {
    if (item.state === "queued") {
      item.state = "cancelled";
      item.reason = run.interruption || (run.cancelled ? "operator_cancelled" : batch.stop_reason || "interrupted");
    }
  });
  batch.status = run.interruption ? "interrupted" : run.cancelled ? "cancelled" : stopped ? "stopped"
    : batch.items.some(function (item) {return item.state === "failed";}) ? "partial" : "complete";
  batch.finished_at = new Date().toISOString();
  await persistArticleBodyRecovery(batch);
}

async function waitForArticleBodyRecoveryGap(run) {
  while (!run.cancelled) {
    var state = await companyCollectorControl("status");
    var deadline = Math.max(state && Date.parse(state.next_navigation_at) || 0, Date.parse(run.waitUntil) || 0);
    if (!state || state.status !== "ok" || !state.is_owner || state.paused_reason || state.rate_limited
        || state.capability_pauses && state.capability_pauses.alpha_picks
        || !Number.isFinite(deadline) || deadline <= Date.now()) break;
    run.batch.next_page_at = new Date(deadline).toISOString();
    await persistArticleBodyRecovery(run.batch);
    // Keep this explicit batch responsive to shared state while its port lives.
    // Waiting holds neither a queue slot nor the native acquisition reservation.
    await new Promise(function (resolve) {
      var timer;
      run.wake = function () {clearTimeout(timer); run.wake = null; resolve();};
      timer = setTimeout(run.wake,Math.min(20000,Math.max(0,deadline - Date.now())));
      if (run.cancelled) run.wake();
    });
  }
  delete run.batch.next_page_at;
  delete run.waitUntil;
}

async function captureArticleBodyRecovery(target, run, diagnostics) {
  var tabId = null, guard = null, phase = "extraction";
  var item = run.batch.items.find(function (value) {return value.article_id === target.article_id;});
  function cancelled() {return run.cancelled;}
  function cancelledResult() {
    return run.interruption
      ? failure(run.interruption === "batch_timeout" ? "interrupted" : run.interruption)
      : {status:"cancelled"};
  }
  async function progress(value) {
    if (item) item.phase = value;
    await persistArticleBodyRecovery(run.batch);
  }
  async function checkpoint() {
    requireAcquisitionTask();
    if (await acquisitionPaused("alpha_picks")) {
      throw new SAAcquisition.Stop({status:"deferred",reason:"site_paused"});
    }
    return !cancelled();
  }
  function failure(reason) {
    var code = bodyRecoveryReason(reason,phase === "persistence" ? "detail_save_failed" : "unknown_failure");
    var rejectedBody = code === "parser_empty" || code.startsWith("sa_article_body_");
    var stage = code === "native_host_unavailable" ? "native_transport" : code === "interrupted" ? "extension_runtime"
      : phase === "persistence" && !rejectedBody ? "local_persistence" : "content_parse";
    recordExtensionFailure(diagnostics,{stage:stage,
      reason_code:code,target_kind:"article_detail",target_ref:target.article_id,retryable:true,attempt_count:1});
    return {status:"error",failure_phase:phase,reason:code,
      reason_code:code === "article_context_changed" ? "navigation_timeout" : code};
  }
  try {
    if (!await checkpoint()) return cancelledResult();
    var check = await sendNativeMessage2({action:"check_article_body_recovery_target",
      article_id:target.article_id,body_sha256:target.body_sha256});
    if (cancelled()) return cancelledResult();
    if (check.status === "skipped" && ["already_present","out_of_scope","source_changed"].includes(check.reason)) {
      return {status:"skipped",reason:check.reason};
    }
    if (check.status !== "ok") return failure(check.error_code || "native_host_unavailable");
    var verified = bodyRecoveryTarget(Object.assign({body_sha256:target.body_sha256},check.target));
    if (!verified || verified.article_id !== target.article_id) return failure("manifest_invalid");
    if (verified.body_sha256 !== target.body_sha256) return {status:"skipped",reason:"source_changed"};
    if (!await checkpoint()) return cancelledResult();
    var tab = await managedSaTabs.create({url:verified.url,active:true});
    tabId = tab.id;
    await registerCollectorTab(tabId,"alpha_picks_body_repair");
    await progress("loading");
    if (cancelled()) return cancelledResult();
    await waitForTabLoad(tabId,30000,expectedPathFromUrl(verified.url));
    if (!await checkpoint()) return cancelledResult();
    var ready = await waitForArticleReady(tabId);
    if (!ready.ok) {
      if (await observeSaRestriction(ready.reason_code)) throw new SAAcquisition.Stop(saAcquisitionTask.stop);
      return failure(ready.reason_code || "dom_not_ready");
    }
    if (cancelled()) return cancelledResult();
    guard = await beginArticleCapture(tabId,verified);
    await settleArticleBeforeScroll(tabId);
    if (!await checkpoint()) return cancelledResult();
    await inspectSaAccess(tabId);
    await guard.assert();
    await progress("extracting");
    var detail = await injectDetailScraper(tabId);
    await guard.assert(detail && !detail.error ? detail.url || null : undefined);
    if (cancelled()) return cancelledResult();
    if (!detail || detail.error || !detail.body_markdown || !detail.body_markdown.trim()) return failure("parser_empty");
    var report = formatDetailReport(detail);
    await guard.close();
    guard = null;
    phase = "persistence";
    if (!await checkpoint()) return cancelledResult();
    await progress("saving");
    var saved = await sendNativeMessage2({action:"save_article_body_recovery",article_id:target.article_id,
      expected_body_sha256:target.body_sha256,body_markdown:report,
      body_capture:detail.body_capture || null,
      detail_ticker:detail.detail_ticker || null,detail_ticker_observed_at:detail.detail_ticker_observed_at || null});
    if (saved.status === "skipped" && ["already_present","out_of_scope","source_changed"].includes(saved.reason)) {
      return {status:"skipped",reason:saved.reason};
    }
    if (saved.body_saved === false && (saved.body_quality || saved.status === "ok")) {
      phase = "extraction";
      return failure(bodyRecoveryReason(saved.body_quality && saved.body_quality.reason_code, "parser_empty"));
    }
    if (saved.status !== "ok" || saved.body_saved !== true) return failure("detail_save_failed");
    return {status:"ok",body_saved:true,body_references:saved.body_references || null};
  } catch (error) {
    if (isAcquisitionStop(error)) throw error;
    return failure(error.code || (phase === "extraction" ? "unknown_failure" : "detail_save_failed"));
  } finally {
    if (guard) await guard.close();
    if (tabId !== null) {
      await safeRemoveTab(tabId);
      if (!saAcquisitionTask.ownedTabs.has(tabId)) await unregisterCollectorTab(tabId);
    }
  }
}

async function handleAcquisitionControl(msg) {
  if (msg.action === "enable_sa_updates_here") return activateSaUpdates(msg);
  if (msg.action === "get_company_refresh") {
    var pendingState = await saAcquisition.reconcilePending();
    var status = await companyFinancialRefresh.status();
    var active = saAcquisition.running || saSyncJobInFlight;
    var pending = pendingState.pending;
    var recovery = !active && !!(pending || status.collector && status.collector.is_owner && status.collector.active);
    await syncAcquisitionBadge(status.collector, false).catch(function () {});
    return Object.assign({},status,{acquisition_pending:!!pending,acquisition_runtime_active:active,
      acquisition_recovery_required:recovery,acquisition_pending_since:pending && pending.started_at || null,
      queue:saAcquisitionQueue.status()});
  }
  if (msg.action === "preview_company_refresh") return companyFinancialRefresh.preview(msg.config);
  if (msg.action === "save_company_refresh") return companyFinancialRefresh.configure(Object.assign({},msg.config,{enabled:false}));
  if (msg.action === "cancel_company_refresh") return companyFinancialRefresh.cancelQueue();
  if (msg.action === "run_company_refresh") {
    if (msg.force === true && msg.confirm_force !== true) return {status:"error",error_code:"sa_acquisition_confirmation_required"};
    return companyFinancialRefresh.run({force:msg.force === true});
  }
  var operation = msg.action === "recover_sa_acquisition" ? "recover" : "resume";
  if (operation === "recover" && (saSyncJobInFlight || saAcquisition.running || articleBodyRecoveryActive)) {
    return {status:"error",error_code:"sa_company_collector_busy"};
  }
  if (operation === "recover") return saAcquisitionQueue.enqueue({key:"operator-acquisition-recovery",
    priority:"routine",run:function () {return applyAcquisitionControl(msg,operation);}});
  return applyAcquisitionControl(msg,operation);
}

async function applyAcquisitionControl(msg, operation) {
  if (operation === "recover" && (saSyncJobInFlight || saAcquisition.running || articleBodyRecoveryActive)) {
    return {status:"error",error_code:"sa_company_collector_busy"};
  }
  var pending = (await chrome.storage.local.get("saAcquisitionPending")).saAcquisitionPending;
  var state = await companyCollectorControl(operation,{expected_generation:msg.expected_generation,
    confirm_stopped:msg.confirm_stopped === true,confirm_handled:msg.confirm_handled === true,capability:msg.capability});
  if (state.status !== "ok") return state;
  if (operation === "recover") {
    var current = (await chrome.storage.local.get("saAcquisitionPending")).saAcquisitionPending;
    if (pending && current && current.request_id === pending.request_id
        && current.ledger_id === pending.ledger_id && current.generation === pending.generation) {
      await chrome.storage.local.set({saAcquisitionPending:null});
    }
  }
  else {
    await chrome.storage.local.set({saAcquisitionRestriction:null});
    await companyFinancialRefresh.resume();
  }
  await syncAcquisitionBadge(state);
  await syncAllAutoSyncAlarms();
  return companyFinancialRefresh.status();
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (["preview_article_body_recovery", "start_article_body_recovery",
      "get_article_body_recovery_state", "cancel_article_body_recovery"].includes(msg.action)) {
    if (!sender || sender.id !== chrome.runtime.id || sender.url !== chrome.runtime.getURL("popup.html")) {
      sendResponse({status:"error",error_code:"extension_request_rejected"});
      return false;
    }
    handleArticleBodyRecovery(msg).then(sendResponse).catch(function () {
      sendResponse({status:"error",error_code:"body_recovery_unavailable"});
    });
    return true;
  }
  if (msg.action === "reconciliation_native_request") {
    forwardReconciliationNative(msg.payload, sender).then(sendResponse).catch(function () {
      sendResponse({status:"error", error_code:"native_host_unavailable"});
    });
    return true;
  }
  if (["get_company_refresh","preview_company_refresh","save_company_refresh","enable_sa_updates_here",
      "run_company_refresh","cancel_company_refresh","recover_sa_acquisition","resume_sa_acquisition"].includes(msg.action)) {
    if (!sender || sender.id !== chrome.runtime.id || sender.url !== chrome.runtime.getURL("popup.html")) {
      sendResponse({status:"error",error_code:"extension_request_rejected"});
      return false;
    }
    handleAcquisitionControl(msg).then(sendResponse).catch(function (error) {
      sendResponse({status:"error", error_code:error.message === "sa_company_schedule_invalid"
        ? error.message : "sa_company_schedule_unavailable"});
    });
    return true;
  }
  if (msg.action === "capture_company_data") {
    chrome.tabs.query({ active: true, currentWindow: true }).then(function (tabs) {
      var target = tabs.length === 1 ? { id: tabs[0].id, url: tabs[0].url } : null;
      return enqueueSaSyncJob({ displayName: "Company research", operation: "company_financial_capture", mode: "current_tab" },
        function (diagnostics) { return captureCompanyData(target, diagnostics); });
    }).then(sendResponse).catch(function () {
      sendResponse({ status: "error", error_code: "sa_company_capture_failed" });
    });
    return true;
  }
  if (msg.action === "refresh") {
    var mode = msg.mode || "quick";
    enqueueSaSyncJob({
      displayName: "Alpha Picks " + mode,
      operation: "alpha_picks_sync",
      mode: mode,
    }, function (diagnostics) {
      return doRefresh(mode, { trigger: "manual", diagnostics: diagnostics });
    }).then(sendResponse);
    return true;
  }
  if (msg.action === "manual_fetch") {
    enqueueSaSyncJob({
      displayName: "Manual fetch",
      operation: "alpha_picks_manual_fetch",
      mode: "manual",
    }, function (diagnostics) {
      return doManualFetch(msg.items || [], diagnostics);
    }).then(sendResponse);
    return true;
  }
  if (msg.action === "refresh_market_news") {
    var mnMode = msg.mode || "quick";
    enqueueSaSyncJob({
      displayName: "Market News " + mnMode,
      operation: "market_news_sync",
      mode: mnMode,
    }, function (diagnostics) {
      return doMarketNewsRefresh(mnMode, {
        trigger: "manual",
        diagnostics: diagnostics,
      });
    }).then(sendResponse);
    return true;
  }
  if (msg.action === "get_extension_action_limits") {
    getExtensionActionLimits().then(sendResponse);
    return true;
  }
  if (msg.action === "market_news_recovery_preview") {
    sendMarketNewsRecoveryNative("market_news_recovery_preview", {
      kind: msg.kind,
      source_run_ids: Array.isArray(msg.source_run_ids) ? msg.source_run_ids : undefined,
    }).then(sendResponse);
    return true;
  }
  if (msg.action === "market_news_recovery_state") {
    sendMarketNewsRecoveryNative("market_news_recovery_state", {
      run_id: Number.isInteger(msg.run_id) ? msg.run_id : undefined,
    }).then(sendResponse);
    return true;
  }
  if (msg.action === "market_news_recovery_start") {
    enqueueMarketNewsRecovery({
      kind: msg.kind,
      manifest: msg.manifest,
      manifest_hash: msg.manifest_hash,
    }).then(sendResponse);
    return true;
  }
  if (msg.action === "market_news_recovery_resume") {
    enqueueMarketNewsRecovery({
      run_id: msg.run_id,
      manifest_hash: msg.manifest_hash,
    }).then(sendResponse);
    return true;
  }
  if (msg.action === "market_news_recovery_cancel") {
    sendMarketNewsRecoveryNative("market_news_recovery_cancel", {
      run_id: msg.run_id,
      manifest_hash: msg.manifest_hash,
    }).then(sendResponse);
    return true;
  }
  if (msg.action === "set_alpha_picks_auto_sync") {
    setAlphaPicksAutoSyncEnabled(!!msg.enabled, msg.interval_minutes).then(sendResponse);
    return true;
  }
  if (msg.action === "set_market_news_auto_sync") {
    setMarketNewsAutoSyncEnabled(!!msg.enabled, msg.interval_minutes).then(sendResponse);
    return true;
  }
  if (msg.action === "ensure_auto_sync_alarms") {
    extensionTelemetryController.flush("popup_open").then(function () {
      return ensureAutoSyncAlarms();
    }).then(sendResponse);
    return true;
  }
});

async function captureCompanyData(target, diagnostics, expectedScope) {
  var result;
  var failurePhase = "extraction";
  try {
    var selectedUrl;
    try { selectedUrl = new URL(target && target.url); } catch (_) { throw new Error("sa_company_page_unsupported"); }
    var pagePath = /^\/symbol\/[A-Z][A-Z0-9.-]{0,19}\/(income-statement|balance-sheet|cash-flow-statement|valuation\/metrics|peers\/comparison|earnings\/(?:estimates|revisions))\/?$/.exec(selectedUrl.pathname);
    if (!target || !Number.isInteger(target.id) || selectedUrl.origin !== "https://seekingalpha.com"
        || selectedUrl.username || selectedUrl.password || !pagePath) {
      throw new Error("sa_company_page_unsupported");
    }
    requireAcquisitionTask();
    var tab = await chrome.tabs.get(target.id);
    if (tab.url !== target.url) throw new Error("sa_company_page_changed");
    var dataset = { "valuation/metrics": "valuation", "peers/comparison": "peers", "earnings/estimates": "estimates",
      "earnings/revisions": "revisions" }[pagePath[1]] || "financials";
    var researchPage = dataset !== "financials";
    var admission = await sendNativeMessage2({ action: "get_company_capture_admission", dataset: dataset });
    if (!admission || admission.status !== "ok" || admission.dataset !== dataset) {
      throw new Error(admission && admission.error_code || "sa_company_admission_unavailable");
    }
    if (!expectedScope) await saAcquisitionTask.navigate({kind:"current_tab",destinationClass:"company"},async function () {});
    await inspectSaAccess(target.id);
    tab = await chrome.tabs.get(target.id);
    if (tab.url !== target.url) throw new Error("sa_company_page_changed");
    var extracted = researchPage
      ? await chrome.scripting.executeScript({ target: { tabId: target.id }, files: ["scrape_company_research.js"] })
      : await chrome.scripting.executeScript({ target: { tabId: target.id }, files: ["scrape_company.js"] });
    if (extracted.length !== 1 || !extracted[0].result) throw new Error("sa_company_capture_failed");
    var value = extracted[0].result;
    if (value.status !== "ok") throw new Error(value.error_code || "sa_company_capture_failed");
    if (expectedScope && (researchPage || !value.capture || value.capture.ticker !== expectedScope.ticker
        || !value.capture.controls || typeof value.capture.controls.period !== "string"
        || value.capture.controls.period.toLowerCase() !== expectedScope.view
        || value.capture.controls.currency !== "United States Dollar (USD)"
        || pagePath[1].replaceAll("-", "_") !== expectedScope.statement)) {
      throw new Error("sa_company_scope_mismatch");
    }
    if (researchPage && (!value.capture || value.capture.dataset !== dataset)) throw new Error("sa_company_identity_mismatch");
    tab = await chrome.tabs.get(target.id);
    if (tab.url !== target.url) throw new Error("sa_company_page_changed");
    failurePhase = "persistence";
    result = await sendNativeMessage2({ action: "save_company_data", capture: value.capture });
    if (!result || result.status !== "ok") throw new Error(result && result.error_code || "sa_company_store_unavailable");
    if (!/^[a-f0-9]{64}$/.test(result.observation_id || "") || result.ticker !== value.capture.ticker
        || !result.coverage || result.coverage.scope !== (researchPage ? "recognized_page_tables" : "displayed_table")
        || (researchPage && result.dataset !== value.capture.dataset) || typeof result.deduplicated !== "boolean") {
      throw new Error("sa_company_receipt_invalid");
    }
    if (expectedScope && (result.statement !== expectedScope.statement || result.view !== expectedScope.view || result.currency !== "USD")) {
      throw new Error("sa_company_receipt_invalid");
    }
    if (!researchPage && !expectedScope) {
      try {
        if (await companyFinancialRefresh.noteSuccess({ticker:result.ticker, statement:result.statement, view:result.view}, result)) {
          await companyFinancialRefresh.syncAlarm();
        }
      } catch (_) {
        result.schedule_warning = "sa_company_schedule_unavailable";
      }
    }
  } catch (error) {
    if (isAcquisitionStop(error)) throw error;
    var code = error && /^(sa_company_|data_source_)[a-z_]+$/.test(error.message)
      ? error.message : "sa_company_capture_failed";
    var reason = /layout|structure|identity|units|value_unrecognized/.test(code)
      ? "company_layout_unrecognized" : "company_capture_rejected";
    result = { status: "error", error_code: code, failure_phase: failurePhase, reason_code: reason };
    recordExtensionFailure(diagnostics, { stage: failurePhase === "extraction" ? "content_parse" : "local_persistence",
      reason_code: reason, target_kind: "phase", retryable: false, attempt_count: 1 });
    await observeSaRestriction(code);
  }
  await chrome.storage.local.set({ lastCompanyCapture: Object.assign({ finished_at: new Date().toISOString() }, result) });
  return result;
}

async function refreshCompanyFinancialScope(scope, diagnostics, admitted, observeFailure, confirmCleanup) {
  var tabId = null;
  try {
    if (!await admitted()) return {status:"cancelled"};
    var admission = await sendNativeMessage2({action:"get_company_capture_admission", dataset:"financials"});
    if (!admission || admission.status !== "ok" || admission.dataset !== "financials") {
      if (admission && admission.error_code === "native_host_unavailable") {
        throw new Error("sa_company_native_host_unavailable");
      }
      throw new Error(admission && admission.error_code || "sa_company_admission_unavailable");
    }
    if (!await admitted()) return {status:"cancelled"};
    var pathname = "/symbol/" + scope.ticker + "/" + scope.statement.replaceAll("_", "-");
    var url = "https://seekingalpha.com" + pathname;
    // Only collector-owned tabs are navigated or closed. No focus activation is requested.
    var tab = await managedSaTabs.create({url:url, active:false});
    tabId = tab.id;
    await registerCollectorTab(tabId, "company_financials");
    await waitForTabLoad(tabId, 60000);
    if (!await admitted()) return {status:"cancelled"};
    var prepared = await chrome.scripting.executeScript({target:{tabId:tabId},
      func:prepareCompanyFinancialView, args:[scope.view, pathname]});
    if (!prepared[0] || prepared[0].result.status !== "ok") {
      throw new Error(prepared[0] && prepared[0].result.error_code || "sa_company_dom_not_ready");
    }
    var target = await chrome.tabs.get(tabId);
    if (new URL(target.url).origin !== "https://seekingalpha.com" || new URL(target.url).pathname !== pathname) {
      throw new Error("sa_company_page_changed");
    }
    if (!await admitted()) return {status:"cancelled"};
    var result = await captureCompanyData({id:tabId, url:target.url}, diagnostics, scope);
    if (result.status === "error" && observeFailure) await observeFailure(result.error_code);
    return result;
  } catch (error) {
    if (isAcquisitionStop(error)) throw error;
    var code = /^(sa_company_|data_source_)[a-z_]+$/.test(error.message || "")
      ? error.message : "sa_company_dom_not_ready";
    recordExtensionFailure(diagnostics, {stage:"content_parse",reason_code:"company_capture_rejected",
      target_kind:"phase",retryable:false,attempt_count:1});
    // Persist restrictions before tab cleanup/pacing: reload must not erase them.
    if (observeFailure) await observeFailure(code);
    return {status:"error",error_code:code,reason_code:"company_capture_rejected",failure_phase:"extraction"};
  } finally {
    if (tabId !== null) {
      var removed = await safeRemoveTab(tabId);
      if (confirmCleanup && !removed) {
        var closed = false;
        try { await chrome.tabs.get(tabId); }
        catch (error) { closed = /No tab with id|Invalid tab ID/i.test(error.message || ""); }
        if (!closed) throw new Error("sa_company_collector_cleanup_uncertain");
      }
      await unregisterCollectorTab(tabId);
      // Pace successive manual targets too; timers do not imply source freshness.
    }
  }
}

async function prepareCompanyFinancialView(view, pathname) {
  function visible(node) {
    if (!node) return false;
    for (var item = node; item; item = item.parentElement) {
      if (item.hidden || item.getAttribute("aria-hidden") === "true" || getComputedStyle(item).display === "none"
          || getComputedStyle(item).visibility === "hidden") return false;
    }
    return true;
  }
  function label(node) { return (node.innerText || node.textContent || "").trim(); }
  function control(name) {
    var nodes = Array.from(document.querySelectorAll('main [role="combobox"][aria-labelledby="financials-filter-' + name + '"]')).filter(visible);
    return nodes.length === 1 ? nodes[0] : null;
  }
  var wanted = {period:view === "annual" ? "Annual" : "Quarterly", view:"Absolute", currency:"United States Dollar (USD)"};
  var transition = null;
  var stable = null;
  var steady = 0;
  var start = Date.now();
  while (Date.now() - start < 45000) {
    if (/verify you are human|access denied|access to this page has been denied|just a moment/i.test(document.title)
        || Array.from(document.querySelectorAll('iframe[title="Human verification challenge"]')).some(visible)) {
      return {status:"error",error_code:"sa_company_human_verification_required"};
    }
    var rateLimitMessage = /too\s+many\s+requests|rate\s+limit\s+exceeded/i;
    if (rateLimitMessage.test(document.title)
        || Array.from(document.querySelectorAll('h1')).some(function (node) {
          return visible(node) && rateLimitMessage.test(label(node));
        })) {
      return {status:"error",error_code:"sa_company_rate_limited"};
    }
    if (/\/login|\/sign_in/.test(location.pathname)) return {status:"error",error_code:"sa_company_login_required"};
    if (location.origin !== "https://seekingalpha.com" || location.pathname !== pathname) {
      return {status:"error",error_code:"sa_company_page_changed"};
    }
    var tables = Array.from(document.querySelectorAll('main table[data-test-id="table"]')).filter(visible);
    var table = tables.length === 1 ? tables[0] : null;
    var loaded = table && table.querySelector("tbody > tr") && table.querySelector("thead")
      && !table.closest('[aria-busy="true"]') && !table.querySelector('[aria-busy="true"], [data-test-id="skeleton"]');
    var ready = loaded;
    if (!transition && loaded) {
      for (var name of ["period", "view", "currency"]) {
        var box = control(name);
        if (!box) { ready = false; break; }
        if (label(box) !== wanted[name]) {
          transition = {name:name, headers:label(table.querySelector("thead")), body:label(table.querySelector("tbody"))};
          box.click();
          ready = false;
          break;
        }
      }
    }
    if (transition) {
      var selected = control(transition.name);
      if (!selected || label(selected) !== wanted[transition.name]) {
        var options = Array.from(document.querySelectorAll('[role="listbox"] [role="option"]'))
          .filter(function (node) { return visible(node) && label(node) === wanted[transition.name]; });
        if (options.length === 1) options[0].click();
        ready = false;
      } else {
        // A changed control/units label alone is not evidence that numerical cells loaded.
        ready = loaded && label(table.querySelector("tbody")) !== transition.body
          && (transition.name !== "period" || label(table.querySelector("thead")) !== transition.headers);
      }
    }
    if (ready) {
      var signature = table.textContent;
      steady = signature === stable ? steady + 1 : 0;
      stable = signature;
      if (steady >= 2) {
        if (!transition) return {status:"ok"};
        transition = null;
        stable = null;
        steady = 0;
      }
    } else { stable = null; steady = 0; }
    await new Promise(function (resolve) { setTimeout(resolve, 1000); });
  }
  return {status:"error",error_code:"sa_company_dom_not_ready"};
}

chrome.runtime.onInstalled.addListener(function () {
  cleanupCollectorTabs({ maxAgeMs: COLLECTOR_TAB_STALE_MS });
  refreshAcquisitionStatus().then(syncAllAutoSyncAlarms);
});

chrome.runtime.onStartup.addListener(function () {
  cleanupCollectorTabs({ maxAgeMs: COLLECTOR_TAB_STALE_MS });
  refreshAcquisitionStatus().then(syncAllAutoSyncAlarms);
  extensionTelemetryController.flush("startup");
});

chrome.alarms.onAlarm.addListener(function (alarm) {
  if (!alarm) return;
  if (alarm.name === SA_ACQUISITION_COOLDOWN_ALARM) {
    refreshAcquisitionStatus().then(syncAllAutoSyncAlarms);
    return;
  }
  if (alarm.name === SACompanyRefresh.alarm) {
    companyFinancialRefresh.run(false).catch(function () {});
    return;
  }
  if (!saSyncJobInFlight && !marketNewsRefreshInFlight) {
    cleanupCollectorTabs({ maxAgeMs: COLLECTOR_TAB_STALE_MS });
  }
  if (alarm.name === ALPHA_PICKS_AUTO_SYNC_ALARM) {
    enqueueAutoSaSyncJob("alphaPicks", {
      displayName: "Alpha Picks quick auto-sync",
      operation: "alpha_picks_sync",
      mode: "quick",
    }, function (diagnostics) {
      return doRefresh("quick", { trigger: "alarm", diagnostics: diagnostics });
    });
    return;
  }
  if (alarm.name === MARKET_NEWS_AUTO_SYNC_ALARM) {
    enqueueAutoSaSyncJob("marketNews", {
      displayName: "Market News quick auto-sync",
      operation: "market_news_sync",
      mode: "quick",
    }, async function (diagnostics) {
      if (!(await shouldRunMarketNewsAutoSync())) {
        return { status: "skipped", reason: "not_due" };
      }
      var result = await doMarketNewsRefresh("quick", {
        trigger: "alarm",
        diagnostics: diagnostics,
      });
      if (shouldMarkMarketNewsAutoSyncRun(result)) {
        await markMarketNewsAutoSyncStarted();
      }
      return result;
    });
  }
});

function enqueueSaSyncJob(opts, jobFn) {
  // The server derives the durable job identity from operation + mode.
  if (typeof opts === "string") {
    opts = { displayName: opts };
  }
  opts = opts || {};
  var displayName = opts.displayName || "unnamed";
  var operation = opts.operation || null;
  var mode = opts.mode || null;

  return saAcquisitionQueue.enqueue({key:opts.key || crypto.randomUUID(),priority:
    operation === "company_financial_capture" || operation === "alpha_picks_body_repair" ? "background" : "routine",
    eligible:opts.eligible,run:async function (timing) {
    await extensionTelemetryController.flush("next_job");
    if (saSyncJobInFlight) {
      sendProgress("Queued: " + displayName);
    }
    saSyncJobInFlight = true;
    var startedAt = new Date().toISOString();
    await chrome.storage.local.set({saAcquisitionRuntime:{running:true,operation:operation,started_at:startedAt}}).catch(function () {});
    var diagnostics = SAExtensionDiagnostics.createCollector();
    var capturedResult = null;
    var lifetime = {cancelled:false,onInterrupted:function (reason) {
      if (!saAcquisitionTask) return;
      saAcquisitionTask.interrupt({status:"error",reason:"collector_unavailable",error_code:reason});
      Array.from(saAcquisitionTask.ownedTabs).forEach(function (tabId) {safeRemoveTab(tabId).catch(function () {});});
    }};
    try {
      if (!operation) return await jobFn(diagnostics);
      var borrowedLifetime = operation === "alpha_picks_body_repair" && articleBodyRecoveryActive
        && !articleBodyRecoveryActive.cancelled && articleBodyRecoveryActive.closeLifetime;
      if (!borrowedLifetime && !await holdSaAcquisitionLifetime(lifetime)) {
        capturedResult = attachExtensionRunProtocol(operation,mode,{status:"deferred",
          reason:"collector_unavailable",error_code:lifetime.interruption || "native_host_unavailable"});
        return capturedResult;
      }
      capturedResult = await saAcquisition.runTask(Object.assign({},opts.acquisition || {},{
        operation:operation,mode:mode,trigger:opts.trigger || "manual",intent_revision:opts.intent_revision || 0,
        build:chrome.runtime.getManifest ? chrome.runtime.getManifest().version : "unknown",queue_wait_ms:timing.queue_wait_ms,
      }),async function (task) {
        saAcquisitionTask = task;
        if (lifetime.cancelled) task.interrupt({status:"error",reason:"collector_unavailable",
          error_code:lifetime.interruption || "native_host_unavailable"});
        var value;
        try { requireAcquisitionTask(); value = await jobFn(diagnostics); }
        catch (error) {
          if (isAcquisitionStop(error)) value = Object.assign({},error.detail);
          else {
            recordExtensionFailure(diagnostics,{stage:"extension_runtime",reason_code:"unknown_failure",
              target_kind:"phase",retryable:true,attempt_count:1});
            value = {status:"error",error_code:"sa_acquisition_failed"};
          }
        }
        if (task.stop) value = Object.assign({},value,{acquisition_stop:task.stop});
        return attachExtensionRunProtocol(operation,mode,value);
      });
      if (!capturedResult.extension_run) capturedResult = attachExtensionRunProtocol(operation,mode,capturedResult);
      return capturedResult;
    } catch (err) {
      recordExtensionFailure(diagnostics, {
        stage: "extension_runtime",
        reason_code: "unknown_failure",
        target_kind: "phase",
        retryable: true,
        attempt_count: 1,
      });
      if (!capturedResult && operation) {
        capturedResult = {
          extension_run: buildFailedExtensionProtocolResult(operation, mode),
        };
      }
      throw err;
    } finally {
      saAcquisitionTask = null;
      saSyncJobInFlight = false;
      try {
        var frozenDiagnostics = diagnostics.freeze();
        var event = {
          started_at: startedAt,
          finished_at: new Date().toISOString(),
          result: capturedResult && capturedResult.extension_run,
          extension_diagnostics: frozenDiagnostics,
        };
        if (capturedResult && capturedResult.acquisition) event.acquisition = capturedResult.acquisition;
        await extensionTelemetryController.submit(event);
      } catch (_) {
        // Recording must never break the actual sync flow.
      } finally {
        if (lifetime.closeLifetime) lifetime.closeLifetime();
        await chrome.storage.local.set({saAcquisitionRuntime:{running:false,finished_at:new Date().toISOString()}}).catch(function () {});
      }
    }
  }});
}

async function readAutoSyncIntent(jobKey) {
  if (jobKey !== "alphaPicks" && jobKey !== "marketNews") throw new Error("Unknown automatic job");
  var enabledKey = jobKey + "AutoSyncEnabled";
  var revisionKey = jobKey + "AutoSyncRevision";
  var data = await chrome.storage.local.get([enabledKey, revisionKey]);
  var revision = data[revisionKey] == null ? 0 : data[revisionKey];
  if (!Number.isSafeInteger(revision) || revision < 0) throw new Error("Invalid automatic intent");
  return { enabled: data[enabledKey] === true, revision: revision };
}

async function enqueueAutoSaSyncJob(jobKey, jobOpts, jobFn) {
  var submitted;
  try { submitted = await readAutoSyncIntent(jobKey); }
  catch (_) { return { status: "skipped", reason: "operator_cancelled" }; }
  if (!submitted.enabled) return { status: "skipped", reason: "operator_cancelled" };
  var pendingKey = jobKey + ":" + submitted.revision;
  if (saAutoJobPending[pendingKey]) {
    return Promise.resolve({ status: "skipped", reason: "already_pending" });
  }
  saAutoJobPending[pendingKey] = true;
  try {
    var eligible = async function () {
      var current;
      try { current = await readAutoSyncIntent(jobKey); }
      catch (_) { return false; }
      return current.enabled && current.revision === submitted.revision
        && (jobKey !== "marketNews" || await shouldRunMarketNewsAutoSync());
    };
    return await enqueueSaSyncJob(Object.assign({},jobOpts,{eligible:eligible,trigger:"alarm",intent_revision:submitted.revision}), async function (diagnostics) {
      return jobFn(diagnostics);
    });
  } finally {
    delete saAutoJobPending[pendingKey];
  }
}

async function getExtensionActionLimits() {
  var configured = await sendNativeMessage2({ action: "get_extension_action_limits" });
  var configuredLimits = configured && configured.status === "ok" && configured.limits
    ? configured.limits
    : {};

  function alphaLimits(mode) {
    var comments = COMMENT_SCROLL_PROFILES[mode];
    return {
      article_list_rounds: ALPHA_PICKS_ARTICLE_LIST_ROUNDS[mode],
      detail_enrichment_limit: RECONCILIATION_ENRICHMENT_LIMITS[mode],
      comment_scroll_rounds: comments.maxScrolls,
      comment_scroll_ms: comments.maxDurationMs,
      comment_stable_rounds: comments.staleRounds,
      configured_comment_recovery_batch: mode === "full"
        ? configuredLimits.alpha_picks_full_comment_recovery_batch
        : mode === "backfill"
          ? configuredLimits.alpha_picks_deep_comment_recovery_batch
          : 0,
    };
  }

  return {
    status: "ok",
    limits: {
      alpha_picks: {
        quick: alphaLimits("quick"),
        full: alphaLimits("full"),
        backfill: alphaLimits("backfill"),
      },
      market_news: {
        quick: {
          list_rounds: MARKET_NEWS_PROFILES.quick.listScrolls,
          detail_attempts: MARKET_NEWS_DETAIL_TOTAL_LIMITS.quick,
        },
        catchup: {
          list_rounds: MARKET_NEWS_PROFILES.catchup.listScrolls,
          current_detail_attempts: MARKET_NEWS_DETAIL_CURRENT_LIMITS.catchup,
          backlog_detail_attempts: MARKET_NEWS_DETAIL_BACKFILL_LIMITS.catchup,
          total_detail_attempts: MARKET_NEWS_DETAIL_TOTAL_LIMITS.catchup,
          window_hours: MARKET_NEWS_ROUTINE_CATCHUP_HOURS,
        },
      },
      recovery: {
        max_window_hours: MARKET_NEWS_INCIDENT_RECOVERY_MAX_HOURS,
        max_list_rounds: MARKET_NEWS_INCIDENT_MAX_LIST_SCROLL_ROUNDS,
        max_elapsed_ms: MARKET_NEWS_INCIDENT_MAX_LIST_ELAPSED_MS,
        stable_rounds: MARKET_NEWS_INCIDENT_STABLE_ROUNDS,
        detail_attempts_per_pass: MARKET_NEWS_REPAIR_DETAIL_ATTEMPTS_PER_PASS,
      },
    },
  };
}

function sendMarketNewsRecoveryNative(action, payload) {
  var message = { action: action };
  Object.keys(payload || {}).forEach(function (key) {
    if (payload[key] !== undefined) message[key] = payload[key];
  });
  return sendNativeMessage2(message);
}

async function enqueueMarketNewsRecovery(request) {
  var manifest = request && request.manifest;
  if (request && Number.isInteger(request.run_id)) {
    var saved = await sendMarketNewsRecoveryNative("market_news_recovery_state",{run_id:request.run_id});
    if (!saved || saved.manifest_hash !== request.manifest_hash) return {status:"error",error_code:"manifest_invalid"};
    manifest = saved.manifest;
  }
  var incident = manifest && manifest.kind === "incident_window";
  return enqueueSaSyncJob({operation:incident ? "market_news_incident_recovery" : "market_news_retry_recorded",
    mode:incident ? "incident" : "recorded",displayName:"Market news recovery"},async function () {
    marketNewsRefreshInFlight = true;
    try {
      return await executeMarketNewsRecovery(request || {});
    } catch (error) {
      if (isAcquisitionStop(error)) throw error;
      return {
        status: "error",
        error_code: "recovery_runtime_failed",
      };
    } finally {
      marketNewsRefreshInFlight = false;
    }
  });
}

function latestRecoveryAttempts(state) {
  var attempts = state && state.progress && Array.isArray(state.progress.attempts)
    ? state.progress.attempts
    : [];
  var byId = {};
  attempts.forEach(function (attempt) {
    if (!attempt || typeof attempt.news_id !== "string") return;
    var current = byId[attempt.news_id];
    if (!current || Number(attempt.attempt_count || 0) >= Number(current.attempt_count || 0)) {
      byId[attempt.news_id] = attempt;
    }
  });
  return byId;
}

function targetNeedsAttempt(target, latest) {
  if (!target || target.body_present === true) return false;
  return !latest[target.news_id];
}

async function executeMarketNewsRecovery(request) {
  var state;
  if (Number.isInteger(request.run_id)) {
    state = await sendMarketNewsRecoveryNative("market_news_recovery_state", {
      run_id: request.run_id,
    });
    if (
      !state || state.status === "error" ||
      state.manifest_hash !== request.manifest_hash
    ) {
      return { status: "error", error_code: "manifest_invalid" };
    }
  } else {
    state = await sendMarketNewsRecoveryNative("market_news_recovery_start", {
      manifest: request.manifest,
      manifest_hash: request.manifest_hash,
    });
  }
  if (!state || state.status === "error" || state.status !== "running") return state;

  var manifest = state.manifest;
  if (!manifest || !Array.isArray(manifest.targets)) {
    return { status: "error", error_code: "manifest_invalid" };
  }
  var latest = latestRecoveryAttempts(state);
  var pendingTargets = manifest.targets.filter(function (target) {
    return targetNeedsAttempt(target, latest);
  });
  var attemptTargets = pendingTargets.slice(0, MARKET_NEWS_REPAIR_DETAIL_ATTEMPTS_PER_PASS);
  var remainingBudget = MARKET_NEWS_REPAIR_DETAIL_ATTEMPTS_PER_PASS;
  var tabId = null;
  var discovery = null;

  try {
    if (attemptTargets.length > 0 || manifest.kind === "incident_window") {
      await cleanupCollectorTabs({ force: true });
      var initialUrl = attemptTargets.length > 0
        ? "https://seekingalpha.com" + attemptTargets[0].pathname
        : SA_MARKET_NEWS_URL;
      var tab = await managedSaTabs.create({ url: initialUrl, active: false });
      tabId = tab.id;
      await registerCollectorTab(tabId, "market_news_recovery");
    }

    for (var index = 0; index < attemptTargets.length; index++) {
      var target = attemptTargets[index];
      var previous = latest[target.news_id];
      var attemptCount = Number(previous && previous.attempt_count || 0) + 1;
      var outcome = await recoverMarketNewsTarget(tabId, target);
      var attemptId = "repair-" + state.run_id + "-" + attemptCount + "-" + index;
      state = await sendMarketNewsRecoveryNative("market_news_recovery_checkpoint", {
        run_id: state.run_id,
        manifest_hash: state.manifest_hash,
        news_id: target.news_id,
        attempt_id: attemptId,
        state: outcome.state,
        reason_code: outcome.reason_code,
        evidence_code: outcome.evidence_code || null,
        attempt_count: attemptCount,
      });
      if (!state || state.status === "error") return state;
      remainingBudget--;
    }

    if (manifest.kind === "incident_window") {
      discovery = await discoverMarketNewsIncident(tabId, manifest, remainingBudget);
    }

    if (pendingTargets.length > attemptTargets.length) {
      return await sendMarketNewsRecoveryNative("market_news_recovery_state", {
        run_id: state.run_id,
      });
    }
    return await sendMarketNewsRecoveryNative("market_news_recovery_finalize", {
      run_id: state.run_id,
      manifest_hash: state.manifest_hash,
      discovery: discovery,
    });
  } finally {
    if (tabId) {
      await safeRemoveTab(tabId);
      await unregisterCollectorTab(tabId);
    }
  }
}

async function recoverMarketNewsTarget(tabId, target) {
  var url = "https://seekingalpha.com" + target.pathname;
  try {
    await withTimeout(
      managedSaTabs.update(tabId, { url: url, active: false }),
      MARKET_NEWS_DETAIL_TAB_LOAD_TIMEOUT_MS,
      "market news recovery navigation timeout"
    );
    await waitForTabLoad(tabId, MARKET_NEWS_DETAIL_TAB_LOAD_TIMEOUT_MS, target.pathname);
    await installMarketNewsPageGuards(tabId);
    var fetched = await withTimeout(
      fetchMarketNewsDetailWithRetry(
        tabId,
        { news_id: target.news_id, url: url },
        getMarketNewsProfile("backfill")
      ),
      MARKET_NEWS_DETAIL_ITEM_TIMEOUT_MS,
      "market news recovery detail timeout"
    );
    if (fetched && fetched.ok) {
      return { state: "repaired", reason_code: "body_saved", evidence_code: null };
    }
    if (fetched && fetched.state === "unavailable_at_source") {
      return fetched;
    }
    return {
      state: "failed_retryable",
      reason_code: stableExtensionReason(
        fetched && fetched.reason_code,
        EXTENSION_ITEM_RETRYABLE_REASONS,
        "unknown_failure"
      ),
      evidence_code: null,
    };
  } catch (error) {
    if (isAcquisitionStop(error)) throw error;
    return {
      state: "failed_retryable",
      reason_code: "unknown_failure",
      evidence_code: null,
    };
  }
}

function oldestPublishedAt(items) {
  var oldest = null;
  (items || []).forEach(function (item) {
    var value = Date.parse(item && item.published_at);
    if (Number.isFinite(value) && (oldest === null || value < oldest)) oldest = value;
  });
  return oldest;
}

async function discoverMarketNewsIncident(tabId, manifest, detailBudget) {
  var interval = manifest.interval;
  var intervalStart = Date.parse(interval.start_at);
  var intervalEnd = Date.parse(interval.end_at);
  var startedAt = Date.now();
  var knownIds = await getMarketNewsRecentIds(1000);
  var knownSet = new Set(knownIds);
  var discoveredSet = new Set();
  var discoveredItems = [];
  var detailSaved = 0;
  var stableRounds = 0;
  var previousCount = 0;
  var oldestObserved = null;
  var reachedStart = false;
  var stopReason = "round_limit";

  await managedSaTabs.update(tabId, { url: SA_MARKET_NEWS_URL, active: true });
  await waitForMarketNewsPageLoad(tabId);
  var ready = await waitForMarketNewsReady(tabId);
  if (!ready.ok) {
    return {
      newly_discovered_metadata_count: 0,
      newly_discovered_detail_saved_count: 0,
      reached_interval_start: false,
      stop_reason: "interrupted",
      unresolved_interval: { start_at: interval.start_at, end_at: interval.end_at },
    };
  }

  for (var round = 0; round < MARKET_NEWS_INCIDENT_MAX_LIST_SCROLL_ROUNDS; round++) {
    if (Date.now() - startedAt >= MARKET_NEWS_INCIDENT_MAX_LIST_ELAPSED_MS) {
      stopReason = "elapsed_limit";
      break;
    }
    var items = await injectMarketNewsScraper(tabId);
    if (!Array.isArray(items)) items = [];
    items.forEach(function (item) {
      if (!item || !item.news_id || knownSet.has(item.news_id) || discoveredSet.has(item.news_id)) {
        return;
      }
      discoveredSet.add(item.news_id);
      discoveredItems.push(item);
    });
    var roundOldest = oldestPublishedAt(items);
    if (roundOldest !== null && (oldestObserved === null || roundOldest < oldestObserved)) {
      oldestObserved = roundOldest;
    }
    if (oldestObserved !== null && oldestObserved <= intervalStart) {
      reachedStart = true;
      stopReason = "window_start_reached";
      break;
    }

    var scroll = await chrome.scripting.executeScript({
      target: { tabId: tabId },
      func: function () {
        var root = document.scrollingElement || document.documentElement;
        var before = root ? root.scrollHeight : 0;
        window.scrollBy(0, window.innerHeight);
        var after = root ? root.scrollHeight : before;
        var atBottom = !!root && root.scrollTop + window.innerHeight >= root.scrollHeight - 2;
        return { before: before, after: after, at_bottom: atBottom };
      },
    });
    await sleep(randomBetween(
      MARKET_NEWS_PROFILES.backfill.listScrollSettleMinMs,
      MARKET_NEWS_PROFILES.backfill.listScrollSettleMaxMs
    ));
    var scrollEvidence = scroll[0] && scroll[0].result || {};
    if (items.length <= previousCount) stableRounds++;
    else stableRounds = 0;
    previousCount = items.length;
    if (stableRounds >= MARKET_NEWS_INCIDENT_STABLE_ROUNDS) {
      stopReason = scrollEvidence.at_bottom ? "source_bottom" : "stable_no_growth";
      break;
    }
  }

  if (discoveredItems.length > 0) {
    var metadataSave = await sendNativeMessage2({
      action: "save_market_news",
      items: discoveredItems,
      detail_current_limit: 0,
      detail_backfill_limit: 0,
    });
    if (!metadataSave || metadataSave.status !== "ok") {
      throw new Error("metadata_save_failed");
    }
  }

  for (var index = 0; index < discoveredItems.length && detailBudget > 0; index++) {
    var item = discoveredItems[index];
    var outcome = await recoverMarketNewsTarget(tabId, {
      news_id: item.news_id,
      pathname: new URL(item.url).pathname,
      body_present: false,
    });
    detailBudget--;
    if (outcome.state === "repaired") detailSaved++;
  }

  var unresolvedEnd = oldestObserved === null
    ? intervalEnd
    : Math.min(intervalEnd, Math.max(intervalStart, oldestObserved));
  return {
    newly_discovered_metadata_count: discoveredItems.length,
    newly_discovered_detail_saved_count: detailSaved,
    reached_interval_start: reachedStart,
    stop_reason: stopReason,
    unresolved_interval: reachedStart ? null : {
      start_at: new Date(intervalStart).toISOString(),
      end_at: new Date(unresolvedEnd).toISOString(),
    },
  };
}

// --- Main refresh flow ---

async function recordAlphaPicksFailure(scope, error, batchTs) {
  const receipt = await sendToNativeHost("refresh_failure", scope, [], error, batchTs);
  // The native response acknowledges the failure record, not a successful scrape.
  return {
    status: "error", scope: scope, error: error,
    recorded_failure: !!receipt && receipt.status === "ok" && receipt.recorded_failure === true,
  };
}

async function doRefresh(mode, options) {
  options = options || {};
  var diagnostics = options.diagnostics;
  const batchTs = new Date().toISOString();
  const results = { current: null, closed: null, mode: mode, trigger: options.trigger || "manual" };

  let tabId = null;
  let detailsStarted = false;
  try {
    await cleanupCollectorTabs({ force: true });
    // --- Scrape current picks ---
    sendProgress("Opening current picks page...");
    const tab = await managedSaTabs.create({ url: SA_CURRENT_URL, active: false });
    tabId = tab.id;
    await registerCollectorTab(tabId, "alpha_picks");

    sendProgress("Waiting for current picks table...");
    let ready = await waitForAlphaPicksTableReady(tabId, SA_CURRENT_URL, "current picks");
    if (!ready.ok) {
      recordExtensionFailure(diagnostics, {
        stage: "page_readiness",
        reason_code: ready.reason_code || "dom_not_ready",
        target_kind: "phase",
        retryable: true,
        attempt_count: 1,
      });
      results.current = await recordAlphaPicksFailure("current", ready.error, batchTs);
      if (await observeSaRestriction(ready.reason_code)) {
        results.acquisition_stop = {status:"error",reason:"site_paused",error_code:ready.reason_code};
        results.completed_phases = [];
        await saveRefreshState(batchTs,results);
        return results;
      }
    } else {
      sendProgress("Scraping current picks...");
      const currentPicks = await injectScraper(tabId);
      results.current = await sendToNativeHost("refresh", "current", currentPicks, null, batchTs);
      if (!legacyResultIsOk(results.current)) {
        recordNativeExtensionFailure(diagnostics, results.current, "phase", null);
      }
      results._currentPicks = currentPicks;  // Keep for detail fetch
    }

    // --- Scrape closed (removed) picks ---
    sendProgress("Opening closed picks page...");
    await managedSaTabs.update(tabId, { url: SA_CLOSED_URL });

    sendProgress("Waiting for closed picks table...");
    ready = await waitForAlphaPicksTableReady(tabId, SA_CLOSED_URL, "closed picks");
    if (!ready.ok) {
      recordExtensionFailure(diagnostics, {
        stage: "page_readiness",
        reason_code: ready.reason_code || "dom_not_ready",
        target_kind: "phase",
        retryable: true,
        attempt_count: 1,
      });
      results.closed = await recordAlphaPicksFailure("closed", ready.error, batchTs);
      if (await observeSaRestriction(ready.reason_code)) {
        results.acquisition_stop = {status:"error",reason:"site_paused",error_code:ready.reason_code};
        results.completed_phases = legacyResultIsOk(results.current) ? ["current_picks"] : [];
        await saveRefreshState(batchTs,results);
        return results;
      }
    } else {
      sendProgress("Scraping closed picks...");
      const closedPicks = await injectScraper(tabId);
      results.closed = await sendToNativeHost("refresh", "closed", closedPicks, null, batchTs);
      if (!legacyResultIsOk(results.closed)) {
        recordNativeExtensionFailure(diagnostics, results.closed, "phase", null);
      }
    }

    // --- Incremental detail fetch (current picks only) ---
    var currentPicks = null;
    if (legacyResultIsOk(results.current)) {
      // Re-read currentPicks from the scrape result stored earlier
      // We need to keep them in scope — move the variable up
      currentPicks = results._currentPicks || [];
    }
    if (currentPicks && currentPicks.length > 0) {
      sendProgress("Checking detail cache...");
      detailsStarted = true;
      var detailResult = await doDetailFetch(tabId, currentPicks, mode, diagnostics);
      results.details = detailResult;
      if (detailResult.acquisition_stop) {
        results.acquisition_stop = detailResult.acquisition_stop;
        results.completed_phases = ["current_picks","closed_picks"].filter(function (name) {
          return legacyResultIsOk(results[name === "current_picks" ? "current" : "closed"]);
        });
      }
    }

    await saveRefreshState(batchTs, results);
    sendProgress("Done!");
    return results;
  } catch (err) {
    if (isAcquisitionStop(err)) {
      results.acquisition_stop = err.detail;
      results.completed_phases = ["current_picks","closed_picks"].filter(function (name) {
        return legacyResultIsOk(results[name === "current_picks" ? "current" : "closed"]);
      });
      await saveRefreshState(batchTs,results);
      return results;
    }
    recordExtensionFailure(diagnostics, {
      stage: "extension_runtime",
      reason_code: "unknown_failure",
      target_kind: "phase",
      retryable: true,
      attempt_count: 1,
    });
    const error = err.message || String(err);
    if (detailsStarted && !results.details) {
      results.details = {error: error, reason_code: "article_metadata_failed"};
    }
    if (!results.current) {
      results.current = await recordAlphaPicksFailure("current", error, batchTs);
    }
    if (!results.closed) {
      results.closed = await recordAlphaPicksFailure("closed", error, batchTs);
    }
    await saveRefreshState(batchTs, results);
    return results;
  } finally {
    if (tabId) {
      await safeRemoveTab(tabId);
      await unregisterCollectorTab(tabId);
    }
  }
}


// --- Market News refresh flow ---

async function doMarketNewsRefresh(mode, options) {
  options = options || {};
  var diagnostics = options.diagnostics;
  if (marketNewsRefreshInFlight) {
    return {
      status: "busy",
      error: "market news refresh already running",
      trigger: options.trigger || "manual",
    };
  }
  marketNewsRefreshInFlight = true;
  const batchTs = new Date().toISOString();
  var profile = getMarketNewsProfile(mode);
  var tabId = null;
  var activePhase = "list_navigation";
  try {
    await cleanupCollectorTabs({ force: true });
    sendProgress("Opening market news page...");
    const tab = await managedSaTabs.create({ url: SA_MARKET_NEWS_URL, active: false });
    tabId = tab.id;
    await registerCollectorTab(tabId, "market_news");
    await waitForMarketNewsPageLoad(tabId);

    sendProgress("Waiting for market news...");
    var ready = await waitForMarketNewsReady(tabId);
    if (!ready.ok) {
      await observeSaRestriction(ready.reason_code);
      recordExtensionFailure(diagnostics, {
        stage: "page_readiness",
        reason_code: ready.reason_code || "navigation_timeout",
        target_kind: "phase",
        retryable: true,
        attempt_count: 1,
      });
      var failure = {
        status: "error",
        error: ready.error,
        failure_phase: "list_navigation",
        reason_code: ready.reason_code || "list_navigation_failed",
        saved: 0,
        count: 0,
      };
      await saveMarketNewsState(batchTs, mode, failure);
      return failure;
    }

    activePhase = "list_scrape";
    await chrome.tabs.update(tabId, { active: true });
    await sleep(randomBetween(profile.listStartMinMs, profile.listStartMaxMs));
    var knownNewsIds = await getMarketNewsRecentIds(profile.recentKnownIdsLimit);
    await scrollMarketNews(tabId, profile, knownNewsIds);
    await chrome.tabs.update(tabId, { active: false });

    sendProgress("Scraping market news...");
    var items = await injectMarketNewsScraper(tabId);
    if (!Array.isArray(items)) items = [];

    activePhase = "metadata_save";
    sendProgress("Saving " + items.length + " market-news item(s)...");
    var detailCurrentLimit = getMarketNewsDetailCurrentLimit(mode);
    var detailBackfillLimit = getMarketNewsDetailBackfillLimit(mode);
    var result = await sendNativeMessage2({
      action: "save_market_news",
      items: items,
      detail_current_limit: detailCurrentLimit,
      detail_backfill_limit: detailBackfillLimit,
    });
    if (!result || result.status !== "ok") {
      recordNativeExtensionFailure(diagnostics, result, "phase", null);
      result = {
        status: "error",
        error: (result && result.error) || "save_market_news failed",
        failure_phase: "metadata_save",
        reason_code: "metadata_save_failed",
        saved: 0,
      };
    }
    result.count = items.length;

    activePhase = "detail_fetch";
    var needDetail = buildMarketNewsDetailQueue(result, mode);
    var detailFetched = 0;
    var detailFailed = 0;
    var detailFailures = [];
    result.detail_queued = needDetail.length;
    if (needDetail.length > 0) {
      sendProgress("Fetching " + needDetail.length + " market-news detail page(s)...");
    }
    for (var i = 0; i < needDetail.length; i++) {
      var item = needDetail[i];
      sendProgress("News detail " + (i + 1) + "/" + needDetail.length + ": " + item.news_id);
      try {
        await withTimeout(
          managedSaTabs.update(tabId, { url: item.url, active: false }),
          45000,
          "market news tab update timeout"
        );
        await waitForTabLoad(tabId, MARKET_NEWS_DETAIL_TAB_LOAD_TIMEOUT_MS, expectedPathFromUrl(item.url));
        await withTimeout(
          installMarketNewsPageGuards(tabId),
          10000,
          "market news guard timeout"
        );
        var saveDetail = await withTimeout(
          fetchMarketNewsDetailWithRetry(tabId, item, profile),
          MARKET_NEWS_DETAIL_ITEM_TIMEOUT_MS,
          "market news detail timeout"
        );
        if (saveDetail && saveDetail.ok) {
          detailFetched++;
        } else {
          var detailReason = stableExtensionReason(
            saveDetail && saveDetail.reason_code,
            EXTENSION_ITEM_RETRYABLE_REASONS,
            "unknown_failure"
          );
          if (saveDetail && saveDetail.native_failure) {
            detailFailed += recordNativeExtensionFailure(
              diagnostics,
              saveDetail.native_failure,
              "market_news_detail",
              item.news_id
            );
          } else {
            var detailStage = detailReason === "parser_empty"
              ? "content_parse"
              : (detailReason === "unknown_failure"
                ? "extension_runtime"
                : "page_readiness");
            detailFailed += recordExtensionFailure(diagnostics, {
              stage: detailStage,
              reason_code: detailReason,
              target_kind: "market_news_detail",
              target_ref: item.news_id,
              retryable: true,
              attempt_count: 1,
            });
          }
          detailFailures.push({
            news_id: item.news_id,
            reason_code: detailReason,
            error: (saveDetail && saveDetail.error) || "detail_not_saved",
          });
        }
      } catch (err) {
        if (isAcquisitionStop(err)) {
          result.acquisition_stop = err.detail;
          result.completed_phases = ["list_navigation","list_scrape","metadata_save","capture_readback"];
          result.pending_news_ids = needDetail.slice(i).map(function (pending) {return pending.news_id;});
          break;
        }
        detailFailed += recordExtensionFailure(diagnostics, {
          stage: "extension_runtime",
          reason_code: "unknown_failure",
          target_kind: "market_news_detail",
          target_ref: item.news_id,
          retryable: true,
          attempt_count: 1,
        });
        detailFailures.push({
          news_id: item.news_id,
          reason_code: "unknown_failure",
          error: (err && err.message) || String(err || "detail_error"),
        });
      }
      if (i + 1 < needDetail.length) {
        await sleep(randomBetween(profile.detailGapMinMs, profile.detailGapMaxMs));
      }
    }
    result.detail_fetched = detailFetched;
    result.detail_failed = detailFailed;
    if (detailFailures.length > 0) {
      result.detail_failures = detailFailures;
    }
    result.trigger = options.trigger || "manual";
    activePhase = "capture_readback";
    await saveMarketNewsState(batchTs, mode, result);
    sendProgress("Market news done!");
    return result;
  } catch (err) {
    if (isAcquisitionStop(err)) {
      var stoppedResult = {status:"deferred",acquisition_stop:err.detail,completed_phases:[],saved:0,count:0};
      await saveMarketNewsState(batchTs,mode,stoppedResult);
      return stoppedResult;
    }
    recordExtensionFailure(diagnostics, {
      stage: "extension_runtime",
      reason_code: "unknown_failure",
      target_kind: "phase",
      retryable: true,
      attempt_count: 1,
    });
    var reasonByPhase = {
      list_navigation: "list_navigation_failed",
      list_scrape: "list_scrape_failed",
      metadata_save: "metadata_save_failed",
      detail_fetch: "detail_queue_failed",
      capture_readback: "capture_readback_failed",
    };
    var errorResult = {
      status: "error",
      error: err.message || String(err),
      failure_phase: activePhase,
      reason_code: reasonByPhase[activePhase] || "unknown_failure",
      saved: 0,
      count: 0,
      trigger: options.trigger || "manual",
    };
    await saveMarketNewsState(batchTs, mode, errorResult);
    return errorResult;
  } finally {
    marketNewsRefreshInFlight = false;
    if (tabId) {
      await safeRemoveTab(tabId);
      await unregisterCollectorTab(tabId);
    }
  }
}

function getMarketNewsDetailBackfillLimit(mode) {
  return MARKET_NEWS_DETAIL_BACKFILL_LIMITS[mode] || MARKET_NEWS_DETAIL_BACKFILL_LIMITS.quick;
}

function getMarketNewsDetailCurrentLimit(mode) {
  return MARKET_NEWS_DETAIL_CURRENT_LIMITS[mode] || MARKET_NEWS_DETAIL_CURRENT_LIMITS.quick;
}

function getMarketNewsDetailTotalLimit(mode) {
  return MARKET_NEWS_DETAIL_TOTAL_LIMITS[mode] || MARKET_NEWS_DETAIL_TOTAL_LIMITS.quick;
}

function getMarketNewsProfile(mode) {
  return MARKET_NEWS_PROFILES[mode] || MARKET_NEWS_PROFILES.quick;
}

function buildMarketNewsDetailQueue(result, mode) {
  result = result || {};
  var totalLimit = getMarketNewsDetailTotalLimit(mode);
  var currentLimit = getMarketNewsDetailCurrentLimit(mode);
  var backfillLimit = getMarketNewsDetailBackfillLimit(mode);
  var current = Array.isArray(result.need_detail_current) ? result.need_detail_current : [];
  var backfill = Array.isArray(result.need_detail_backfill) ? result.need_detail_backfill : [];
  var combined = Array.isArray(result.need_detail) ? result.need_detail : [];

  if (current.length === 0 && backfill.length === 0) {
    return totalLimit > 0 ? combined.slice(0, totalLimit) : combined.slice();
  }

  var queue = [];
  var seen = {};

  function addItems(items, limit) {
    var added = 0;
    for (var i = 0; i < items.length; i++) {
      if (limit != null && added >= limit) break;
      if (queue.length >= totalLimit) break;
      var item = items[i];
      var newsId = item && item.news_id;
      if (!newsId || seen[newsId]) continue;
      seen[newsId] = true;
      queue.push(item);
      added++;
    }
    return added;
  }

  var currentAdded = addItems(current, currentLimit);
  var backfillBudget = backfillLimit;
  if (currentAdded < currentLimit) {
    backfillBudget += (currentLimit - currentAdded);
  }
  addItems(backfill, backfillBudget);
  if (queue.length < totalLimit) {
    addItems(combined, totalLimit - queue.length);
  }
  return queue;
}

var autoSyncSettingWrites = Promise.resolve();

function writeAutoSyncSettings(jobKey, enabled, intervalMinutes, expectedRevision) {
  var run = autoSyncSettingWrites.catch(function () {}).then(async function () {
    var intent = await readAutoSyncIntent(jobKey);
    // The comparison belongs inside the write queue, not before awaiting it.
    if (expectedRevision !== undefined && intent.revision !== expectedRevision) {
      return {status:"skipped",reason:"operator_settings_changed"};
    }
    if (intent.revision >= Number.MAX_SAFE_INTEGER) throw new Error("Automatic intent revision exhausted");
    var intervalKey = jobKey + "AutoSyncIntervalMinutes";
    var data = await chrome.storage.local.get([intervalKey]);
    var normalize = jobKey === "alphaPicks"
      ? normalizeAlphaPicksAutoSyncIntervalMinutes : normalizeMarketNewsAutoSyncIntervalMinutes;
    var interval = normalize(intervalMinutes != null ? intervalMinutes : data[intervalKey]);
    var update = {};
    update[jobKey + "AutoSyncEnabled"] = enabled === true;
    update[jobKey + "AutoSyncRevision"] = intent.revision + 1;
    update[intervalKey] = interval;
    if (jobKey === "marketNews") update.marketNewsAutoSyncLastStartedAt = null;
    await chrome.storage.local.set(update);
    return {status:"ok",interval:interval,revision:intent.revision + 1};
  });
  autoSyncSettingWrites = run;
  return run;
}

async function setAlphaPicksAutoSyncEnabled(enabled, intervalMinutes, expectedRevision) {
  var written = await writeAutoSyncSettings("alphaPicks", enabled, intervalMinutes, expectedRevision);
  if (written.status !== "ok") return written;
  await syncAlphaPicksAutoSyncAlarm();
  return {
    status: "ok",
    enabled: enabled,
    interval_minutes: written.interval,
    revision: written.revision,
  };
}

async function setMarketNewsAutoSyncEnabled(enabled, intervalMinutes, expectedRevision) {
  var written = await writeAutoSyncSettings("marketNews", enabled, intervalMinutes, expectedRevision);
  if (written.status !== "ok") return written;
  var normalizedInterval = written.interval;
  await syncMarketNewsAutoSyncAlarm();
  var schedule = getMarketNewsAutoSyncSchedule(normalizedInterval);
  return {
    status: "ok",
    enabled: enabled,
    interval_minutes: schedule.intervalMinutes,
    interval_setting: normalizedInterval,
    interval_label: schedule.label,
    revision: written.revision,
  };
}

async function syncAllAutoSyncAlarms() {
  await syncAlphaPicksAutoSyncAlarm();
  await syncMarketNewsAutoSyncAlarm();
  await companyFinancialRefresh.syncAlarm();
}

async function refreshAcquisitionStatus() {
  try { await syncAcquisitionBadge(await companyCollectorControl("status")); }
  catch (_) { await syncAcquisitionBadge(null).catch(function () {}); }
}

async function ensureAutoSyncAlarms() {
  var data = await chrome.storage.local.get([
    "alphaPicksAutoSyncEnabled",
    "marketNewsAutoSyncEnabled",
  ]);
  var alarms = await getAllAlarms();
  var names = {};
  for (var i = 0; i < alarms.length; i++) {
    if (alarms[i] && alarms[i].name) {
      names[alarms[i].name] = true;
    }
  }

  var repaired = [];
  if (data.alphaPicksAutoSyncEnabled && !names[ALPHA_PICKS_AUTO_SYNC_ALARM]) {
    await syncAlphaPicksAutoSyncAlarm();
    repaired.push(ALPHA_PICKS_AUTO_SYNC_ALARM);
  }
  if (data.marketNewsAutoSyncEnabled && !names[MARKET_NEWS_AUTO_SYNC_ALARM]) {
    await syncMarketNewsAutoSyncAlarm();
    repaired.push(MARKET_NEWS_AUTO_SYNC_ALARM);
  }
  if (!names[SACompanyRefresh.alarm]) await companyFinancialRefresh.syncAlarm();
  return {
    status: "ok",
    repaired: repaired,
  };
}

async function syncAlphaPicksAutoSyncAlarm() {
  var data = await chrome.storage.local.get(["alphaPicksAutoSyncEnabled", "alphaPicksAutoSyncIntervalMinutes"]);
  var enabled = !!data.alphaPicksAutoSyncEnabled;
  var intervalMinutes = normalizeAlphaPicksAutoSyncIntervalMinutes(data.alphaPicksAutoSyncIntervalMinutes);
  if (data.alphaPicksAutoSyncIntervalMinutes !== intervalMinutes) {
    await chrome.storage.local.set({ alphaPicksAutoSyncIntervalMinutes: intervalMinutes });
  }
  await chrome.alarms.clear(ALPHA_PICKS_AUTO_SYNC_ALARM);
  if (enabled && !await acquisitionPaused("alpha_picks")) {
    await chrome.alarms.create(ALPHA_PICKS_AUTO_SYNC_ALARM, {
      delayInMinutes: intervalMinutes,
      periodInMinutes: intervalMinutes,
    });
  }
}

async function syncMarketNewsAutoSyncAlarm() {
  var data = await chrome.storage.local.get(["marketNewsAutoSyncEnabled", "marketNewsAutoSyncIntervalMinutes"]);
  var enabled = !!data.marketNewsAutoSyncEnabled;
  var intervalMinutes = normalizeMarketNewsAutoSyncIntervalMinutes(data.marketNewsAutoSyncIntervalMinutes);
  if (data.marketNewsAutoSyncIntervalMinutes !== intervalMinutes) {
    await chrome.storage.local.set({ marketNewsAutoSyncIntervalMinutes: intervalMinutes });
  }
  await chrome.alarms.clear(MARKET_NEWS_AUTO_SYNC_ALARM);
  if (enabled && !await acquisitionPaused("news")) {
    var periodMinutes = intervalMinutes === MARKET_NEWS_AUTO_SYNC_AUTO_VALUE
      ? MARKET_NEWS_AUTO_SYNC_HEARTBEAT_MINUTES
      : intervalMinutes;
    await chrome.alarms.create(MARKET_NEWS_AUTO_SYNC_ALARM, {
      delayInMinutes: periodMinutes,
      periodInMinutes: periodMinutes,
    });
  }
}

async function shouldRunMarketNewsAutoSync() {
  var data = await chrome.storage.local.get([
    "marketNewsAutoSyncEnabled",
    "marketNewsAutoSyncIntervalMinutes",
    "marketNewsAutoSyncLastStartedAt",
  ]);
  if (!data.marketNewsAutoSyncEnabled) return false;

  var intervalSetting = normalizeMarketNewsAutoSyncIntervalMinutes(data.marketNewsAutoSyncIntervalMinutes);
  if (intervalSetting !== MARKET_NEWS_AUTO_SYNC_AUTO_VALUE) {
    return true;
  }

  var lastStartedAt = data.marketNewsAutoSyncLastStartedAt;
  if (!lastStartedAt) return true;
  var lastTs = Date.parse(lastStartedAt);
  if (!Number.isFinite(lastTs)) return true;

  var schedule = getMarketNewsAutoSyncSchedule(intervalSetting, new Date());
  var requiredMs = schedule.intervalMinutes * 60 * 1000;
  return (Date.now() - lastTs) >= requiredMs;
}

async function markMarketNewsAutoSyncStarted() {
  await chrome.storage.local.set({
    marketNewsAutoSyncLastStartedAt: new Date().toISOString(),
  });
}

function shouldMarkMarketNewsAutoSyncRun(result) {
  if (!result || typeof result !== "object") return false;
  return result.status !== "error" && result.status !== "busy";
}

function normalizeAlphaPicksAutoSyncIntervalMinutes(value) {
  var mins = parseInt(value, 10);
  if (ALPHA_PICKS_AUTO_SYNC_ALLOWED_PERIODS.indexOf(mins) === -1) {
    return ALPHA_PICKS_AUTO_SYNC_DEFAULT_PERIOD_MINUTES;
  }
  return mins;
}

function normalizeMarketNewsAutoSyncIntervalMinutes(value) {
  if (value === MARKET_NEWS_AUTO_SYNC_AUTO_VALUE) {
    return MARKET_NEWS_AUTO_SYNC_AUTO_VALUE;
  }
  var mins = parseInt(value, 10);
  if (MARKET_NEWS_AUTO_SYNC_ALLOWED_PERIODS.indexOf(mins) === -1) {
    return MARKET_NEWS_AUTO_SYNC_DEFAULT_PERIOD_MINUTES;
  }
  return mins;
}

function formatAutoSyncIntervalLabel(intervalMinutes) {
  var mins = parseInt(intervalMinutes, 10);
  if (mins === 60) return "every 60 min";
  return "every " + mins + " min";
}

function getMarketNewsAutoSyncSchedule(intervalSetting, now) {
  if (intervalSetting !== MARKET_NEWS_AUTO_SYNC_AUTO_VALUE) {
    var fixedMinutes = parseInt(intervalSetting, 10);
    return {
      intervalMinutes: fixedMinutes,
      label: formatAutoSyncIntervalLabel(fixedMinutes),
    };
  }

  var parts = getNewYorkTimeParts(now || new Date());
  var totalMinutes = (parts.hour * 60) + parts.minute;
  var windows = parts.weekday === "Sat" || parts.weekday === "Sun"
    ? MARKET_NEWS_AUTO_SYNC_WINDOWS_ET.weekend
    : MARKET_NEWS_AUTO_SYNC_WINDOWS_ET.weekday;
  var resolvedMinutes = resolveMarketNewsAutoSyncInterval(windows, totalMinutes);

  return {
    intervalMinutes: resolvedMinutes,
    label: "auto (" + formatAutoSyncIntervalLabel(resolvedMinutes) + ", ET)",
  };
}

function resolveMarketNewsAutoSyncInterval(windows, totalMinutes) {
  for (var i = 0; i < windows.length; i++) {
    var window = windows[i];
    if (totalMinutes >= window.start && totalMinutes < window.end) {
      return window.interval;
    }
  }
  return MARKET_NEWS_AUTO_SYNC_DEFAULT_PERIOD_MINUTES;
}

function getNewYorkTimeParts(now) {
  var formatter = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  var parts = formatter.formatToParts(now || new Date());
  var out = { weekday: "", hour: 0, minute: 0 };
  for (var i = 0; i < parts.length; i++) {
    var part = parts[i];
    if (part.type === "weekday") out.weekday = part.value;
    if (part.type === "hour") out.hour = parseInt(part.value, 10) || 0;
    if (part.type === "minute") out.minute = parseInt(part.value, 10) || 0;
  }
  return out;
}

// --- Tab management ---

function waitForTabLoad(tabId, timeoutMs, expectedUrlFragment) {
  timeoutMs = timeoutMs || DEFAULT_TAB_LOAD_TIMEOUT_MS;
  return new Promise((resolve, reject) => {
    var settled = false;
    var timeoutId = null;

    function cleanup() {
      chrome.tabs.onUpdated.removeListener(onUpdated);
      chrome.tabs.onRemoved.removeListener(onRemoved);
      if (timeoutId) {
        clearTimeout(timeoutId);
        timeoutId = null;
      }
    }

    function finish(error) {
      if (settled) return;
      settled = true;
      cleanup();
      if (error) {
        reject(error);
      } else {
        resolve();
      }
    }

    const onUpdated = (id, changeInfo, tab) => {
      if (id !== tabId) return;
      if (changeInfo.status === "complete" || (tab && tab.status === "complete")) {
        inspectSaAccess(tabId).then(function () {
          if (tabMatchesExpectedUrl(tab, expectedUrlFragment)) finish();
        }).catch(finish);
      }
    };

    const onRemoved = (id) => {
      if (id === tabId) {
        finish(new Error("Tab closed before load completed"));
      }
    };

    chrome.tabs.onUpdated.addListener(onUpdated);
    chrome.tabs.onRemoved.addListener(onRemoved);

    timeoutId = setTimeout(() => {
      chrome.tabs.get(tabId).then((tab) => {
        finish(new Error(formatTabLoadTimeout(tab, expectedUrlFragment, timeoutMs)));
      }).catch(() => {
        finish(new Error("Timeout waiting for tab load"));
      });
    }, timeoutMs);

    chrome.tabs.get(tabId).then((tab) => {
      if (!tab) {
        finish(new Error("Tab not found"));
        return;
      }
      if (tab.status === "complete") {
        inspectSaAccess(tabId).then(function () {
          if (tabMatchesExpectedUrl(tab, expectedUrlFragment)) finish();
        }).catch(finish);
      }
    }).catch((err) => {
      finish(err || new Error("Failed to inspect tab state"));
    });
  }).then(async function () { await inspectSaAccess(tabId); });
}

function formatTabLoadTimeout(tab, expectedUrlFragment, timeoutMs) {
  var status = (tab && tab.status) || "unknown";
  var url = shortenForLog((tab && tab.url) || "", 180);
  var pendingUrl = shortenForLog((tab && tab.pendingUrl) || "", 180);
  return (
    "Timeout waiting for tab load" +
    " (" + timeoutMs + "ms" +
    ", expected=" + (expectedUrlFragment || "any") +
    ", status=" + status +
    ", url=" + (url || "n/a") +
    ", pendingUrl=" + (pendingUrl || "n/a") +
    ")"
  );
}

function shortenForLog(value, maxLen) {
  value = String(value || "");
  maxLen = maxLen || 180;
  if (value.length <= maxLen) return value;
  return value.slice(0, maxLen - 3) + "...";
}

function expectedPathFromUrl(url) {
  try {
    return new URL(url).pathname;
  } catch (_) {
    return url || null;
  }
}

function tabMatchesExpectedUrl(tab, expectedUrlFragment) {
  if (!expectedUrlFragment) return true;
  var currentUrl = (tab && (tab.url || tab.pendingUrl)) || "";
  return currentUrl.indexOf(expectedUrlFragment) >= 0;
}

function withTimeout(promise, timeoutMs, label) {
  var timer = null;
  var timeout = new Promise(function (_, reject) {
    timer = setTimeout(function () {
      reject(new Error(label || "operation timeout"));
    }, timeoutMs);
  });
  return Promise.race([promise, timeout]).finally(function () {
    if (timer) clearTimeout(timer);
  });
}

async function waitForMarketNewsPageLoad(tabId) {
  var expectedPath = expectedPathFromUrl(SA_MARKET_NEWS_URL);
  var firstError = null;
  try {
    await waitForTabLoad(tabId, MARKET_NEWS_INITIAL_TAB_LOAD_TIMEOUT_MS, expectedPath);
    return;
  } catch (err) {
    if (isAcquisitionStop(err)) throw err;
    firstError = err;
  }

  var firstProbe = await probeMarketNewsListDom(tabId);
  if (firstProbe.status === "ready") {
    console.warn("[SA] Market News tab did not report complete, but DOM is ready:", firstProbe);
    return;
  }
  if (firstProbe.status === "login_redirect") {
    await observeSaRestriction("login_required");
    throw new Error("Session expired");
  }

  sendProgress("Retrying market news page load...");
  try {
    await managedSaTabs.reload(tabId);
    await waitForTabLoad(tabId, MARKET_NEWS_RETRY_TAB_LOAD_TIMEOUT_MS, expectedPath);
    return;
  } catch (retryErr) {
    if (isAcquisitionStop(retryErr)) throw retryErr;
    var retryProbe = await probeMarketNewsListDom(tabId);
    if (retryProbe.status === "ready") {
      console.warn("[SA] Market News tab retry did not report complete, but DOM is ready:", retryProbe);
      return;
    }
    if (retryProbe.status === "login_redirect") {
      await observeSaRestriction("login_required");
      throw new Error("Session expired");
    }
    throw new Error(
      "Timeout waiting for market news tab load after retry; first=" +
      ((firstError && firstError.message) || String(firstError)) +
      "; retry=" +
      ((retryErr && retryErr.message) || String(retryErr)) +
      "; probe=" + formatMarketNewsProbe(retryProbe)
    );
  }
}

async function probeMarketNewsListDom(tabId) {
  try {
    var results = await chrome.scripting.executeScript({
      target: { tabId },
      func: function () {
        var href = location.href || "";
        if (href.includes("/login") || href.includes("/sign_in")) {
          return { status: "login_redirect", url: href };
        }
        var body = document.body;
        var text = body ? body.innerText : "";
        var links = document.querySelectorAll('a[href*="/news/"]');
        if (links.length >= 3) {
          return { status: "ready", count: links.length, textLength: text.length, url: href };
        }
        if (text.length > 1000 && links.length > 0) {
          return { status: "ready", count: links.length, textLength: text.length, url: href };
        }
        return {
          status: "loading",
          count: links.length,
          textLength: text.length,
          readyState: document.readyState,
          url: href,
        };
      },
    });
    return (results[0] && results[0].result) || { status: "no_result" };
  } catch (err) {
    return { status: "probe_error", error: (err && err.message) || String(err) };
  }
}

function formatMarketNewsProbe(probe) {
  probe = probe || {};
  return JSON.stringify({
    status: probe.status || "unknown",
    count: probe.count,
    textLength: probe.textLength,
    readyState: probe.readyState,
    url: shortenForLog(probe.url || "", 180),
    error: probe.error,
  });
}

async function getCollectorTabs() {
  try {
    var data = await chrome.storage.local.get([COLLECTOR_TABS_STORAGE_KEY]);
    var tabs = data && data[COLLECTOR_TABS_STORAGE_KEY];
    return tabs && typeof tabs === "object" ? tabs : {};
  } catch (_) {
    return {};
  }
}

async function setCollectorTabs(tabs) {
  var value = {};
  if (tabs && typeof tabs === "object") {
    value[COLLECTOR_TABS_STORAGE_KEY] = tabs;
  } else {
    value[COLLECTOR_TABS_STORAGE_KEY] = {};
  }
  await chrome.storage.local.set(value);
}

async function registerCollectorTab(tabId, flow) {
  if (tabId == null) return;
  var tabs = await getCollectorTabs();
  tabs[String(tabId)] = {
    tabId: tabId,
    flow: flow || "unknown",
    createdAt: new Date().toISOString(),
  };
  await setCollectorTabs(tabs);
}

async function unregisterCollectorTab(tabId) {
  if (tabId == null) return;
  var tabs = await getCollectorTabs();
  delete tabs[String(tabId)];
  await setCollectorTabs(tabs);
}

async function cleanupCollectorTabs(options) {
  options = options || {};
  var force = !!options.force;
  var maxAgeMs = options.maxAgeMs || COLLECTOR_TAB_STALE_MS;
  var now = Date.now();
  var tabs = await getCollectorTabs();
  var changed = false;
  var entries = Object.keys(tabs);

  for (var i = 0; i < entries.length; i++) {
    var key = entries[i];
    var item = tabs[key] || {};
    var tabId = item.tabId != null ? item.tabId : parseInt(key, 10);
    var createdAt = Date.parse(item.createdAt || "");
    var isStale = !Number.isFinite(createdAt) || (now - createdAt) >= maxAgeMs;
    if (!force && !isStale) continue;

    await safeRemoveTab(tabId);
    delete tabs[key];
    changed = true;
  }

  if (changed) {
    await setCollectorTabs(tabs);
  }
}

async function safeRemoveTab(tabId) {
  if (tabId == null) return false;
  try {
    await chrome.tabs.remove(tabId);
    if (saAcquisitionTask) saAcquisitionTask.ownedTabs.delete(tabId);
    return true;
  } catch (err) {
    var message = err && err.message ? err.message : String(err || "");
    if (message && message.indexOf("No tab with id") >= 0) {
      if (saAcquisitionTask) saAcquisitionTask.ownedTabs.delete(tabId);
      return false;
    }
    console.warn("[SA] Failed to remove tab", tabId, message);
    return false;
  }
}

// --- DOM readiness polling ---

async function waitForAlphaPicksTableReady(tabId, expectedUrl, label, timeoutMs = ALPHA_PICKS_PAGE_TIMEOUT_MS) {
  const start = Date.now();
  const expectedPath = expectedPathFromUrl(expectedUrl);
  const expectedOrigin = new URL(expectedUrl).origin;
  let lastSnapshot = null;
  while (Date.now() - start < timeoutMs) {
    if (saAcquisitionTask) requireAcquisitionTask();
    let tab = null;
    try {
      tab = await chrome.tabs.get(tabId);
    } catch (err) {
      lastSnapshot = { scriptError: "tab not found: " + (err && err.message ? err.message : String(err || "")) };
      await sleep(500);
      continue;
    }

    lastSnapshot = {
      tabStatus: (tab && tab.status) || "unknown",
      tabUrl: (tab && tab.url) || "",
      pendingUrl: (tab && tab.pendingUrl) || "",
    };
    // A newly created tab can be complete but still contain its initial blank document.
    if (!lastSnapshot.tabUrl || lastSnapshot.tabUrl === "about:blank") {
      await sleep(500);
      continue;
    }
    const pageOrigin = new URL(lastSnapshot.tabUrl).origin;
    if (pageOrigin !== expectedOrigin) {
      return {ok: false, reason_code: "dom_not_ready", error: "Unexpected Alpha Picks page origin: " + pageOrigin};
    }
    try {
      await inspectSaAccess(tabId);
    } catch (err) {
      const message = err && err.message ? err.message : String(err || "");
      // The tab URL may advance before its new document becomes injectable.
      if (isAcquisitionStop(err) || tab.status !== "loading" ||
          !/Missing host permission for the tab|Cannot access contents of (?:the )?url/i.test(message)) throw err;
      lastSnapshot.scriptError = message;
      await sleep(500);
      continue;
    }
    const snapshot = await inspectAlphaPicksReadiness(tabId, expectedPath);
    lastSnapshot = Object.assign({}, snapshot || {}, lastSnapshot);

    if (lastSnapshot.status === "login_redirect") {
      return {
        ok: false,
        error: "Session expired: " + (lastSnapshot.url || "unknown redirect"),
        reason_code: "login_required",
      };
    }
    if (lastSnapshot.status === "paywall") {
      return {
        ok: false,
        error: "Paywall: " + lastSnapshot.marker,
        reason_code: "access_restricted",
      };
    }
    if (lastSnapshot.status === "ready") {
      return { ok: true };
    }
    await sleep(500);
  }
  return {
    ok: false,
    error: formatAlphaPicksReadinessTimeout(label, expectedPath, timeoutMs, lastSnapshot),
    reason_code: "dom_not_ready",
  };
}

async function inspectAlphaPicksReadiness(tabId, expectedPath) {
  try {
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: (paywallMarkers, rowSelectors, expectedPathArg) => {
        const body = document.body;
        const text = body ? body.innerText || "" : "";
        const selectorCounts = {};
        let maxRows = 0;
        for (const selector of rowSelectors) {
          const count = document.querySelectorAll(selector).length;
          selectorCounts[selector] = count;
          if (count > maxRows) maxRows = count;
        }
        const url = location.href;
        const pathMatches = !expectedPathArg || location.pathname.indexOf(expectedPathArg) >= 0;
        if (location.href.includes("/login") || location.href.includes("/sign_in")) {
          return { status: "login_redirect", url, selectorCounts };
        }
        for (const marker of paywallMarkers) {
          if (text.includes(marker)) {
            return { status: "paywall", marker, url, selectorCounts };
          }
        }
        if (pathMatches && maxRows > 0) {
          return { status: "ready", url, selectorCounts, rowCount: maxRows };
        }
        return {
          status: "loading",
          url,
          expectedPath: expectedPathArg || "",
          pathMatches,
          documentReadyState: document.readyState,
          title: document.title || "",
          selectorCounts,
          rowCount: maxRows,
          bodySnippet: text.replace(/\s+/g, " ").slice(0, 280),
        };
      },
      args: [PAYWALL_MARKERS, ALPHA_PICKS_ROW_SELECTORS, expectedPath],
    });
    return (results[0] && results[0].result) || { status: "loading", scriptError: "empty script result" };
  } catch (err) {
    return {
      status: "loading",
      scriptError: err && err.message ? err.message : String(err || ""),
    };
  }
}

function formatAlphaPicksReadinessTimeout(label, expectedPath, timeoutMs, snapshot) {
  snapshot = snapshot || {};
  const counts = snapshot.selectorCounts
    ? Object.keys(snapshot.selectorCounts).map(function (k) {
        return k + ":" + snapshot.selectorCounts[k];
      }).join(", ")
    : "n/a";
  return (
    "Timeout waiting for Alpha Picks " + (label || "page") +
    " (" + timeoutMs + "ms" +
    ", expected=" + (expectedPath || "any") +
    ", tabStatus=" + (snapshot.tabStatus || "unknown") +
    ", documentReadyState=" + (snapshot.documentReadyState || "unknown") +
    ", url=" + shortenForLog(snapshot.url || snapshot.tabUrl || "", 180) +
    ", pendingUrl=" + shortenForLog(snapshot.pendingUrl || "", 180) +
    ", title=" + shortenForLog(snapshot.title || "", 120) +
    ", selectorCounts=" + counts +
    ", scriptError=" + shortenForLog(snapshot.scriptError || "", 160) +
    ", bodySnippet=" + shortenForLog(snapshot.bodySnippet || "", 220) +
    ")"
  );
}

async function waitForTableReady(tabId, timeoutMs = 30000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: (paywallMarkers, tableSelector) => {
        // Check login redirect
        if (location.href.includes("/login") || location.href.includes("/sign_in")) {
          return { status: "login_redirect", url: location.href };
        }
        // Check paywall
        const text = document.body ? document.body.innerText : "";
        for (const p of paywallMarkers) {
          if (text.includes(p)) return { status: "paywall", marker: p };
        }
        // Check table exists
        const row = document.querySelector(tableSelector);
        if (row) return { status: "ready" };
        return { status: "loading" };
      },
      args: [PAYWALL_MARKERS, TABLE_SELECTOR],
    });
    const check = results[0] && results[0].result;
    if (!check || check.status === "login_redirect") {
      return { ok: false, error: "Session expired: " + (check ? check.url : "unknown redirect") };
    }
    if (check.status === "paywall") {
      return { ok: false, error: "Paywall: " + check.marker };
    }
    if (check.status === "ready") {
      return { ok: true };
    }
    await sleep(500);
  }
  return { ok: false, error: "Timeout waiting for table" };
}

// --- Scraper injection ---

async function injectScraper(tabId) {
  const results = await chrome.scripting.executeScript({
    target: { tabId },
    files: ["scrape.js"],
  });
  return (results[0] && results[0].result) || [];
}

// --- Native Messaging ---

function sendToNativeHost(action, scope, picks, error, batchTs) {
  return new Promise((resolve) => {
    const msg = { action, scope, batch_ts: batchTs };
    if (action === "refresh") {
      msg.picks = picks;
    } else {
      msg.error = error || "unknown";
    }
    chrome.runtime.sendNativeMessage(NATIVE_HOST, msg, (response) => {
      if (chrome.runtime.lastError) {
        resolve({
          status: "error",
          scope,
          error: "Native host error: " + chrome.runtime.lastError.message,
          error_code: "native_host_unavailable",
        });
      } else {
        resolve(response || {
          status: "error",
          scope,
          error: "No response from native host",
          error_code: "invalid_native_response",
        });
      }
    });
  });
}

// --- Helpers ---

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function randomBetween(minMs, maxMs) {
  if (maxMs <= minMs) return minMs;
  return Math.floor(Math.random() * (maxMs - minMs + 1)) + minMs;
}

function sendProgress(text) {
  // Send to popup if open
  chrome.runtime.sendMessage({ type: "progress", text }).catch(() => {
    // Popup may not be open, ignore
  });
}

function getAllAlarms() {
  return new Promise(function (resolve) {
    chrome.alarms.getAll(function (alarms) {
      resolve(Array.isArray(alarms) ? alarms : []);
    });
  });
}

function mergeArticleFetchWork(normalWork, extraWork, mode) {
  var result = [];
  var seen = new Set();
  var normal = normalWork || [];
  for (var i = 0; i < normal.length; i++) {
    var normalItem = normal[i];
    if (!normalItem || !normalItem.article_id || seen.has(normalItem.article_id)) continue;
    seen.add(normalItem.article_id);
    result.push(normalItem);
  }

  var cap = RECONCILIATION_ENRICHMENT_LIMITS[mode] || 4;
  var added = 0;
  var extra = extraWork || [];
  for (var j = 0; j < extra.length; j++) {
    if (added >= cap) break;
    var extraItem = extra[j];
    if (!extraItem || !extraItem.article_id || seen.has(extraItem.article_id)) continue;
    seen.add(extraItem.article_id);
    result.push(extraItem);
    added++;
  }
  return result;
}

function normalizeManualFetchItem(item) {
  if (!item || typeof item !== "object") return null;
  var symbol = String(item.symbol || "").trim().toUpperCase();
  var role = item.role;
  var anchor = String(item.event_anchor_date || "").trim();
  if (!/^[A-Z][A-Z.]{0,9}$/.test(symbol)) return null;
  if (role !== "entry" && role !== "exit") return null;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(anchor)) return null;
  var parsedDate = new Date(anchor + "T00:00:00Z");
  if (isNaN(parsedDate.getTime()) || parsedDate.toISOString().slice(0, 10) !== anchor) {
    return null;
  }

  var parsedUrl;
  try {
    parsedUrl = new URL(String(item.url || ""));
  } catch (_) {
    return null;
  }
  if (
    parsedUrl.protocol !== "https:" ||
    parsedUrl.hostname !== "seekingalpha.com" ||
    parsedUrl.username ||
    parsedUrl.password ||
    parsedUrl.search ||
    parsedUrl.hash
  ) {
    return null;
  }
  var idMatch = parsedUrl.pathname.match(
    /^\/alpha-picks\/articles\/(\d+)(?:-[^/]+)?\/?$/
  );
  if (!idMatch) return null;

  var lineageId = Number(item.lineage_id);
  if (item.lineage_id != null && (!Number.isInteger(lineageId) || lineageId <= 0)) {
    return null;
  }
  var replaceLinkId = Number(item.replace_link_id);
  if (
    item.replace_link_id != null &&
    (!Number.isInteger(replaceLinkId) || replaceLinkId <= 0)
  ) {
    return null;
  }
  return {
    symbol: symbol,
    role: role,
    event_anchor_date: anchor,
    url: parsedUrl.href,
    article_id: idMatch[1],
    lineage_id: item.lineage_id == null ? null : lineageId,
    replace_link_id: item.replace_link_id == null ? null : replaceLinkId,
    confirm_warnings: item.confirm_warnings === true,
  };
}

// --- Detail fetch (incremental) ---

async function doDetailFetch(tabId, currentPicks, mode, diagnostics) {
  // ── Step 1: Load articles page + scroll ──
  sendProgress("Loading articles page...");
  await managedSaTabs.update(tabId, { url: SA_ARTICLES_URL });
  await waitForTabLoad(tabId, 30000, expectedPathFromUrl(SA_ARTICLES_URL));

  var articlesReady = await waitForArticlesReady(tabId);
  if (!articlesReady.ok) {
    recordExtensionFailure(diagnostics, {
      stage: "page_readiness",
      reason_code: articlesReady.reason_code || "dom_not_ready",
      target_kind: "phase",
      retryable: true,
      attempt_count: 1,
    });
    return { fetched: 0, failed: 0, error: articlesReady.error };
  }

  // Scroll: activate tab for IntersectionObserver
  var scrollMode = mode;
  await chrome.tabs.update(tabId, { active: true });
  await sleep(500);
  if (mode === "full" || mode === "backfill") {
    sendProgress(mode === "backfill"
      ? "Deep backfill: loading all articles..."
      : "Full scan: loading all articles...");
    await scrollToLoadAll(tabId, ALPHA_PICKS_ARTICLE_LIST_ROUNDS[mode]);
  } else {
    sendProgress("Loading recent articles...");
    await scrollToLoadAll(tabId, ALPHA_PICKS_ARTICLE_LIST_ROUNDS.quick);
  }
  await chrome.tabs.update(tabId, { active: false });

  // Scrape article list (ALL articles, not just ticker-tagged)
  sendProgress("Scraping article list...");
  var articleList = await injectArticlesListScraper(tabId);
  if (!articleList || articleList.error) {
    recordExtensionFailure(diagnostics, {
      stage: "content_parse",
      reason_code: "parser_empty",
      target_kind: "phase",
      retryable: true,
      attempt_count: 1,
    });
    return { fetched: 0, failed: 0, error: articleList ? articleList.error : "No articles found" };
  }
  if (!Array.isArray(articleList) || articleList.length === 0) {
    recordExtensionFailure(diagnostics, {
      stage: "content_parse",
      reason_code: "parser_empty",
      target_kind: "phase",
      retryable: true,
      attempt_count: 1,
    });
    return { fetched: 0, failed: 0, error: "Empty article list" };
  }

  // ── Step 2: Save articles metadata → get need_content + need_comments ──
  sendProgress("Saving " + articleList.length + " articles metadata...");
  var metaResult = await sendNativeMessage2({
    action: "save_articles_meta",
    mode: scrollMode,
    articles: articleList,
  });

  if (!metaResult || metaResult.status !== "ok") {
    recordNativeExtensionFailure(diagnostics, metaResult, "phase", null);
    var metaError = (metaResult && metaResult.error) || "save_articles_meta failed";
    return { fetched: 0, failed: 0, error: metaError };
  }

  var needContent = mergeArticleFetchWork(
    metaResult.need_content || [],
    (metaResult.reconciliation && metaResult.reconciliation.enrichment) || [],
    scrollMode
  );
  var needComments = metaResult.need_comments || [];
  var unresolvedSymbols = metaResult.unresolved_symbols || [];

  // ── Step 3: Fetch article content + comments for need_content ──
  var fetched = 0, failed = 0, commentsRefreshed = 0;
  var netNewComments = 0;
  var reconciliationFailed = 0;
  if (metaResult.reconciliation && metaResult.reconciliation.status === "failed") {
    reconciliationFailed += recordExtensionFailure(diagnostics, {
      stage: "reconciliation",
      reason_code: "reconciliation_failed",
      target_kind: "phase",
      retryable: true,
      attempt_count: 1,
    });
  }
  var detailIds = new Set(needContent.map(function (item) {return item.article_id;}));
  var work = needContent.map(function (item) {return {item:item,body:true};}).concat(
    needComments.filter(function (item) {return !detailIds.has(item.article_id);})
      .map(function (item) {return {item:item,body:false};}));
  if (mode === "quick" && metaResult.quick_workload) {
    var order = metaResult.quick_workload.selected_article_ids || [];
    work.sort(function (a,b) {return order.indexOf(a.item.article_id) - order.indexOf(b.item.article_id);});
  }
  var total = work.length;
  function stoppedDetails(error) {
    return {articles_saved:metaResult.saved || 0,fetched:fetched,failed:failed,
      comments_refreshed:commentsRefreshed || 0,net_new_comments:netNewComments,
      reconciliation_failed:reconciliationFailed,quick_workload:metaResult.quick_workload || null,
      acquisition_stop:error.detail};
  }

  if (needContent.length > 0) {
    sendProgress("Fetching " + needContent.length + " article(s)...");
  }

  async function fetchBody(item, i) {
    sendProgress("Article " + (i + 1) + "/" + total + ": " + item.article_id);

    try {
      // Navigate to article (tab must be active for comment scroll)
      await managedSaTabs.update(tabId, { url: item.url, active: true });
      await waitForTabLoad(tabId, 30000, expectedPathFromUrl(item.url));
      var ready = await waitForArticleReady(tabId);
      if (!ready.ok) {
        failed += recordExtensionFailure(diagnostics, {
          stage: "page_readiness",
          reason_code: ready.reason_code || "dom_not_ready",
          target_kind: "article_detail",
          target_ref: item.article_id,
          retryable: true,
          attempt_count: 1,
        });
        if (await observeSaRestriction(ready.reason_code)) throw new SAAcquisition.Stop(saAcquisitionTask.stop);
        return;
      }
      var captured = await captureArticle(tabId, item, scrollMode, true);
      var detail = captured.detail;
      if (!detail || detail.error) {
        failed += recordExtensionFailure(diagnostics, {
          stage: "content_parse",
          reason_code: "parser_empty",
          target_kind: "article_detail",
          target_ref: item.article_id,
          retryable: true,
          attempt_count: 1,
        });
        return;
      }

      var bodyScrollStats = captured.scroll;
      var comments = captured.comments;

      var report = formatDetailReport(detail);
      var saveResult = await sendNativeMessage2({
        action: "save_article_content",
        article_id: item.article_id,
        body_markdown: report,
        body_capture: detail.body_capture || null,
        comments: comments,
        detail_ticker: detail.detail_ticker || null,
        detail_ticker_observed_at: detail.detail_ticker_observed_at || null,
        provider_comments_count: item.provider_comments_count,
        comment_scan_mode: bodyScrollStats.mode || scrollMode,
        comment_scan_policy: bodyScrollStats.recency || null,
        comment_scan_stop_reason: bodyScrollStats && bodyScrollStats.stop_reason,
        comment_scan_stable_bottom_rounds:
          (bodyScrollStats && bodyScrollStats.stable_bottom_rounds) || 0,
      });
      if (saveResult && saveResult.ok) netNewComments += saveResult.net_new_comments || 0;
      if (saveResult && saveResult.ok && saveResult.body_saved !== false) {
        fetched++;
        if (saveResult.comment_scan_usable !== true || saveResult.comment_backfill_pending === true
            || bodyScrollStats.controls_unresolved) {
          failed += recordExtensionFailure(diagnostics, {
            stage: "content_parse",
            reason_code: "comment_scan_failed",
            target_kind: "article_comments",
            target_ref: item.article_id,
            retryable: true,
            attempt_count: 1,
          });
        }
        if (
          saveResult.reconciliation &&
          saveResult.reconciliation.status === "failed"
        ) {
          reconciliationFailed += recordExtensionFailure(diagnostics, {
            stage: "reconciliation",
            reason_code: "reconciliation_failed",
            target_kind: "article_detail",
            target_ref: item.article_id,
            retryable: true,
            attempt_count: 1,
          });
        }
      } else if (saveResult && saveResult.body_saved === false) {
        failed += recordExtensionFailure(diagnostics, {
          stage: "content_parse", reason_code: "parser_empty", target_kind: "article_detail",
          target_ref: item.article_id, retryable: true, attempt_count: 1,
        });
      } else {
        failed += recordNativeExtensionFailure(
          diagnostics,
          saveResult,
          "article_detail",
          item.article_id
        );
      }
    } catch (err) {
      if (isAcquisitionStop(err)) return stoppedDetails(err);
      failed += recordExtensionFailure(diagnostics, {
        stage: err.code === "article_context_changed" ? "tab_navigation" : "extension_runtime",
        reason_code: err.code === "article_context_changed" ? err.code : "unknown_failure",
        message: err.evidence ? "Unexpected navigation signals: " + err.evidence.event_count : undefined,
        target_kind: "article_detail",
        target_ref: item.article_id,
        retryable: true,
        attempt_count: 1,
      });
    }
    // No artificial delay — comment scroll provides natural dwell time
  }

  async function fetchComments(cItem, i) {
    sendProgress("Comments " + (i + 1) + "/" + total + ": " + cItem.article_id);

    try {
      await managedSaTabs.update(tabId, { url: cItem.url, active: true });
      await waitForTabLoad(tabId, 30000, expectedPathFromUrl(cItem.url));
      var commentsReady = await waitForArticleReady(tabId);
      if (!commentsReady.ok) {
        failed += recordExtensionFailure(diagnostics, {
          stage: "page_readiness",
          reason_code: commentsReady.reason_code || "dom_not_ready",
          target_kind: "article_comments",
          target_ref: cItem.article_id,
          retryable: true,
          attempt_count: 1,
        });
        if (await observeSaRestriction(commentsReady.reason_code)) throw new SAAcquisition.Stop(saAcquisitionTask.stop);
        return;
      }
      var commentCapture = await captureArticle(tabId, cItem, scrollMode, false);
      var commentScrollStats = commentCapture.scroll;
      var cComments = commentCapture.comments;

      var saveCommentsOnlyResult = await sendNativeMessage2({
        action: "save_comments_only",
        article_id: cItem.article_id,
        comments: cComments,
        provider_comments_count: cItem.provider_comments_count,
        comment_scan_mode: commentScrollStats.mode || scrollMode,
        comment_scan_policy: commentScrollStats.recency || null,
        comment_scan_stop_reason:
          commentScrollStats && commentScrollStats.stop_reason,
        comment_scan_stable_bottom_rounds:
          (commentScrollStats && commentScrollStats.stable_bottom_rounds) || 0,
      });
      if (saveCommentsOnlyResult && saveCommentsOnlyResult.status === "ok") {
        netNewComments += saveCommentsOnlyResult.net_new_comments || 0;
        if (saveCommentsOnlyResult.comment_scan_usable === true
            && saveCommentsOnlyResult.comment_backfill_pending !== true && !commentScrollStats.controls_unresolved) {
          commentsRefreshed++;
        } else {
          failed += recordExtensionFailure(diagnostics, {
            stage: "content_parse",
            reason_code: "comment_scan_failed",
            target_kind: "article_comments",
            target_ref: cItem.article_id,
            retryable: true,
            attempt_count: 1,
          });
        }
      } else {
        failed += recordNativeExtensionFailure(
          diagnostics,
          saveCommentsOnlyResult,
          "article_comments",
          cItem.article_id
        );
      }
    } catch (err) {
      if (isAcquisitionStop(err)) return stoppedDetails(err);
      failed += recordExtensionFailure(diagnostics, {
        stage: err.code === "article_context_changed" ? "tab_navigation" : "extension_runtime",
        reason_code: err.code === "article_context_changed" ? err.code : "unknown_failure",
        message: err.evidence ? "Unexpected navigation signals: " + err.evidence.event_count : undefined,
        target_kind: "article_comments",
        target_ref: cItem.article_id,
        retryable: true,
        attempt_count: 1,
      });
    }
  }

  for (var i = 0; i < work.length; i++) {
    var stopped = await (work[i].body ? fetchBody(work[i].item,i) : fetchComments(work[i].item,i));
    if (stopped) return stopped;
  }

  // ── Step 5: Read the event-scoped review queue ──
  sendProgress("Loading article review queue...");
  var auditResult = await sendNativeMessage2({ action: "audit_unresolved" });
  var reviewRequired = 0;
  if (auditResult && auditResult.status === "ok") {
    unresolvedSymbols = auditResult.unresolved_symbols || [];
    reviewRequired =
      auditResult.review_queue && Number.isInteger(auditResult.review_queue.total)
        ? auditResult.review_queue.total
        : unresolvedSymbols.length;
  }

  return {
    articles_saved: metaResult.saved || 0,
    fetched: fetched,
    failed: failed,
    comments_refreshed: commentsRefreshed,
    net_new_comments: netNewComments,
    unresolved_symbols: unresolvedSymbols,
    review_required: reviewRequired,
    reconciliation_failed: reconciliationFailed,
    quick_workload: metaResult.quick_workload || null,
  };
}

// --- Manual fetch (user-provided URLs for missing tickers) ---

async function doManualFetch(items, diagnostics) {
  if (items.length === 0) return { fetched: 0, failed: 0 };

  var tabId = null;
  var fetched = 0, failed = 0;
  var accepted = 0;
  var confirmations = [];
  var prepared = [];

  for (var p = 0; p < items.length; p++) {
    var normalized = normalizeManualFetchItem(items[p]);
    if (!normalized) {
      failed += recordExtensionFailure(diagnostics, {
        stage: "extension_runtime",
        reason_code: "unknown_failure",
        target_kind: "phase",
        retryable: false,
        attempt_count: 1,
      });
      continue;
    }
    if (normalized.lineage_id == null) {
      var resolution = await sendNativeMessage2({
        action: "resolve_reconciliation_event",
        symbol: normalized.symbol,
        role: normalized.role,
        event_anchor_date: normalized.event_anchor_date,
      });
      if (!resolution || resolution.status !== "ok" || !resolution.lineage_id) {
        failed += recordExtensionFailure(diagnostics, {
          stage: "reconciliation",
          reason_code: "reconciliation_failed",
          target_kind: "phase",
          target_ref: normalized.symbol,
          retryable: true,
          attempt_count: 1,
        });
        continue;
      }
      normalized.lineage_id = resolution.lineage_id;
    }
    prepared.push(normalized);
  }
  if (prepared.length === 0) {
    return { fetched: 0, failed: failed, accepted: 0, confirmation_required: [] };
  }

  try {
    await cleanupCollectorTabs({ force: true });
    // Create a tab for fetching
    var tab = await managedSaTabs.create({ url: prepared[0].url, active: false });
    tabId = tab.id;
    await registerCollectorTab(tabId, "manual_fetch");

    for (var i = 0; i < prepared.length; i++) {
      var item = prepared[i];
      sendProgress("Manual: " + item.symbol + " (" + (i + 1) + "/" + prepared.length + ")");

      try {
        if (i > 0) {
          await managedSaTabs.update(tabId, { url: item.url, active: true });
        }
        await waitForTabLoad(tabId, 30000, expectedPathFromUrl(item.url));
        var ready = await waitForArticleReady(tabId);
        if (!ready.ok) {
          failed += recordExtensionFailure(diagnostics, {
            stage: "page_readiness",
            reason_code: ready.reason_code || "dom_not_ready",
            target_kind: "article_detail",
            target_ref: item.article_id,
            retryable: true,
            attempt_count: 1,
          });
          if (await observeSaRestriction(ready.reason_code)) throw new SAAcquisition.Stop(saAcquisitionTask.stop);
          continue;
        }
        var articleId = item.article_id;
        var captured = await captureArticle(tabId, item, "backfill", true, {scope:"recent"});
        var detail = captured.detail;
        if (!detail || detail.error) {
          failed += recordExtensionFailure(diagnostics, {
            stage: "content_parse",
            reason_code: "parser_empty",
            target_kind: "article_detail",
            target_ref: item.article_id,
            retryable: true,
            attempt_count: 1,
          });
          continue;
        }

        var manualScrollStats = captured.scroll;
        var comments = captured.comments;

        var report = formatDetailReport(detail);

        var pubDate = detail.publish_date || null;
        var manualMetaResult = await sendNativeMessage2({
          action: "save_articles_meta",
          mode: "full",
          articles: [{
            article_id: articleId,
            url: item.url,
            title: detail.title || "Alpha Picks article " + articleId,
            date: pubDate,
            article_type: "analysis",
          }],
        });
        if (!manualMetaResult || manualMetaResult.status !== "ok") {
          recordNativeExtensionFailure(
            diagnostics,
            manualMetaResult,
            "article_detail",
            articleId
          );
        }
        var saveResult = await sendNativeMessage2({
          action: "save_article_content",
          article_id: articleId,
          body_markdown: report,
          body_capture: detail.body_capture || null,
          comments: comments,
          detail_ticker: detail.detail_ticker || null,
          detail_ticker_observed_at: detail.detail_ticker_observed_at || null,
          provider_comments_count: null,
          comment_scan_mode: manualScrollStats.mode || "backfill",
          comment_scan_policy: manualScrollStats.recency || null,
          comment_scan_stop_reason:
            manualScrollStats && manualScrollStats.stop_reason,
          comment_scan_stable_bottom_rounds:
            (manualScrollStats && manualScrollStats.stable_bottom_rounds) || 0,
        });
        if (saveResult && saveResult.ok && saveResult.body_saved !== false) {
          fetched++;
          if (saveResult.comment_scan_usable !== true || saveResult.comment_backfill_pending === true
              || manualScrollStats.controls_unresolved) {
            failed += recordExtensionFailure(diagnostics, {
              stage: "content_parse",
              reason_code: "comment_scan_failed",
              target_kind: "article_comments",
              target_ref: articleId,
              retryable: true,
              attempt_count: 1,
            });
          }
          var acceptResult = await sendNativeMessage2({
            action: "accept_reconciliation_link",
            lineage_id: item.lineage_id,
            role: item.role,
            event_anchor_date: item.event_anchor_date,
            article_id: articleId,
            article_url: item.url,
            replace_link_id: item.replace_link_id,
            confirm_warnings: item.confirm_warnings,
          });
          if (acceptResult && acceptResult.status === "ok") {
            accepted++;
          } else if (acceptResult && acceptResult.status === "confirmation_required") {
            confirmations.push({
              symbol: item.symbol,
              role: item.role,
              event_anchor_date: item.event_anchor_date,
              url: item.url,
              article_id: articleId,
              lineage_id: item.lineage_id,
              replace_link_id: item.replace_link_id,
              warnings: acceptResult.warnings || [],
              candidate: acceptResult.candidate || null,
            });
          } else {
            failed += recordExtensionFailure(diagnostics, {
              stage: "reconciliation",
              reason_code: "reconciliation_failed",
              target_kind: "article_detail",
              target_ref: articleId,
              retryable: true,
              attempt_count: 1,
            });
          }
        } else if (saveResult && saveResult.body_saved === false) {
          failed += recordExtensionFailure(diagnostics, {
            stage: "content_parse", reason_code: "parser_empty", target_kind: "article_detail",
            target_ref: articleId, retryable: true, attempt_count: 1,
          });
        } else {
          failed += recordNativeExtensionFailure(
            diagnostics,
            saveResult,
            "article_detail",
            articleId
          );
        }
      } catch (err) {
        if (isAcquisitionStop(err)) return {fetched:fetched,failed:failed,accepted:accepted,
          confirmation_required:confirmations,acquisition_stop:err.detail};
        failed += recordExtensionFailure(diagnostics, {
          stage: err.code === "article_context_changed" ? "tab_navigation" : "extension_runtime",
          reason_code: err.code === "article_context_changed" ? err.code : "unknown_failure",
          message: err.evidence ? "Unexpected navigation signals: " + err.evidence.event_count : undefined,
          target_kind: "article_detail",
          target_ref: item.article_id,
          retryable: true,
          attempt_count: 1,
        });
      }
    }

    sendProgress("Manual fetch done: " + fetched + " saved");

    return {
      fetched: fetched,
      failed: failed,
      accepted: accepted,
      confirmation_required: confirmations,
    };
  } finally {
    if (tabId) {
      await safeRemoveTab(tabId);
      await unregisterCollectorTab(tabId);
    }
  }
}

async function scrollToLoadAll(tabId, maxScrolls) {
  maxScrolls = maxScrolls || 40;
  var staleCount = 0; // Count consecutive scrolls with no new content

  for (var i = 0; i < maxScrolls; i++) {
    // Record current article count + scroll down by one viewport height
    var before = await chrome.scripting.executeScript({
      target: { tabId },
      func: function () {
        var count = document.querySelectorAll('a[href*="/alpha-picks/articles/"]').length;
        // Incremental scroll: one viewport at a time (triggers IntersectionObserver)
        window.scrollBy(0, window.innerHeight);
        return count;
      },
    });
    var prevCount = before[0] && before[0].result || 0;

    // Wait for new content to load (SA infinite scroll can be slow)
    await sleep(2500);

    // Check if new content appeared
    var after = await chrome.scripting.executeScript({
      target: { tabId },
      func: function () {
        return document.querySelectorAll('a[href*="/alpha-picks/articles/"]').length;
      },
    });
    var newCount = after[0] && after[0].result || 0;

    sendProgress("Loading articles... (" + newCount + " links, scroll " + (i + 1) + ")");

    if (newCount <= prevCount) {
      staleCount++;
      // Allow 2 retries before giving up (content may load slowly)
      if (staleCount >= 3) break;
    } else {
      staleCount = 0;
    }
  }
}

function getCommentScrollProfile(mode) {
  return COMMENT_SCROLL_PROFILES[mode] || COMMENT_SCROLL_PROFILES.quick;
}

async function beginArticleCapture(tabId, item) {
  var token = crypto.randomUUID();
  var watch = SACommentCapture.watchNavigation(chrome.tabs, tabId, item.url);
  async function probe(phase, detailUrl) {
    watch.assert();
    var options = {phase:phase,token:token,articleId:item.article_id};
    if (detailUrl !== undefined) options.detailUrl = detailUrl;
    var results = await chrome.scripting.executeScript({target:{tabId:tabId},
      func:SACommentCapture.documentState,
      args:[options],
    });
    watch.assert();
    if (!results[0] || !results[0].result || !results[0].result.ok) throw SACommentCapture.contextError();
  }
  try {await probe('begin');} catch (error) {watch.close(); throw error;}
  return {
    token:token,
    assert:function (detailUrl) {return probe('check', detailUrl);},
    checkNavigation:watch.assert,
    evidence:watch.evidence,
    close:async function () {
      watch.close();
      try {
        await chrome.scripting.executeScript({target:{tabId:tabId},func:SACommentCapture.documentState,
          args:[{phase:'end',token:token,articleId:item.article_id}]});
      } catch (_) { /* The tab may have closed or navigated away. */ }
    },
  };
}

async function captureArticle(tabId, item, mode, includeBody, options) {
  options = options || {};
  var scope = options.scope || item.comment_scan_scope || (mode === "backfill" ? "history" : "recent");
  var referenceMs = Date.now();
  // The backend selects first/pending article work independently of the job mode.
  if (item.comment_scan_mode === "backfill") mode = "backfill";
  var guard = await beginArticleCapture(tabId, item);
  var audits = [];
  try {
    await settleArticleBeforeScroll(tabId);
    await guard.assert();
    var detail = includeBody ? await injectDetailScraper(tabId) : null;
    await guard.assert(detail && !detail.error ? detail.url || null : undefined);
    if (includeBody && (!detail || detail.error)) return {detail:detail};
    await injectCommentsScraper(tabId);
    await guard.assert();
    var scroll = await scrollToComments(tabId, {mode:mode,articleId:item.article_id,
      scope:scope,nowMs:referenceMs,guard:guard,strategy:options.strategy,trace:options.trace,audits:audits});
    await guard.assert();
    var result = await injectCommentsScraper(tabId);
    await guard.assert();
    var selection = SACommentCapture.commentPolicy(result.comments || [],scope,referenceMs);
    selection.summary.deferred_historical_controls = scroll.deferred_historical_controls || 0;
    scroll.recency = selection.summary;
    // Only serialized, verified data crosses this boundary; cleanup and later
    // persistence never read the page again, so they need no live-tab lease.
    return {detail:detail,comments:selection.comments,scroll:scroll,
      navigation:guard.evidence ? guard.evidence() : null};
  } catch (error) {
    if (options.trace) error.capture_trace = {control_audits:audits,
      navigation:guard.evidence ? guard.evidence() : null};
    throw error;
  } finally {await guard.close();}
}

async function settleArticleBeforeScroll(tabId) {
  await chrome.scripting.executeScript({
    target: { tabId },
    func: function () {
      window.scrollTo(0, 0);
    },
  });
  await sleep(ARTICLE_INITIAL_SETTLE_MS);
}

async function scrollToComments(tabId, options) {
  // SA comments are lazy-loaded by scrolling — they appear inside
  // paywall-full-content as div.border-t-share-separator-thin elements.
  // Scroll incrementally to trigger loading, but never let one article
  // monopolize the whole refresh. Hard caps prevent hangs; stale detection
  // exits early when the DOM stops growing.
  options = options || {};
  var profile = getCommentScrollProfile(options.mode);
  var startedAt = Date.now();
  var bestCount = 0;
  var rounds = 0;
  var stableBottomRounds = 0;
  var stopReason = "max_scrolls";
  var audits = options.audits || [], unresolved = false;
  var lastObservation = null;
  var deferredHistorical = 0;

  for (var i = 0; i < profile.maxScrolls; i++) {
    if (options.guard) options.guard.checkNavigation();
    if ((Date.now() - startedAt) >= profile.maxDurationMs) {
      stopReason = "timeout";
      break;
    }
    var result = await chrome.scripting.executeScript({
      target: { tabId },
      func: SACommentCapture.scanPage,
      args: [{strategy: options.strategy || "guarded", token:options.guard && options.guard.token,
        scope:options.scope,nowMs:options.nowMs,deadlineMs:startedAt + profile.maxDurationMs}],
    });
    var check = result[0] && result[0].result;
    if (check && check.recency) deferredHistorical = check.recency.deferred_historical_controls;
    if (check) lastObservation = {
      elapsed_ms: Date.now() - startedAt, comments: check.comments,
      at_bottom: typeof check.atBottom === "boolean" ? check.atBottom : null,
      loading: Boolean(check.loading), click_count: check.click_count || 0,
      traversal_steps:check.traversal_steps || 0,render_wait_incomplete:Boolean(check.render_wait_incomplete),
      progress: check.progress || null,
    };
    if (check && check.control_audit) {
      var audit = check.control_audit;
      if (options.trace) audits.push(Object.assign({round:i + 1,audit:audit}, lastObservation));
      if (audit.unresolved_candidates > 0) unresolved = true;
    }
    if (options.guard) options.guard.checkNavigation();
    if (check && check.page_changed) throw SACommentCapture.contextError();
    rounds++;

    var grew = Boolean(check && check.comments > bestCount);
    if (grew) {
      bestCount = check.comments;
    }

    if (check && check.atBottom && !grew && !check.clicked && !check.loading) {
      stableBottomRounds++;
      if (stableBottomRounds >= profile.staleRounds) {
        stopReason = "stable_bottom";
        break;
      }
    } else {
      stableBottomRounds = 0;
    }

    await sleep(profile.settleMs);
  }

  var stats = {
    mode: profile.name,
    article_id: options.articleId || null,
    comments_loaded: bestCount,
    rounds: rounds,
    elapsed_ms: Date.now() - startedAt,
    stop_reason: unresolved ? "controls_unresolved" : stopReason,
    stable_bottom_rounds: stableBottomRounds,
    controls_unresolved:unresolved,
    deferred_historical_controls:deferredHistorical,
    last_observation:lastObservation,
  };
  console.info("[SA] scrollToComments", JSON.stringify(stats));
  if (options.trace) stats.control_audits = audits;
  return stats;
}


async function waitForMarketNewsReady(tabId, timeoutMs) {
  timeoutMs = timeoutMs || 20000;
  var start = Date.now();
  while (Date.now() - start < timeoutMs) {
    await inspectSaAccess(tabId);
    var results = await chrome.scripting.executeScript({
      target: { tabId },
      func: function () {
        if (location.href.includes("/login") || location.href.includes("/sign_in")) {
          return { status: "login_redirect" };
        }
        var text = document.body ? document.body.innerText : "";
        var links = document.querySelectorAll('a[href*="/news/"]');
        if (links.length >= 3) return { status: "ready", count: links.length };
        if (text.length > 1000 && links.length > 0) return { status: "ready", count: links.length };
        return { status: "loading", count: links.length };
      },
    });
    var check = results[0] && results[0].result;
    if (!check) return {ok:false,error:"Page readiness unavailable",reason_code:"dom_not_ready"};
    if (check.status === "login_redirect") {
      await observeSaRestriction("login_required");
      return { ok: false, error: "Session expired", reason_code: "login_required" };
    }
    if (check.status === "ready") return { ok: true, count: check.count };
    await sleep(500);
  }
  return {
    ok: false,
    error: "Timeout waiting for market news",
    reason_code: "navigation_timeout",
  };
}

async function waitForMarketNewsDetailReady(tabId, timeoutMs) {
  timeoutMs = timeoutMs || 15000;
  var start = Date.now();
  while (Date.now() - start < timeoutMs) {
    await inspectSaAccess(tabId);
    var results = await chrome.scripting.executeScript({
      target: { tabId },
      func: function (paywallMarkers) {
        if (location.href.includes("/login") || location.href.includes("/sign_in")) {
          return { status: "login_redirect" };
        }
        var navigation = typeof performance !== "undefined" &&
          typeof performance.getEntriesByType === "function"
          ? performance.getEntriesByType("navigation")[0]
          : null;
        var responseStatus = navigation && Number(navigation.responseStatus);
        if (responseStatus === 404 || responseStatus === 410) {
          return { status: "source_unavailable", response_status: responseStatus };
        }
        if (document.querySelector(
          '[data-test-id="content-removed"], [data-testid="content-removed"]'
        )) {
          return { status: "source_removed" };
        }
        var text = document.body ? document.body.innerText : "";
        for (var i = 0; i < paywallMarkers.length; i++) {
          if (text.includes(paywallMarkers[i])) {
            return { status: "paywall", marker: paywallMarkers[i] };
          }
        }
        var article = document.querySelector("article") || document.querySelector("main");
        var hasTitle = !!document.querySelector("h1");
        if (article && article.innerText.trim().length > 120 && hasTitle) {
          return { status: "ready" };
        }
        return { status: "loading" };
      },
      args: [PAYWALL_MARKERS],
    });
    var check = results[0] && results[0].result;
    if (!check) return {ok:false,error:"Page readiness unavailable",reason_code:"dom_not_ready"};
    if (check.status === "login_redirect") {
      await observeSaRestriction("login_required");
      return { ok: false, error: "Session expired", reason_code: "login_required" };
    }
    if (check.status === "source_unavailable") {
      return {
        ok: false,
        unavailable_at_source: true,
        reason_code: check.response_status === 410 ? "source_http_410" : "source_http_404",
        evidence_code: check.response_status === 410 ? "http_410" : "http_404",
      };
    }
    if (check.status === "source_removed") {
      return {
        ok: false,
        unavailable_at_source: true,
        reason_code: "source_removed_marker",
        evidence_code: "source_removed",
      };
    }
    if (check.status === "paywall") {
      await observeSaRestriction("access_restricted");
      return {
        ok: false,
        error: "Paywall: " + check.marker,
        reason_code: "access_restricted",
      };
    }
    if (check.status === "ready") return { ok: true };
    await sleep(500);
  }
  return {
    ok: false,
    error: "Timeout waiting for market news detail",
    reason_code: "detail_timeout",
  };
}

async function fetchMarketNewsDetailWithRetry(tabId, item, profile) {
  var lastReasonCode = "unknown_failure";
  var lastNativeFailure = null;
  for (var attempt = 0; attempt < 2; attempt++) {
    requireAcquisitionTask();
    if (attempt > 0) {
      sendProgress("Retrying news detail: " + item.news_id);
      await managedSaTabs.reload(tabId);
      await waitForTabLoad(tabId, 30000, expectedPathFromUrl(item.url));
      await installMarketNewsPageGuards(tabId);
      await sleep(randomBetween(profile.retryDelayMinMs, profile.retryDelayMaxMs));
    }

    var detailReady = await waitForMarketNewsDetailReady(tabId);
    if (!detailReady.ok) {
      if (await observeSaRestriction(detailReady.reason_code)) throw new SAAcquisition.Stop(saAcquisitionTask.stop);
      if (detailReady.unavailable_at_source === true) {
        return {
          ok: false,
          state: "unavailable_at_source",
          reason_code: detailReady.reason_code,
          evidence_code: detailReady.evidence_code,
        };
      }
      lastReasonCode = stableExtensionReason(
        detailReady.reason_code,
        EXTENSION_ITEM_RETRYABLE_REASONS,
        "unknown_failure"
      );
      continue;
    }

    await sleep(randomBetween(
      profile.detailReadyDwellMinMs,
      profile.detailReadyDwellMaxMs
    ));

    var detail = await injectDetailScraper(tabId);
    if (!detail || detail.error) {
      lastReasonCode = "parser_empty";
      continue;
    }

    var report = formatDetailReport(detail);
    if (!report || report.trim().length < 40) {
      lastReasonCode = "parser_empty";
      continue;
    }

    var saveDetail = await sendNativeMessage2({
      action: "save_market_news_detail",
      news_id: item.news_id,
      body_markdown: report,
    });
    if (saveDetail && saveDetail.ok) {
      return { ok: true };
    }
    lastReasonCode = "detail_save_failed";
    lastNativeFailure = saveDetail;
  }
  return {
    ok: false,
    reason_code: lastReasonCode,
    native_failure: lastNativeFailure,
  };
}

async function installMarketNewsPageGuards(tabId) {
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      func: function () {
        if (window.__mindfulrlMarketNewsGuardInstalled) return;
        window.__mindfulrlMarketNewsGuardInstalled = true;

        var blocked = [
          /please check back later/i,
          /content error/i,
          /something went wrong/i,
          /temporarily unavailable/i,
        ];

        function shouldSuppress(text) {
          if (!text) return false;
          for (var i = 0; i < blocked.length; i++) {
            if (blocked[i].test(text)) return true;
          }
          return false;
        }

        window.alert = function () {};
        window.confirm = function () { return false; };
        window.prompt = function () { return null; };

        function hideErrorOverlays() {
          var nodes = document.querySelectorAll(
            '[role=\"dialog\"], [aria-live], [aria-modal=\"true\"], .toast, .snackbar, .modal, .popup'
          );
          for (var i = 0; i < nodes.length; i++) {
            var node = nodes[i];
            var text = (node.innerText || node.textContent || '').trim();
            if (!shouldSuppress(text)) continue;
            node.style.setProperty('display', 'none', 'important');
            node.style.setProperty('visibility', 'hidden', 'important');
            node.setAttribute('data-mindfulrl-hidden', 'true');
          }
        }

        hideErrorOverlays();
        var observer = new MutationObserver(function () {
          hideErrorOverlays();
        });
        observer.observe(document.documentElement || document.body, {
          subtree: true,
          childList: true,
          attributes: false,
        });
      },
    });
  } catch (_) {
    // Best-effort guard only.
  }
}

function getContiguousKnownTailCount(ids, knownIdSet) {
  if (!ids || ids.length === 0 || !knownIdSet || knownIdSet.size === 0) return 0;
  var count = 0;
  for (var i = ids.length - 1; i >= 0; i--) {
    var id = ids[i];
    if (!id || !knownIdSet.has(id)) break;
    count++;
  }
  return count;
}

async function getMarketNewsRecentIds(limit) {
  var result = await sendNativeMessage2({
    action: "get_market_news_recent_ids",
    limit: limit || 200,
  });
  if (!result || result.status !== "ok" || !Array.isArray(result.news_ids)) {
    return [];
  }
  return result.news_ids;
}

async function scrollMarketNews(tabId, maxScrolls, knownNewsIds) {
  var profile = maxScrolls || getMarketNewsProfile("quick");
  var maxRounds = profile.listScrolls || 3;
  var staleCount = 0;
  var knownIdSet = new Set(Array.isArray(knownNewsIds) ? knownNewsIds : []);
  for (var i = 0; i < maxRounds; i++) {
    var before = await chrome.scripting.executeScript({
      target: { tabId },
      func: function () {
        var anchors = document.querySelectorAll('a[href*="/news/"]');
        var ids = [];
        var seen = {};
        for (var n = 0; n < anchors.length; n++) {
          var href = anchors[n].getAttribute("href") || anchors[n].href || "";
          var match = href.match(/\/news\/(\d+)/);
          if (!match || seen[match[1]]) continue;
          seen[match[1]] = true;
          ids.push(match[1]);
        }
        window.scrollBy(0, window.innerHeight);
        return { count: ids.length, ids: ids };
      },
    });
    var beforeResult = before[0] && before[0].result || {};
    var prevCount = beforeResult.count || 0;
    await sleep(randomBetween(profile.listScrollSettleMinMs, profile.listScrollSettleMaxMs));
    var after = await chrome.scripting.executeScript({
      target: { tabId },
      func: function () {
        var anchors = document.querySelectorAll('a[href*="/news/"]');
        var ids = [];
        var seen = {};
        for (var n = 0; n < anchors.length; n++) {
          var href = anchors[n].getAttribute("href") || anchors[n].href || "";
          var match = href.match(/\/news\/(\d+)/);
          if (!match || seen[match[1]]) continue;
          seen[match[1]] = true;
          ids.push(match[1]);
        }
        return { count: ids.length, ids: ids };
      },
    });
    var afterResult = after[0] && after[0].result || {};
    var newCount = afterResult.count || 0;
    var knownTail = getContiguousKnownTailCount(afterResult.ids || [], knownIdSet);
    sendProgress("Loading market news... (" + newCount + " links, scroll " + (i + 1) + ", known tail " + knownTail + ")");
    if (knownTail >= (profile.knownTailStopCount || 8)) {
      break;
    }
    if (newCount <= prevCount) {
      staleCount++;
      if (staleCount >= 2) break;
    } else {
      staleCount = 0;
    }
  }
}

function injectMarketNewsScraper(tabId) {
  return chrome.scripting
    .executeScript({ target: { tabId }, files: ["scrape_market_news.js"] })
    .then(function (results) {
      return (results[0] && results[0].result) || [];
    });
}

async function waitForArticlesReady(tabId, timeoutMs) {
  timeoutMs = timeoutMs || 20000;
  var start = Date.now();
  while (Date.now() - start < timeoutMs) {
    await inspectSaAccess(tabId);
    var results = await chrome.scripting.executeScript({
      target: { tabId },
      func: function () {
        if (location.href.includes("/login") || location.href.includes("/sign_in"))
          return { status: "login_redirect" };
        var links = document.querySelectorAll('a[href*="/alpha-picks/articles/"]');
        if (links.length >= 3) return { status: "ready", count: links.length };
        return { status: "loading" };
      },
    });
    var check = results[0] && results[0].result;
    if (!check) return {ok:false,error:"Page readiness unavailable",reason_code:"dom_not_ready"};
    if (check.status === "login_redirect") {
      await observeSaRestriction("login_required");
      return { ok: false, error: "Session expired", reason_code: "login_required" };
    }
    if (check.status === "ready") return { ok: true };
    await sleep(500);
  }
  return {
    ok: false,
    error: "Timeout waiting for articles page",
    reason_code: "navigation_timeout",
  };
}

function injectArticlesListScraper(tabId) {
  return chrome.scripting
    .executeScript({
      target: { tabId },
      files: ["article_identity.js", "scrape_articles_list.js"],
    })
    .then(function (results) {
      return (results[0] && results[0].result) || { error: "No result" };
    });
}

async function waitForArticleReady(tabId, timeoutMs) {
  timeoutMs = timeoutMs || 15000;
  var start = Date.now();
  while (Date.now() - start < timeoutMs) {
    await inspectSaAccess(tabId);
    var results = await chrome.scripting.executeScript({
      target: { tabId },
      func: function (paywallMarkers) {
        if (location.href.includes("/login") || location.href.includes("/sign_in"))
          return { status: "login_redirect" };
        var text = document.body ? document.body.innerText : "";
        for (var i = 0; i < paywallMarkers.length; i++) {
          if (text.includes(paywallMarkers[i])) return { status: "paywall", marker: paywallMarkers[i] };
        }
        // Article ready when content > 500 chars
        var article = document.querySelector("article") || document.querySelector("main");
        if (article && article.innerText.trim().length > 500) return { status: "ready" };
        return { status: "loading" };
      },
      args: [PAYWALL_MARKERS],
    });
    var check = results[0] && results[0].result;
    if (!check) return {ok:false,error:"Page readiness unavailable",reason_code:"dom_not_ready"};
    if (check.status === "login_redirect") {
      await observeSaRestriction("login_required");
      return { ok: false, error: "Session expired", reason_code: "login_required" };
    }
    if (check.status === "paywall") {
      await observeSaRestriction("access_restricted");
      return {
        ok: false,
        error: "Paywall: " + check.marker,
        reason_code: "access_restricted",
      };
    }
    if (check.status === "ready") return { ok: true };
    await sleep(500);
  }
  return {
    ok: false,
    error: "Timeout waiting for article",
    reason_code: "detail_timeout",
  };
}

function injectDetailScraper(tabId) {
  return chrome.scripting
    .executeScript({
      target: { tabId },
      files: ["article_identity.js", "scrape_detail.js"],
    })
    .then(function (results) {
      return (results[0] && results[0].result) || { error: "No result" };
    });
}

function injectCommentsScraper(tabId) {
  return chrome.scripting
    .executeScript({ target: { tabId }, files: ["comment_capture.js", "scrape_comments.js"] })
    .then(function (results) {
      return (results[0] && results[0].result) || { comments: [] };
    });
}

function formatDetailReport(detail) {
  var parts = [];
  var body = detail.body_markdown || "";
  var normalizedBody = body.trim();
  var normalizedTitleHeading = detail.title ? ("# " + detail.title).trim() : "";
  if (detail.title && (!normalizedBody || !normalizedBody.startsWith(normalizedTitleHeading))) {
    parts.push("# " + detail.title);
  }
  if (detail.author) parts.push("*Author: " + detail.author + "*");
  if (body) parts.push(body);
  return parts.join("\n\n");
}

function sendNativeMessage2(msg) {
  return new Promise(function (resolve) {
    chrome.runtime.sendNativeMessage(NATIVE_HOST, msg, function (response) {
      if (chrome.runtime.lastError) {
        resolve({
          status: "error",
          error: chrome.runtime.lastError.message,
          error_code: "native_host_unavailable",
        });
      } else {
        resolve(response || {
          status: "error",
          error: "No response",
          error_code: "invalid_native_response",
        });
      }
    });
  });
}

// --- Persistence ---

async function saveRefreshState(batchTs, results) {
  await chrome.storage.local.set({
    lastRefresh: {
      batch_ts: batchTs,
      current: results.current,
      closed: results.closed,
      details: results.details || null,
      mode: results.mode || "quick",
      trigger: results.trigger || "manual",
    },
  });
}


async function saveMarketNewsState(batchTs, mode, result) {
  await chrome.storage.local.set({
    lastMarketNewsRefresh: {
      batch_ts: batchTs,
      mode: mode || "quick",
      result: result,
    },
  });
}
