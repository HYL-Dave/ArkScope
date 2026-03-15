// popup.js — Refresh button + status display

const statusEl = document.getElementById("status");
const refreshBtn = document.getElementById("refreshBtn");
const progressEl = document.getElementById("progress");

// Load last refresh state from chrome.storage.local
chrome.storage.local.get("lastRefresh", (data) => {
  renderStatus(data.lastRefresh);
});

refreshBtn.addEventListener("click", () => {
  refreshBtn.disabled = true;
  refreshBtn.textContent = "Refreshing...";
  progressEl.style.display = "block";
  progressEl.textContent = "Opening SA page...";

  chrome.runtime.sendMessage({ action: "refresh" }, (response) => {
    refreshBtn.disabled = false;
    refreshBtn.textContent = "Refresh All";
    progressEl.style.display = "none";

    // Reload status from storage (background.js writes it after refresh)
    chrome.storage.local.get("lastRefresh", (data) => {
      renderStatus(data.lastRefresh);
    });
  });
});

// Listen for progress updates from background
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "progress") {
    progressEl.textContent = msg.text;
  }
});

function renderStatus(lastRefresh) {
  if (!lastRefresh) {
    statusEl.className = "empty";
    statusEl.textContent = "No data yet. Click Refresh.";
    return;
  }

  const ts = lastRefresh.batch_ts;
  const current = lastRefresh.current;
  const closed = lastRefresh.closed;
  const timeStr = ts ? new Date(ts).toLocaleString() : "unknown";

  const currentOk = current && current.status === "ok";
  const closedOk = closed && closed.status === "ok";

  // Clear previous content
  statusEl.textContent = "";

  if (currentOk && closedOk) {
    statusEl.className = "success";
    const line1 = document.createTextNode("Last refresh: " + timeStr);
    const br = document.createElement("br");
    const line2 = document.createTextNode(
      "Current: " + current.count + " picks | Closed: " + closed.count + " picks"
    );
    statusEl.append(line1, br, line2);
  } else if (currentOk || closedOk) {
    statusEl.className = "partial";
    const ok = currentOk ? "current" : "closed";
    const fail = currentOk ? "closed" : "current";
    const okCount = (currentOk ? current : closed).count;
    const failError = (currentOk ? closed : current).error || "unknown";
    const line1 = document.createTextNode("Partial refresh: " + timeStr);
    const br = document.createElement("br");
    const line2 = document.createTextNode(
      ok + ": " + okCount + " picks | " + fail + ": failed (" + failError + ")"
    );
    statusEl.append(line1, br, line2);
  } else if (current || closed) {
    statusEl.className = "error";
    const error = (current && current.error) || (closed && closed.error) || "unknown";
    const line1 = document.createTextNode("Failed: " + timeStr);
    const br = document.createElement("br");
    const line2 = document.createTextNode(error);
    statusEl.append(line1, br, line2);
  } else {
    statusEl.className = "empty";
    statusEl.textContent = "No data yet. Click Refresh.";
  }
}
