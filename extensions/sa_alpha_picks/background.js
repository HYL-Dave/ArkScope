// background.js — Service worker for SA Alpha Picks extension
// Orchestrates: open tab → wait for DOM → scrape current → switch to closed → scrape → native messaging → close tab

"use strict";

const SA_CURRENT_URL = "https://seekingalpha.com/alpha-picks/picks/current";
const SA_CLOSED_URL = "https://seekingalpha.com/alpha-picks/picks/removed";
const SA_ARTICLES_URL = "https://seekingalpha.com/alpha-picks/articles";
const SA_MARKET_NEWS_URL = "https://seekingalpha.com/market-news";
const NATIVE_HOST = "com.mindfulrl.sa_alpha_picks";
const TABLE_SELECTOR = "table tbody tr";
const PAYWALL_MARKERS = ["Subscribe to unlock", "Upgrade your plan", "Premium required"];
const MARKET_NEWS_DETAIL_BACKFILL_LIMITS = {
  quick: 0,
  full: 20,
  backfill: 60,
  manual: 0,
};
const MARKET_NEWS_PROFILES = {
  quick: {
    name: "quick",
    maxDetailFetches: 12,
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
  if (msg.action === "refresh_market_news") {
    doMarketNewsRefresh(msg.mode || "quick").then(sendResponse);
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


// --- Market News refresh flow ---

async function doMarketNewsRefresh(mode) {
  const batchTs = new Date().toISOString();
  var profile = getMarketNewsProfile(mode);
  var tabId = null;
  try {
    sendProgress("Opening market news page...");
    const tab = await chrome.tabs.create({ url: SA_MARKET_NEWS_URL, active: false });
    tabId = tab.id;
    await waitForTabLoad(tabId);

    sendProgress("Waiting for market news...");
    var ready = await waitForMarketNewsReady(tabId);
    if (!ready.ok) {
      var failure = { status: "error", error: ready.error, saved: 0, count: 0 };
      await saveMarketNewsState(batchTs, mode, failure);
      return failure;
    }

    await chrome.tabs.update(tabId, { active: true });
    await sleep(randomBetween(profile.listStartMinMs, profile.listStartMaxMs));
    var knownNewsIds = await getMarketNewsRecentIds(profile.recentKnownIdsLimit);
    await scrollMarketNews(tabId, profile, knownNewsIds);
    await chrome.tabs.update(tabId, { active: false });

    sendProgress("Scraping market news...");
    var items = await injectMarketNewsScraper(tabId);
    if (!Array.isArray(items)) items = [];

    sendProgress("Saving " + items.length + " market-news item(s)...");
    var detailBackfillLimit = getMarketNewsDetailBackfillLimit(mode);
    var result = await sendNativeMessage2({
      action: "save_market_news",
      items: items,
      detail_backfill_limit: detailBackfillLimit,
    });
    if (!result || result.status !== "ok") {
      result = { status: "error", error: (result && result.error) || "save_market_news failed", saved: 0 };
    }
    result.count = items.length;

    var needDetail = result.need_detail || [];
    if (profile.maxDetailFetches && needDetail.length > profile.maxDetailFetches) {
      needDetail = needDetail.slice(0, profile.maxDetailFetches);
    }
    var detailFetched = 0;
    var detailFailed = 0;
    result.detail_queued = needDetail.length;
    if (needDetail.length > 0) {
      sendProgress("Fetching " + needDetail.length + " market-news detail page(s)...");
    }
    for (var i = 0; i < needDetail.length; i++) {
      var item = needDetail[i];
      sendProgress("News detail " + (i + 1) + "/" + needDetail.length + ": " + item.news_id);
      try {
        await chrome.tabs.update(tabId, { url: item.url, active: false });
        await waitForTabLoad(tabId);
        await installMarketNewsPageGuards(tabId);
        var saveDetail = await fetchMarketNewsDetailWithRetry(tabId, item, profile);
        if (saveDetail && saveDetail.ok) {
          detailFetched++;
        } else {
          detailFailed++;
        }
      } catch (_) {
        detailFailed++;
      }
      if (i + 1 < needDetail.length) {
        await sleep(randomBetween(profile.detailGapMinMs, profile.detailGapMaxMs));
      }
    }
    result.detail_fetched = detailFetched;
    result.detail_failed = detailFailed;
    await saveMarketNewsState(batchTs, mode, result);
    sendProgress("Market news done!");
    return result;
  } catch (err) {
    var errorResult = { status: "error", error: err.message || String(err), saved: 0, count: 0 };
    await saveMarketNewsState(batchTs, mode, errorResult);
    return errorResult;
  } finally {
    if (tabId) {
      try { chrome.tabs.remove(tabId); } catch (_) { /* tab may already be closed */ }
    }
  }
}

function getMarketNewsDetailBackfillLimit(mode) {
  return MARKET_NEWS_DETAIL_BACKFILL_LIMITS[mode] || MARKET_NEWS_DETAIL_BACKFILL_LIMITS.quick;
}

function getMarketNewsProfile(mode) {
  return MARKET_NEWS_PROFILES[mode] || MARKET_NEWS_PROFILES.quick;
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

// --- Detail fetch (incremental) ---

async function doDetailFetch(tabId, currentPicks, mode) {
  // ── Step 1: Load articles page + scroll ──
  sendProgress("Loading articles page...");
  await chrome.tabs.update(tabId, { url: SA_ARTICLES_URL });
  await waitForTabLoad(tabId);

  var articlesReady = await waitForArticlesReady(tabId);
  if (!articlesReady.ok) {
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
    await scrollToLoadAll(tabId, 200);
  } else {
    sendProgress("Loading recent articles...");
    await scrollToLoadAll(tabId, 5);
  }
  await chrome.tabs.update(tabId, { active: false });

  // Scrape article list (ALL articles, not just ticker-tagged)
  sendProgress("Scraping article list...");
  var articleList = await injectArticlesListScraper(tabId);
  if (!articleList || articleList.error) {
    return { fetched: 0, failed: 0, error: articleList ? articleList.error : "No articles found" };
  }
  if (!Array.isArray(articleList) || articleList.length === 0) {
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
    await scrollToLoadAll(tabId, 200);
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
    var metaError = (metaResult && metaResult.error) || "save_articles_meta failed";
    return { fetched: 0, failed: 0, error: metaError };
  }

  var needContent = metaResult.need_content || [];
  var needComments = metaResult.need_comments || [];
  var unresolvedSymbols = metaResult.unresolved_symbols || [];

  // ── Step 3: Fetch article content + comments for need_content ──
  var fetched = 0, failed = 0;
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
      await waitForTabLoad(tabId);
      var ready = await waitForArticleReady(tabId);
      if (!ready.ok) { failed++; continue; }

      // Scrape body
      var detail = await injectDetailScraper(tabId);
      if (!detail || detail.error) { failed++; continue; }

      // Scroll down to comments section + load all comments
      // This naturally provides human-like dwell time (10-30s per page)
      await scrollToComments(tabId, {
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
      });
      if (saveResult && saveResult.ok) {
        fetched++;
      } else {
        failed++;
      }
    } catch (err) {
      failed++;
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
      await waitForTabLoad(tabId);
      await waitForArticleReady(tabId);

      // Scroll to load comments (natural delay)
      await scrollToComments(tabId, {
        mode: scrollMode,
        articleId: cItem.article_id,
      });

      var cResult = await injectCommentsScraper(tabId);
      var cComments = (cResult && cResult.comments) || [];

      await sendNativeMessage2({
        action: "save_comments_only",
        article_id: cItem.article_id,
        comments: cComments,
      });
      commentsRefreshed++;
    } catch (err) {
      // Best effort for comments refresh
    }
  }

  // ── Step 5: Audit unresolved (full-text fallback) ──
  sendProgress("Auditing unresolved picks...");
  var auditResult = await sendNativeMessage2({ action: "audit_unresolved" });
  if (auditResult && auditResult.status === "ok") {
    unresolvedSymbols = auditResult.unresolved_symbols || [];
  }

  return {
    articles_saved: metaResult.saved || 0,
    fetched: fetched,
    failed: failed,
    comments_refreshed: commentsRefreshed,
    unresolved_symbols: unresolvedSymbols,
  };
}

// --- Manual fetch (user-provided URLs for missing tickers) ---

async function doManualFetch(items) {
  if (items.length === 0) return {};

  var tabId = null;
  var fetched = 0, failed = 0;
  var succeededSymbols = [];
  try {
    // Create a tab for fetching
    var tab = await chrome.tabs.create({ url: items[0].url, active: false });
    tabId = tab.id;

    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      sendProgress("Manual: " + item.symbol + " (" + (i + 1) + "/" + items.length + ")");

      try {
        if (i > 0) {
          await chrome.tabs.update(tabId, { url: item.url, active: true });
        }
        await waitForTabLoad(tabId);
        var ready = await waitForArticleReady(tabId);
        if (!ready.ok) { failed++; continue; }

        // Extract article_id from URL
        var idMatch = item.url.match(/\/articles\/(\d+)/);
        var articleId = idMatch ? idMatch[1] : null;

        var detail = await injectDetailScraper(tabId);
        if (!detail || detail.error) { failed++; continue; }

        // Scroll to load comments (v3 path)
        await scrollToComments(tabId, {
          mode: "manual",
          articleId: articleId || item.symbol || "manual",
        });
        var commentsResult = await injectCommentsScraper(tabId);
        var comments = (commentsResult && commentsResult.comments) || [];

        var report = formatDetailReport(detail);

        if (articleId) {
          // v3 path: save to sa_articles + auto-sync to picks
          // Use publish date from article page (scrape_detail.js extracts it)
          var pubDate = detail.publish_date || null;
          // First ensure article metadata exists (with date)
          await sendNativeMessage2({
            action: "save_articles_meta",
            mode: "full",
            articles: [{
              article_id: articleId,
              url: item.url,
              title: detail.title || item.symbol + " analysis",
              ticker: item.symbol,
              date: pubDate,
              article_type: "analysis",
            }],
          });
          var saveResult = await sendNativeMessage2({
            action: "save_article_content",
            article_id: articleId,
            body_markdown: report,
            comments: comments,
          });
          if (saveResult && saveResult.ok) {
            fetched++;
            succeededSymbols.push(item.symbol);
          } else {
            failed++;
          }
        } else {
          // Fallback: legacy save_detail_by_symbol
          var saveResult = await sendNativeMessage2({
            action: "save_detail_by_symbol",
            symbol: item.symbol,
            detail_report: report,
          });
          if (saveResult && saveResult.status === "ok") {
            fetched++;
            succeededSymbols.push(item.symbol);
          } else {
            failed++;
          }
        }
      } catch (err) {
        failed++;
      }
    }

    sendProgress("Manual fetch done: " + fetched + " saved");

    // Update storage to clear unresolved_symbols for fetched items
    var storage = await chrome.storage.local.get("lastRefresh");
    if (storage.lastRefresh && storage.lastRefresh.details) {
      var unresolved = storage.lastRefresh.details.unresolved_symbols || storage.lastRefresh.details.no_article || [];
      // Only clear symbols that actually succeeded (not all attempted)
      storage.lastRefresh.details.unresolved_symbols = unresolved.filter(function (s) { return succeededSymbols.indexOf(s) < 0; });
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

function getCommentScrollProfile(mode) {
  return COMMENT_SCROLL_PROFILES[mode] || COMMENT_SCROLL_PROFILES.quick;
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
  var staleCount = 0;
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

        window.scrollBy(0, window.innerHeight);
        return { comments: commentEls.length, atBottom: atBottom, clicked: clicked };
      },
    });
    var check = result[0] && result[0].result;
    rounds++;

    if (check && check.comments > bestCount) {
      bestCount = check.comments;
    }

    if (check && check.atBottom && !check.clicked) {
      staleCount++;
      if (staleCount >= profile.staleRounds) {
        stopReason = bestCount > 0 ? "stale" : "empty";
        break;
      }
    } else {
      staleCount = 0;
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
    if (!check || check.status === "login_redirect") return { ok: false, error: "Session expired" };
    if (check.status === "ready") return { ok: true, count: check.count };
    await sleep(500);
  }
  return { ok: false, error: "Timeout waiting for market news" };
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
      return { ok: false, error: "Session expired" };
    }
    if (check.status === "paywall") {
      return { ok: false, error: "Paywall: " + check.marker };
    }
    if (check.status === "ready") return { ok: true };
    await sleep(500);
  }
  return { ok: false, error: "Timeout waiting for market news detail" };
}

async function fetchMarketNewsDetailWithRetry(tabId, item, profile) {
  for (var attempt = 0; attempt < 2; attempt++) {
    if (attempt > 0) {
      sendProgress("Retrying news detail: " + item.news_id);
      await chrome.tabs.reload(tabId);
      await waitForTabLoad(tabId);
      await installMarketNewsPageGuards(tabId);
      await sleep(randomBetween(profile.retryDelayMinMs, profile.retryDelayMaxMs));
    }

    var detailReady = await waitForMarketNewsDetailReady(tabId);
    if (!detailReady.ok) {
      continue;
    }

    await sleep(randomBetween(
      profile.detailReadyDwellMinMs,
      profile.detailReadyDwellMaxMs
    ));

    var detail = await injectDetailScraper(tabId);
    if (!detail || detail.error) {
      continue;
    }

    var report = formatDetailReport(detail);
    if (!report || report.trim().length < 40) {
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
  }
  return { ok: false };
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


async function saveMarketNewsState(batchTs, mode, result) {
  await chrome.storage.local.set({
    lastMarketNewsRefresh: {
      batch_ts: batchTs,
      mode: mode || "quick",
      result: result,
    },
  });
}
