"""Mounted popup lifecycle and immediate-result contracts, without live calls."""

import json
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def run(scenario="snapshot", **fixture):
    process = subprocess.run([
        "node", str(ROOT / "tests/js/run_sa_extension_popup_fixture.mjs"),
        str(ROOT / "extensions/sa_alpha_picks"), scenario, json.dumps(fixture),
    ], cwd=ROOT, capture_output=True, text=True, check=True)
    return json.loads(process.stdout)


def state(*, active=False, recovery=False, pending=False, running=False):
    return {
        "status": "ok", "config": {"enabled": False, "target_mode": "watchlist", "tickers": [],
            "statements": ["income_statement"], "views": ["annual"], "interval_days": 7},
        "collector": {"status": "ok", "generation": 7, "is_owner": True,
            "owner": {"browser": "firefox"},
            "policy": {"hour_limit": None, "day_limit": None, "hour_reserve": 0, "day_reserve": 0},
            "active": {"operation": "alpha_picks_sync", "started_at": "2026-09-26T10:00:00Z",
                       "navigation_attempt_count": 3} if active or recovery else None},
        "acquisition_pending": pending, "acquisition_runtime_active": active,
        "acquisition_recovery_required": recovery, "running": running,
        "acquisition_pending_since": "2026-09-26T10:00:00Z" if pending else None,
        "scopes": [], "queue": {"pending": {"routine": 1, "background": 1}, "oldest_wait_ms": 200},
    }


@pytest.mark.parametrize("browser", ["firefox", "chrome"])
def test_pending_active_is_live_not_a_stopped_capture(browser):
    result = run(browser=browser, companyRefresh=state(active=True, pending=True))
    assert "alpha_picks_sync" in result["acquisitionLive"]
    assert "2026-09-26T10:00:00Z" in result["acquisitionLive"]
    assert "3" in result["acquisitionLive"]
    assert "running" in result["acquisitionLive"].lower()
    assert "Queued: 2" in result["acquisitionLive"]
    assert result["acquisitionLiveRole"] == "status"
    assert result["acquisitionWarningHidden"] is True
    assert "recovery required" not in result["acquisitionWarning"].lower()
    assert result["acquisitionRecoverDisabled"] is True
    assert result["acquisitionRecoveryShortcutHidden"] is True


def test_stopped_capture_warning_is_visible_outside_finance_details():
    result = run(companyRefresh=state(recovery=True, pending=True))
    assert "recovery required" in result["acquisitionLive"].lower()
    assert result["acquisitionLiveRole"] == "alert"
    assert result["acquisitionLiveInDetails"] is False
    assert result["acquisitionRecoveryShortcutHidden"] is False


@pytest.mark.parametrize("reason", ["sa_company_layout_unrecognized", "sa_company_parser_failures"])
def test_financial_local_parser_pause_is_visible_and_has_non_access_resume(reason):
    snapshot = state()
    snapshot["paused_reason"] = reason
    snapshot["pending_count"] = 3
    result = run(companyRefresh=snapshot)
    assert result["acquisitionWarningHidden"] is False
    assert reason in result["acquisitionWarning"]
    assert result["acquisitionResumeHidden"] is False
    assert result["acquisitionResumeDisabled"] is False
    assert "financial" in result["acquisitionResumeText"].lower()
    result = run("resume_financial_parser", companyRefresh=snapshot)
    actions = [m for m in result["sent"] if m["action"].startswith("resume_")]
    assert actions == [{"action": "resume_company_parser", "expected_generation": 7}]


def test_shared_cooldown_disables_parser_resume_and_remains_visible():
    snapshot = state()
    snapshot["paused_reason"] = "sa_company_parser_failures"
    snapshot["collector"].update(rate_limited=True, rate_limit_until="2026-09-29T00:00:00Z")
    result = run("resume_financial_parser", companyRefresh=snapshot)
    assert "cooldown" in result["acquisitionWarning"].lower()
    assert result["acquisitionResumeDisabled"] is True
    assert not any(m["action"].startswith("resume_") for m in result["sent"])


def test_missing_runtime_evidence_is_not_rendered_as_idle_or_recoverable():
    snapshot = state(recovery=True, pending=True)
    del snapshot["acquisition_runtime_active"]
    del snapshot["acquisition_recovery_required"]
    result = run(companyRefresh=snapshot)
    assert "unfinished" in result["acquisitionLive"].lower()
    assert "unavailable" in result["acquisitionLive"].lower()
    assert "idle" not in result["acquisitionLive"].lower()
    assert result["acquisitionRecoverDisabled"] is True


def test_malformed_successful_status_does_not_leave_initial_loading_message():
    result = run(companyRefresh={"status": "ok"})
    assert "unavailable" in result["acquisitionLive"].lower()
    assert "checking" not in result["acquisitionLive"].lower()
    assert result["acquisitionRecoverDisabled"] is True


def test_recovery_shortcut_only_reveals_existing_confirmation():
    result = run("review_stopped_acquisition", companyRefresh=state(recovery=True, pending=True))
    assert result["companyOptionsOpen"] is True
    assert result["companyAdvancedOpen"] is True
    assert result["activeId"] == "companyRecoveryConfirmed"
    assert not any(msg["action"] == "recover_sa_acquisition" for msg in result["sent"])


@pytest.mark.parametrize("active,running,confirm,want_send", [
    (True, False, True, False), (False, True, True, False),
    (False, False, False, False), (False, False, True, True),
])
def test_recovery_requires_stopped_runtime_and_confirmation(active, running, confirm, want_send):
    result = run("recover_acquisition", companyRefresh=state(
        active=active, running=running, recovery=not active, pending=True), confirmStopped=confirm)
    calls = [msg for msg in result["sent"] if msg["action"] == "recover_sa_acquisition"]
    assert bool(calls) is want_send
    if calls:
        assert calls[0]["expected_generation"] == 7
        assert calls[0]["confirm_stopped"] is True


def test_runtime_storage_wakeup_rereads_live_status_instead_of_trusting_disk():
    result = run("acquisition_runtime_wakeup", companyRefresh=state(active=True, pending=True),
                 nextCompanyRefresh=state(), runtimeSignal={"running": True})
    assert len([msg for msg in result["sent"] if msg["action"] == "get_company_refresh"]) == 2
    assert "idle" in result["acquisitionLive"].lower()
    assert "running" not in result["acquisitionLive"].lower()


def test_runtime_finish_wakeup_during_form_save_is_not_lost():
    result = run("configure_company_refresh", companyRefresh=state(active=True, pending=True),
                 runtimeDuringAction="save_company_refresh", nextCompanyRefresh=state(),
                 runtimeSignal={"running": False})
    assert "idle" in result["acquisitionLive"].lower()
    assert result["acquisitionRecoveryShortcutHidden"] is True


HISTORY = {
    "lastRefresh": {"batch_ts": "2026-09-25T00:00:00Z", "mode": "quick",
        "current": {"status": "ok", "count": 17}, "closed": {"status": "ok", "count": 8}},
    "lastMarketNewsRefresh": {"batch_ts": "2026-09-25T00:00:00Z", "mode": "quick",
        "result": {"status": "ok", "saved": 13, "count": 15}},
}


@pytest.mark.parametrize("scenario", ["click_alpha_refresh", "click_news_refresh"])
@pytest.mark.parametrize("response,reason,label", [
    ({"status": "deferred", "reason": "collector_busy"}, "collector_busy", "deferred"),
    ({"status": "error", "error_code": "native_host_unavailable"}, "native_host_unavailable", "failed"),
    ({"status": "ok", "acquisition_stop": {"status": "deferred", "reason": "site_pacing"}}, "site_pacing", "deferred"),
    (None, "empty_extension_response", "unknown"),
])
def test_click_receipt_does_not_reuse_old_success(scenario, response, reason, label):
    result = run(scenario, storage=HISTORY, storageAfterClick=HISTORY, refreshResult=response)
    assert reason in result["refreshAttemptStatus"]
    assert label in result["refreshAttemptStatus"].lower()
    assert "17 picks" in result["storedAlphaStatus"]
    assert "13 saved" in result["storedNewsStatus"]
    assert result["refreshButtonsDisabled"] == [False] * 5


@pytest.mark.parametrize("scenario", ["click_alpha_refresh", "click_news_refresh"])
def test_runtime_callback_error_is_reported_without_stale_success(scenario):
    result = run(scenario, storage=HISTORY, runtimeError="connection closed")
    assert "extension_runtime_unavailable" in result["refreshAttemptStatus"]
    assert result["refreshAttemptRole"] == "alert"


def test_deferred_click_keeps_the_specific_error_and_retry_time():
    result = run("click_alpha_refresh", refreshResult={"status": "deferred", "reason": "site_paused",
        "error_code": "rate_limited", "retry_after": "2026-09-26T12:00:00Z"})
    assert "site_paused" in result["refreshAttemptStatus"]
    assert "rate_limited" in result["refreshAttemptStatus"]
    assert "2026-09-26T12:00:00Z" in result["refreshAttemptStatus"]


def test_callback_quick_workload_does_not_wait_for_storage_update():
    result = run("click_alpha_refresh", storage=HISTORY, refreshResult={"details": {
        "quick_workload": {"navigation_budget": 4, "selected_count": 4,
                           "eligible_count": 19, "deferred_count": 15,
                           "backlog_scope": "eligible_candidates"},
    }})
    assert "15 eligible candidates deferred" in result["refreshAttemptStatus"]
    assert "15 eligible candidates deferred" not in result["storedAlphaStatus"]


def test_quick_backlog_is_scoped_and_not_called_up_to_date():
    history = {**HISTORY["lastRefresh"], "details": {
        "fetched": 0, "comments_refreshed": 0,
        "quick_workload": {"navigation_budget": 4, "selected_count": 4,
                           "eligible_count": 19, "deferred_count": 15,
                           "backlog_scope": "eligible_candidates"},
    }}
    result = run(storage={"lastRefresh": history})
    assert "15 eligible candidates deferred" in result["storedAlphaStatus"]
    assert "4 selected" in result["storedAlphaStatus"]
    assert "4 navigation" in result["storedAlphaStatus"]
    assert "up to date" not in result["storedAlphaStatus"].lower()
