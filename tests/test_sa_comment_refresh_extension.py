"""Per-article budgets and partial receipts through the real extension flow."""

import pytest

from tests.test_sa_extension_reconciliation_flow import _DETAIL_FLOW_SETUP, _run_background


@pytest.mark.parametrize("include_body", [False, True])
@pytest.mark.parametrize("allowed", [False, True])
def test_scope_is_read_again_immediately_before_traversal(include_body, allowed):
    result = _run_background(r"""
      let scrolled=0,scraped=0,bodies=0,closed=0,scopeReads=0;
      beginArticleCapture=async()=>({assert:async()=>{},close:async()=>{closed++;}});
      settleArticleBeforeScroll=async()=>{};
      injectDetailScraper=async()=>{bodies++;return {body_markdown:'body'};};
      injectCommentsScraper=async()=>{scraped++;return {comments:[]};};
      scrollToComments=async()=>{scrolled++;return {mode:'quick',stop_reason:'stable_bottom'};};
      sendNativeMessage2=async message=>{
        if(message.action==='get_article_acquisition_eligibility'){
          scopeReads++;return {status:'ok',allowed:ALLOWED,reason_code:ALLOWED?null:'sa_article_former_out_of_scope'};
        }
        throw Error('unexpected native mutation');
      };
      const captured=await captureArticle(1,{article_id:'1001',comments_allowed:!ALLOWED},'quick',INCLUDE_BODY);
      return {captured,scrolled,scraped,bodies,closed,scopeReads};
    """.replace("ALLOWED", str(allowed).lower()).replace("INCLUDE_BODY", str(include_body).lower()), real_scope=True)
    assert result["scopeReads"] == 1
    assert result["scrolled"] == int(allowed)
    assert result["scraped"] == 2 * int(allowed)
    assert result["bodies"] == int(include_body)
    assert result["closed"] == 1
    assert bool(result["captured"]["scroll"].get("scope_skipped")) is not allowed


@pytest.mark.parametrize("available", [False, True])
def test_comments_only_race_stops_before_navigation_without_false_pending(available):
    result = _run_background(_DETAIL_FLOW_SETUP + r"""
      let navigations=0,commentWrites=0;
      managedSaTabs.update=async(_tab,options)=>{if(options.url.includes('/article/'))navigations++;};
      sendNativeMessage2=async message=>{
        if(message.action==='save_articles_meta')return {status:'ok',saved:1,need_content:[],
          need_comments:[{article_id:'1001',url:'https://seekingalpha.com/article/1001-old',comments_allowed:true}],
          reconciliation:{status:'ok',enrichment:[]}};
        if(message.action==='get_article_acquisition_eligibility')return AVAILABLE
          ? {status:'ok',allowed:false,reason_code:'sa_article_former_out_of_scope'}
          : {status:'deferred',allowed:false,error_code:'sa_article_scope_unavailable'};
        if(message.action==='save_comments_only')commentWrites++;
        return {status:'ok'};
      };
      const details=await doDetailFetch(1,[],'quick');
      const run=attachExtensionRunProtocol('alpha_picks_sync','quick',{current:{status:'ok'},closed:{status:'ok'},details,
        acquisition_stop:details.acquisition_stop,completed_phases:['current_picks','closed_picks']});
      return {navigations,commentWrites,details,run:run.extension_run};
    """.replace("AVAILABLE", str(available).lower()), real_scope=True)
    assert result["navigations"] == result["commentWrites"] == 0
    assert result["details"]["failed"] == 0
    assert not result["details"].get("comment_progress", {}).get("pending_articles")
    if available:
        assert result["details"]["comment_scope_skipped"] == 1
        assert result["run"]["derived_outcome"] == "complete"
    else:
        assert result["run"]["derived_outcome"] == "deferred"
        from src.sa.extension_run_protocol import derive_run_result
        wire = {key:value for key,value in result["run"].items() if key not in {"job_name","db_status"}}
        assert derive_run_result(wire) == result["run"]


def test_former_first_detail_keeps_body_without_a_comment_receipt():
    result = _run_background(_DETAIL_FLOW_SETUP + r"""
      let saved=null,scrolls=0;
      scrollToComments=async()=>{scrolls++;return {};};
      sendNativeMessage2=async message=>{
        if(message.action==='save_articles_meta')return {status:'ok',saved:1,need_comments:[],
          need_content:[{article_id:'1001',url:'https://seekingalpha.com/article/1001-old'}],reconciliation:{status:'ok',enrichment:[]}};
        if(message.action==='get_article_acquisition_eligibility')return {status:'ok',allowed:message.operation==='body',reason_code:'sa_article_former_out_of_scope'};
        if(message.action==='save_article_content') {saved=message;return {status:'ok',ok:true,body_saved:true,comments_scope_skipped:true};}
        return {status:'ok'};
      };
      const details=await doDetailFetch(1,[],'quick');
      return {details,saved,scrolls};
    """, real_scope=True)
    assert result["details"]["fetched"] == 1
    assert result["details"]["failed"] == result["scrolls"] == 0
    assert result["saved"]["comments_scope_skipped"] is True
    assert result["saved"]["comments"] == []
    assert not result["details"].get("comment_progress")


@pytest.mark.parametrize("available", [False, True])
def test_body_exclusion_after_queueing_stops_before_navigation(available):
    result = _run_background(_DETAIL_FLOW_SETUP + r"""
      let navigations=0,writes=0;
      managedSaTabs.update=async(_tab,options)=>{if(options.url.includes('/article/'))navigations++;};
      sendNativeMessage2=async message=>{
        if(message.action==='save_articles_meta')return {status:'ok',saved:1,need_comments:[],
          need_content:[{article_id:'1001',url:'https://seekingalpha.com/article/1001-retired'}],reconciliation:{status:'ok',enrichment:[]}};
        if(message.action==='get_article_acquisition_eligibility')return AVAILABLE
          ? {status:'ok',allowed:false,reason_code:'sa_article_permanently_excluded'}
          : {status:'deferred',allowed:false,error_code:'sa_article_scope_unavailable'};
        if(message.action==='save_article_content')writes++;
        return {status:'ok'};
      };
      const details=await doDetailFetch(1,[],'quick');
      return {details,navigations,writes};
    """.replace("AVAILABLE", str(available).lower()), real_scope=True)
    assert result["navigations"] == result["writes"] == 0
    assert result["details"]["failed"] == 0
    if available:
        assert result["details"]["body_scope_skipped"] == 1
    else:
        assert result["details"]["acquisition_stop"]["reason"] == "article_scope_unavailable"


def test_quick_fetch_respects_global_order_and_does_not_silently_upgrade():
    result = _run_background(_DETAIL_FLOW_SETUP + r"""
      const visits=[],rounds=[];
      scrollToLoadAll=async(_tab,n)=>rounds.push(n);
      captureArticle=async(_tab,item,_mode,includeBody)=>{
        visits.push({id:item.article_id,body:includeBody});
        return {detail:{body:'Analysis'},comments:[],scroll:{mode:'quick'}};
      };
      sendNativeMessage2=async message=>{
        if(message.action==='save_articles_meta')return {status:'ok',saved:6,auto_upgrade:true,
          need_content:[{article_id:'old',url:'https://seekingalpha.com/article/1-old'}],
          need_comments:[{article_id:'new',url:'https://seekingalpha.com/article/2-new'}],
          reconciliation:{enrichment:[]},quick_workload:{navigation_budget:4,selected_count:2,
            eligible_count:6,deferred_count:4,backlog_scope:'eligible_candidates',selected_article_ids:['new','old']}};
        return {status:'ok',ok:true,comment_scan_usable:true};
      };
      const result=await doDetailFetch(1,[],'quick');
      return {visits,rounds,result};
    """)
    assert result["visits"] == [{"id": "new", "body": False}, {"id": "old", "body": True}]
    assert result["rounds"] == [5]
    assert result["result"]["quick_workload"]["deferred_count"] == 4


@pytest.mark.parametrize("override,expected_mode,expected_stop,expected_count", [
    ("backfill", "backfill", "stable_bottom", 107),
    (None, "quick", "max_scrolls", 81),
])
def test_first_article_budget_can_reach_tail_without_lengthening_routine_scan(
    override, expected_mode, expected_stop, expected_count,
):
    import json

    result = _run_background(r"""
      let now=0;
      Date.now=()=>now;
      sleep=async ms=>{now+=ms;};
      beginArticleCapture=async()=>({assert:async()=>{},checkNavigation(){},close:async()=>{}});
      settleArticleBeforeScroll=async()=>{};
      chrome.scripting.executeScript=async()=>[{result:{
        comments:now>=48000?107:81,atBottom:now>=48000,clicked:false,loading:false,
      }}];
      injectCommentsScraper=async()=>({comments:[]});
      const result=await captureArticle(1,{article_id:'1',comment_scan_mode:OVERRIDE},'quick',false);
      return result.scroll;
    """.replace("OVERRIDE", json.dumps(override)))
    assert result["mode"] == expected_mode
    assert result["stop_reason"] == expected_stop
    assert result["comments_loaded"] == expected_count
    if override:
        assert 48000 <= result["elapsed_ms"] < 120000
    else:
        assert result["elapsed_ms"] == 10800


def test_first_capture_keeps_existing_deep_cap_and_reports_unreached_bottom():
    result = _run_background(r"""
      let now=0;const starts=[];
      Date.now=()=>now;
      sleep=async ms=>{now+=ms;};
      beginArticleCapture=async()=>({assert:async()=>{},checkNavigation(){},close:async()=>{}});
      settleArticleBeforeScroll=async()=>{};
      chrome.scripting.executeScript=async()=>{
        starts.push(now);
        return [{result:{comments:3,atBottom:false,clicked:false,loading:false,
          progress:{scroll_y_before:100,scroll_y_after:200,document_height:2000,viewport_height:100}}}];
      };
      injectCommentsScraper=async()=>({comments:[]});
      const captured=await captureArticle(1,{article_id:'1',comment_scan_mode:'backfill'},'quick',false);
      return {scroll:captured.scroll,starts};
    """)
    assert result["scroll"]["stop_reason"] == "timeout"
    assert 120000 <= result["scroll"]["elapsed_ms"] < 121600
    assert all(start < 120000 for start in result["starts"])
    assert result["scroll"]["last_observation"]["at_bottom"] is False
    assert result["scroll"]["last_observation"]["progress"]["document_height"] == 2000


@pytest.mark.parametrize("content", [False, True])
@pytest.mark.parametrize("pending", [False, True])
def test_actual_per_article_mode_is_saved_and_pending_is_not_reported_complete(content, pending):
    result = _run_background(_DETAIL_FLOW_SETUP + r"""
      const modes=[];
      scrollToComments=async(_tab,options)=>{
        modes.push(options.mode);
        return {mode:options.mode,stop_reason:PENDING?'timeout':'stable_bottom',stable_bottom_rounds:PENDING?0:5};
      };
      injectCommentsScraper=async()=>({comments:[{comment_id:'new',comment_text:'new reply'}]});
      sendNativeMessage2=async message=>{
        calls.push(message);
        if(message.action==='save_articles_meta') return {
          status:'ok',saved:1,
          need_content:CONTENT?[{article_id:'a1',url:'https://seekingalpha.com/article/1-a',comment_scan_mode:'backfill'}]:[],
          need_comments:CONTENT?[]:[{article_id:'a1',url:'https://seekingalpha.com/article/1-a',comment_scan_mode:'backfill'}],
          unresolved_symbols:[],reconciliation:{status:'ok',enrichment:[]},
        };
        if(message.action==='save_article_content'||message.action==='save_comments_only')
          return {status:'ok',ok:true,comment_scan_usable:true,comment_backfill_pending:PENDING,net_new_comments:1};
        return {status:'ok',unresolved_symbols:[],review_queue:{total:0,events:[]}};
      };
      const summary=await doDetailFetch(1,[],'quick');
      return {modes,summary,saves:calls.filter(m=>['save_article_content','save_comments_only'].includes(m.action))};
    """.replace("CONTENT", str(content).lower()).replace("PENDING", str(pending).lower()))
    assert result["modes"] == ["backfill"]
    assert len(result["saves"]) == 1
    assert result["saves"][0]["comment_scan_mode"] == "backfill"
    assert result["summary"]["failed"] == 0
    assert result["summary"]["net_new_comments"] == 1
    if pending:
        assert result["summary"]["comment_progress"] == {
            "pending_articles": 1, "net_new_comments": 1, "stop_reasons": ["timeout"],
        }
    if not content:
        assert result["summary"]["comments_refreshed"] == int(not pending)


def test_trace_records_each_round_progress_not_just_final_timeout():
    result = _run_background(r"""
      sleep=async()=>{};
      let round=0;
      chrome.scripting.executeScript=async()=>[{result:{
        comments:++round,atBottom:false,clicked:true,click_count:1,loading:false,
        progress:{scroll_y_before:round*100,scroll_y_after:round*100+100,document_height:4000,viewport_height:100},
        control_audit:{unresolved_candidates:0,omitted_count:0,items:[],clicked_indices:[0]},
      }}];
      return await scrollToComments(1,{mode:'quick',articleId:'1',trace:true});
    """)
    assert result["stop_reason"] == "max_scrolls"
    assert len(result["control_audits"]) == 12
    assert result["control_audits"][0]["comments"] == 1
    assert result["control_audits"][-1]["at_bottom"] is False
    assert result["control_audits"][-1]["progress"]["scroll_y_after"] == 1300


def test_explicit_manual_article_repair_uses_deep_budget_and_reports_pending():
    result = _run_background(_DETAIL_FLOW_SETUP + r"""
      cleanupCollectorTabs=registerCollectorTab=unregisterCollectorTab=safeRemoveTab=async()=>{};
      chrome.tabs.create=async()=>({id:1});
      const modes=[];
      scrollToComments=async(_tab,options)=>{
        modes.push(options.mode);
        return {mode:options.mode,stop_reason:'timeout',stable_bottom_rounds:0};
      };
      sendNativeMessage2=async message=>{
        calls.push(message);
        if(message.action==='save_article_content')
          return {ok:true,comment_scan_usable:true,comment_backfill_pending:true,net_new_comments:38};
        return {status:'ok',lineage_id:7};
      };
      const summary=await doManualFetch([{symbol:'TEST',role:'entry',event_anchor_date:'2026-07-15',
        url:'https://seekingalpha.com/alpha-picks/articles/6316639-test'}]);
      return {modes,summary,saves:calls.filter(m=>m.action==='save_article_content'),
        run:attachExtensionRunProtocol('alpha_picks_manual_fetch','manual',summary).extension_run};
    """)
    assert result["modes"] == ["backfill"]
    assert result["saves"][0]["comment_scan_mode"] == "backfill"
    assert len(result["saves"]) == 1
    assert result["summary"]["fetched"] == 1
    assert result["summary"]["failed"] == 0
    assert result["summary"]["net_new_comments"] == 38
    assert result["summary"]["comment_progress"] == {
        "pending_articles": 1, "net_new_comments": 38, "stop_reasons": ["timeout"],
    }
    assert result["run"]["derived_outcome"] == "deferred"
    assert result["run"]["phases"]["manual_fetch"] == {
        "state": "deferred", "reason_code": "comment_backfill_pending",
    }
