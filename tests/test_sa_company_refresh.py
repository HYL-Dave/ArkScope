"""Financial refresh eligibility, not publication recency or paid fallback."""

import json
import subprocess

import pytest

from tests.test_sa_extension_popup import ROOT, _run, _run_background_probe


SETUP = """
let clock = Date.parse('2026-09-22T00:00:00Z');
const saved = {};
const alarms = [];
const calls = [];
const storage = {
  async get(key) { return {[key]: structuredClone(saved[key])}; },
  async set(value) { Object.assign(saved, structuredClone(value)); },
};
const deps = {
  storage,
  alarms: {async clear() {}, async create(name, value) { alarms.push({name, ...value}); }},
  now: () => clock,
  runScope: async (scope, mode, admitted) => {
    if (!await admitted()) return {status:'cancelled'};
    calls.push({scope, mode});
    return {status:'ok', observation_id:'a'.repeat(64),currency:'USD'};
  },
};
const api = SACompanyRefresh.create(deps);
const config = {enabled:true, tickers:['AMD'], statements:['income_statement'], views:['annual','quarterly'], interval_days:7};
await api.configure(config);
"""


def probe(body):
    # JSON cloning is sufficient: this state intentionally contains no Date objects.
    return _run_background_probe(
        "const structuredClone = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));\n"
        + SETUP + body
    )


def test_due_updates_are_scoped_and_reads_do_not_extend_the_deadline():
    result = probe("""
      await api.run(false);
      const first = await api.status();
      await api.run(false);
      clock += 20 * 3600000;
      const before = await api.status();
      await api.status();
      await api.configure(config);
      const after = await api.status();
      await api.run(false);
      return {calls,first,before,after};
    """)
    assert [c["scope"]["view"] for c in result["calls"]] == ["annual", "quarterly"]
    assert result["first"]["scopes"][0]["next_due_at"] == "2026-09-29T00:00:00.000Z"
    assert result["first"]["scopes"][1]["last_success_at"] is None
    assert result["before"]["scopes"] == result["after"]["scopes"]


def test_refresh_can_be_forced_but_does_not_change_the_configured_interval():
    result = probe("""
      await api.run(true);
      clock += 86400000;
      await api.run(false);
      await api.run(true);
      return {calls, status:await api.status()};
    """)
    assert len(result["calls"]) == 4
    assert result["status"]["config"]["interval_days"] == 7
    assert result["status"]["scopes"][0]["last_success_at"] == "2026-09-23T00:00:00.000Z"


def test_invalid_scope_never_replaces_the_saved_configuration():
    result = probe("""
      const errors = [];
      for (const patch of [{tickers:['../AMD']}, {interval_days:0}, {interval_days:1.5},
        {views:['ttm']}, {statements:[]}, {enabled:'true'}, {tickers:['AMD?x=y']}]) {
        try { await api.configure({...config,...patch}); } catch (e) { errors.push(e.message); }
      }
      return {errors,status:await api.status(),calls};
    """)
    assert result["errors"] == ["sa_company_schedule_invalid"] * 7
    assert result["status"]["config"]["tickers"] == ["AMD"]
    assert result["calls"] == []


def test_disabled_schedule_keeps_manual_update_available():
    result = probe("""
      await api.configure({...config,enabled:false});
      await api.run(false);
      const automatic = calls.length;
      await api.run(true);
      return {automatic,calls,status:await api.status()};
    """)
    assert result["automatic"] == 0
    assert len(result["calls"]) == 2
    assert result["status"]["config"]["enabled"] is False


def test_protocol_accepts_manual_and_scheduled_financial_captures():
    from src.sa.extension_run_protocol import derive_run_result

    for mode in ("scheduled", "manual"):
        result = derive_run_result({
            "schema_version": 1, "operation": "company_financial_capture", "mode": mode,
            "item_outcomes": [], "phases": {
                "extraction": {"state": "complete", "reason_code": None},
                "persistence": {"state": "complete", "reason_code": None},
            },
        })
        assert result["derived_outcome"] == "complete"
        assert result["job_name"] == "sa_company_financial_capture"


def test_failure_preserves_old_success_and_backs_off_across_restart():
    result = probe("""
      await api.run(false);
      clock += 8 * 86400000;
      deps.runScope = async () => ({status:'error',error_code:'sa_company_dom_not_ready'});
      await api.run(false);
      const failed = await api.status();
      const restarted = SACompanyRefresh.create(deps);
      await restarted.run(false); // Only the other, previously uncaptured scope is eligible.
      return {failed,after:await restarted.status()};
    """)
    record = result["failed"]["scopes"][0]
    assert record["last_success_at"] == "2026-09-22T00:00:00.000Z"
    assert record["retry_after"] == "2026-09-30T06:00:00.000Z"
    assert record["last_error"] == "sa_company_dom_not_ready"
    assert result["after"]["scopes"][0] == record


def test_challenge_stops_the_whole_batch_until_explicit_manual_retry():
    result = probe("""
      let attempted = 0;
      deps.runScope = async () => {
        attempted++;
        return {status:'error',error_code:'sa_company_human_verification_required'};
      };
      await api.run(true);
      const paused = await api.status();
      clock += 30 * 86400000;
      await SACompanyRefresh.create(deps).run(false);
      return {paused,attempted};
    """)
    assert result["attempted"] == 1
    assert result["paused"]["paused_reason"] == "sa_company_human_verification_required"
    assert all(scope["last_success_at"] is None for scope in result["paused"]["scopes"])


def test_rate_limit_stops_the_batch_and_manual_retry_cannot_bypass_cooldown():
    result = probe("""
      await api.run(false);
      const oldSuccess = (await api.status()).scopes[0].last_success_at;
      let attempted = 0;
      deps.runScope = async () => {
        attempted++;
        return {status:'error',error_code:'sa_company_rate_limited'};
      };
      await api.run(true);
      const limited = await api.status();
      const restarted = SACompanyRefresh.create(deps);
      await restarted.configure({...config,tickers:['AAPL']});
      await restarted.run(true);
      await restarted.run(false);
      return {attempted,oldSuccess,limited,after:await restarted.status(),alarms};
    """)
    assert result["attempted"] == 1
    assert result["limited"]["rate_limited"] is True
    assert result["limited"]["rate_limit_until"] == "2026-09-22T06:00:00.000Z"
    assert result["limited"]["scopes"][0]["last_success_at"] == result["oldSuccess"]
    assert result["after"]["scopes"][0]["last_success_at"] is None
    assert result["after"]["scopes"][0]["next_due_at"] == "2026-09-22T06:00:00.000Z"
    assert result["alarms"][-1]["when"] == 1790056800000


def test_repeated_rate_limits_back_off_across_symbols_then_recover_one_scope():
    result = probe("""
      const attempted = [];
      deps.runScope = async (scope) => {
        attempted.push(scope.ticker);
        return {status:'error',error_code:'sa_company_rate_limited'};
      };
      await api.run(false);
      clock += 6 * 3600000;
      await api.configure({...config,tickers:['AAPL']});
      await api.run(false);
      const second = await api.status();
      clock += 12 * 3600000 - 1;
      await api.run(true);
      const beforeDeadline = attempted.length;
      clock += 1;
      deps.runScope = async (scope) => {
        attempted.push(scope.ticker);
        return {status:'ok',currency:'USD',observation_id:'b'.repeat(64)};
      };
      await api.run(false);
      return {attempted,beforeDeadline,second,recovered:await api.status()};
    """)
    assert result["second"]["rate_limit_until"] == "2026-09-22T18:00:00.000Z"
    assert result["beforeDeadline"] == 2
    assert result["attempted"] == ["AMD", "AAPL", "AAPL"]
    assert result["recovered"]["rate_limited"] is False
    assert result["recovered"]["scopes"][0]["last_success_at"] == "2026-09-22T18:00:00.000Z"
    assert result["recovered"]["scopes"][1]["last_success_at"] is None


def test_cooldown_is_rechecked_before_an_already_queued_navigation():
    result = probe("""
      let permitted;
      deps.runScope = async (_scope, _mode, admitted) => {
        saved.companyFinancialRefresh.rate_limit_until = '2026-09-22T06:00:00.000Z';
        permitted = await admitted();
        return {status:'cancelled'};
      };
      await api.run(true);
      return {permitted,status:await api.status()};
    """)
    assert result["permitted"] is False
    assert result["status"]["rate_limited"] is True
    assert all(scope["last_attempt_at"] is None for scope in result["status"]["scopes"])


def test_capturing_an_already_loaded_page_does_not_clear_acquisition_cooldown():
    result = probe("""
      let attempted = 0;
      deps.runScope = async () => {
        attempted++;
        return {status:'error',error_code:'sa_company_rate_limited'};
      };
      await api.run(false);
      const before = await api.status();
      await api.noteSuccess({ticker:'AMD',statement:'income_statement',view:'annual'},
        {currency:'USD',observation_id:'b'.repeat(64)});
      await api.run(true);
      return {before,after:await api.status(),attempted};
    """)
    assert result["attempted"] == 1
    assert result["after"]["rate_limit_until"] == result["before"]["rate_limit_until"]
    assert result["after"]["scopes"][0]["observation_id"] == "b" * 64


def test_rate_backoff_caps_at_seven_days_and_success_resets_it():
    result = probe("""
      await api.configure({...config,views:['annual']});
      deps.runScope = async () => ({status:'error',error_code:'sa_company_rate_limited'});
      const waits = [];
      for (let index=0; index<8; index++) {
        await api.run(true);
        const status = await api.status();
        waits.push((Date.parse(status.rate_limit_until)-clock)/3600000);
        clock = Date.parse(status.rate_limit_until);
      }
      deps.runScope = async () => ({status:'ok',currency:'USD',observation_id:'b'.repeat(64)});
      await api.run(true);
      deps.runScope = async () => ({status:'error',error_code:'sa_company_rate_limited'});
      await api.run(true);
      return {waits,afterSuccess:(Date.parse((await api.status()).rate_limit_until)-clock)/3600000};
    """)
    assert result["waits"] == [6, 12, 24, 48, 96, 168, 168, 168]
    assert result["afterSuccess"] == 6


@pytest.mark.parametrize("code", ["sa_company_rate_limited", "sa_company_human_verification_required"])
@pytest.mark.parametrize("phase", ["prepare", "capture"])
def test_restriction_is_persisted_before_tab_cleanup_finishes(code, phase):
    result = probe("""
      const code = CODE;
      const phase = PHASE;
      let cleanupStarted, release;
      const cleanup = new Promise(resolve => { cleanupStarted=resolve; });
      const gate = new Promise(resolve => { release=resolve; });
      chrome.tabs.create=async options=>({id:1,url:options.url});
      chrome.tabs.get=async()=>({id:1,url:'https://seekingalpha.com/symbol/AMD/income-statement'});
      safeRemoveTab=async()=>{};
      registerCollectorTab=async()=>{};
      unregisterCollectorTab=async()=>{};
      waitForTabLoad=async()=>{};
      sleep=async()=>{cleanupStarted();await gate;};
      sendNativeMessage2=async()=>({status:'ok',dataset:'financials'});
      chrome.scripting.executeScript=async()=>[{result:phase==='prepare'
        ? {status:'error',error_code:code} : {status:'ok'}}];
      captureCompanyData=async()=>({status:'error',error_code:code});
      deps.runScope=(scope,_mode,admitted,observeFailure)=>refreshCompanyFinancialScope(
        scope,SAExtensionDiagnostics.createCollector(),admitted,observeFailure);
      const pending=api.run(true);
      await cleanup;
      const during=await api.status();
      let extraAttempts=0;
      deps.runScope=async()=>{extraAttempts++;return {status:'ok',currency:'USD',observation_id:'b'.repeat(64)};};
      const restarted=SACompanyRefresh.create(deps);
      await restarted.configure({...config,tickers:['AAPL']});
      await restarted.run(false);
      release();await pending;
      return {during,extraAttempts,state:saved.companyFinancialRefresh};
    """.replace("CODE", json.dumps(code)).replace("PHASE", json.dumps(phase)))
    assert result["extraAttempts"] == 0
    assert result["during"]["scopes"][0]["last_error"] == code
    assert result["state"]["records"]["AMD/income_statement/annual"]["failures"] == 1
    if code == "sa_company_rate_limited":
        assert result["during"]["rate_limited"] is True
        assert result["state"]["rate_limit_failures"] == 1
    else:
        assert result["during"]["paused_reason"] == code


def test_duplicate_triggers_join_and_disabling_queued_work_prevents_navigation():
    result = probe("""
      let release;
      let entered;
      const queued = new Promise(resolve => { entered = resolve; });
      const gate = new Promise(resolve => { release = resolve; });
      deps.runScope = async (_scope, _mode, admitted) => {
        entered();
        await gate;
        return {status:await admitted() ? 'ok' : 'cancelled'};
      };
      const first = api.run(false);
      const second = api.run(false);
      const joined = first === second;
      await queued;
      await api.configure({...config,enabled:false});
      release();
      await first;
      return {joined,status:await api.status()};
    """)
    assert result["joined"] is True
    assert all(scope["last_success_at"] is None for scope in result["status"]["scopes"])


def test_scheduled_capture_rejects_wrong_view_before_writing():
    result = _run_background_probe("""
      const url = 'https://seekingalpha.com/symbol/AMD/income-statement';
      let writes = 0;
      chrome.tabs.get = async () => ({url});
      chrome.scripting.executeScript = async () => [{result:{status:'ok',capture:{
        ticker:'AMD',controls:{period:'Annual'},source_url:url
      }}}];
      sendNativeMessage2 = async request => {
        if (request.action === 'get_company_capture_admission') return {status:'ok',dataset:'financials'};
        writes++;
        return {status:'ok'};
      };
      const result = await captureCompanyData({id:1,url}, SAExtensionDiagnostics.createCollector(),
        {ticker:'AMD',statement:'income_statement',view:'quarterly'});
      return {result,writes};
    """)
    assert result["writes"] == 0
    assert result["result"]["error_code"] == "sa_company_scope_mismatch"


def test_disabled_provider_is_rejected_before_a_scheduled_tab_is_opened():
    result = _run_background_probe("""
      let opened = 0;
      chrome.tabs.create = async () => { opened++; return {id:1}; };
      sendNativeMessage2 = async () => ({status:'error',error_code:'data_source_not_selected'});
      const result = await refreshCompanyFinancialScope(
        {ticker:'AMD',statement:'income_statement',view:'annual'}, SAExtensionDiagnostics.createCollector(), async () => true);
      return {opened,result};
    """)
    assert result["opened"] == 0
    assert result["result"]["error_code"] == "data_source_not_selected"


def test_manual_capture_while_waiting_in_queue_prevents_an_automatic_repurchase():
    result = probe("""
      let admittedAfterCapture;
      deps.runScope = async (scope, mode, admitted) => {
        clock += 1000;
        await api.noteSuccess(scope, {observation_id:'b'.repeat(64),currency:'USD'});
        admittedAfterCapture = await admitted();
        return {status:'cancelled'};
      };
      const result = await api.run(false);
      return {admittedAfterCapture,result};
    """)
    assert result["admittedAfterCapture"] is False
    assert result["result"]["running"] is False


def test_alarm_is_recoverable_if_browser_worker_dies_during_capture():
    result = probe("return {alarms};")
    assert result["alarms"][-1]["periodInMinutes"] >= 1
    assert result["alarms"][-1]["when"] == 1790035260000  # 2026-09-22 00:01 UTC


def test_current_page_capture_with_another_currency_does_not_freshen_usd_scope():
    result = probe("""
      await api.noteSuccess({ticker:'AMD',statement:'income_statement',view:'annual'},
        {observation_id:'b'.repeat(64),currency:'EUR'});
      return await api.status();
    """)
    assert result["scopes"][0]["last_success_at"] is None


def test_popup_saves_selected_tickers_views_and_interval_without_starting_refresh():
    result = _run("configure_company_refresh")
    messages = [message for message in result["sent"] if message["action"] == "configure_company_refresh"]
    assert len(messages) == 1
    assert messages[0]["config"] == {
        "enabled": True, "tickers": ["AMD", "AAPL"], "interval_days": 14,
        "statements": ["income_statement"], "views": ["annual", "quarterly"],
    }
    assert not any(message["action"] == "run_company_refresh" for message in result["sent"])


def test_popup_shows_failed_scope_without_claiming_the_previous_capture_is_new():
    result = _run(companyRefresh={
        "status": "ok", "config": {"enabled": True, "tickers": ["AMD"], "interval_days": 7,
                                    "statements": ["income_statement"], "views": ["annual"]},
        "paused_reason": "sa_company_human_verification_required", "running": False,
        "scopes": [{"ticker": "AMD", "statement": "income_statement", "view": "annual",
                    "last_success_at": "2026-09-01T00:00:00Z", "next_due_at": "2026-09-08T00:00:00Z",
                    "last_error": "sa_company_human_verification_required"}],
    })
    assert "Paused" in result["companyRefreshStatus"]
    assert "2026-09-01" in result["companyRefreshStatus"]
    assert "human_verification" in result["companyRefreshStatus"]


def test_native_host_failure_stops_before_navigation_and_is_not_a_dom_failure():
    result = _run_background_probe("""
      let navigations = 0;
      chrome.tabs.create = async () => { navigations += 1; throw new Error('must not navigate'); };
      chrome.runtime.sendNativeMessage = (_host, _message, callback) => {
        chrome.runtime.lastError = {message:'An unexpected error occurred'};
        callback();
        chrome.runtime.lastError = null;
      };
      const result = await refreshCompanyFinancialScope(
        {ticker:'AMD', statement:'income_statement', view:'annual'},
        SAExtensionDiagnostics.createCollector(), async () => true);
      return {result, navigations};
    """)
    assert result["navigations"] == 0
    assert result["result"]["error_code"] == "sa_company_native_host_unavailable"


def test_popup_prominently_reports_a_failed_local_app_connection():
    result = _run(companyRefresh={
        "status": "ok", "config": {"enabled": False, "tickers": ["AMD"], "interval_days": 7,
                                    "statements": ["income_statement"], "views": ["annual"]},
        "paused_reason": None, "running": False,
        "scopes": [{"ticker": "AMD", "statement": "income_statement", "view": "annual",
                    "last_success_at": None, "next_due_at": "2026-09-23T00:00:00Z",
                    "last_error": "sa_company_native_host_unavailable"}],
    })
    assert result["companyRefreshStatus"].startswith("Local app connection unavailable")
    assert "sa_company_native_host_unavailable" in result["companyRefreshStatus"]


def test_popup_explains_shared_rate_cooldown_deadline():
    result = _run(companyRefresh={
        "status": "ok", "config": {"enabled": True, "tickers": ["AMD"], "interval_days": 7,
                                    "statements": ["income_statement"], "views": ["annual"]},
        "paused_reason": None, "running": False, "rate_limited": True,
        "rate_limit_until": "2026-09-22T06:00:00Z", "scopes": [],
    })
    assert "2026-09-22T06:00:00Z" in result["companyRefreshStatus"]
    assert "cooldown" in result["companyRefreshStatus"].lower()


@pytest.mark.parametrize("scenario,expected", [
    ("loaded", "ok"), ("old_table", "sa_company_dom_not_ready"),
    ("old_currency", "sa_company_dom_not_ready"), ("old_view", "sa_company_dom_not_ready"),
    ("challenge", "sa_company_human_verification_required"),
    ("login", "sa_company_login_required"),
    ("rate_title", "sa_company_rate_limited"),
    ("rate_heading", "sa_company_rate_limited"),
    ("multiline_rate", "sa_company_rate_limited"),
    ("rate_and_challenge_title", "sa_company_human_verification_required"),
    ("rate_and_challenge_frame", "sa_company_human_verification_required"),
])
def test_prepare_waits_for_the_requested_period_table_not_just_the_dropdown(scenario, expected):
    source = _run_background_probe("return prepareCompanyFinancialView.toString();")
    script = r"""
      const {JSDOM} = require('jsdom');
      const scenario = process.argv[2];
      const url = scenario === 'login' ? 'https://seekingalpha.com/login' : 'https://seekingalpha.com/symbol/AMD/income-statement';
      const dom = new JSDOM(`<html><head><title>${scenario === 'challenge' ? 'Verify you are human' : 'AMD financials'}</title></head>
      <body><main><button role="combobox" aria-labelledby="financials-filter-period">Annual</button>
      <button role="combobox" aria-labelledby="financials-filter-view">Absolute</button>
      <button role="combobox" aria-labelledby="financials-filter-currency">United States Dollar (USD)</button>
      <table data-test-id="table"><thead><tr><th>Dec 2025</th></tr></thead><tbody><tr><td>100</td></tr></tbody></table></main></body></html>`,
      {url,runScripts:'outside-only'});
      const w = dom.window;
      if (scenario === 'rate_title') w.document.title='429 Too Many Requests';
      if (scenario === 'rate_heading') {
        const h = w.document.createElement('h1'); h.textContent='Too many requests';
        w.document.querySelector('main').prepend(h);
      }
      if (scenario === 'multiline_rate') {
        const h = w.document.createElement('h1'); h.innerHTML='Too many<br>\nrequests';
        w.document.querySelector('main').prepend(h);
      }
      if (scenario === 'rate_and_challenge_title') {
        w.document.title='Verify you are human';
        w.document.querySelector('main').insertAdjacentHTML('afterbegin','<h1>Too many requests</h1>');
      }
      if (scenario === 'rate_and_challenge_frame') {
        w.document.title='429 Too Many Requests';
        w.document.body.insertAdjacentHTML('beforeend','<iframe title="Human verification challenge"></iframe>');
      }
      let clock = 0;
      w.Date.now = () => clock;
      w.setTimeout = callback => { clock += 1000; queueMicrotask(callback); };
      const period = w.document.querySelector('[aria-labelledby="financials-filter-period"]');
      if (scenario === 'old_currency' || scenario === 'old_view') {
        period.textContent='Quarterly';
        const name = scenario === 'old_currency' ? 'currency' : 'view';
        const box = w.document.querySelector('[aria-labelledby="financials-filter-' + name + '"]');
        const desired = box.textContent;
        box.textContent = name === 'currency' ? 'Euro (EUR)' : 'Growth';
        box.onclick = () => {
          const list = w.document.createElement('div'); list.setAttribute('role','listbox');
          const option = w.document.createElement('div'); option.setAttribute('role','option'); option.textContent=desired;
          option.onclick = () => { box.textContent=desired; list.remove(); };
          list.appendChild(option); w.document.body.appendChild(list);
        };
      }
      period.onclick = () => {
        const list = w.document.createElement('div'); list.setAttribute('role','listbox');
        const option = w.document.createElement('div'); option.setAttribute('role','option'); option.textContent='Quarterly';
        option.onclick = () => {
          period.textContent='Quarterly'; list.remove();
          if (scenario === 'loaded') {
            w.document.querySelector('thead th').textContent='Jun 2026';
            w.document.querySelector('tbody td').textContent='30';
          }
        };
        list.appendChild(option); w.document.body.appendChild(list);
      };
      w.eval('(' + process.argv[1] + ')')('quarterly','/symbol/AMD/income-statement').then(result => {
        process.stdout.write(JSON.stringify(result)); w.close();
      });
    """
    completed = subprocess.run(["node", "-e", script, source, scenario], cwd=ROOT,
                               capture_output=True, text=True, check=True)
    result = json.loads(completed.stdout)
    assert result.get("error_code", result["status"]) == expected


def test_disabling_during_native_admission_never_opens_a_tab():
    result = _run_background_probe("""
      let enabled = true;
      let opened = 0;
      chrome.tabs.create = async () => { opened++; return {id:1}; };
      chrome.tabs.remove = async () => {};
      waitForTabLoad = async () => {};
      sleep = async () => {};
      sendNativeMessage2 = async () => { enabled = false; return {status:'ok',dataset:'financials'}; };
      const result = await refreshCompanyFinancialScope({ticker:'AMD',statement:'income_statement',view:'annual'},
        SAExtensionDiagnostics.createCollector(), async () => enabled);
      return {opened,result};
    """)
    assert result["opened"] == 0
    assert result["result"]["status"] == "cancelled"


def test_increasing_interval_while_queued_prevents_an_unneeded_refresh():
    result = probe("""
      await api.run(true);
      clock += 8 * 86400000;
      let permitted;
      deps.runScope = async (scope, mode, admitted) => {
        await api.configure({...config,interval_days:30});
        permitted = await admitted();
        return {status:'cancelled'};
      };
      await api.run(false);
      return {permitted,status:await api.status()};
    """)
    assert result["permitted"] is False
    assert result["status"]["scopes"][0]["next_due_at"] == "2026-10-22T00:00:00.000Z"


def test_completion_notifies_an_already_open_popup_after_running_is_cleared():
    result = probe("""
      const observed = [];
      const set = storage.set;
      const get = storage.get;
      storage.get = async key => {
        await new Promise(resolve => setTimeout(resolve, 1));
        return get(key);
      };
      storage.set = async value => {
        await set(value);
        // Browser storage listeners do not block the write promise.
        setTimeout(async () => observed.push((await api.status()).running), 0);
      };
      deps.runScope = async () => {
        await new Promise(resolve => setTimeout(resolve, 5));
        return {status:'ok',currency:'USD',observation_id:'a'.repeat(64)};
      };
      deps.alarms.create = async () => { await new Promise(resolve => setTimeout(resolve, 5)); };
      await api.run(false);
      await new Promise(resolve => setTimeout(resolve, 10));
      return {observed};
    """)
    assert result["observed"][-1] is False


@pytest.mark.parametrize("delivery", ["immediate", "microtask"])
def test_mounted_popup_finishes_alarm_run_regardless_of_storage_event_order(delivery):
    script = r"""
    const fs=require('fs'), vm=require('vm'), {JSDOM}=require('jsdom');
    vm.runInThisContext(fs.readFileSync('extensions/sa_alpha_picks/company_refresh.js','utf8'));
    (async()=>{
      const saved={}, listeners=[];
      let release;
      const gate=new Promise(resolve=>release=resolve);
      const api=SACompanyRefresh.create({
        storage:{async get(k){return {[k]:structuredClone(saved[k])}},async set(v){
          Object.assign(saved,structuredClone(v));
          const publish=()=>listeners.forEach(fn=>fn({companyFinancialRefresh:{}},'local'));
          if(process.argv[1]==='immediate')publish();else queueMicrotask(publish);
        }},alarms:{async clear(){},async create(){}},
        runScope:async()=>{await gate;return {status:'ok',currency:'USD',observation_id:'a'.repeat(64)}}
      });
      await api.configure({enabled:true,tickers:['AMD'],statements:['income_statement'],views:['annual'],interval_days:7});
      const dom=new JSDOM(fs.readFileSync('extensions/sa_alpha_picks/popup.html','utf8'),{runScripts:'outside-only'});
      dom.window.chrome={runtime:{sendMessage(msg,cb){api.status().then(cb)}},storage:{onChanged:{addListener(fn){listeners.push(fn)}}}};
      dom.window.eval(fs.readFileSync('extensions/sa_alpha_picks/popup_company_refresh.js','utf8'));
      const run=api.run(false);
      await new Promise(resolve=>setImmediate(resolve));release();await run;
      await new Promise(resolve=>setImmediate(resolve));
      process.stdout.write(JSON.stringify({running:(await api.status()).running,
        disabled:dom.window.document.getElementById('companyRefreshNow').disabled}));
      dom.window.close();
    })();
    """
    result = subprocess.run(["node", "-e", script, delivery], cwd=ROOT, text=True, capture_output=True, check=True)
    assert json.loads(result.stdout) == {"running": False, "disabled": False}
