"""Current source validation must preserve writer availability and approval binding."""

from contextlib import contextmanager
import sqlite3

import pytest

from src.lifecycle_investigation import adoption, review, store as journal
from src.lifecycle_journal_codec import canonical_json, digest_json
from tests.test_lifecycle_investigation_review import context, prepare, confirm, rows
from tests.test_ticker_identity_history import damage_saved_rows


def observe_source_work(monkeypatch, callback, *, phase="decode"):
    if phase == "decode":
        original = journal._decoded
        def decode(raw, digest):
            value = original(raw, digest)
            if isinstance(value, dict) and "text" in value and "text_sha256" in value:
                callback()
            return value
        monkeypatch.setattr(journal, "_decoded", decode)
    else:
        original = adoption.validate_finding
        def validate(*args, **kwargs):
            callback()
            return original(*args, **kwargs)
        monkeypatch.setattr(adoption, "validate_finding", validate)


@pytest.mark.parametrize("phase", ["decode", "finding"])
@pytest.mark.parametrize("command", ["prepare", "confirm", "execute", "generic_prepare", "generic_confirm"])
@pytest.mark.parametrize("journal_mode", ["DELETE", "WAL"])
def test_current_source_validation_leaves_profile_writers_available(tmp_path, monkeypatch, command, phase, journal_mode):
    c = context(tmp_path, future=command not in {"prepare", "confirm"})
    with sqlite3.connect(c["profile"]) as conn:
        assert conn.execute(f"PRAGMA journal_mode={journal_mode}").fetchone()[0] == journal_mode.lower()
        conn.execute("CREATE TABLE test_writer_progress (value INTEGER)")
        conn.execute("INSERT INTO test_writer_progress VALUES (0)")
    packet = prepare(c)
    if command not in {"prepare", "confirm"}:
        scheduled = confirm(c, packet)
        assert scheduled["status"] == "scheduled"
        with sqlite3.connect(c["profile"]) as conn:
            preview = conn.execute("SELECT approved_preview_sha256 FROM ticker_identity_transitions").fetchone()[0]
    observations = []
    def other_writer():
        with sqlite3.connect(c["profile"], timeout=0) as other:
            other.execute("UPDATE test_writer_progress SET value=value+1")
        observations.append("committed")
    observe_source_work(monkeypatch, other_writer, phase=phase)
    if command == "prepare":
        assert prepare(c)["ready"]
        assert "OLD" in c["sources"]()
    elif command == "confirm":
        assert confirm(c, packet)["status"] == "applied"
        assert "OLD" not in c["sources"]()
    elif command == "execute":
        c["now"][0] = "2026-09-09T15:00:00Z"
        assert c["service"].execute_transition(scheduled["transition_id"], preview_sha256=preview,
            before_write=lambda: None)["status"] == "applied"
    elif command == "generic_prepare":
        current = c["service"].prepare_review(packet["case_id"], assessment_id=packet["assessment_id"], options=c["options"])
        assert current["packet_sha256"] == packet["packet_sha256"]
    else:
        current = c["service"].confirm_review(packet["case_id"], assessment_id=packet["assessment_id"],
            packet_sha256=packet["packet_sha256"], action=packet["action"], options=c["options"], before_write=lambda: None)
        assert current["status"] == "scheduled"
    assert observations == ["committed"]
    with sqlite3.connect(c["profile"]) as conn:
        assert conn.execute("SELECT value FROM test_writer_progress").fetchone()[0] == 1
    assert "LIVE" in c["sources"]()


@pytest.mark.parametrize("change", ["source_added", "cancellation_after_trigger_bypass", "result_rewritten", "schema_generation", "model_request_added", "call_added"])
def test_current_validated_read_rechecks_its_binding_inside_the_transaction(tmp_path, change):
    c = context(tmp_path)
    read = adoption.validated_read(c["profile"], c["run_id"])
    with sqlite3.connect(c["profile"]) as conn:
        if change == "source_added":
            material = next(iter(c["investigation"].read(c["run_id"])["sources"].values()))
            conn.execute("INSERT INTO lifecycle_investigation_sources VALUES (?,?,?,?)",
                (c["run_id"], "source-2", canonical_json(material), digest_json(material)))
        elif change == "cancellation_after_trigger_bypass":
            damage_saved_rows(conn, "lifecycle_investigation_jobs",
                "UPDATE lifecycle_investigation_jobs SET cancel_requested_at=?", (c["now"][0],))
        elif change == "model_request_added":
            ordinal = conn.execute("SELECT MAX(ordinal)+1 FROM lifecycle_investigation_steps").fetchone()[0]
            material = {"call_id": "unbound", "phase": "analysis", "supplied_passages": []}
            conn.execute("INSERT INTO lifecycle_investigation_steps VALUES (?,?,?,?,?,?)",
                (c["run_id"], ordinal, "model_request", canonical_json(material), digest_json(material), c["now"][0]))
        elif change == "call_added":
            conn.execute("INSERT INTO lifecycle_investigation_calls (run_id,call_id) VALUES (?,?)", (c["run_id"], "unbound"))
        elif change == "result_rewritten":
            damage_saved_rows(conn, "lifecycle_investigation_results", "UPDATE lifecycle_investigation_results SET payload_sha256=?", ("0" * 64,))
        else:
            conn.execute("CREATE TABLE unrelated_schema_change (value TEXT)")
    with c["investigation"].connection(write=True) as conn:
        with pytest.raises(ValueError, match="^investigation_integrity$"):
            adoption.read_on_connection(conn, c["run_id"], validated=read)
        assert conn.in_transaction
    assert "OLD" in c["sources"]()


@pytest.mark.parametrize("when", ["during_validation", "after_validation"])
def test_current_source_rewrite_with_unchanged_digest_invalidates_verified_read(tmp_path, monkeypatch, when):
    c = context(tmp_path)
    changed = []
    def rewrite():
        with sqlite3.connect(c["profile"]) as conn:
            damage_saved_rows(conn, "lifecycle_investigation_sources",
                "UPDATE lifecycle_investigation_sources SET payload_json='{}'")
        changed.append(True)
    if when == "during_validation":
        observe_source_work(monkeypatch, rewrite, phase="finding")
        with pytest.raises(ValueError, match="^investigation_integrity$"):
            adoption.validated_read(c["profile"], c["run_id"])
    else:
        read = adoption.validated_read(c["profile"], c["run_id"])
        rewrite()
        with c["investigation"].connection(write=True) as conn:
            with pytest.raises(ValueError, match="^investigation_integrity$"):
                adoption.read_on_connection(conn, c["run_id"], validated=read)
    assert changed == [True] and "OLD" in c["sources"]()


@pytest.mark.parametrize("wrong", ["profile", "run", "transaction", "unvalidated_dict"])
def test_current_verified_material_cannot_cross_profile_run_or_transaction(tmp_path, wrong):
    c = context(tmp_path)
    read = adoption.validated_read(c["profile"], c["run_id"])
    path = c["profile"]
    if wrong == "profile":
        path = tmp_path / "copied-profile.db"
        with sqlite3.connect(c["profile"]) as source, sqlite3.connect(path) as target:
            source.backup(target)
            target.execute(f"PRAGMA schema_version={read.binding[-1]}")
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        if wrong != "transaction":
            conn.execute("BEGIN IMMEDIATE")
        if wrong == "profile":
            assert adoption.binding_on_connection(conn, c["run_id"]) == read.binding
        with pytest.raises(ValueError, match="^investigation_integrity$"):
            adoption.read_on_connection(conn, "li_other" if wrong == "run" else c["run_id"],
                validated=read.material if wrong == "unvalidated_dict" else read)
        assert conn.in_transaction is (wrong != "transaction")


@pytest.mark.parametrize("change", ["membership", "open_position", "observation", "active_otc", "stale"])
def test_current_prevalidated_sources_do_not_cache_mutable_adoption_authority(tmp_path, monkeypatch, change):
    from dataclasses import replace
    from src.portfolio_state import PortfolioStore
    from src.profile_state import ProfileStateStore
    from src.security_lifecycle_listing_evidence import _evidence
    from tests.test_security_lifecycle_provider_authority import record
    c = context(tmp_path)
    packet = prepare(c)
    original, changed = review.validated_read, []
    def read(path, identity):
        result = original(path, identity)
        assert not changed
        changed.append(True)
        if change == "membership":
            ProfileStateStore(c["profile"]).import_lists([{"name": "New", "kind": "custom", "tickers": ["OLD"]}])
        elif change == "open_position":
            portfolio = PortfolioStore(c["profile"])
            account = portfolio.ensure_manual_account()
            portfolio.upsert_manual_position(account_id=account.id, symbol="OLD", quantity=1)
        elif change == "observation":
            c["now"][0] = "2026-09-08T01:01:00Z"
            c["checks"].record(ticker="OLD", at=c["now"][0], evidence=(), diagnostics={}, blockers=("massive_unavailable",))
        elif change == "active_otc":
            c["checks"].record(ticker="OLD", at=c["now"][0], evidence=[_evidence(replace(
                record("massive_reference", "active", market="otc"), retrieved_at=c["now"][0]))], diagnostics={})
        else:
            c["now"][0] = "2026-09-12T01:00:00Z"
        return result
    monkeypatch.setattr(review, "validated_read", read)
    with pytest.raises((ValueError, RuntimeError), match="review_changed|web_review_ineligible"):
        confirm(c, packet)
    assert changed == [True] and "OLD" in c["sources"]()
    with sqlite3.connect(c["profile"]) as conn:
        for table in ("lifecycle_investigation_acceptances", "security_lifecycle_assessments", "security_lifecycle_cases"):
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_current_permission_is_rechecked_after_expensive_validation_before_opening_writer(tmp_path, monkeypatch):
    c = context(tmp_path)
    packet = prepare(c)
    original, verified, permission_checks, opened_writers = review.validated_read, [], [], []
    connection = c["service"]._profile_connection
    @contextmanager
    def profile_connection(*, write):
        if write:
            opened_writers.append(True)
        with connection(write=write) as conn:
            yield conn
    def read(path, identity):
        result = original(path, identity)
        verified.append(True)
        return result
    def before_write():
        permission_checks.append(bool(verified))
        if verified:
            raise PermissionError("permission_revoked_during_validation")
    monkeypatch.setattr(review, "validated_read", read)
    monkeypatch.setattr(c["service"], "_profile_connection", profile_connection)
    before = rows(c)
    with pytest.raises(PermissionError, match="permission_revoked_during_validation"):
        confirm(c, packet, before_write=before_write)
    assert permission_checks == [False, True] and opened_writers == []
    assert rows(c) == before


def test_current_source_validation_is_not_cached_between_user_commands(tmp_path, monkeypatch):
    c = context(tmp_path)
    decoded = []
    observe_source_work(monkeypatch, lambda: decoded.append(True))
    packet = prepare(c)
    assert decoded == [True]
    assert confirm(c, packet)["status"] == "applied"
    assert decoded == [True, True]
    assert confirm(c, packet)["status"] == "already_applied"
    assert decoded == [True, True, True]


def test_current_confirmation_rejects_source_added_after_validation(tmp_path, monkeypatch):
    c = context(tmp_path)
    packet = prepare(c)
    original = review.validated_read
    def read(path, identity):
        checked = original(path, identity)
        material = next(iter(checked.material["sources"].values()))
        with sqlite3.connect(c["profile"]) as conn:
            conn.execute("INSERT INTO lifecycle_investigation_sources VALUES (?,?,?,?)",
                (identity, "source-2", canonical_json(material), digest_json(material)))
        return checked
    monkeypatch.setattr(review, "validated_read", read)
    with pytest.raises(ValueError, match="^investigation_integrity$"):
        confirm(c, packet)
    assert "OLD" in c["sources"]()
    with sqlite3.connect(c["profile"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM lifecycle_investigation_sources").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM lifecycle_investigation_acceptances").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM ticker_identity_transitions").fetchone()[0] == 0


def test_current_adoption_prevalidation_never_releases_callers_transaction(tmp_path):
    c = context(tmp_path, future=True)
    assert confirm(c, prepare(c))["status"] == "scheduled"
    with c["investigation"].connection(write=True) as conn:
        with pytest.raises(RuntimeError, match="^caller_transaction_open$"):
            review.validated_adoption_read(c["service"], conn=conn, assessment_id=review.assessment_id_for(c["run_id"]))
        assert conn.in_transaction


def test_current_confirmation_does_not_starve_a_real_investigation_worker(tmp_path, monkeypatch):
    from threading import Event, current_thread
    from src.auth_drivers.lifecycle_web_models import WebCredential
    from src.lifecycle_investigation.controller import InvestigationController
    from src.lifecycle_investigation.news import LocalNews
    from tests.lifecycle_investigation_fixtures import completed_runner, wait_done
    c = context(tmp_path)
    with sqlite3.connect(c["profile"]) as conn:
        assert conn.execute("PRAGMA journal_mode=DELETE").fetchone()[0] == "delete"
    packet = prepare(c)
    binding, _ = c["preflight"]._material("OLD")
    started, validating, finished = Event(), Event(), Event()
    original, main_thread = adoption.validate_finding, current_thread()
    async def runner(*args, **kwargs):
        started.set()
        assert validating.wait(3)
        result = await completed_runner(*args, **kwargs)
        finished.set()
        return result
    service = InvestigationController(c["investigation"],
        credential_loader=lambda selected: WebCredential(selected, api_key="synthetic", generation=binding["credential_generation"]),
        news_factory=lambda: LocalNews(tmp_path / "news.db", None, clock=lambda: c["now"][0]),
        runner=runner, heartbeat_seconds=.02)
    try:
        identity = service.start(binding=binding, request_key="other-worker")["run_id"]
        assert started.wait(3)
        def validate(*args, **kwargs):
            if current_thread() is main_thread:
                validating.set()
                assert finished.wait(3)
                assert wait_done(service, identity)["status"] == "succeeded"
            return original(*args, **kwargs)
        monkeypatch.setattr(adoption, "validate_finding", validate)
        assert confirm(c, packet)["status"] == "applied"
        assert wait_done(service, identity)["status"] == "succeeded"
        assert "OLD" not in c["sources"]() and "LIVE" in c["sources"]()
    finally:
        validating.set()
        service.close()
