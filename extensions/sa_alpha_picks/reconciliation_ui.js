(function (root) {
  "use strict";

  var ROLE_LABELS = {
    entry: "Entry",
    exit: "Exit",
  };
  var EVIDENCE_LABELS = {
    list_ticker: "List ticker",
    detail_ticker: "Article ticker",
    exact_ticker: "Ticker match",
    date_within_window: "Date within window",
    exact_event_date: "Event date match",
    user_selected: "User selected",
    user_confirmed: "User confirmed",
  };
  var REASON_LABELS = {
    ambiguous_candidates: "Multiple candidate articles",
    ticker_metadata_conflict: "List and article tickers conflict",
    missing_event_anchor: "Event date missing; manual review required",
    outside_match_window: "Article date outside matching window",
    date_mismatch: "Article date differs from event",
    replacement: "Replaces current link",
    no_candidate: "No candidate article",
    review_required: "Manual review required",
  };

  function element(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = String(text);
    return node;
  }

  function reasonLabel(code) {
    return REASON_LABELS[code] || "Manual review required";
  }

  function eventPayload(event, candidate, confirmWarnings) {
    return {
      lineage_id: event.lineage_id,
      role: event.role,
      event_anchor_date: event.event_anchor_date,
      article_id: String(candidate.article_id),
      article_url: String(candidate.url),
      replace_link_id: candidate.replace_link_id == null
        ? (event.current_link && event.current_link.link_id) || null
        : candidate.replace_link_id,
      confirm_warnings: confirmWarnings === true,
    };
  }

  function rejectionPayload(event, candidate) {
    return {
      lineage_id: event.lineage_id,
      role: event.role,
      event_anchor_date: event.event_anchor_date,
      article_id: String(candidate.article_id),
      reason_code: "user_rejected",
    };
  }

  function showActionError(candidateNode) {
    var prior = candidateNode.querySelector("[data-action-error]");
    if (prior) prior.remove();
    var error = element("div", "reconciliation-action-error", "Action failed. Try again.");
    error.setAttribute("data-action-error", "");
    candidateNode.appendChild(error);
  }

  function notifyChanged(handlers, result) {
    if (typeof handlers.onChanged === "function") {
      handlers.onChanged(result);
    }
  }

  function renderConfirmation(candidateNode, event, candidate, handlers, result) {
    var prior = candidateNode.querySelector("[data-confirmation]");
    if (prior) prior.remove();

    var confirmation = element("div", "reconciliation-confirmation");
    confirmation.setAttribute("data-confirmation", "");
    var warningCodes = Array.isArray(result.warnings) ? result.warnings : [];
    var warningText = warningCodes.length > 0
      ? warningCodes.map(reasonLabel).join("; ")
      : "This link requires another confirmation";
    confirmation.appendChild(element("div", "reconciliation-warning", warningText));

    var actions = element("div", "reconciliation-confirm-actions");
    var confirmButton = element("button", "reconciliation-confirm", "Use anyway");
    confirmButton.type = "button";
    confirmButton.setAttribute("data-action", "confirm-candidate");
    var cancelButton = element("button", "reconciliation-cancel", "Cancel");
    cancelButton.type = "button";
    cancelButton.setAttribute("data-action", "cancel-confirmation");
    actions.append(confirmButton, cancelButton);
    confirmation.appendChild(actions);
    candidateNode.appendChild(confirmation);

    cancelButton.addEventListener("click", function () {
      confirmation.remove();
    });
    confirmButton.addEventListener("click", function () {
      if (typeof handlers.onUseCandidate !== "function") return;
      confirmButton.disabled = true;
      Promise.resolve(
        handlers.onUseCandidate(eventPayload(event, candidate, true))
      ).then(function (confirmed) {
        if (confirmed && confirmed.status === "ok") {
          confirmation.remove();
          notifyChanged(handlers, confirmed);
          return;
        }
        confirmButton.disabled = false;
        showActionError(candidateNode);
      }).catch(function () {
        confirmButton.disabled = false;
        showActionError(candidateNode);
      });
    });
  }

  function candidateNode(event, candidate, handlers) {
    var node = element("article", "reconciliation-candidate");
    var title = element("a", "reconciliation-candidate-title");
    title.textContent = candidate.title || "Alpha Picks article";
    title.href = candidate.url;
    title.target = "_blank";
    title.rel = "noreferrer";
    node.appendChild(title);

    var details = element("div", "reconciliation-candidate-details");
    details.appendChild(element(
      "span",
      "reconciliation-content-state",
      candidate.content_state === "complete" ? "Full text" : "Headline only"
    ));
    if (candidate.published_date) {
      details.appendChild(element("span", "", "Article date " + candidate.published_date));
    }
    node.appendChild(details);

    var evidenceCodes = Array.isArray(candidate.evidence_codes)
      ? candidate.evidence_codes
      : [];
    var evidenceLabels = evidenceCodes
      .map(function (code) { return EVIDENCE_LABELS[code]; })
      .filter(Boolean);
    if (evidenceLabels.length > 0) {
      node.appendChild(element(
        "div",
        "reconciliation-evidence",
        "Evidence: " + evidenceLabels.join(", ")
      ));
    }
    if (candidate.reason_code && candidate.reason_code !== "review_required") {
      node.appendChild(element(
        "div",
        "reconciliation-candidate-reason",
        reasonLabel(candidate.reason_code)
      ));
    }

    var actions = element("div", "reconciliation-candidate-actions");
    var useButton = element("button", "reconciliation-use", "Use article");
    useButton.type = "button";
    useButton.setAttribute("data-action", "use-candidate");
    var rejectButton = element("button", "reconciliation-reject", "Reject candidate");
    rejectButton.type = "button";
    rejectButton.setAttribute("data-action", "reject-candidate");
    actions.append(useButton, rejectButton);
    node.appendChild(actions);

    if (typeof handlers.onUseCandidate !== "function") useButton.disabled = true;
    if (typeof handlers.onRejectCandidate !== "function") rejectButton.disabled = true;

    useButton.addEventListener("click", function () {
      if (typeof handlers.onUseCandidate !== "function") return;
      useButton.disabled = true;
      Promise.resolve(
        handlers.onUseCandidate(eventPayload(event, candidate, false))
      ).then(function (result) {
        useButton.disabled = false;
        if (result && result.status === "confirmation_required") {
          renderConfirmation(node, event, candidate, handlers, result);
          return;
        }
        if (result && result.status === "ok") {
          notifyChanged(handlers, result);
          return;
        }
        showActionError(node);
      }).catch(function () {
        useButton.disabled = false;
        showActionError(node);
      });
    });

    rejectButton.addEventListener("click", function () {
      if (typeof handlers.onRejectCandidate !== "function") return;
      rejectButton.disabled = true;
      Promise.resolve(
        handlers.onRejectCandidate(rejectionPayload(event, candidate))
      ).then(function (result) {
        rejectButton.disabled = false;
        if (result && result.status === "ok") {
          notifyChanged(handlers, result);
          return;
        }
        showActionError(node);
      }).catch(function () {
        rejectButton.disabled = false;
        showActionError(node);
      });
    });
    return node;
  }

  function renderQueue(container, queue, handlers) {
    handlers = handlers || {};
    var events = queue && Array.isArray(queue.events) ? queue.events : [];
    var total = queue && Number.isInteger(queue.total) ? queue.total : events.length;
    container.replaceChildren();
    container.appendChild(element(
      "div",
      "reconciliation-summary",
      total > 0 ? total + " events to review" : "No events to review"
    ));

    events.forEach(function (event) {
      var eventNode = element("section", "reconciliation-event");
      var role = ROLE_LABELS[event.role] || "Event";
      eventNode.appendChild(element(
        "div",
        "reconciliation-event-title",
        String(event.symbol || "Unknown ticker") + " · " + role
      ));
      eventNode.appendChild(element(
        "div",
        "reconciliation-event-meta",
        "Event date: " + (event.event_anchor_date || "Not provided")
      ));
      if (event.reason_code) {
        eventNode.appendChild(element(
          "div",
          "reconciliation-event-reason",
          reasonLabel(event.reason_code)
        ));
      }
      var candidates = Array.isArray(event.candidates) ? event.candidates : [];
      if (candidates.length === 0) {
        eventNode.appendChild(element(
          "div",
          "reconciliation-no-candidate",
          "No candidate articles available"
        ));
      } else {
        candidates.forEach(function (candidate) {
          eventNode.appendChild(candidateNode(event, candidate, handlers));
        });
      }
      container.appendChild(eventNode);
    });
  }

  function parseAdvancedLines(text) {
    var items = [];
    var errors = [];
    String(text || "").split(/\r?\n/).forEach(function (rawLine, index) {
      var line = rawLine.trim();
      if (!line) return;
      var parts = line.split(/\s+/);
      if (parts.length !== 4) {
        errors.push({ line: index + 1, message: "Expected: TICKER ROLE DATE ARTICLE_URL" });
        return;
      }
      var symbol = parts[0].toUpperCase();
      var role = parts[1];
      var anchor = parts[2];
      var parsedDate = new Date(anchor + "T00:00:00Z");
      var validDate = /^\d{4}-\d{2}-\d{2}$/.test(anchor)
        && !isNaN(parsedDate.getTime())
        && parsedDate.toISOString().slice(0, 10) === anchor;
      var parsedUrl = null;
      try {
        parsedUrl = new URL(parts[3]);
      } catch (_) {
        parsedUrl = null;
      }
      var validUrl = parsedUrl
        && parsedUrl.protocol === "https:"
        && parsedUrl.hostname === "seekingalpha.com"
        && !parsedUrl.username
        && !parsedUrl.password
        && !parsedUrl.search
        && !parsedUrl.hash
        && /^\/alpha-picks\/articles\/\d+(?:-[^/]+)?\/?$/.test(parsedUrl.pathname);
      if (
        !/^[A-Z][A-Z.]{0,9}$/.test(symbol)
        || (role !== "entry" && role !== "exit")
        || !validDate
        || !validUrl
      ) {
        errors.push({ line: index + 1, message: "Invalid event or article URL" });
        return;
      }
      items.push({
        symbol: symbol,
        role: role,
        event_anchor_date: anchor,
        url: parsedUrl.href,
      });
    });
    return { items: items, errors: errors };
  }

  root.ArkScopeReconciliationUI = {
    renderQueue: renderQueue,
    parseAdvancedLines: parseAdvancedLines,
  };
})(typeof window !== "undefined" ? window : globalThis);
