import json
import sqlite3

import pytest

from tests.test_security_lifecycle_population import stores, sec as observe, persist


def test_retirement_disposal_is_scoped_and_preserves_other_data(tmp_path):
    from src.lifecycle_investigation.disposal import preview_disposal, apply_disposal_stage
    from src.lifecycle_investigation.schema import install_journal
    market, profile = stores(tmp_path)
    event = observe(market, ticker="OLD", ref="old")
    persist(profile, event)
    with sqlite3.connect(profile) as conn:
        install_journal(conn, at="2026-09-08T00:00:00Z")
        conn.execute("CREATE TABLE unrelated(value TEXT)")
        conn.execute("INSERT INTO unrelated VALUES ('keep')")
    plan = preview_disposal(market, profile)
    assert plan["counts"]["discard_cases"] == 1
    assert plan["counts"]["discard_observations"] == 1
    for stage, path in (("profile", profile), ("market", market)):
        result = apply_disposal_stage(path, plan, stage=stage, approval_sha256=plan["approval_sha256"],
            backup_path=tmp_path / f"{stage}-backup.sqlite", app_stopped=True, profile_path=profile)
        assert result["status"] == "completed"
        assert apply_disposal_stage(path, plan, stage=stage, approval_sha256=plan["approval_sha256"],
            backup_path=tmp_path / "unused", app_stopped=True, profile_path=profile)["status"] == "already_completed"
    with sqlite3.connect(profile) as conn:
        assert conn.execute("SELECT * FROM unrelated").fetchall() == [("keep",)]
        assert conn.execute("SELECT COUNT(*) FROM security_lifecycle_cases").fetchone()[0] == 0


def test_disposal_stops_for_new_dependency_and_never_requires_quiescing_unrelated_sa(tmp_path):
    from src.lifecycle_investigation.disposal import preview_disposal, apply_disposal_stage
    from src.lifecycle_investigation.schema import install_journal
    market, profile = stores(tmp_path)
    event = observe(market, ticker="OLD", ref="old")
    case = persist(profile, event)
    with sqlite3.connect(profile) as conn:
        install_journal(conn, at="2026-09-08T00:00:00Z")
    plan = preview_disposal(market, profile)
    with sqlite3.connect(profile) as conn:
        conn.execute("CREATE TABLE new_dependency(case_id TEXT REFERENCES security_lifecycle_cases(case_id))")
        conn.execute("INSERT INTO new_dependency VALUES (?)", (case,))
    with pytest.raises(ValueError, match="disposal_changed"):
        apply_disposal_stage(profile, plan, stage="profile", approval_sha256=plan["approval_sha256"],
            backup_path=tmp_path / "backup", app_stopped=True)
    assert preview_disposal(market, profile)["counts"]["retained_cases"] == 1


@pytest.mark.parametrize("journal_installed", (False, True))
def test_current_composition_excludes_unretained_sec_without_a_cutover(tmp_path, journal_installed):
    from src.lifecycle_investigation.schema import install_journal
    from src.security_lifecycle_investigation import compose_security_lifecycle
    from src.security_lifecycle_provider_store import ProviderCheckStore
    market, profile = stores(tmp_path)
    event = observe(market, ticker="OLD", ref="old")
    persist(profile, event)
    observe(market, ticker="UNSAVED", ref="unsaved")
    persist(profile, {"source": "sec_edgar", "source_ref": "missing", "ticker": "MISSING"})
    ProviderCheckStore(profile).record(ticker="LISTED", at="2026-09-08T00:00:00Z", evidence=(), diagnostics={})
    if journal_installed:
        with sqlite3.connect(profile) as conn:
            install_journal(conn, at="2026-09-08T00:00:00Z")
    cases = compose_security_lifecycle(str(market), str(profile))["cases"]
    assert [(case["source"], case["ticker"]) for case in cases] == [("listing_authority", "LISTED")]


@pytest.mark.parametrize("journal_installed", (False, True))
def test_retained_sec_action_history_is_readable_but_not_background_intake(tmp_path, monkeypatch, journal_installed):
    from src.lifecycle_investigation.schema import install_journal
    from src.security_lifecycle_investigation import compose_security_lifecycle
    from src.security_lifecycle_provider_store import ProviderCheckStore
    from src.service import security_lifecycle_automation_scheduler as scheduler
    from src.tools.security_lifecycle_tools import SecurityLifecycleReadService
    from src.ticker_identity_transition import profile_snapshot_sha256
    from tests.test_ticker_identity_transition import _transition_connection, _insert_due_transition

    market, _ = stores(tmp_path)
    profile = tmp_path / "profile_state.db"
    with _transition_connection(tmp_path) as conn:
        _insert_due_transition(conn, transition_id="slt_retained", approval_authority="attended_user", approved_at="2026-09-08T00:00:00Z")
        preview = {"source_ticker": "OLD", "successor_ticker": "NEW"}
        preview["preview_sha256"] = profile_snapshot_sha256(preview)
        conn.execute("UPDATE ticker_identity_transitions SET approved_preview_json=?,approved_preview_sha256=?",
                     (json.dumps(preview), preview["preview_sha256"]))
        conn.commit()
        if journal_installed:
            install_journal(conn, at="2026-09-08T00:00:00Z")
    persist(profile, observe(market, ticker="DISCARD", ref="discard"))
    ProviderCheckStore(profile).record(ticker="LISTED", at="2026-09-08T00:00:00Z", evidence=(), diagnostics={})
    cases = compose_security_lifecycle(str(market), str(profile))["cases"]
    assert {"OLD", "LISTED"} <= {case["ticker"] for case in cases}
    service = SecurityLifecycleReadService(market_db_path=str(market), profile_db_path=str(profile), source_loader=lambda: {})
    retained = next(case for case in service._cases() if case["ticker"] == "OLD")
    assert retained["ticker_transition"]["transition_id"] == "slt_retained"
    assert retained["assessment_history"][0]["assessment_id"] == "sla_1"
    monkeypatch.setattr(scheduler, "_market_path", lambda: market)
    monkeypatch.setattr(scheduler, "_profile_path", lambda: profile)
    assert [case["ticker"] for case in scheduler._load_cases()] == ["LISTED"]


def test_market_dependencies_are_retained_before_profile_disposal(tmp_path):
    from src.lifecycle_investigation.disposal import preview_disposal
    market, profile = stores(tmp_path)
    event = observe(market, ticker="OLD", ref="old")
    persist(profile, event)
    with sqlite3.connect(market) as conn:
        conn.execute("CREATE TABLE independent_receipt(id INTEGER PRIMARY KEY, observation_id INTEGER REFERENCES security_lifecycle_observations(id))")
        conn.execute("INSERT INTO independent_receipt VALUES (1,?)", (event["id"],))
    plan = preview_disposal(market, profile)
    assert plan["counts"]["discard_cases"] == plan["counts"]["discard_observations"] == 0
    assert plan["retained"][0]["reason"] == "market_dependency"


def test_disposal_market_stage_requires_profile_receipt_and_receipts_cannot_be_forged(tmp_path):
    from src.lifecycle_investigation.disposal import preview_disposal, apply_disposal_stage
    from src.lifecycle_investigation.schema import install_journal
    market, profile = stores(tmp_path)
    persist(profile, observe(market, ticker="OLD", ref="old"))
    with sqlite3.connect(profile) as conn:
        install_journal(conn, at="2026-09-08T00:00:00Z")
    plan = preview_disposal(market, profile)
    arguments = dict(approval_sha256=plan["approval_sha256"], backup_path=tmp_path / "backup", app_stopped=True, profile_path=profile)
    with pytest.raises(ValueError, match="disposal_profile_stage_required"):
        apply_disposal_stage(market, plan, stage="market", **arguments)
    receipt = apply_disposal_stage(profile, plan, stage="profile", **arguments)
    assert len(receipt["backup_sha256"]) == 64
    with sqlite3.connect(profile) as conn:
        with pytest.raises(sqlite3.IntegrityError, match="disposal_receipt_immutable"):
            conn.execute("UPDATE lifecycle_legacy_disposal_receipts SET receipt_json='{}'")


def test_disposal_deletes_draft_dependencies_but_retains_human_acceptance(tmp_path):
    from src.lifecycle_investigation.disposal import preview_disposal, apply_disposal_stage
    from src.lifecycle_investigation.schema import install_journal
    from src.security_lifecycle_investigation import SecurityLifecycleInvestigationStore, observation_fingerprint
    market, profile = stores(tmp_path)
    for ticker in ("DRAFT", "HUMAN"):
        event = observe(market, ticker=ticker, ref=ticker)
        case = persist(profile, event)
        with sqlite3.connect(profile) as conn:
            store = SecurityLifecycleInvestigationStore(conn)
            fingerprint = observation_fingerprint(event)
            assessment = store.create_assessment(case_id=case, relevance="direct_tracked_security", confidence="high", author="human",
                conclusion="Preserve an accepted user assessment.", impact_summary="No change.", outcomes=("no_tracked_security_change",),
                citations=({"reference_kind": "observation", "cited_content_sha256": fingerprint},),
                observation_fingerprint_sha256=fingerprint, at="2026-09-08T00:00:00Z")
            if ticker == "HUMAN":
                store.accept_assessment(assessment, observation_fingerprint_sha256=fingerprint, acceptance_authority="human", at="2026-09-08T00:00:00Z")
    with sqlite3.connect(profile) as conn:
        install_journal(conn, at="2026-09-08T00:00:00Z")
    plan = preview_disposal(market, profile)
    assert plan["counts"]["discard_cases"] == 1
    apply_disposal_stage(profile, plan, stage="profile", approval_sha256=plan["approval_sha256"], backup_path=tmp_path / "backup", app_stopped=True)
    with sqlite3.connect(profile) as conn:
        assert conn.execute("SELECT ticker FROM security_lifecycle_cases").fetchall() == [("HUMAN",)]
        assert conn.execute("SELECT COUNT(*) FROM security_lifecycle_assessments").fetchone()[0] == 1


def test_v1_web_dependencies_are_deleted_atomically_and_their_guards_restored(tmp_path, monkeypatch):
    from src.lifecycle_investigation import disposal
    from src.lifecycle_investigation.schema import install_journal
    from src.lifecycle_web_schema import verify_web_journal
    from tests.test_lifecycle_web_store import setup_store, completed
    market, _ = stores(tmp_path)
    profile, store = setup_store(tmp_path)
    identity = completed(store)
    observe(market, ticker="OLD", ref="source-1")
    with sqlite3.connect(profile) as conn:
        install_journal(conn, at="2026-09-08T00:00:00Z")
    plan = disposal.preview_disposal(market, profile)
    assert plan["counts"]["discard_cases"] == 1
    real_hash = disposal._sha_file
    monkeypatch.setattr(disposal, "_sha_file", lambda path: (_ for _ in ()).throw(OSError("receipt publication failed")))
    with pytest.raises(OSError, match="receipt publication failed"):
        disposal.apply_disposal_stage(profile, plan, stage="profile", approval_sha256=plan["approval_sha256"],
            backup_path=tmp_path / "failed-backup", app_stopped=True)
    assert store.read(identity)["status"] == "succeeded"
    with sqlite3.connect(profile) as conn:
        verify_web_journal(conn)
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name='lifecycle_legacy_disposal_receipts'").fetchall()
    monkeypatch.setattr(disposal, "_sha_file", real_hash)
    disposal.apply_disposal_stage(profile, plan, stage="profile", approval_sha256=plan["approval_sha256"],
        backup_path=tmp_path / "successful-backup", app_stopped=True)
    with sqlite3.connect(profile) as conn:
        verify_web_journal(conn)
        assert conn.execute("SELECT COUNT(*) FROM lifecycle_web_runs").fetchone()[0] == 0
        assert not conn.execute("PRAGMA foreign_key_check").fetchall()
