// background.js — Service worker for SA Alpha Picks extension
// Orchestrates: open tab → wait for DOM → scrape current → switch to closed → scrape → native messaging → close tab

"use strict";

const SA_CURRENT_URL = "https://seekingalpha.com/alpha-picks/picks/current";
const SA_CLOSED_URL = "https://seekingalpha.com/alpha-picks/picks/removed";
const SA_ARTICLES_URL = "https://seekingalpha.com/alpha-picks/articles";
const NATIVE_HOST = "com.mindfulrl.sa_alpha_picks";
const TABLE_SELECTOR = "table tbody tr";
const PAYWALL_MARKERS = ["Subscribe to unlock", "Upgrade your plan", "Premium required"];

// --- Message listener (from popup) ---

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "refresh") {
    doRefresh(msg.mode || "quick").then(sendResponse);
    return true;
  }
  if (msg.action === "manual_fetch") {
    doManualFetch(msg.items || []).then(sendResponse);
    return true;
  }
});

// --- Main refresh flow ---

async function doRefresh(mode) {
  const batchTs = new Date().toISOString();
  const results = { current: null, closed: null, mode: mode };

  let tabId = null;
  try {
    // --- Scrape current picks ---
    sendProgress("Opening current picks page...");
    const tab = await chrome.tabs.create({ url: SA_CURRENT_URL, active: false });
    tabId = tab.id;
    await waitForTabLoad(tabId);

    sendProgress("Waiting for current picks table...");
    let ready = await waitForTableReady(tabId);
    if (!ready.ok) {
      results.current = await sendToNativeHost("refresh_failure", "current", [], ready.error, batchTs);
    } else {
      sendProgress("Scraping current picks...");
      const currentPicks = await injectScraper(tabId);
      results.current = await sendToNativeHost("refresh", "current", currentPicks, null, batchTs);
      results._currentPicks = currentPicks;  // Keep for detail fetch
    }

    // --- Scrape closed (removed) picks ---
    sendProgress("Opening closed picks page...");
    await chrome.tabs.update(tabId, { url: SA_CLOSED_URL });
    await waitForTabLoad(tabId);

    sendProgress("Waiting for closed picks table...");
    ready = await waitForTableReady(tabId);
    if (!ready.ok) {
      results.closed = await sendToNativeHost("refresh_failure", "closed", [], ready.error, batchTs);
    } else {
      sendProgress("Scraping closed picks...");
      const closedPicks = await injectScraper(tabId);
      results.closed = await sendToNativeHost("refresh", "closed", closedPicks, null, batchTs);
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
      var detailResult = await doDetailFetch(tabId, currentPicks, mode);
      results.details = detailResult;
    }

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

// --- Detail fetch (incremental) ---

async function doDetailFetch(tabId, currentPicks, mode) {
  // Step 1: Navigate to articles page and scrape article list
  sendProgress("Loading articles page...");
  await chrome.tabs.update(tabId, { url: SA_ARTICLES_URL });
  await waitForTabLoad(tabId);

  // Wait for article links to appear
  var articlesReady = await waitForArticlesReady(tabId);
  if (!articlesReady.ok) {
    return { fetched: 0, skipped: 0, failed: 0, error: articlesReady.error };
  }

  // Scroll to load more articles
  // Quick: minimal scroll (2-3 pages, ~10s) — covers new picks from recent weeks
  // Full: deep scroll (until bottom, minutes) — covers all historical picks
  if (mode === "full") {
    sendProgress("Full scan: loading all articles...");
    await chrome.tabs.update(tabId, { active: true });
    await sleep(500);
    await scrollToLoadAll(tabId, 200); // Up to 200 scrolls (~8 min max)
    await chrome.tabs.update(tabId, { active: false });
  } else {
    sendProgress("Loading recent articles...");
    await chrome.tabs.update(tabId, { active: true });
    await sleep(500);
    await scrollToLoadAll(tabId, 5); // Quick: just 5 scrolls (~15s)
    await chrome.tabs.update(tabId, { active: false });
  }

  sendProgress("Scraping article list...");
  var articleList = await injectArticlesListScraper(tabId);
  if (!articleList || articleList.error) {
    return { fetched: 0, skipped: 0, failed: 0, error: articleList ? articleList.error : "No articles found" };
  }
  if (!Array.isArray(articleList) || articleList.length === 0) {
    return { fetched: 0, skipped: 0, failed: 0, error: "Empty article list" };
  }

  // Step 2: Send articles + current picks to native host for matching
  var pickSymbols = currentPicks.map(function (p) {
    return { symbol: p.symbol, picked_date: p.picked_date };
  });

  var cacheCheck = await sendNativeMessage2({
    action: "check_detail_cache",
    picks: pickSymbols,
    articles: articleList,
  });

  if (!cacheCheck || cacheCheck.status !== "ok") {
    var cacheError = (cacheCheck && cacheCheck.error) || "check_detail_cache failed";
    return { fetched: 0, skipped: 0, failed: 0, error: cacheError };
  }

  var needDetail = cacheCheck.need_detail || [];
  var noArticle = cacheCheck.no_article || [];
  var totalPicks = pickSymbols.length;
  if (needDetail.length === 0) {
    return { fetched: 0, skipped: totalPicks, failed: 0, no_article: noArticle };
  }

  // Step 3: Fetch each article
  sendProgress("Fetching " + needDetail.length + " detail reports...");

  var fetched = 0, failed = 0;
  for (var i = 0; i < needDetail.length; i++) {
    var item = needDetail[i];
    sendProgress("Detail " + (i + 1) + "/" + needDetail.length + ": " + item.symbol);

    try {
      await chrome.tabs.update(tabId, { url: item.article_url });
      await waitForTabLoad(tabId);
      var ready = await waitForArticleReady(tabId);
      if (!ready.ok) { failed++; continue; }

      var detail = await injectDetailScraper(tabId);
      if (!detail || detail.error) { failed++; continue; }

      var report = formatDetailReport(detail);
      var saveResult = await sendNativeMessage2({
        action: "save_detail",
        symbol: item.symbol,
        picked_date: item.picked_date,
        detail_report: report,
      });
      if (saveResult && saveResult.status === "ok") {
        fetched++;
      } else {
        failed++;
      }
    } catch (err) {
      failed++;
    }

    if (i < needDetail.length - 1) await sleep(2000);
  }

  return { fetched: fetched, skipped: totalPicks - needDetail.length, failed: failed, no_article: noArticle };
}

// --- Manual fetch (user-provided URLs for missing tickers) ---

async function doManualFetch(items) {
  if (items.length === 0) return {};

  var tabId = null;
  var fetched = 0, failed = 0;
  try {
    // Create a tab for fetching
    var tab = await chrome.tabs.create({ url: items[0].url, active: false });
    tabId = tab.id;

    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      sendProgress("Manual: " + item.symbol + " (" + (i + 1) + "/" + items.length + ")");

      try {
        if (i > 0) {
          await chrome.tabs.update(tabId, { url: item.url });
        }
        await waitForTabLoad(tabId);
        var ready = await waitForArticleReady(tabId);
        if (!ready.ok) { failed++; continue; }

        var detail = await injectDetailScraper(tabId);
        if (!detail || detail.error) { failed++; continue; }

        var report = formatDetailReport(detail);

        // Ask native host to resolve picked_date and save
        var saveResult = await sendNativeMessage2({
          action: "save_detail_by_symbol",
          symbol: item.symbol,
          detail_report: report,
        });
        if (saveResult && saveResult.status === "ok") {
          fetched++;
        } else {
          failed++;
        }
      } catch (err) {
        failed++;
      }

      if (i < items.length - 1) await sleep(2000);
    }

    sendProgress("Manual fetch done: " + fetched + " saved");

    // Update storage to clear the no_article list for fetched items
    var storage = await chrome.storage.local.get("lastRefresh");
    if (storage.lastRefresh && storage.lastRefresh.details) {
      var noArt = storage.lastRefresh.details.no_article || [];
      var fetchedSymbols = items.filter(function (_, idx) { return idx < fetched; }).map(function (it) { return it.symbol; });
      storage.lastRefresh.details.no_article = noArt.filter(function (s) { return fetchedSymbols.indexOf(s) < 0; });
      storage.lastRefresh.details.fetched = (storage.lastRefresh.details.fetched || 0) + fetched;
      await chrome.storage.local.set({ lastRefresh: storage.lastRefresh });
    }

    return { fetched: fetched, failed: failed };
  } finally {
    if (tabId) {
      try { chrome.tabs.remove(tabId); } catch (_) {}
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
      return { ok: false, error: "Session expired" };
    if (check.status === "ready") return { ok: true };
    await sleep(500);
  }
  return { ok: false, error: "Timeout waiting for articles page" };
}

function injectArticlesListScraper(tabId) {
  return chrome.scripting
    .executeScript({ target: { tabId }, files: ["scrape_articles_list.js"] })
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
      return { ok: false, error: "Session expired" };
    if (check.status === "paywall")
      return { ok: false, error: "Paywall: " + check.marker };
    if (check.status === "ready") return { ok: true };
    await sleep(500);
  }
  return { ok: false, error: "Timeout waiting for article" };
}

function injectDetailScraper(tabId) {
  return chrome.scripting
    .executeScript({ target: { tabId }, files: ["scrape_detail.js"] })
    .then(function (results) {
      return (results[0] && results[0].result) || { error: "No result" };
    });
}

function formatDetailReport(detail) {
  var parts = [];
  if (detail.title) parts.push("# " + detail.title);
  if (detail.author) parts.push("*Author: " + detail.author + "*");
  if (detail.body_markdown) parts.push(detail.body_markdown);
  return parts.join("\n\n");
}

function sendNativeMessage2(msg) {
  return new Promise(function (resolve) {
    chrome.runtime.sendNativeMessage(NATIVE_HOST, msg, function (response) {
      if (chrome.runtime.lastError) {
        resolve({ status: "error", error: chrome.runtime.lastError.message });
      } else {
        resolve(response || { status: "error", error: "No response" });
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
    },
  });
}
