"""Old/new workers must preserve exact financial intent, not just a queue count."""

from copy import deepcopy
from datetime import datetime
import pytest

from tests.sa_cutover_assertions import assert_financial_checkpoint_preserved
from tests.sa_midfill_fixture import UpgradeRig
from tests.test_sa_article_acquisition_scope import scope_case


@pytest.fixture
def upgrade_case(scope_case, tmp_path, monkeypatch):
    with UpgradeRig(scope_case, tmp_path, monkeypatch) as rig:
        yield rig


@pytest.mark.parametrize("scheduled", [False, True])
@pytest.mark.parametrize("retry", [False, True])
def test_midfill_upgrade_resumes_remaining_scope_without_restarting(upgrade_case, scheduled, retry):
    case = upgrade_case
    case.initialize(scheduled=scheduled)
    case.run_financial()
    if retry:
        case.seed_retry_on_last_pending()
    before = case.checkpoint()
    ids = before["browser"]["companyFinancialRefresh"]["pending_scopes"]
    assert len(ids) == 3 and len(set(ids)) == 3
    assert len(case.saved) == 1
    first_saved = case.saved[0]
    case.reload("candidate")
    after = case.checkpoint()
    assert_financial_checkpoint_preserved(before, after)
    wake = case.worker("snapshot")["alarms"][-1]["when"] / 1000
    assert wake >= datetime.fromisoformat(after["native"]["next_navigation_at"]).timestamp()
    case.run_financial()
    assert case.checkpoint()["browser"]["companyFinancialRefresh"]["pending_scopes"] == ids
    case.advance(61)
    case.run_financial()
    assert case.saved[-1]["scope_id"] == ids[0]
    assert case.saved[-1]["receipt"]["active"] is None
    assert case.checkpoint()["browser"]["companyFinancialRefresh"]["pending_scopes"] == ids[1:]
    assert sum(row["scope_id"] == first_saved["scope_id"] for row in case.saved) == 1
    case.verify_captures()


@pytest.mark.parametrize("field", ["drop", "replace", "order", "intent_revision", "success", "retry", "generation", "owner", "ledger", "budget", "schedule"])
def test_preservation_rejects_destructive_mutations(upgrade_case, field):
    case = upgrade_case
    case.initialize(scheduled=False); case.run_financial(); case.seed_retry_on_last_pending()
    before = case.checkpoint(); after = deepcopy(before)
    state = after["browser"]["companyFinancialRefresh"]
    if field == "drop": state["pending_scopes"].pop()
    elif field == "replace": state["pending_scopes"][0] = "DIFFERENT/income_statement/annual"
    elif field == "order": state["pending_scopes"].reverse()
    elif field == "intent_revision": state["intent_revision"] = 0
    elif field == "success": next(v for v in state["records"].values() if v.get("last_success_at"))["last_success_at"] = "2000-01-01T00:00:00Z"
    elif field == "retry": state["records"][state["pending_scopes"][-1]]["retry_after"] = None
    elif field == "generation": after["native"]["generation"] += 1
    elif field == "owner": after["native"]["owner"]["client_id"] = "x" * 32
    elif field == "ledger": after["native"]["ledger_id"] = "0" * 32
    elif field == "budget": after["native"]["policy"]["day_limit"] = 5
    elif field == "schedule": after["browser"]["alphaPicksAutoSyncEnabled"] = False
    with pytest.raises(AssertionError):
        assert_financial_checkpoint_preserved(before, after)


@pytest.mark.parametrize("operation", ["cancel", "configure"])
def test_old_cancel_and_configuration_are_not_pause_operations(upgrade_case, operation):
    case = upgrade_case
    case.initialize(scheduled=True); case.run_financial()
    before = case.checkpoint()
    case.worker(operation)
    with pytest.raises(AssertionError):
        assert_financial_checkpoint_preserved(before, case.checkpoint())


def test_body_interleave_and_rollback_keep_new_captures_and_financial_intent(upgrade_case):
    case = upgrade_case
    case.initialize(scheduled=False); case.run_financial(); case.reload("candidate")
    before = case.checkpoint()
    job = case.start_body()
    assert_financial_checkpoint_preserved(before, case.checkpoint())
    case.advance(61)
    receipt = case.run_body(job)
    assert receipt["acquisition"]["body_recovery_job_id"] == job["job_id"]
    case.advance(61); case.run_financial()
    case.cancel_body(job)
    before_rollback = case.checkpoint()
    case.reload("baseline")
    assert_financial_checkpoint_preserved(before_rollback, case.checkpoint())
    case.advance(61); case.run_financial()
    case.run_news()
    case.verify_captures()
    assert case.body_is_saved()
    assert case.body_status()["state"] == "cancelled"


def test_uncertain_acquisition_is_not_an_idle_checkpoint(upgrade_case):
    case = upgrade_case
    case.initialize(scheduled=False); case.run_financial()
    before = case.checkpoint()
    before["browser"]["saAcquisitionPending"] = {"task_id": "still-owned"}
    with pytest.raises(AssertionError, match="saAcquisitionPending"):
        assert_financial_checkpoint_preserved(before, deepcopy(before))
