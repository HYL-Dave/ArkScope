(function () {
  "use strict";
  var form = document.getElementById("companyRefreshForm");
  var output = document.getElementById("companyRefreshStatus");
  var button = document.getElementById("companyRefreshNow");
  var dirty = false;
  var updating = false;
  form.addEventListener("input", function () { dirty = true; });
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
      document.getElementById("companyRefreshTickers").value = result.config.tickers.join(", ");
      document.getElementById("companyRefreshEnabled").checked = result.config.enabled;
      document.getElementById("companyRefreshDays").value = result.config.interval_days;
      form.querySelectorAll('[name="companyRefreshStatement"]').forEach(function (input) {
        input.checked = result.config.statements.includes(input.value);
      });
      form.querySelectorAll('[name="companyRefreshView"]').forEach(function (input) {
        input.checked = result.config.views.includes(input.value);
      });
    }
    button.disabled = updating || result.running;
    button.textContent = result.running ? "Updating..." : result.paused_reason ? "Resume / update now" : "Update now";
    var hostUnavailable = (result.scopes || []).some(function (scope) {
      return scope.last_error === "sa_company_native_host_unavailable";
    });
    paragraph(result.rate_limited ? "Rate limit cooldown until " + result.rate_limit_until
      : result.paused_reason ? "Paused: " + result.paused_reason
      : result.running ? "Updating" : hostUnavailable ? "Local app connection unavailable"
        : result.config.enabled ? "Scheduled" : "Schedule off");
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
      tickers:Array.from(new Set(document.getElementById("companyRefreshTickers").value.toUpperCase().split(/[\s,]+/).filter(Boolean))),
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
