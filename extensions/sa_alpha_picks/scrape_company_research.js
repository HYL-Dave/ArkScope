/* Explicit current-page capture; never navigate, click, subscribe or call private APIs. */
(async function () {
  "use strict";
  var startUrl = location.href;
  var startX = window.scrollX;
  var startY = window.scrollY;
  var interrupted = false;
  var listeners = ["wheel", "touchstart", "keydown", "click", "input", "change"];
  var interrupt = function () { interrupted = true; };
  var deadline = Date.now() + 90000;
  function fail(code) { throw new Error(code); }
  function text(node) { return (node.innerText || node.textContent || "").trim().replace(/\s+/g, " "); }
  function visible(node) {
    for (var e = node; e && e.nodeType === 1; e = e.parentElement) {
      var style = getComputedStyle(e);
      if (e.hidden || e.getAttribute("aria-hidden") === "true" || style.display === "none" || style.visibility === "hidden") return false;
    }
    return true;
  }
  function all(root, selector) { return Array.from(root.querySelectorAll(selector)).filter(visible); }
  function one(root, selector) {
    var matches = all(root, selector);
    if (matches.length !== 1) fail("sa_company_layout_unrecognized");
    return matches[0];
  }
  function guard() {
    if (interrupted) fail("sa_company_capture_interrupted");
    if (location.href !== startUrl) fail("sa_company_page_changed");
    if (main && (!main.isConnected || one(document, "main") !== main)) fail("sa_company_page_changed");
    if (/access.*denied|verify.*human|just a moment/i.test(document.title)
        || all(document, 'iframe[title="Human verification challenge"]').length) fail("sa_company_human_verification_required");
    if (Date.now() >= deadline) fail("sa_company_dom_not_ready");
  }
  function cellText(cell) {
    if (cell.querySelector('a[href*="/subscribe"], [data-test-id*="locked"]')) fail("sa_company_access_restricted");
    var result = text(cell);
    if (!result) fail("sa_company_dom_not_ready");
    return result;
  }
  function readTable(section, id) {
    if (section.matches('[aria-busy="true"]') || section.querySelector('[aria-busy="true"], [data-test-id*="skeleton"]')) fail("sa_company_dom_not_ready");
    // Horizontal arrows reveal already-present columns; an unknown page control cannot certify completeness.
    if (all(section, 'nav[aria-label*="agination"], [data-test-id*="pagination"]').length
        || all(section, "button,a[rel=next]").some(function (e) {
          return [text(e), e.getAttribute("aria-label") || ""].some(function (label) {
            return /^(next( page)?|previous page|load more|show more)$/i.test(label);
          }) || e.getAttribute("rel") === "next";
        })) fail("sa_company_pagination_unverified");
    var table = one(section, 'table[data-test-id="table"]');
    if (!table.tHead || table.tHead.rows.length !== 1 || table.tBodies.length !== 1 || table.querySelector("table")) fail("sa_company_layout_unrecognized");
    var headerCells = Array.from(table.tHead.rows[0].cells);
    var scrolling = headerCells.length && headerCells[headerCells.length - 1].getAttribute("data-test-id") === "scroll-controls-header";
    var headers = headerCells.slice(0, scrolling ? -1 : undefined).map(function (cell) {
      if (cell.tagName !== "TH" || cell.colSpan !== 1 || cell.rowSpan !== 1) fail("sa_company_layout_unrecognized");
      return { id: cell.getAttribute("data-test-id"), label: cellText(cell) };
    });
    if (headers.length < 2) fail("sa_company_dom_not_ready");
    var rows = Array.from(table.tBodies[0].rows).filter(visible).map(function (row) {
      var cells = Array.from(row.cells);
      if (cells.length !== headerCells.length) fail("sa_company_dom_not_ready");
      if (cells.some(function (cell) { return cell.colSpan !== 1 || cell.rowSpan !== 1; })) fail("sa_company_layout_unrecognized");
      if (scrolling && text(cells[cells.length - 1])) fail("sa_company_layout_unrecognized");
      if (cells[0].tagName === "TH" && cells[0].getAttribute("scope") !== "row") fail("sa_company_layout_unrecognized");
      if (cells.slice(1).some(function (c) { return c.tagName !== "TD"; })) fail("sa_company_layout_unrecognized");
      return { label: cellText(cells[0]), values: cells.slice(1, scrolling ? -1 : undefined).map(cellText) };
    });
    if (!rows.length) fail("sa_company_dom_not_ready");
    return { id: id, headers: headers, rows: rows };
  }
  async function readyTable(main, id) {
    var selector = 'section[data-test-id="' + id + '"]';
    var section = one(main, selector);
    section.scrollIntoView({ block: "center", behavior: "instant" });
    var until = Math.min(deadline, Date.now() + 10000);
    var last = null;
    while (Date.now() < until) {
      guard();
      section = one(main, selector);
      try {
        var value = readTable(section, id);
        var signature = JSON.stringify(value);
        if (signature === last) return value;
        last = signature;
      } catch (error) {
        if (error.message !== "sa_company_dom_not_ready") throw error;
        last = null;
      }
      await new Promise(function (resolve) { setTimeout(resolve, 300); });
    }
    fail("sa_company_dom_not_ready");
  }
  try {
    guard();
    var url = new URL(location.href);
    var match = /^\/symbol\/([A-Z][A-Z0-9.-]{0,19})\/(valuation\/metrics|peers\/comparison|earnings\/estimates|earnings\/revisions)\/?$/.exec(url.pathname);
    if (url.origin !== "https://seekingalpha.com" || !match || url.search) fail("sa_company_page_unsupported");
    var ticker = match[1];
    var dataset = { "valuation/metrics": "valuation", "peers/comparison": "peers", "earnings/estimates": "estimates", "earnings/revisions": "revisions" }[match[2]];
    var main = one(document, "main");
    var heading = text(one(main, "h1"));
    if (!heading.startsWith(ticker + " - ") || !document.title.includes("(" + ticker + ")")) fail("sa_company_identity_mismatch");
    var peers = ["profile", "ratings", "quant-rankings", "quant-factor-grades", "trading", "total-return", "dividends",
      "dividend-grades", "valuation", "growth", "profitability", "ownership", "performance", "risk", "eps-revisions",
      "income-statement-ttm", "balance-sheet-mrq", "cash-flow-statement-ttm"];
    var ids = dataset === "peers" ? peers.map(function (id) { return "card-container-" + id; })
      : dataset === "valuation" ? ["card-container-valuation-metrics"]
        : dataset === "estimates" ? ["consensus-normalized-estimates-card", "consensus-revenues-estimates-card"]
          : ["consensus-eps-revision-trend-card", "consensus-revenue-revision-trend-card"];
    var view = dataset === "peers" || dataset === "valuation" ? "snapshot" : "annual";
    var annualHeading = dataset === "estimates" ? "Annual Estimates Summary" : "Annual Estimates Revisions";
    if (view === "annual" && !all(main, "h2").some(function (e) { return text(e).toLowerCase() === annualHeading.toLowerCase(); })) fail("sa_company_view_unsupported");
    listeners.forEach(function (type) { document.addEventListener(type, interrupt, { capture: true, passive: true }); });
    var tables = [];
    for (var id of ids) tables.push(await readyTable(main, id));
    guard();
    if (text(one(main, "h1")) !== heading) fail("sa_company_page_changed");
    // Re-read after scrolling: a virtualized-away or changed earlier table is not a complete page.
    var finalTables = ids.map(function (id) { return readTable(one(main, 'section[data-test-id="' + id + '"]'), id); });
    if (JSON.stringify(finalTables) !== JSON.stringify(tables)) fail("sa_company_page_changed");
    if (dataset !== "valuation") {
      var actualIds = all(main, "table").map(function (t) { return t.closest("section") && t.closest("section").getAttribute("data-test-id"); });
      if (JSON.stringify(actualIds) !== JSON.stringify(ids)) fail("sa_company_layout_unrecognized");
    }
    return { status: "ok", capture: {
      schema_version: 2, layout_id: "sa.company-research.v1", source_url: url.origin + url.pathname.replace(/\/$/, ""),
      ticker: ticker, title: document.title, heading: heading, captured_at: new Date().toISOString(), dataset: dataset, view: view,
      tables: finalTables, loading: { strategy: "bounded_section_scroll", pagination: "no_pagination_controls" },
    } };
  } catch (error) {
    return { status: "error", error_code: error && /^sa_company_[a-z_]+$/.test(error.message) ? error.message : "sa_company_layout_unrecognized" };
  } finally {
    listeners.forEach(function (type) { document.removeEventListener(type, interrupt, true); });
    if (!interrupted && location.href === startUrl) window.scrollTo({ left: startX, top: startY, behavior: "instant" });
  }
})();
