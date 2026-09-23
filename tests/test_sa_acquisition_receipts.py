"""A finished native task, not a browser label, authorizes an acquisition claim."""

import copy
from datetime import datetime, timezone

import pytest

from src.sa.company_collector import CompanyCollector
from src.service.job_runs_store import JobRunsLocalStore
from tests.test_sa_acquisition_authority import activate, begin, call, navigation, CHROME
from tests.test_sa_extension_run_protocol import _case


@pytest.fixture
def chain(tmp_path, monkeypatch):
    from src.api.routes import jobs
    from src import sa_native_host as host

    obj = CompanyCollector(tmp_path / "control.db", clock=lambda: 100000.)
    activate(obj)
    permit = begin(obj)
    navigation(obj, permit)
    receipt = call(obj, "finish_task", token=permit["token"], generation=1,
                   cleanup_confirmed=True, result={"status": "ok"})["acquisition"]
    store = JobRunsLocalStore(tmp_path / "profile.db")
    monkeypatch.setattr("src.sa.company_collector.CompanyCollector", lambda: obj)
    monkeypatch.setattr(jobs, "get_job_runs_store", lambda dal: store)
    monkeypatch.setattr(host, "_post_extension_job_to_sidecar",
                        lambda payload: jobs.record_extension_job(jobs.ExtensionJobRecordRequest(**payload), dal=None).model_dump())
    payload = copy.deepcopy(_case("complete_market_sync")["input"])
    payload["schema_version"] = 2
    for key in ("counts", "derived_outcome", "healthy_anchor_eligible"):
        payload.pop(key, None)
    now = datetime.fromtimestamp(100000, timezone.utc).isoformat()
    event = dict(action="record_extension_job", client_event_id="new-v2", started_at=now, finished_at=now,
                 result=payload, acquisition=receipt)
    return obj, store, host, jobs, event


def test_delayed_event_after_owner_switch_is_recorded_once_with_original_identity(chain):
    obj, store, host, _, event = chain
    call(obj, "select", CHROME, expected_generation=1, confirm_schedules=True)
    first = host.handle_message(event)
    assert first["persisted"] is True, first
    assert host.handle_message(event)["run_id"] == first["run_id"]
    rows = store.list_runs(limit=10)
    assert len(rows) == 1
    assert rows[0]["payload"]["acquisition"] == event["acquisition"]
    assert rows[0]["payload"]["acquisition"]["generation"] == 1


@pytest.mark.parametrize("field,value", [("generation", 2), ("client_id", "d" * 32), ("navigation_attempt_count", 99)])
def test_native_and_api_both_reject_tampered_identity(chain, field, value):
    _, store, host, jobs, event = chain
    event["acquisition"][field] = value
    assert host.handle_message(event)["persisted"] is False
    args = {key: value for key, value in event.items() if key != "action"}
    assert jobs.record_extension_job(jobs.ExtensionJobRecordRequest(**args), dal=None).persisted is False
    assert store.list_runs(limit=10) == []


def test_missing_proof_cannot_claim_completed_v2_acquisition(chain):
    _, store, host, _, event = chain
    event.pop("acquisition")
    assert host.handle_message(event)["persisted"] is False
    assert store.list_runs(limit=10) == []


def test_pre_admission_wait_has_no_invented_identity_or_healthy_anchor(chain):
    _, store, host, _, event = chain
    event.pop("acquisition")
    for name in event["result"]["phases"]:
        event["result"]["phases"][name] = dict(state="deferred", reason_code="collector_other_installation")
    event["result"]["item_outcomes"] = []
    assert host.handle_message(event)["persisted"] is True
    row = store.list_runs(limit=1)[0]
    assert "acquisition" not in row["payload"]
    assert row["result"]["derived_outcome"] == "deferred"
    assert row["result"]["healthy_anchor_eligible"] is False
    from src.service.sa_extension_health import _telemetry_last_segment

    segment = _telemetry_last_segment(store)
    assert segment["state"] == "warn"
    assert segment["code"] == "capture_deferred"
    assert segment["counts"]["phase_deferred"] == 5
