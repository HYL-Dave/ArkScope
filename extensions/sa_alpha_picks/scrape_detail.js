// scrape_detail.js — Injected into SA Alpha Picks detail page by chrome.scripting.executeScript
// Extracts article content as structured Markdown.
// Returns: { title, author, body_markdown, url, scraped_at } or { error, ... }
//
// Uses recursive TreeWalker (not querySelectorAll) to avoid nested content duplication.

(function () {
  "use strict";

  var COMMENT_ROW = '[class*="border-t-share-separator-thin"]';
  var ARTICLE_LEGAL_SENTENCES = [
    "i/we have no stock, option or similar derivative position in any of the companies mentioned, " +
      "and no plans to initiate any such positions within the next 72 hours.",
    "i wrote this article myself, and it expresses my own opinions.",
    "i am not receiving compensation for it (other than from seeking alpha).",
    "i have no business relationship with any company whose stock is mentioned in this article.",
    "past performance is no guarantee of future results.",
    "no recommendation or advice is being given as to whether any investment is suitable for a particular investor.",
    "any views or opinions expressed above may not reflect those of seeking alpha as a whole.",
    "seeking alpha is not a licensed securities dealer, broker or us investment adviser or investment bank.",
    "our analysts are third party authors that include both professional investors and individual investors " +
      "who may not be licensed or certified by any institute or regulatory body.",
  ];
  var commentExclusions = new Set();
  var articleExclusionCache = new WeakMap();
  var textCache = new WeakMap();
  var bodyTextCache = new WeakMap();
  var displayCache = new WeakMap();
  var narrativeCache = new WeakMap();
  if (document.body) classifyCommentUnits(document.body);

  // Prefer provider-owned content containers. Generic <article> nodes can be
  // disclosure cards, and the page may contain more than one content container.
  var providerSelectors = [
    '[data-test-id="content-container"]',
    '[data-testid="content-container"]',
    '[data-test-id="article-body"]',
    '[data-testid="article-body"]',
    ".paywall-full-content",
    "#content-body",
  ];
  var extractionSelector = providerSelectors.concat(["article", "main"]).join(",");
  var container = findLargestContainer(providerSelectors);
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
        var length = retainedText(nodes[j], !isMarketNewsPage()).text.trim().length;
        var eligible = length > 200 || (!isMarketNewsPage() && hasShortProviderProse(nodes[j]));
        if (eligible && length > bestLength) {
          best = nodes[j];
          bestLength = length;
        }
      }
    }
    return best;
  }

  function hasShortProviderProse(node) {
    var bodyId = /^(?:article-body|content-container)$/;
    if (!bodyId.test(node.getAttribute("data-test-id") || "") &&
        !bodyId.test(node.getAttribute("data-testid") || "")) return false;

    // Short-body eligibility, not completeness: require an exact provider marker
    // and a retained paragraph with two complete sentences of at least four words.
    // No character floor here; generic containers still require >200 characters.
    var paragraphs = node.matches("p") ? [node] : node.querySelectorAll("p");
    var segmenter = new Intl.Segmenter("en", { granularity: "sentence" });
    for (var i = 0; i < paragraphs.length; i++) {
      if (hasExcludedAncestor(paragraphs[i])) continue;
      var text = retainedText(paragraphs[i], true).text.replace(/\s+/g, " ").trim();
      if (/^(?:short placeholder|content (?:is )?(?:temporarily )?(?:unavailable|loading))\b/i.test(text) ||
          /^(?:(?:please )?(?:sign|log) in|subscribe to (?:read|continue))\b/i.test(text)) continue;
      var sentences = Array.from(segmenter.segment(text)).filter(function (part) {
        var sentence = part.segment.trim();
        return /[.!?]["')\]]*$/.test(sentence) && sentence.split(/\s+/).length >= 4;
      });
      if (sentences.length >= 2) return true;
    }
    return false;
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
      if (node.nodeType !== 1 && node.nodeType !== 3) continue;
      if (isExcluded(node)) continue;
      if (node.nodeType === 3 || (!isBlock(node) && /^(A|SPAN|STRONG|EM|B|I|CODE|SMALL|SUB|SUP|BR)$/.test(node.tagName || ""))) {
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
      if (current.matches(extractionSelector) && current.querySelector(COMMENT_ROW) &&
          !hasRetainedNarrative(current)) return true;
    }
    return false;
  }

  function displayOf(node) {
    if (!displayCache.has(node)) displayCache.set(node, getComputedStyle(node).display);
    return displayCache.get(node);
  }

  function isBlock(node) {
    return node.nodeType === 1 && /^(block|flow-root|flex|grid|list-item|table|table-row)$/.test(displayOf(node));
  }

  // Preserve rendered text when unchanged; never recover an excluded subtree
  // through a parent, list item or table cell's unfiltered innerText.
  // Headings remain in Markdown but do not establish a usable article body.
  function retainedText(node, bodyOnly) {
    var cache = bodyOnly ? bodyTextCache : textCache;
    if (cache.has(node)) return cache.get(node);
    var result;
    if (node.nodeType === 3) {
      result = { text: node.textContent || "", pruned: false };
    } else if (node.nodeType !== 1) {
      result = { text: "", pruned: false };
    } else if (isExcluded(node) || (bodyOnly && /^H[1-6]$/.test(node.tagName))) {
      result = { text: "", pruned: true };
    } else if (node.tagName === "BR") {
      result = { text: "\n", pruned: false };
    } else {
      var parts = [];
      var pruned = false;
      for (var i = 0; i < node.childNodes.length; i++) {
        var element = node.childNodes[i];
        var child = retainedText(element, bodyOnly);
        var block = isBlock(element);
        if (block && parts.length && !parts[parts.length - 1].endsWith("\n")) parts.push("\n");
        if (child.text) parts.push(child.text);
        if (block && child.text && !child.text.endsWith("\n")) parts.push("\n");
        pruned = pruned || child.pruned;
      }
      result = { text: pruned ? parts.join("") : (node.innerText || ""), pruned: pruned };
    }
    cache.set(node, result);
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

  function isArticleBoilerplate(node) {
    var metadataId = /^(?:author-name|post-page-meta|post-date|post-primary-tickers)$/;
    if (metadataId.test(node.getAttribute("data-test-id") || "") ||
        metadataId.test(node.getAttribute("data-testid") || "")) return true;
    if (node.matches("time[datetime]") && node.parentElement && isBlock(node.parentElement)) {
      var standalone = Array.from(node.parentElement.childNodes).every(function (sibling) {
        return sibling === node || isBlock(sibling) ||
          (sibling.nodeType !== 1 && sibling.nodeType !== 3) || !sibling.textContent.trim();
      });
      if (standalone) return true;
    }

    // Only classify a standalone rendered block. Never discard a mixed parent
    // from its combined text, or an inline mention inside an analysis paragraph.
    if (!isBlock(node)) return false;
    var descendants = node.querySelectorAll("*");
    for (var i = 0; i < descendants.length; i++) {
      if (isBlock(descendants[i])) return false;
    }
    var text = (node.innerText || "").replace(/\u2019/g, "'").replace(/\s+/g, " ").trim();
    if (/^(?:Analyst's|Seeking Alpha's) Disclosure\s*(?::|$)/i.test(text)) return true;
    if (/^By:\s+[^.!?]{1,120}$/i.test(text)) return true;

    // Split-label layouts can leave the legal paragraphs unlabelled. Require
    // the entire block to consist of known sentences, not just a legal prefix.
    var remaining = text.toLowerCase();
    while (remaining) {
      var matched = false;
      for (var j = 0; j < ARTICLE_LEGAL_SENTENCES.length; j++) {
        var sentence = ARTICLE_LEGAL_SENTENCES[j];
        if (remaining.startsWith(sentence)) {
          remaining = remaining.slice(sentence.length).trim();
          matched = true;
          break;
        }
      }
      if (!matched) return false;
    }
    return !!text;
  }

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
    if (node.nodeType !== 1) return false;
    if (displayOf(node) === "none") return true;
    if (isMarketNewsPage()) return false;
    if (!articleExclusionCache.has(node)) {
      articleExclusionCache.set(node, isArticleBoilerplate(node));
    }
    return articleExclusionCache.get(node);
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
