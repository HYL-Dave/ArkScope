(function (root) {
  "use strict";

  function Stop(detail) {
    this.name = "SAAcquisitionStop";
    this.message = detail.error_code || detail.reason || "collector_unavailable";
    this.detail = detail;
  }
  Stop.prototype = Object.create(Error.prototype);

  function capability(operation) {
    return operation === "company_financial_capture" ? "financials"
      : operation.indexOf("alpha_picks") === 0 ? "alpha_picks" : "news";
  }

  function deferred(reply) {
    reply = reply || {};
    var reason = reply.reason || (/other_browser/.test(reply.error_code || "")
      ? "collector_other_installation" : "collector_unavailable");
    return Object.assign({}, reply, {status:"deferred",reason:reason});
  }

  function create(options) {
    var storage = options.storage, control = options.control;
    var now = options.now || Date.now, uuid = options.uuid || function () {return crypto.randomUUID();};

    async function runTask(descriptor, handler) {
      var pending, state, permit;
      try {
        if ((await storage.get("saAcquisitionPending")).saAcquisitionPending) return deferred();
        var ledger = (await storage.get("saAcquisitionLedger")).saAcquisitionLedger;
        state = await control("status", ledger ? {ledger_id:ledger} : {});
        if (options.onStatus) await options.onStatus(state);
        if (!state || state.status !== "ok" || !state.policy) return deferred(state);
        if (!state.is_owner) return deferred({reason:"collector_other_installation"});
        var restricted = state.paused_reason || state.capability_pauses && state.capability_pauses[capability(descriptor.operation)];
        if (restricted || state.rate_limited) return deferred({reason:"site_paused",error_code:restricted || "rate_limited",retry_after:state.rate_limit_until});
        pending = {request_id:uuid(),ledger_id:state.ledger_id,generation:state.generation,navigation:null};
        await storage.set({saAcquisitionPending:pending,saAcquisitionLedger:state.ledger_id});
        var beginRequest = Object.assign({}, descriptor, {
          task_operation:descriptor.operation,request_id:pending.request_id,
          generation:state.generation,protocol_version:2,intent_revision:descriptor.intent_revision || 0,
          trigger:descriptor.trigger || "manual",build:descriptor.build || "unknown",
        });
        delete beginRequest.operation;
        permit = await control("begin_task", beginRequest);
        if (!permit || permit.status === "uncertain" || permit.replayed) return deferred(permit);
        if (permit.status !== "ok") {
          await storage.set({saAcquisitionPending:null});
          if (permit.status === "reused") {
            var capturedAt = Date.parse(permit.last_success_at || "");
            var scope = descriptor.scope || {};
            if (!/^[a-f0-9]{64}$/.test(permit.observation_id || "") || permit.currency !== "USD"
                || permit.ticker !== scope.ticker || permit.statement !== scope.statement || permit.view !== scope.view
                || !Number.isFinite(capturedAt) || capturedAt <= 0 || capturedAt > now()) {
              return {status:"error",error_code:"sa_company_receipt_unverified"};
            }
            return Object.assign({},permit,{status:"ok",acquisition_outcome:"reused"});
          }
          return deferred(permit);
        }
        if (!/^[a-f0-9]{32}$/.test(permit.token || "") || !/^[a-f0-9]{32}$/.test(permit.task_id || "") || permit.generation !== state.generation) return deferred();
      } catch (_) { return deferred(); }

      var uncertain = false, stopped = null, navigationInFlight = false, terminal = false;
      var ownedTabs = new Set();
      var auth = {token:permit.token,generation:permit.generation};
      function stop(detail, unknown) {
        stopped = stopped || detail;
        uncertain = uncertain || unknown === true;
        throw new Stop(stopped);
      }
      var task = {
        operation:descriptor.operation,
        get stop() {return stopped;},
        get uncertain() {return uncertain;},
        ownedTabs:ownedTabs,
        navigate: async function (request, perform) {
          if (stopped) throw new Stop(stopped);
          if (terminal || navigationInFlight) return stop(deferred(), true);
          navigationInFlight = true;
          var authorized = false;
          try {
            pending.navigation = {id:request.id || uuid(),kind:request.kind,destination_class:request.destinationClass};
            await storage.set({saAcquisitionPending:pending});
            var reply = await control("admit_navigation", Object.assign({},auth,{navigation_id:pending.navigation.id,
              kind:request.kind,destination_class:request.destinationClass}));
            if (!reply || reply.replayed || reply.status === "error") return stop(deferred(reply), true);
            if (reply.status === "deferred") return stop(deferred(reply));
            if (reply.allowed !== true || reply.replayed !== false || !/^[a-f0-9]{32}$/.test(reply.attempt_id || "")) return stop(deferred(), true);
            authorized = true;
            var value = await perform();
            if (request.kind === "create" && value && Number.isInteger(value.id)) ownedTabs.add(value.id);
            pending.navigation = null;
            await storage.set({saAcquisitionPending:pending});
            return value;
          } catch (error) {
            if (error && error.name === "SAAcquisitionStop") throw error;
            // A rejected browser call can still have created/navigated a tab.
            return stop(deferred({error_code:authorized ? "sa_acquisition_navigation_uncertain" : "native_host_unavailable"}), true);
          } finally { navigationInFlight = false; }
        },
        observeRestriction: async function (reason, retryAt) {
          if (["login_required","human_verification_required","rate_limited","access_restricted"].indexOf(reason) === -1) return;
          stopped = {status:"error",reason:"site_paused",error_code:reason};
          try {
            await storage.set({saAcquisitionRestriction:{reason:reason,capability:capability(descriptor.operation),observed_at:new Date(now()).toISOString()}});
            var reply = await control("observe_restriction", Object.assign({},auth,{reason:reason,retry_after:retryAt || null}));
            if (!reply || reply.status !== "ok") return stop(stopped, true);
            if (options.onStatus) await options.onStatus(reply);
            return reply;
          } catch (_) { return stop(stopped, true); }
        },
        finish: async function (result, cleanupConfirmed) {
          if (uncertain || navigationInFlight || !cleanupConfirmed || terminal) return deferred({error_code:"sa_acquisition_cleanup_unconfirmed"});
          terminal = true;
          try {
            var status = result.extension_run ? result.extension_run.derived_outcome : result.status;
            var projection = {status:status === "complete" || status === "ok" ? "ok"
              : status === "deferred" ? "deferred" : status === "skipped" || status === "cancelled" ? "cancelled" : "error"};
            if (result.observation_id) projection.observation_id = result.observation_id;
            if (result.error_code) projection.error_code = result.error_code;
            var reply = await control("finish_task", Object.assign({},auth,{result:projection,cleanup_confirmed:true}));
            if (!reply || reply.status !== "ok" || !reply.acquisition) return deferred();
            await storage.set({saAcquisitionPending:null});
            return reply;
          } catch (_) { return deferred(); }
        },
      };
      var result;
      try { result = await handler(task) || {}; }
      catch (error) { result = error && error.name === "SAAcquisitionStop" ? Object.assign({},error.detail) : {status:"error",error_code:"sa_acquisition_failed"}; }
      if (stopped) result = Object.assign({},result,{acquisition_stop:stopped});
      var finish = await task.finish(result, ownedTabs.size === 0);
      if (finish.acquisition) result.acquisition = finish.acquisition;
      else result.acquisition_uncertain = true;
      return result;
    }

    return {runTask:runTask};
  }

  root.SAAcquisition = Object.freeze({create:create,Stop:Stop,capability:capability});
}(globalThis));
