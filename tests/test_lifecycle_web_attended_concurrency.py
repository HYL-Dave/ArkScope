"""Large-source work must not hold the shared profile writer hostage."""

from contextlib import contextmanager
import sqlite3
from threading import Event, current_thread
import time

import pytest

from tests.test_lifecycle_web_review import context, prepare, confirm


@pytest.mark.parametrize("phase", ["decode", "finding"])
@pytest.mark.parametrize("command", ["prepare", "confirm", "execute"])
def test_attended_web_source_validation_leaves_other_profile_writers_available(tmp_path, monkeypatch, command, phase):
    from src import lifecycle_web_store as journal

    c = context(tmp_path, future=command == "execute")
    packet = prepare(c)
    if command == "execute":
        scheduled = confirm(c, packet)
        c["now"][0] = "2026-09-07T15:00:00Z"
        with sqlite3.connect(c["profile"]) as conn:
            preview = conn.execute("SELECT approved_preview_sha256 FROM ticker_identity_transitions WHERE transition_id=?",
                                   (scheduled["transition_id"],)).fetchone()[0]
    original = journal.LifecycleWebStore._decode_page if phase == "decode" else journal.validate_finding
    observations = []

    def validate(*args, **kwargs):
        with sqlite3.connect(c["profile"], timeout=0) as other:
            other.execute("UPDATE lifecycle_web_runs SET lease_until=lease_until")
        observations.append("other_writer_committed")
        return original(*args, **kwargs)

    if phase == "decode":
        monkeypatch.setattr(journal.LifecycleWebStore, "_decode_page", staticmethod(validate))
    else:
        monkeypatch.setattr(journal, "validate_finding", validate)
    if command == "prepare":
        result = prepare(c)
        assert result["ready"] and "OLD" in c["sources"]()
    elif command == "confirm":
        result = confirm(c, packet)
        assert result["status"] == "applied" and "OLD" not in c["sources"]()
    else:
        result = c["service"].execute_transition(scheduled["transition_id"], preview_sha256=preview, before_write=lambda: None)
        assert result["status"] == "applied" and "OLD" not in c["sources"]()
    assert observations == ["other_writer_committed"]
    assert "LIVE" in c["sources"]()


@pytest.mark.parametrize("change", ["source_added", "terminal_state", "cancellation", "schema_generation"])
def test_validated_web_read_rechecks_its_binding_inside_the_transaction(tmp_path, change):
    from dataclasses import asdict
    from src.lifecycle_web_schema import TRIGGERS, WebJournalError
    from src.lifecycle_journal_codec import canonical_json, digest_json
    from tests.test_security_lifecycle_web_finding import source_page

    c = context(tmp_path)
    read = c["web"].validated_read(c["run_id"])
    with c["web"].connection(write=True) as conn:
        if change == "source_added":
            material = asdict(source_page("A new source not covered by the verified read."))
            conn.execute("INSERT INTO lifecycle_web_pages VALUES (?,?,?,?)", (c["run_id"], "source-2", canonical_json(material), digest_json(material)))
        elif change == "terminal_state":
            conn.execute("UPDATE lifecycle_web_runs SET status='failed',failure_code='web_execution_failed' WHERE run_id=?", (c["run_id"],))
        elif change == "cancellation":
            conn.execute("UPDATE lifecycle_web_runs SET cancel_requested_at=? WHERE run_id=?", (c["now"][0], c["run_id"]))
        else:
            trigger = "lifecycle_web_pages_update_immutable"
            conn.execute("DROP TRIGGER " + trigger)
            conn.execute(TRIGGERS[trigger])
    with c["web"].connection(write=True) as conn:
        with pytest.raises(WebJournalError, match="^web_journal_integrity$"):
            c["web"].read_on_connection(conn, c["run_id"], validated=read)
        assert conn.in_transaction
    assert "OLD" in c["sources"]()


@pytest.mark.parametrize("when", ["during_validation", "after_validation"])
def test_page_rewrite_with_unchanged_digest_cannot_reuse_a_verified_read(tmp_path, monkeypatch, when):
    from src.lifecycle_web_schema import TRIGGERS, WebJournalError
    from src.lifecycle_web_store import LifecycleWebStore

    c = context(tmp_path)
    original, changed = LifecycleWebStore._decode_page, []

    def rewrite():
        with sqlite3.connect(c["profile"]) as conn:
            trigger = "lifecycle_web_pages_update_immutable"
            conn.execute("DROP TRIGGER " + trigger)
            conn.execute("UPDATE lifecycle_web_pages SET page_json='{}' WHERE run_id=?", (c["run_id"],))
            conn.execute(TRIGGERS[trigger])
        changed.append(True)

    if when == "during_validation":
        def decode(row):
            result = original(row)
            rewrite()
            return result
        monkeypatch.setattr(LifecycleWebStore, "_decode_page", staticmethod(decode))
        with pytest.raises(WebJournalError, match="^web_journal_integrity$"):
            c["web"].validated_read(c["run_id"])
    else:
        read = c["web"].validated_read(c["run_id"])
        rewrite()
        with c["web"].connection(write=True) as conn:
            with pytest.raises(WebJournalError, match="^web_journal_integrity$"):
                c["web"].read_on_connection(conn, c["run_id"], validated=read)
    assert changed == [True] and "OLD" in c["sources"]()


@pytest.mark.parametrize("wrong", ["profile", "run", "transaction", "unvalidated_dict"])
def test_verified_web_material_cannot_cross_its_profile_run_or_transaction(tmp_path, wrong):
    from src.lifecycle_web_schema import WebJournalError

    c = context(tmp_path)
    read = c["web"].validated_read(c["run_id"])
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
            assert c["web"]._review_binding(conn, c["run_id"]) == read.binding
        with pytest.raises(WebJournalError, match="^web_journal_integrity$"):
            c["web"].read_on_connection(conn, "other-run" if wrong == "run" else c["run_id"],
                validated=read.material if wrong == "unvalidated_dict" else read)
        assert conn.in_transaction is (wrong != "transaction")


@pytest.mark.parametrize("change", ["membership", "open_position", "observation", "active_otc", "stale"])
def test_prevalidated_sources_do_not_cache_mutable_adoption_authority(tmp_path, monkeypatch, change):
    from dataclasses import replace
    from src.lifecycle_web_store import LifecycleWebStore
    from src.portfolio_state import PortfolioStore
    from src.profile_state import ProfileStateStore
    from src.security_lifecycle_listing_evidence import _evidence
    from tests.test_security_lifecycle_provider_authority import record

    c = context(tmp_path)
    packet = prepare(c)
    original, changed = LifecycleWebStore.validated_read, []

    def read(store, identity):
        result = original(store, identity)
        assert not changed
        changed.append(True)
        if change == "membership":
            ProfileStateStore(c["profile"]).import_lists([{"name": "New", "kind": "custom", "tickers": ["OLD"]}])
        elif change == "open_position":
            portfolio = PortfolioStore(c["profile"])
            account = portfolio.ensure_manual_account()
            portfolio.upsert_manual_position(account_id=account.id, symbol="OLD", quantity=1)
        elif change == "observation":
            c["now"][0] = "2026-09-06T01:01:00Z"
            c["checks"].record(ticker="OLD", at=c["now"][0], evidence=(), diagnostics={}, blockers=("massive_unavailable",))
        elif change == "active_otc":
            c["checks"].record(ticker="OLD", at=c["now"][0], evidence=[_evidence(replace(
                record("massive_reference", "active", market="otc"), retrieved_at=c["now"][0]))], diagnostics={})
        else:
            c["now"][0] = "2026-09-10T01:00:00Z"
        return result

    monkeypatch.setattr(LifecycleWebStore, "validated_read", read)
    with pytest.raises((ValueError, RuntimeError), match="review_changed|web_review_ineligible"):
        confirm(c, packet)
    assert changed == [True] and "OLD" in c["sources"]()
    with sqlite3.connect(c["profile"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM lifecycle_web_acceptances").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM security_lifecycle_assessments").fetchone()[0] == 0


def test_permission_is_rechecked_after_expensive_source_validation(tmp_path, monkeypatch):
    from src.lifecycle_web_store import LifecycleWebStore

    c = context(tmp_path)
    packet = prepare(c)
    original, verified, permission_checks = LifecycleWebStore.validated_read, [], []
    connection, opened_writers = c["service"]._profile_connection, []

    @contextmanager
    def profile_connection(*, write):
        if write:
            opened_writers.append(True)
        with connection(write=write) as conn:
            yield conn

    def read(store, identity):
        result = original(store, identity)
        verified.append(True)
        return result

    def before_write():
        permission_checks.append(bool(verified))
        if verified:
            raise PermissionError("permission_revoked_during_validation")

    monkeypatch.setattr(LifecycleWebStore, "validated_read", read)
    monkeypatch.setattr(c["service"], "_profile_connection", profile_connection)
    with pytest.raises(PermissionError, match="permission_revoked_during_validation"):
        confirm(c, packet, before_write=before_write)
    assert permission_checks == [False, True]
    assert opened_writers == []
    with sqlite3.connect(c["profile"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM lifecycle_web_acceptances").fetchone()[0] == 0
    assert "OLD" in c["sources"]()


def test_source_validation_is_not_cached_between_user_commands(tmp_path, monkeypatch):
    from src.lifecycle_web_store import LifecycleWebStore

    c = context(tmp_path)
    original, decoded = LifecycleWebStore._decode_page, []

    def decode(row):
        decoded.append(True)
        return original(row)

    monkeypatch.setattr(LifecycleWebStore, "_decode_page", staticmethod(decode))
    packet = prepare(c)
    assert decoded == [True]
    assert confirm(c, packet)["status"] == "applied"
    assert decoded == [True, True]
    assert confirm(c, packet)["status"] == "already_applied"
    assert decoded == [True, True, True]


def test_generic_review_of_a_web_adoption_uses_the_same_verified_read(tmp_path, monkeypatch):
    from src.lifecycle_web_store import LifecycleWebStore

    c = context(tmp_path, future=True)
    packet = prepare(c)
    assert confirm(c, packet)["status"] == "scheduled"
    original, decoded = LifecycleWebStore._decode_page, []

    def decode(row):
        with sqlite3.connect(c["profile"], timeout=0) as other:
            other.execute("UPDATE lifecycle_web_runs SET lease_until=lease_until")
        decoded.append(True)
        return original(row)

    monkeypatch.setattr(LifecycleWebStore, "_decode_page", staticmethod(decode))
    current = c["service"].prepare_review(c["case_id"], assessment_id=packet["assessment_id"], options=c["options"])
    assert current["packet_sha256"] == packet["packet_sha256"]
    repeated = c["service"].confirm_review(c["case_id"], assessment_id=packet["assessment_id"],
        packet_sha256=packet["packet_sha256"], action=packet["action"], options=c["options"], before_write=lambda: None)
    assert repeated["status"] == "scheduled" and "OLD" in c["sources"]()
    assert decoded == [True, True]


def test_adoption_prevalidation_never_releases_a_callers_transaction(tmp_path):
    from src.lifecycle_web_review import assessment_id_for, validated_adoption_read

    c = context(tmp_path, future=True)
    assert confirm(c, prepare(c))["status"] == "scheduled"
    with c["web"].connection(write=True) as conn:
        with pytest.raises(RuntimeError, match="^caller_transaction_open$"):
            validated_adoption_read(c["service"], conn=conn, assessment_id=assessment_id_for(c["run_id"]))
        assert conn.in_transaction


def test_attended_confirmation_cannot_starve_a_real_current_worker(tmp_path, monkeypatch):
    from src import lifecycle_web_store as journal
    from src.auth_drivers.lifecycle_web_models import WebCredential
    from src.lifecycle_investigation.controller import InvestigationController
    from src.lifecycle_investigation.news import LocalNews
    from src.lifecycle_investigation.schema import install_journal
    from src.lifecycle_investigation.store import InvestigationStore
    from src.lifecycle_investigation.target import TargetPreflight
    from src.auth_drivers.lifecycle_web_models import credential_generation
    from tests.lifecycle_investigation_fixtures import completed_runner, synthetic_credentials, wait_done
    from tests.test_lifecycle_investigation_findings import NOTICE
    from tests.test_lifecycle_investigation_news import corpus

    c = context(tmp_path)
    packet = prepare(c)
    with sqlite3.connect(c["profile"]) as conn:
        install_journal(conn, at=c["now"][0])
    credentials, rows, route = synthetic_credentials()
    preflight = TargetPreflight(c["service"], credential_store=credentials, route_loader=lambda: route)
    binding, _ = preflight._material("OLD")
    news_path = corpus(tmp_path, body=NOTICE)
    store = InvestigationStore(c["profile"], clock=lambda: c["now"][0])
    started, validating, progress = Event(), Event(), []
    main_thread = current_thread()
    original = journal.validate_finding
    connect = sqlite3.connect

    def scaled_connection(*args, **kwargs):
        if kwargs.get("timeout") in {journal.JOURNAL_BUSY_SECONDS, 10}:
            kwargs["timeout"] = 0.05
        return connect(*args, **kwargs)

    async def runner(*args, **kwargs):
        started.set()
        assert validating.wait(3)
        result = await completed_runner(*args, **kwargs)
        progress.append("model_and_source_terminal")
        return result

    controller = InvestigationController(store,
        credential_loader=lambda selected: WebCredential(selected, api_key="synthetic", generation=credential_generation(rows[0])),
        news_factory=lambda: LocalNews(news_path, None), runner=runner, heartbeat_seconds=0.02)
    try:
        run = controller.start(binding=binding, request_key="other-worker")
        assert started.wait(3)

        def validate(*args, **kwargs):
            if current_thread() is main_thread:
                validating.set()
                deadline = time.monotonic() + 3
                while controller.is_local_running(run["run_id"]) and time.monotonic() < deadline:
                    time.sleep(0.01)
                assert not controller.is_local_running(run["run_id"])
                with connect(c["profile"]) as conn:
                    assert conn.execute("SELECT status,failure_code FROM lifecycle_investigation_jobs WHERE run_id=?", (run["run_id"],)).fetchone() == ("succeeded", None)
            return original(*args, **kwargs)

        monkeypatch.setattr(sqlite3, "connect", scaled_connection)
        monkeypatch.setattr(journal, "validate_finding", validate)
        result = confirm(c, packet)
        assert result["status"] == "applied"
        assert wait_done(controller, run["run_id"])["status"] == "succeeded"
        assert progress == ["model_and_source_terminal"]
        assert "OLD" not in c["sources"]() and "LIVE" in c["sources"]()
    finally:
        validating.set()
        controller.close()
