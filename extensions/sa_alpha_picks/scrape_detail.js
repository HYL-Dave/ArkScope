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

  // --- Publish date ---
  var publishDate = null;
  // Try <time> element (most reliable)
  var timeEl = document.querySelector('time[datetime]');
  if (timeEl) {
    publishDate = timeEl.getAttribute('datetime').substring(0, 10);
  }
  if (!publishDate) {
    // Try date pattern in page text near the title
    var headerArea = document.querySelector('header') || container;
    var dateMatch = (headerArea.innerText || '').match(
      /(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{1,2},\s+\d{4}/
    );
    if (dateMatch) publishDate = dateMatch[0];
  }

  // --- Body → Markdown (TreeWalker) ---
  var bodyMd = extractMarkdown(container);
  if (isMarketNewsPage()) {
    bodyMd = cleanMarketNewsMarkdown(bodyMd, title);
  }

  return {
    title: title,
    author: author,
    publish_date: publishDate,
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

  function isMarketNewsPage() {
    return /^\/news\//.test(location.pathname || "");
  }

  function cleanMarketNewsMarkdown(markdown, titleText) {
    if (!markdown) return markdown;
    titleText = (titleText || "").trim();
    var titleHeading = titleText ? "# " + titleText : "";

    var lines = markdown.split(/\r?\n/);
    var cleaned = [];
    for (var i = 0; i < lines.length; i++) {
      cleaned.push(lines[i].replace(/\s+$/, ""));
    }

    while (cleaned.length > 0 && !cleaned[0].trim()) cleaned.shift();

    var keptHeading = false;
    var out = [];
    if (
      cleaned.length > 0 &&
      cleaned[0].trim() === titleHeading
    ) {
      out.push(cleaned[0].trim());
      keptHeading = true;
      cleaned = cleaned.slice(1);
    }

    var start = 0;
    while (start < cleaned.length) {
      var current = cleaned[start].trim();
      if (!current) {
        start += 1;
        continue;
      }
      if (isMarketNewsBodyLine(current)) break;
      start += 1;
    }

    cleaned = cleaned.slice(start);

    var tail = [];
    for (var j = 0; j < cleaned.length; j++) {
      var line = cleaned[j].trim();
      if (!line) {
        tail.push("");
        continue;
      }
      if (isMarketNewsSectionStart(line)) break;
      if (isMarketNewsNoiseLine(line)) continue;
      tail.push(line);
    }

    out = out.concat(tail);

    var deduped = [];
    var seenTitleHeading = keptHeading;
    for (var d = 0; d < out.length; d++) {
      var normalized = out[d].trim ? out[d].trim() : out[d];
      if (!normalized) {
        deduped.push(out[d]);
        continue;
      }
      if (titleText && normalized === titleText) continue;
      if (titleHeading && normalized === titleHeading) {
        if (seenTitleHeading) continue;
        seenTitleHeading = true;
      }
      deduped.push(out[d]);
    }

    var compact = [];
    var blank = false;
    for (var k = 0; k < deduped.length; k++) {
      var entry = deduped[k].trim ? deduped[k].trim() : deduped[k];
      if (!entry) {
        if (!blank && compact.length > 0) compact.push("");
        blank = true;
        continue;
      }
      compact.push(entry);
      blank = false;
    }
    while (compact.length > 0 && !compact[compact.length - 1]) compact.pop();

    if (!keptHeading && compact.length > 0 && titleHeading) {
      compact.unshift(titleHeading);
    }

    return compact.join("\n");
  }

  function isMarketNewsBodyLine(line) {
    if (!line) return false;
    if (isMarketNewsNoiseLine(line)) return false;
    if (isMarketNewsSectionStart(line)) return false;

    if (/^- (?!Share$|Save$|Play$|Comments?$)/.test(line) && line.length >= 20) {
      return true;
    }

    if (/^[A-Z].{60,}$/.test(line) && !/\b(?:AM|PM)\s+ET\b/.test(line)) {
      return true;
    }

    return false;
  }

  function isMarketNewsSectionStart(line) {
    return /^(?:##|###)\s+(?:More on|Recommended For You|Related Stocks|Related news|Read more on|More Trending News)\b/i.test(
      line || ""
    ) || /^(?:See More|Source\s*\|)\b/i.test(
      line || ""
    );
  }

  function isMarketNewsNoiseLine(line) {
    line = line || "";
    if (!line) return false;

    if (
      /^(?:- )?(?:Share|Save|Play|Comments?)$/i.test(line) ||
      /^\((?:<)?\d+\s*min\)$/i.test(line) ||
      /^\(\d+\)$/.test(line) ||
      /^Follow Seeking Alpha on Google\b/i.test(line) ||
      /^See More\b/i.test(line) ||
      /^Source\s*\|/i.test(line) ||
      /\bPlease check back later\b/i.test(line) ||
      /\bContent error\b/i.test(line) ||
      /\bSomething went wrong\b/i.test(line) ||
      /\btemporarily unavailable\b/i.test(line)
    ) {
      return true;
    }

    if (
      /^By:\s+/i.test(line) ||
      /\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{1,2},\s+\d{4}/.test(line) ||
      /\b(?:Today|Yesterday),?\s+\d{1,2}:\d{2}\s*(?:AM|PM)\b/i.test(line) ||
      /\b(?:AM|PM)\s+ET\b/.test(line)
    ) {
      return true;
    }

    return false;
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
