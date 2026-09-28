(function (root) {
  "use strict";
  const KEY = "saArticleBodyRecoveryV2", ALARM = "saArticleBodyRecoveryContinuation";
  const TERMINAL = ["complete", "partial", "cancelled"];
  const STATES = ["pending", "running", "waiting", "paused", "cancelling", ...TERMINAL];
  const POLL_MS = 60000;
  function error(code) { return {status:"error", error_code:code}; }
  function jobReply(value) {
    return value && value.status === "ok" && value.protocol_version === 2
      && /^[a-f0-9]{32}$/.test(value.job_id || "") && Number.isSafeInteger(value.revision)
      && value.revision > 0 && STATES.includes(value.state);
  }
  function identity(state) {
    return {client_id:state.owner.client_id, browser:state.owner.browser,
      generation:state.generation, ledger_id:state.ledger_id};
  }
  function sameOwner(left, right) {
    return left && right && ["client_id", "browser", "generation", "ledger_id"].every(k=>left[k] === right[k]);
  }
  function validRef(value) {
    return value && value.schema_version === 2 && value.owner && typeof value.owner.client_id === "string"
      && ["chrome", "firefox"].includes(value.owner.browser) && Number.isSafeInteger(value.owner.generation)
      && typeof value.owner.ledger_id === "string" && typeof value.cancel_requested === "boolean"
      && (value.next_wake === null || Number.isFinite(value.next_wake) && value.next_wake >= 0)
      && (value.job_id === null || /^[a-f0-9]{32}$/.test(value.job_id) && Number.isSafeInteger(value.revision) && value.revision > 0)
      && (value.pending_start === null || value.pending_start && typeof value.pending_start.request_id === "string"
        && /^[a-f0-9]{64}$/.test(value.pending_start.manifest_id));
  }

  function create(deps) {
    const now = deps.now || Date.now, uuid = deps.uuid || (()=>crypto.randomUUID());
    let writing = Promise.resolve(), waking = null, starting = null, active = null;
    async function read() {
      const value = (await deps.storage.get(KEY))[KEY];
      if (value == null) return null;
      if (!validRef(value)) throw error("sa_body_local_state_invalid");
      return value;
    }
    function update(change) {
      const write = writing.then(async()=>{
        const value = await change(await read());
        await deps.storage.set({[KEY]:value});
        return value;
      });
      writing = write.catch(()=>{});
      return write;
    }
    async function owned(ref) {
      const state = await deps.collector();
      if (!state || state.status !== "ok" || !state.is_owner || !state.owner) throw error("sa_body_owner_changed");
      if (ref && !sameOwner(ref.owner,identity(state))) throw error("sa_body_owner_changed");
      return state;
    }
    async function call(operation, ref, fields) {
      const state = await owned(["state", "items", "cancel"].includes(operation) ? null : ref);
      return deps.control(operation, Object.assign({protocol_version:2,expected_generation:state.generation,
        job_id:ref && ref.job_id,revision:ref && ref.revision},fields || {}));
    }
    async function remember(reply) {
      if (!jobReply(reply)) return reply;
      await update(ref=>{
        if (!ref || ref.job_id && ref.job_id !== reply.job_id) throw error("sa_body_local_state_invalid");
        return {...ref,job_id:reply.job_id,revision:reply.revision,pending_start:null};
      });
      return reply;
    }
    async function schedule(reply, delay) {
      const ref = await read();
      if (!ref || !ref.job_id && !ref.pending_start && !ref.cancel_requested) return reply;
      const stopped = !ref.cancel_requested && jobReply(reply) && [...TERMINAL,"paused"].includes(reply.state);
      const deadline = Date.parse(reply && (reply.next_eligible_at || reply.retry_after));
      const when = stopped ? null : Number.isFinite(deadline) && deadline > now() ? deadline : now() + (delay || 1000);
      await update(current=>current && {...current,next_wake:when});
      if (when === null) await deps.alarms.clear(ALARM);
      else await deps.alarms.create(ALARM,{when});
      return reply;
    }
    async function failed(reason) {
      const reply = error(reason && reason.error_code || "native_host_unavailable");
      try { await schedule(reply,POLL_MS); } catch (_) { await deps.alarms.clear(ALARM); }
      return reply;
    }
    async function finishStart(ref) {
      if (!ref.pending_start) return ref;
      const reply = await call("start",ref,{...ref.pending_start,trigger:"manual"});
      if (!jobReply(reply)) {
        // A lost response keeps its idempotency key; a definitive rejection
        // requires a new preview and explicit Start, never an alarm retry.
        if (reply && reply.status === "error"
            && !["native_host_unavailable", "invalid_native_response"].includes(reply.error_code)) {
          await update(current=>({...current,pending_start:null,next_wake:null}));
          await deps.alarms.clear(ALARM);
        }
        throw reply || error("sa_body_upgrade_required");
      }
      await remember(reply);
      return read();
    }
    async function cancelNative(ref) {
      ref = await finishStart(ref);
      if (!ref.job_id) return error("sa_body_job_not_found");
      const state = await call("state",ref);
      if (!jobReply(state)) throw state;
      await remember(state);
      const reply = await call("cancel",await read());
      if (!jobReply(reply)) throw reply;
      await remember(reply);
      await update(current=>({...current,cancel_requested:false}));
      return schedule(reply, POLL_MS);
    }
    async function preview() {
      try {
        const reply = await deps.native({action:"preview_article_body_recovery",protocol_version:2});
        if (reply && reply.status === "error") return reply;
        if (!reply || reply.protocol_version !== 2 || !/^[a-f0-9]{64}$/.test(reply.manifest_id || "")
            || !Array.isArray(reply.targets)) return error("sa_body_upgrade_required");
        return reply;
      } catch (err) { return failed(err); }
    }
    async function doStart(manifestId) {
      if (!/^[a-f0-9]{64}$/.test(manifestId || "")) return error("preview_required");
      try {
        const existing = await read();
        if (existing && (existing.pending_start || existing.cancel_requested)) return error("already_pending");
        const collector = await owned(null);
        const current = await call("state",existing);
        if (jobReply(current) && !TERMINAL.includes(current.state)) return error("sa_body_job_exists");
        if (!current || current.status !== "ok") return current || error("native_host_unavailable");
        const ref = {schema_version:2,owner:identity(collector),job_id:null,revision:null,cancel_requested:false,
          pending_start:{request_id:uuid(),manifest_id:manifestId},next_wake:now()+1000};
        await update(()=>ref);
        // A worker crash after this write must still wake the same manual intent.
        await deps.alarms.create(ALARM,{when:ref.next_wake});
        const started = await finishStart(ref);
        return schedule(await call("state",started));
      } catch (err) { return failed(err); }
    }
    function start(manifestId) {
      if (starting) return Promise.resolve(error("already_pending"));
      starting = doStart(manifestId).finally(()=>{starting=null;});
      return starting;
    }
    async function status() {
      try {
        const ref = await read();
        if (ref && ref.cancel_requested) return {status:"ok",state:"cancelling",job_id:ref.job_id,cancel_pending:true};
        if (ref && ref.pending_start) return {status:"ok",state:"waiting",reason_code:"sa_body_start_unconfirmed"};
        const reply = await call("state",ref);
        if (jobReply(reply)) {
          const page = await call("items",ref,{job_id:reply.job_id});
          if (!jobReply(page)) return page || error("native_host_unavailable");
          return {...reply,items:page.items || [],next_cursor:page.next_cursor || null,reconnect_required:!ref};
        }
        const legacy = (await deps.storage.get("saArticleBodyRecovery")).saArticleBodyRecovery;
        return {...reply,legacy_history:legacy || null};
      } catch (err) { return error(err && err.error_code || "native_host_unavailable"); }
    }
    async function items(jobId, cursor) {
      try {
        const ref = await read();
        const page = await call("items",ref,{job_id:jobId,cursor:cursor || null});
        return {...page,reconnect_required:!ref};
      } catch (err) { return error(err && err.error_code || "native_host_unavailable"); }
    }
    async function step(run) {
      try {
        let ref = await read();
        if (!ref || !ref.job_id && !ref.pending_start) return {status:"ok",state:"not_started"};
        if (ref.cancel_requested) return await cancelNative(ref);
        ref = await finishStart(ref);
        if (run.cancelled || (await read()).cancel_requested) return await cancelNative(await read());
        const pending = await deps.reconcilePending();
        if (pending.pending || pending.runtime_active) return await schedule({status:"ok",state:"waiting",reason_code:"sa_body_cleanup_unconfirmed"},POLL_MS);
        let next = await call("next",ref);
        if (!jobReply(next)) throw next;
        await remember(next);
        if (run.cancelled || (await read()).cancel_requested) return await cancelNative(await read());
        if (!next.target) return await schedule(next,POLL_MS);
        const target = next.target;
        run.body_job_id = next.job_id;
        const result = await deps.enqueue({key:next.job_id+":"+target.article_id,displayName:"Article body repair",
          operation:"alpha_picks_body_repair",mode:"manual",trigger:"continuation",intent_revision:next.revision,
          acquisition:{body_job_id:next.job_id,body_job_revision:next.revision,article_id:target.article_id},
          onLifetime:lifetime=>{run.lifetime=lifetime;if(run.cancelled)lifetime.cancelled=true;},
          eligible:async()=>!run.cancelled && !(await read()).cancel_requested},
        diagnostics=>run.cancelled ? {status:"cancelled",reason:"operator_cancelled"} : deps.capture(target,run,diagnostics));
        ref = await read();
        if (run.cancelled || ref.cancel_requested) return await cancelNative(ref);
        if (result.acquisition && result.acquisition.body_recovery_job_id === ref.job_id) {
          const checkpoint = await call("checkpoint",ref,{article_id:target.article_id,task_id:result.acquisition.task_id});
          if (!jobReply(checkpoint)) throw checkpoint;
          await remember(checkpoint);
        }
        // Readback selects but never admits a second article in this turn.
        next = await call("next",await read());
        if (!jobReply(next)) throw next;
        await remember(next);
        return await schedule(next,result.acquisition_uncertain || result.status === "deferred" ? POLL_MS : 1000);
      } catch (err) { return failed(err); }
    }
    function wake() {
      if (waking) return waking;
      active = {cancelled:false};
      waking = step(active).finally(()=>{active=null;waking=null;});
      return waking;
    }
    async function cancel(jobId) {
      try {
        let ref = await read();
        if (!ref || jobId && ref.job_id !== jobId) {
          if (ref && (ref.pending_start || ref.cancel_requested)) return error("already_pending");
          if (!/^[a-f0-9]{32}$/.test(jobId || "")) return error("sa_body_job_not_found");
          const collector = await owned(null);
          const state = await call("state",null,{job_id:jobId});
          if (!jobReply(state) || state.job_id !== jobId) return state || error("sa_body_job_not_found");
          // Explicit discard by the selected collector is not a transfer of
          // acquisition intent. This reference can only cancel the old job.
          ref = {schema_version:2,owner:identity(collector),job_id:state.job_id,revision:state.revision,
            cancel_requested:true,pending_start:null,next_wake:now()+1000};
          await update(()=>ref);
        }
        if (active) {
          active.cancelled = true;
          if (active.lifetime) {
            active.lifetime.cancelled = true;
            if (active.lifetime.wake) active.lifetime.wake();
          }
        }
        await update(current=>({...current,cancel_requested:true}));
        return await cancelNative(await read());
      } catch (err) {
        const reply = await failed(err);
        return {...reply,state:"cancelling",cancel_pending:true};
      }
    }
    async function resume(jobId) {
      try {
        let ref = await read();
        if (ref && ref.cancel_requested) return error("sa_body_cancel_pending");
        const state = await call("state",ref,{job_id:jobId});
        if (!jobReply(state) || TERMINAL.includes(state.state)) return error("sa_body_job_not_active");
        if (state.owner_changed) return error("sa_body_owner_changed");
        if (!ref) {
          const collector = await owned(null);
          ref = {schema_version:2,owner:identity(collector),job_id:state.job_id,revision:state.revision,
            cancel_requested:false,pending_start:null,next_wake:now()+1000};
          await update(()=>ref);
        }
        await remember(state);
        const reply = state.state === "paused" ? await call("resume",await read(),{confirm_handled:true}) : state;
        if (!jobReply(reply)) return reply;
        await remember(reply);
        return schedule(reply);
      } catch (err) { return failed(err); }
    }
    async function syncAlarm() {
      try {
        const ref = await read();
        if (!ref || ref.next_wake === null && !ref.cancel_requested && !ref.pending_start) {
          await deps.alarms.clear(ALARM);return;
        }
        await deps.alarms.create(ALARM,{when:Math.max(now()+1000,ref.next_wake || 0)});
      } catch (_) { await deps.alarms.clear(ALARM); }
    }
    return {preview,start,status,items,wake,cancel,resume,syncAlarm,get running() {return !!waking;}};
  }
  root.SAArticleBodyRecovery = Object.freeze({create,alarm:ALARM,storageKey:KEY});
}(globalThis));
