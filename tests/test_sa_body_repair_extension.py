"""Offline contracts for the bounded, manual article-body repair entry."""

import copy
import json
from pathlib import Path
import subprocess
from uuid import uuid4

import pytest

from src.sa.company_collector import CompanyCollector
from src.sa.extension_run_protocol import ProtocolError, derive_run_result
from tests.test_sa_body_recovery_jobs import journal_case
from tests.test_sa_article_acquisition_scope import scope_case
from tests.test_sa_acquisition_authority import FIREFOX
from tests.test_sa_article_body_recovery import NARRATIVE


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tests/js/run_sa_body_repair_fixture.mjs"


@pytest.mark.parametrize("scenario", [
    "preview_bound", "repair_success", "priority", "cancel_active", "cancel_queued",
    "owner_gate", "pause_gate", "capacity_gate", "navigation_gate", "site_stop",
    "revalidate", "save_rejected", "navigation_changed", "cleanup_failed",
    "interrupted", "popup", "combined_save_rejected", "cancel_gap", "gap_priority", "pacing_stop",
    "lane_priority", "idle_gap",
    "initial_pacing", "pacing_race", "lifetime_disconnect", "lifetime_unavailable", "save_comment_thread",
    "lifetime_handshake_timeout", "lifetime_deadline",
    "lifetime_cancel_setup", "lifetime_disconnect_active",
])
def test_body_repair_browser_behavior(scenario):
    result = subprocess.run(["node", str(RUNNER), scenario], cwd=ROOT,
                            capture_output=True, text=True, timeout=25)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("kind,outcome", [
    ("complete", "complete"), ("failed", "failed"), ("skipped", "skipped"),
    ("deferred", "deferred"), ("site_pacing", "deferred"), ("scheduled", None), ("healthy", None),
    ("wrong_phases", None), ("items", None),
    ("comment_thread", "failed"),
])
def test_body_repair_protocol_parity(tmp_path, kind, outcome):
    payload = {
        "schema_version": 2, "operation": "alpha_picks_body_repair", "mode": "manual",
        "phases": {name: {"state": "complete", "reason_code": None}
                   for name in ("extraction", "persistence")}, "item_outcomes": [],
    }
    if kind in {"failed", "skipped", "deferred", "site_pacing"}:
        reason = {"failed": "detail_save_failed", "skipped": "operator_cancelled",
                  "deferred": "capacity_exhausted", "site_pacing": "site_pacing"}[kind]
        for phase in payload["phases"].values():
            phase.update(state="deferred" if kind == "site_pacing" else kind, reason_code=reason)
    if kind == "comment_thread":
        payload["phases"]["extraction"] = {"state": "failed", "reason_code": "sa_article_body_comment_thread"}
    if kind == "scheduled":
        payload["mode"] = "scheduled"
    if kind == "healthy":
        payload["healthy_anchor_eligible"] = True
    if kind == "wrong_phases":
        payload["phases"]["comments"] = payload["phases"].pop("persistence")
    if kind == "items":
        payload["item_outcomes"] = [{"news_id": "123", "state": "repaired",
            "reason_code": "body_saved", "attempt_count": 1, "evidence_code": None}]
    if outcome is None:
        with pytest.raises(ProtocolError) as failure:
            derive_run_result(copy.deepcopy(payload))
        expected = {"ok": False, "error_code": failure.value.code}
    else:
        result = derive_run_result(copy.deepcopy(payload))
        assert result["derived_outcome"] == outcome
        assert result["healthy_anchor_eligible"] is False
        assert result["job_name"] == "sa_alpha_picks_body_repair"
        expected = {"ok": True, "result": result}
    fixture = tmp_path / "protocol.json"
    fixture.write_text(json.dumps({"protocol_cases": [{"name": kind, "input": payload}]}))
    js = subprocess.run([
        "node", str(ROOT / "tests/js/run_sa_extension_protocol_fixture.mjs"),
        str(fixture), str(ROOT / "extensions/sa_alpha_picks/extension_run_protocol.js"),
    ], check=True, capture_output=True, text=True)
    assert json.loads(js.stdout) == [{"name": kind, **expected}]


def test_body_repair_uses_server_background_reserve_and_manual_admission(journal_case):
    client, clock, control = FIREFOX, journal_case.now, journal_case.collector
    job = journal_case.start()

    def call(operation, **fields):
        return control.handle({"client": client, "operation": operation, "generation": 1, **fields})

    assert call("configure", expected_generation=1, confirm_activation=True,
                policy={"hour_limit": 2, "day_limit": 10, "hour_reserve": 1, "day_reserve": 1},
                financial_gap_seconds=60)["status"] == "ok"

    def begin(operation="alpha_picks_body_repair", trigger="manual"):
        return call("begin_task", task_operation=operation, mode="manual" if operation.endswith("repair") else "quick",
                    request_id=uuid4().hex, trigger=trigger, intent_revision=job["revision"], build="test", protocol_version=2,
                    body_job_id=job["job_id"], body_job_revision=job["revision"], article_id="1000")

    assert begin(trigger="alarm")["status"] == "error"
    permit = begin()
    assert permit["status"] == "ok"
    assert permit["active"]["priority"] == "background"
    assert call("admit_navigation", token=permit["token"], navigation_id=uuid4().hex,
                kind="create", destination_class="article")["allowed"] is True
    journal_case.conn.execute("UPDATE sa_articles SET body_markdown=? WHERE article_id='1000'", (NARRATIVE,))
    journal_case.conn.commit()
    assert call("finish_task", token=permit["token"], cleanup_confirmed=True,
                result={"status": "ok"})["active"] is None
    clock[0] += 60
    assert begin()["reason"] == "capacity_exhausted"
    assert begin("alpha_picks_sync")["status"] == "ok"


@pytest.mark.parametrize("previous", ["alpha_picks_body_repair", "company_financial_capture"])
@pytest.mark.parametrize("policy", [
    {"hour_limit": 100, "day_limit": 1000, "hour_reserve": 10, "day_reserve": 100},
    {"hour_limit": None, "day_limit": None, "hour_reserve": 0, "day_reserve": 0},
])
def test_body_repair_obeys_shared_gap_after_body_or_financial_but_news_does_not(journal_case, previous, policy):
    clock, control, client = journal_case.now, journal_case.collector, FIREFOX
    job = journal_case.start()
    next_aid = ["1000"]

    def call(operation, **fields):
        return control.handle({"client": client, "operation": operation, "generation": 1, **fields})

    assert call("configure", expected_generation=1, confirm_activation=True,
                policy=policy,
                financial_gap_seconds=45)["status"] == "ok"

    def begin(operation, mode="manual"):
        return call("begin_task", task_operation=operation, mode=mode,
                    request_id=uuid4().hex, trigger="manual", intent_revision=job["revision"], build="test", protocol_version=2,
                    body_job_id=job["job_id"], body_job_revision=job["revision"], article_id=next_aid[0])

    permit = begin(previous, "current_tab" if previous == "company_financial_capture" else "manual")
    assert permit["status"] == "ok"
    assert call("admit_navigation", token=permit["token"], navigation_id=uuid4().hex,
                kind="create", destination_class="article" if previous.endswith("repair") else "company")["allowed"]
    if previous == "alpha_picks_body_repair":
        journal_case.conn.execute("UPDATE sa_articles SET body_markdown=? WHERE article_id='1000'", (NARRATIVE,))
        journal_case.conn.commit()
    finished = call("finish_task", token=permit["token"], cleanup_confirmed=True, result={"status":"ok"})
    deadline = finished["next_navigation_at"]
    clock[0] += 44
    blocked = begin("alpha_picks_body_repair")
    assert blocked["status"] == "deferred"
    assert blocked["error_code"] == "sa_company_pacing"
    assert blocked["retry_after"] == deadline
    assert blocked["active"] is None
    news = begin("market_news_sync", "quick")
    assert news["status"] == "ok"
    assert call("finish_task", token=news["token"], cleanup_confirmed=True, result={"status":"ok"})["next_navigation_at"] == deadline
    clock[0] += 1
    next_aid[0] = journal_case.control("next", job_id=job["job_id"], revision=job["revision"])["target"]["article_id"]
    assert begin("alpha_picks_body_repair")["status"] == "ok"


@pytest.mark.parametrize("operation,mode", [
    ("alpha_picks_body_repair", "manual"), ("company_financial_capture", "current_tab"),
])
def test_cancellation_without_navigation_does_not_restart_the_page_gap(journal_case, operation, mode):
    clock, control, client = journal_case.now, journal_case.collector, FIREFOX
    job = journal_case.start()

    def call(action, **fields):
        return control.handle({"client": client, "operation": action, "generation": 1, **fields})

    assert call("configure", expected_generation=1, confirm_activation=True,
                policy={"hour_limit": 10, "day_limit": 10, "hour_reserve": 0, "day_reserve": 0},
                financial_gap_seconds=60)["status"] == "ok"
    request = {"task_operation": operation, "mode": mode, "trigger": "manual",
               "intent_revision": job["revision"], "build": "test", "protocol_version": 2,
               "body_job_id": job["job_id"], "body_job_revision": job["revision"], "article_id": "1000"}
    first = call("begin_task", **request, request_id=uuid4().hex)
    assert first["status"] == "ok"
    cancelled = call("finish_task", token=first["token"], cleanup_confirmed=True,
                     result={"status": "cancelled"})
    assert cancelled["next_navigation_at"] == first["next_navigation_at"]
    assert cancelled["acquisition"]["navigation_attempt_count"] == 0
    request["article_id"] = journal_case.control("next", job_id=job["job_id"], revision=job["revision"])["target"]["article_id"]
    assert call("begin_task", **request, request_id=uuid4().hex)["status"] == "ok"
