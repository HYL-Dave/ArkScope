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
//           ├─ date ("Mar 13, 2026, 3:02 PM" or relative variants)
//           ├─ badges ("Premium", "Investing Group")
//           └─ div.break-words (comment text)

(function () {
  "use strict";

  var commentEls = document.querySelectorAll('[class*="border-t-share-separator-thin"]');
  if (commentEls.length === 0) {
    return { comments: [], info: "No comment elements found" };
  }

  var comments = [];
  for (var i = 0; i < commentEls.length; i++) {
    var parsed = parseComment(commentEls[i]);
    if (parsed) comments.push(parsed);
  }

  resolveReplyParents(comments);
  return { comments: comments };

  function parseComment(el) {
    var textEl = el.querySelector('div[class*="break-words"]');
    var text = normalizeWhitespace(textEl ? textEl.innerText : "");
    if (!text || text.length < 3) return null;

    var commenter = extractCommenter(el);
    var commentDate = extractCommentDate(el, textEl);
    var upvotes = extractUpvotes(el);

    var hash = 0;
    var raw = (commenter || "") + ":" + (commentDate || "") + ":" + text.substring(0, 100);
    for (var h = 0; h < raw.length; h++) {
      hash = (hash << 5) - hash + raw.charCodeAt(h);
      hash |= 0;
    }

    return {
      comment_id: "syn_" + Math.abs(hash).toString(36),
      parent_comment_id: null,
      commenter: commenter.substring(0, 200),
      comment_text: text,
      upvotes: upvotes,
      comment_date: commentDate,
    };
  }

  function extractCommenter(el) {
    var commenter = "";
    var nameEl = el.querySelector('a[href*="/user/"]') || el.querySelector('a[href*="/author/"]');
    if (nameEl) commenter = normalizeWhitespace(nameEl.innerText);
    if (commenter) return commenter;

    var spans = el.querySelectorAll('span, a, strong');
    for (var i = 0; i < spans.length; i++) {
      var text = normalizeWhitespace(spans[i].innerText);
      if (text.length > 2 && text.length < 40 && text.indexOf('\n') < 0) {
        return text;
      }
    }
    return "";
  }

  function extractCommentDate(el, textEl) {
    var timeEl = el.querySelector('time[datetime]');
    if (timeEl) {
      var datetimeAttr = normalizeDatetimeAttr(timeEl.getAttribute('datetime'));
      if (datetimeAttr) return datetimeAttr;
      var timeText = normalizeTextDate(timeEl.innerText);
      if (timeText) return timeText;
    }

    var candidates = [];
    var seen = {};

    function addCandidate(value) {
      var normalized = normalizeWhitespace(value);
      if (!normalized || seen[normalized]) return;
      seen[normalized] = true;
      candidates.push(normalized);
    }

    var nodes = el.querySelectorAll('span, a, div');
    for (var i = 0; i < nodes.length; i++) {
      var node = nodes[i];
      if (textEl && textEl.contains(node)) continue;
      var text = normalizeWhitespace(node.innerText);
      if (!text || text.length > 80 || text.indexOf('\n') >= 0) continue;
      addCandidate(text);
    }
    addCandidate(el.innerText);

    for (var j = 0; j < candidates.length; j++) {
      var parsed = normalizeTextDate(candidates[j]);
      if (parsed) return parsed;
    }
    return null;
  }

  function extractUpvotes(el) {
    var upvotes = 0;
    var allSpans = el.querySelectorAll('span, button');
    for (var i = 0; i < allSpans.length; i++) {
      var text = normalizeWhitespace(allSpans[i].innerText);
      if (/^\d+$/.test(text)) {
        var value = parseInt(text, 10);
        if (value > 0 && value < 10000) {
          upvotes = value;
          break;
        }
      }
    }
    return upvotes;
  }

  function resolveReplyParents(comments) {
    for (var i = 0; i < comments.length; i++) {
      var mentionTokens = extractLeadingMentionTokens(comments[i].comment_text);
      if (!mentionTokens.length) continue;

      var candidatesByName = {};
      for (var j = i - 1; j >= 0; j--) {
        var prior = comments[j];
        if (!prior.commenter || candidatesByName[prior.commenter]) continue;
        candidatesByName[prior.commenter] = {
          comment_id: prior.comment_id,
          index: j,
          tokens: tokenizeName(prior.commenter),
        };
      }

      var matches = [];
      for (var name in candidatesByName) {
        if (!Object.prototype.hasOwnProperty.call(candidatesByName, name)) continue;
        var candidate = candidatesByName[name];
        var score = scoreMentionMatch(mentionTokens, candidate.tokens);
        if (score <= 0) continue;
        matches.push({
          score: score,
          token_count: candidate.tokens.length,
          index: candidate.index,
          comment_id: candidate.comment_id,
        });
      }

      if (!matches.length) continue;

      matches.sort(function (a, b) {
        if (b.score !== a.score) return b.score - a.score;
        if (b.token_count !== a.token_count) return b.token_count - a.token_count;
        return b.index - a.index;
      });

      if (
        matches.length > 1 &&
        matches[1].score === matches[0].score &&
        matches[1].token_count === matches[0].token_count
      ) {
        continue;
      }
      comments[i].parent_comment_id = matches[0].comment_id;
    }
  }

  function scoreMentionMatch(mentionTokens, commenterTokens) {
    if (!mentionTokens.length || !commenterTokens.length) return 0;
    if (isTokenPrefix(commenterTokens, mentionTokens)) {
      return 100 + commenterTokens.length;
    }
    if (commenterTokens[0] === mentionTokens[0]) {
      return commenterTokens.length === 1 ? 10 : 1;
    }
    return 0;
  }

  function isTokenPrefix(expectedTokens, actualTokens) {
    if (expectedTokens.length > actualTokens.length) return false;
    for (var i = 0; i < expectedTokens.length; i++) {
      if (expectedTokens[i] !== actualTokens[i]) return false;
    }
    return true;
  }

  function extractLeadingMentionTokens(text) {
    if (!text || text.charAt(0) !== '@') return [];
    var raw = text.substring(1, 120);
    return tokenizeName(raw);
  }

  function tokenizeName(value) {
    var normalized = normalizeWhitespace(value)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, ' ')
      .trim();
    return normalized ? normalized.split(/\s+/) : [];
  }

  function normalizeWhitespace(value) {
    return (value || '').replace(/\s+/g, ' ').trim();
  }

  function normalizeDatetimeAttr(value) {
    var text = normalizeWhitespace(value);
    if (!text) return null;

    var parsed = Date.parse(text);
    if (!isNaN(parsed)) return serializeLocalDate(new Date(parsed));
    return text;
  }

  function normalizeTextDate(value) {
    var text = normalizeWhitespace(value);
    if (!text) return null;

    var parsed = parseDateText(text);
    if (!parsed) return null;
    return serializeLocalDate(parsed);
  }

  function parseDateText(text) {
    var relativeMatch = text.match(/\b(Today|Yesterday)\b[,]?\s+(\d{1,2}:\d{2}\s*(?:AM|PM))/i);
    if (relativeMatch) {
      var now = new Date();
      var dayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      if (/^yesterday$/i.test(relativeMatch[1])) {
        dayStart.setDate(dayStart.getDate() - 1);
      }
      var relDate = applyClockTime(dayStart, relativeMatch[2]);
      if (relDate) return relDate;
    }

    var isoMatch = text.match(/\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?\b/);
    if (isoMatch) {
      var isoParsed = Date.parse(isoMatch[0]);
      if (!isNaN(isoParsed)) return new Date(isoParsed);
    }

    var absMatch = text.match(/\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+\d{1,2},\s*\d{4},?\s+\d{1,2}:\d{2}\s*(?:AM|PM)\b/i);
    if (absMatch) {
      var cleaned = absMatch[0].replace(/Sept/i, 'Sep');
      var absParsed = Date.parse(cleaned);
      if (!isNaN(absParsed)) return new Date(absParsed);
    }

    var numericMatch = text.match(/\b\d{1,2}\/\d{1,2}\/\d{4},?\s+\d{1,2}:\d{2}\s*(?:AM|PM)\b/i);
    if (numericMatch) {
      var numericParsed = Date.parse(numericMatch[0]);
      if (!isNaN(numericParsed)) return new Date(numericParsed);
    }

    return null;
  }

  function serializeLocalDate(date) {
    var year = String(date.getFullYear());
    var month = String(date.getMonth() + 1).padStart(2, '0');
    var day = String(date.getDate()).padStart(2, '0');
    var hours = String(date.getHours()).padStart(2, '0');
    var minutes = String(date.getMinutes()).padStart(2, '0');
    var seconds = String(date.getSeconds()).padStart(2, '0');
    return year + '-' + month + '-' + day + 'T' + hours + ':' + minutes + ':' + seconds;
  }

  function applyClockTime(baseDate, clockText) {
    var match = clockText.match(/(\d{1,2}):(\d{2})\s*(AM|PM)/i);
    if (!match) return null;
    var hours = parseInt(match[1], 10);
    var minutes = parseInt(match[2], 10);
    var meridiem = match[3].toUpperCase();
    if (hours === 12) hours = 0;
    if (meridiem === 'PM') hours += 12;

    var result = new Date(baseDate.getTime());
    result.setHours(hours, minutes, 0, 0);
    return result;
  }
})();
