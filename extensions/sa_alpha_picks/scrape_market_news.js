// scrape_market_news.js — Injected into Seeking Alpha /market-news page.
// Extracts recent market-news metadata only; no article body scraping.

(function () {
  "use strict";

  function absUrl(href) {
    try {
      return new URL(href, location.origin).href.split("#")[0];
    } catch (_) {
      return href || "";
    }
  }

  function unique(values) {
    var seen = {};
    var out = [];
    for (var i = 0; i < values.length; i++) {
      var v = (values[i] || "").trim().toUpperCase();
      if (!v || seen[v]) continue;
      seen[v] = true;
      out.push(v);
    }
    return out;
  }

  function extractNewsId(url) {
    var m = (url || "").match(/\/news\/(\d+)/);
    return m ? m[1] : "";
  }

  function findCard(anchor) {
    var current = anchor;
    var best = anchor;
    for (var i = 0; i < 7 && current && current.parentElement; i++) {
      current = current.parentElement;
      var text = (current.innerText || "").trim();
      if (!text) continue;
      if (text.length > 2000) break;
      best = current;
      if (current.tagName && ["ARTICLE", "LI"].indexOf(current.tagName.toUpperCase()) >= 0) break;
      if (/\b(Save|Copy Link|Comments?)\b/i.test(text) && text.indexOf(anchor.innerText.trim()) >= 0) break;
    }
    return best;
  }

  function extractTickers(card) {
    var tickers = [];
    var links = card.querySelectorAll('a[href*="/symbol/"]');
    for (var i = 0; i < links.length; i++) {
      var href = links[i].getAttribute("href") || links[i].href || "";
      var fromHref = href.match(/\/symbol\/([^/?#]+)/);
      if (fromHref) {
        tickers.push(decodeURIComponent(fromHref[1]).replace(/:.*$/, ""));
        continue;
      }
      var text = (links[i].innerText || "").trim();
      var m = text.match(/^([A-Z][A-Z0-9.:-]{0,14})\b/);
      if (m) tickers.push(m[1].replace(/:.*$/, ""));
    }
    return unique(tickers);
  }

  function extractCommentsCount(text) {
    var m = (text || "").match(/(\d{1,4})\s+Comments?/i);
    return m ? parseInt(m[1], 10) : 0;
  }

  function extractPublishedText(text) {
    text = text || "";
    var patterns = [
      /\bNow!?\b/i,
      /\bToday,?\s+\d{1,2}:\d{2}\s*(?:AM|PM)\b/i,
      /\bYesterday,?\s+\d{1,2}:\d{2}\s*(?:AM|PM)\b/i,
      /\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{1,2},\s+\d{4}(?:,?\s+\d{1,2}:\d{2}\s*(?:AM|PM))?\b/i,
    ];
    for (var i = 0; i < patterns.length; i++) {
      var m = text.match(patterns[i]);
      if (m) return m[0];
    }
    return "";
  }

  function parsePublishedAt(text) {
    if (!text) return null;
    var now = new Date();
    if (/^now!?$/i.test(text.trim())) return now.toISOString();

    var m = text.match(/^(Today|Yesterday),?\s+(\d{1,2}):(\d{2})\s*(AM|PM)$/i);
    if (m) {
      var d = new Date(now.getTime());
      if (/yesterday/i.test(m[1])) d.setDate(d.getDate() - 1);
      var h = parseInt(m[2], 10);
      var min = parseInt(m[3], 10);
      var ampm = m[4].toUpperCase();
      if (ampm === "PM" && h < 12) h += 12;
      if (ampm === "AM" && h === 12) h = 0;
      d.setHours(h, min, 0, 0);
      return d.toISOString();
    }

    var parsed = Date.parse(text);
    if (!Number.isNaN(parsed)) return new Date(parsed).toISOString();
    return null;
  }

  function extractSummary(card, title, publishedText) {
    var lines = (card.innerText || "")
      .split("\n")
      .map(function (s) { return s.trim(); })
      .filter(Boolean);
    var rejected = {
      "Save": true,
      "Copy Link": true,
      "Comments": true,
    };
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      if (line === title || line === publishedText || rejected[line]) continue;
      if (/^\d+\s+Comments?$/i.test(line)) continue;
      if (/^[A-Z][A-Z0-9.:-]{0,14}\s+[+-]?\d/.test(line)) continue;
      if (line.length >= 40) return line;
    }
    return "";
  }

  var anchors = document.querySelectorAll('a[href*="/news/"]');
  var byId = {};
  var items = [];

  for (var i = 0; i < anchors.length; i++) {
    var anchor = anchors[i];
    var url = absUrl(anchor.getAttribute("href") || anchor.href || "");
    var newsId = extractNewsId(url);
    var title = (anchor.innerText || "").trim().replace(/\s+/g, " ");
    if (!newsId || title.length < 12) continue;
    if (byId[newsId]) continue;

    var card = findCard(anchor);
    var cardText = (card.innerText || "").trim();
    var publishedText = extractPublishedText(cardText);
    var item = {
      news_id: newsId,
      url: url,
      title: title,
      published_text: publishedText,
      published_at: parsePublishedAt(publishedText),
      tickers: extractTickers(card),
      comments_count: extractCommentsCount(cardText),
      summary: extractSummary(card, title, publishedText),
      category: "market-news",
      raw_data: {
        card_text: cardText,
        scraped_url: location.href,
      },
    };
    byId[newsId] = true;
    items.push(item);
  }

  return items;
})();
