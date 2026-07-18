// popup.js — Three-mode refresh: Quick + Full Scan + Deep Backfill

var statusEl = document.getElementById("status");
var marketNewsStatusEl = document.getElementById("marketNewsStatus");
var quickBtn = document.getElementById("quickBtn");
var fullBtn = document.getElementById("fullBtn");
var backfillBtn = document.getElementById("backfillBtn");
var marketNewsBtn = document.getElementById("marketNewsBtn");
var marketNewsCatchupBtn = document.getElementById("marketNewsCatchupBtn");
var alphaPicksAutoSyncToggle = document.getElementById("alphaPicksAutoSyncToggle");
var alphaPicksAutoSyncInterval = document.getElementById("alphaPicksAutoSyncInterval");
var marketNewsAutoSyncToggle = document.getElementById("marketNewsAutoSyncToggle");
var marketNewsAutoSyncInterval = document.getElementById("marketNewsAutoSyncInterval");
var marketNewsAutoSyncResolvedEl = document.getElementById("marketNewsAutoSyncResolved");
var progressEl = document.getElementById("progress");
var reconciliationQueueEl = document.getElementById("reconciliationQueue");
var reconciliationErrorEl = document.getElementById("reconciliationError");
var manualConfirmationEl = document.getElementById("manualConfirmation");
var manualInput = document.getElementById("manualInput");
var manualBtn = document.getElementById("manualBtn");
var RECONCILIATION_NATIVE_HOST = "com.mindfulrl.sa_alpha_picks";
var lastReconciliationQueue = null;
var ALPHA_PICKS_AUTO_SYNC_DEFAULT_INTERVAL = "30";
var MARKET_NEWS_AUTO_SYNC_DEFAULT_INTERVAL = "60";
var MARKET_NEWS_AUTO_SYNC_AUTO_VALUE = "auto";
var MARKET_NEWS_AUTO_SYNC_WINDOWS_ET = {
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

// Load last refresh state + restore manual input
chrome.storage.local.get([
  "lastRefresh",
  "lastMarketNewsRefresh",
  "manualDraft",
  "alphaPicksAutoSyncEnabled",
  "alphaPicksAutoSyncIntervalMinutes",
  "marketNewsAutoSyncEnabled",
  "marketNewsAutoSyncIntervalMinutes"
], function (data) {
  if (data.manualDraft) {
    manualInput.value = data.manualDraft;
  }
  alphaPicksAutoSyncToggle.checked = !!data.alphaPicksAutoSyncEnabled;
  alphaPicksAutoSyncInterval.value = normalizeAlphaPicksAutoSyncIntervalValue(data.alphaPicksAutoSyncIntervalMinutes);
  alphaPicksAutoSyncInterval.setAttribute("data-last-value", alphaPicksAutoSyncInterval.value);
  marketNewsAutoSyncToggle.checked = !!data.marketNewsAutoSyncEnabled;
  marketNewsAutoSyncInterval.value = normalizeMarketNewsAutoSyncIntervalValue(data.marketNewsAutoSyncIntervalMinutes);
  marketNewsAutoSyncInterval.setAttribute("data-last-value", marketNewsAutoSyncInterval.value);
  renderMarketNewsAutoSyncResolved();
  renderStatus(data.lastRefresh);
  renderMarketNewsStatus(data.lastMarketNewsRefresh);
  loadReconciliationQueue();
  chrome.runtime.sendMessage({ action: "ensure_auto_sync_alarms" }, function () {
    if (chrome.runtime.lastError) {
      return;
    }
  });
});

// Persist manual input on change (survives popup close/reopen)
manualInput.addEventListener("input", function () {
  chrome.storage.local.set({ manualDraft: manualInput.value });
});

quickBtn.addEventListener("click", function () {
  startRefresh("quick");
});

fullBtn.addEventListener("click", function () {
  startRefresh("full");
});

backfillBtn.addEventListener("click", function () {
  startRefresh("backfill");
});

marketNewsBtn.addEventListener("click", function () {
  startMarketNewsRefresh("quick");
});

marketNewsCatchupBtn.addEventListener("click", function () {
  startMarketNewsRefresh("catchup");
});

alphaPicksAutoSyncToggle.addEventListener("change", function () {
  var enabled = !!alphaPicksAutoSyncToggle.checked;
  updateAlphaPicksAutoSyncSetting({
    enabled: enabled,
    interval_minutes: parseInt(alphaPicksAutoSyncInterval.value, 10),
  }, function (result) {
    if (!result || result.status !== "ok") {
      alphaPicksAutoSyncToggle.checked = !enabled;
    }
  });
});

alphaPicksAutoSyncInterval.addEventListener("change", function () {
  var previousValue = alphaPicksAutoSyncInterval.getAttribute("data-last-value") || ALPHA_PICKS_AUTO_SYNC_DEFAULT_INTERVAL;
  var intervalMinutes = parseInt(alphaPicksAutoSyncInterval.value, 10);
  updateAlphaPicksAutoSyncSetting({
    enabled: !!alphaPicksAutoSyncToggle.checked,
    interval_minutes: intervalMinutes,
  }, function (result) {
    if (!result || result.status !== "ok") {
      alphaPicksAutoSyncInterval.value = previousValue;
      return;
    }
    alphaPicksAutoSyncInterval.setAttribute("data-last-value", String(result.interval_minutes));
  });
});

marketNewsAutoSyncToggle.addEventListener("change", function () {
  var enabled = !!marketNewsAutoSyncToggle.checked;
  updateMarketNewsAutoSyncSetting({
    enabled: enabled,
    interval_minutes: marketNewsAutoSyncInterval.value,
  }, function (result) {
    if (!result || result.status !== "ok") {
      marketNewsAutoSyncToggle.checked = !enabled;
      renderMarketNewsAutoSyncResolved();
    }
  });
});

marketNewsAutoSyncInterval.addEventListener("change", function () {
  var previousValue = marketNewsAutoSyncInterval.getAttribute("data-last-value") || MARKET_NEWS_AUTO_SYNC_DEFAULT_INTERVAL;
  var intervalMinutes = marketNewsAutoSyncInterval.value;
  updateMarketNewsAutoSyncSetting({
    enabled: !!marketNewsAutoSyncToggle.checked,
    interval_minutes: intervalMinutes,
  }, function (result) {
    if (!result || result.status !== "ok") {
      marketNewsAutoSyncInterval.value = previousValue;
      renderMarketNewsAutoSyncResolved();
      return;
    }
  });
});

function startRefresh(mode) {
  quickBtn.disabled = true;
  fullBtn.disabled = true;
  backfillBtn.disabled = true;
  marketNewsBtn.disabled = true;
  if (marketNewsCatchupBtn) marketNewsCatchupBtn.disabled = true;
  var activeBtn = mode === "full" ? fullBtn : (mode === "backfill" ? backfillBtn : quickBtn);
  var originalText = activeBtn.textContent;
  activeBtn.textContent = mode === "full"
    ? "Scanning..."
    : (mode === "backfill" ? "Backfilling..." : "Refreshing...");
  progressEl.style.display = "block";
  progressEl.textContent = mode === "backfill" ? "Preparing backlog scan..." : "Opening SA page...";

  chrome.runtime.sendMessage({ action: "refresh", mode: mode }, function () {
    quickBtn.disabled = false;
    fullBtn.disabled = false;
    backfillBtn.disabled = false;
    marketNewsBtn.disabled = false;
    if (marketNewsCatchupBtn) marketNewsCatchupBtn.disabled = false;
    activeBtn.textContent = originalText;
    progressEl.style.display = "none";

    chrome.storage.local.get("lastRefresh", function (data) {
      renderStatus(data.lastRefresh);
      loadReconciliationQueue();
    });
  });
}


function startMarketNewsRefresh(mode) {
  mode = mode || "quick";
  quickBtn.disabled = true;
  fullBtn.disabled = true;
  backfillBtn.disabled = true;
  marketNewsBtn.disabled = true;
  if (marketNewsCatchupBtn) marketNewsCatchupBtn.disabled = true;
  var activeBtn = mode === "catchup" ? marketNewsCatchupBtn : marketNewsBtn;
  var originalText = activeBtn.textContent;
  activeBtn.textContent = mode === "catchup" ? "Catching Up..." : "Syncing News...";
  progressEl.style.display = "block";
  progressEl.textContent = mode === "catchup"
    ? "Opening market news for catchup..."
    : "Opening market news...";

  chrome.runtime.sendMessage({ action: "refresh_market_news", mode: mode }, function () {
    quickBtn.disabled = false;
    fullBtn.disabled = false;
    backfillBtn.disabled = false;
    marketNewsBtn.disabled = false;
    if (marketNewsCatchupBtn) marketNewsCatchupBtn.disabled = false;
    activeBtn.textContent = originalText;
    progressEl.style.display = "none";

    chrome.storage.local.get("lastMarketNewsRefresh", function (data) {
      renderMarketNewsStatus(data.lastMarketNewsRefresh);
    });
  });
}

function updateAlphaPicksAutoSyncSetting(payload, onDone) {
  chrome.runtime.sendMessage({
    action: "set_alpha_picks_auto_sync",
    enabled: !!payload.enabled,
    interval_minutes: payload.interval_minutes,
  }, function (result) {
    if (!result || result.status !== "ok") {
      progressEl.style.display = "block";
      progressEl.textContent = "Failed to update Alpha Picks auto-sync";
      progressEl.style.color = "#c62828";
      if (onDone) onDone(result);
      return;
    }
    alphaPicksAutoSyncInterval.value = String(result.interval_minutes);
    alphaPicksAutoSyncInterval.setAttribute("data-last-value", String(result.interval_minutes));
    progressEl.style.display = "block";
    progressEl.style.color = "#666";
    progressEl.textContent = result.enabled
      ? "Alpha Picks auto-sync enabled (" + formatAutoSyncIntervalLabel(result.interval_minutes) + ")"
      : "Alpha Picks auto-sync disabled";
    if (onDone) onDone(result);
  });
}

function updateMarketNewsAutoSyncSetting(payload, onDone) {
  chrome.runtime.sendMessage({
    action: "set_market_news_auto_sync",
    enabled: !!payload.enabled,
    interval_minutes: payload.interval_minutes,
  }, function (result) {
    if (!result || result.status !== "ok") {
      progressEl.style.display = "block";
      progressEl.textContent = "Failed to update auto-sync setting";
      progressEl.style.color = "#c62828";
      if (onDone) onDone(result);
      return;
    }
    var intervalSetting = result.interval_setting != null
      ? String(result.interval_setting)
      : normalizeMarketNewsAutoSyncIntervalValue(payload.interval_minutes);
    marketNewsAutoSyncInterval.value = intervalSetting;
    marketNewsAutoSyncInterval.setAttribute("data-last-value", intervalSetting);
    progressEl.style.display = "block";
    progressEl.style.color = "#666";
    progressEl.textContent = result.enabled
      ? "Market News auto-sync enabled (" + (result.interval_label || formatAutoSyncIntervalLabel(result.interval_minutes)) + ")"
      : "Market News auto-sync disabled";
    renderMarketNewsAutoSyncResolved(result.interval_setting, result.enabled);
    if (onDone) onDone(result);
  });
}

function normalizeAlphaPicksAutoSyncIntervalValue(value) {
  var allowed = { "15": true, "30": true, "60": true };
  var normalized = String(value || ALPHA_PICKS_AUTO_SYNC_DEFAULT_INTERVAL);
  if (!allowed[normalized]) return ALPHA_PICKS_AUTO_SYNC_DEFAULT_INTERVAL;
  return normalized;
}

function normalizeMarketNewsAutoSyncIntervalValue(value) {
  var allowed = { "5": true, "15": true, "60": true, "auto": true };
  var normalized = String(value || MARKET_NEWS_AUTO_SYNC_DEFAULT_INTERVAL);
  if (!allowed[normalized]) return MARKET_NEWS_AUTO_SYNC_DEFAULT_INTERVAL;
  return normalized;
}

function formatAutoSyncIntervalLabel(intervalMinutes) {
  if (String(intervalMinutes) === MARKET_NEWS_AUTO_SYNC_AUTO_VALUE) {
    return "auto";
  }
  var mins = parseInt(intervalMinutes, 10);
  if (mins === 60) return "every 60 min";
  return "every " + mins + " min";
}

function renderMarketNewsAutoSyncResolved(intervalSetting, enabled) {
  if (!marketNewsAutoSyncResolvedEl) return;
  var normalizedSetting = normalizeMarketNewsAutoSyncIntervalValue(
    intervalSetting != null ? intervalSetting : marketNewsAutoSyncInterval.value
  );
  var isEnabled = enabled != null ? !!enabled : !!marketNewsAutoSyncToggle.checked;
  if (!isEnabled) {
    marketNewsAutoSyncResolvedEl.textContent = "Market News auto-sync is disabled.";
    return;
  }

  if (normalizedSetting !== MARKET_NEWS_AUTO_SYNC_AUTO_VALUE) {
    marketNewsAutoSyncResolvedEl.textContent =
      "Current Market News cadence: " + formatAutoSyncIntervalLabel(normalizedSetting) + ".";
    return;
  }

  var schedule = getMarketNewsAutoSyncSchedule(nowDate());
  marketNewsAutoSyncResolvedEl.textContent =
    "Auto currently resolves to " + formatAutoSyncIntervalLabel(schedule.intervalMinutes) +
    " (" + schedule.timeLabel + " ET).";
}

function getMarketNewsAutoSyncSchedule(now) {
  var parts = getNewYorkTimeParts(now || nowDate());
  var totalMinutes = (parts.hour * 60) + parts.minute;
  var windows = parts.weekday === "Sat" || parts.weekday === "Sun"
    ? MARKET_NEWS_AUTO_SYNC_WINDOWS_ET.weekend
    : MARKET_NEWS_AUTO_SYNC_WINDOWS_ET.weekday;
  var resolvedMinutes = resolveMarketNewsAutoSyncInterval(windows, totalMinutes);

  return {
    intervalMinutes: resolvedMinutes,
    timeLabel: parts.weekday + " " + formatHourMinute(parts.hour, parts.minute),
  };
}

function resolveMarketNewsAutoSyncInterval(windows, totalMinutes) {
  for (var i = 0; i < windows.length; i++) {
    var window = windows[i];
    if (totalMinutes >= window.start && totalMinutes < window.end) {
      return window.interval;
    }
  }
  return parseInt(MARKET_NEWS_AUTO_SYNC_DEFAULT_INTERVAL, 10);
}

function getNewYorkTimeParts(now) {
  var formatter = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  var parts = formatter.formatToParts(now || nowDate());
  var out = { weekday: "", hour: 0, minute: 0 };
  for (var i = 0; i < parts.length; i++) {
    var part = parts[i];
    if (part.type === "weekday") out.weekday = part.value;
    if (part.type === "hour") out.hour = parseInt(part.value, 10) || 0;
    if (part.type === "minute") out.minute = parseInt(part.value, 10) || 0;
  }
  return out;
}

function formatHourMinute(hour, minute) {
  var hh = String(hour).padStart(2, "0");
  var mm = String(minute).padStart(2, "0");
  return hh + ":" + mm;
}

function nowDate() {
  return new Date();
}

setInterval(function () {
  renderMarketNewsAutoSyncResolved();
}, 60000);

function sendReconciliationNative(payload) {
  return new Promise(function (resolve) {
    chrome.runtime.sendNativeMessage(RECONCILIATION_NATIVE_HOST, payload, function (result) {
      if (chrome.runtime.lastError) {
        resolve({ status: "error", error_code: "native_host_unavailable" });
        return;
      }
      resolve(result || { status: "error", error_code: "empty_native_response" });
    });
  });
}

function renderReconciliationQueue(queue) {
  ArkScopeReconciliationUI.renderQueue(reconciliationQueueEl, queue, {
    onUseCandidate: function (payload) {
      return sendReconciliationNative(Object.assign(
        { action: "accept_reconciliation_link" }, payload
      ));
    },
    onRejectCandidate: function (payload) {
      return sendReconciliationNative(Object.assign(
        { action: "reject_reconciliation_candidate" }, payload
      ));
    },
    onChanged: function () {
      loadReconciliationQueue();
    },
  });
}

function loadReconciliationQueue() {
  return sendReconciliationNative({ action: "get_reconciliation_queue", limit: 50 })
    .then(function (result) {
      if (result && result.status === "ok" && Array.isArray(result.events)) {
        lastReconciliationQueue = {
          events: result.events,
          total: Number.isInteger(result.total) ? result.total : result.events.length,
        };
        reconciliationErrorEl.hidden = true;
        reconciliationErrorEl.textContent = "";
        renderReconciliationQueue(lastReconciliationQueue);
        return lastReconciliationQueue;
      }
      reconciliationErrorEl.hidden = false;
      reconciliationErrorEl.textContent = "Unable to update article link review. Try again.";
      if (lastReconciliationQueue) renderReconciliationQueue(lastReconciliationQueue);
      return null;
    });
}

function renderManualConfirmations(confirmations) {
  manualConfirmationEl.replaceChildren();
  (confirmations || []).forEach(function (item) {
    var row = document.createElement("div");
    row.className = "reconciliation-confirmation";
    var warning = document.createElement("div");
    warning.className = "reconciliation-warning";
    warning.textContent = item.symbol + " needs another confirmation because of its article date or existing link";
    var actions = document.createElement("div");
    actions.className = "reconciliation-confirm-actions";
    var confirmButton = document.createElement("button");
    confirmButton.type = "button";
    confirmButton.className = "reconciliation-confirm";
    confirmButton.textContent = "Use anyway";
    var cancelButton = document.createElement("button");
    cancelButton.type = "button";
    cancelButton.className = "reconciliation-cancel";
    cancelButton.textContent = "Cancel";
    actions.append(confirmButton, cancelButton);
    row.append(warning, actions);
    manualConfirmationEl.appendChild(row);

    cancelButton.addEventListener("click", function () {
      row.remove();
    });
    confirmButton.addEventListener("click", function () {
      confirmButton.disabled = true;
      sendReconciliationNative({
        action: "accept_reconciliation_link",
        lineage_id: item.lineage_id,
        role: item.role,
        event_anchor_date: item.event_anchor_date,
        article_id: item.article_id,
        article_url: item.url,
        replace_link_id: item.replace_link_id,
        confirm_warnings: true,
      }).then(function (result) {
        if (result && result.status === "ok") {
          row.remove();
          loadReconciliationQueue();
          return;
        }
        confirmButton.disabled = false;
        progressEl.style.display = "block";
        progressEl.style.color = "#c62828";
        progressEl.textContent = "Confirmation failed. Try again.";
      });
    });
  });
}

manualBtn.addEventListener("click", function () {
  var parsed = ArkScopeReconciliationUI.parseAdvancedLines(manualInput.value);
  if (parsed.errors.length > 0 || parsed.items.length === 0) {
    progressEl.style.display = "block";
    progressEl.style.color = "#c62828";
    progressEl.textContent = parsed.errors.length > 0
      ? "Line " + parsed.errors[0].line + " has invalid format"
      : "Enter at least one complete event";
    return;
  }

  manualBtn.disabled = true;
  manualBtn.textContent = "Fetching...";
  progressEl.style.display = "block";
  chrome.runtime.sendMessage({ action: "manual_fetch", items: parsed.items }, function (result) {
    manualBtn.disabled = false;
    manualBtn.textContent = "Fetch and review";
    progressEl.style.display = "block";
    var confirmations = result && Array.isArray(result.confirmation_required)
      ? result.confirmation_required
      : [];
    renderManualConfirmations(confirmations);
    if (confirmations.length > 0) {
      progressEl.textContent = "Article fetched; confirm the link";
      progressEl.style.color = "#e65100";
    } else if (result && result.fetched > 0) {
      progressEl.textContent = "Fetched " + result.fetched + " article" +
        (result.fetched === 1 ? "" : "s") +
        (result.failed > 0 ? "; " + result.failed + " failed" : "");
      progressEl.style.color = "#2e7d32";
      manualInput.value = "";
      chrome.storage.local.remove("manualDraft");
    } else if (result && result.failed > 0) {
      progressEl.textContent = result.failed + " article" +
        (result.failed === 1 ? " could" : "s could") + " not be fetched or linked";
      progressEl.style.color = "#c62828";
    } else {
      progressEl.textContent = "No valid articles to process. Check the input.";
      progressEl.style.color = "#e65100";
    }
    loadReconciliationQueue();
    chrome.storage.local.get("lastRefresh", function (data) {
      renderStatus(data.lastRefresh);
    });
  });
});

// Listen for progress updates from background
chrome.runtime.onMessage.addListener(function (msg) {
  if (msg.type === "progress") {
    progressEl.textContent = msg.text;
  }
});

chrome.storage.onChanged.addListener(function (changes, areaName) {
  if (areaName !== "local") return;
  if (changes.lastRefresh) {
    renderStatus(changes.lastRefresh.newValue);
    loadReconciliationQueue();
  }
  if (changes.lastMarketNewsRefresh) {
    renderMarketNewsStatus(changes.lastMarketNewsRefresh.newValue);
  }
});

function renderMarketNewsStatus(lastMarketNewsRefresh) {
  if (!marketNewsStatusEl) return;
  if (!lastMarketNewsRefresh) {
    marketNewsStatusEl.className = "empty";
    marketNewsStatusEl.textContent = "Market News: not synced yet.";
    return;
  }
  var ts = lastMarketNewsRefresh.batch_ts;
  var timeStr = ts ? new Date(ts).toLocaleString() : "unknown";
  var result = lastMarketNewsRefresh.result || {};
  var modeLabel = "";
  if (lastMarketNewsRefresh.mode === "catchup") modeLabel = " (catchup)";
  else if (lastMarketNewsRefresh.mode === "full") modeLabel = " (full)";
  else if (lastMarketNewsRefresh.mode === "backfill") modeLabel = " (backfill)";
  else if (lastMarketNewsRefresh.mode === "quick") modeLabel = " (quick)";
  if (result.status === "ok") {
    marketNewsStatusEl.className = "success";
    var detailSuffix = "";
    if (typeof result.detail_fetched === "number") {
      detailSuffix = ", " + result.detail_fetched + " detail fetched";
    }
    marketNewsStatusEl.textContent = "Market News" + modeLabel + ": " + (result.saved || 0) + " saved / " + (result.count || 0) + " scraped" + detailSuffix + " (" + timeStr + ")";
  } else {
    marketNewsStatusEl.className = "error";
    marketNewsStatusEl.textContent = "Market News" + modeLabel + " failed: " + (result.error || "unknown") + " (" + timeStr + ")";
  }
}

function renderStatus(lastRefresh) {
  if (!lastRefresh) {
    statusEl.className = "empty";
    statusEl.textContent = "No data yet. Click a button below.";
    return;
  }

  var ts = lastRefresh.batch_ts;
  var current = lastRefresh.current;
  var closed = lastRefresh.closed;
  var timeStr = ts ? new Date(ts).toLocaleString() : "unknown";
  var modeLabel = " (quick)";
  if (lastRefresh.mode === "full") modeLabel = " (full scan)";
  if (lastRefresh.mode === "backfill") modeLabel = " (deep backfill)";

  var currentOk = current && current.status === "ok";
  var closedOk = closed && closed.status === "ok";

  statusEl.textContent = "";

  if (currentOk && closedOk) {
    statusEl.className = "success";
    statusEl.append(
      document.createTextNode("Last refresh: " + timeStr + modeLabel),
      document.createElement("br"),
      document.createTextNode(
        "Current: " + current.count + " picks | Closed: " + closed.count + " picks"
      )
    );
  } else if (currentOk || closedOk) {
    statusEl.className = "partial";
    var ok = currentOk ? "current" : "closed";
    var fail = currentOk ? "closed" : "current";
    var okCount = (currentOk ? current : closed).count;
    var failError = (currentOk ? closed : current).error || "unknown";
    statusEl.append(
      document.createTextNode("Partial refresh: " + timeStr + modeLabel),
      document.createElement("br"),
      document.createTextNode(ok + ": " + okCount + " picks | " + fail + ": failed (" + failError + ")")
    );
  } else if (current || closed) {
    statusEl.className = "error";
    var error = (current && current.error) || (closed && closed.error) || "unknown";
    statusEl.append(
      document.createTextNode("Failed: " + timeStr),
      document.createElement("br"),
      document.createTextNode(error)
    );
  } else {
    statusEl.className = "empty";
    statusEl.textContent = "No data yet. Click a button below.";
    return;
  }

  // Articles + details results (v3 format)
  var details = lastRefresh.details;
  if (details) {
    if (details.error) {
      statusEl.append(
        document.createElement("br"),
        document.createTextNode("Articles: error (" + details.error + ")")
      );
    } else {
      var parts = [];
      if (details.articles_saved > 0) parts.push(details.articles_saved + " recent articles scanned");
      if (details.fetched > 0) parts.push(details.fetched + " content fetched");
      if (details.comments_refreshed > 0) {
        var refreshedLabel = details.comments_refreshed === 1
          ? " article comments rescanned"
          : " articles' comments rescanned";
        parts.push(details.comments_refreshed + refreshedLabel);
      }
      if ((details.net_new_comments || 0) > 0) {
        var newCommentsLabel = details.net_new_comments === 1
          ? " net new comment stored"
          : " net new comments stored";
        parts.push(details.net_new_comments + newCommentsLabel);
      }
      if (details.failed > 0) parts.push(details.failed + " failed");
      var detailLine = "Articles: " + (parts.length > 0 ? parts.join(", ") : "up to date");
      statusEl.append(document.createElement("br"), document.createTextNode(detailLine));
    }

    if (Number.isInteger(details.review_required) && details.review_required > 0) {
      statusEl.append(
        document.createElement("br"),
        document.createTextNode("Article links: " + details.review_required + " events to review")
      );
    }
  }
}
