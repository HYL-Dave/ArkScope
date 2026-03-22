// scrape_articles_list.js — Injected into SA Alpha Picks articles page
// Extracts ALL articles (with or without ticker).
// Returns: array of { article_id, url, title, ticker, date, comments_count, article_type }
//
// v3: Returns ALL articles (not just ticker-tagged).
// article_type auto-detected from title keywords.

(function () {
  "use strict";

  var links = document.querySelectorAll('a[href*="/alpha-picks/articles/"]');
  var seen = {};
  var articles = [];

  for (var i = 0; i < links.length; i++) {
    var a = links[i];
    var href = a.href.split("#")[0];
    var text = a.innerText.trim();

    if (!text || text.length < 15 || /^\d+\s*Comments?$/i.test(text)) continue;
    if (seen[href]) continue;
    seen[href] = true;

    // Extract article_id from URL: /alpha-picks/articles/6272753-... → "6272753"
    var idMatch = href.match(/\/articles\/(\d+)/);
    var articleId = idMatch ? idMatch[1] : null;
    if (!articleId) continue;

    // Find the enclosing <article> card
    var card = a.closest("article");
    if (!card) {
      card = a.parentElement;
      while (card && card.innerText.length < 100) card = card.parentElement;
    }
    var cardText = card ? card.innerText : "";

    // Extract date
    var dateMatch = cardText.match(
      /(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+\d{1,2},\s+\d{4}/
    );
    var date = dateMatch ? dateMatch[0] : null;

    // Extract ticker (nullable)
    var ticker = null;
    if (date) {
      var afterDate = cardText.substring(cardText.indexOf(date) + date.length);
      // Ticker: only uppercase letters + dot (NO digits — digits are comment count)
      // e.g. "LITE216 Comments" → ticker=LITE, "BRK.B34 Comments" → ticker=BRK.B
      var tickerMatch = afterDate.match(
        /^\s*([A-Z][A-Z.]*(?::[A-Z]{1,4})?)\s*\d+\s*Comments?/
      );
      if (!tickerMatch) {
        tickerMatch = afterDate.match(/^\s*([A-Z][A-Z.]{0,9})\s*$/);
      }
      if (tickerMatch) {
        ticker = tickerMatch[1];
        var colonIdx = ticker.indexOf(":");
        if (colonIdx > 0) ticker = ticker.substring(0, colonIdx);
      }
    }

    // Extract comments count from card text
    var commentsMatch = cardText.match(/(\d+)\s*Comments?/);
    var commentsCount = commentsMatch ? parseInt(commentsMatch[1], 10) : 0;

    // Auto-detect article_type from title + ticker presence
    var articleType = detectArticleType(text, ticker);

    articles.push({
      article_id: articleId,
      url: href,
      title: text.substring(0, 200),
      ticker: ticker,
      date: date,
      comments_count: commentsCount,
      article_type: articleType,
    });
  }

  return articles.length > 0
    ? articles
    : { error: "No articles found", total_links: links.length };

  function detectArticleType(title, ticker) {
    var t = title.toLowerCase();
    if (t.indexOf("webinar") >= 0 || t.indexOf("transcript") >= 0) return "webinar";
    if (t.indexOf("market recap") >= 0 || t.indexOf("portfolio review") >= 0) return "recap";
    if (
      t.indexOf("sold") >= 0 ||
      t.indexOf("closing") >= 0 ||
      t.indexOf("removing") >= 0 ||
      t.indexOf("initial stake") >= 0
    )
      return "removal";
    if (t.indexOf("stock buy") >= 0 || t.indexOf("stock sell") >= 0) return "analysis";
    // Has ticker → likely analysis (stock-specific article)
    if (ticker) return "analysis";
    return "commentary";
  }
})();
