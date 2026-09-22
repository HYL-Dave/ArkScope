(function () {
  "use strict";
  var form = document.getElementById("companyRefreshForm");
  var output = document.getElementById("companyRefreshStatus");
  var button = document.getElementById("companyRefreshNow");
  var targetMode = document.getElementById("companyRefreshTargetMode");
  var tickerInput = document.getElementById("companyRefreshTickers");
  var collectorOutput = document.getElementById("companyCollectorStatus");
  var selectCollector = document.getElementById("companyCollectorSelect");
  var recoverCollector = document.getElementById("companyCollectorRecover");
  var cancelQueue = document.getElementById("companyRefreshCancel");
  var dirty = false;
  var updating = false;
  form.addEventListener("input", function () { dirty = true; });
  function targetControls() {
    tickerInput.disabled = targetMode.value === "watchlist";
    tickerInput.required = !tickerInput.disabled;
    tickerInput.parentElement.hidden = tickerInput.disabled;
  }
  targetMode.addEventListener("change", function () { dirty = true; targetControls(); });
  function send(action, extra) {
    return new Promise(function (resolve) {
      chrome.runtime.sendMessage(Object.assign({action:action}, extra || {}), function (result) {
        resolve(chrome.runtime.lastError || !result ? {status:"error",error_code:"sa_company_schedule_unavailable"} : result);
      });
    });
  }
  function paragraph(value) { var node = document.createElement("p"); node.textContent = value; output.appendChild(node); }
  function render(result) {
    output.replaceChildren();
    if (result.status !== "ok" || !result.config) {
      paragraph(result.error_code || "sa_company_schedule_unavailable");
      return;
    }
    if (!dirty) {
      targetMode.value = result.config.target_mode || "manual";
      document.getElementById("companyRefreshTickers").value = result.config.tickers.join(", ");
      document.getElementById("companyRefreshEnabled").checked = result.config.enabled;
      document.getElementById("companyRefreshDays").value = result.config.interval_days;
      form.querySelectorAll('[name="companyRefreshStatement"]').forEach(function (input) {
        input.checked = result.config.statements.includes(input.value);
      });
      form.querySelectorAll('[name="companyRefreshView"]').forEach(function (input) {
        input.checked = result.config.views.includes(input.value);
      });
      targetControls();
    }
    var control = result.collector;
    collectorOutput.textContent = !control ? "" : control.status !== "ok" ? control.error_code
      : !control.owner ? "Collector: not selected" : "Collector: " + control.owner.browser
        + (control.is_owner ? " (this installation)" : " (another installation)");
    selectCollector.disabled = !!(control && (control.status !== "ok" || control.is_owner || control.active));
    recoverCollector.hidden = !(control && control.active);
    recoverCollector.disabled = !!result.running;
    var denied = control && (control.status !== "ok" || !control.is_owner || control.active || control.rate_limited);
    button.disabled = updating || result.running || !!denied || result.pending_count > 0 && !(result.paused_reason || control && control.paused_reason);
    button.textContent = result.running ? "Updating..." : result.paused_reason || control && control.paused_reason ? "Resume / update now" : "Update now";
    cancelQueue.hidden = !(result.pending_count > 0);
    var targetOutput = document.getElementById("companyRefreshTargets");
    targetOutput.replaceChildren();
    var info = result.target_info;
    if (info) {
      if (info.status !== "ok") targetOutput.textContent = info.error_code;
      else {
        var count = document.createElement("p");
        count.textContent = "App watchlist: " + info.tickers.length + " / " + info.total_count + " supported";
        targetOutput.appendChild(count);
        (info.unsupported || []).forEach(function (item) {
          var row = document.createElement("p"); row.textContent = item.ticker + ": " + item.reason; targetOutput.appendChild(row);
        });
        var details = document.createElement("details");
        var summary = document.createElement("summary"); summary.textContent = "Targets and membership"; details.appendChild(summary);
        info.tickers.forEach(function (ticker) {
          var row = document.createElement("p");
          row.textContent = ticker + " | " + ((info.sources_by_ticker || {})[ticker] || []).join(", ");
          details.appendChild(row);
        });
        Object.entries(info.source_status || {}).forEach(function (entry) {
          (entry[1].warnings || []).forEach(function (warning) {
            var row = document.createElement("p"); row.textContent = entry[0] + ": " + warning; details.appendChild(row);
          });
        });
        targetOutput.appendChild(details);
      }
    }
    var hostUnavailable = (result.scopes || []).some(function (scope) {
      return scope.last_error === "sa_company_native_host_unavailable";
    });
    paragraph(result.rate_limited || control && control.rate_limited ? "Rate limit cooldown until " + (control && control.rate_limit_until || result.rate_limit_until)
      : result.paused_reason || control && control.paused_reason ? "Paused: " + (result.paused_reason || control.paused_reason)
      : denied ? "Waiting for collector"
      : result.blocked_reason ? result.blocked_reason + " | Next attempt: " + (result.deferred_until || "Pending")
      : result.running ? "Updating" : hostUnavailable ? "Local app connection unavailable"
        : result.config.enabled ? "Scheduled" : "Schedule off");
    if (result.pending_count) paragraph("Queued: " + result.pending_count + " scopes");
    (result.scopes || []).forEach(function (scope) {
      var name = {income_statement:"Income",balance_sheet:"Balance",cash_flow_statement:"Cash flow"}[scope.statement];
      paragraph(scope.ticker + " / " + name + " / " + scope.view + " / USD"
        + " | Last success: " + (scope.last_success_at || "Never")
        + " | Next attempt: " + (scope.next_due_at || "Due")
        + (scope.last_error ? " | " + scope.last_error : ""));
    });
  }
  function config() {
    function checked(name) {
      return Array.from(form.querySelectorAll('[name="' + name + '"]:checked'), function (input) { return input.value; });
    }
    return {
      enabled:document.getElementById("companyRefreshEnabled").checked,
      target_mode:targetMode.value,
      tickers:targetMode.value === "watchlist" ? [] : Array.from(new Set(tickerInput.value.toUpperCase().split(/[\s,]+/).filter(Boolean))),
      interval_days:Number(document.getElementById("companyRefreshDays").value),
      statements:checked("companyRefreshStatement"), views:checked("companyRefreshView"),
    };
  }
  async function save() {
    if (!form.reportValidity()) return false;
    var result = await send("configure_company_refresh", {config:config()});
    dirty = result.status !== "ok";
    render(result);
    return result.status === "ok";
  }
  form.addEventListener("submit", function (event) { event.preventDefault(); save(); });
  selectCollector.addEventListener("click", async function () { render(await send("select_company_collector")); });
  recoverCollector.addEventListener("click", async function () {
    if (!window.confirm("Stop the previous collector and close its acquisition tabs before continuing. Has that collector stopped?")) return;
    render(await send("recover_company_collector", {confirm_stopped:true}));
  });
  cancelQueue.addEventListener("click", async function () { render(await send("cancel_company_refresh")); });
  button.addEventListener("click", async function () {
    if (updating) return;
    updating = true;
    button.disabled = true;
    try {
      if (await save()) render(await send("run_company_refresh"));
    } finally {
      updating = false;
      render(await send("get_company_refresh"));
    }
  });
  send("get_company_refresh").then(render);
  chrome.storage.onChanged.addListener(function (changes, area) {
    if (area === "local" && changes.companyFinancialRefresh) send("get_company_refresh").then(render);
  });
})();
