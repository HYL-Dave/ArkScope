// Browser-local intent; native admission coordinates collectors. No publication-date inference.
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
    var targetMode = value.target_mode || "manual";
    if (!["manual", "watchlist"].includes(targetMode)) fail();
    var tickers = targetMode === "watchlist" ? [] : list(value.tickers, function (item) { return /^[A-Z][A-Z0-9.-]{0,19}$/.test(item); });
    return { enabled: value.enabled, target_mode: targetMode, interval_days: value.interval_days, tickers: tickers,
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
  function rateLimitDeadline(state) {
    return state.rate_limit_until ? Date.parse(state.rate_limit_until) : 0;
  }
  function retryDelay(failures) {
    return Math.min(6 * 3600000 * Math.pow(2, failures - 1), 7 * DAY);
  }
  function paused(code) {
    return /human_verification|access_restricted|login_required|layout_unrecognized|structure_changed|identity_mismatch|units_unrecognized|value_unrecognized/.test(code);
  }
  function create(deps) {
    var now = deps.now || Date.now;
    var pending = null;
    var writes = Promise.resolve();
    var collector = null;
    function empty() {
      return {config: {enabled:false, target_mode:"manual", tickers:[], statements:["income_statement"], views:["annual"], interval_days:7},
        records:{}, paused_reason:null, rate_limit_until:null, rate_limit_failures:0};
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
    async function targets(state) {
      if (state.config.target_mode !== "watchlist") return {scopes:scopes(state.config), info:null};
      var info;
      try { info = await deps.resolveWatchlist(); }
      catch (_) { info = {status:"error",error_code:"sa_company_watchlist_unavailable"}; }
      if (!info || info.status !== "ok" || !Array.isArray(info.tickers)
          || info.tickers.some(function (ticker) { return typeof ticker !== "string" || !/^[A-Z][A-Z0-9.-]{0,19}$/.test(ticker); })) {
        return {scopes:[],info:info && info.status === "error" ? info : {status:"error",error_code:"sa_company_watchlist_unavailable"}};
      }
      return {scopes:scopes(Object.assign({}, state.config, {tickers:Array.from(new Set(info.tickers))})), info:info};
    }
    async function readCollector() {
      if (!deps.control) return null;
      try { collector = await deps.control("status"); }
      catch (_) { collector = null; }
      if (!collector || collector.status !== "ok") collector = {status:"error",error_code:"sa_company_collector_unavailable"};
      return collector;
    }
    function blocked(control) {
      return control && (control.status !== "ok" || !control.is_owner || control.rate_limited || control.paused_reason || control.active);
    }
    async function status() {
      var state = await read();
      var resolved = await targets(state);
      var control = await readCollector();
      var ids = new Set(resolved.scopes.map(key));
      var queue = resolved.info && resolved.info.status !== "ok" ? (state.pending_scopes || [])
        : (state.pending_scopes || []).filter(function (id) { return ids.has(id); });
      return {status:"ok", config:state.config, paused_reason:state.paused_reason, running:!!pending,
        collector:control, target_info:resolved.info, pending_count:queue.length,
        blocked_reason:state.blocked_reason || null, deferred_until:state.deferred_until || null,
        rate_limited:rateLimitDeadline(state) > now(), rate_limit_until:state.rate_limit_until || null,
        scopes:resolved.scopes.map(function (scope) {
          var record = state.records[key(scope)] || {};
          var due = Math.max(deadline(record, state.config.interval_days), rateLimitDeadline(state));
          return Object.assign({}, scope, {last_success_at:null, last_attempt_at:null, last_error:null}, record,
            {next_due_at:due ? new Date(due).toISOString() : null, due:due <= now()});
        })};
    }
    async function syncAlarm() {
      var state = await read();
      await deps.alarms.clear(ALARM);
      if ((!state.config.enabled && !(state.pending_scopes || []).length) || state.paused_reason) return;
      // Repair/retry local connectivity even when the complete App list is unavailable.
      if (blocked(collector)) {
        await deps.alarms.create(ALARM, {when:Math.max(now() + 3600000, Date.parse(collector.rate_limit_until || "") || 0), periodInMinutes:60});
        return;
      }
      var resolved = await targets(state);
      if (resolved.info && resolved.info.status !== "ok") {
        await deps.alarms.create(ALARM, {when:now() + 3600000, periodInMinutes:60});
        return;
      }
      var times = resolved.scopes.map(function (scope) {
        return Math.max(deadline(state.records[key(scope)] || {}, state.config.interval_days), rateLimitDeadline(state));
      });
      if ((state.pending_scopes || []).length) times.push(rateLimitDeadline(state));
      if (!times.length) times.push(now() + 3600000);
      await deps.alarms.create(ALARM, {when:Math.max(now() + 60000, Math.min.apply(null, times),
        Date.parse(state.deferred_until || "") || 0), periodInMinutes:60});
    }
    async function configure(value) {
      var config = normalize(value);
      await mutate(function (state) {
        if (JSON.stringify(state.config) !== JSON.stringify(config)) {
          state.intent_revision = (state.intent_revision || 0) + 1;
          state.pending_scopes = [];
          state.pending_requested_at = null;
          state.deferred_until = null;
          state.blocked_reason = null;
        }
        state.config = config;
      });
      await syncAlarm();
      return status();
    }
    async function cancelQueue() {
      await mutate(function (state) {
        state.intent_revision = (state.intent_revision || 0) + 1;
        state.pending_scopes = [];
        state.pending_requested_at = null;
        state.deferred_until = null;
        state.blocked_reason = null;
      });
      await syncAlarm();
      return status();
    }
    async function noteSuccess(scope, receipt) {
      if (!scope || !STATEMENTS.includes(scope.statement) || !VIEWS.includes(scope.view) || receipt.currency !== "USD") return;
      var current = await read();
      var resolved = await targets(current);
      if (!resolved.scopes.some(function (item) { return key(item) === key(scope); })) return false;
      var updated = false;
      await mutate(function (state) {
        if (JSON.stringify(state.config) !== JSON.stringify(current.config)) return;
        updated = true;
        state.records[key(scope)] = {last_success_at:receipt.last_success_at || new Date(now()).toISOString(), last_attempt_at:new Date(now()).toISOString(),
          last_error:null, failures:0, retry_after:null, observation_id:receipt.observation_id};
      });
      return updated;
    }
    async function perform(force) {
      var control = await readCollector();
      if (force && control && control.status === "ok" && control.is_owner && control.paused_reason && !control.active) {
        await deps.control("resume");
        control = await readCollector();
      }
      if (blocked(control)) return status();
      // Refresh overrides source-age policy, never the financial-batch cooldown.
      if (rateLimitDeadline(await read()) > now()) return status();
      if (force) await mutate(function (state) { state.paused_reason = null; });
      var state = await read();
      var intentRevision = state.intent_revision || 0;
      var resolved = await targets(state);
      if (resolved.info && resolved.info.status !== "ok") return status();
      if (((await read()).intent_revision || 0) !== intentRevision) return status();
      if (force || (state.pending_scopes || []).length) {
        var ids = new Set(resolved.scopes.map(key));
        var configRevision = state.intent_revision || 0;
        await mutate(function (current) {
          if ((current.intent_revision || 0) !== configRevision) return;
          current.pending_scopes = (current.pending_scopes || []).filter(function (id) { return ids.has(id); });
          if (force && !current.pending_scopes.length) {
            current.pending_scopes = resolved.scopes.map(key);
            current.pending_requested_at = new Date(now()).toISOString();
          }
        });
        state = await read();
        if ((state.intent_revision || 0) !== intentRevision) return status();
      }
      var queued = (state.pending_scopes || []).length > 0;
      if ((!force && !queued && !state.config.enabled) || state.paused_reason) return status();
      var selected = resolved.scopes.filter(function (scope) {
        if (queued) return state.pending_scopes.includes(key(scope));
        return force || deadline(state.records[key(scope)] || {}, state.config.interval_days) <= now();
      });
      // One overdue scope per alarm. Missed browser sessions never produce a catch-up burst.
      if (!force || state.config.target_mode === "watchlist") selected = selected.slice(0, 1);
      for (var scope of selected) {
        var beforeQueue = (await read()).records[key(scope)] || {};
        var successBeforeQueue = beforeQueue.last_success_at;
        var attemptAt = new Date(now()).toISOString();
        var admitted = async function () {
          var latest = await read();
          var latestTargets = await targets(latest);
          var latestSuccess = (latest.records[key(scope)] || {}).last_success_at;
          return (latest.intent_revision || 0) === intentRevision && !latest.paused_reason && rateLimitDeadline(latest) <= now()
            && (queued ? (latest.pending_scopes || []).includes(key(scope)) : force || latest.config.enabled)
            && latestTargets.scopes.some(function (item) { return key(item) === key(scope); })
            && (force || queued || (latestSuccess === successBeforeQueue
              && (!latestSuccess || Date.parse(latestSuccess) + latest.config.interval_days * DAY <= now())));
        };
        if (!await admitted()) break;
        await mutate(function (current) {
          var record = current.records[key(scope)] || {};
          current.records[key(scope)] = Object.assign({}, record, {
            last_attempt_at:attemptAt, last_error:"sa_company_refresh_interrupted",
            retry_after:new Date(now() + 6 * 3600000).toISOString()});
        });
        var failureWrite = null;
        var observeFailure = function (errorCode) {
          if (failureWrite) return failureWrite;
          failureWrite = mutate(function (current) {
            var record = current.records[key(scope)] || {};
            var failures = Math.min((record.failures || 0) + 1, 6);
            var code = /^sa_company_[a-z_]+$|^data_source_[a-z_]+$/.test(errorCode || "")
              ? errorCode : "sa_company_refresh_failed";
            current.records[key(scope)] = Object.assign({}, record, {failures:failures, last_error:code,
              retry_after:new Date(now() + retryDelay(failures)).toISOString()});
            if (code === "sa_company_rate_limited") {
              current.rate_limit_failures = Math.min((current.rate_limit_failures || 0) + 1, 6);
              current.rate_limit_until = new Date(now() + retryDelay(current.rate_limit_failures)).toISOString();
            }
            if (paused(code)) current.paused_reason = code;
          });
          return failureWrite;
        };
        var result;
        try { result = await deps.runScope(scope, force || queued ? "manual" : "scheduled", admitted, observeFailure,
          state.config.interval_days, queued ? state.pending_requested_at : null); }
        catch (_) { result = {status:"error", error_code:"sa_company_refresh_failed"}; }
        if (failureWrite) await failureWrite;
        if (result.status === "cancelled" || result.status === "deferred") {
          await mutate(function (current) {
            if ((current.intent_revision || 0) !== intentRevision) return;
            var record = current.records[key(scope)] || {};
            if (record.last_attempt_at === attemptAt && record.last_error === "sa_company_refresh_interrupted") {
              current.records[key(scope)] = beforeQueue;
            }
            if (result.status === "deferred" && result.deferral_kind === "scope") {
              current.records[key(scope)] = Object.assign({}, current.records[key(scope)] || {}, {
                last_error:result.error_code, retry_after:result.retry_after,
              });
            } else if (result.status === "deferred") {
              current.blocked_reason = result.error_code || "sa_company_collector_unavailable";
              current.deferred_until = new Date(Math.max(now() + 60000,
                Date.parse(result.retry_after || "") || now() + 3600000)).toISOString();
            }
          });
          break;
        }
        if (result.status === "ok" && !failureWrite) {
          await noteSuccess(scope, result);
          await mutate(function (current) {
            current.rate_limit_until = null;
            current.rate_limit_failures = 0;
            current.blocked_reason = null;
            current.deferred_until = null;
          });
        } else if (!failureWrite) await observeFailure(result.error_code);
        if (queued) await mutate(function (current) {
          if ((current.intent_revision || 0) !== intentRevision) return;
          if (!current.paused_reason && rateLimitDeadline(current) <= now()) {
            current.pending_scopes = (current.pending_scopes || []).filter(function (id) { return id !== key(scope); });
            if (!current.pending_scopes.length) current.pending_requested_at = null;
          }
        });
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
    return {configure:configure, status:status, run:run, syncAlarm:syncAlarm, noteSuccess:noteSuccess, cancelQueue:cancelQueue};
  }
  root.SACompanyRefresh = {create:create, alarm:ALARM};
})(globalThis);
