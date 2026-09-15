// scrape_detail.js — Injected into SA Alpha Picks detail page by chrome.scripting.executeScript
// Extracts article content as structured Markdown.
// Returns: { title, author, body_markdown, url, scraped_at } or { error, ... }
//
// Uses recursive TreeWalker (not querySelectorAll) to avoid nested content duplication.

(function () {
  "use strict";

  var COMMENT_ROW = '[class*="border-t-share-separator-thin"]';
  var commentExclusions = new Set();
  var textCache = new WeakMap();
  var displayCache = new WeakMap();
  var narrativeCache = new WeakMap();
  if (document.body) classifyCommentUnits(document.body);

  // Prefer provider-owned content containers. Generic <article> nodes can be
  // disclosure cards, and the page may contain more than one content container.
  var container = findLargestContainer([
    '[data-test-id="content-container"]',
    '[data-testid="content-container"]',
    '[data-test-id="article-body"]',
    '[data-testid="article-body"]',
    ".paywall-full-content",
    "#content-body",
  ]);
  if (!container) {
    container = findLargestContainer(["article", "main"]);
  }
  if (!container) {
    return {
      error: "Article container not found",
      selectors_tried: [
        '[data-test-id="content-container"]',
        '[data-testid="content-container"]',
        '[data-test-id="article-body"]',
        '[data-testid="article-body"]',
        ".paywall-full-content",
        "#content-body",
        "article",
        "main",
      ],
      page_text_length: (document.body ? document.body.innerText.length : 0),
    };
  }

  // --- Metadata ---
  var title = "";
  var h1 = document.querySelector("h1");
  if (h1) title = h1.innerText.trim();
  var detailTicker = ArkScopeArticleIdentity.extractDetailTicker(document, h1);

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
    detail_ticker: detailTicker,
    detail_ticker_observed_at: detailTicker ? new Date().toISOString() : null,
    body_markdown: bodyMd,
    url: location.href,
    scraped_at: new Date().toISOString(),
  };

  function findLargestContainer(selectors) {
    var best = null;
    var bestLength = 0;
    for (var i = 0; i < selectors.length; i++) {
      var nodes = document.querySelectorAll(selectors[i]);
      for (var j = 0; j < nodes.length; j++) {
        if (hasExcludedAncestor(nodes[j])) continue;
        if (inCommentOnlyContext(nodes[j])) continue;
        var length = retainedText(nodes[j]).text.trim().length;
        if (length > 200 && length > bestLength) {
          best = nodes[j];
          bestLength = length;
        }
      }
    }
    return best;
  }

  // --- Core extraction ---

  function extractMarkdown(root) {
    if (hasExcludedAncestor(root)) return "";
    var parts = [];
    var inline = [];
    function finishInline() {
      var text = inline.join("").trim();
      if (text) parts.push(text);
      inline = [];
    }
    var children = root.childNodes;
    for (var i = 0; i < children.length; i++) {
      var node = children[i];
      if (isExcluded(node)) continue;
      if (node.nodeType === 3 || /^(A|SPAN|STRONG|EM|B|I|CODE|SMALL|SUB|SUP|BR)$/.test(node.tagName || "")) {
        inline.push(retainedText(node).text);
        continue;
      }
      finishInline();
      var md = nodeToMarkdown(node);
      if (md) parts.push(md);
    }
    finishInline();
    return parts.join("\n\n");
  }

  function hasExcludedAncestor(node) {
    for (var current = node; current; current = current.parentElement) {
      if (isExcluded(current)) return true;
    }
    return false;
  }

  function hasRetainedNarrative(root) {
    if (narrativeCache.has(root)) return narrativeCache.get(root);
    var nodes = root.querySelectorAll("p, ul, ol, table, blockquote");
    for (var i = 0; i < nodes.length; i++) {
      if (!hasExcludedAncestor(nodes[i]) && retainedText(nodes[i]).text.trim()) {
        narrativeCache.set(root, true);
        return true;
      }
    }
    narrativeCache.set(root, false);
    return false;
  }

  function inCommentOnlyContext(node) {
    for (var current = node; current; current = current.parentElement) {
      if (current.querySelector(COMMENT_ROW) && !hasRetainedNarrative(current)) return true;
    }
    return false;
  }

  function displayOf(node) {
    if (!displayCache.has(node)) displayCache.set(node, getComputedStyle(node).display);
    return displayCache.get(node);
  }

  // Preserve rendered text when unchanged; never recover an excluded subtree
  // through a parent, list item or table cell's unfiltered innerText.
  function retainedText(node) {
    if (textCache.has(node)) return textCache.get(node);
    var result;
    if (node.nodeType === 3) {
      result = { text: node.textContent || "", pruned: false };
    } else if (node.nodeType !== 1) {
      result = { text: "", pruned: false };
    } else if (isExcluded(node)) {
      result = { text: "", pruned: true };
    } else if (node.tagName === "BR") {
      result = { text: "\n", pruned: false };
    } else {
      var parts = [];
      var pruned = false;
      for (var i = 0; i < node.childNodes.length; i++) {
        var element = node.childNodes[i];
        var child = retainedText(element);
        var block = element.nodeType === 1 && /^(block|flow-root|flex|grid|list-item|table|table-row)$/.test(displayOf(element));
        if (block && parts.length && !parts[parts.length - 1].endsWith("\n")) parts.push("\n");
        if (child.text) parts.push(child.text);
        if (block && child.text && !child.text.endsWith("\n")) parts.push("\n");
        pruned = pruned || child.pruned;
      }
      result = { text: pruned ? parts.join("") : (node.innerText || ""), pruned: pruned };
    }
    textCache.set(node, result);
    return result;
  }

  // Only a known row anchors a comment group. Unknown prose breaks sibling
  // grouping, and a mixed parent is never excluded as a whole. Do not mutate
  // the page: the comment scraper runs against this same DOM afterward.
  function classifyCommentUnits(node) {
    if (node.nodeType === 3) return node.textContent.trim() ? "content" : "empty";
    if (node.nodeType !== 1) return "empty";
    if (isExcluded(node)) {
      return node.matches(COMMENT_ROW) || node.querySelector(COMMENT_ROW) ? "comment" : "control";
    }
    if (/^H[1-6]$/.test(node.tagName) &&
        /^comments(?:\s*\([0-9,]+\))?$/i.test((node.innerText || "").trim())) return "heading";

    var units = [];
    var run = [];
    var anchored = false;
    var covered = 0;
    function finishRun() {
      if (anchored) {
        for (var r = 0; r < run.length; r++) commentExclusions.add(run[r]);
        covered += run.length;
      }
      run = [];
      anchored = false;
    }
    for (var i = 0; i < node.childNodes.length; i++) {
      var child = node.childNodes[i];
      var kind = classifyCommentUnits(child);
      if (kind === "empty") continue;
      units.push(kind);
      if (kind === "content") {
        finishRun();
      } else {
        run.push(child);
        anchored = anchored || kind === "comment";
      }
    }
    finishRun();
    if (!units.length) return "empty";
    if (covered === units.length) {
      commentExclusions.add(node);
      return "comment";
    }
    if (units.every(function (kind) { return kind === "control"; })) return "control";
    if (units.every(function (kind) { return kind === "heading" || kind === "control"; })) return "heading";
    return "content";
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
    var text = retainedText(node).text.trim();
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
        if (isExcluded(items[j])) continue;
        var prefix = tag === "ol" ? j + 1 + ". " : "- ";
        lines.push(prefix + retainedText(items[j]).text.trim());
      }
      return lines.join("\n");
    }

    if (tag === "table") return tableToMarkdown(node);

    // Container elements: recurse into children
    if (tag === "div" || tag === "section" || tag === "figure" || tag === "article" || tag === "main") {
      return extractMarkdown(node) || null;
    }

    // p, span, etc. — direct text
    return text;
  }

  // --- Exclusion ---

  function isExcluded(node) {
    if (commentExclusions.has(node)) return true;
    if (node.matches && node.matches(COMMENT_ROW + ', button, input, select, textarea, [role="button"]')) return true;
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

    // Match semantic class tokens, not incidental substrings such as
    // "no-sidebar" or "commentary-layout" on an article's ancestors.
    var cls = typeof node.className === "string" ? node.className : "";
    var classes = cls.split(/\s+/);
    for (var i = 0; i < classes.length; i++) {
      if (/^(?:ad-|related-|cta-|(?:promo|comments?|sidebar|newsletter)(?:[-_]|$))/.test(classes[i])) return true;
    }
    return node.nodeType === 1 && displayOf(node) === "none";
  }

  // --- Table → Markdown ---

  function tableToMarkdown(table) {
    var rows = table.rows;
    if (rows.length === 0) return "";
    var lines = [];
    for (var r = 0; r < rows.length; r++) {
      if (hasExcludedAncestor(rows[r])) continue;
      var cells = rows[r].cells;
      var line = "| ";
      for (var c = 0; c < cells.length; c++) {
        line += retainedText(cells[c]).text.trim() + " | ";
      }
      var first = lines.length === 0;
      lines.push(line);
      if (first) {
        var sep = "| ";
        for (var s = 0; s < cells.length; s++) sep += "--- | ";
        lines.push(sep);
      }
    }
    return lines.join("\n");
  }
})();
