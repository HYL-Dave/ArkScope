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


def test_upgrade_popup_explicit_resume_preserves_saved_settings_and_successes():
    result = run(scenario="upgrade")
    assert result["before"]["upgradeVisible"] is True
    assert "Upgrade paused" in result["before"]["liveStatus"]
    assert result["after"]["upgradeVisible"] is False
    before, after = result["before"]["data"], result["after"]["data"]
    for key in ("config", "records"):
        assert before["companyFinancialRefresh"][key] == after["companyFinancialRefresh"][key]
    assert before["companyCollectorIdentity"] == after["companyCollectorIdentity"]
    assert any(action == {"action":"resume_sa_upgrade", "confirm_checked":True} for action in result["actions"])
    assert not any(action["action"] in {"save_company_refresh", "enable_sa_updates_here", "resume_sa_acquisition"} for action in result["actions"])


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


def test_new_profile_can_activate_without_filling_page_budgets():
    result = run(scenario="activate", newProfile=True, enabled=False)
    assert result["before"]["budgetEnabled"] is False
    assert result["before"]["budgetInputsDisabled"] is True
    activation = next(a for a in result["actions"] if a["action"] == "enable_sa_updates_here")
    assert activation["policy"] == dict(hour_limit=None, day_limit=None, hour_reserve=0, day_reserve=0)
    assert result["after"]["data"]["alphaPicksAutoSyncEnabled"] is True
    assert result["after"]["data"]["companyFinancialRefresh"]["config"]["enabled"] is False
    assert "Page budget: no hourly / daily cap" in result["after"]["status"]


def test_existing_page_budget_is_not_silently_disabled():
    result = run(scenario="activate", enabled=False)
    assert result["before"]["budgetEnabled"] is True
    assert result["before"]["budgetInputsDisabled"] is False
    activation = next(a for a in result["actions"] if a["action"] == "enable_sa_updates_here")
    assert activation["policy"] == dict(hour_limit=20, day_limit=100, hour_reserve=4, day_reserve=20)


def test_disabling_budget_discards_stale_fields_without_changing_routine_intervals():
    result = run(scenario="activate", enabled=False, budgetEnabled=False)
    activation = next(a for a in result["actions"] if a["action"] == "enable_sa_updates_here")
    assert activation["policy"] == dict(hour_limit=None, day_limit=None, hour_reserve=0, day_reserve=0)
    assert result["after"]["alphaInterval"] == result["before"]["alphaInterval"]
    assert result["after"]["newsInterval"] == result["before"]["newsInterval"]
    assert result["after"]["budgetEnabled"] is False
    assert result["after"]["budgetInputsDisabled"] is True


def test_incomplete_budget_draft_does_not_block_due_update_under_accepted_policy():
    result = run(scenario="due", budgetDraft=True,
                 policy=dict(hour_limit=None, day_limit=None, hour_reserve=0, day_reserve=0))
    assert any(a["action"] == "run_company_refresh" for a in result["actions"])
    assert not any(a["action"] in {"save_company_refresh", "enable_sa_updates_here"}
                   for a in result["actions"])


def test_enabling_empty_budget_never_silently_activates_uncapped_mode():
    result = run(scenario="activate", budgetDraft=True,
                 policy=dict(hour_limit=None, day_limit=None, hour_reserve=0, day_reserve=0))
    assert not any(a["action"] == "enable_sa_updates_here" for a in result["actions"])
    assert result["after"]["data"]["alphaPicksAutoSyncEnabled"] is True
