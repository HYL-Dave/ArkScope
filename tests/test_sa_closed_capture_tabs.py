"""Closed browser tabs must not leave routine collection permanently reserved."""

import json

import pytest

from tests.sa_acquisition_helpers import AUTHORITY
from tests.test_sa_extension_popup import _run_background_probe


@pytest.mark.parametrize("message", ["No tab with id: 3400.", "Invalid tab ID: 3400"])
def test_already_closed_tab_confirms_cleanup_in_both_browsers(message):
    result = _run_background_probe(AUTHORITY + "const message=" + json.dumps(message) + ";" + """
      saAcquisitionTask={ownedTabs:new Set([3400])};
      chrome.tabs.remove=async()=>{throw new Error(message);};
      const cleaned=await safeRemoveTab(3400);
      return {cleaned,owned:[...saAcquisitionTask.ownedTabs]};
    """)
    assert result == {"cleaned": True, "owned": []}


@pytest.mark.parametrize("message", ["Invalid tab ID: 99", "Browser connection lost", "Permission denied"])
def test_unconfirmed_removal_does_not_release_owned_tab(message):
    result = _run_background_probe(AUTHORITY + "const message=" + json.dumps(message) + ";" + """
      saAcquisitionTask={ownedTabs:new Set([3400])};
      chrome.tabs.remove=async()=>{throw new Error(message);};
      return {cleaned:await safeRemoveTab(3400),owned:[...saAcquisitionTask.ownedTabs]};
    """)
    assert result == {"cleaned": False, "owned": [3400]}


@pytest.mark.parametrize("message", ["No tab with id: 3400.", "Invalid tab ID: 3400"])
def test_closed_picks_tab_stops_without_waiting_or_navigating_and_releases_task(message):
    result = _run_background_probe(AUTHORITY + "const message=" + json.dumps(message) + ";" + """
      let elapsed=0,updates=0,scripts=0,finishes=0;
      Date.now=()=>elapsed;sleep=async ms=>{elapsed+=ms;};
      chrome.tabs.create=async()=>({id:3400});
      chrome.tabs.get=chrome.tabs.remove=async()=>{throw new Error(message);};
      chrome.tabs.update=async()=>{updates++;throw new Error(message);};
      chrome.scripting.executeScript=async()=>{scripts++;return [];};
      authorityReply=async operation=>{if(operation==='finish_task')finishes++;return null;};
      const value=await enqueueSaSyncJob({operation:'alpha_picks_sync',mode:'quick'},diagnostics=>doRefresh('quick',{diagnostics}));
      const pending=(await chrome.storage.local.get('saAcquisitionPending')).saAcquisitionPending;
      let nextRan=false;
      await enqueueSaSyncJob({operation:'market_news_sync',mode:'quick'},async()=>{nextRan=true;return {status:'ok'};});
      return {value,pending,elapsed,updates,scripts,finishes,nextRan};
    """)
    assert result["elapsed"] == 0
    assert result["updates"] == result["scripts"] == 0
    assert result["pending"] is None
    assert result["finishes"] == 2
    assert result["nextRan"] is True
    assert result["value"]["extension_run"]["phases"]["current_picks"] == {
        "state": "failed", "reason_code": "interrupted",
    }
    assert "acquisition" in result["value"]
    assert not result["value"].get("acquisition_uncertain")


@pytest.mark.parametrize("message", ["No tab with id: 3400.", "Invalid tab ID: 3400"])
def test_tab_closed_during_update_is_terminal_not_an_unknown_navigation(message):
    result = _run_background_probe(AUTHORITY + "const message=" + json.dumps(message) + ";" + """
      chrome.tabs.create=async()=>({id:3400});
      chrome.tabs.update=chrome.tabs.remove=async()=>{throw new Error(message);};
      const value=await enqueueSaSyncJob({operation:'alpha_picks_sync',mode:'quick'},async()=>{
        const tab=await managedSaTabs.create({url:'https://seekingalpha.com/alpha-picks/picks/current'});
        try {await managedSaTabs.update(tab.id,{url:'https://seekingalpha.com/alpha-picks/picks/closed'});}
        finally {await safeRemoveTab(tab.id);}
      });
      return {value,pending:(await chrome.storage.local.get('saAcquisitionPending')).saAcquisitionPending};
    """)
    assert result["pending"] is None
    assert "acquisition" in result["value"]
    assert not result["value"].get("acquisition_uncertain")
    assert result["value"]["acquisition_stop"]["error_code"] == "interrupted"
