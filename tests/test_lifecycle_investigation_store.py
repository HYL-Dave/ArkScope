import sqlite3
from copy import deepcopy

import pytest

from tests.test_security_lifecycle_terminal_workflow import setup_workflow


def running(tmp_path, *, ticker="OLD"):
    from src.lifecycle_investigation.runtime import InvestigationRuntime
    from src.lifecycle_investigation.schema import install_journal
    from src.lifecycle_investigation.store import InvestigationStore
    from src.lifecycle_investigation.target import Target
    from src.lifecycle_journal_codec import digest_json
    c = setup_workflow(tmp_path, assess=False, event_available=False)
    with sqlite3.connect(c["profile"]) as conn:
        install_journal(conn, at=c["now"][0])
    binding = {"version": 2, "language": "en", "target": Target(ticker=ticker, as_of="2026-09-08").model_dump(),
        "selection": {"provider": "anthropic", "model": "claude-sonnet-5", "auth_mode": "claude_code_oauth", "credential_id": "local:7"},
        "runtime": InvestigationRuntime().model_dump(), "effort": "high", "credential_generation": "generation-1",
        "provider_observations": [], "provider_sha256": digest_json([])}
    store = InvestigationStore(c["profile"], clock=lambda: c["now"][0])
    identity = store.start(binding=binding, owner="worker", request_key="explicit-click")["run_id"]
    return c, store, identity, binding


def test_current_installation_preserves_unrelated_data_and_requires_no_case(tmp_path):
    from src.lifecycle_investigation.schema import install_journal, verify_journal
    c = setup_workflow(tmp_path, assess=False, event_available=False)
    with sqlite3.connect(c["profile"]) as conn:
        conn.execute("CREATE TABLE unrelated_receipts (receipt TEXT NOT NULL)")
        conn.execute("INSERT INTO unrelated_receipts VALUES ('retained')")
        before = conn.execute("SELECT COUNT(*) FROM security_lifecycle_cases").fetchone()[0]
        conn.commit()
        install_journal(conn, at=c["now"][0])
        verify_journal(conn)
        install_journal(conn, at=c["now"][0])
        assert conn.execute("SELECT * FROM unrelated_receipts").fetchall() == [("retained",)]
        assert conn.execute("SELECT COUNT(*) FROM security_lifecycle_cases").fetchone()[0] == before
        assert not list(conn.execute("PRAGMA foreign_key_list(lifecycle_investigation_jobs)"))


def test_journal_read_does_not_install_or_tolerate_unknown_schema(tmp_path):
    from src.lifecycle_investigation.schema import verify_journal
    with sqlite3.connect(tmp_path / "profile.db") as conn:
        with pytest.raises(ValueError, match="investigation_not_installed"):
            verify_journal(conn)
        assert list(conn.execute("SELECT name FROM sqlite_master")) == []


@pytest.mark.parametrize("failure", ("no_result", "failed_remote"))
def test_success_requires_a_completed_owned_conclusion(tmp_path, failure):
    _, store, identity, _ = running(tmp_path)
    store.reserve_call(identity, owner="worker", call_id="one")
    store.bind_call(identity, owner="worker", call_id="one", remote_id="remote-one",
        terminal="completed" if failure == "no_result" else "failed")
    with pytest.raises(ValueError, match="investigation_integrity"):
        store.finish(identity, owner="worker", status="succeeded")
    assert store.read(identity)["status"] == "running"
    store.finish(identity, owner="worker", status="failed", failure_code="model_output_invalid")
    assert store.read(identity)["status"] == "failed"


def test_unknown_remote_is_not_reported_cancelled_or_successful(tmp_path):
    _, store, identity, _ = running(tmp_path)
    store.reserve_call(identity, owner="worker", call_id="one")
    store.cancel(identity)
    store.finish(identity, owner="worker", status="succeeded")
    row = store.read(identity)
    assert (row["status"], row["failure_code"]) == ("remote_outcome_unknown", "remote_outcome_unknown")


def test_expired_lease_recovers_other_target_without_replaying_a_request(tmp_path):
    from src.lifecycle_investigation.controller import project_job
    c, store, first, binding = running(tmp_path)
    store.reserve_call(first, owner="worker", call_id="one")
    second_binding = deepcopy(binding)
    second_binding["target"]["ticker"] = "LIVE"
    second = store.start(binding=second_binding, owner="worker", request_key="other-click")["run_id"]
    c["now"][0] = "2026-09-09T00:00:00Z"
    assert project_job(store.read(first), at=c["now"][0])["status"] == "remote_outcome_unknown"
    store.recover()
    assert store.read(first)["status"] == "remote_outcome_unknown"
    assert store.read(second)["failure_code"] == "worker_interrupted"
    assert store.start(binding=binding, owner="other", request_key="explicit-click") == {"run_id": first, "created": False}
    changed = deepcopy(binding)
    changed["effort"] = "medium"
    with pytest.raises(ValueError, match="investigation_request_changed"):
        store.start(binding=changed, owner="other", request_key="explicit-click")
    replacement = store.start(binding=binding, owner="other", request_key="new-explicit-click")
    assert replacement["created"] and replacement["run_id"] != first


def test_cancel_owner_and_immutable_call_guards_are_independent(tmp_path):
    _, store, identity, _ = running(tmp_path)
    with pytest.raises(ValueError, match="investigation_owner_changed"):
        store.step(identity, owner="other", kind="searching", payload={})
    store.reserve_call(identity, owner="worker", call_id="one")
    store.bind_call(identity, owner="worker", call_id="one", remote_id="remote-one", terminal="completed")
    with pytest.raises(ValueError, match="investigation_recording_unavailable"):
        store.bind_call(identity, owner="worker", call_id="one", remote_id="remote-two", terminal="completed")
    store.cancel(identity)
    with pytest.raises(ValueError, match="stop_requested"):
        store.reserve_call(identity, owner="worker", call_id="two")
    store.finish(identity, owner="worker", status="failed")
    assert store.read(identity)["status"] == "cancelled"
    with pytest.raises(ValueError, match="investigation_not_running"):
        store.step(identity, owner="worker", kind="searching", payload={})


@pytest.mark.parametrize("kind", ["model", "journal", "contract", "source", "value", "unexpected"])
@pytest.mark.parametrize("message", ["provider_call_failed", "secret=private-token", "x" * 101])
def test_current_error_projection_keeps_typed_codes_but_never_raw_provider_errors(kind, message):
    from src.auth_drivers.lifecycle_web_models import WebModelError
    from src.lifecycle_investigation.store import safe_code
    from src.lifecycle_public_sources import SourceReadError
    from src.lifecycle_investigation.store import JournalError
    from src.security_lifecycle_web_contract import WebContractError

    classes = {"model": WebModelError, "journal": JournalError, "contract": WebContractError,
        "source": SourceReadError, "value": ValueError, "unexpected": RuntimeError}
    expected = "provider_call_failed" if kind not in {"value", "unexpected"} and message == "provider_call_failed" else "web_execution_failed"
    assert safe_code(classes[kind](message)) == expected
    assert safe_code(ValueError("investigation_recording_unavailable")) == "investigation_recording_unavailable"


def test_current_error_projection_keeps_the_unavailable_route_code():
    from src.lifecycle_investigation.store import safe_code
    from src.model_routing import ModelRouteUnavailable

    assert safe_code(ModelRouteUnavailable()) == "model_route_unavailable"


def test_current_start_replays_request_without_resetting_recorded_work(tmp_path):
    c, store, identity, binding = running(tmp_path)
    store.step(identity, owner="worker", kind="local_search", payload={"query": {}})
    before = store.read(identity)
    assert store.start(binding=binding, owner="other", request_key="explicit-click") == {"run_id": identity, "created": False}
    assert store.read(identity) == before
    with pytest.raises(ValueError, match="investigation_running"):
        store.start(binding=binding, owner="other", request_key="new-click")


def test_current_recording_failure_stops_control_before_remote_dispatch(tmp_path, monkeypatch):
    _, store, identity, _ = running(tmp_path)
    control = store.control(identity, owner="worker")
    def fail(*args, **kwargs):
        raise ValueError("investigation_recording_unavailable")
    monkeypatch.setattr(store, "reserve_call", fail)
    with pytest.raises(ValueError, match="^investigation_recording_unavailable$"):
        control.reserve_model_request("not-dispatched")
    assert control.stop_state != "running"
    row = store.read(identity)
    assert row["calls"] == [] and row["result"] is None and row["status"] == "running"


@pytest.mark.parametrize("expired", [False, True])
def test_current_wrong_or_expired_owner_cannot_record_provider_work(tmp_path, expired):
    c, store, identity, _ = running(tmp_path)
    if expired:
        c["now"][0] = "2026-09-09T00:00:00Z"
    with pytest.raises(ValueError, match="investigation_not_running" if expired else "investigation_owner_changed"):
        store.reserve_call(identity, owner="worker" if expired else "other", call_id="not-dispatched")
    assert store.read(identity)["calls"] == []


def test_current_source_rows_are_immutable_and_no_human_acceptance_is_fabricated(tmp_path):
    from tests.test_lifecycle_investigation_review import context
    c = context(tmp_path)
    row = c["investigation"].read(c["run_id"])
    assert row["status"] == "succeeded" and not row["adopted"]
    with sqlite3.connect(c["profile"]) as conn:
        for statement in ("UPDATE lifecycle_investigation_sources SET payload_json='{}'", "DELETE FROM lifecycle_investigation_sources",
                          "UPDATE lifecycle_investigation_jobs SET status='failed'", "UPDATE lifecycle_investigation_jobs SET cancel_requested_at=created_at"):
            with pytest.raises(sqlite3.IntegrityError, match="investigation_immutable"):
                conn.execute(statement)
        for table in ("security_lifecycle_cases", "security_lifecycle_assessments", "lifecycle_investigation_acceptances"):
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
