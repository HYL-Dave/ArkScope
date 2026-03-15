// scrape.js — Injected into SA Alpha Picks page by chrome.scripting.executeScript
// Pure DOM operations, no chrome.* API usage.
// Returns: array of pick objects

(function () {
  "use strict";

  const TABLE_SELECTOR = '[data-testid="portfolio-table"] tbody tr';

  const rows = document.querySelectorAll(TABLE_SELECTOR);
  const picks = [];

  rows.forEach((row) => {
    const cells = row.querySelectorAll("td");
    if (cells.length < 6) return;

    const texts = Array.from(cells).map((c) => c.innerText.trim());
    const link = row.querySelector("a[href]");

    const detailUrl = link ? link.href : null;
    const pick = {
      company: texts[0] || "",
      symbol: extractSymbol(texts),
      picked_date: extractDate(texts),
      return_pct: extractPct(texts),
      sector: extractSector(texts),
      sa_rating: extractRating(texts),
      holding_pct: extractHoldingPct(texts),
      detail_url: detailUrl,
      raw_data: { cells: texts, detail_url: detailUrl },
    };

    if (pick.symbol) {
      picks.push(pick);
    }
  });

  return picks;

  // --- Helper functions (same logic as Python _extract_* methods) ---

  function extractSymbol(texts) {
    for (const t of texts) {
      const cleaned = t.trim().toUpperCase();
      if (cleaned.length >= 1 && cleaned.length <= 5 && /^[A-Z]+$/.test(cleaned)) {
        return cleaned;
      }
    }
    return "";
  }

  function extractDate(texts) {
    for (const t of texts) {
      // ISO format: 2025-01-15
      if (/^\d{4}-\d{2}-\d{2}/.test(t)) {
        return t.substring(0, 10);
      }
      // Month DD, YYYY: Jan 15, 2025
      const m = t.match(/^([A-Z][a-z]{2})\s+(\d{1,2}),?\s+(\d{4})/);
      if (m) {
        const months = {
          Jan: "01", Feb: "02", Mar: "03", Apr: "04",
          May: "05", Jun: "06", Jul: "07", Aug: "08",
          Sep: "09", Oct: "10", Nov: "11", Dec: "12",
        };
        const month = months[m[1]];
        if (month) {
          const day = m[2].padStart(2, "0");
          return m[3] + "-" + month + "-" + day;
        }
      }
    }
    return null;
  }

  function extractPct(texts) {
    for (const t of texts) {
      const m = t.match(/([+-]?\d+\.?\d*)%/);
      if (m) {
        return parseFloat(m[1]);
      }
    }
    return null;
  }

  function extractSector(texts) {
    const sectors = [
      "Technology", "Healthcare", "Financial", "Consumer", "Energy",
      "Industrial", "Communication", "Materials", "Utilities", "Real Estate",
    ];
    for (const t of texts) {
      for (const s of sectors) {
        if (t.toLowerCase().includes(s.toLowerCase())) {
          return t.trim();
        }
      }
    }
    return null;
  }

  function extractRating(texts) {
    const ratings = new Set([
      "STRONG BUY", "BUY", "HOLD", "SELL", "STRONG SELL",
    ]);
    for (const t of texts) {
      const upper = t.trim().toUpperCase();
      if (ratings.has(upper)) {
        return upper;
      }
    }
    return null;
  }

  function extractHoldingPct(texts) {
    const pcts = [];
    for (const t of texts) {
      const m = t.match(/(\d+\.?\d*)%/);
      if (m) {
        pcts.push(parseFloat(m[1]));
      }
    }
    // Last percentage is holding % (return % comes first)
    return pcts.length >= 2 ? pcts[pcts.length - 1] : null;
  }
})();
