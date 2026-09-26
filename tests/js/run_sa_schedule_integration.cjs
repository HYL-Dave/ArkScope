"use strict";

// Real popup and background, with one shared in-memory browser storage boundary.
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const {JSDOM} = require("jsdom");
const root = path.resolve(__dirname, "../../extensions/sa_alpha_picks");
const source = name => fs.readFileSync(path.join(root, name), "utf8");
const options = JSON.parse(process.argv[2]);
const clone = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
const event = () => ({listeners: [], addListener(fn) {this.listeners.push(fn);},
  removeListener(fn) {this.listeners = this.listeners.filter(item => item !== fn);}});
const settle = async () => {for (let i = 0; i < 20; i++) await new Promise(resolve => setImmediate(resolve));};

async function main() {
  const client = {browser: "chrome", client_id: "c".repeat(32)};
  const authority = {status: "ok", owner: client, is_owner: true, generation: 1,
    ledger_id: "a".repeat(32), policy: {hour_limit: 20, day_limit: 100, hour_reserve: 4, day_reserve: 20},
    capability_pauses: {}, paused_reason: null, active: null, financial_gap_seconds: 60};
  if (options.newProfile) authority.policy = null;
  if (options.policy) authority.policy = clone(options.policy);
  const data = {companyCollectorIdentity: client, companyFinancialRefresh: {
    config: {enabled: options.enabled !== false, target_mode: "manual", tickers: ["AMD"],
      statements: ["income_statement"], views: ["annual"], interval_days: 7,
      interval_days_by_view: {annual: 7, quarterly: 7}, financial_gap_seconds: 60},
    records: {"AMD/income_statement/annual": {last_success_at: new Date().toISOString()}}},
    alphaPicksAutoSyncEnabled: true, alphaPicksAutoSyncIntervalMinutes: 30,
    marketNewsAutoSyncEnabled: true, marketNewsAutoSyncIntervalMinutes: "60"};
  const changed = event(), messages = event(), alarms = new Map(), actions = [];
  let releaseActivation;
  const local = {
    get(keys, callback) {
      const result = keys === null ? clone(data) : Object.fromEntries(
        (Array.isArray(keys) ? keys : typeof keys === "string" ? [keys] : Object.keys(keys || {}))
          .map(key => [key, clone(data[key])]));
      if (callback) {queueMicrotask(() => callback(result)); return;}
      return Promise.resolve(result);
    },
    set(values, callback) {
      const changes = {};
      for (const [key, value] of Object.entries(values)) {
        if (JSON.stringify(data[key]) !== JSON.stringify(value)) changes[key] = {oldValue: clone(data[key]), newValue: clone(value)};
        data[key] = clone(value);
      }
      if (Object.keys(changes).length) queueMicrotask(() => changed.listeners.forEach(fn => fn(clone(changes), "local")));
      if (callback) queueMicrotask(callback);
      return Promise.resolve();
    },
    remove(keys, callback) {
      for (const key of Array.isArray(keys) ? keys : [keys]) delete data[key];
      if (callback) queueMicrotask(callback);
      return Promise.resolve();
    },
  };
  const forbidden = async () => {throw new Error("Real navigation / extraction forbidden in integration fixture");};
  const baseRuntime = {id: "schedule-test", getURL: file => "chrome-extension://schedule-test/" + file,
    getManifest: () => ({name: "ArkScope Company Test", version: "1.0.0"}), lastError: null};
  const chrome = {runtime: {...baseRuntime, onMessage: messages, onInstalled: event(), onStartup: event(),
    sendMessage: async () => {},
    sendNativeMessage(host, msg, callback) {
      let response;
      if (msg.action === "sa_acquisition_control") {
        if (msg.operation === "configure" && options.scenario === "failure") response = {status: "error", error_code: "sa_company_collector_busy"};
        else if (msg.operation === "configure") {authority.policy=clone(msg.policy);response=authority;}
        else if (msg.operation === "begin_task") response = {status: "deferred", reason: "capacity_exhausted", retry_after: new Date(Date.now() + 3600000).toISOString()};
        else response = authority;
      } else if (msg.action === "get_reconciliation_queue") response = {status: "ok", events: [], total: 0};
      else if (msg.action === "record_extension_job") response = {status: "ok", persisted: true, run_id: 1};
      else response = {status: "error", error_code: "isolated_fixture_action_disabled"};
      if (options.scenario === "stop" && msg.operation === "configure") {releaseActivation = () => callback(clone(response)); return;}
      queueMicrotask(() => callback(clone(response)));
    }}, storage: {local, onChanged: changed},
    alarms: {onAlarm: event(), clear: async name => alarms.delete(name), create: async (name, value) => alarms.set(name, clone(value)),
      getAll(callback) {const result = Array.from(alarms, ([name, value]) => ({name, ...value}));
        if (callback) queueMicrotask(() => callback(result)); return Promise.resolve(result);}},
    action: {setBadgeText: async () => {}, setBadgeBackgroundColor: async () => {}, setTitle: async () => {}},
    tabs: {onUpdated: event(), onRemoved: event(), query: async () => [], get: forbidden, create: forbidden,
      update: forbidden, reload: forbidden, remove: forbidden}, scripting: {executeScript: forbidden}};
  const background = vm.createContext({chrome, console: {info() {}, log() {}, warn() {}, error() {}},
    URL, TextEncoder, crypto: require("node:crypto").webcrypto, setTimeout: () => 1, clearTimeout() {},
    navigator: {userAgent: "Isolated test"}, structuredClone});
  background.importScripts = (...names) => names.forEach(name => vm.runInContext(source(name), background, {filename: name}));
  vm.runInContext(source("background.js"), background, {filename: "background.js"});
  const dom = new JSDOM(source("popup.html"), {url: baseRuntime.getURL("popup.html"), runScripts: "outside-only"});
  const win = dom.window, doc = win.document, $ = id => doc.getElementById(id);
  win.chrome = {runtime: {...baseRuntime, onMessage: event(), sendMessage(msg, callback) {
    actions.push(clone(msg));
    for (const listener of messages.listeners) {
      if (listener(clone(msg), {id: baseRuntime.id, url: baseRuntime.getURL("popup.html")}, value => callback(clone(value))) === true) return;
    }
    throw new Error("Unhandled popup action: " + msg.action);
  }}, storage: {local, onChanged: changed}};
  win.setInterval = () => 1;
  win.clearInterval = () => {};
  for (const script of doc.querySelectorAll("script[src]")) vm.runInContext(source(script.src.split("/").pop()), dom.getInternalVMContext());
  await settle();
  const snapshot = () => ({data: clone(data), alarms: Array.from(alarms.keys()),
    companyEnabled: $("companyRefreshEnabled").checked, alphaEnabled: $("alphaPicksAutoSyncToggle").checked,
    newsEnabled: $("marketNewsAutoSyncToggle").checked, alphaInterval: $("alphaPicksAutoSyncInterval").value,
    newsInterval: $("marketNewsAutoSyncInterval").value, summary: $("companyRoutineIntent").textContent,
    status: $("companyRefreshStatus").textContent, policyLimit: doc.querySelector('[name="hour_limit"]').value,
    budgetEnabled: $("companyBudgetEnabled")?.checked ?? null,
    budgetInputsDisabled: [...doc.querySelectorAll('.company-budget input')].every(input=>input.disabled)});
  const before = snapshot();
  actions.length = 0;
  if (options.budgetDraft && $("companyBudgetEnabled")) {
    $("companyBudgetEnabled").checked = true;
    $("companyBudgetEnabled").dispatchEvent(new win.Event("input", {bubbles: true}));
  }
  if (["activate", "failure", "stop"].includes(options.scenario)) {
    if (typeof options.budgetEnabled === 'boolean' && $("companyBudgetEnabled")) {
      $("companyBudgetEnabled").checked = options.budgetEnabled;
      $("companyBudgetEnabled").dispatchEvent(new win.Event("input", {bubbles: true}));
    }
    $("companyActivationConfirmed").click();
    $("companyCollectorSelect").click();
    await settle();
    if (options.scenario === "stop") {
      assert.equal(typeof releaseActivation, "function", "Activation must reach the held native reply");
      const toggle = $(options.job === "marketNews" ? "marketNewsAutoSyncToggle" : "alphaPicksAutoSyncToggle");
      assert.equal(toggle.disabled, false);
      toggle.checked = false;
      toggle.dispatchEvent(new win.Event("change", {bubbles: true}));
      await settle();
      assert.equal(data[options.job + "AutoSyncEnabled"], false);
      releaseActivation();
      await settle();
    }
  } else if (options.scenario === "storage") {
    await local.set({alphaPicksAutoSyncEnabled: false, marketNewsAutoSyncEnabled: false,
      alphaPicksAutoSyncIntervalMinutes: 60, marketNewsAutoSyncIntervalMinutes: "15"});
    await settle();
  } else {
    if (options.consent) $(options.consent).click();
    if (options.edit) {
      const input = options.edit === "policy" ? doc.querySelector('[name="hour_limit"]') : $("companyRefreshDays");
      input.value = options.edit === "policy" ? "12" : "10";
      input.dispatchEvent(new win.Event("input", {bubbles: true}));
    }
    await settle();
    $(options.scenario === "force" ? "companyRefreshForce" : "companyRefreshNow").click();
    await settle();
  }
  const result = {before, after: snapshot(), actions};
  dom.window.close();
  process.stdout.write(JSON.stringify(result));
}
main().catch(error => {console.error(error); process.exitCode = 1;});
