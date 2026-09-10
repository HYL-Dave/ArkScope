import sqlite3
from copy import deepcopy

import pytest

from tests.test_security_lifecycle_terminal_workflow import setup_workflow


def running(tmp_path, *, ticker="OLD"):
    from src.lifecycle_investigation.runtime import InvestigationRuntime
    from src.lifecycle_investigation.schema import install_journal
    from src.lifecycle_investigation.store import InvestigationStore
    from src.lifecycle_investigation.target import Target
    from src.lifecycle_web_store import _sha
    c = setup_workflow(tmp_path, assess=False, event_available=False)
    with sqlite3.connect(c["profile"]) as conn:
        install_journal(conn, at=c["now"][0])
    binding = {"version": 2, "language": "en", "target": Target(ticker=ticker, as_of="2026-09-08").model_dump(),
        "selection": {"provider": "anthropic", "model": "claude-sonnet-5", "auth_mode": "claude_code_oauth", "credential_id": "local:7"},
        "runtime": InvestigationRuntime().model_dump(), "effort": "high", "credential_generation": "generation-1",
        "provider_observations": [], "provider_sha256": _sha([])}
    store = InvestigationStore(c["profile"], clock=lambda: c["now"][0])
    identity = store.start(binding=binding, owner="worker", request_key="explicit-click")["run_id"]
    return c, store, identity, binding


def test_v2_installation_preserves_v1_and_requires_no_case(tmp_path):
    from src.lifecycle_investigation.schema import install_journal, verify_journal
    from src.lifecycle_web_schema import install_web_journal, verify_web_journal
    c = setup_workflow(tmp_path, assess=False, event_available=False)
    with sqlite3.connect(c["profile"]) as conn:
        install_web_journal(conn, at=c["now"][0])
        before = list(conn.execute("SELECT name,sql FROM sqlite_master WHERE name LIKE 'lifecycle_web_%'"))
        install_journal(conn, at=c["now"][0])
        verify_journal(conn)
        verify_web_journal(conn)
        assert before == list(conn.execute("SELECT name,sql FROM sqlite_master WHERE name LIKE 'lifecycle_web_%'"))
        assert not list(conn.execute("PRAGMA foreign_key_list(lifecycle_investigation_jobs)"))
        install_journal(conn, at=c["now"][0])


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
    from src.lifecycle_web_store import WebJournalError
    from src.security_lifecycle_web_contract import WebContractError

    classes = {"model": WebModelError, "journal": WebJournalError, "contract": WebContractError,
        "source": SourceReadError, "value": ValueError, "unexpected": RuntimeError}
    expected = "provider_call_failed" if kind not in {"value", "unexpected"} and message == "provider_call_failed" else "web_execution_failed"
    assert safe_code(classes[kind](message)) == expected
    assert safe_code(ValueError("investigation_recording_unavailable")) == "investigation_recording_unavailable"


def test_current_error_projection_keeps_the_unavailable_route_code():
    from src.lifecycle_investigation.store import safe_code
    from src.model_routing import ModelRouteUnavailable

    assert safe_code(ModelRouteUnavailable()) == "model_route_unavailable"
