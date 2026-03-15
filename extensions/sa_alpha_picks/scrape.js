// scrape.js — Injected into SA Alpha Picks page by chrome.scripting.executeScript
// Pure DOM operations, no chrome.* API usage.
// Returns: array of pick objects
//
// Real SA DOM structure (as of 2026-03):
//   URL: /alpha-picks/picks/current or /alpha-picks/picks/removed
//   Selector: table tbody tr
//   Columns: Symbol | Picked Date | Return% | Sector | Rating | Holding% | (link)
//   Date format: M/D/YYYY (e.g. "3/2/2026")
//   No "Company" column.

(function () {
  "use strict";

  const rows = document.querySelectorAll("table tbody tr");
  const picks = [];

  rows.forEach((row) => {
    const cells = row.querySelectorAll("td");
    if (cells.length < 5) return;

    const texts = Array.from(cells).map((c) => c.innerText.trim());
    const link = row.querySelector("a[href]");
    const detailUrl = link ? link.href : null;

    // Fixed column order: Symbol, Picked Date, Return%, Sector, Rating, Holding%
    const symbol = (texts[0] || "").toUpperCase();
    if (!symbol || symbol.length > 10) return; // skip header-like rows

    const pick = {
      company: "",  // SA doesn't show company name in table
      symbol: symbol,
      picked_date: parseDate(texts[1]),
      return_pct: parsePct(texts[2]),
      sector: texts[3] || null,
      sa_rating: parseRating(texts[4]),
      holding_pct: parsePct(texts[5]),
      detail_url: detailUrl,
      raw_data: { cells: texts, detail_url: detailUrl },
    };

    picks.push(pick);
  });

  return picks;

  // --- Helpers ---

  function parseDate(text) {
    if (!text) return null;
    // M/D/YYYY → YYYY-MM-DD
    const mdy = text.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
    if (mdy) {
      return mdy[3] + "-" + mdy[1].padStart(2, "0") + "-" + mdy[2].padStart(2, "0");
    }
    // ISO format: 2025-01-15
    if (/^\d{4}-\d{2}-\d{2}/.test(text)) {
      return text.substring(0, 10);
    }
    // Month DD, YYYY: Jan 15, 2025
    const m = text.match(/^([A-Z][a-z]{2})\s+(\d{1,2}),?\s+(\d{4})/);
    if (m) {
      const months = {
        Jan: "01", Feb: "02", Mar: "03", Apr: "04",
        May: "05", Jun: "06", Jul: "07", Aug: "08",
        Sep: "09", Oct: "10", Nov: "11", Dec: "12",
      };
      const month = months[m[1]];
      if (month) return m[3] + "-" + month + "-" + m[2].padStart(2, "0");
    }
    return null;
  }

  function parsePct(text) {
    if (!text) return null;
    const m = text.match(/([+-]?\d+\.?\d*)%/);
    return m ? parseFloat(m[1]) : null;
  }

  function parseRating(text) {
    if (!text) return null;
    const upper = text.trim().toUpperCase();
    const ratings = new Set(["STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL"]);
    return ratings.has(upper) ? upper : null;
  }
})();