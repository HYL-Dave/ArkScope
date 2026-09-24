(function (root) {
  "use strict";

  function contextError(evidence) {
    var error = new Error('Article document changed during capture');
    error.code = 'article_context_changed';
    error.evidence = evidence || null;
    return error;
  }

  function commentPolicy(comments, scope, nowMs) {
    scope = scope === 'history' ? 'history' : 'recent';
    var cutoff = nowMs - 30 * 86400000;
    var byId = new Map(), selected = new Set(), kinds = new Map();
    var counts = {recent_count:0,older_count:0,unknown_date_count:0,context_count:0};
    comments.forEach(function (row) {
      byId.set(row.comment_id, row);
      // Unzoned dates are SA's displayed browser-local time, not verified UTC.
      var date = typeof row.comment_date === 'string' ? Date.parse(row.comment_date) : NaN;
      var kind = !Number.isFinite(date) || date > nowMs ? 'unknown' : date >= cutoff ? 'recent' : 'older';
      kinds.set(row.comment_id, kind);
      counts[kind === 'unknown' ? 'unknown_date_count' : kind + '_count']++;
      if (scope === 'history' || kind !== 'older') selected.add(row.comment_id);
    });
    // Resolve context before filtering; parent age never determines reply age.
    Array.from(selected).forEach(function (id) {
      var seen = new Set();
      for (var row = byId.get(id); row && row.parent_comment_id && !seen.has(row.parent_comment_id);) {
        seen.add(row.parent_comment_id);
        row = byId.get(row.parent_comment_id);
        if (row) selected.add(row.comment_id);
      }
    });
    var priorities = {};
    comments.forEach(function (row) {
      if (kinds.get(row.comment_id) === 'older' && selected.has(row.comment_id) && scope !== 'history') counts.context_count++;
      priorities[row.dom_index] = selected.has(row.comment_id) ? 0 : 2;
    });
    // Priority is not retention: already materialized older rows cost no extra
    // provider request and remain available as context. Nothing is deleted.
    return {comments:comments,
      priorities:priorities, summary:Object.assign({scope:scope,window_days:scope === 'recent' ? 30 : null,
        reference_at:new Date(nowMs).toISOString(),cutoff_at:scope === 'recent' ? new Date(cutoff).toISOString() : null,
        date_basis:'displayed_date_browser_local_if_unzoned',coverage:'unverified',
        deferred_historical_controls:0},counts)};
  }

  // Events are observations, not cancellable navigation or a request counter.
  function watchNavigation(tabs, tabId, initialUrl) {
    var events = [], count = 0;
    function record(kind) {count++; if (events.length < 16) events.push(kind);}
    function updated(id, change) {
      if (id !== tabId) return;
      if (change.status === 'loading') record('document_loading');
      else if (change.url && change.url.split('#')[0] !== initialUrl.split('#')[0]) record('url_changed');
    }
    function removed(id) {if (id === tabId) record('tab_closed');}
    function created(tab) {if (tab.openerTabId === tabId) record('new_context');}
    tabs.onUpdated.addListener(updated);
    tabs.onRemoved.addListener(removed);
    tabs.onCreated.addListener(created);
    function evidence() {return {event_count:count, events:events.slice()};}
    return {
      assert:function () {if (count) throw contextError(evidence());},
      evidence:evidence,
      close:function () {
        tabs.onUpdated.removeListener(updated);
        tabs.onRemoved.removeListener(removed);
        tabs.onCreated.removeListener(created);
      },
    };
  }

  // Isolated-world witness also detects same-URL reloads and BFCache restoration.
  function documentState(options) {
    function articleId(value) {
      try {
        var url = new URL(value, location.href);
        if (url.protocol !== 'https:' || url.hostname !== 'seekingalpha.com'
            || url.username || url.password || url.port) return null;
        var match = url.pathname.match(/^\/(?:alpha-picks\/articles|article)\/(\d+)(?:-[^/]*)?\/?$/);
        return match ? match[1] : null;
      } catch (_) {return null;}
    }
    var canonical = document.querySelector('link[rel="canonical"][href]');
    var valid = articleId(location.href) === String(options.articleId)
      && (!canonical || articleId(canonical.href) === String(options.articleId));
    if (options.detailUrl !== undefined) valid = valid && articleId(options.detailUrl) === String(options.articleId);
    var state = globalThis.__arkCommentDocument;
    if (options.phase === 'begin' && valid) {
      if (state) removeEventListener('pagehide', state.onHide);
      state = {token:options.token,hidden:false};
      state.onHide = function () {state.hidden = true;};
      addEventListener('pagehide', state.onHide);
      globalThis.__arkCommentDocument = state;
    }
    var ok = valid && !!state && state.token === options.token && !state.hidden;
    if (options.phase === 'end' && state && state.token === options.token) {
      removeEventListener('pagehide', state.onHide);
      delete globalThis.__arkCommentDocument;
    }
    return {ok:ok, url:location.href};
  }

  // Serialized by scripting.executeScript: keep DOM helpers inside this function.
  async function scanPage(options) {
    options = options || {};
    if (options.token && (!globalThis.__arkCommentDocument
        || globalThis.__arkCommentDocument.token !== options.token
        || globalThis.__arkCommentDocument.hidden)) return {page_changed:true};
    var rowSelector = '[class*="border-t-share-separator-thin"]';
    var commentEls = document.querySelectorAll(rowSelector);
    var scrollBefore = window.scrollY;
    var atBottom = (window.innerHeight + window.scrollY) >= (document.body.scrollHeight - 200);
    var pageMiddle = document.body.scrollHeight / 2;
    var controls = Array.from(document.querySelectorAll('button, a, [role="button"]'));
    var initialUrl = location.href.split('#')[0];
    var policy = globalThis.SACommentCapture.commentPolicy(
      globalThis.__arkReadComments ? globalThis.__arkReadComments({includeDomIndex:true}).comments : [],
      options.scope, Number.isFinite(options.nowMs) ? options.nowMs : Date.now());
    var rowIndices = new Map(Array.from(commentEls).map(function (row, index) {return [row,index];}));

    function inReplyFooter(element) {
      // Observed SA layout: parent row + reply list ending in a separate footer.
      var footer = element.parentElement;
      var replies = footer && footer.parentElement;
      var parentRow = replies && replies.previousElementSibling;
      if (!footer || !footer.matches('div.mb-18.ml-52') || footer.children.length !== 1
          || footer.firstElementChild !== element || !replies || replies.tagName !== 'DIV'
          || !replies.classList.contains('print:block') || replies.lastElementChild !== footer
          || !parentRow || !parentRow.matches(rowSelector) || replies.parentElement.children.length !== 2) return false;
      var rows = Array.from(replies.children).slice(0, -1);
      return rows.length > 0 && rows.every(function (wrapper) {
        var row = wrapper.firstElementChild;
        return wrapper.tagName === 'DIV' && wrapper.children.length === 1 && row
          && row.matches(rowSelector) && row.classList.contains('pl-52');
      });
    }

    function inCommentScope(element) {
      if (element.closest(rowSelector) || inReplyFooter(element)) return true;
      for (var parent = element.parentElement; parent; parent = parent.parentElement) {
        if (parent.matches('body, main, article, .paywall-full-content')) return false;
        var heading = parent.querySelector('h2, h3, h4, [role="heading"]');
        if (heading && /^comments(?:\s*\([\d,]+\))?$/i.test(heading.textContent.trim())
            && parent.querySelector(rowSelector) && !parent.querySelector('article')) return true;
      }
      return false;
    }

    function unavailable(element) {
      if (element.disabled || element.getAttribute('aria-disabled') === 'true'
          || element.closest('[inert]')) return 'control_disabled';
      var style = getComputedStyle(element);
      var rect = element.getBoundingClientRect();
      if (element.offsetParent === null || style.display === 'none' || style.visibility === 'hidden'
          || rect.width <= 0 || rect.height <= 0) return 'control_hidden';
      return null;
    }

    function rejection(element, label) {
      if (element.parentElement && element.parentElement.closest('button, a, [role="button"]')) return 'nested_control';
      if (!inCommentScope(element)) return 'outside_comment_controls';
      var inlineText = element.closest('[class*="break-words"]');
      var textExpansion = inlineText && /^(?:show|read|see) more(?:\s*\.\.\.)?$/i.test(label);
      if (/^(?:show|read|see) less$/i.test(label)) return 'already_expanded';
      if (!textExpansion && !/^(?:show|load|view|see)\s+(?:(?:all|more|previous|older|\d+)\s+)*(?:comments?|replies|reply)(?:\s*\([\d,]+\))?$/i.test(label)) {
        return 'label_unrecognized';
      }
      var inactive = unavailable(element);
      if (inactive) return inactive;
      var link = element.closest('a[href]');
      if (link) {
        var href = link.getAttribute('href').trim();
        var base = document.querySelector('base[target]');
        var target = (link.getAttribute('target') || base && base.getAttribute('target') || '_self').toLowerCase();
        if (target !== '_self' || link.hasAttribute('download')) return 'link_new_context';
        if (!href.startsWith('#') || new URL(link.href).href.split('#')[0] !== initialUrl) return 'link_navigation';
      }
      var button = element.closest('button, input');
      if (button && button.form && button.type !== 'button') return 'form_submission';
      return null;
    }

    function describe(element, label, legacy, reason, index) {
      var link = element.closest('a[href]'), href = null;
      var ancestors = [];
      for (var parent = element.parentElement; parent && ancestors.length < 4; parent = parent.parentElement) {
        ancestors.push({tag:parent.tagName.toLowerCase(),role:parent.getAttribute('role'),
          classes:Array.from(parent.classList).slice(0, 6).map(function (name) {return name.slice(0, 80);})});
      }
      if (link) {
        try {
          var parsed = new URL(link.href);
          href = parsed.protocol === 'https:' || parsed.protocol === 'http:'
            ? parsed.origin + parsed.pathname : parsed.protocol;
        } catch (_) { href = 'invalid'; }
      }
      return {index:index, tag:element.tagName.toLowerCase(), label:label.slice(0, 100),
        role:element.getAttribute('role'), href:href, in_comment_scope:inCommentScope(element),
        legacy:legacy, guarded:reason === null, reason:reason, ancestors:ancestors};
    }

    function isLegacy(element) {
      var lower = (element.innerText || '').trim().toLowerCase();
      var rect = element.getBoundingClientRect();
      return element.matches('button, a') && rect.top + window.scrollY >= pageMiddle
        && (lower.indexOf('show') >= 0 || lower.indexOf('load more') >= 0 || lower.indexOf('more repl') >= 0)
        && element.offsetParent !== null;
    }
    var candidates = controls.map(function (element, index) {
      var label = (element.innerText || '').trim().replace(/\s+/g, ' ');
      var legacy = isLegacy(element);
      var reason = rejection(element, label);
      var description = describe(element, label, legacy, reason, index);
      var replyIntent = /^(?:show|load|view|see)\s+(?:(?:all|more|previous|older|newer|newest|latest|additional|hidden|\d+)\s+)*(?:comments?|replies|reply)(?:\s*\([\d,]+\))?$/i.test(label);
      var unresolved = reason !== null && ['control_hidden','control_disabled','already_expanded'].indexOf(reason) === -1
        && (replyIntent || legacy && description.in_comment_scope) && !unavailable(element);
      var row = element.closest(rowSelector);
      var priority = row && policy.priorities[rowIndices.get(row)];
      var textExpansion = element.closest('[class*="break-words"]')
        && /^(?:show|read|see) more(?:\s*\.\.\.)?$/i.test(label);
      // Hidden replies have unknown dates even when their parent is old.
      var deferred = reason === null && options.strategy !== 'observe'
        && policy.summary.scope === 'recent' && textExpansion && priority === 2;
      if (deferred) policy.summary.deferred_historical_controls++;
      description.deferred_historical = Boolean(deferred);
      return {element:element, legacy:legacy, reason:reason, unresolved:unresolved, description:description,
        priority:priority === 0 ? 0 : 1,deferred:deferred};
    });
    var accepted = new Set(candidates.filter(function (item) {return item.reason === null;})
      .map(function (item) {return item.element;}));
    candidates.forEach(function (item) {
      if (item.reason !== 'nested_control' || !item.unresolved) return;
      // A duplicate is covered only when its outer control is actually accepted.
      for (var parent = item.element.parentElement; parent; parent = parent.parentElement) {
        if (accepted.has(parent)) {item.unresolved = false; break;}
      }
    });
    var relevant = candidates.filter(function (item) {return item.legacy || item.reason === null || item.unresolved;});
    var audit = {legacy_candidates:candidates.filter(function (item) {return item.legacy;}).length,
      guarded_candidates:candidates.filter(function (item) {return item.reason === null;}).length,
      unresolved_candidates:candidates.filter(function (item) {return item.unresolved;}).length,
      items:relevant.slice(0, 64).map(function (item) {return item.description;}),
      omitted_count:Math.max(0, relevant.length - 64), clicked_indices:[]};
    var clicked = false, clickCount = 0, changed = false;
    var ordered = candidates.slice();
    if (options.strategy !== 'observe') ordered.sort(function (a,b) {return a.priority - b.priority;});
    for (var i = 0; i < ordered.length; i++) {
      var item = ordered[i];
      if (options.strategy === 'observe' ? !isLegacy(item.element) : item.reason !== null) continue;
      if (item.deferred) continue;
      if (!item.element.isConnected) continue;
      if (location.href.split('#')[0] !== initialUrl) {changed = true; break;}
      // Recheck after earlier clicks, which may have changed a later control.
      if (options.strategy !== 'observe' && rejection(item.element,
          (item.element.innerText || '').trim().replace(/\s+/g, ' ')) !== null) continue;
      item.element.click();
      clicked = true;
      clickCount++;
      if (audit.clicked_indices.length < 64) audit.clicked_indices.push(item.description.index);
    }
    changed = changed || location.href.split('#')[0] !== initialUrl;

    var loading = false;
    var loadingNodes = document.querySelectorAll(
      '[aria-busy="true"], [role="progressbar"], [class*="loading"], [class*="spinner"]'
    );
    for (var l = 0; l < loadingNodes.length; l++) {
      var loadingRect = loadingNodes[l].getBoundingClientRect();
      var loadingTop = loadingRect.top + window.scrollY;
      var loadingStyle = getComputedStyle(loadingNodes[l]);
      if (loadingTop >= pageMiddle && loadingRect.width > 0 && loadingRect.height > 0
          && loadingStyle.display !== 'none' && loadingStyle.visibility !== 'hidden') {
        loading = true;
        break;
      }
    }
    var traversalSteps = 0, renderIncomplete = false;
    if (!changed) {
      var advance = window.innerHeight;
      if (options.strategy !== 'observe') {
        // Locate the materialized frontier, but render intermediate viewports:
        // an IntersectionObserver may sit before already expanded replies.
        for (var r = 0; r < commentEls.length; r++) {
          var rect = commentEls[r].getBoundingClientRect();
          var bottom = Number.isFinite(rect.bottom) ? rect.bottom : rect.top + rect.height;
          if (rect.width > 0 && rect.height > 0 && Number.isFinite(bottom)) {
            advance = Math.max(advance, bottom - window.innerHeight);
          }
        }
      }
      if (advance <= window.innerHeight || options.strategy === 'observe') {
        window.scrollBy(0, window.innerHeight);
        traversalSteps++;
      } else {
        var deadline = Math.min(Date.now() + 500,
          Number.isFinite(options.deadlineMs) ? options.deadlineMs : Infinity);
        for (var step = 0; step < 8 && advance > 0 && Date.now() < deadline; step++) {
          if (location.href.split('#')[0] !== initialUrl) {changed = true; break;}
          var before = window.scrollY;
          window.scrollBy(0, Math.min(advance, window.innerHeight * 0.75));
          traversalSteps++;
          var moved = window.scrollY - before;
          if (moved <= 0) break;
          advance -= moved;
          var painted = await new Promise(function (resolve) {
            var first, second;
            var timer = setTimeout(function () {
              cancelAnimationFrame(first); cancelAnimationFrame(second); resolve(false);
            }, Math.max(1, Math.min(100, deadline - Date.now())));
            first = requestAnimationFrame(function () {
              second = requestAnimationFrame(function () {clearTimeout(timer); resolve(true);});
            });
          });
          if (!painted) {renderIncomplete = true; break;}
          if (options.token && (!globalThis.__arkCommentDocument
              || globalThis.__arkCommentDocument.token !== options.token
              || globalThis.__arkCommentDocument.hidden)) {changed = true; break;}
          if (document.querySelectorAll(rowSelector).length !== commentEls.length) break;
        }
      }
    }
    changed = changed || location.href.split('#')[0] !== initialUrl;
    return {comments:commentEls.length, atBottom:atBottom, clicked:clicked,
      click_count:clickCount, loading:loading || renderIncomplete, page_changed:changed, control_audit:audit,
      traversal_steps:traversalSteps,render_wait_incomplete:renderIncomplete,
      recency:policy.summary,
      progress:{scroll_y_before:scrollBefore,scroll_y_after:window.scrollY,
        document_height:document.body.scrollHeight,viewport_height:window.innerHeight}};
  }

  root.SACommentCapture = Object.freeze({scanPage:scanPage, documentState:documentState,
    watchNavigation:watchNavigation, contextError:contextError,commentPolicy:commentPolicy});
}(globalThis));
