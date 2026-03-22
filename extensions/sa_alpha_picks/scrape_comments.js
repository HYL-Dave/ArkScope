// scrape_comments.js — Injected into SA Alpha Picks article page
// Extracts comments from the article page.
//
// SA DOM structure (as of 2026-03):
//   Comments are lazy-loaded by scrolling, inside paywall-full-content.
//   Each comment is a div with class containing "border-t" + "separator".
//   Structure per comment:
//     div.border-t-share-separator-thin
//       └─ div (avatar + content)
//           ├─ username (link or text)
//           ├─ date ("Mar 13, 2026, 3:02 PM")
//           ├─ badges ("Premium", "Investing Group")
//           └─ div.break-words (comment text)

(function () {
  "use strict";

  // Find comment elements by border separator class
  var commentEls = document.querySelectorAll('[class*="border-t-share-separator-thin"]');

  if (commentEls.length === 0) {
    return { comments: [], info: "No comment elements found" };
  }

  // Pass 1: Parse all comments
  var comments = [];
  for (var i = 0; i < commentEls.length; i++) {
    var el = commentEls[i];
    var parsed = parseComment(el);
    if (parsed) comments.push(parsed);
  }

  // Pass 2: Resolve reply parents via @username mentions
  // SA uses flat DOM — replies start with "@Username" in the text
  var usernameToId = {};
  for (var j = 0; j < comments.length; j++) {
    if (comments[j].commenter) {
      usernameToId[comments[j].commenter] = comments[j].comment_id;
    }
  }
  for (var k = 0; k < comments.length; k++) {
    var text = comments[k].comment_text;
    if (text && text.charAt(0) === "@") {
      // Extract mentioned username: "@Username rest of text"
      var spaceIdx = text.indexOf(" ");
      var mentioned = spaceIdx > 1 ? text.substring(1, spaceIdx) : text.substring(1);
      if (usernameToId[mentioned]) {
        comments[k].parent_comment_id = usernameToId[mentioned];
      }
    }
  }

  return { comments: comments };

  function parseComment(el) {
    // Extract comment text (div with break-words class)
    var textEl = el.querySelector('[class*="break-words"]');
    var text = textEl ? textEl.innerText.trim() : "";
    if (!text || text.length < 3) return null;

    // Extract username
    var commenter = "";
    var nameEl = el.querySelector('a[href*="/user/"]') ||
                 el.querySelector('a[href*="/author/"]');
    if (nameEl) commenter = nameEl.innerText.trim();
    if (!commenter) {
      // Fallback: first bold/strong text or first short text element
      var spans = el.querySelectorAll('span, a, strong');
      for (var s = 0; s < spans.length; s++) {
        var st = spans[s].innerText.trim();
        if (st.length > 2 && st.length < 40 && st.indexOf('\n') < 0) {
          commenter = st;
          break;
        }
      }
    }

    // Extract date
    var commentDate = null;
    var timeEl = el.querySelector('time[datetime]');
    if (timeEl) {
      commentDate = timeEl.getAttribute('datetime');
    } else {
      // Look for date pattern in element text
      var allText = el.innerText;
      var dateMatch = allText.match(
        /(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4},?\s+\d{1,2}:\d{2}\s*(AM|PM)?/i
      );
      if (dateMatch) commentDate = dateMatch[0];
    }

    // Extract upvotes (like count)
    var upvotes = 0;
    var allSpans = el.querySelectorAll('span, button');
    for (var u = 0; u < allSpans.length; u++) {
      var ut = allSpans[u].innerText.trim();
      // Look for standalone number that could be like count
      if (/^\d+$/.test(ut) && parseInt(ut) > 0 && parseInt(ut) < 10000) {
        upvotes = parseInt(ut);
        break;
      }
    }

    // parent_comment_id resolved in Pass 2 via @username detection
    var parentId = null;

    // Generate synthetic comment_id (will be re-hashed to sha256 in Python)
    var hash = 0;
    var raw = (commenter || "") + ":" + (commentDate || "") + ":" + text.substring(0, 100);
    for (var h = 0; h < raw.length; h++) {
      hash = (hash << 5) - hash + raw.charCodeAt(h);
      hash |= 0;
    }
    var commentId = "syn_" + Math.abs(hash).toString(36);

    return {
      comment_id: commentId,
      parent_comment_id: parentId,
      commenter: commenter.substring(0, 200),
      comment_text: text,
      upvotes: upvotes,
      comment_date: commentDate,
    };
  }
})();
