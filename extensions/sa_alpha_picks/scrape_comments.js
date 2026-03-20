// scrape_comments.js — Injected into SA Alpha Picks article page
// Extracts comment tree (top-level + nested replies).
// Returns: array of { comment_id, parent_comment_id, commenter, comment_text, upvotes, comment_date }
//
// DOM structure needs live testing — SA comment section may use various selectors.
// This script tries multiple strategies with fallbacks.

(function () {
  "use strict";

  // Strategy 1: Look for comment containers with data attributes
  var COMMENT_SELECTORS = [
    '[data-testid="comment"]',
    '[data-testid="comments-list"] > div',
    ".comment-thread",
    "#comments-section li",
    "#comments li",
    'section[id*="comment"] > div > div',
  ];

  var commentEls = [];
  for (var i = 0; i < COMMENT_SELECTORS.length; i++) {
    commentEls = document.querySelectorAll(COMMENT_SELECTORS[i]);
    if (commentEls.length > 0) break;
  }

  // Strategy 2: Broader search — find elements that look like comments
  if (commentEls.length === 0) {
    // Look for a comments section by text content
    var allSections = document.querySelectorAll("section, div");
    for (var s = 0; s < allSections.length; s++) {
      var el = allSections[s];
      if (el.id && el.id.toLowerCase().indexOf("comment") >= 0) {
        commentEls = el.querySelectorAll(":scope > div > div, :scope > ul > li");
        if (commentEls.length > 0) break;
      }
    }
  }

  if (commentEls.length === 0) {
    // Check if there are even any comments on this page
    var pageText = document.body ? document.body.innerText : "";
    var hasCommentWord = /\d+\s*Comments?/.test(pageText);
    return {
      comments: [],
      info: hasCommentWord
        ? "Comments section exists but selectors did not match"
        : "No comments section found on page",
    };
  }

  var comments = [];
  for (var c = 0; c < commentEls.length; c++) {
    var el = commentEls[c];
    var parsed = parseComment(el, null);
    if (parsed) {
      comments.push(parsed);
      // Look for nested replies
      var replies = el.querySelectorAll(
        ':scope > div[class*="reply"], :scope > ul > li'
      );
      for (var r = 0; r < replies.length; r++) {
        var reply = parseComment(replies[r], parsed.comment_id);
        if (reply) comments.push(reply);
      }
    }
  }

  return { comments: comments };

  function parseComment(el, parentId) {
    var text = "";
    // Try to find the comment body text
    var bodyEl =
      el.querySelector('[data-testid="comment-body"]') ||
      el.querySelector(".comment-body") ||
      el.querySelector("p");
    if (bodyEl) {
      text = bodyEl.innerText.trim();
    } else {
      // Fallback: use the element's text, excluding nested comments
      text = el.innerText.trim();
      // Truncate if too long (likely includes child elements)
      if (text.length > 2000) text = text.substring(0, 2000);
    }
    if (!text || text.length < 5) return null;

    // Extract commenter name
    var commenter = "";
    var nameEl =
      el.querySelector('[data-testid="comment-author"]') ||
      el.querySelector(".comment-author") ||
      el.querySelector('a[href*="/user/"]') ||
      el.querySelector("strong, b");
    if (nameEl) commenter = nameEl.innerText.trim();

    // Extract upvotes
    var upvotes = 0;
    var likeEl =
      el.querySelector('[data-testid="like-count"]') ||
      el.querySelector(".like-count");
    if (likeEl) {
      var m = likeEl.innerText.match(/(\d+)/);
      if (m) upvotes = parseInt(m[1], 10);
    }

    // Extract date
    var commentDate = null;
    var dateEl =
      el.querySelector("time") ||
      el.querySelector('[data-testid="comment-date"]') ||
      el.querySelector(".comment-date");
    if (dateEl) {
      commentDate =
        dateEl.getAttribute("datetime") || dateEl.innerText.trim();
    }

    // Generate comment_id (prefer SA native ID, fallback to hash)
    var nativeId =
      el.getAttribute("data-comment-id") ||
      el.getAttribute("id") ||
      "";
    var commentId = nativeId || hashId(text, commenter, commentDate);

    return {
      comment_id: commentId,
      parent_comment_id: parentId,
      commenter: commenter.substring(0, 200),
      comment_text: text,
      upvotes: upvotes,
      comment_date: commentDate,
    };
  }

  function hashId(text, commenter, date) {
    // Simple hash for synthetic ID (real sha256 done in Python)
    var str = (commenter || "") + ":" + (date || "") + ":" + (text || "").substring(0, 100);
    var hash = 0;
    for (var i = 0; i < str.length; i++) {
      hash = (hash << 5) - hash + str.charCodeAt(i);
      hash |= 0;
    }
    return "syn_" + Math.abs(hash).toString(36);
  }
})();
