// scrape.js — Injected into SA Alpha Picks page by chrome.scripting.executeScript
// Pure DOM operations, no chrome.* API usage.
// Returns: array of pick objects
//
// Real SA DOM structure (as of 2026-03):
//
// Current page (/alpha-picks/picks/current):
//   Header: Company | Symbol | Picked | Return | Sector | Rating | Holding% | (link)
//   Data may include a leading Company cell before Symbol.
//
// Removed page (/alpha-picks/picks/removed):
//   Header: Company | Symbol | Picked | Closed | Return | Sector | Rating | (link)
//   Data may include a leading Company cell before Symbol.
//
// Detection: URL path (most reliable)

(function () {
  "use strict";

  var isRemovedPage = location.pathname.includes("/removed");

  var visibleRowCount = document.querySelectorAll("table tbody tr").length;
  if (visibleRowCount === 0) {
    visibleRowCount = document.querySelectorAll('[role="row"]').length;
  }
  var rows = collectCandidateRows();
  var picks = [];

  for (var i = 0; i < rows.length; i++) {
    var cells = collectCells(rows[i]);
    var texts = [];
    for (var j = 0; j < cells.length; j++) {
      texts.push(cells[j].innerText.trim());
    }

    var link = rows[i].querySelector("a[href]");
    var detailUrl = link ? link.href : null;
    var pick;

    var symbolIndex = findSymbolIndex(texts);
    if (symbolIndex < 0) continue;
    var symbol = (texts[symbolIndex] || "").toUpperCase();

    if (isRemovedPage) {
      pick = {
        company: "",
        symbol: symbol,
        picked_date: parseDate(texts[symbolIndex + 1]),
        closed_date: parseDate(texts[symbolIndex + 2]),
        return_pct: parsePct(texts[symbolIndex + 3]),
        sector: texts[symbolIndex + 4] || null,
        sa_rating: parseRating(texts[symbolIndex + 5]),
        holding_pct: null,
        detail_url: detailUrl,
        raw_data: { cells: texts, detail_url: detailUrl },
      };
    } else {
      pick = {
        company: "",
        symbol: symbol,
        picked_date: parseDate(texts[symbolIndex + 1]),
        return_pct: parsePct(texts[symbolIndex + 2]),
        sector: texts[symbolIndex + 3] || null,
        sa_rating: parseRating(texts[symbolIndex + 4]),
        holding_pct: parsePct(texts[symbolIndex + 5]),
        detail_url: detailUrl,
        raw_data: { cells: texts, detail_url: detailUrl },
      };
    }

    picks.push(pick);
  }

  if (visibleRowCount > 0 && picks.length === 0) {
    throw new Error("Alpha Picks rows were present but none could be parsed");
  }
  return picks;

  // --- Helpers ---

  function collectCandidateRows() {
    var tableRows = Array.prototype.slice.call(document.querySelectorAll("table tbody tr"));
    if (tableRows.length) return tableRows;
    var roleRows = Array.prototype.slice.call(document.querySelectorAll('[role="row"]'));
    return roleRows.filter(function (row) {
      var cells = collectCells(row);
      var texts = Array.prototype.map.call(cells, function (cell) {
        return (cell.innerText || "").trim();
      });
      return findSymbolIndex(texts) >= 0;
    });
  }

  function collectCells(row) {
    var cells = row.querySelectorAll("td");
    if (cells.length) return cells;
    return row.querySelectorAll('[role="cell"], [role="gridcell"]');
  }

  function findSymbolIndex(texts) {
    for (var i = 0; i + 1 < texts.length; i++) {
      var candidate = String(texts[i] || "").trim().toUpperCase();
      if (!/^[A-Z][A-Z.]{0,9}$/.test(candidate)) continue;
      if (parseDate(texts[i + 1])) return i;
    }
    return -1;
  }

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
