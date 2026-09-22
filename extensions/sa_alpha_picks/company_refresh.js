// Browser-local refresh state. Publication dates and provider readiness are not inferred.
(function (root) {
  "use strict";
  var KEY = "companyFinancialRefresh";
  var ALARM = "company-financial-refresh";
  var DAY = 86400000;
  var STATEMENTS = ["income_statement", "balance_sheet", "cash_flow_statement"];
  var VIEWS = ["annual", "quarterly"];

  function normalize(value) {
    function fail() { throw new Error("sa_company_schedule_invalid"); }
    if (!value || typeof value.enabled !== "boolean" || !Number.isSafeInteger(value.interval_days)
        || value.interval_days < 1 || value.interval_days > 365) fail();
    function list(items, allowed) {
      if (!Array.isArray(items) || !items.length || items.some(function (item) {
        return typeof item !== "string" || !allowed(item);
      })) fail();
      return Array.from(new Set(items));
    }
    var tickers = list(value.tickers, function (item) { return /^[A-Z][A-Z0-9.-]{0,19}$/.test(item); });
    return { enabled: value.enabled, interval_days: value.interval_days, tickers: tickers,
      statements: list(value.statements, function (item) { return STATEMENTS.includes(item); }),
      views: list(value.views, function (item) { return VIEWS.includes(item); }) };
  }
  function scopes(config) {
    return config.tickers.flatMap(function (ticker) {
      return config.statements.flatMap(function (statement) {
        return config.views.map(function (view) { return {ticker: ticker, statement: statement, view: view}; });
      });
    });
  }
  function key(scope) { return [scope.ticker, scope.statement, scope.view].join("/"); }
  function deadline(record, days) {
    // A failed or interrupted acquisition does not move last_success_at.
    return Math.max(record.retry_after ? Date.parse(record.retry_after) : 0,
      record.last_success_at ? Date.parse(record.last_success_at) + days * DAY : 0);
  }
  function paused(code) {
    return /human_verification|access_restricted|login_required|layout_unrecognized|structure_changed|identity_mismatch|units_unrecognized|value_unrecognized/.test(code);
  }
  function create(deps) {
    var now = deps.now || Date.now;
    var pending = null;
    var writes = Promise.resolve();
    function empty() {
      return {config: {enabled:false, tickers:[], statements:["income_statement"], views:["annual"], interval_days:7},
        records:{}, paused_reason:null};
    }
    async function read() {
      await writes;
      return (await deps.storage.get(KEY))[KEY] || empty();
    }
    function mutate(fn) {
      var work = writes.then(async function () {
        var state = (await deps.storage.get(KEY))[KEY] || empty();
        fn(state);
        await deps.storage.set({[KEY]:state});
      });
      writes = work.catch(function () {});
      return work;
    }
    async function status() {
      var state = await read();
      return {status:"ok", config:state.config, paused_reason:state.paused_reason, running:!!pending,
        scopes:scopes(state.config).map(function (scope) {
          var record = state.records[key(scope)] || {};
          var due = deadline(record, state.config.interval_days);
          return Object.assign({}, scope, {last_success_at:null, last_attempt_at:null, last_error:null}, record,
            {next_due_at:due ? new Date(due).toISOString() : null, due:due <= now()});
        })};
    }
    async function syncAlarm() {
      var state = await read();
      await deps.alarms.clear(ALARM);
      if (!state.config.enabled || state.paused_reason || !state.config.tickers.length) return;
      var times = scopes(state.config).map(function (scope) {
        return deadline(state.records[key(scope)] || {}, state.config.interval_days);
      });
      await deps.alarms.create(ALARM, {when:Math.max(now() + 60000, Math.min.apply(null, times)), periodInMinutes:60});
    }
    async function configure(value) {
      var config = normalize(value);
      await mutate(function (state) { state.config = config; });
      await syncAlarm();
      return status();
    }
    async function noteSuccess(scope, receipt) {
      if (!scope || !STATEMENTS.includes(scope.statement) || !VIEWS.includes(scope.view) || receipt.currency !== "USD") return;
      if (!scopes((await read()).config).some(function (item) { return key(item) === key(scope); })) return false;
      var updated = false;
      await mutate(function (state) {
        if (!scopes(state.config).some(function (item) { return key(item) === key(scope); })) return;
        updated = true;
        state.records[key(scope)] = {last_success_at:new Date(now()).toISOString(), last_attempt_at:new Date(now()).toISOString(),
          last_error:null, failures:0, retry_after:null, observation_id:receipt.observation_id};
      });
      return updated;
    }
    async function perform(force) {
      if (force) await mutate(function (state) { state.paused_reason = null; });
      var state = await read();
      if ((!force && !state.config.enabled) || state.paused_reason) return status();
      var targets = scopes(state.config).filter(function (scope) {
        return force || deadline(state.records[key(scope)] || {}, state.config.interval_days) <= now();
      });
      // One overdue scope per alarm. Missed browser sessions never produce a catch-up burst.
      if (!force) targets = targets.slice(0, 1);
      for (var scope of targets) {
        var beforeQueue = (await read()).records[key(scope)] || {};
        var successBeforeQueue = beforeQueue.last_success_at;
        var attemptAt = new Date(now()).toISOString();
        var admitted = async function () {
          var latest = await read();
          var latestSuccess = (latest.records[key(scope)] || {}).last_success_at;
          return !latest.paused_reason && (force || latest.config.enabled)
            && scopes(latest.config).some(function (item) { return key(item) === key(scope); })
            && (force || (latestSuccess === successBeforeQueue
              && (!latestSuccess || Date.parse(latestSuccess) + latest.config.interval_days * DAY <= now())));
        };
        if (!await admitted()) break;
        await mutate(function (current) {
          var record = current.records[key(scope)] || {};
          current.records[key(scope)] = Object.assign({}, record, {
            last_attempt_at:attemptAt, last_error:"sa_company_refresh_interrupted",
            retry_after:new Date(now() + 6 * 3600000).toISOString()});
        });
        var result;
        try { result = await deps.runScope(scope, force ? "manual" : "scheduled", admitted); }
        catch (_) { result = {status:"error", error_code:"sa_company_refresh_failed"}; }
        if (result.status === "cancelled") {
          await mutate(function (current) {
            var record = current.records[key(scope)] || {};
            if (record.last_attempt_at === attemptAt && record.last_error === "sa_company_refresh_interrupted") {
              current.records[key(scope)] = beforeQueue;
            }
          });
          break;
        }
        if (result.status === "ok") {
          await noteSuccess(scope, result);
        } else {
          await mutate(function (current) {
            var record = current.records[key(scope)] || {};
            var failures = Math.min((record.failures || 0) + 1, 6);
            var code = /^sa_company_[a-z_]+$|^data_source_[a-z_]+$/.test(result.error_code || "")
              ? result.error_code : "sa_company_refresh_failed";
            current.records[key(scope)] = Object.assign({}, record, {failures:failures, last_error:code,
              retry_after:new Date(now() + Math.min(6 * 3600000 * Math.pow(2, failures - 1), 7 * DAY)).toISOString()});
            if (paused(code)) current.paused_reason = code;
          });
        }
      }
      return status();
    }
    function run(force) {
      if (pending) return pending;
      pending = perform(force === true).then(async function () {
        pending = null;
        await mutate(function (state) { state.status_revision = (state.status_revision || 0) + 1; });
        await syncAlarm();
        return status();
      }, async function (error) {
        pending = null;
        await mutate(function (state) { state.status_revision = (state.status_revision || 0) + 1; });
        await syncAlarm();
        throw error;
      });
      return pending;
    }
    return {configure:configure, status:status, run:run, syncAlarm:syncAlarm, noteSuccess:noteSuccess};
  }
  root.SACompanyRefresh = {create:create, alarm:ALARM};
})(globalThis);
