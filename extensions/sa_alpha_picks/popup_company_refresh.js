(function () {
  "use strict";
  var $ = function(id) {return document.getElementById(id);};
  var form=$("companyRefreshForm"), output=$("companyRefreshStatus"), target=$("companyRefreshTargetMode"), ticker=$("companyRefreshTickers");
  var dirty=false, policyDirty=false, busy=false, revision=0, readRevision=0, state=null, expectedGeneration=null;
  var liveState=null, reloadPending=false, actionError=null;
  function lockForm(value) {
    busy=value;
    form.querySelectorAll('input, select, button').forEach(function(input){
      if(value){input.dataset.wasDisabled=String(input.disabled);input.disabled=true;}
      else if(input.dataset.wasDisabled!==undefined){input.disabled=input.dataset.wasDisabled==='true';delete input.dataset.wasDisabled;}
    });
    if(!value && reloadPending) {reloadPending=false;reload();}
  }
  function send(action,extra) {
    return new Promise(function(resolve) {
      chrome.runtime.sendMessage(Object.assign({action:action},extra || {}),function(result) {
        resolve(chrome.runtime.lastError || !result ? {status:"error",error_code:"sa_company_schedule_unavailable"} : result);
      });
    });
  }
  function line(parent,text) {var p=document.createElement("p");p.textContent=text;parent.appendChild(p);}
  function checked(name) {return Array.from(form.querySelectorAll('[name="'+name+'"]:checked'),function(input){return input.value;});}
  function config() {
    return {enabled:$("companyRefreshEnabled").checked,target_mode:target.value,
      tickers:target.value === "watchlist" ? [] : Array.from(new Set(ticker.value.toUpperCase().split(/[\s,]+/).filter(Boolean))),
      interval_days_by_view:{annual:Number($("companyRefreshDays").value),quarterly:Number($("companyRefreshQuarterlyDays").value)},
      financial_gap_seconds:Number($("companyFinancialGap").value),
      statements:checked("companyRefreshStatement"),views:checked("companyRefreshView")};
  }
  function targetControls() {
    ticker.disabled=target.value === "watchlist";ticker.required=!ticker.disabled;ticker.parentElement.hidden=ticker.disabled;
  }
  function budgetControls() {
    var enabled=$("companyBudgetEnabled").checked;
    $("companyPageBudget").hidden=!enabled;
    form.querySelectorAll('.company-budget input').forEach(function(input){input.disabled=!enabled;});
  }
  function policy() {
    if(!$("companyBudgetEnabled").checked)return {hour_limit:null,day_limit:null,hour_reserve:0,day_reserve:0};
    var value={};
    ["hour_limit","day_limit","hour_reserve","day_reserve"].forEach(function(key) {
      var text=form.querySelector('[name="'+key+'"]').value;value[key]=text === "" ? null : Number(text);
    });
    return value;
  }
  function renderPreview(result) {
    var node=$("companyScopePreview");node.replaceChildren();
    if (!result || result.status !== "ok") {line(node,result && result.error_code || "Scope preview unavailable");return;}
    var count=result.counts;
    line(node,(result.first_fill ? "Initial fill" : "Maintenance")+": "+result.total_scopes+" scopes");
    line(node,"Missing checks "+count.missing+" | Due "+count.due+" | Reusable "+count.reusable+" | Blocked "+count.blocked);
    line(node,"Minimum pacing wait: "+Math.ceil(result.pacing_lower_bound_seconds/60)+" min | "+config().financial_gap_seconds+" s gap");
    if (result.active_delay_seconds>0) line(node,"Current pacing delay: "+Math.ceil(result.active_delay_seconds)+" s");
    if (result.observed_duration && result.observed_duration.sample_count) line(node,"Observed capture: "+Math.round(result.observed_duration.mean_ms/1000)+" s average / "+result.observed_duration.sample_count+" scopes");
    else line(node,"Capture-duration coverage: not measured");
    if (result.blocked_reason) line(node,"Waiting: "+result.blocked_reason);
  }
  async function preview() {
    var ticket=++revision;
    var result=await send("preview_company_refresh",{config:config()});
    if(ticket===revision)renderPreview(result);
  }
  function recoveryAllowed() {
    return !busy && liveState && liveState.acquisition_runtime_active === false
      && liveState.acquisition_recovery_required === true && !(state && state.running);
  }
  function renderLifecycle() {
    var node=$("saAcquisitionLive"), control=state && state.collector || {};
    var running=liveState && (liveState.acquisition_runtime_active === true || state && state.running);
    var stopped=!running && liveState && liveState.acquisition_recovery_required === true;
    var active=control.active || {};
    node.className=stopped ? "partial" : "empty";
    node.setAttribute("role",stopped ? "alert" : "status");
    if(running) {
      node.textContent="Acquisition running: "+(active.operation || "operation pending")
        +" | Started: "+(active.started_at || liveState && liveState.acquisition_pending_since || "unknown")
        +" | Navigation attempts: "+(Number.isInteger(active.navigation_attempt_count) ? active.navigation_attempt_count : "unknown");
    } else if(stopped) {
      node.textContent="Stopped capture: recovery required."
        +" | Operation: "+(active.operation || "unknown")
        +" | Since: "+(liveState.acquisition_pending_since || active.started_at || "unknown");
    } else {
      node.textContent=liveState ? "Acquisition: idle here." : "Acquisition status unavailable.";
    }
    var pending=state && state.queue && state.queue.pending;
    if(pending && Number.isInteger(pending.routine) && Number.isInteger(pending.background)) {
      node.textContent+=" | Queued: "+(pending.routine+pending.background);
    }
    $("saAcquisitionReviewRecovery").hidden=!stopped;
    $("companyCollectorRecover").hidden=!(stopped || running && (control.active || state.acquisition_pending));
    $("companyCollectorRecover").disabled=!recoveryAllowed();
  }
  function warning(control) {
    var node=$("saAcquisitionWarning"), caps=Object.keys(control && control.capability_pauses || {});
    var reason=control && control.paused_reason;
    node.hidden=!reason && !caps.length && !(control && control.rate_limited);
    node.textContent=reason === "login_required" ? "Seeking Alpha sign-in expired. Acquisition paused."
      : reason === "human_verification_required" ? "Seeking Alpha verification required. Acquisition paused."
      : caps.length ? "Subscription access unavailable: "+caps.join(", ")+". Premium and Alpha Picks require separate access."
      : control && control.rate_limited ? "Seeking Alpha cooldown until "+control.rate_limit_until
      : reason || "";
    $("saAcquisitionResume").hidden=!(reason || caps.length);
    $("saAcquisitionResume").disabled=busy || !(control && control.is_owner) || !!control.active;
  }
  function render(result, fromRead) {
    var valid=result && result.status === "ok" && result.config;
    var error=(result && result.activation_step ? result.activation_step+": " : "")
      +(result && result.error_code || "sa_company_schedule_unavailable");
    if(!fromRead)actionError=valid ? null : error;
    output.replaceChildren();
    if(actionError)line(output,"Last action: "+actionError);
    if (!valid) {
      if(fromRead)line(output,error);
      return;
    }
    var firstRender=!state;
    state=result;
    if(typeof result.acquisition_runtime_active === "boolean")liveState=result;
    var control=result.collector || {}, values=result.config;
    if (!dirty) {
      target.value=values.target_mode || "manual";ticker.value=values.tickers.join(", ");
      $("companyRefreshEnabled").checked=values.enabled;
      var periods=values.interval_days_by_view || {annual:values.interval_days || 7,quarterly:values.interval_days || 7};
      $("companyRefreshDays").value=periods.annual;$("companyRefreshQuarterlyDays").value=periods.quarterly;
      $("companyFinancialGap").value=values.financial_gap_seconds || 60;
      form.querySelectorAll('[name="companyRefreshStatement"]').forEach(function(input){input.checked=values.statements.includes(input.value);});
      form.querySelectorAll('[name="companyRefreshView"]').forEach(function(input){input.checked=values.views.includes(input.value);});
      targetControls();
    }
    if (!dirty && !policyDirty) {
      $("companyBudgetEnabled").checked=!!(control.policy && control.policy.hour_limit!==null);
      if(control.policy)Object.keys(control.policy).forEach(function(key){var input=form.querySelector('[name="'+key+'"]');if(input)input.value=control.policy[key] == null ? "" : control.policy[key];});
      budgetControls();
      if(firstRender)$("companyAdvanced").open=!control.policy;
      expectedGeneration=control.generation == null ? 0 : control.generation;
    }
    var changed=control.generation != null && control.generation!==expectedGeneration;
    $("companyReloadSettings").hidden=!changed;
    $("companyCollectorSelect").disabled=busy || !!control.active || changed;
    $("companyCollectorSelect").textContent=$("companyRefreshEnabled").checked ? "Enable updates here" : "Use these settings here";
    $("companyCollectorStatus").textContent=control.status === "error" ? control.error_code
      : !control.owner ? "Collector: not selected" : "Collector: "+control.owner.browser+(control.is_owner ? " (this installation)" : " (another installation)");
    var name=chrome.runtime.getManifest ? chrome.runtime.getManifest().name : "";
    $("companyEnvironment").textContent=/Company Test/.test(name) ? "Data: isolated test profile" : "Data: host-configured App profile";
    var denied=control.status !== "ok" || !control.is_owner || control.active || control.paused_reason || control.rate_limited
      || control.capability_pauses && control.capability_pauses.financials || result.paused_reason || result.acquisition_pending;
    $("companyRefreshNow").disabled=busy || !!result.running || !!denied;
    $("companyRefreshForce").disabled=$("companyRefreshNow").disabled;
    renderLifecycle();
    $("companyRefreshCancel").hidden=!result.pending_count;
    warning(control);
    var targets=$("companyRefreshTargets"), info=result.target_info;targets.replaceChildren();
    if(info) {
      if(info.status!=="ok")line(targets,info.error_code);
      else {
        line(targets,"App watchlist: "+info.tickers.length+" / "+info.total_count+" supported");
        (info.unsupported || []).forEach(function(item){line(targets,item.ticker+": "+item.reason);});
        var membership=document.createElement("details"), label=document.createElement("summary");
        label.textContent="Targets and membership";membership.appendChild(label);
        info.tickers.forEach(function(symbol){line(membership,symbol+" | "+((info.sources_by_ticker || {})[symbol] || []).join(", "));});
        Object.entries(info.source_status || {}).forEach(function(entry){
          (entry[1].warnings || []).forEach(function(value){line(targets,entry[0]+": "+value);});
        });
        targets.appendChild(membership);
      }
    }
    var connectionFailed=(result.scopes || []).some(function(scope){return scope.last_error === 'sa_company_native_host_unavailable';});
    if(connectionFailed)line(output,"Local app connection unavailable: sa_company_native_host_unavailable");
    if(result.rate_limited || control.rate_limited)line(output,"Seeking Alpha cooldown until "+(control.rate_limit_until || result.rate_limit_until));
    line(output,result.running ? "Updating" : result.paused_reason ? "Paused: "+result.paused_reason
      : denied ? "Waiting for collector / access" : result.config.enabled ? "Scheduled" : "Schedule off");
    if(result.pending_count)line(output,"Queued: "+result.pending_count+" scopes");
    if(control.active)line(output,"Current: "+(control.active.scope ? control.active.scope.ticker+" / "+control.active.scope.view : control.active.operation));
    if(control.financial_gap_seconds)line(output,"Accepted financial gap: "+control.financial_gap_seconds+" s");
    if(control.policy)line(output,control.policy.hour_limit===null ? "Page budget: no hourly / daily cap"
      : "Page budget: "+control.policy.hour_limit+" / hour | "+control.policy.day_limit+" / day");
    if(control.next_financial_at)line(output,"Next financial eligibility: "+control.next_financial_at);
    if(result.blocked_reason)line(output,result.blocked_reason+" | Next attempt: "+(result.deferred_until || "Pending"));
    if(result.queue && result.queue.oldest_wait_ms)line(output,"Queue wait: "+Math.round(result.queue.oldest_wait_ms/1000)+" s");
    var records=document.createElement("details"), summary=document.createElement("summary");summary.textContent="Scope status";records.appendChild(summary);
    (result.scopes || []).forEach(function(scope){line(records,scope.ticker+" / "+scope.statement+" / "+scope.view+" / USD | Last success: "+(scope.last_success_at || "Never")+" | Next attempt: "+(scope.next_due_at || "Due")+(scope.last_error ? " | "+scope.last_error : ""));});
    output.appendChild(records);
  }
  async function reload() {
    if(busy) {reloadPending=true;return;}
    var ticket=++readRevision;
    var result=await send("get_company_refresh");
    if(ticket!==readRevision)return;
    if(busy) {reloadPending=true;return;}
    if(result.status!=="ok") {liveState=null;renderLifecycle();$("saAcquisitionResume").disabled=true;}
    render(result,true);await preview();
  }
  form.addEventListener("input",function(event){
    var input=event.target;
    if(input.matches('#companyBudgetEnabled, [name="hour_limit"], [name="day_limit"], [name="hour_reserve"], [name="day_reserve"]')) {
      policyDirty=true;budgetControls();return;
    }
    if(!input.matches('#companyRefreshEnabled, #companyRefreshTargetMode, #companyRefreshTickers, #companyRefreshDays, #companyRefreshQuarterlyDays, #companyFinancialGap, [name="companyRefreshStatement"], [name="companyRefreshView"]'))return;
    dirty=true;targetControls();preview();
  });
  target.addEventListener("change",function(){dirty=true;targetControls();preview();});
  form.addEventListener("submit",async function(event){event.preventDefault();if(busy)return;lockForm(true);var result;try{result=await send("save_company_refresh",{config:config()});}finally{lockForm(false);}dirty=result.status!=="ok";render(result);await preview();});
  $("companyCollectorSelect").addEventListener("click",async function(){
    if(busy || !form.reportValidity())return;
    if($("companyBudgetEnabled").checked && Array.from(form.querySelectorAll('.company-budget input')).some(function(input){return input.value === "";})) {
      $("companyAdvanced").open=true;render({status:"error",error_code:"Enter both page limits and routine reserves."});return;
    }
    if(!$("companyActivationConfirmed").checked){$("companyAdvanced").open=true;render({status:"error",error_code:"Confirm stopped installations and acquisition settings."});return;}
    lockForm(true);
    var result=await send("enable_sa_updates_here",{config:config(),policy:policy(),expected_generation:expectedGeneration,
      confirm_activation:true,confirm_schedules:true,confirm_stopped:$("companyRecoveryConfirmed").checked});
    lockForm(false);
    if(result.status!=="ok")$("companyRefreshEnabled").checked=false;
    else {dirty=false;policyDirty=false;}
    render(result);
    if(result.status==='ok')await preview();
  });
  async function update(force) {
    if(busy)return;
    if(force && !$("companyForceConfirmed").checked){render({status:"error",error_code:"Confirm force refresh."});return;}
    if(!form.reportValidity())return;
    lockForm(true);
    var result;
    try {
      if(dirty)result=await send("save_company_refresh",{config:config()});
      if(!result || result.status==='ok'){dirty=false;result=await send("run_company_refresh",{force:force,confirm_force:force});}
    } finally {lockForm(false);}
    render(result);
    await preview();
  }
  $("companyRefreshNow").addEventListener("click",function(){update(false);});
  $("companyRefreshForce").addEventListener("click",function(){update(true);});
  $("companyRefreshCancel").addEventListener("click",async function(){render(await send("cancel_company_refresh"));await preview();});
  $("companyCollectorRecover").addEventListener("click",async function(){
    if(!recoveryAllowed() || !$("companyRecoveryConfirmed").checked)return;
    lockForm(true);
    var result=await send("recover_sa_acquisition",{expected_generation:state.collector.generation,confirm_stopped:true});
    lockForm(false);
    if(result.status==="ok") {actionError=null;$("companyRecoveryConfirmed").checked=false;await reload();}
    else render(result);
  });
  $("saAcquisitionReviewRecovery").addEventListener("click",function(){
    $("companyRefreshOptions").open=true;
    $("companyAdvanced").open=true;
    $("companyRecoveryConfirmed").focus();
  });
  $("saAcquisitionResume").addEventListener("click",async function(){
    var caps=Object.keys(state.collector.capability_pauses || {});
    render(await send("resume_sa_acquisition",{expected_generation:state.collector.generation,confirm_handled:true,capability:caps[0]}));
  });
  $("companyReloadSettings").addEventListener("click",function(){dirty=false;policyDirty=false;actionError=null;reload();});
  chrome.storage.onChanged.addListener(function(changes,area){
    // Persisted runtime is a wake-up signal, never evidence of liveness.
    if(area === "local" && (changes.companyFinancialRefresh || changes.saAcquisitionStatus
      || changes.saAcquisitionPending || changes.saAcquisitionRuntime))reload();
  });
  reload();
})();
