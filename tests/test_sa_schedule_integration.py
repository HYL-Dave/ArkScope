"""Schedule effects across the real popup/background/storage boundary, no SA IO."""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tests/js/run_sa_schedule_integration.cjs"


def run(**options):
    result = subprocess.run(["node", str(RUNNER), json.dumps(options)], cwd=ROOT,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("enabled", [True, False])
def test_force_confirmation_never_changes_the_schedule(enabled):
    result = run(scenario="force", consent="companyForceConfirmed", enabled=enabled)
    assert result["after"]["data"]["companyFinancialRefresh"]["config"]["enabled"] is enabled
    assert result["after"]["companyEnabled"] is enabled
    assert not any(action["action"] == "save_company_refresh" for action in result["actions"])
    assert any(action == {"action": "run_company_refresh", "force": True, "confirm_force": True}
               for action in result["actions"])


@pytest.mark.parametrize("consent", [None, "companyRecoveryConfirmed", "companyActivationConfirmed"])
def test_due_update_and_unrelated_consent_do_not_save_settings(consent):
    result = run(scenario="due", consent=consent)
    assert result["after"]["data"]["companyFinancialRefresh"]["config"]["enabled"] is True
    assert not any(action["action"] == "save_company_refresh" for action in result["actions"])


@pytest.mark.parametrize("job,alarm", [("alphaPicks", "alpha-picks-auto-sync"), ("marketNews", "market-news-auto-sync")])
def test_activation_preserves_a_newer_stop_from_the_open_popup(job, alarm):
    result = run(scenario="stop", job=job)
    assert any(action["action"].startswith("set_") and action["enabled"] is False for action in result["actions"])
    assert result["after"]["data"][job + "AutoSyncEnabled"] is False
    assert alarm not in result["after"]["alarms"]
    assert result["after"]["alphaEnabled" if job == "alphaPicks" else "newsEnabled"] is False


def test_uncontended_activation_preserves_enabled_routine_intents():
    result = run(scenario="activate")["after"]
    assert result["data"]["alphaPicksAutoSyncEnabled"] is True
    assert result["data"]["marketNewsAutoSyncEnabled"] is True
    assert result["data"]["companyFinancialRefresh"]["config"]["enabled"] is True
    assert result["summary"] == "Routine schedules: Alpha Picks on | News on"


def test_failed_activation_immediately_updates_all_visible_switches():
    result = run(scenario="failure")["after"]
    assert result["data"]["alphaPicksAutoSyncEnabled"] is False
    assert result["data"]["marketNewsAutoSyncEnabled"] is False
    assert result["alphaEnabled"] is result["newsEnabled"] is result["companyEnabled"] is False
    assert result["summary"] == "Routine schedules: Alpha Picks off | News off"
    assert "configure: sa_company_collector_busy" in result["status"]


def test_storage_changes_update_intervals_and_summary_without_feedback_writes():
    result = run(scenario="storage")
    assert result["after"]["alphaInterval"] == "60"
    assert result["after"]["newsInterval"] == "15"
    assert result["after"]["summary"] == "Routine schedules: Alpha Picks off | News off"
    assert not any(action["action"].startswith("set_") for action in result["actions"])


def test_actual_config_edits_still_require_disabled_save_before_update():
    result = run(scenario="due", edit="period")
    assert any(action["action"] == "save_company_refresh" for action in result["actions"])
    config = result["after"]["data"]["companyFinancialRefresh"]["config"]
    assert config["interval_days_by_view"]["annual"] == 10
    assert config["enabled"] is False


def test_unsaved_policy_edit_is_retained_without_disabling_the_schedule():
    result = run(scenario="due", edit="policy")
    assert result["after"]["policyLimit"] == "12"
    assert result["after"]["data"]["companyFinancialRefresh"]["config"]["enabled"] is True
    assert not any(action["action"] == "save_company_refresh" for action in result["actions"])
