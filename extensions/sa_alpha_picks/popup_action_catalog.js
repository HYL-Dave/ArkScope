(function (root) {
  "use strict";

  function objectValue(value) {
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  }

  function integer(value) {
    return Number.isInteger(value) && value >= 0 ? value : "unavailable";
  }

  function seconds(value) {
    return Number.isInteger(value) && value >= 0
      ? Math.round(value / 1000)
      : "unavailable";
  }

  function configuredBatch(value, suffix) {
    if (!Number.isInteger(value) || value <= 0) {
      return "configured limit unavailable";
    }
    return value + " configured pending comment rows" + (suffix || "");
  }

  function buildCatalog(response) {
    var limits = objectValue(response && response.limits);
    var alpha = objectValue(limits.alpha_picks);
    var quick = objectValue(alpha.quick);
    var full = objectValue(alpha.full);
    var backfill = objectValue(alpha.backfill);
    var market = objectValue(limits.market_news);
    var marketQuick = objectValue(market.quick);
    var catchup = objectValue(market.catchup);

    return [
      {
        id: "quick",
        group: "alpha-picks",
        label: "Quick Update",
        description: "Refresh current and removed picks, recent articles, and a shallow comment window.",
        scope: "Up to " + integer(quick.article_list_rounds) +
          " article-list rounds; all normal missing-body and changed-count detail work " +
          "returned by that scan, with no separate global Alpha detail cap; " +
          integer(quick.detail_enrichment_limit) +
          " additional reconciliation enrichments; each comment scan is capped at " +
          integer(quick.comment_scroll_rounds) + " comment-scroll rounds within " +
          seconds(quick.comment_scroll_ms) + " seconds.",
        whenToUse: "Routine updates when no continuity warning is active.",
        nonGuarantee: "Does not prove older article or comment history is complete.",
      },
      {
        id: "full",
        group: "alpha-picks",
        label: "Full Article Scan",
        description: "Load the full reachable article list and perform a bounded deep content and comment scan.",
        scope: "Up to " + integer(full.article_list_rounds) +
          " article-list rounds; all normal detail work returned by that scan, with no " +
          "separate global Alpha detail cap; " + integer(full.detail_enrichment_limit) +
          " additional reconciliation enrichments; each comment scan is capped at " +
          integer(full.comment_scroll_rounds) + " comment-scroll rounds within " +
          seconds(full.comment_scroll_ms) + " seconds; plus " +
          configuredBatch(full.configured_comment_recovery_batch) + ".",
        whenToUse: "Periodic review or a pending continuity warning that is not parked.",
        nonGuarantee: "Bounded scanning may leave older provider history unreachable.",
      },
      {
        id: "backfill",
        group: "alpha-picks",
        label: "Deep Repair Scan",
        description: "Run the deepest bounded article scan and give comment recovery terminal authority.",
        scope: "Up to " + integer(backfill.article_list_rounds) +
          " article-list rounds; all normal detail work returned by that scan, with no " +
          "separate global Alpha detail cap; " + integer(backfill.detail_enrichment_limit) +
          " additional reconciliation enrichments; each comment scan is capped at " +
          integer(backfill.comment_scroll_rounds) + " comment-scroll rounds within " +
          seconds(backfill.comment_scroll_ms) + " seconds with " +
          integer(backfill.comment_stable_rounds) + " stable-bottom rounds; plus " + configuredBatch(
            backfill.configured_comment_recovery_batch,
            ", including parked rows"
          ) + ".",
        whenToUse: "Manual repair after Full scans cannot reconnect a comment baseline.",
        nonGuarantee: "It records unreachable history honestly; it cannot recreate content removed by the source.",
      },
      {
        id: "market-news",
        group: "market-news",
        label: "Sync Latest News",
        description: "Collect the newest Market News metadata and a bounded set of detail pages.",
        scope: "Up to " + integer(marketQuick.list_rounds) +
          " list rounds and " + integer(marketQuick.detail_attempts) +
          " Market News detail attempts.",
        whenToUse: "Routine Market News updates.",
        nonGuarantee: "Does not recover a missed interval or details outside the current queue.",
      },
      {
        id: "market-news-catchup",
        group: "market-news",
        label: "Catch Up News (24h)",
        description: "Retry recent Market News metadata and details within the routine 24-hour horizon.",
        scope: "Last " + integer(catchup.window_hours) + " hours; up to " +
          integer(catchup.list_rounds) + " list rounds and " +
          integer(catchup.total_detail_attempts) + " total detail attempts (" +
          integer(catchup.current_detail_attempts) + " current + " +
          integer(catchup.backlog_detail_attempts) + " backlog).",
        whenToUse: "A short interruption that remains inside the recent-news window.",
        nonGuarantee: "Does not recover details or missing metadata older than 24 hours.",
      },
    ];
  }

  var outcomeLabels = Object.freeze({
    complete: "Complete",
    degraded: "Needs attention",
    failed: "Failed",
    skipped: "Skipped",
  });
  var reasonLabels = Object.freeze({
    telemetry_unavailable: "Audit recording is unavailable",
    detail_timeout: "One or more detail pages timed out",
    access_restricted: "Source access is restricted",
    login_required: "Seeking Alpha sign-in is required",
    parser_empty: "A detail page could not be parsed",
    detail_save_failed: "A detail page could not be saved",
    extension_dependency_missing: "An extension runtime file is missing",
    interrupted: "The operation was interrupted and can be retried",
    unknown_failure: "The operation needs attention",
  });
  var auditLabels = Object.freeze({
    persisted: "Audit recorded",
    pending: "Audit pending",
    unavailable: "Audit unavailable",
  });

  root.SAExtensionPopupActions = Object.freeze({
    buildCatalog: buildCatalog,
    outcomeLabel: function (value) {
      return outcomeLabels[value] || "Unknown state";
    },
    reasonLabel: function (value) {
      return reasonLabels[value] || "Additional details are available in ArkScope";
    },
    auditLabel: function (value) {
      return auditLabels[value] || "Audit state unavailable";
    },
  });
})(typeof globalThis !== "undefined" ? globalThis : this);
