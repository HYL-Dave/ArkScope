// background.js — Service worker for SA Alpha Picks extension
// Orchestrates: open tab → wait for DOM → scrape current → switch to closed → scrape → native messaging → close tab

"use strict";

const SA_URL = "https://seekingalpha.com/alpha-picks/portfolio";
const NATIVE_HOST = "com.mindfulrl.sa_alpha_picks";
const TABLE_SELECTOR = '[data-testid="portfolio-table"] tbody tr';
const PAYWALL_MARKERS = ["Subscribe to unlock", "Upgrade your plan", "Premium required"];

// --- Message listener (from popup) ---

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "refresh") {
    doRefresh().then(sendResponse);
    return true; // async response
  }
});

// --- Main refresh flow ---

async function doRefresh() {
  const batchTs = new Date().toISOString();
  const results = { current: null, closed: null };

  let tabId = null;
  try {
    // Open SA page in background tab
    sendProgress("Opening SA Alpha Picks page...");
    const tab = await chrome.tabs.create({ url: SA_URL, active: false });
    tabId = tab.id;

    // Wait for initial page load
    await waitForTabLoad(tabId);

    // Wait for table to be ready (current tab is default)
    sendProgress("Waiting for portfolio table...");
    let ready = await waitForTableReady(tabId);
    if (!ready.ok) {
      results.current = await sendToNativeHost("refresh_failure", "current", [], ready.error, batchTs);
      results.closed = await sendToNativeHost("refresh_failure", "closed", [], ready.error, batchTs);
      await saveRefreshState(batchTs, results);
      return results;
    }

    // Scrape current tab
    sendProgress("Scraping current picks...");
    const currentPicks = await injectScraper(tabId);
    results.current = await sendToNativeHost("refresh", "current", currentPicks, null, batchTs);

    // Snapshot current table for change detection
    const currentSnapshot = await getTableSnapshot(tabId);

    // Click Closed tab
    sendProgress("Switching to Closed tab...");
    await clickClosedTab(tabId);

    // Wait for closed tab to be ready (button active + content changed)
    sendProgress("Waiting for closed picks...");
    const tabSwitched = await waitForClosedTabReady(tabId, currentSnapshot);
    if (!tabSwitched.ok) {
      results.closed = await sendToNativeHost("refresh_failure", "closed", [], tabSwitched.error, batchTs);
      await saveRefreshState(batchTs, results);
      return results;
    }

    // Scrape closed tab
    sendProgress("Scraping closed picks...");
    const closedPicks = await injectScraper(tabId);
    results.closed = await sendToNativeHost("refresh", "closed", closedPicks, null, batchTs);

    await saveRefreshState(batchTs, results);
    sendProgress("Done!");
    return results;
  } catch (err) {
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
      try { chrome.tabs.remove(tabId); } catch (_) { /* tab may already be closed */ }
    }
  }
}

// --- Tab management ---

function waitForTabLoad(tabId) {
  return new Promise((resolve) => {
    const listener = (id, changeInfo) => {
      if (id === tabId && changeInfo.status === "complete") {
        chrome.tabs.onUpdated.removeListener(listener);
        resolve();
      }
    };
    chrome.tabs.onUpdated.addListener(listener);
  });
}

// --- DOM readiness polling ---

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

// --- Closed tab switching + verification ---

async function clickClosedTab(tabId) {
  await chrome.scripting.executeScript({
    target: { tabId },
    func: () => {
      const buttons = document.querySelectorAll("button");
      for (const btn of buttons) {
        if (btn.textContent.trim() === "Closed") {
          btn.click();
          return true;
        }
      }
      return false;
    },
  });
}

async function getTableSnapshot(tabId) {
  const results = await chrome.scripting.executeScript({
    target: { tabId },
    func: (tableSelector) => {
      const rows = document.querySelectorAll(tableSelector);
      return Array.from(rows).slice(0, 3).map((r) => r.innerText.trim()).join("|");
    },
    args: [TABLE_SELECTOR],
  });
  return (results[0] && results[0].result) || "";
}

async function waitForClosedTabReady(tabId, currentSnapshot, timeoutMs = 15000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      args: [currentSnapshot, TABLE_SELECTOR],
      func: (prevSnapshot, tableSelector) => {
        // 1. Check Closed button is active
        const buttons = document.querySelectorAll("button");
        let closedActive = false;
        for (const btn of buttons) {
          if (btn.textContent.trim() === "Closed") {
            closedActive =
              btn.getAttribute("aria-selected") === "true" ||
              btn.classList.contains("active") ||
              btn.classList.contains("selected") ||
              parseInt(window.getComputedStyle(btn).fontWeight, 10) >= 600;
          }
        }
        if (!closedActive) return { status: "button_not_active" };

        // 2. Check table rows exist
        const rows = document.querySelectorAll(tableSelector);
        if (!rows.length) return { status: "no_rows" };

        // 3. Check content has changed (first 3 rows different from current snapshot)
        const newHash = Array.from(rows)
          .slice(0, 3)
          .map((r) => r.innerText.trim())
          .join("|");
        if (newHash === prevSnapshot) return { status: "content_unchanged" };

        return { status: "ready" };
      },
    });
    const check = results[0] && results[0].result;
    if (check && check.status === "ready") return { ok: true };
    await sleep(500);
  }
  return { ok: false, error: "Timeout: Closed tab content did not update" };
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
        });
      } else {
        resolve(response || { status: "error", scope, error: "No response from native host" });
      }
    });
  });
}

// --- Helpers ---

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function sendProgress(text) {
  // Send to popup if open
  chrome.runtime.sendMessage({ type: "progress", text }).catch(() => {
    // Popup may not be open, ignore
  });
}

async function saveRefreshState(batchTs, results) {
  await chrome.storage.local.set({
    lastRefresh: {
      batch_ts: batchTs,
      current: results.current,
      closed: results.closed,
    },
  });
}
