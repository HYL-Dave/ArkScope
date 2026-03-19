// popup.js — Two-mode refresh: Quick (daily) + Full Scan (deep)

var statusEl = document.getElementById("status");
var quickBtn = document.getElementById("quickBtn");
var fullBtn = document.getElementById("fullBtn");
var progressEl = document.getElementById("progress");
var manualSection = document.getElementById("manualSection");
var manualInput = document.getElementById("manualInput");
var manualBtn = document.getElementById("manualBtn");

// Load last refresh state + restore manual input
chrome.storage.local.get(["lastRefresh", "manualDraft"], function (data) {
  if (data.manualDraft) {
    manualInput.value = data.manualDraft;
  }
  renderStatus(data.lastRefresh);
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

function startRefresh(mode) {
  quickBtn.disabled = true;
  fullBtn.disabled = true;
  var activeBtn = mode === "full" ? fullBtn : quickBtn;
  var originalText = activeBtn.textContent;
  activeBtn.textContent = mode === "full" ? "Scanning..." : "Refreshing...";
  progressEl.style.display = "block";
  progressEl.textContent = "Opening SA page...";

  chrome.runtime.sendMessage({ action: "refresh", mode: mode }, function () {
    quickBtn.disabled = false;
    fullBtn.disabled = false;
    activeBtn.textContent = originalText;
    progressEl.style.display = "none";

    chrome.storage.local.get("lastRefresh", function (data) {
      renderStatus(data.lastRefresh);
    });
  });
}

manualBtn.addEventListener("click", function () {
  var lines = manualInput.value.trim().split("\n");
  var items = [];
  for (var i = 0; i < lines.length; i++) {
    var parts = lines[i].trim().split(/\s+/);
    if (parts.length >= 2) {
      items.push({ symbol: parts[0].toUpperCase(), url: parts.slice(1).join(" ") });
    }
  }
  if (items.length === 0) return;

  manualBtn.disabled = true;
  manualBtn.textContent = "Fetching...";
  progressEl.style.display = "block";

  chrome.runtime.sendMessage({ action: "manual_fetch", items: items }, function (result) {
    manualBtn.disabled = false;
    manualBtn.textContent = "Fetch Manual";
    progressEl.style.display = "block";
    // Show result
    if (result && result.fetched > 0) {
      progressEl.textContent = "Done: " + result.fetched + " saved" +
        (result.failed > 0 ? ", " + result.failed + " failed" : "");
      progressEl.style.color = "#2e7d32";
      manualInput.value = "";
      chrome.storage.local.remove("manualDraft");
    } else if (result && result.failed > 0) {
      progressEl.textContent = "Failed: " + result.failed + " articles could not be fetched";
      progressEl.style.color = "#c62828";
    } else {
      progressEl.textContent = "No result — check if URLs are correct";
      progressEl.style.color = "#e65100";
    }
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
  var modeLabel = lastRefresh.mode === "full" ? " (full scan)" : " (quick)";

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

  // Detail fetch results
  var details = lastRefresh.details;
  if (details) {
    var detailLine = "";
    if (details.error) {
      detailLine = "Details: error (" + details.error + ")";
    } else {
      var parts = [];
      if (details.skipped > 0) parts.push(details.skipped + " cached");
      if (details.fetched > 0) parts.push(details.fetched + " fetched");
      if (details.failed > 0) parts.push(details.failed + " failed");
      detailLine = "Details: " + (parts.length > 0 ? parts.join(", ") : "up to date");
    }
    statusEl.append(document.createElement("br"), document.createTextNode(detailLine));

    // Show tickers with no matching article + enable manual input
    if (details.no_article && details.no_article.length > 0) {
      var missingLine = "Missing article: " + details.no_article.join(", ");
      statusEl.append(document.createElement("br"), document.createTextNode(missingLine));

      // Show manual fetch section — only pre-fill if user hasn't started typing
      manualSection.style.display = "block";
      if (!manualInput.value || !manualInput.value.includes("http")) {
        manualInput.value = details.no_article.map(function (t) { return t + " "; }).join("\n");
      }
    } else {
      manualSection.style.display = "none";
    }
  }
}
