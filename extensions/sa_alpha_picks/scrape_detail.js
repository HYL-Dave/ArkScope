// scrape_detail.js — Injected into SA Alpha Picks detail page by chrome.scripting.executeScript
// Extracts article content as structured Markdown.
// Returns: { title, author, body_markdown, url, scraped_at } or { error, ... }
//
// Uses recursive TreeWalker (not querySelectorAll) to avoid nested content duplication.

(function () {
  "use strict";

  // Try multiple article body selectors (SA DOM may change)
  var SELECTORS = [
    "article",
    '[data-testid="article-body"]',
    '[data-testid="content-container"]',
    ".paywall-full-content",
    "#content-body",
    "main",
  ];

  var container = null;
  for (var i = 0; i < SELECTORS.length; i++) {
    container = document.querySelector(SELECTORS[i]);
    if (container && container.innerText.trim().length > 200) break;
    container = null;
  }
  if (!container) {
    return {
      error: "Article container not found",
      selectors_tried: SELECTORS,
      page_text_length: (document.body ? document.body.innerText.length : 0),
    };
  }

  // --- Metadata ---
  var title = "";
  var h1 = document.querySelector("h1");
  if (h1) title = h1.innerText.trim();

  var author = "";
  var authorEl =
    document.querySelector('[data-testid="author-name"]') ||
    document.querySelector('a[href*="/author/"]');
  if (authorEl) author = authorEl.innerText.trim();

  // --- Body → Markdown (TreeWalker) ---
  var bodyMd = extractMarkdown(container);

  return {
    title: title,
    author: author,
    body_markdown: bodyMd,
    url: location.href,
    scraped_at: new Date().toISOString(),
  };

  // --- Core extraction ---

  function extractMarkdown(root) {
    var parts = [];
    var children = root.children;
    for (var i = 0; i < children.length; i++) {
      var node = children[i];
      if (isExcluded(node)) continue;
      var md = nodeToMarkdown(node);
      if (md) parts.push(md);
    }
    return parts.join("\n\n");
  }

  function nodeToMarkdown(node) {
    // Recursive exclusion: check at every level
    if (isExcluded(node)) return null;

    var tag = node.tagName ? node.tagName.toLowerCase() : "";
    var text = node.innerText ? node.innerText.trim() : "";
    if (!text) return null;

    if (tag === "h1") return "# " + text;
    if (tag === "h2") return "## " + text;
    if (tag === "h3") return "### " + text;
    if (tag === "h4") return "#### " + text;
    if (tag === "blockquote") return "> " + text.replace(/\n/g, "\n> ");

    if (tag === "ul" || tag === "ol") {
      // :scope > li — direct children only, avoid nested list duplication
      var items = node.querySelectorAll(":scope > li");
      var lines = [];
      for (var j = 0; j < items.length; j++) {
        var prefix = tag === "ol" ? j + 1 + ". " : "- ";
        lines.push(prefix + items[j].innerText.trim());
      }
      return lines.join("\n");
    }

    if (tag === "table") return tableToMarkdown(node);

    // Container elements: recurse into children
    if (tag === "div" || tag === "section" || tag === "figure") {
      var ch = node.children;
      if (ch.length > 0) {
        // Has child elements — recurse (do NOT fallback to text to avoid
        // leaking excluded descendant content)
        var subParts = [];
        for (var k = 0; k < ch.length; k++) {
          var sub = nodeToMarkdown(ch[k]);
          if (sub) subParts.push(sub);
        }
        return subParts.length > 0 ? subParts.join("\n\n") : null;
      }
      // Leaf container (no child elements) — use text
      return text;
    }

    // p, span, etc. — direct text
    return text;
  }

  // --- Exclusion ---

  function isExcluded(node) {
    // Tag-based exclusion
    var tag = node.tagName ? node.tagName.toLowerCase() : "";
    if (
      tag === "nav" ||
      tag === "footer" ||
      tag === "aside" ||
      tag === "script" ||
      tag === "style"
    )
      return true;

    // Class-based exclusion (no dot prefix — className is "foo bar", not ".foo")
    var EXCLUDED_CLASSES = [
      "ad-",
      "promo",
      "related-",
      "comment",
      "sidebar",
      "newsletter",
      "cta-",
    ];
    var cls = typeof node.className === "string" ? node.className : "";
    for (var i = 0; i < EXCLUDED_CLASSES.length; i++) {
      if (cls.indexOf(EXCLUDED_CLASSES[i]) >= 0) return true;
    }
    return false;
  }

  // --- Table → Markdown ---

  function tableToMarkdown(table) {
    var rows = table.querySelectorAll("tr");
    if (rows.length === 0) return "";
    var lines = [];
    for (var r = 0; r < rows.length; r++) {
      var cells = rows[r].querySelectorAll("th, td");
      var line = "| ";
      for (var c = 0; c < cells.length; c++) {
        line += cells[c].innerText.trim() + " | ";
      }
      lines.push(line);
      if (r === 0) {
        var sep = "| ";
        for (var s = 0; s < cells.length; s++) sep += "--- | ";
        lines.push(sep);
      }
    }
    return lines.join("\n");
  }
})();
