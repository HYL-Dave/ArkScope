// scrape.js — Injected into SA Alpha Picks page by chrome.scripting.executeScript
// Pure DOM operations, no chrome.* API usage.
// Returns: array of pick objects
//
// Real SA DOM structure (as of 2026-03):
//
// Current page (/alpha-picks/picks/current):
//   Columns: Symbol | Picked | Return% | Sector | Rating | Holding% | (link)
//
// Removed page (/alpha-picks/picks/removed):
//   Columns: Company | Symbol | Picked | Closed | Return% | Sector | Rating | (link)

(function () {
  "use strict";

  // Detect page type from table headers
  const headers = Array.from(document.querySelectorAll("table thead th"))
    .map((th) => th.innerText.trim().toLowerCase());
  const hasCompanyCol = headers.length > 0 && headers[0].startsWith("company");

  const rows = document.querySelectorAll("table tbody tr");
  const picks = [];

  rows.forEach((row) => {
    const cells = row.querySelectorAll("td");
    const texts = Array.from(cells).map((c) => c.innerText.trim());
    const link = row.querySelector("a[href]");
    const detailUrl = link ? link.href : null;

    var pick;
    if (hasCompanyCol) {
      // Removed page: Company | Symbol | Picked | Closed | Return% | Sector | Rating | (link)
      if (texts.length < 6) return;
      var symbol = (texts[1] || "").toUpperCase();
      if (!symbol || symbol.length > 10) return;
      pick = {
        company: texts[0] || "",
        symbol: symbol,
        picked_date: parseDate(texts[2]),
        closed_date: parseDate(texts[3]),
        return_pct: parsePct(texts[4]),
        sector: texts[5] || null,
        sa_rating: parseRating(texts[6]),
        holding_pct: null,
        detail_url: detailUrl,
        raw_data: { cells: texts, detail_url: detailUrl },
      };
    } else {
      // Current page: Symbol | Picked | Return% | Sector | Rating | Holding% | (link)
      if (texts.length < 5) return;
      var symbol = (texts[0] || "").toUpperCase();
      if (!symbol || symbol.length > 10) return;
      pick = {
        company: "",
        symbol: symbol,
        picked_date: parseDate(texts[1]),
        return_pct: parsePct(texts[2]),
        sector: texts[3] || null,
        sa_rating: parseRating(texts[4]),
        holding_pct: parsePct(texts[5]),
        detail_url: detailUrl,
        raw_data: { cells: texts, detail_url: detailUrl },
      };
    }

    picks.push(pick);
  });

  return picks;

  // --- Helpers ---

  function parseDate(text) {
    if (!text) return null;
    // M/D/YYYY → YYYY-MM-DD
    var mdy = text.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
    if (mdy) {
      return mdy[3] + "-" + mdy[1].padStart(2, "0") + "-" + mdy[2].padStart(2, "0");
    }
    // ISO format
    if (/^\d{4}-\d{2}-\d{2}/.test(text)) {
      return text.substring(0, 10);
    }
    return null;
  }

  function parsePct(text) {
    if (!text) return null;
    // Remove commas (e.g. "1,571.37%")
    var cleaned = text.replace(/,/g, "");
    var m = cleaned.match(/([+-]?\d+\.?\d*)%/);
    return m ? parseFloat(m[1]) : null;
  }

  function parseRating(text) {
    if (!text) return null;
    var upper = text.trim().toUpperCase();
    var ratings = ["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"];
    return ratings.indexOf(upper) >= 0 ? upper : null;
  }
})();