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
  if (message.action === 'enable_sa_updates_here' && fixture.activationError) return {status:'error',error_code:fixture.activationError,activation_step:'configure'};
  if (message.action === 'preview_company_refresh') {
    const count=(message.config?.target_mode==='watchlist' ? (fixture.watchlistCount || 180) : message.config?.tickers?.length || 0)
      * (message.config?.statements?.length || 0) * (message.config?.views?.length || 0);
    return {status:'ok',counts:{missing:count,due:0,reusable:0,blocked:0},total_scopes:count,first_fill:count>0,
      pacing_lower_bound_seconds:Math.max(0,count-1)*(message.config?.financial_gap_seconds || 60),
      observed_duration:{sample_count:0,mean_ms:null,total_scopes:count}};
  }
  if (['get_company_refresh','save_company_refresh','enable_sa_updates_here','run_company_refresh'].includes(message.action)) {
    return clone(fixture.companyRefresh || {status:"ok",config:message.config || {
      enabled:false,target_mode:'watchlist',tickers:[],statements:['income_statement'],views:['annual'],interval_days:7
    },collector:{status:'ok',generation:0,owner:null,policy:null},scopes:[],running:false,paused_reason:null});
  }
  if (message.action === "capture_company_data") return clone(fixture.companyResult || {status: "error", error_code: "sa_company_page_unsupported"});
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
    return Object.hasOwn(fixture, "refreshResult") ? clone(fixture.refreshResult) : {status: "ok"};
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
        const respond = () => {
          if (fixture.runtimeError && ["refresh", "refresh_market_news"].includes(message.action)) {
            chrome.runtime.lastError = {message: fixture.runtimeError};
          }
          if (callback) callback(clone(response));
          chrome.runtime.lastError = null;
        };
        if (fixture.runtimeDuringAction === message.action) {
          queueMicrotask(async () => {
            fixture.companyRefresh = fixture.nextCompanyRefresh;
            await chrome.storage.local.set({saAcquisitionRuntime: fixture.runtimeSignal});
            setTimeout(respond, 0);
          });
        } else if (callback) queueMicrotask(respond);
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
    layout: {
      bodyMinWidth: document.defaultView.getComputedStyle(document.body).minWidth,
      bodyWidth: document.defaultView.getComputedStyle(document.body).width,
    },
    bodyText: text(document.body),
    bodyHtml: document.body.innerHTML,
    advanced: advanced ? {open: advanced.open, hidden: advanced.hidden} : null,
    retry: retry ? {hidden: retry.hidden, text: text(retry)} : null,
    confirmation: confirmation ? {hidden: confirmation.hidden, text: text(confirmation)} : null,
    recoveryStatus: text(recoveryStatus),
    recoveryStatusRole: recoveryStatus?.getAttribute("role") || null,
    lastRunStatus: text(document.getElementById("lastRunStatus")),
    companyCaptureStatus: text(document.getElementById("companyCaptureStatus")),
    companyCaptureDisabled: document.getElementById("companyCaptureBtn")?.disabled,
    companyRefreshStatus: text(document.getElementById("companyRefreshStatus")),
    companyCollectorStatus: text(document.getElementById("companyCollectorStatus")),
    companyRefreshTargets: text(document.getElementById("companyRefreshTargets")),
    companyRefreshTargetMode: document.getElementById("companyRefreshTargetMode")?.value,
    companyRefreshTickerRequired: document.getElementById("companyRefreshTickers")?.required,
    companyRefreshNowDisabled: document.getElementById("companyRefreshNow")?.disabled,
    companyRefreshEnabled: document.getElementById('companyRefreshEnabled')?.checked,
    companyScopePreview: text(document.getElementById('companyScopePreview')),
    acquisitionLive: text(document.getElementById('saAcquisitionLive')),
    acquisitionLiveRole: document.getElementById('saAcquisitionLive')?.getAttribute('role'),
    acquisitionLiveInDetails: !!document.getElementById('saAcquisitionLive')?.closest('details'),
    acquisitionWarning: text(document.getElementById('saAcquisitionWarning')),
    acquisitionWarningHidden: document.getElementById('saAcquisitionWarning')?.hidden,
    acquisitionRecoveryShortcutHidden: document.getElementById('saAcquisitionReviewRecovery')?.hidden,
    acquisitionRecoverDisabled: document.getElementById('companyCollectorRecover')?.disabled,
    companyAdvancedOpen: document.getElementById('companyAdvanced')?.open,
    companyOptionsOpen: document.getElementById('companyRefreshOptions')?.open,
    refreshAttemptStatus: text(document.getElementById('refreshAttemptStatus')),
    refreshAttemptRole: document.getElementById('refreshAttemptStatus')?.getAttribute('role'),
    storedAlphaStatus: text(document.getElementById('status')),
    storedNewsStatus: text(document.getElementById('marketNewsStatus')),
    refreshButtonsDisabled: ['quickBtn','fullBtn','backfillBtn','marketNewsBtn','marketNewsCatchupBtn'].map(
      id => document.getElementById(id)?.disabled),
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
    url: fixture.browser === "chrome" ? "chrome-extension://arkscope/popup.html" : "moz-extension://arkscope/popup.html",
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

  const scripts = Array.from(dom.window.document.querySelectorAll("script[src]"), node => node.getAttribute("src"));
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

    if (scenario === 'acquisition_runtime_wakeup') {
      fixture.companyRefresh = fixture.nextCompanyRefresh;
      await mocks.chrome.storage.local.set({saAcquisitionRuntime: fixture.runtimeSignal});
      await settle();
    } else if (scenario === 'review_stopped_acquisition') {
      dom.window.document.getElementById('companyRefreshOptions').open = false;
      dom.window.document.getElementById('companyAdvanced').open = false;
      dom.window.document.getElementById('saAcquisitionReviewRecovery')?.click();
      await settle();
    } else if (scenario === 'recover_acquisition') {
      dom.window.document.getElementById('companyRecoveryConfirmed').checked = fixture.confirmStopped === true;
      dom.window.document.getElementById('companyCollectorRecover').click();
      await settle();
    } else if (scenario === 'click_alpha_refresh' || scenario === 'click_news_refresh') {
      dom.window.document.getElementById(scenario === 'click_alpha_refresh' ? 'quickBtn' : 'marketNewsBtn').click();
      await settle();
      if (fixture.storageAfterClick) {
        await mocks.chrome.storage.local.set(fixture.storageAfterClick);
        await settle();
      }
    } else if (scenario === 'preview_company_scope' || scenario === 'enable_sa_updates_here') {
      const doc=dom.window.document;
      doc.getElementById('companyRefreshTargetMode').value='watchlist';
      doc.getElementById('companyRefreshEnabled').checked=true;
      doc.querySelectorAll('[name="companyRefreshStatement"],[name="companyRefreshView"]').forEach(input=>input.checked=true);
      const gap=doc.getElementById('companyFinancialGap'); if(gap) gap.value='15';
      doc.getElementById('companyBudgetEnabled').checked=true;
      doc.getElementById('companyBudgetEnabled').dispatchEvent(new dom.window.Event('input',{bubbles:true}));
      for(const [key,value] of Object.entries({hour_limit:20,day_limit:100,hour_reserve:5,day_reserve:20})) {
        const input=doc.querySelector('[name="'+key+'"]');if(input)input.value=String(value);
      }
      const confirmed=doc.getElementById('companyActivationConfirmed');if(confirmed)confirmed.checked=true;
      doc.getElementById('companyRefreshTargetMode').dispatchEvent(new dom.window.Event('input',{bubbles:true}));
      await settle();
      if(scenario==='enable_sa_updates_here') {doc.getElementById('companyCollectorSelect')?.click();await settle();}
    } else if (scenario === "configure_company_watchlist") {
      const select = dom.window.document.getElementById("companyRefreshTargetMode");
      if (select) { select.value="watchlist"; select.dispatchEvent(new dom.window.Event("change", {bubbles:true})); }
      dom.window.document.getElementById("companyRefreshForm")?.dispatchEvent(new dom.window.Event("submit", {bubbles:true,cancelable:true}));
      await settle();
    } else if (scenario === "select_company_collector") {
      dom.window.document.getElementById("companyCollectorSelect")?.click();
      await settle();
    } else if (scenario === "configure_company_refresh") {
      const doc = dom.window.document;
      doc.getElementById("companyRefreshTargetMode").value = "manual";
      doc.getElementById("companyRefreshTargetMode").dispatchEvent(new dom.window.Event("change", {bubbles:true}));
      const ticker = doc.getElementById("companyRefreshTickers");
      if (ticker) ticker.value = "amd, aapl AMD";
      const interval = doc.getElementById("companyRefreshDays");
      if (interval) interval.value = "14";
      const enabled = doc.getElementById("companyRefreshEnabled");
      if (enabled) enabled.checked = true;
      const quarterly = doc.querySelector('[name="companyRefreshView"][value="quarterly"]');
      if (quarterly) quarterly.checked = true;
      doc.getElementById("companyRefreshForm")?.dispatchEvent(new dom.window.Event("submit", {bubbles:true,cancelable:true}));
      await settle();
    } else if (scenario === "update_company_due") {
      dom.window.document.getElementById("companyRefreshNow")?.click();
      await settle();
    } else if (scenario === "company_capture_storage_update") {
      await mocks.chrome.storage.local.set({lastCompanyCapture: fixture.companyResult});
      await settle();
    } else if (scenario === "capture_company") {
      dom.window.document.getElementById("companyCaptureBtn")?.click();
      await settle();
    } else if (scenario === "click_retry") {
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
    if (fixture.runtimeDuringAction) await settle();
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
