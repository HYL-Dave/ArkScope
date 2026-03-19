// scrape_articles_list.js — Injected into SA Alpha Picks articles page
// Extracts article list with ticker symbols and URLs.
// Returns: array of { ticker, url, title, date } or { error }
//
// Card text pattern (from DOM):
//   {Title}\n{Date}{TICKER}{N Comments}\n{preview...}
//   e.g. "AI And Cloud...\nMar. 16, 2026LITE34 Comments\nLumentum..."
//
// General articles (recaps/reviews) have no ticker — excluded.

(function () {
  "use strict";

  // Find all article links (deduplicate by URL)
  var links = document.querySelectorAll('a[href*="/alpha-picks/articles/"]');
  var seen = {};
  var articles = [];

  for (var i = 0; i < links.length; i++) {
    var a = links[i];
    var href = a.href.split("#")[0]; // Strip tracking fragment
    var text = a.innerText.trim();

    // Skip non-title links (empty text, "N Comments", very short)
    if (!text || text.length < 15 || /^\d+\s*Comments?$/i.test(text)) continue;
    // Skip duplicates
    if (seen[href]) continue;
    seen[href] = true;

    // Find the enclosing <article> card (SA uses <article> for each entry)
    var card = a.closest("article");
    if (!card) {
      // Fallback: walk up to find a container with date + ticker info
      card = a.parentElement;
      while (card && card.innerText.length < 100) card = card.parentElement;
    }
    var cardText = card ? card.innerText : "";

    // Extract date: "Mar. 16, 2026" or similar
    var dateMatch = cardText.match(
      /(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{1,2},\s+\d{4}/
    );
    var date = dateMatch ? dateMatch[0] : null;

    // Extract ticker: appears between date and "N Comments"
    // Pattern: "Mar. 16, 2026LITE34 Comments" or "Mar. 16, 2026\nLITE\n34 Comments"
    var ticker = null;
    if (date) {
      var afterDate = cardText.substring(cardText.indexOf(date) + date.length);
      // Match ticker with optional exchange suffix and optional comment count
      // Patterns: "LITE34 Comments", "SSRMSSRM:CA22 Comments", "UBER" (no comments)
      var tickerMatch = afterDate.match(/^\s*([A-Z][A-Z0-9.]*(?::[A-Z]{1,4})?)\s*\d+\s*Comments?/);
      if (!tickerMatch) {
        // Fallback: ticker at end with no comment count (e.g. oldest articles)
        tickerMatch = afterDate.match(/^\s*([A-Z][A-Z0-9.]{0,9})\s*$/);
      }
      if (tickerMatch) {
        ticker = tickerMatch[1];
        // Strip exchange suffix for matching (KGCK:CA → KGCK, CLS:CA → CLS)
        var colonIdx = ticker.indexOf(":");
        if (colonIdx > 0) ticker = ticker.substring(0, colonIdx);
      }
    }

    // Only include articles with a ticker (skip recaps/reviews)
    if (ticker) {
      articles.push({
        ticker: ticker,
        url: href,
        title: text.substring(0, 120),
        date: date,
      });
    }
  }

  if (articles.length === 0) {
    return {
      error: "No ticker-linked articles found",
      total_links: links.length,
    };
  }

  return articles;
})();
