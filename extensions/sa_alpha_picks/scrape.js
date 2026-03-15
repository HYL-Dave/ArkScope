// scrape.js — Injected into SA Alpha Picks page by chrome.scripting.executeScript
// Pure DOM operations, no chrome.* API usage.
// Returns: array of pick objects
//
// Real SA DOM structure (as of 2026-03):
//
// Current page (/alpha-picks/picks/current):
//   Header: Company | Symbol | Picked | Return | Sector | Rating | Holding% | (link)
//   Data:   Symbol  | Picked | Return%| Sector | Rating | Holding% | (link)
//   Note: header has Company column but data rows do NOT
//
// Removed page (/alpha-picks/picks/removed):
//   Header: Company | Symbol | Picked | Closed | Return | Sector | Rating | (link)
//   Data:   Symbol  | Picked | Closed | Return%| Sector | Rating | (link)
//   Note: same quirk — header has Company but data rows do NOT
//
// Detection: URL path (most reliable)

(function () {
  "use strict";

  var isRemovedPage = location.pathname.includes("/removed");

  var rows = document.querySelectorAll("table tbody tr");
  var picks = [];

  for (var i = 0; i < rows.length; i++) {
    var cells = rows[i].querySelectorAll("td");
    var texts = [];
    for (var j = 0; j < cells.length; j++) {
      texts.push(cells[j].innerText.trim());
    }

    var link = rows[i].querySelector("a[href]");
    var detailUrl = link ? link.href : null;
    var pick;

    if (isRemovedPage) {
      // Removed data rows (no Company td despite header having it):
      // Symbol | Picked | Closed | Return% | Sector | Rating | (link)
      if (texts.length < 6) continue;
      var symbol = (texts[0] || "").toUpperCase();
      if (!symbol || symbol.length > 10) continue;
      pick = {
        company: "",
        symbol: symbol,
        picked_date: parseDate(texts[1]),
        closed_date: parseDate(texts[2]),
        return_pct: parsePct(texts[3]),
        sector: texts[4] || null,
        sa_rating: parseRating(texts[5]),
        holding_pct: null,
        detail_url: detailUrl,
        raw_data: { cells: texts, detail_url: detailUrl },
      };
    } else {
      // Current data rows (no Company td despite header having it):
      // Symbol | Picked | Return% | Sector | Rating | Holding% | (link)
      if (texts.length < 5) continue;
      var symbol = (texts[0] || "").toUpperCase();
      if (!symbol || symbol.length > 10) continue;
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
  }

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