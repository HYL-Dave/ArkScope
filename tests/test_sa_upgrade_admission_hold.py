"""Upgrade verification pauses admission without rewriting financial intent."""

import json

import pytest

from tests.test_sa_extension_reconciliation_flow import _run_background
from tests.test_sa_extension_popup import _run_background_probe
from tests.test_sa_auto_sync_admission import SETUP


@pytest.mark.parametrize("setter", ["setAlphaPicksAutoSyncEnabled", "setMarketNewsAutoSyncEnabled"])
def test_first_schedule_toggle_is_not_mistaken_for_an_existing_upgrade(setter):
    result = _run_background_probe(SETUP + f"""
      const result=await {setter}(true,30);
      return {{result,upgrade:await acquisitionUpgradeState()}};
    """)
    assert result["result"]["status"] == "ok"
    assert result["upgrade"] == {"version":1,"held":False}


@pytest.mark.parametrize("initial,held", [
    ({}, False),
    ({"alphaPicksAutoSyncEnabled":True}, True),
    ({"companyFinancialRefresh":{"pending_scopes":["AAPL/income_statement/annual"]}}, True),
    ({"saBodyV2Upgrade":{"version":1,"held":True}}, True),
    ({"saBodyV2Upgrade":{"version":1,"held":False},"marketNewsAutoSyncEnabled":True}, False),
    ({"saBodyV2Upgrade":{"version":99,"held":False}}, True),
])
def test_upgrade_hold_is_durable_and_fresh_installs_are_not_paused(initial, held):
    result = _run_background("saUpgradeCheck=null; var store=" + json.dumps(initial) + r""";
      chrome.storage.local.get=async()=>structuredClone(store);
      chrome.storage.local.set=async values=>Object.assign(store,values);
      const first=await acquisitionUpgradeHeld(); saUpgradeCheck=null;
      return {first,reloaded:await acquisitionUpgradeHeld(),store};
    """.replace("structuredClone(store)", "JSON.parse(JSON.stringify(store))"))
    assert result["first"] is result["reloaded"] is held
    assert result["store"] == {**initial,"saBodyV2Upgrade":{"version":1,"held":held}}


def test_held_upgrade_blocks_manual_start_and_alarm_repair_without_queue_mutation():
    result = _run_background(r"""
      saUpgradeCheck=null;
      var financial={config:{enabled:false},intent_revision:7,status_revision:9,pending_scopes:['original']};
      var store={companyFinancialRefresh:financial}, called=0;
      chrome.storage.local.get=async()=>JSON.parse(JSON.stringify(store));
      chrome.storage.local.set=async values=>Object.assign(store,values);
      const replies=[];
      for(const action of ['run_company_refresh','save_company_refresh','cancel_company_refresh','enable_sa_updates_here'])
        replies.push(await handleAcquisitionControl({action}));
      replies.push(await enqueueSaSyncJob({operation:'market_news_sync'},async()=>{called++;}));
      replies.push(await handleArticleBodyRecovery({action:'start_article_body_recovery'}));
      replies.push(await ensureAutoSyncAlarms());
      return {replies,called,financial:store.companyFinancialRefresh};
    """)
    assert result["called"] == 0
    assert all(reply["reason"] == "upgrade_verification_required" for reply in result["replies"])
    assert result["financial"] == {"config":{"enabled":False},"intent_revision":7,"status_revision":9,"pending_scopes":["original"]}


@pytest.mark.parametrize("state,pending,confirmed", [
    ({"status":"ok","is_owner":True}, None, False),
    ({"status":"ok","is_owner":True,"active":{"task_id":"uncertain"}}, None, True),
    ({"status":"ok","is_owner":True}, {"request_id":"uncertain"}, True),
])
def test_upgrade_release_requires_explicit_confirmation_and_idle(state, pending, confirmed):
    result = _run_background("saUpgradeCheck=null; var shared=" + json.dumps(state) + ";var local=" + json.dumps(pending) + r""";
      var store={saBodyV2Upgrade:{version:1,held:true},saAcquisitionPending:local};
      chrome.storage.local.get=async()=>store;
      chrome.storage.local.set=async values=>Object.assign(store,values);
      companyCollectorControl=async()=>shared;
      var reply=await releaseAcquisitionUpgrade({confirm_checked:CONFIRMED});
      return {reply,held:store.saBodyV2Upgrade.held};
    """.replace("CONFIRMED", json.dumps(confirmed)))
    assert result["reply"]["status"] == "error"
    assert result["held"] is True


@pytest.mark.parametrize("is_owner", [False, True])
def test_upgrade_release_never_changes_selection_or_bypasses_restrictions(is_owner):
    result = _run_background("var isOwner=" + json.dumps(is_owner) + r""";
      saUpgradeCheck=null;
      var store={saBodyV2Upgrade:{version:1,held:true}}, calls=[];
      var shared={status:'ok',is_owner:isOwner,owner:{client_id:'unchanged'},paused_reason:'login_required',rate_limited:true};
      chrome.storage.local.get=async()=>store;
      chrome.storage.local.set=async values=>Object.assign(store,values);
      companyCollectorControl=async operation=>{calls.push(operation);return shared;};
      syncAllAutoSyncAlarms=async()=>{};
      handleAcquisitionControl=async()=>({status:'ok'});
      var reply=await releaseAcquisitionUpgrade({confirm_checked:true});
      return {reply,calls,store,shared};
    """)
    assert result["reply"]["status"] == "ok"
    assert result["calls"] == ["status"]
    assert result["store"]["saBodyV2Upgrade"]["held"] is False
    assert result["shared"]["paused_reason"] == "login_required"
    assert result["shared"]["rate_limited"] is True
    assert result["shared"]["is_owner"] is is_owner
