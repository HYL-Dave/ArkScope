"""Shared browser queue and fail-closed native admission at the I/O boundary."""

from tests.test_sa_extension_popup import _run_background_probe
from tests.sa_acquisition_helpers import AUTHORITY
import pytest


LOAD = "importScripts('acquisition_queue.js', 'acquisition_client.js');\n"


@pytest.mark.parametrize("hidden, expected", [(False, "human_verification_required"), (True, "rate_limited")])
def test_visible_challenge_takes_precedence_over_rate_limit_title(hidden, expected):
    result = _run_background_probe(r"""
      globalThis.location={pathname:'/symbol/AMD'};
      const challenge={hidden:HIDDEN,parentElement:null,getAttribute:()=>null};
      globalThis.document={title:'Too many requests',querySelector:selector=>selector==='h1' ? null : challenge};
      globalThis.getComputedStyle=()=>({display:'block',visibility:'visible'});
      return readSaAccessMarkers();
    """.replace("HIDDEN", str(hidden).lower()))
    assert result == expected


def test_routine_fifo_runs_before_waiting_financial_work_and_coalesces():
    result = _run_background_probe(LOAD + r"""
      const queue = SAQueue.create({now: () => 1000});
      const order = [];
      let release, entered;
      const started = new Promise(resolve => { entered = resolve; });
      const active = queue.enqueue({key:'active', priority:'background', eligible:async()=>true,
        run:async()=>{entered(); await new Promise(resolve=>{release=resolve;}); order.push('active');}});
      await started;
      const enqueue = (key, priority) => queue.enqueue({key, priority, eligible:async()=>true, run:async()=>{order.push(key);}});
      const finance = enqueue('finance','background');
      const duplicate = enqueue('finance','background');
      const news = enqueue('news','routine');
      const picks = enqueue('picks','routine');
      const waiting = queue.status();
      release(); await Promise.all([active,finance,duplicate,news,picks]);
      return {order, waiting, idle:queue.status()};
    """)
    assert result["order"] == ["active", "news", "picks", "finance"]
    assert result["waiting"]["pending"] == {"routine": 2, "background": 1}
    assert result["idle"]["active"] is None


def test_new_routine_work_preempts_financial_eligibility_wait():
    result = _run_background_probe(LOAD + r"""
      const queue = SAQueue.create({now: () => 1000});
      let release, entered;
      const started = new Promise(resolve => {entered=resolve;});
      const gate = new Promise(resolve => {release=resolve;});
      const order=[];
      const finance=queue.enqueue({key:'financial',priority:'background',eligible:async()=>{
        entered(); await gate; return true;
      },run:async()=>order.push('financial')});
      await started;
      const news=queue.enqueue({key:'news',priority:'routine',eligible:async()=>true,run:async()=>order.push('news')});
      release(); await Promise.all([finance,news]); return order;
    """)
    assert result == ["news", "financial"]


CLIENT_SETUP = LOAD + r"""
const saved={}; const calls=[];
const storage={get:async key=>({[key]:saved[key]}),set:async values=>Object.assign(saved,JSON.parse(JSON.stringify(values)))};
let navReply={status:'ok',allowed:true,replayed:false,attempt_id:'d'.repeat(32)};
const control=async (operation, payload)=>{
  calls.push({operation,...payload});
  if(operation==='status') return {status:'ok',is_owner:true,generation:1,ledger_id:'a'.repeat(32),policy:{},paused_reason:null,capability_pauses:{}};
  if(operation==='begin_task') return {status:'ok',token:'b'.repeat(32),task_id:'c'.repeat(32),generation:1};
  if(operation==='admit_navigation') return navReply;
  if(operation==='finish_task') return {status:'ok',acquisition:{task_id:'c'.repeat(32)}};
  return {status:'ok'};
};
const client=SAAcquisition.create({control,storage,now:()=>1000,uuid:()=>crypto.randomUUID()});
const descriptor={operation:'market_news_sync',mode:'quick',trigger:'manual',intent_revision:0,build:'test'};
"""


def test_navigation_debit_is_before_browser_io_and_receipt_is_frozen():
    result = _run_background_probe(CLIENT_SETUP + r"""
      let called=0, durable=false;
      const result=await client.runTask(descriptor,async task=>{
        await task.navigate({id:'page',kind:'create',destinationClass:'news'},async()=>{
          durable=!!saved.saAcquisitionPending.navigation;
          calls.push({operation:'browser'}); called++; return {};
        });
        return {status:'ok'};
      });
      return {result,called,durable,calls,pending:saved.saAcquisitionPending};
    """)
    assert result["called"] == 1 and result["durable"] is True
    operations = [item["operation"] for item in result["calls"]]
    assert operations.index("admit_navigation") < operations.index("browser") < operations.index("finish_task")
    assert result["result"]["acquisition"]["task_id"] == "c" * 32
    assert result["pending"] is None


def test_replayed_or_missing_native_reply_never_navigates_or_releases_reservation():
    for reply in ("{status:'ok',allowed:false,replayed:true,attempt_id:'d'.repeat(32)}", "null"):
        result = _run_background_probe(CLIENT_SETUP + f"navReply={reply};" + r"""
          let pages=0;
          const result=await client.runTask(descriptor,async task=>{
            await task.navigate({id:'page',kind:'create',destinationClass:'news'},async()=>{pages++;return {};});
          });
          return {result,pages,calls,pending:saved.saAcquisitionPending};
        """)
        assert result["pages"] == 0
        assert result["pending"] is not None
        assert not any(c["operation"] == "finish_task" for c in result["calls"])


def test_login_observation_is_persisted_and_stops_the_next_navigation():
    result = _run_background_probe(CLIENT_SETUP + r"""
      let pages=0;
      const result=await client.runTask(descriptor,async task=>{
        await task.navigate({id:'one',kind:'create',destinationClass:'news'},async()=>{pages++;return {};});
        await task.observeRestriction('login_required');
        await task.navigate({id:'two',kind:'update',destinationClass:'news'},async()=>{pages++;return {};});
      });
      return {result,pages,calls,restriction:saved.saAcquisitionRestriction};
    """)
    assert result["pages"] == 1
    assert result["restriction"]["reason"] == "login_required"
    operations = [c["operation"] for c in result["calls"]]
    assert operations.index("observe_restriction") < operations.index("finish_task")


def test_pending_crashed_work_does_not_silently_resume():
    result = _run_background_probe(CLIENT_SETUP + r"""
      saved.saAcquisitionPending={request_id:'lost'};
      let called=0;
      const result=await client.runTask(descriptor,async()=>{called++;return {};});
      return {result,called,calls};
    """)
    assert result["called"] == 0
    assert result["result"]["reason"] == "collector_unavailable"
    assert not any(c["operation"] == "begin_task" for c in result["calls"])


def test_alpha_picks_login_failure_is_saved_before_cleanup_and_no_second_page():
    result = _run_background_probe(r"""
      const events=[];
      chrome.alarms.clear=async()=>{};
      saAcquisitionTask={stop:null,ownedTabs:new Set(),navigate:async(_,fn)=>fn(),
        observeRestriction:async reason=>{events.push(reason);saAcquisitionTask.stop={reason:'site_paused',error_code:reason,status:'error'};}};
      cleanupCollectorTabs=async()=>{}; registerCollectorTab=async()=>{}; unregisterCollectorTab=async()=>{};
      safeRemoveTab=async()=>{events.push('cleanup');return true;};
      chrome.tabs.create=async opts=>{events.push(new URL(opts.url).pathname);return {id:8};};
      chrome.tabs.update=async(_,opts)=>{events.push(new URL(opts.url).pathname);return {id:8};};
      waitForAlphaPicksTableReady=async()=>({ok:false,reason_code:'login_required',error:'Session expired'});
      sendToNativeHost=async()=>({status:'error'}); saveRefreshState=async()=>{};
      await doRefresh('quick'); return events;
    """)
    assert result == ["/alpha-picks/picks/current", "login_required", "cleanup"]


def test_login_pause_survives_alarm_repair_without_disabling_user_intent():
    result = _run_background_probe(r"""
      await chrome.storage.local.set({alphaPicksAutoSyncEnabled:true,marketNewsAutoSyncEnabled:true,
        saAcquisitionRestriction:{reason:'login_required',capability:'financials'}});
      const created=[];
      chrome.alarms.clear=async()=>{};
      chrome.alarms.create=async name=>created.push(name);
      await syncAllAutoSyncAlarms();
      return {created,intent:await chrome.storage.local.get('alphaPicksAutoSyncEnabled')};
    """)
    assert result["created"] == []
    assert result["intent"]["alphaPicksAutoSyncEnabled"] is True


def test_partial_news_failure_is_not_hidden_by_budget_deferral():
    result = _run_background_probe(r"""
      return attachExtensionRunProtocol('market_news_sync','quick',{
        status:'ok',detail_failed:1,detail_failures:[{news_id:'123',reason_code:'parser_empty'}],
        completed_phases:['list_navigation','list_scrape','metadata_save','capture_readback'],
        acquisition_stop:{status:'deferred',reason:'capacity_exhausted'},
      }).extension_run;
    """)
    assert result["derived_outcome"] == "degraded"
    assert result["item_outcomes"][0]["news_id"] == "123"


def test_news_budget_exhaustion_preserves_saved_body_and_pending_ids():
    result = _run_background_probe(AUTHORITY + r"""
      const pages=[],bodies=[]; let debits=0;
      authorityReply=async operation=>operation==='admit_navigation' && ++debits>2
        ? {status:'deferred',reason:'capacity_exhausted'} : null;
      cleanupCollectorTabs=async()=>{}; registerCollectorTab=async()=>{}; unregisterCollectorTab=async()=>{};
      chrome.tabs.create=async opts=>{pages.push(opts.url);return {id:8};};
      chrome.tabs.update=async(_id,opts)=>{if(opts.url)pages.push(opts.url);return {id:8};};
      chrome.tabs.remove=async()=>{};
      waitForMarketNewsPageLoad=async()=>{};waitForTabLoad=async()=>{};
      waitForMarketNewsReady=async()=>({ok:true});sleep=async()=>{};
      installMarketNewsPageGuards=async()=>{};getMarketNewsRecentIds=async()=>[];
      scrollMarketNews=async()=>{};injectMarketNewsScraper=async()=>[];
      fetchMarketNewsDetailWithRetry=async(_id,item)=>{bodies.push(item.news_id);return {ok:true};};
      sendNativeMessage2=async()=>({status:'ok',need_detail:[{news_id:'123',url:'https://seekingalpha.com/news/123'},
        {news_id:'124',url:'https://seekingalpha.com/news/124'}]});
      const value=await enqueueSaSyncJob({operation:'market_news_sync',mode:'quick'},()=>doMarketNewsRefresh('quick'));
      return {value,pages,bodies};
    """)
    assert len(result["pages"]) == 2
    assert result["bodies"] == ["123"]
    assert result["value"]["detail_fetched"] == 1
    assert result["value"]["pending_news_ids"] == ["124"]
    assert result["value"]["extension_run"]["derived_outcome"] == "deferred"
    assert "acquisition" in result["value"]


def test_unadmitted_current_page_never_injects_a_scraper():
    result = _run_background_probe(r"""
      let scripts=0;
      chrome.scripting.executeScript=async()=>{scripts++;return [{result:{}}];};
      sendNativeMessage2=async()=>({status:'ok',dataset:'financials'});
      let stopped;
      try {await captureCompanyData({id:8,url:'https://seekingalpha.com/symbol/AMD/income-statement'},SAExtensionDiagnostics.createCollector());}
      catch(error) {stopped=error.name;}
      return {scripts,stopped};
    """)
    assert result == {"scripts": 0, "stopped": "SAAcquisitionStop"}
