(function (root) {
  "use strict";

  var SCHEMA_VERSION = 1;
  var MAX_ENTRIES = 32;
  var MAX_OMITTED_COUNT = 10000;
  var MAX_MESSAGE_LENGTH = 240;
  var STAGES = Object.freeze([
    "tab_navigation",
    "page_readiness",
    "script_injection",
    "content_parse",
    "native_transport",
    "local_persistence",
    "reconciliation",
    "extension_runtime",
  ]);
  var TARGET_KINDS = Object.freeze([
    "article_detail",
    "article_comments",
    "market_news_detail",
    "phase",
  ]);
  var DIAGNOSTIC_ONLY_REASONS = Object.freeze([
    "tab_closed",
    "browser_api_failed",
    "script_injection_failed",
    "native_response_invalid",
    "database_busy",
    "database_integrity_failed",
    "database_write_failed",
  ]);
  var NON_FAILURE_REASONS = Object.freeze([
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
  ]);
  var protocolReasons = root.SAExtensionRunProtocol
    && Array.isArray(root.SAExtensionRunProtocol.REASON_CODES)
    ? root.SAExtensionRunProtocol.REASON_CODES
    : [];
  var REASON_CODES = Object.freeze(protocolReasons.filter(function (reason) {
    return NON_FAILURE_REASONS.indexOf(reason) === -1;
  }).concat(DIAGNOSTIC_ONLY_REASONS));
  var REQUIRED_KEYS = Object.freeze([
    "stage",
    "reason_code",
    "target_kind",
    "retryable",
    "attempt_count",
  ]);
  var OPTIONAL_KEYS = Object.freeze(["target_ref", "message"]);
  var TARGET_REF_RE = /^[A-Za-z0-9._:-]{1,128}$/;
  var PROHIBITED_TEXT = Object.freeze([
    /(?:https?|file):\/\/|\bwww\./i,
    /\?[A-Za-z0-9_.%-]+=/,
    /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b/,
    /\b(?:authorization|bearer|cookie|set-cookie|api[_ -]?key|access[_ -]?token|refresh[_ -]?token)\b/i,
    /\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{8,}/,
    /(?:^|\s)(?:\/[A-Za-z0-9._-]+){2,}(?:\/|\b)/,
    /\b[A-Za-z]:\\(?:[^\\\s]+\\)+/i,
    /\b(?:select\s+.+\s+from|insert\s+into|update\s+\w+\s+set|delete\s+from|create\s+table|drop\s+table)\b/i,
    /\btraceback\b|\bFile ".+", line \d+/i,
    /<[^>]+>/,
  ]);

  function isObject(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }

  function hasExactKeys(value) {
    var keys = Object.keys(value);
    var allowed = REQUIRED_KEYS.concat(OPTIONAL_KEYS);
    return REQUIRED_KEYS.every(function (key) { return keys.indexOf(key) !== -1; })
      && keys.every(function (key) { return allowed.indexOf(key) !== -1; });
  }

  function containsProhibitedText(value) {
    return PROHIBITED_TEXT.some(function (pattern) { return pattern.test(value); });
  }

  function projectEntry(candidate) {
    if (!isObject(candidate) || !hasExactKeys(candidate)) return null;
    if (STAGES.indexOf(candidate.stage) === -1
        || REASON_CODES.indexOf(candidate.reason_code) === -1
        || TARGET_KINDS.indexOf(candidate.target_kind) === -1
        || typeof candidate.retryable !== "boolean"
        || !Number.isInteger(candidate.attempt_count)
        || candidate.attempt_count < 1
        || candidate.attempt_count > 1000) {
      return null;
    }
    if (candidate.target_ref !== undefined
        && (typeof candidate.target_ref !== "string"
          || !TARGET_REF_RE.test(candidate.target_ref))) {
      return null;
    }
    if (candidate.message !== undefined
        && (typeof candidate.message !== "string"
          || !candidate.message
          || candidate.message.length > MAX_MESSAGE_LENGTH
          || containsProhibitedText(candidate.message))) {
      return null;
    }
    var projected = {
      stage: candidate.stage,
      reason_code: candidate.reason_code,
      target_kind: candidate.target_kind,
      retryable: candidate.retryable,
      attempt_count: candidate.attempt_count,
    };
    if (candidate.target_ref !== undefined) projected.target_ref = candidate.target_ref;
    if (candidate.message !== undefined) projected.message = candidate.message;
    return Object.freeze(projected);
  }

  function freezeEnvelope(entries, omittedCount) {
    return Object.freeze({
      schema_version: SCHEMA_VERSION,
      entries: Object.freeze(entries.slice()),
      omitted_count: Math.min(omittedCount, MAX_OMITTED_COUNT),
    });
  }

  function createCollector(options) {
    options = options || {};
    var now = typeof options.now === "function" ? options.now : Date.now;
    var entries = [];
    var omittedCount = 0;
    var rejected = 0;

    function record(candidate) {
      if (entries.length >= MAX_ENTRIES) {
        omittedCount = Math.min(omittedCount + 1, MAX_OMITTED_COUNT);
        return false;
      }
      var projected = projectEntry(candidate);
      if (!projected) {
        rejected += 1;
        return false;
      }
      var occurred = new Date(now());
      if (!Number.isFinite(occurred.getTime())) {
        rejected += 1;
        return false;
      }
      entries.push(Object.freeze(Object.assign({
        occurred_at: occurred.toISOString(),
      }, projected)));
      return true;
    }

    return Object.freeze({
      freeze: function () { return freezeEnvelope(entries, omittedCount); },
      record: record,
      rejectedCount: function () { return rejected; },
    });
  }

  root.SAExtensionDiagnostics = Object.freeze({
    MAX_ENTRIES: MAX_ENTRIES,
    REASON_CODES: REASON_CODES,
    STAGES: STAGES,
    TARGET_KINDS: TARGET_KINDS,
    createCollector: createCollector,
  });
}(globalThis));
