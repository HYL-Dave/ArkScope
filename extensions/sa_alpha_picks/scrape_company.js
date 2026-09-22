// Capture the displayed financial table only. No navigation, fetch or page mutation.
(function () {
  "use strict";

  function fail(code) { throw new Error(code); }
  function text(element) {
    return (element && (element.innerText || element.textContent) || "").trim().replace(/\s+/g, " ");
  }
  function visible(element) {
    for (var node = element; node; node = node.parentElement) {
      if (node.hidden || node.getAttribute("aria-hidden") === "true"
          || getComputedStyle(node).display === "none" || getComputedStyle(node).visibility === "hidden") return false;
    }
    return true;
  }
  function one(parent, selector) {
    var matches = Array.from(parent.querySelectorAll(selector)).filter(visible);
    if (matches.length !== 1) fail("sa_company_layout_unrecognized");
    return matches[0];
  }

  try {
    var url = new URL(location.href);
    var match = /^\/symbol\/([A-Z][A-Z0-9.-]{0,19})\/(income-statement|balance-sheet|cash-flow-statement)\/?$/.exec(url.pathname);
    if (url.origin !== "https://seekingalpha.com" || !match) fail("sa_company_page_unsupported");
    var rateLimitMessage = /too many requests|rate limit exceeded/i;
    if (rateLimitMessage.test(document.title)
        || Array.from(document.querySelectorAll('h1')).some(function (node) {
          return visible(node) && rateLimitMessage.test(text(node));
        })) fail("sa_company_rate_limited");
    if (/access denied|access to this page has been denied|verify you are human|just a moment/i.test(document.title)
        || Array.from(document.querySelectorAll('iframe[title="Human verification challenge"]')).some(visible)) {
      fail("sa_company_human_verification_required");
    }
    var main = one(document, "main");
    var heading = text(one(main, "h1"));
    if (!heading.startsWith(match[1] + " - ") || !document.title.includes("(" + match[1] + ")")) {
      fail("sa_company_identity_mismatch");
    }
    var controls = {};
    ["period", "view", "order", "currency"].forEach(function (name) {
      controls[name] = text(one(main, '[role="combobox"][aria-labelledby="financials-filter-' + name + '"]'));
    });
    if (!["Annual", "Quarterly"].includes(controls.period) || controls.view !== "Absolute") {
      fail("sa_company_view_unsupported");
    }
    var table = one(main, 'table[data-test-id="table"]');
    if (table.closest('[aria-busy="true"]') || table.querySelector('table, [aria-busy="true"], [data-test-id="skeleton"]')) {
      fail("sa_company_dom_not_ready");
    }
    var headerRows = Array.from(table.querySelectorAll("thead > tr"));
    if (headerRows.length !== 1) fail("sa_company_layout_unrecognized");
    var headers = Array.from(headerRows[0].cells).map(function (cell) {
      if (cell.tagName !== "TH" || cell.colSpan !== 1 || cell.rowSpan !== 1) fail("sa_company_layout_unrecognized");
      return { id: cell.getAttribute("data-test-id"), label: text(cell) };
    });
    if (headers.length < 3 || headers[0].id !== "value-header" || headers[0].label !== "Line Item"
        || headers[1].id !== "chart-header" || headers[1].label !== "Price Chart") {
      fail("sa_company_dom_not_ready");
    }
    var rows = Array.from(table.querySelectorAll("tbody > tr")).map(function (row) {
      var cells = Array.from(row.cells);
      if (!cells.length) fail("sa_company_layout_unrecognized");
      var first = cells[0];
      if (first.tagName !== "TH" || first.rowSpan !== 1 || !text(first)) fail("sa_company_layout_unrecognized");
      if (first.getAttribute("scope") === "colgroup") {
        if (cells.length !== 1 || first.colSpan !== headers.length) fail("sa_company_layout_unrecognized");
        return { kind: "section", label: text(first), values: [] };
      }
      if (first.getAttribute("scope") !== "row" || cells.length !== headers.length
          || cells.some(function (cell) { return cell.colSpan !== 1 || cell.rowSpan !== 1; })
          || cells.slice(1).some(function (cell) { return cell.tagName !== "TD"; })) {
        fail("sa_company_layout_unrecognized");
      }
      if (cells.some(function (cell) { return cell.querySelector('a[href*="subscribe"], [data-test-id*="locked"]'); })) {
        fail("sa_company_access_restricted");
      }
      return { kind: "data", label: text(first), values: cells.slice(1).map(text) };
    });
    if (!rows.length) fail("sa_company_dom_not_ready");
    var notes = (main.innerText || main.textContent || "").split("\n").map(function (line) { return line.trim(); })
      .filter(function (line) { return /^In (Millions|Thousands) of .+ except per share items$/.test(line); });
    if (notes.length !== 1) fail("sa_company_units_unrecognized");
    return { status: "ok", capture: {
      schema_version: 1,
      layout_id: "sa.financial-table.v1",
      source_url: url.origin + url.pathname.replace(/\/$/, ""),
      ticker: match[1], title: document.title, heading: heading,
      captured_at: new Date().toISOString(), controls: controls,
      unit_note: notes[0], headers: headers, rows: rows,
    } };
  } catch (error) {
    var code = error && /^sa_company_[a-z_]+$/.test(error.message)
      ? error.message : "sa_company_layout_unrecognized";
    return { status: "error", error_code: code };
  }
})();
