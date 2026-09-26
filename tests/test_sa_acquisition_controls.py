"""Operator intent and explicit ownership changes at the popup boundary."""

from tests.test_sa_extension_popup import _run_background_probe
from tests.sa_acquisition_helpers import AUTHORITY
import pytest


SETUP = AUTHORITY + """
const selection={enabled:false,target_mode:'watchlist',tickers:[],statements:['income_statement'],views:['annual'],
  interval_days:7,interval_days_by_view:{annual:7,quarterly:7},financial_gap_seconds:15};
const accepted={config:selection,expected_generation:1,confirm_schedules:true,confirm_activation:true,
  policy:{hour_limit:8,day_limit:20,hour_reserve:2,day_reserve:4}};
const actions=[];
const originalControl=companyCollectorControl;
companyCollectorControl=async(operation,message)=>{actions.push(operation);return originalControl(operation,message);};
chrome.alarms.create=async()=>{};
sendNativeMessage2=async request=>request.action==='get_company_watchlist'
  ? {status:'ok',tickers:['AAPL','AMD'],total_count:2,unsupported:[]} : {status:'ok'};
"""


def test_activation_requires_explicit_confirmation_and_matching_generation():
    result = _run_background_probe(SETUP + """
      const missing=await activateSaUpdates({...accepted,confirm_schedules:false});
      const stale=await activateSaUpdates({...accepted,expected_generation:0});
      return {missing,stale,actions};
    """)
    assert result["missing"]["status"] == result["stale"]["status"] == "error"
    assert "configure" not in result["actions"] and "select" not in result["actions"]


def test_failed_activation_keeps_intent_off_and_preserves_failure_stage():
    result = _run_background_probe(SETUP + """
      authorityReply=async operation=>operation==='configure' ? {status:'error',error_code:'collector_busy'} : null;
      const result=await activateSaUpdates({...accepted,config:{...selection,enabled:true}});
      return {result,settings:(await chrome.storage.local.get('companyFinancialRefresh')).companyFinancialRefresh};
    """)
    assert result["settings"]["config"]["enabled"] is False
    assert result["result"]["activation_step"] == "configure"
    assert result["result"]["error_code"] == "collector_busy"


def test_repeated_activation_of_current_owner_does_not_select_again():
    result = _run_background_probe(SETUP + """
      const one=await activateSaUpdates(accepted);
      const two=await activateSaUpdates(accepted);
      return {one,two,actions};
    """)
    assert result["one"]["status"] == result["two"]["status"] == "ok"
    assert "select" not in result["actions"]


def test_explicit_uncapped_activation_keeps_routine_intent_and_financial_schedule_off():
    result = _run_background_probe(SETUP + """
      await chrome.storage.local.set({alphaPicksAutoSyncEnabled:true,marketNewsAutoSyncEnabled:true});
      let configured;
      const control=companyCollectorControl;
      companyCollectorControl=async(operation,message)=>{
        if(operation==='configure')configured=message.policy;
        return control(operation,message);
      };
      const result=await activateSaUpdates({...accepted,policy:{hour_limit:null,day_limit:null,hour_reserve:0,day_reserve:0}});
      return {result,configured,saved:await chrome.storage.local.get(['alphaPicksAutoSyncEnabled','marketNewsAutoSyncEnabled','companyFinancialRefresh'])};
    """)
    assert result["result"]["status"] == "ok"
    assert result["configured"] == dict(hour_limit=None, day_limit=None, hour_reserve=0, day_reserve=0)
    assert result["saved"]["alphaPicksAutoSyncEnabled"] is True
    assert result["saved"]["marketNewsAutoSyncEnabled"] is True
    assert result["saved"]["companyFinancialRefresh"]["config"]["enabled"] is False


def test_explicit_browser_switch_selects_before_changing_owner_policy():
    result = _run_background_probe(SETUP + """
      let current={...admittedState,is_owner:false,owner:{browser:'chrome'},policy:accepted.policy};
      authorityReply=async operation=>{
        if(operation==='select') current={...current,is_owner:true,generation:2};
        if(operation==='configure' && !current.is_owner) return {status:'error',error_code:'sa_company_collector_other_browser'};
        return current;
      };
      const result=await activateSaUpdates(accepted);
      return {result,actions};
    """)
    assert result["result"]["status"] == "ok"
    assert result["actions"].index("select") < result["actions"].index("configure")


def test_status_badge_is_distinct_for_login_and_subscription_access():
    result = _run_background_probe("""
      const badge=[],titles=[];
      chrome.action={setBadgeText:async v=>badge.push(v.text),setBadgeBackgroundColor:async()=>{},setTitle:async v=>titles.push(v.title)};
      await syncAcquisitionBadge({paused_reason:'login_required'});
      await syncAcquisitionBadge({capability_pauses:{financials:'access_restricted'}});
      await syncAcquisitionBadge({paused_reason:null,capability_pauses:{}});
      return {badge,titles};
    """)
    assert result["badge"] == ["!", "!", ""]
    assert "sign in" in result["titles"][0] and "subscription" in result["titles"][1]


@pytest.mark.parametrize("failure", ["select", "persist", "enable", "generation_race"])
def test_partial_activation_failures_leave_all_three_intents_disabled(failure):
    result = _run_background_probe(SETUP + """
      await chrome.storage.local.set({alphaPicksAutoSyncEnabled:true,marketNewsAutoSyncEnabled:true});
      const failure=""" + repr(failure) + """;
      if(failure==='select') authorityReply=async operation=>operation==='status' ? {...admittedState,is_owner:false,policy:accepted.policy}
        : operation==='select' ? {status:'error',error_code:'collector_busy'} : null;
      if(failure==='generation_race') authorityReply=async operation=>operation==='configure' ? {status:'error',error_code:'sa_acquisition_generation_stale'} : null;
      if(failure==='persist') {
        const write=chrome.storage.local.set;
        chrome.storage.local.set=async value=>{if(value.saAcquisitionLedger)throw new Error('write_failed');return write(value);};
      }
      if(failure==='enable') {
        const configure=companyFinancialRefresh.configure;
        companyFinancialRefresh.configure=async value=>{if(value.enabled)throw new Error('alarm_failed');return configure(value);};
      }
      const result=await activateSaUpdates({...accepted,config:{...selection,enabled:true}});
      const saved=await chrome.storage.local.get(['companyFinancialRefresh','alphaPicksAutoSyncEnabled','marketNewsAutoSyncEnabled']);
      return {result,saved};
    """)
    assert result["result"]["status"] == "error"
    assert result["saved"]["companyFinancialRefresh"]["config"]["enabled"] is False
    assert result["saved"]["alphaPicksAutoSyncEnabled"] is False
    assert result["saved"]["marketNewsAutoSyncEnabled"] is False


@pytest.mark.parametrize("job,setter", [("alphaPicks", "setAlphaPicksAutoSyncEnabled"),
                                       ("marketNews", "setMarketNewsAutoSyncEnabled")])
def test_activation_does_not_restore_intent_changed_before_suspension(job, setter):
    result = _run_background_probe(SETUP + """
      await setAlphaPicksAutoSyncEnabled(true,30);
      await setMarketNewsAutoSyncEnabled(true,60);
      const read=chrome.storage.local.get;
      let intercepted=false;
      chrome.storage.local.get=async keys=>{
        const snapshot=await read(keys);
        if(!intercepted && Array.isArray(keys) && keys.includes('alphaPicksAutoSyncEnabled')
            && keys.includes('marketNewsAutoSyncEnabled') && keys.includes('alphaPicksAutoSyncIntervalMinutes')) {
          intercepted=true;
          await """ + setter + """(false,15);
        }
        return snapshot;
      };
      const activated=await activateSaUpdates(accepted);
      return {activated,intercepted,saved:await read(['""" + job + """AutoSyncEnabled','""" + job + """AutoSyncIntervalMinutes'])};
    """)
    assert result["intercepted"] is True
    assert result["activated"]["status"] == "ok"
    assert result["saved"][job + "AutoSyncEnabled"] is False
    assert str(result["saved"][job + "AutoSyncIntervalMinutes"]) == "15"
