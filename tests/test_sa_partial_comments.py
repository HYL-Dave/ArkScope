"""Saved comment progress is pending work, not a parser or persistence failure."""

from __future__ import annotations

import copy
import json
import subprocess

import pytest

from src.sa.extension_run_protocol import ProtocolError, derive_run_result
from tests.test_sa_extension_reconciliation_flow import _DETAIL_FLOW_SETUP, _run_background
from tests.test_sa_extension_run_protocol import JS_PROTOCOL, RUNNER


def _pending_payload(reason="comment_backfill_pending", stop="timeout"):
    return {
        "schema_version": 2,
        "operation": "alpha_picks_sync",
        "mode": "quick",
        "phases": {
            "current_picks": {"state": "complete", "reason_code": None},
            "closed_picks": {"state": "complete", "reason_code": None},
            "article_details": {"state": "deferred", "reason_code": reason},
            "reconciliation": {"state": "complete", "reason_code": None},
        },
        "item_outcomes": [],
        "comment_progress": {
            "pending_articles": 1,
            "net_new_comments": 38,
            "stop_reasons": [stop],
        },
    }


@pytest.mark.parametrize("content", [False, True])
@pytest.mark.parametrize("saved", [0, 38])
@pytest.mark.parametrize("stop,pending,controls,reason", [
    ("timeout", True, False, "comment_backfill_pending"),
    ("max_scrolls", True, False, "comment_backfill_pending"),
    ("controls_unresolved", False, True, "controls_unresolved"),
])
def test_saved_comments_are_deferred_with_progress_not_failed(content, saved, stop, pending, controls, reason):
    config = json.dumps(dict(content=content, saved=saved, stop=stop, pending=pending, controls=controls))
    result = _run_background(_DETAIL_FLOW_SETUP + "const cfg=" + config + r""";
      const diagnostics=SAExtensionDiagnostics.createCollector();
      scrollToComments=async()=>({mode:'backfill',stop_reason:cfg.stop,
        controls_unresolved:cfg.controls,stable_bottom_rounds:0});
      sendNativeMessage2=async message=>{
        calls.push(message);
        if(message.action==='save_articles_meta')return {status:'ok',saved:1,
          need_content:cfg.content?[{article_id:'a1',url:'https://seekingalpha.com/article/1-a'}]:[],
          need_comments:cfg.content?[]:[{article_id:'a1',url:'https://seekingalpha.com/article/1-a'}],
          reconciliation:{status:'ok',enrichment:[]}};
        if(['save_article_content','save_comments_only'].includes(message.action))
          return {status:'ok',ok:true,body_saved:true,comment_scan_usable:true,
            comment_backfill_pending:cfg.pending,net_new_comments:cfg.saved};
        return {status:'ok',review_queue:{total:0,events:[]}};
      };
      const details=await doDetailFetch(1,[],'quick',diagnostics);
      const run=attachExtensionRunProtocol('alpha_picks_sync','quick',{
        current:{status:'ok'},closed:{status:'ok'},details});
      return {details,run:run.extension_run,diagnostics:diagnostics.freeze(),
        save:calls.find(m=>['save_article_content','save_comments_only'].includes(m.action))};
    """)
    assert result["details"]["failed"] == 0
    assert result["details"]["fetched"] == int(content)
    assert result["details"]["comments_refreshed"] == 0
    assert result["details"]["net_new_comments"] == saved
    assert result["details"]["comment_progress"] == {
        "pending_articles": 1, "net_new_comments": saved, "stop_reasons": [stop],
    }
    assert result["run"]["phases"]["article_details"] == {"state": "deferred", "reason_code": reason}
    assert result["run"]["derived_outcome"] == "deferred"
    assert result["run"]["db_status"] == "deferred"
    assert result["run"]["healthy_anchor_eligible"] is False
    assert result["run"]["comment_progress"] == result["details"]["comment_progress"]
    assert result["diagnostics"]["entries"] == []
    assert result["save"]["comment_scan_stop_reason"] == stop
    assert result["save"]["comment_scan_mode"] == "backfill"
    wire = {key: value for key, value in result["run"].items() if key not in {"job_name", "db_status"}}
    assert derive_run_result(wire) == result["run"]


@pytest.mark.parametrize("content", [False, True])
@pytest.mark.parametrize("failure,reason", [("parse", "comment_scan_failed"), ("save", "detail_save_failed")])
def test_unusable_scan_and_native_write_failure_remain_failures(content, failure, reason):
    result = _run_background(_DETAIL_FLOW_SETUP + "const cfg=" + json.dumps(dict(content=content, failure=failure)) + r""";
      const diagnostics=SAExtensionDiagnostics.createCollector();
      scrollToComments=async()=>({mode:'backfill',stop_reason:'controls_unresolved',controls_unresolved:true});
      sendNativeMessage2=async message=>{
        if(message.action==='save_articles_meta')return {status:'ok',saved:1,
          need_content:cfg.content?[{article_id:'a1',url:'https://seekingalpha.com/article/1-a'}]:[],
          need_comments:cfg.content?[]:[{article_id:'a1',url:'https://seekingalpha.com/article/1-a'}]};
        if(['save_article_content','save_comments_only'].includes(message.action))
          return cfg.failure==='parse'
            ? {status:'ok',ok:true,comment_scan_usable:false,comment_backfill_pending:true,net_new_comments:0}
            : {status:'error',ok:false,error_code:'database_write_failed'};
        return {status:'ok'};
      };
      const details=await doDetailFetch(1,[],'quick',diagnostics);
      return {details,run:attachExtensionRunProtocol('alpha_picks_sync','quick',{
        current:{status:'ok'},closed:{status:'ok'},details}).extension_run,diagnostics:diagnostics.freeze()};
    """)
    assert result["details"]["failed"] == 1
    assert result["run"]["phases"]["article_details"] == {"state": "failed", "reason_code": reason}
    assert result["run"]["derived_outcome"] == "degraded"
    assert result["run"]["db_status"] == "failed"
    assert result["run"]["healthy_anchor_eligible"] is False
    assert not result["run"].get("comment_progress", {}).get("pending_articles")
    assert result["diagnostics"]["entries"][0]["reason_code"] == (
        "comment_scan_failed" if failure == "parse" else "database_write_failed"
    )


def _js_result(tmp_path, payload):
    fixture = tmp_path / "partial.json"
    fixture.write_text(json.dumps({"protocol_cases": [{"name": "partial", "input": payload}]}))
    run = subprocess.run(["node", str(RUNNER), str(fixture), str(JS_PROTOCOL)],
                         check=True, capture_output=True, text=True)
    return json.loads(run.stdout)[0]


@pytest.mark.parametrize("reason,stop", [("comment_backfill_pending", "timeout"), ("controls_unresolved", "controls_unresolved")])
@pytest.mark.parametrize("failure,outcome", [(None, "deferred"), ("article_details", "degraded"), ("current_picks", "failed")])
def test_partial_protocol_matches_js_and_keeps_real_failure_precedence(tmp_path, reason, stop, failure, outcome):
    payload = _pending_payload(reason, stop)
    if failure:
        payload["phases"][failure] = {"state": "failed", "reason_code": "detail_save_failed"}
    js = _js_result(tmp_path, payload)
    assert js["ok"] is True
    result = derive_run_result(payload)
    assert js["result"] == result
    assert result["derived_outcome"] == outcome
    assert result["healthy_anchor_eligible"] is False
    assert result["comment_progress"] == payload["comment_progress"]


@pytest.mark.parametrize("mutation", ["v1", "complete", "negative", "boolean", "unknown_stop", "empty_stops", "duplicate_stops", "extra_field", "wrong_phase"])
def test_invalid_partial_progress_fails_closed_in_both_protocols(tmp_path, mutation):
    payload = _pending_payload()
    if mutation == "v1":
        payload["schema_version"] = 1
    elif mutation == "complete":
        payload["phases"]["article_details"] = {"state": "complete", "reason_code": None}
    elif mutation == "negative":
        payload["comment_progress"]["net_new_comments"] = -1
    elif mutation == "boolean":
        payload["comment_progress"]["pending_articles"] = True
    elif mutation == "unknown_stop":
        payload["comment_progress"]["stop_reasons"] = ["raw provider prose"]
    elif mutation == "empty_stops":
        payload["comment_progress"]["stop_reasons"] = []
    elif mutation == "duplicate_stops":
        payload["comment_progress"]["stop_reasons"] = ["timeout", "timeout"]
    elif mutation == "extra_field":
        payload["comment_progress"]["error"] = "raw provider prose"
    else:
        payload["phases"]["current_picks"], payload["phases"]["article_details"] = (
            payload["phases"]["article_details"], payload["phases"]["current_picks"])
    with pytest.raises(ProtocolError):
        derive_run_result(payload)
    assert _js_result(tmp_path, payload)["ok"] is False


def test_partial_receipt_survives_native_outbox_and_preserves_healthy_anchor(tmp_path, monkeypatch):
    from src.api.routes import jobs as jobs_route
    from src.sa_native_host import _handle_record_extension_job
    from src.service.job_runs_store import JobRunsLocalStore
    from src.service.sa_extension_health import _telemetry_last_segment
    from src.sa.company_collector import CompanyCollector
    from tests.test_sa_acquisition_authority import activate, call, navigation, UNCAPPED

    payload = _pending_payload()
    collector = CompanyCollector(tmp_path / "control.db", clock=lambda: 100000.)
    activate(collector, UNCAPPED)

    def receipt(status):
        permit = call(collector, "begin_task", generation=1, request_id="test-" + status,
                      task_operation="alpha_picks_sync", mode="quick", trigger="manual",
                      intent_revision=0, build="test", protocol_version=2)
        navigation(collector, permit)
        return call(collector, "finish_task", token=permit["token"], generation=1,
                    cleanup_confirmed=True, result={"status": status})["acquisition"]

    healthy_receipt, pending_receipt = receipt("ok"), receipt("deferred")
    monkeypatch.setattr("src.sa.company_collector.CompanyCollector", lambda: collector)
    emitted = _run_background("const payload=" + json.dumps(payload) + ";const acquisition=" + json.dumps(pending_receipt) + r""";
      const data={},delivered=[];
      const storage={get:async keys=>Object.fromEntries(keys.map(key=>[key,data[key]])),
        set:async values=>Object.assign(data,JSON.parse(JSON.stringify(values)))};
      const options={storage,now:()=>Date.parse('2026-09-26T01:01:00Z'),
        deliver:async event=>{delivered.push(event);return {persisted:false,error_code:'sidecar_unavailable'};}};
      const controller=SAExtensionTelemetry.createController(options);
      const delivery=await controller.submit({client_event_id:'partial-comments',started_at:'2026-09-26T01:00:00Z',
        finished_at:'2026-09-26T01:00:30Z',result:payload,acquisition});
      const restarted=SAExtensionTelemetry.createController(Object.assign({},options,{
        deliver:async event=>{delivered.push(event);return {persisted:true,run_id:42};}}));
      await restarted.flush('startup');
      return {delivery,delivered,summary:data[SAExtensionTelemetry.LAST_RUN_STORAGE_KEY]};
    """)
    assert emitted["delivery"]["delivery"] == "pending"
    assert len(emitted["delivered"]) == 2
    assert emitted["delivered"][0] == emitted["delivered"][1]
    assert emitted["summary"]["comment_progress"] == payload["comment_progress"]
    assert emitted["delivered"][0]["result"]["comment_progress"] == payload["comment_progress"]
    store = JobRunsLocalStore(tmp_path / "jobs.db")
    monkeypatch.setattr(jobs_route, "get_job_runs_store", lambda dal: store)
    monkeypatch.setattr("src.sa_native_host._post_extension_job_to_sidecar", lambda event:
                        jobs_route.record_extension_job(jobs_route.ExtensionJobRecordRequest(**event), dal=None).model_dump())
    event = emitted["delivered"][0]
    complete = copy.deepcopy(event)
    complete["client_event_id"] = "healthy-before-partial"
    complete["acquisition"] = healthy_receipt
    complete["started_at"] = "2026-09-25T01:00:00Z"
    complete["finished_at"] = "2026-09-25T01:00:30Z"
    complete["result"] = {key: value for key, value in payload.items() if key != "comment_progress"}
    complete["result"]["phases"] = {name: {"state": "complete", "reason_code": None} for name in payload["phases"]}
    healthy = _handle_record_extension_job(None, complete)
    response = _handle_record_extension_job(None, event)
    assert healthy["persisted"] is True, healthy
    assert response["persisted"] is True, response
    row = store.list_runs(limit=1)[0]
    assert row["status"] == "deferred"
    assert row["result"]["comment_progress"] == payload["comment_progress"]
    summary = store.structured_extension_summary_by_name(["sa_alpha_picks_refresh"])["sa_alpha_picks_refresh"]
    assert summary["latest_derived_complete"]["id"] == healthy["run_id"]
    health = _telemetry_last_segment(store)
    assert (health["state"], health["code"]) == ("warn", "capture_deferred")
    assert health["comment_progress"] == payload["comment_progress"]
    assert jobs_route.jobs_history(name=None, limit=10, offset=0, dal=None).runs[0].status == "deferred"
    assert _handle_record_extension_job(None, event)["run_id"] == response["run_id"]


@pytest.mark.parametrize("stop", [None, {"status": "deferred", "reason": "capacity_exhausted"},
                                     {"status": "error", "reason": "site_paused", "error_code": "login_required"}])
@pytest.mark.parametrize("manual", [False, True])
def test_acquisition_stop_keeps_pending_progress_without_masking_restrictions(stop, manual):
    result = _run_background("const cfg=" + json.dumps(dict(stop=stop, manual=manual)) + r""";
      const details={fetched:1,failed:0,comment_progress:{pending_articles:1,net_new_comments:38,stop_reasons:['timeout']}};
      const result=cfg.manual ? details : {current:{status:'ok'},closed:{status:'ok'},details,
        completed_phases:['current_picks','closed_picks']};
      if(cfg.stop)result.acquisition_stop=cfg.stop;
      return attachExtensionRunProtocol(cfg.manual?'alpha_picks_manual_fetch':'alpha_picks_sync',
        cfg.manual?'manual':'quick',result).extension_run;
    """)
    assert result["comment_progress"] == {"pending_articles": 1, "net_new_comments": 38, "stop_reasons": ["timeout"]}
    assert result["healthy_anchor_eligible"] is False
    phase = result["phases"]["manual_fetch" if manual else "article_details"]
    if stop and stop["status"] == "error":
        assert phase == {"state": "failed", "reason_code": "login_required"}
        assert result["db_status"] == "failed"
    else:
        assert phase == {"state": "deferred", "reason_code": "comment_backfill_pending"}
        assert result["db_status"] == "deferred"


def test_scheduled_refresh_progress_does_not_announce_pending_comments_as_done():
    result = _run_background(_DETAIL_FLOW_SETUP + r"""
      const messages=[],stored={};
      sendProgress=message=>messages.push(message);
      cleanupCollectorTabs=registerCollectorTab=unregisterCollectorTab=safeRemoveTab=async()=>{};
      chrome.tabs.create=async()=>({id:1});
      chrome.storage.local.set=async values=>Object.assign(stored,values);
      waitForAlphaPicksTableReady=async()=>({ok:true});
      injectScraper=async()=>[{symbol:'TEST'}];
      sendToNativeHost=async()=>({status:'ok',count:1});
      scrollToComments=async()=>({mode:'backfill',stop_reason:'timeout'});
      sendNativeMessage2=async message=>{
        if(message.action==='save_articles_meta')return {status:'ok',saved:1,
          need_comments:[{article_id:'a1',url:'https://seekingalpha.com/article/1-a'}]};
        if(message.action==='save_comments_only')return {status:'ok',comment_scan_usable:true,
          comment_backfill_pending:true,net_new_comments:38};
        return {status:'ok'};
      };
      const result=await doRefresh('quick',{trigger:'alarm'});
      return {result,messages,stored};
    """)
    assert result["messages"][-1].startswith("Partial")
    assert "38" in result["messages"][-1]
    assert "pending" in result["messages"][-1]
    assert "timeout" in result["messages"][-1]
    assert result["stored"]["lastRefresh"]["trigger"] == "alarm"
    assert result["stored"]["lastRefresh"]["details"]["comment_progress"]["pending_articles"] == 1


def test_immediate_popup_refresh_result_displays_pending_progress():
    from tests.test_sa_extension_popup import _run

    result = _run("click_alpha_refresh", refreshResult={
        "details": {"failed": 0, "comment_progress": _pending_payload()["comment_progress"]},
        "extension_run": {"derived_outcome": "deferred"},
    })
    assert "Partial" in result["refreshAttemptStatus"]
    assert "38 net new comments stored" in result["refreshAttemptStatus"]
    assert "1 article pending" in result["refreshAttemptStatus"]
    assert "time budget reached" in result["refreshAttemptStatus"]


def test_manual_popup_progress_is_partial_despite_saved_body():
    from tests.test_sa_extension_popup import _run

    result = _run("click_manual_fetch", manualResult={
        "fetched": 1, "failed": 0, "net_new_comments": 38,
        "comment_progress": _pending_payload()["comment_progress"],
    })
    assert "Partial" in result["progress"]
    assert "38 net new comments stored" in result["progress"]
    assert "1 article pending" in result["progress"]
    assert result["progressColor"] != "rgb(46, 125, 50)"


def test_popup_shows_partial_saved_progress_and_counts_deferred_phase():
    from tests.test_sa_extension_popup import _run

    payload = _pending_payload("controls_unresolved", "controls_unresolved")
    result = _run(storage={
        "lastRefresh": {"batch_ts": "2026-09-26T01:00:00Z", "mode": "quick",
                        "current": {"status": "ok", "count": 10}, "closed": {"status": "ok", "count": 5},
                        "details": {"net_new_comments": 38, "failed": 0, "comment_progress": payload["comment_progress"]}},
        "arkscope.sa.lastRun.v1": {"operation": "alpha_picks_sync", "mode": "quick", "derived_outcome": "deferred",
                                  "counts": {"phase_complete": 3, "phase_deferred": 1}, "audit_state": "persisted",
                                  "comment_progress": payload["comment_progress"]},
    })
    assert "Partial" in result["lastRunStatus"]
    assert "3/4 phases complete" in result["lastRunStatus"]
    assert "38 net new comments stored" in result["lastRunStatus"]
    assert "1 article pending" in result["lastRunStatus"]
    assert "unresolved controls" in result["lastRunStatus"].lower()
    assert 'id="status" class="partial"' in result["bodyHtml"]
