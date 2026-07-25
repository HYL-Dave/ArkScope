import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import {JSDOM} from "jsdom";

const [extensionDir, scenario, fixtureJson = "{}"] = process.argv.slice(2);
const fixture = JSON.parse(fixtureJson);

function clone(value) {
  return value === undefined ? undefined : JSON.parse(JSON.stringify(value));
}

function responseFor(message) {
  if (message.action === "ensure_auto_sync_alarms") return {status: "ok"};
  if (message.action === "get_extension_action_limits") {
    return clone(fixture.actionLimits || {status: "error", error_code: "not_configured"});
  }
  if (message.action === "market_news_recovery_preview") {
    const previews = fixture.previews || {};
    return clone(previews[message.kind] || {status: "no_work", can_start: false, target_count: 0});
  }
  if (message.action === "market_news_recovery_state") {
    return clone(fixture.state || {status: "error", error_code: "repair_not_found"});
  }
  if (message.action === "market_news_recovery_start") {
    return clone(fixture.startResult || {status: "error", error_code: "not_configured"});
  }
  if (message.action === "market_news_recovery_resume") {
    return clone(fixture.resumeResult || fixture.state || {status: "error"});
  }
  if (message.action === "refresh" || message.action === "refresh_market_news") {
    return {status: "ok"};
  }
  return {status: "ok", events: [], total: 0};
}

function createChrome(initialStorage) {
  const data = clone(initialStorage || {});
  const sent = [];
  const native = [];
  const messageListeners = [];
  const storageListeners = [];

  function select(keys) {
    if (keys == null) return clone(data);
    if (typeof keys === "string") return {[keys]: clone(data[keys])};
    if (Array.isArray(keys)) {
      return Object.fromEntries(keys.map((key) => [key, clone(data[key])]));
    }
    return Object.fromEntries(
      Object.entries(keys).map(([key, fallback]) => [
        key,
        data[key] === undefined ? clone(fallback) : clone(data[key]),
      ]),
    );
  }

  const chrome = {
    runtime: {
      lastError: null,
      onMessage: {addListener(listener) { messageListeners.push(listener); }},
      sendMessage(message, callback) {
        sent.push(clone(message));
        const response = responseFor(message);
        if (callback) queueMicrotask(() => callback(clone(response)));
        return Promise.resolve(clone(response));
      },
      sendNativeMessage(_host, message, callback) {
        native.push(clone(message));
        const response = {status: "ok", events: [], total: 0};
        if (callback) queueMicrotask(() => callback(response));
      },
    },
    storage: {
      local: {
        get(keys, callback) {
          const result = select(keys);
          if (callback) queueMicrotask(() => callback(result));
          return Promise.resolve(result);
        },
        set(values, callback) {
          const changes = {};
          for (const [key, value] of Object.entries(values)) {
            changes[key] = {oldValue: clone(data[key]), newValue: clone(value)};
            data[key] = clone(value);
          }
          for (const listener of storageListeners) listener(changes, "local");
          if (callback) queueMicrotask(callback);
          return Promise.resolve();
        },
        remove(keys, callback) {
          for (const key of Array.isArray(keys) ? keys : [keys]) delete data[key];
          if (callback) queueMicrotask(callback);
          return Promise.resolve();
        },
      },
      onChanged: {addListener(listener) { storageListeners.push(listener); }},
    },
  };
  return {chrome, data, sent, native, messageListeners};
}

function text(node) {
  return node ? node.textContent.replace(/\s+/g, " ").trim() : "";
}

function rgba(value) {
  const match = String(value || "").match(
    /^rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)(?:\s*,\s*([\d.]+))?\s*\)$/,
  );
  if (!match) return null;
  return [
    Number(match[1]),
    Number(match[2]),
    Number(match[3]),
    match[4] == null ? 1 : Number(match[4]),
  ];
}

function composite(foreground, background) {
  const alpha = foreground[3] + background[3] * (1 - foreground[3]);
  if (alpha === 0) return [0, 0, 0, 0];
  return [
    (foreground[0] * foreground[3]
      + background[0] * background[3] * (1 - foreground[3])) / alpha,
    (foreground[1] * foreground[3]
      + background[1] * background[3] * (1 - foreground[3])) / alpha,
    (foreground[2] * foreground[3]
      + background[2] * background[3] * (1 - foreground[3])) / alpha,
    alpha,
  ];
}

function resolvedBackground(element) {
  const layers = [];
  for (let current = element; current; current = current.parentElement) {
    const layer = rgba(current.ownerDocument.defaultView.getComputedStyle(current).backgroundColor);
    if (layer && layer[3] > 0) layers.push(layer);
  }
  let result = [255, 255, 255, 1];
  for (const layer of layers.reverse()) result = composite(layer, result);
  return result.slice(0, 3).map((channel) => Math.round(channel));
}

function selectorFor(element) {
  if (element.id) return "#" + element.id;
  const classes = [...element.classList];
  return element.tagName.toLowerCase() + (classes.length ? "." + classes.join(".") : "");
}

function styleSample(element, label) {
  const style = element.ownerDocument.defaultView.getComputedStyle(element);
  const foreground = rgba(style.color);
  const border = rgba(style.borderTopColor);
  return {
    label,
    selector: selectorFor(element),
    text: text(element),
    foreground: foreground ? foreground.slice(0, 3) : null,
    background: resolvedBackground(element),
    surrounding: resolvedBackground(element.parentElement || element),
    border: border ? border.slice(0, 3) : null,
    borderStyle: style.borderTopStyle,
    borderWidth: Number.parseFloat(style.borderTopWidth) || 0,
    fontSize: Number.parseFloat(style.fontSize) || 0,
    fontWeight: Number.parseFloat(style.fontWeight) || 400,
    disabled: element.matches("button") && element.disabled,
    actionId: element.dataset.actionId || null,
  };
}

function exposeContrastStates(document, popupFixture) {
  const view = document.defaultView;
  const incidentPreview = popupFixture.previews?.incident_window;
  if (incidentPreview && typeof view.renderRecoveryConfirmation === "function") {
    view.renderRecoveryConfirmation(incidentPreview);
  }
  if (typeof view.renderReconciliationQueue === "function") {
    view.renderReconciliationQueue({
      total: 1,
      events: [{
        lineage_id: 1,
        symbol: "TEST",
        role: "entry",
        event_anchor_date: "2026-07-20",
        reason_code: "review_required",
        candidates: [{
          article_id: "fixture-article",
          url: "https://seekingalpha.com/alpha-picks/articles/1-fixture",
          title: "Fixture article",
          content_state: "complete",
          published_date: "2026-07-20",
          evidence_codes: ["exact_ticker"],
          reason_code: "review_required",
        }],
      }],
    });
  }
  if (typeof view.renderManualConfirmations === "function") {
    view.renderManualConfirmations([{symbol: "TEST"}]);
  }

  document.querySelectorAll("details").forEach((node) => { node.open = true; });
  document.querySelectorAll("[hidden]").forEach((node) => { node.hidden = false; });
  document.querySelectorAll(".action-description").forEach((node) => {
    node.style.display = "block";
  });
  document.querySelectorAll("button").forEach((node) => { node.disabled = false; });
  document.getElementById("marketNewsAutoSyncResolved").textContent =
    "Every 5 minutes in the current ET window";
  const status = document.getElementById("status");
  status.className = "partial";
  status.textContent = "Needs attention";
}

function contrastAudit(document) {
  const textSamples = [];
  const walker = document.createTreeWalker(document.body, document.defaultView.NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (!node.nodeValue.trim()) continue;
    const element = node.parentElement;
    const style = document.defaultView.getComputedStyle(element);
    if (style.display === "none" || style.visibility === "hidden") continue;
    textSamples.push(styleSample(element, selectorFor(element)));
  }

  const status = document.getElementById("status");
  const statusSamples = ["success", "partial", "error", "empty"].map((state) => {
    status.className = state;
    return styleSample(status, "#status." + state);
  });
  status.className = "partial";

  const controls = [...document.querySelectorAll("button")].map((button) =>
    styleSample(button, selectorFor(button)),
  );
  const disabledControls = [...document.querySelectorAll("button")].map((button) => {
    button.disabled = true;
    const sample = styleSample(button, selectorFor(button) + ":disabled");
    button.disabled = false;
    return sample;
  });
  return {textSamples, statusSamples, controls, disabledControls};
}

function snapshot(document, sent) {
  const actions = [...document.querySelectorAll("[data-action-id]")]
    .filter((node) => node.matches("button"))
    .map((button) => {
      const descriptionId = button.getAttribute("aria-describedby");
      return {
        id: button.dataset.actionId,
        label: text(button),
        group: button.closest("[data-action-group]")?.dataset.actionGroup || null,
        descriptionId,
        description: text(document.getElementById(descriptionId)),
        title: button.getAttribute("title"),
      };
    });
  const disclosure = [...document.querySelectorAll("#actionHelp tbody tr")].map((row) => ({
    id: row.dataset.actionId,
    cells: [...row.querySelectorAll("td")].map(text),
  }));
  const advanced = document.getElementById("marketNewsRecoveryAdvanced");
  const retry = document.getElementById("retryRecordedFailuresBtn");
  const confirmation = document.getElementById("recoveryConfirmation");
  const recoveryStatus = document.getElementById("marketNewsRecoveryStatus");
  const advancedPreview = document.getElementById("marketNewsRecoveryPreview");
  const reviewScope = document.getElementById("reviewRecoveryScopeBtn");
  return {
    actions,
    disclosure,
    bodyText: text(document.body),
    bodyHtml: document.body.innerHTML,
    advanced: advanced ? {open: advanced.open, hidden: advanced.hidden} : null,
    retry: retry ? {hidden: retry.hidden, text: text(retry)} : null,
    confirmation: confirmation ? {hidden: confirmation.hidden, text: text(confirmation)} : null,
    recoveryStatus: text(recoveryStatus),
    recoveryStatusRole: recoveryStatus?.getAttribute("role") || null,
    lastRunStatus: text(document.getElementById("lastRunStatus")),
    advancedPreview: text(advancedPreview),
    reviewScope: reviewScope
      ? {hidden: reviewScope.hidden, text: text(reviewScope)}
      : null,
    autoSyncGroups: {
      alpha: document.getElementById("alphaPicksAutoSyncToggle")
        ?.closest("[data-action-group]")?.dataset.actionGroup || null,
      market: document.getElementById("marketNewsAutoSyncToggle")
        ?.closest("[data-action-group]")?.dataset.actionGroup || null,
    },
    activeId: document.activeElement && document.activeElement.id,
    sent: clone(sent),
  };
}

async function settle() {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await new Promise((resolve) => setTimeout(resolve, 0));
}

async function runPopup() {
  const htmlPath = path.join(extensionDir, "popup.html");
  const dom = new JSDOM(fs.readFileSync(htmlPath, "utf8"), {
    url: "moz-extension://arkscope/popup.html",
    runScripts: "outside-only",
    pretendToBeVisual: true,
  });
  const mocks = createChrome(fixture.storage);
  dom.window.chrome = mocks.chrome;
  dom.window.console = console;
  dom.window.setInterval = () => 1;
  dom.window.clearInterval = () => {};
  dom.window.confirm = () => {
    throw new Error("window.confirm is forbidden");
  };

  const scripts = [
    "popup_action_catalog.js",
    "reconciliation_ui.js",
    "popup.js",
  ];
  try {
    for (const name of scripts) {
      const scriptPath = path.join(extensionDir, name);
      vm.runInContext(
        fs.readFileSync(scriptPath, "utf8"),
        dom.getInternalVMContext(),
        {filename: scriptPath},
      );
    }
    await settle();

    if (scenario === "click_retry") {
      dom.window.document.getElementById("retryRecordedFailuresBtn")?.click();
      await settle();
    } else if (scenario === "click_incident") {
      dom.window.document.getElementById("incidentRecoveryBtn")?.click();
      await settle();
    } else if (scenario === "escape_confirmation") {
      dom.window.document.getElementById("incidentRecoveryBtn")?.click();
      await settle();
      dom.window.document.getElementById("recoveryConfirmation")?.dispatchEvent(
        new dom.window.KeyboardEvent("keydown", {key: "Escape", bubbles: true}),
      );
      await settle();
    } else if (scenario === "confirm_recovery") {
      dom.window.document.getElementById("incidentRecoveryBtn")?.click();
      await settle();
      dom.window.document.querySelector('[data-action="confirm-recovery"]')?.click();
      await settle();
    } else if (scenario === "click_resume") {
      dom.window.document.getElementById("resumeRecoveryBtn")?.click();
      await settle();
    } else if (scenario === "focus_descriptions") {
      for (const button of dom.window.document.querySelectorAll("[data-action-id]")) {
        button.focus();
        button.dispatchEvent(new dom.window.FocusEvent("focusin", {bubbles: true}));
      }
    } else if (scenario === "contrast_audit") {
      exposeContrastStates(dom.window.document, fixture);
    }
    const result = snapshot(dom.window.document, mocks.sent);
    if (scenario === "contrast_audit") {
      result.contrastAudit = contrastAudit(dom.window.document);
    }
    return result;
  } finally {
    dom.window.close();
  }
}

process.stdout.write(JSON.stringify(await runPopup()));
