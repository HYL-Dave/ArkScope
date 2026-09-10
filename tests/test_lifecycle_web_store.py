from dataclasses import asdict
import json
import sqlite3

import pytest

from src.auth_drivers.lifecycle_web_models import ModelCall, ModelReply
from src.security_lifecycle_investigation import SecurityLifecycleInvestigationStore
from src.security_lifecycle_schema import create_profile_schema, verify_profile_connection
from src.security_lifecycle_web_contract import validate_selection
from src.security_lifecycle_web_finding import WebFinding, strict_schema, validate_finding
from tests.test_security_lifecycle_web_finding import NOTICE, finding_payload, public_input, source_page
from tests.test_security_lifecycle_web_pipeline import _options


AT = "2026-09-06T01:00:00+00:00"


def setup_store(tmp_path, *, install=True):
    from src.lifecycle_web_store import LifecycleWebStore, install_web_journal

    path = tmp_path / "profile.sqlite"
    with sqlite3.connect(path) as conn:
        create_profile_schema(conn)
        conn.execute("INSERT INTO security_lifecycle_cases VALUES (?,?,?,?,?,?)", ("case-1", "sec_edgar", "source-1", "OLD", AT, AT))
        conn.commit()
        if install:
            install_web_journal(conn, at=AT)
        verify_profile_connection(conn)
    store = LifecycleWebStore(path, clock=lambda: AT)
    return path, store


def start(store, *, auth="api_key", owner="worker-1", request_key="request-1"):
    selection = validate_selection("openai", auth, "gpt-5.6-luna", "local:7")
    return store.start(case_id="case-1", observation_sha256="a" * 64, request=public_input(), selection=selection,
                       options=_options(auth), owner=owner, request_key=request_key)


def completed(store, *, usage_report=None):
    run = start(store)
    control = store.control(run["run_id"], owner="worker-1")
    store.set_phase(run["run_id"], owner="worker-1", phase="searching")
    control.reserve_model_request("search-1")
    control.bind_remote_id("search-1", "remote-search")
    control.observe_terminal("search-1", response_id="remote-search", status="completed", selection=control.selection)
    store.set_phase(run["run_id"], owner="worker-1", phase="reading_sources")
    store.add_page(run["run_id"], owner="worker-1", source_id="source-1", page=source_page(NOTICE))
    store.set_phase(run["run_id"], owner="worker-1", phase="analyzing")
    control.reserve_model_request("analysis-1")
    control.bind_remote_id("analysis-1", "remote-analysis")
    control.observe_terminal("analysis-1", response_id="remote-analysis", status="completed", selection=control.selection)
    store.complete(run["run_id"], owner="worker-1", payload=finding_payload(), source_failures={},
                   usage={"input_tokens": 20, "output_tokens": 40}, source_requests=1, usage_report=usage_report)
    return run["run_id"]


def test_web_journal_installation_is_explicit_and_preserves_existing_schema(tmp_path):
    from src.lifecycle_web_store import WebJournalError, install_web_journal

    path, store = setup_store(tmp_path, install=False)
    with pytest.raises(WebJournalError, match="web_journal_not_installed"):
        start(store)
    with sqlite3.connect(path) as conn:
        before = dict(conn.execute("SELECT name,sql FROM sqlite_master WHERE name LIKE 'security_lifecycle_%'"))
        install_web_journal(conn, at=AT)
        install_web_journal(conn, at=AT)
        verify_profile_connection(conn)
        assert dict(conn.execute("SELECT name,sql FROM sqlite_master WHERE name LIKE 'security_lifecycle_%'")) == before
        assert conn.execute("SELECT COUNT(*) FROM lifecycle_web_installation").fetchone()[0] == 1


def test_web_journal_preserves_model_authorship_without_creating_human_acceptance(tmp_path):
    path, store = setup_store(tmp_path)
    identity = completed(store)
    row = store.read(identity)
    assert row["status"] == "succeeded" and row["finding"].action == "terminal_delisting"
    assert row["selection"].auth_mode == "api_key"
    assert row["request"] == public_input()
    assert row["calls"] == {"search-1": {"remote_id": "remote-search", "terminal": "completed"},
                            "analysis-1": {"remote_id": "remote-analysis", "terminal": "completed"}}
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM security_lifecycle_assessments").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM security_lifecycle_investigation_runs").fetchone()[0] == 0


def test_start_is_idempotent_and_does_not_reset_or_replay_existing_execution(tmp_path):
    from src.lifecycle_web_store import WebJournalError

    _, store = setup_store(tmp_path)
    first = start(store)
    assert start(store)["run_id"] == first["run_id"]
    with pytest.raises(WebJournalError, match="web_investigation_running"):
        start(store, request_key="second-command")
    with pytest.raises(WebJournalError, match="web_request_identity_changed"):
        start(store, auth="chatgpt_oauth")


def test_stale_or_wrong_worker_cannot_record_provider_work(tmp_path):
    from src.lifecycle_web_store import WebJournalError

    _, store = setup_store(tmp_path)
    run = start(store)
    with pytest.raises(WebJournalError, match="web_owner_changed"):
        store.control(run["run_id"], owner="other-worker")
    store.request_cancel(run["run_id"])
    control = store.control(run["run_id"], owner="worker-1")
    with pytest.raises((ValueError, WebJournalError), match="stop_requested"):
        control.reserve_model_request("search-1")
    assert store.read(run["run_id"])["calls"] == {}


def test_recording_failure_stops_before_dispatch_and_never_fakes_completion(tmp_path, monkeypatch):
    from src.lifecycle_web_store import WebJournalError

    _, store = setup_store(tmp_path)
    run = start(store)
    control = store.control(run["run_id"], owner="worker-1")
    def fail(*args, **kwargs):
        raise WebJournalError("web_recording_unavailable")
    monkeypatch.setattr(store, "reserve_call", fail)
    with pytest.raises(WebJournalError, match="web_recording_unavailable"):
        control.reserve_model_request("search-1")
    assert control.stop_state != "running"
    assert store.read(run["run_id"])["status"] != "succeeded"


def test_cancel_ack_does_not_write_a_cancelled_remote_terminal(tmp_path):
    _, store = setup_store(tmp_path)
    run = start(store)
    control = store.control(run["run_id"], owner="worker-1")
    control.reserve_model_request("search-1")
    control.bind_remote_id("search-1", "remote-search")
    store.request_cancel(run["run_id"])
    control.request_stop()
    control.observe_interrupt_ack("search-1", "remote-search")
    control.observe_transport_loss("search-1")
    store.fail(run["run_id"], owner="worker-1", code="stop_requested", control=control)
    assert store.read(run["run_id"])["status"] == "remote_outcome_unknown"
    assert store.read(run["run_id"])["calls"]["search-1"]["terminal"] is None


@pytest.mark.parametrize("pending", [False, True])
def test_expired_lease_recovers_honestly_without_provider_or_retry(tmp_path, pending):
    _, store = setup_store(tmp_path)
    run = start(store)
    if pending:
        control = store.control(run["run_id"], owner="worker-1")
        control.reserve_model_request("search-1")
    store.recover_expired(at="2026-09-06T01:10:00+00:00")
    row = store.read(run["run_id"])
    assert row["status"] == ("remote_outcome_unknown" if pending else "failed")
    assert row["failure_code"] == "web_execution_interrupted"
    assert start(store)["run_id"] == run["run_id"]


def test_immutable_source_rows_cannot_be_rebound_after_investigation(tmp_path):
    path, store = setup_store(tmp_path)
    identity = completed(store)
    with sqlite3.connect(path) as conn:
        with pytest.raises(sqlite3.IntegrityError, match="web_immutable_record"):
            conn.execute("UPDATE lifecycle_web_pages SET page_json='{}' WHERE run_id=?", (identity,))
        with pytest.raises(sqlite3.IntegrityError, match="web_immutable_record"):
            conn.execute("UPDATE lifecycle_web_results SET payload_json='{}' WHERE run_id=?", (identity,))
    assert store.read(identity)["finding"].action == "terminal_delisting"


def test_completed_result_requires_all_owned_remote_terminals(tmp_path):
    from src.lifecycle_web_store import WebJournalError

    _, store = setup_store(tmp_path)
    run = start(store)
    with pytest.raises(WebJournalError, match="web_model_work_incomplete"):
        store.complete(run["run_id"], owner="worker-1", payload=finding_payload(), source_failures={},
                       usage={"input_tokens": None, "output_tokens": None}, source_requests=0)
    assert store.read(run["run_id"])["status"] != "succeeded"
