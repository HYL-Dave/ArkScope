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
var saSyncJobChain = Promise.resolve();
var saSyncJobInFlight = false;
var saAutoJobPending = {
  alphaPicks: false,
  marketNews: false,
};

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
  return !!value && typeof value === "object" && (value.status === "ok" || value.ok === true);
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
  var detailFailed = Number(details.failed || 0) > 0 || !!details.error;
  var detailReason = details.error
    ? stableExtensionReason(details.reason_code, EXTENSION_PHASE_FAILURE_REASONS, "article_metadata_failed")
    : stableExtensionReason(details.reason_code, EXTENSION_PHASE_FAILURE_REASONS, "detail_save_failed");
  var reconciliationFailed = Number(details.reconciliation_failed || 0) > 0;

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
        ? extensionPhase("failed", "reconciliation_failed")
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
  var structured;
  if (operation === "alpha_picks_sync") {
    structured = buildAlphaPicksProtocolResult(mode, result);
  } else if (operation === "alpha_picks_manual_fetch") {
    structured = buildAlphaPicksManualProtocolResult(result);
  } else if (operation === "market_news_sync") {
    structured = buildMarketNewsProtocolResult(mode, result);
  } else {
    throw new Error("unsupported extension operation");
  }
  return Object.assign({}, result, { extension_run: structured });
}

// --- Message listener (from popup) ---

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
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

chrome.runtime.onInstalled.addListener(function () {
  cleanupCollectorTabs({ maxAgeMs: COLLECTOR_TAB_STALE_MS });
  syncAllAutoSyncAlarms();
});

chrome.runtime.onStartup.addListener(function () {
  cleanupCollectorTabs({ maxAgeMs: COLLECTOR_TAB_STALE_MS });
  syncAllAutoSyncAlarms();
  extensionTelemetryController.flush("startup");
});

chrome.alarms.onAlarm.addListener(function (alarm) {
  if (!alarm) return;
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

  var run = saSyncJobChain.catch(function () {}).then(async function () {
    await extensionTelemetryController.flush("next_job");
    if (saSyncJobInFlight) {
      sendProgress("Queued: " + displayName);
    }
    saSyncJobInFlight = true;
    var startedAt = new Date().toISOString();
    var diagnostics = SAExtensionDiagnostics.createCollector();
    var capturedResult = null;
    try {
      capturedResult = attachExtensionRunProtocol(operation, mode, await jobFn(diagnostics));
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
      saSyncJobInFlight = false;
      try {
        var frozenDiagnostics = diagnostics.freeze();
        await extensionTelemetryController.submit({
          started_at: startedAt,
          finished_at: new Date().toISOString(),
          result: capturedResult && capturedResult.extension_run,
          extension_diagnostics: frozenDiagnostics,
        });
      } catch (_) {
        // Recording must never break the actual sync flow.
      }
    }
  });
  saSyncJobChain = run.catch(function () {});
  return run;
}

function enqueueAutoSaSyncJob(jobKey, jobOpts, jobFn) {
  if (saAutoJobPending[jobKey]) {
    return Promise.resolve({ status: "skipped", reason: "already_pending" });
  }
  saAutoJobPending[jobKey] = true;
  return enqueueSaSyncJob(jobOpts, async function (diagnostics) {
    try {
      return await jobFn(diagnostics);
    } finally {
      saAutoJobPending[jobKey] = false;
    }
  });
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

function enqueueMarketNewsRecovery(request) {
  var run = saSyncJobChain.catch(function () {}).then(async function () {
    await extensionTelemetryController.flush("next_job");
    saSyncJobInFlight = true;
    marketNewsRefreshInFlight = true;
    try {
      return await executeMarketNewsRecovery(request || {});
    } catch (error) {
      return {
        status: "error",
        error_code: "recovery_runtime_failed",
      };
    } finally {
      marketNewsRefreshInFlight = false;
      saSyncJobInFlight = false;
    }
  });
  saSyncJobChain = run.catch(function () {});
  return run;
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
      var tab = await chrome.tabs.create({ url: initialUrl, active: false });
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
      chrome.tabs.update(tabId, { url: url, active: false }),
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
  } catch (_) {
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

  await chrome.tabs.update(tabId, { url: SA_MARKET_NEWS_URL, active: true });
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

async function doRefresh(mode, options) {
  options = options || {};
  var diagnostics = options.diagnostics;
  const batchTs = new Date().toISOString();
  const results = { current: null, closed: null, mode: mode, trigger: options.trigger || "manual" };

  let tabId = null;
  try {
    await cleanupCollectorTabs({ force: true });
    // --- Scrape current picks ---
    sendProgress("Opening current picks page...");
    const tab = await chrome.tabs.create({ url: SA_CURRENT_URL, active: false });
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
      results.current = await sendToNativeHost("refresh_failure", "current", [], ready.error, batchTs);
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
    await chrome.tabs.update(tabId, { url: SA_CLOSED_URL });

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
      results.closed = await sendToNativeHost("refresh_failure", "closed", [], ready.error, batchTs);
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
    if (results.current && results.current.status === "ok") {
      // Re-read currentPicks from the scrape result stored earlier
      // We need to keep them in scope — move the variable up
      currentPicks = results._currentPicks || [];
    }
    if (currentPicks && currentPicks.length > 0) {
      sendProgress("Checking detail cache...");
      var detailResult = await doDetailFetch(tabId, currentPicks, mode, diagnostics);
      results.details = detailResult;
    }

    await saveRefreshState(batchTs, results);
    sendProgress("Done!");
    return results;
  } catch (err) {
    recordExtensionFailure(diagnostics, {
      stage: "extension_runtime",
      reason_code: "unknown_failure",
      target_kind: "phase",
      retryable: true,
      attempt_count: 1,
    });
    const error = err.message || String(err);
    if (!results.current) {
      results.current = await sendToNativeHost("refresh_failure", "current", [], error, batchTs);
    }
    if (!results.closed) {
      results.closed = await sendToNativeHost("refresh_failure", "closed", [], error, batchTs);
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
    const tab = await chrome.tabs.create({ url: SA_MARKET_NEWS_URL, active: false });
    tabId = tab.id;
    await registerCollectorTab(tabId, "market_news");
    await waitForMarketNewsPageLoad(tabId);

    sendProgress("Waiting for market news...");
    var ready = await waitForMarketNewsReady(tabId);
    if (!ready.ok) {
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
          chrome.tabs.update(tabId, { url: item.url, active: false }),
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

async function setAlphaPicksAutoSyncEnabled(enabled, intervalMinutes) {
  var data = await chrome.storage.local.get(["alphaPicksAutoSyncIntervalMinutes"]);
  var normalizedInterval = normalizeAlphaPicksAutoSyncIntervalMinutes(
    intervalMinutes != null ? intervalMinutes : data.alphaPicksAutoSyncIntervalMinutes
  );
  await chrome.storage.local.set({
    alphaPicksAutoSyncEnabled: enabled,
    alphaPicksAutoSyncIntervalMinutes: normalizedInterval,
  });
  await syncAlphaPicksAutoSyncAlarm();
  return {
    status: "ok",
    enabled: enabled,
    interval_minutes: normalizedInterval,
  };
}

async function setMarketNewsAutoSyncEnabled(enabled, intervalMinutes) {
  var data = await chrome.storage.local.get(["marketNewsAutoSyncIntervalMinutes"]);
  var normalizedInterval = normalizeMarketNewsAutoSyncIntervalMinutes(
    intervalMinutes != null ? intervalMinutes : data.marketNewsAutoSyncIntervalMinutes
  );
  await chrome.storage.local.set({
    marketNewsAutoSyncEnabled: enabled,
    marketNewsAutoSyncIntervalMinutes: normalizedInterval,
    marketNewsAutoSyncLastStartedAt: null,
  });
  await syncMarketNewsAutoSyncAlarm();
  var schedule = getMarketNewsAutoSyncSchedule(normalizedInterval);
  return {
    status: "ok",
    enabled: enabled,
    interval_minutes: schedule.intervalMinutes,
    interval_setting: normalizedInterval,
    interval_label: schedule.label,
  };
}

async function syncAllAutoSyncAlarms() {
  await syncAlphaPicksAutoSyncAlarm();
  await syncMarketNewsAutoSyncAlarm();
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
  if (enabled) {
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
  if (enabled) {
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
      if (
        (changeInfo.status === "complete" || (tab && tab.status === "complete")) &&
        tabMatchesExpectedUrl(tab, expectedUrlFragment)
      ) {
        finish();
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
      if (tab.status === "complete" && tabMatchesExpectedUrl(tab, expectedUrlFragment)) {
        finish();
      }
    }).catch((err) => {
      finish(err || new Error("Failed to inspect tab state"));
    });
  });
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
    firstError = err;
  }

  var firstProbe = await probeMarketNewsListDom(tabId);
  if (firstProbe.status === "ready") {
    console.warn("[SA] Market News tab did not report complete, but DOM is ready:", firstProbe);
    return;
  }
  if (firstProbe.status === "login_redirect") {
    throw new Error("Session expired");
  }

  sendProgress("Retrying market news page load...");
  try {
    await chrome.tabs.reload(tabId);
    await waitForTabLoad(tabId, MARKET_NEWS_RETRY_TAB_LOAD_TIMEOUT_MS, expectedPath);
    return;
  } catch (retryErr) {
    var retryProbe = await probeMarketNewsListDom(tabId);
    if (retryProbe.status === "ready") {
      console.warn("[SA] Market News tab retry did not report complete, but DOM is ready:", retryProbe);
      return;
    }
    if (retryProbe.status === "login_redirect") {
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
    return true;
  } catch (err) {
    var message = err && err.message ? err.message : String(err || "");
    if (message && message.indexOf("No tab with id") >= 0) {
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
  let lastSnapshot = null;
  while (Date.now() - start < timeoutMs) {
    let tab = null;
    try {
      tab = await chrome.tabs.get(tabId);
    } catch (err) {
      lastSnapshot = { scriptError: "tab not found: " + (err && err.message ? err.message : String(err || "")) };
      await sleep(500);
      continue;
    }

    const snapshot = await inspectAlphaPicksReadiness(tabId, expectedPath);
    lastSnapshot = Object.assign({}, snapshot || {}, {
      tabStatus: (tab && tab.status) || "unknown",
      tabUrl: (tab && tab.url) || "",
      pendingUrl: (tab && tab.pendingUrl) || "",
    });

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
  await chrome.tabs.update(tabId, { url: SA_ARTICLES_URL });
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

  // Check auto_upgrade (first run, empty DB — status is "ok" but auto_upgrade=true)
  if (metaResult && metaResult.auto_upgrade && mode === "quick") {
    sendProgress("First run detected, switching to full scan...");
    scrollMode = "full";
    await chrome.tabs.update(tabId, { active: true });
    await sleep(500);
    await scrollToLoadAll(tabId, ALPHA_PICKS_ARTICLE_LIST_ROUNDS.full);
    await chrome.tabs.update(tabId, { active: false });
    // Re-scrape after full scroll
    articleList = await injectArticlesListScraper(tabId);
    if (Array.isArray(articleList) && articleList.length > 0) {
      metaResult = await sendNativeMessage2({
        action: "save_articles_meta",
        mode: "full",
        articles: articleList,
      });
    }
  }

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
  var fetched = 0, failed = 0;
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
  var total = needContent.length + needComments.length;

  if (needContent.length > 0) {
    sendProgress("Fetching " + needContent.length + " article(s)...");
  }

  for (var i = 0; i < needContent.length; i++) {
    var item = needContent[i];
    sendProgress("Article " + (i + 1) + "/" + needContent.length + ": " + item.article_id);

    try {
      // Navigate to article (tab must be active for comment scroll)
      await chrome.tabs.update(tabId, { url: item.url, active: true });
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
        continue;
      }
      await settleArticleBeforeScroll(tabId);

      // Scrape body
      var detail = await injectDetailScraper(tabId);
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

      // Scroll down to comments section + load all comments
      // This naturally provides human-like dwell time (10-30s per page)
      var bodyScrollStats = await scrollToComments(tabId, {
        mode: scrollMode,
        articleId: item.article_id,
      });

      // Scrape comments
      var commentsResult = await injectCommentsScraper(tabId);
      var comments = (commentsResult && commentsResult.comments) || [];

      var report = formatDetailReport(detail);
      var saveResult = await sendNativeMessage2({
        action: "save_article_content",
        article_id: item.article_id,
        body_markdown: report,
        comments: comments,
        detail_ticker: detail.detail_ticker || null,
        detail_ticker_observed_at: detail.detail_ticker_observed_at || null,
        provider_comments_count: item.provider_comments_count,
        comment_scan_mode: scrollMode,
        comment_scan_stop_reason: bodyScrollStats && bodyScrollStats.stop_reason,
        comment_scan_stable_bottom_rounds:
          (bodyScrollStats && bodyScrollStats.stable_bottom_rounds) || 0,
      });
      if (saveResult && saveResult.ok) {
        fetched++;
        netNewComments += saveResult.net_new_comments || 0;
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
      } else {
        failed += recordNativeExtensionFailure(
          diagnostics,
          saveResult,
          "article_detail",
          item.article_id
        );
      }
    } catch (err) {
      failed += recordExtensionFailure(diagnostics, {
        stage: "extension_runtime",
        reason_code: "unknown_failure",
        target_kind: "article_detail",
        target_ref: item.article_id,
        retryable: true,
        attempt_count: 1,
      });
    }
    // No artificial delay — comment scroll provides natural dwell time
  }

  // ── Step 4: Refresh comments for articles flagged by DAL ──
  var commentsRefreshed = 0;
  if (needComments.length > 0) {
    sendProgress("Refreshing comments for " + needComments.length + " article(s)...");
  }
  for (var j = 0; j < needComments.length; j++) {
    var cItem = needComments[j];
    sendProgress("Comments " + (j + 1) + "/" + needComments.length + ": " + cItem.article_id);

    try {
      await chrome.tabs.update(tabId, { url: cItem.url, active: true });
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
        continue;
      }
      await settleArticleBeforeScroll(tabId);

      // Scroll to load comments (natural delay)
      var commentScrollStats = await scrollToComments(tabId, {
        mode: scrollMode,
        articleId: cItem.article_id,
      });

      var cResult = await injectCommentsScraper(tabId);
      var cComments = (cResult && cResult.comments) || [];

      var saveCommentsOnlyResult = await sendNativeMessage2({
        action: "save_comments_only",
        article_id: cItem.article_id,
        comments: cComments,
        provider_comments_count: cItem.provider_comments_count,
        comment_scan_mode: scrollMode,
        comment_scan_stop_reason:
          commentScrollStats && commentScrollStats.stop_reason,
        comment_scan_stable_bottom_rounds:
          (commentScrollStats && commentScrollStats.stable_bottom_rounds) || 0,
      });
      if (saveCommentsOnlyResult && saveCommentsOnlyResult.status === "ok") {
        if (saveCommentsOnlyResult.comment_scan_usable === true) {
          commentsRefreshed++;
          netNewComments += saveCommentsOnlyResult.net_new_comments || 0;
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
      failed += recordExtensionFailure(diagnostics, {
        stage: "extension_runtime",
        reason_code: "unknown_failure",
        target_kind: "article_comments",
        target_ref: cItem.article_id,
        retryable: true,
        attempt_count: 1,
      });
    }
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
    var tab = await chrome.tabs.create({ url: prepared[0].url, active: false });
    tabId = tab.id;
    await registerCollectorTab(tabId, "manual_fetch");

    for (var i = 0; i < prepared.length; i++) {
      var item = prepared[i];
      sendProgress("Manual: " + item.symbol + " (" + (i + 1) + "/" + prepared.length + ")");

      try {
        if (i > 0) {
          await chrome.tabs.update(tabId, { url: item.url, active: true });
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
          continue;
        }
        await settleArticleBeforeScroll(tabId);

        var articleId = item.article_id;

        var detail = await injectDetailScraper(tabId);
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

        // Scroll to load comments (v3 path)
        var manualScrollStats = await scrollToComments(tabId, {
          mode: "manual",
          articleId: articleId,
        });
        var commentsResult = await injectCommentsScraper(tabId);
        var comments = (commentsResult && commentsResult.comments) || [];

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
          comments: comments,
          detail_ticker: detail.detail_ticker || null,
          detail_ticker_observed_at: detail.detail_ticker_observed_at || null,
          provider_comments_count: null,
          comment_scan_mode: "manual",
          comment_scan_stop_reason:
            manualScrollStats && manualScrollStats.stop_reason,
          comment_scan_stable_bottom_rounds:
            (manualScrollStats && manualScrollStats.stable_bottom_rounds) || 0,
        });
        if (saveResult && saveResult.ok) {
          fetched++;
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
        } else {
          failed += recordNativeExtensionFailure(
            diagnostics,
            saveResult,
            "article_detail",
            articleId
          );
        }
      } catch (err) {
        failed += recordExtensionFailure(diagnostics, {
          stage: "extension_runtime",
          reason_code: "unknown_failure",
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

  for (var i = 0; i < profile.maxScrolls; i++) {
    if ((Date.now() - startedAt) >= profile.maxDurationMs) {
      stopReason = "timeout";
      break;
    }
    var result = await chrome.scripting.executeScript({
      target: { tabId },
      func: function () {
        var commentEls = document.querySelectorAll('[class*="border-t-share-separator-thin"]');
        var atBottom = (window.innerHeight + window.scrollY) >= (document.body.scrollHeight - 200);

        // Click "Show more replies/comments" buttons — scoped to bottom half of page
        var pageMiddle = document.body.scrollHeight / 2;
        var buttons = document.querySelectorAll('button, a');
        var clicked = false;
        for (var b = 0; b < buttons.length; b++) {
          var rect = buttons[b].getBoundingClientRect();
          var absTop = rect.top + window.scrollY;
          // Only click buttons in the bottom half (comments area)
          if (absTop < pageMiddle) continue;
          var bt = buttons[b].innerText.trim().toLowerCase();
          if ((bt.indexOf('show') >= 0 || bt.indexOf('load more') >= 0 || bt.indexOf('more repl') >= 0)
              && buttons[b].offsetParent !== null) {
            buttons[b].click();
            clicked = true;
          }
        }

        var loading = false;
        var loadingNodes = document.querySelectorAll(
          '[aria-busy="true"], [role="progressbar"], [class*="loading"], [class*="spinner"]'
        );
        for (var l = 0; l < loadingNodes.length; l++) {
          var loadingRect = loadingNodes[l].getBoundingClientRect();
          var loadingTop = loadingRect.top + window.scrollY;
          var loadingStyle = window.getComputedStyle(loadingNodes[l]);
          if (
            loadingTop >= pageMiddle &&
            loadingRect.width > 0 &&
            loadingRect.height > 0 &&
            loadingStyle.display !== 'none' &&
            loadingStyle.visibility !== 'hidden'
          ) {
            loading = true;
            break;
          }
        }

        window.scrollBy(0, window.innerHeight);
        return {
          comments: commentEls.length,
          atBottom: atBottom,
          clicked: clicked,
          loading: loading,
        };
      },
    });
    var check = result[0] && result[0].result;
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
    stop_reason: stopReason,
    stable_bottom_rounds: stableBottomRounds,
  };
  console.info("[SA] scrollToComments", JSON.stringify(stats));
  return stats;
}


async function waitForMarketNewsReady(tabId, timeoutMs) {
  timeoutMs = timeoutMs || 20000;
  var start = Date.now();
  while (Date.now() - start < timeoutMs) {
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
    if (!check || check.status === "login_redirect") {
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
    if (!check || check.status === "login_redirect") {
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
    if (attempt > 0) {
      sendProgress("Retrying news detail: " + item.news_id);
      await chrome.tabs.reload(tabId);
      await waitForTabLoad(tabId, 30000, expectedPathFromUrl(item.url));
      await installMarketNewsPageGuards(tabId);
      await sleep(randomBetween(profile.retryDelayMinMs, profile.retryDelayMaxMs));
    }

    var detailReady = await waitForMarketNewsDetailReady(tabId);
    if (!detailReady.ok) {
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
    if (!check || check.status === "login_redirect")
      return { ok: false, error: "Session expired", reason_code: "login_required" };
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
    if (!check || check.status === "login_redirect")
      return { ok: false, error: "Session expired", reason_code: "login_required" };
    if (check.status === "paywall")
      return {
        ok: false,
        error: "Paywall: " + check.marker,
        reason_code: "access_restricted",
      };
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
    .executeScript({ target: { tabId }, files: ["scrape_comments.js"] })
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
