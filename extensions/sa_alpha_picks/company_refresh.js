// Browser-local intent; native admission coordinates collectors. No publication-date inference.
(function (root) {
  "use strict";
  var KEY = "companyFinancialRefresh";
  var ALARM = "company-financial-refresh";
  var DAY = 86400000;
  var STATEMENTS = ["income_statement", "balance_sheet", "cash_flow_statement"];
  var VIEWS = ["annual", "quarterly"];

  function providerSymbol(ticker) {
    return ticker === "BRK B" || ticker === "BRK-B" ? "BRK.B" : ticker;
  }

  function defaults(value) {
    return Object.assign({},value,{interval_days_by_view:value.interval_days_by_view || {
      annual:value.interval_days || 7,quarterly:value.interval_days || 7},
      financial_gap_seconds:value.financial_gap_seconds === undefined ? 60 : value.financial_gap_seconds});
  }

  function normalize(value) {
    function fail() { throw new Error("sa_company_schedule_invalid"); }
    if (!value || typeof value.enabled !== "boolean") fail();
    if (value.interval_days !== undefined && (!Number.isSafeInteger(value.interval_days) || value.interval_days<1 || value.interval_days>365)) fail();
    if (value.interval_days_by_view !== undefined && (!value.interval_days_by_view || typeof value.interval_days_by_view !== "object")) fail();
    value = defaults(value);
    if (VIEWS.some(function (view) {var days=value.interval_days_by_view[view];return !Number.isSafeInteger(days) || days<1 || days>365;})
        || typeof value.financial_gap_seconds !== "number" || !Number.isFinite(value.financial_gap_seconds)
        || value.financial_gap_seconds <= 0 || value.financial_gap_seconds > 2147483) fail();
    function list(items, allowed) {
      if (!Array.isArray(items) || !items.length || items.some(function (item) {
        return typeof item !== "string" || !allowed(item);
      })) fail();
      return Array.from(new Set(items));
    }
    var targetMode = value.target_mode || "manual";
    if (!["manual", "watchlist"].includes(targetMode)) fail();
    var tickers = targetMode === "watchlist" ? [] : list(value.tickers, function (item) {
      return /^[A-Z][A-Z0-9.-]{0,19}$/.test(providerSymbol(item));
    });
    tickers = Array.from(new Set(tickers.map(providerSymbol)));
    return { enabled: value.enabled, target_mode: targetMode, interval_days: value.interval_days || 7,
      interval_days_by_view:{annual:value.interval_days_by_view.annual,quarterly:value.interval_days_by_view.quarterly},
      financial_gap_seconds:value.financial_gap_seconds,tickers: tickers,
      statements: list(value.statements, function (item) { return STATEMENTS.includes(item); }),
      views: list(value.views, function (item) { return VIEWS.includes(item); }) };
  }
  function scopes(config) {
    var seen = new Set();
    // Keep legacy local record/queue keys; requests are normalized at admission.
    return config.tickers.filter(function (ticker) {
      var symbol = providerSymbol(ticker);
      if (seen.has(symbol)) return false;
      seen.add(symbol);
      return true;
    }).flatMap(function (ticker) {
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
    var timer = null, timerRevision = 0, cancellationEpoch = 0;
    function empty() {
      return {config: {enabled:false, target_mode:"manual", tickers:[], statements:["income_statement"], views:["annual"], interval_days:7},
        records:{}, paused_reason:null, rate_limit_until:null, rate_limit_failures:0};
    }
    async function read() {
      await writes;
      var state = (await deps.storage.get(KEY))[KEY] || empty();
      state.config = defaults(state.config);
      return state;
    }
    function mutate(fn) {
      var work = writes.then(async function () {
        var state = (await deps.storage.get(KEY))[KEY] || empty();
        state.config = defaults(state.config);
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
      if (!collector || (collector.status !== "ok" && !(collector.status === "error" && typeof collector.error_code === "string"))) {
        collector = {status:"error",error_code:"sa_company_collector_unavailable"};
      }
      return collector;
    }
    function blocked(control) {
      return control && (control.status !== "ok" || !control.is_owner || control.rate_limited || control.paused_reason
        || control.capability_pauses && control.capability_pauses.financials || control.active);
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
          var due = Math.max(deadline(record, state.config.interval_days_by_view[scope.view]), rateLimitDeadline(state));
          return Object.assign({}, scope, {last_success_at:null, last_attempt_at:null, last_error:null}, record,
            {next_due_at:due ? new Date(due).toISOString() : null, due:due <= now()});
        })};
    }
    async function preview(value) {
      var state = await read();
      var config = value ? normalize(value) : state.config;
      var resolved = await targets(Object.assign({},state,{config:config}));
      var control = await readCollector();
      var counts = {missing:0,due:0,reusable:0,blocked:0}, samples=[];
      var rows = resolved.scopes.map(function (scope) {
        var record = state.records[key(scope)] || {};
        var due = deadline(record,config.interval_days_by_view[scope.view]);
        var kind = Date.parse(record.retry_after || "") > now() ? "blocked"
          : !record.last_success_at ? "missing" : due <= now() ? "due" : "reusable";
        counts[kind]++;
        if (Number.isFinite(record.duration_ms) && record.duration_ms>=0) samples.push(record.duration_ms);
        return Object.assign({},scope,{state:kind,last_success_at:record.last_success_at || null,next_due_at:due ? new Date(due).toISOString() : null});
      });
      var remaining = counts.missing + counts.due;
      return {status:resolved.info && resolved.info.status !== "ok" ? "error" : "ok",config:config,
        target_info:resolved.info,scopes:rows,counts:counts,total_scopes:rows.length,first_fill:counts.missing>0,
        pacing_lower_bound_seconds:Math.max(0,remaining-1)*config.financial_gap_seconds,
        active_delay_seconds:Math.max(0,((control && Date.parse(control.next_financial_at)) || now())-now())/1000,
        observed_duration:{sample_count:samples.length,total_scopes:rows.length,
          mean_ms:samples.length ? samples.reduce(function(a,b){return a+b;},0)/samples.length : null},
        collector:control,blocked_reason:control && (control.error_code || control.paused_reason
          || control.capability_pauses && control.capability_pauses.financials || (!control.is_owner ? "collector_other_installation" : null)) || state.paused_reason || state.blocked_reason || null};
    }
    async function syncAlarm() {
      var revision = ++timerRevision;
      if (timer !== null && deps.clearTimer) deps.clearTimer(timer);
      timer = null;
      var state = await read();
      await deps.alarms.clear(ALARM);
      if (deps.shouldPause && await deps.shouldPause()) return;
      if ((!state.config.enabled && !(state.pending_scopes || []).length) || state.paused_reason) return;
      var control = await readCollector();
      if (control && (control.paused_reason || control.capability_pauses && control.capability_pauses.financials)) return;
      async function schedule(at) {
        if (revision !== timerRevision) return;
        await mutate(function (current) {current.next_wake_at=at;});
        if (revision !== timerRevision) return;
        await deps.alarms.create(ALARM,{when:at,periodInMinutes:60});
        var delay = Math.max(0,at-now());
        if (deps.setTimer && delay<=60000) timer=deps.setTimer(async function () {
          if (revision !== timerRevision) return;
          timer=null;
          await run({scheduled:true});
        },delay);
      }
      // Repair/retry local connectivity even when the complete App list is unavailable.
      if (blocked(control)) {
        await schedule(Math.max(now() + (control.active ? 30000 : 3600000),Date.parse(control.rate_limit_until || "") || 0));
        return;
      }
      var resolved = await targets(state);
      if (resolved.info && resolved.info.status !== "ok") {
        await schedule(now()+3600000);
        return;
      }
      var queuedIds = new Set(state.pending_scopes || []);
      var times = resolved.scopes.filter(function (scope) {
        return state.config.enabled || queuedIds.has(key(scope));
      }).map(function (scope) {
        var record = state.records[key(scope)] || {};
        var due = queuedIds.has(key(scope)) ? Date.parse(record.retry_after || "") || 0
          : deadline(record, state.config.interval_days_by_view[scope.view]);
        return Math.max(due, rateLimitDeadline(state));
      });
      if (!times.length) times.push(now() + 3600000);
      await schedule(Math.max(now()+1000,Math.min.apply(null,times),
        control && Date.parse(control.next_financial_at || "") || 0,Date.parse(state.deferred_until || "") || 0));
    }
    async function configure(value) {
      var config = normalize(value);
      await mutate(function (state) {
        if (JSON.stringify(state.config) !== JSON.stringify(config)) {
          cancellationEpoch++;
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
      cancellationEpoch++;
      await mutate(function (state) {
        state.intent_revision = (state.intent_revision || 0) + 1;
        state.pending_scopes = [];
        state.pending_requested_at = null;
        state.pending_force = false;
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
        var previous = state.records[key(scope)] || {};
        state.records[key(scope)] = {last_success_at:receipt.last_success_at || new Date(now()).toISOString(), last_attempt_at:new Date(now()).toISOString(),
          duration_ms:receipt.acquisition ? receipt.acquisition.acquisition_duration_ms : previous.duration_ms,
          last_error:null, failures:0, retry_after:null, observation_id:receipt.observation_id};
      });
      return updated;
    }
    async function perform(request, startedEpoch) {
      var force = request.force === true, manual = request.scheduled !== true;
      var control = await readCollector();
      if (blocked(control && Object.assign({},control,{active:null}))) return status();
      if (deps.shouldPause && await deps.shouldPause()) return status();
      // Refresh overrides source-age policy, never the financial-batch cooldown.
      if (rateLimitDeadline(await read()) > now()) return status();
      var state = await read();
      var intentRevision = state.intent_revision || 0;
      var resolved = await targets(state);
      if (resolved.info && resolved.info.status !== "ok") return status();
      if (((await read()).intent_revision || 0) !== intentRevision || startedEpoch !== cancellationEpoch) return status();
      if (manual || (state.pending_scopes || []).length) {
        var ids = new Set(resolved.scopes.map(key));
        var configRevision = state.intent_revision || 0;
        await mutate(function (current) {
          if ((current.intent_revision || 0) !== configRevision || startedEpoch !== cancellationEpoch) return;
          current.pending_scopes = (current.pending_scopes || []).filter(function (id) { return ids.has(id); });
          if (manual && !current.pending_scopes.length) {
            current.pending_scopes = resolved.scopes.filter(function(scope) {
              return force || deadline(current.records[key(scope)] || {},current.config.interval_days_by_view[scope.view])<=now();
            }).map(key);
            current.pending_requested_at = new Date(now()).toISOString();
            current.pending_force = force;
          }
        });
        state = await read();
        if ((state.intent_revision || 0) !== intentRevision || startedEpoch !== cancellationEpoch) return status();
      }
      var queued = (state.pending_scopes || []).length > 0;
      // Persist manual intent before transient capacity/pacing waits, including after a browser switch.
      if (control && (control.active || Date.parse(control.next_financial_at || "") > now())) return status();
      if ((!manual && !queued && !state.config.enabled) || state.paused_reason) return status();
      force = queued ? state.pending_force === true : force;
      var selected = resolved.scopes.filter(function (scope) {
        if (Date.parse((state.records[key(scope)] || {}).retry_after || "") > now()) return false;
        if (queued) return state.pending_scopes.includes(key(scope));
        return force || deadline(state.records[key(scope)] || {}, state.config.interval_days_by_view[scope.view]) <= now();
      });
      // One overdue scope per alarm. Missed browser sessions never produce a catch-up burst.
      if (!request.legacy_force) selected = selected.slice(0,1);
      else if (state.config.target_mode === "watchlist") selected = selected.slice(0,1);
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
              && (!latestSuccess || Date.parse(latestSuccess) + latest.config.interval_days_by_view[scope.view] * DAY <= now())));
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
        try { result = await deps.runScope(scope, manual || queued ? "manual" : "scheduled", admitted, observeFailure,
          state.config.interval_days_by_view[scope.view], queued ? state.pending_requested_at : null,force); }
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
              current.deferred_until = new Date(Math.max(now() + 1000,
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
    function run(request) {
      if (pending) return pending;
      // Boolean calls are internal legacy callers; popup commands use explicit intent.
      request = typeof request === "boolean" ? {force:request,scheduled:!request,legacy_force:request} : request || {force:false};
      pending = perform(request,cancellationEpoch).then(async function () {
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
    async function resume() { await mutate(function(state){state.paused_reason=null;});return status(); }
    return {configure:configure, status:status, preview:preview, run:run, syncAlarm:syncAlarm, noteSuccess:noteSuccess, cancelQueue:cancelQueue,resume:resume};
  }
  root.SACompanyRefresh = {create:create, alarm:ALARM,normalize:normalize,providerSymbol:providerSymbol};
})(globalThis);
