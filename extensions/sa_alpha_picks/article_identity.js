(function (root) {
  "use strict";

  var TICKER = "[A-Z][A-Z.]{0,9}";
  var ABSOLUTE_DATE = /^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{1,2},\s+\d{4}$/;

  function normalizeTicker(value) {
    var text = String(value || "").trim().toUpperCase();
    return new RegExp("^" + TICKER + "$").test(text) ? text : null;
  }

  function extractListTicker(card, dateText) {
    var scoped = card || null;
    var normalizedDate = String(dateText || "").trim();
    if (!scoped || !ABSOLUTE_DATE.test(normalizedDate)) return null;

    var nodes = scoped.querySelectorAll(
      '[data-testid*="ticker" i], [data-test-id*="ticker" i], a[href*="/symbol/"]'
    );
    for (var i = 0; i < nodes.length; i++) {
      var exact = normalizeTicker(nodes[i].textContent);
      if (exact) return exact;
    }

    var text = String(scoped.innerText || scoped.textContent || "")
      .replace(/\s+/g, " ")
      .trim();
    var at = text.indexOf(normalizedDate);
    if (at < 0) return null;
    var tail = text.slice(at + normalizedDate.length);
    var match = tail.match(
      /^\s*,?\s*(?:\d{1,2}:\d{2}\s*(?:AM|PM)(?:\s+ET)?\s*)?(?:[•·|]\s*)?([A-Z][A-Z.]{0,9})(?=\s*(?:[•·|]|\d+\s*Comments?\b|$))/i
    );
    return match ? normalizeTicker(match[1]) : null;
  }

  function extractDetailTicker(doc, h1) {
    if (!doc || !h1) return null;
    var scope = h1.parentElement;
    for (var depth = 0; scope && depth < 4; depth += 1, scope = scope.parentElement) {
      var text = String(scope.innerText || scope.textContent || "").replace(/\s+/g, " ");
      var match = text.match(/\(([A-Z][A-Z.]{0,9})\)\s+Stock\b/);
      if (match) return normalizeTicker(match[1]);
    }
    return null;
  }

  root.ArkScopeArticleIdentity = {
    normalizeTicker: normalizeTicker,
    extractListTicker: extractListTicker,
    extractDetailTicker: extractDetailTicker,
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
