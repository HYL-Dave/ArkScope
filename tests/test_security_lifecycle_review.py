"""One attended confirmation, real transactions, and no external execution."""

import json
import socket
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta
from threading import Barrier

import pytest

from src.profile_state import ProfileStateStore
from src.security_lifecycle_investigation import SecurityLifecycleInvestigationStore, observation_fingerprint
from src.ticker_identity_service import TickerIdentityConflict, TickerIdentityService
from src.ticker_identity_transition import TransitionOptions
from tests.test_security_lifecycle_terminal_workflow import setup_workflow


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("review_must_not_use_network")
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)


def context(tmp_path, *, accepted=False):
    c = setup_workflow(tmp_path, ended="2023-05-16", assess=True, event_available=False)
    with sqlite3.connect(c["profile"]) as conn:
        store = SecurityLifecycleInvestigationStore(conn)
        assessment = store.list_assessments(c["case_id"])[0]
        c["assessment_id"] = assessment["assessment_id"]
        if not accepted:
            conn.execute("DELETE FROM security_lifecycle_action_proposals")
            conn.execute("UPDATE security_lifecycle_assessments SET status='draft',accepted_at=NULL,acceptance_authority=NULL")
    c["options"] = TransitionOptions(execute_on=c["ended"])
    return c


def prepare(c):
    return c["service"].prepare_review(c["case_id"], assessment_id=c["assessment_id"], options=c["options"])


def confirm(c, packet, *, before_write=lambda: None):
    return c["service"].confirm_review(c["case_id"], assessment_id=c["assessment_id"],
        packet_sha256=packet["packet_sha256"], action=packet["action"], options=c["options"], before_write=before_write)


def rows(c):
    with sqlite3.connect(c["profile"]) as conn:
        return tuple(conn.iterdump())


def test_prepare_review_is_read_only_and_does_not_fake_acceptance(tmp_path):
    c = context(tmp_path)
    before = rows(c)
    packet = prepare(c)
    assert packet["ready"] is True, packet
    assert packet["action"] == "terminal_delisting"
    assert packet["finding"]["effective_date"] == c["ended"]
    assert packet["effects"]["suppression"]["hide_source"] is True
    assert packet["effects"]["sa_tracking_memberships"]
    assert rows(c) == before
    assert prepare(c) == packet


@pytest.mark.parametrize("accepted", (False, True))
def test_confirmation_applies_exact_reviewed_action_with_one_command(tmp_path, accepted):
    c = context(tmp_path, accepted=accepted)
    packet = prepare(c)
    result = confirm(c, packet)
    assert result["status"] == "applied", result
    assert result["current_effects_match"] is True
    assert result["packet_sha256"] == packet["packet_sha256"]
    assert c["sources"]() == {"LIVE": ("manual_lists",)}
    with sqlite3.connect(c["profile"]) as conn:
        store = SecurityLifecycleInvestigationStore(conn)
        assessment = store.get_assessment(c["assessment_id"])
        assert assessment["status"] == "accepted"
        assert conn.execute("SELECT COUNT(*) FROM ticker_identity_transitions").fetchone()[0] == 1
        receipt = conn.execute("SELECT approval_authority,approved_preview_json FROM ticker_identity_transitions").fetchone()
        assert receipt[0] == "attended_user"
        confirmation = json.loads(receipt[1])["review_confirmation"]
        assert confirmation["packet_sha256"] == packet["packet_sha256"]
        assert confirmation["actor"] == "attended_user"
        assert confirmation["action"] == packet["action"]
        assert confirmation["version"] == 1


def test_existing_acceptance_is_not_a_confirmation_and_cannot_schedule(tmp_path):
    c = context(tmp_path, accepted=True)
    prepare(c)
    assert c["service"].list_due_transitions(on_date="2026-09-05", limit=20, allow_automation_approved=True) == []
    assert "OLD" in c["sources"]()


@pytest.mark.parametrize("change", ("membership", "finding", "source", "evidence"))
def test_confirmation_rejects_changed_material_without_accepting_draft(tmp_path, change):
    c = context(tmp_path)
    packet = prepare(c)
    if change == "membership":
        ProfileStateStore(c["profile"]).import_lists([{"name": "New", "kind": "custom", "tickers": ["OLD"]}])
    elif change == "finding":
        with sqlite3.connect(c["profile"]) as conn:
            conn.execute("UPDATE security_lifecycle_assessments SET conclusion='A different conclusion'")
    elif change == "source":
        c["checks"].record(ticker="OLD", at="2026-09-05T01:01:00Z", evidence=c["material"], diagnostics={})
        c["now"][0] = "2026-09-05T01:01:00Z"
    else:
        with sqlite3.connect(c["profile"]) as conn:
            store = SecurityLifecycleInvestigationStore(conn)
            store.add_evidence(case_id=c["case_id"], run_id=None, kind="manual_text", adapter="manual", excerpt="New contrary evidence.",
                source_url=None, title=None, publisher=None, domain=None, source_published_at=None, retrieved_at=None,
                mime_type=None, document_status=None, at=c["now"][0])
    before = rows(c)
    with pytest.raises((TickerIdentityConflict, ValueError), match="review_changed|stale_assessment"):
        confirm(c, packet)
    assert rows(c) == before
    assert "OLD" in c["sources"]()


def test_confirmation_does_not_bind_unrelated_tickers_or_sa_capture_timestamps(tmp_path):
    c = context(tmp_path)
    packet = prepare(c)
    ProfileStateStore(c["profile"]).import_lists([{"name": "Other", "kind": "custom", "tickers": ["OTHER"]}])
    c["tracking"].reconcile(({**c["observed"], "observed_at": "2026-09-05T01:01:00Z"},), at="2026-09-05T01:01:00Z")
    assert confirm(c, packet)["status"] == "applied"
    assert set(c["sources"]()) == {"LIVE", "OTHER"}


def test_confirmation_rejects_forged_digest_and_action_without_writes(tmp_path):
    c = context(tmp_path)
    packet = prepare(c)
    before = rows(c)
    for forged in ({**packet, "packet_sha256": "0" * 64}, {**packet, "action": "symbol_continuation"}):
        with pytest.raises(TickerIdentityConflict, match="review_changed"):
            confirm(c, forged)
    assert rows(c) == before


def test_confirmation_permission_denial_precedes_every_write(tmp_path):
    c = context(tmp_path)
    packet = prepare(c)
    before = rows(c)
    def denied():
        raise PermissionError("denied")
    with pytest.raises(PermissionError, match="denied"):
        confirm(c, packet, before_write=denied)
    assert rows(c) == before


def test_duplicate_confirmation_reads_receipt_without_reapplying(tmp_path):
    c = context(tmp_path)
    packet = prepare(c)
    first = confirm(c, packet)
    before = rows(c)
    second = confirm(c, packet)
    assert second["status"] == "already_applied", second
    assert second["transition_id"] == first["transition_id"]
    assert second["current_effects_match"] is True
    assert rows(c) == before


def test_confirmation_recovers_after_durable_approval(tmp_path, monkeypatch):
    c = context(tmp_path)
    packet = prepare(c)
    def interrupted(step):
        if step == "approval_committed":
            raise RuntimeError("interrupted")
    monkeypatch.setattr(c["service"], "_review_step", interrupted, raising=False)
    with pytest.raises(RuntimeError, match="interrupted"):
        confirm(c, packet)
    with sqlite3.connect(c["profile"]) as conn:
        assert conn.execute("SELECT status FROM ticker_identity_transitions").fetchall() == [("approved",)]
    assert "OLD" in c["sources"]()
    monkeypatch.setattr(c["service"], "_review_step", lambda step: None)
    assert confirm(c, packet)["status"] == "applied"


@pytest.mark.parametrize("step", ("assessment_accepted", "proposals_created", "approval_created"))
def test_confirmation_rolls_back_all_staging_before_approval_commit(tmp_path, monkeypatch, step):
    c = context(tmp_path)
    packet = prepare(c)
    before = rows(c)
    def interrupted(current):
        if current == step:
            raise RuntimeError("interrupted")
    monkeypatch.setattr(c["service"], "_review_step", interrupted, raising=False)
    with pytest.raises(RuntimeError, match="interrupted"):
        confirm(c, packet)
    assert rows(c) == before


def test_replayed_confirmation_does_not_claim_current_effects_after_user_edit(tmp_path):
    c = context(tmp_path)
    packet = prepare(c)
    first = confirm(c, packet)
    ProfileStateStore(c["profile"]).set_universe_hidden("OLD", False)
    second = confirm(c, packet)
    assert second["transition_id"] == first["transition_id"]
    assert second["status"] == "applied_state_changed"
    assert second["current_effects_match"] is False


def reclock(c, at):
    from src.security_lifecycle_investigation import observation_fingerprint
    from src.security_lifecycle_listing_evidence import _evidence
    from tests.test_security_lifecycle_provider_authority import terminal_records

    day = datetime.fromisoformat(at.replace("Z", "+00:00")).date()
    material = tuple(_evidence(replace(row, source_as_of=(day - timedelta(days=1)).isoformat(), retrieved_at=at,
        delisted_utc=c["ended"] if row.delisted_utc else None)) for row in terminal_records())
    c["checks"].record(ticker="OLD", at=at, evidence=material, diagnostics={})
    fingerprint = observation_fingerprint(c["checks"].latest()["OLD"]["observation"])
    with sqlite3.connect(c["profile"]) as conn:
        conn.execute("UPDATE security_lifecycle_assessments SET observation_fingerprint_sha256=?", (fingerprint,))
        conn.execute("UPDATE security_lifecycle_assessment_evidence SET cited_content_sha256=?", (fingerprint,))
    c["now"][0] = at


@pytest.mark.parametrize("at", ("2026-09-05T01:00:00Z", "2026-11-01T03:30:00Z", "2027-03-14T04:30:00Z"))
def test_review_uses_new_york_execution_date_not_utc_date(tmp_path, at):
    c = context(tmp_path)
    reclock(c, at)
    c["options"] = TransitionOptions(execute_on=at[:10])
    packet = prepare(c)
    result = confirm(c, packet)
    assert result["status"] == "scheduled", result
    assert result["applied_at"] is None and result["current_effects_match"] is None
    assert "OLD" in c["sources"]()
    assert confirm(c, packet)["status"] == "scheduled"


@pytest.mark.parametrize("changed", (False, True))
def test_scheduled_review_preserves_due_runner_result_contract(tmp_path, monkeypatch, changed):
    from src.service import ticker_identity_scheduler as scheduler

    c = context(tmp_path)
    c["options"] = TransitionOptions(execute_on="2026-09-05")
    result = confirm(c, prepare(c))
    assert result["status"] == "scheduled"
    if changed:
        ProfileStateStore(c["profile"]).set_universe_hidden("OLD", True)
    c["now"][0] = "2026-09-05T13:00:00Z"
    monkeypatch.setattr(scheduler, "_service", lambda: c["service"])
    result = scheduler.run_due_ticker_identity_transitions(allow_automation_approved=False,
        transition_mutation_allowed=lambda: False, now=datetime.fromisoformat(c["now"][0].replace("Z", "+00:00")))
    assert result["status"] == "succeeded", result
    assert result["failed_transition_ids"] == []
    assert result["needs_review"] == int(changed)
    assert result["applied"] == int(not changed)


def test_two_simultaneous_confirmations_apply_and_record_only_once(tmp_path):
    c = context(tmp_path)
    packet = prepare(c)
    barrier = Barrier(2)
    def call():
        entered = False
        def permission():
            nonlocal entered
            if not entered:
                entered = True
                barrier.wait(timeout=10)
        return confirm(c, packet, before_write=permission)
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(call), executor.submit(call)]
        results = [future.result(timeout=20) for future in futures]
    assert sorted(row["status"] for row in results) == ["already_applied", "applied"]
    with sqlite3.connect(c["profile"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM ticker_identity_transitions").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM ticker_identity_transition_attempts").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM ticker_identity_transition_activity").fetchone()[0] == 1


def test_lost_response_replays_verified_receipt_after_restarting_service(tmp_path, monkeypatch):
    c = context(tmp_path)
    packet = prepare(c)
    def interrupted(step):
        if step == "application_committed":
            raise RuntimeError("response_lost")
    monkeypatch.setattr(c["service"], "_review_step", interrupted)
    with pytest.raises(RuntimeError, match="response_lost"):
        confirm(c, packet)
    before = rows(c)
    c["service"] = TickerIdentityService(profile_db_path=str(c["profile"]), market_db_path=str(c["market"]),
        source_loader=c["sources"], clock=lambda: c["now"][0])
    assert confirm(c, packet)["status"] == "already_applied"
    assert rows(c) == before


@pytest.mark.parametrize("fail_at", (2, 3))
def test_permission_revoked_during_staging_rolls_back_acceptance_and_approval(tmp_path, fail_at):
    c = context(tmp_path)
    packet = prepare(c)
    before = rows(c)
    calls = 0
    def permission():
        nonlocal calls
        calls += 1
        if calls == fail_at:
            raise PermissionError("revoked")
    with pytest.raises(PermissionError, match="revoked"):
        confirm(c, packet, before_write=permission)
    assert calls == fail_at and rows(c) == before


def test_permission_revoked_before_apply_keeps_a_truthful_durable_approval(tmp_path):
    c = context(tmp_path)
    packet = prepare(c)
    calls = 0
    def permission():
        nonlocal calls
        calls += 1
        if calls == 4:
            raise PermissionError("revoked")
    with pytest.raises(PermissionError, match="revoked"):
        confirm(c, packet, before_write=permission)
    with sqlite3.connect(c["profile"]) as conn:
        assert conn.execute("SELECT status FROM ticker_identity_transitions").fetchall() == [("approved",)]
    assert "OLD" in c["sources"]()
    assert confirm(c, packet)["status"] == "applied"


def test_newer_assessment_invalidates_review_even_without_new_evidence(tmp_path):
    c = context(tmp_path)
    packet = prepare(c)
    with sqlite3.connect(c["profile"]) as conn:
        store = SecurityLifecycleInvestigationStore(conn)
        old = store.get_assessment(c["assessment_id"])
        store.create_assessment(case_id=c["case_id"], relevance="direct_tracked_security", confidence="high", author="human",
            conclusion="Later conflicting assessment", impact_summary="Continue tracking.", outcomes=("no_tracked_security_change",),
            citations=old["citations"], observation_fingerprint_sha256=old["observation_fingerprint_sha256"], at=c["now"][0])
    before = rows(c)
    with pytest.raises(TickerIdentityConflict, match="review_changed"):
        confirm(c, packet)
    assert rows(c) == before


@pytest.mark.parametrize("change", ("content", "link"))
def test_citation_material_is_bound_and_integrity_checked(tmp_path, change):
    c = context(tmp_path)
    with sqlite3.connect(c["profile"]) as conn:
        store = SecurityLifecycleInvestigationStore(conn)
        evidence_id = store.add_evidence(case_id=c["case_id"], run_id=None, kind="manual_text", adapter="manual",
            excerpt="The reviewed primary notice.", source_url="https://example.com/original", title="Original notice", publisher=None,
            domain=None, source_published_at=None, retrieved_at=None, mime_type=None, document_status=None, at=c["now"][0])
        conn.execute("UPDATE security_lifecycle_assessments SET evidence_set_sha256=?", (store._evidence_set_sha256(c["case_id"]),))
        conn.execute("INSERT INTO security_lifecycle_assessment_evidence(assessment_id,reference_kind,evidence_id,cited_content_sha256) VALUES (?,'evidence',?,?)",
            (c["assessment_id"], evidence_id, store.get_evidence(evidence_id)["content_sha256"]))
    packet = prepare(c)
    with sqlite3.connect(c["profile"]) as conn:
        column = "excerpt" if change == "content" else "source_url"
        conn.execute(f"UPDATE security_lifecycle_evidence SET {column}=? WHERE evidence_id=?", ("Altered" if change == "content" else "https://example.com/changed", evidence_id))
    before = rows(c)
    with pytest.raises((ValueError, TickerIdentityConflict), match="review_changed|review_citation_invalid"):
        confirm(c, packet)
    assert rows(c) == before


def test_open_position_veto_survives_the_one_command_path(tmp_path):
    from src.portfolio_state import PortfolioStore

    c = context(tmp_path)
    packet = prepare(c)
    portfolio = PortfolioStore(c["profile"])
    account = portfolio.ensure_manual_account()
    portfolio.upsert_manual_position(account_id=account.id, symbol="OLD", quantity=1)
    before = rows(c)
    with pytest.raises(TickerIdentityConflict, match="review_changed"):
        confirm(c, packet)
    assert rows(c) == before
    assert prepare(c)["ready"] is False
    assert "portfolio_position_open" in prepare(c)["block_reasons"]


@pytest.mark.parametrize("suffix", ("#literal", "%23literal", " with spaces"))
def test_confirmation_uses_the_selected_literal_database_filename(tmp_path, suffix):
    c = context(tmp_path)
    original = c["profile"]
    selected = original.with_name(original.name + suffix)
    with sqlite3.connect(original) as source, sqlite3.connect(selected) as target:
        source.backup(target)
    before = rows(c)
    c["profile"] = selected
    c["service"] = TickerIdentityService(profile_db_path=str(selected), market_db_path=str(c["market"]),
        source_loader=lambda: {"OLD": ("manual_lists", "sa_alpha_picks_former"), "LIVE": ("manual_lists",)}, clock=lambda: c["now"][0])
    assert confirm(c, prepare(c))["status"] == "applied"
    assert rows({**c, "profile": original}) == before


def test_old_accepted_assessment_is_not_new_web_action_consent(tmp_path):
    from src.sa_tracking_memberships import SaTrackingMembershipStore
    from tests.test_ticker_identity_routes import _build_context

    old = _build_context(tmp_path, outcomes=("listing_ended",), successor=None, source="sec_edgar")
    with sqlite3.connect(old["profile_path"]) as conn:
        SaTrackingMembershipStore.install(conn)
        assessment_id = conn.execute("SELECT assessment_id FROM security_lifecycle_assessments").fetchone()[0]
    c = {"profile": old["profile_path"], "service": old["service"], "case_id": old["case_id"], "assessment_id": assessment_id,
         "options": TransitionOptions(execute_on="2026-08-25")}
    before = rows(c)
    packet = prepare(c)
    assert not packet["ready"]
    assert "listing_authority_required" in packet["block_reasons"]
    with pytest.raises(ValueError, match="review_ineligible"):
        confirm(c, packet)
    assert rows(c) == before


def test_legacy_and_automation_approval_cannot_forge_new_confirmation(tmp_path):
    from src.ticker_identity_transition import TickerIdentityTransitionStore

    c = context(tmp_path, accepted=True)
    legacy = c["service"].preview_case(c["case_id"], options=c["options"])
    with sqlite3.connect(c["profile"]) as conn:
        store = TickerIdentityTransitionStore(conn)
        for method in (store.approve, store.approve_automation):
            with pytest.raises(ValueError, match="review_confirmation_command_required"):
                method(preview={**legacy, "review_confirmation": {}}, approved_preview_sha256=legacy["preview_sha256"])
        assert conn.execute("SELECT COUNT(*) FROM ticker_identity_transitions").fetchone()[0] == 0


@pytest.mark.parametrize("accepted", (False, True))
def test_reviewed_same_security_rename_moves_only_its_tracking_sources(tmp_path, accepted):
    from src.security_lifecycle_listing_evidence import _evidence
    from tests.test_security_lifecycle_provider_authority import FIGI, events, record, terminal_records

    c = context(tmp_path)
    c["now"][0] = "2026-09-05T01:01:00Z"
    material = tuple(_evidence(row) for row in (*terminal_records(), record("massive_reference", "active", ticker="NEW", figi=FIGI)))
    material += (events((("OLD", "NEW", "2026-06-22"),)),)
    c["checks"].record(ticker="OLD", at=c["now"][0], evidence=material, diagnostics={})
    fingerprint = observation_fingerprint(c["checks"].latest()["OLD"]["observation"])
    with sqlite3.connect(c["profile"]) as conn:
        store = SecurityLifecycleInvestigationStore(conn)
        c["assessment_id"] = store.create_assessment(case_id=c["case_id"], relevance="direct_tracked_security", confidence="high", author="human",
            conclusion="Exact event and matching security identity.", impact_summary="Continue under NEW.", outcomes=("symbol_changed",),
            successor_ticker="NEW", effective_date="2026-06-22", citations=[{"reference_kind": "observation", "cited_content_sha256": fingerprint}],
            observation_fingerprint_sha256=fingerprint, at=c["now"][0])
        if accepted:
            store.accept_assessment(c["assessment_id"], observation_fingerprint_sha256=fingerprint, acceptance_authority="human", at=c["now"][0])
    c["options"] = TransitionOptions(execute_on="2026-06-22")
    with sqlite3.connect(c["sa"]) as conn:
        sa_before = tuple(conn.iterdump())
    packet = prepare(c)
    assert packet["ready"], packet
    assert packet["action"] == "symbol_continuation"
    result = confirm(c, packet)
    assert result["status"] == "applied"
    assert c["sources"]() == {"LIVE": ("manual_lists",), "NEW": ("manual_lists", "sa_alpha_picks_former")}
    with sqlite3.connect(c["sa"]) as conn:
        assert tuple(conn.iterdump()) == sa_before
    before = rows(c)
    assert confirm(c, packet)["status"] == "already_applied"
    assert rows(c) == before


def test_automation_assessment_still_requires_this_human_action_confirmation(tmp_path, monkeypatch):
    from tests.test_security_lifecycle_terminal_workflow import workflow_worker

    c = setup_workflow(tmp_path, assess=False)
    assert workflow_worker(c, monkeypatch, mutation_allowed=False).run(limit=1, mode="live")["accepted"] == 1
    with sqlite3.connect(c["profile"]) as conn:
        row = SecurityLifecycleInvestigationStore(conn).list_assessments(c["case_id"])[0]
        assert row["acceptance_authority"] == "automation_policy"
        c["assessment_id"] = row["assessment_id"]
        assert conn.execute("SELECT COUNT(*) FROM ticker_identity_transitions").fetchone()[0] == 0
    c["options"] = TransitionOptions(execute_on=c["ended"])
    packet = prepare(c)
    assert packet["ready"], packet
    result = confirm(c, packet)
    assert result["status"] == "applied"
    with sqlite3.connect(c["profile"]) as conn:
        row = conn.execute("SELECT approval_authority,approved_preview_json FROM ticker_identity_transitions").fetchone()
        assert row[0] == "attended_user"
        receipt = json.loads(row[1])["review_confirmation"]
        assert receipt["actor"] == "attended_user" and receipt["packet_sha256"] == packet["packet_sha256"]


def stage_approval(c, monkeypatch):
    packet = prepare(c)
    with monkeypatch.context() as patch:
        def interrupted(step):
            if step == "approval_committed":
                raise RuntimeError("interrupted")
        patch.setattr(c["service"], "_review_step", interrupted)
        with pytest.raises(RuntimeError, match="interrupted"):
            confirm(c, packet)
    with sqlite3.connect(c["profile"]) as conn:
        transition_id = conn.execute("SELECT transition_id FROM ticker_identity_transitions").fetchone()[0]
    return packet, transition_id


def test_application_crash_rolls_back_all_effects_but_preserves_the_confirmation(tmp_path, monkeypatch):
    c = context(tmp_path)
    packet, transition_id = stage_approval(c, monkeypatch)
    before = rows(c)
    with monkeypatch.context() as patch:
        def interrupted(step):
            if step == "application_staged":
                raise RuntimeError("apply_interrupted")
        patch.setattr(c["service"], "_review_step", interrupted)
        with pytest.raises(RuntimeError, match="apply_interrupted"):
            confirm(c, packet)
    assert rows(c) == before
    assert c["service"].get_review_confirmation(transition_id)["status"] == "approved"
    assert confirm(c, packet)["status"] == "applied"


@pytest.mark.parametrize("change", ("stale", "future", "active_otc", "incomplete"))
def test_provider_revalidation_cannot_be_replaced_by_a_durable_human_confirmation(tmp_path, monkeypatch, change):
    from src.security_lifecycle_listing_evidence import _evidence
    from tests.test_security_lifecycle_provider_authority import record

    c = context(tmp_path)
    packet, transition_id = stage_approval(c, monkeypatch)
    if change == "stale":
        c["now"][0] = "2026-09-10T01:00:00Z"
    elif change == "future":
        c["now"][0] = "2026-09-04T01:00:00Z"
    else:
        material = [_evidence(record("massive_reference", "active", market="otc"))] if change == "active_otc" else c["material"][:2]
        c["now"][0] = "2026-09-05T01:01:00Z"
        c["checks"].record(ticker="OLD", at=c["now"][0], evidence=material, diagnostics={})
    assert confirm(c, packet)["status"] == "blocked"
    assert "OLD" in c["sources"]()
    with sqlite3.connect(c["profile"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM ticker_identity_transition_activity").fetchone()[0] == 0
    assert c["service"].get_review_confirmation(transition_id)["status"] == "blocked"


@pytest.mark.parametrize("end_state", ("cancelled", "reversed"))
def test_replaying_old_confirmation_never_reactivates_cancelled_or_reversed_action(tmp_path, monkeypatch, end_state):
    c = context(tmp_path)
    packet, transition_id = stage_approval(c, monkeypatch)
    if end_state == "cancelled":
        c["service"].cancel_transition(transition_id, before_write=lambda: None)
    else:
        assert confirm(c, packet)["status"] == "applied"
        c["service"].reverse_transition(transition_id, before_write=lambda: None)
    before = rows(c)
    assert confirm(c, packet)["status"] == end_state
    assert rows(c) == before and "OLD" in c["sources"]()


@pytest.mark.parametrize("change", ("actor", "confirmed_at", "packet_version", "effects"))
def test_confirmation_readback_rejects_tampered_action_binding(tmp_path, monkeypatch, change):
    from src.security_lifecycle_review import packet_digest
    from src.ticker_identity_transition import profile_snapshot_sha256

    c = context(tmp_path)
    _, transition_id = stage_approval(c, monkeypatch)
    with sqlite3.connect(c["profile"]) as conn:
        preview = json.loads(conn.execute("SELECT approved_preview_json FROM ticker_identity_transitions").fetchone()[0])
        confirmation = preview["review_confirmation"]
        if change == "actor":
            confirmation["actor"] = "automation_policy"
        elif change == "confirmed_at":
            confirmation["confirmed_at"] = None
        elif change == "packet_version":
            confirmation["packet"]["version"] = True
        else:
            confirmation["packet"]["effects"]["suppression"]["hide_source"] = False
        digest = packet_digest(confirmation["packet"])
        confirmation["packet"]["packet_sha256"] = digest
        confirmation["packet_sha256"] = digest
        preview["preview_sha256"] = profile_snapshot_sha256(preview)
        conn.execute("UPDATE ticker_identity_transitions SET approved_preview_json=?,approved_preview_sha256=?",
                     (json.dumps(preview), preview["preview_sha256"]))
    before = rows(c)
    with pytest.raises(ValueError, match="review_confirmation_invalid"):
        c["service"].get_review_confirmation(transition_id)
    assert rows(c) == before


def test_legacy_store_apply_cannot_bypass_action_packet_revalidation(tmp_path, monkeypatch):
    from src.ticker_identity_transition import TickerIdentityTransitionStore

    c = context(tmp_path)
    _, transition_id = stage_approval(c, monkeypatch)
    before = rows(c)
    with sqlite3.connect(c["profile"]) as conn:
        store = TickerIdentityTransitionStore(conn, clock=lambda: c["now"][0])
        transition = store.get(transition_id)
        with pytest.raises(ValueError, match="review_confirmation_command_required"):
            store.apply(transition_id, current_preview=transition["approved_preview"], expected_preview_sha256=transition["approved_preview_sha256"], trigger="attended_user")
    assert rows(c) == before


def test_lost_readback_reports_unavailable_not_unverified_success(tmp_path, monkeypatch):
    from contextlib import contextmanager
    from src.ticker_identity_service import TickerIdentityStoreUnavailable

    c = context(tmp_path)
    packet = prepare(c)
    connection = c["service"]._profile_connection
    @contextmanager
    def fail_readback(*, write):
        if not write:
            raise TickerIdentityStoreUnavailable()
        with connection(write=write) as conn:
            yield conn
    with monkeypatch.context() as patch:
        patch.setattr(c["service"], "_profile_connection", fail_readback)
        with pytest.raises(TickerIdentityStoreUnavailable):
            confirm(c, packet)
    with sqlite3.connect(c["profile"]) as conn:
        assert conn.execute("SELECT status FROM ticker_identity_transitions").fetchall() == [("applied",)]
    before = rows(c)
    assert confirm(c, packet)["status"] == "already_applied"
    assert rows(c) == before


@pytest.mark.parametrize("operation", ("accept", "propose", "approve", "apply"))
def test_connection_taking_primitives_require_an_actual_caller_transaction(tmp_path, operation):
    from src.ticker_identity_transition import TickerIdentityTransitionStore

    c = context(tmp_path, accepted=True)
    preview = c["service"].preview_case(c["case_id"], options=c["options"])
    before = rows(c)
    with sqlite3.connect(c["profile"]) as conn:
        investigation = SecurityLifecycleInvestigationStore(conn)
        transitions = TickerIdentityTransitionStore(conn)
        assert not conn.in_transaction
        with pytest.raises(RuntimeError, match="caller_transaction_required"):
            if operation == "accept":
                investigation.accept_assessment(c["assessment_id"], observation_fingerprint_sha256=preview["observation_fingerprint_sha256"],
                    acceptance_authority="human", at=c["now"][0], _caller_transaction=True)
            elif operation == "propose":
                investigation.generate_action_proposals(case_id=c["case_id"], observation_fingerprint_sha256=preview["observation_fingerprint_sha256"],
                    sources_by_ticker=c["sources"](), at=c["now"][0], _caller_transaction=True)
            elif operation == "approve":
                transitions._approve(preview=preview, approved_preview_sha256=preview["preview_sha256"], automation=False, _caller_transaction=True)
            else:
                transitions.apply("no-transition", current_preview=preview, expected_preview_sha256=preview["preview_sha256"], trigger="attended_user", _caller_transaction=True)
    assert rows(c) == before


@pytest.mark.parametrize("timing", ("before_review", "after_review"))
def test_dismissed_required_proposal_is_not_offered_as_confirmable(tmp_path, timing):
    c = context(tmp_path, accepted=True)
    old_packet = prepare(c)
    with sqlite3.connect(c["profile"]) as conn:
        store = SecurityLifecycleInvestigationStore(conn)
        proposal = next(row for row in store.list_proposals(c["case_id"]) if row["action_type"] == "notify")
        store.dismiss_proposal(proposal["proposal_id"], at=c["now"][0])
    before = rows(c)
    packet = prepare(c)
    assert packet["ready"] is False
    assert "proposal_missing" in packet["block_reasons"]
    with pytest.raises((ValueError, TickerIdentityConflict), match="review_ineligible|review_changed"):
        confirm(c, packet if timing == "before_review" else old_packet)
    assert rows(c) == before


def test_fresh_review_after_profile_change_can_reapprove_a_blocked_action(tmp_path, monkeypatch):
    c = context(tmp_path)
    packet, transition_id = stage_approval(c, monkeypatch)
    ProfileStateStore(c["profile"]).import_lists([{"name": "Another", "kind": "custom", "tickers": ["OLD", "OTHER"]}])
    assert confirm(c, packet)["status"] == "blocked"
    changed_packet = prepare(c)
    assert changed_packet["ready"] and changed_packet["packet_sha256"] != packet["packet_sha256"]
    result = confirm(c, changed_packet)
    assert result["status"] == "applied" and result["transition_id"] == transition_id
    assert set(c["sources"]()) == {"LIVE", "OTHER"}
    assert ProfileStateStore(c["profile"]).get_ticker("OLD").lists == []


def test_unavailable_source_context_has_no_confirmable_fallback(tmp_path, monkeypatch):
    c = context(tmp_path)
    monkeypatch.setattr(c["service"]._read_service, "sources_by_ticker", lambda: None)
    before = rows(c)
    packet = prepare(c)
    assert packet["ready"] is False and "source_context_unavailable" in packet["block_reasons"]
    with pytest.raises(ValueError, match="review_ineligible"):
        confirm(c, packet)
    assert rows(c) == before


@pytest.mark.parametrize("authority,reviewed", (
    ("attended_user", True), ("automation_policy", True),
    ("attended_user", False), ("automation_policy", False),
))
def test_legacy_reapproval_cannot_discard_an_action_confirmation(tmp_path, monkeypatch, authority, reviewed):
    from tests.test_security_lifecycle_terminal_workflow import workflow_worker

    c = setup_workflow(tmp_path, assess=False)
    assert workflow_worker(c, monkeypatch, mutation_allowed=False).run(limit=1, mode="live")["accepted"] == 1
    with sqlite3.connect(c["profile"]) as conn:
        assessment = SecurityLifecycleInvestigationStore(conn).list_assessments(c["case_id"])[0]
        assert assessment["acceptance_authority"] == "automation_policy"
        c["assessment_id"] = assessment["assessment_id"]
    c["options"] = TransitionOptions(execute_on="2026-09-06")
    if reviewed:
        packet, transition_id = stage_approval(c, monkeypatch)
    options = TransitionOptions(execute_on=c["ended"])
    preview = c["service"].preview_case(c["case_id"], options=options)
    assert preview["eligible"] and "review_confirmation" not in preview
    before = rows(c)

    def legacy_approval():
        if authority == "attended_user":
            return c["service"].approve_case(c["case_id"], options=options,
                preview_sha256=preview["preview_sha256"], before_write=lambda: None)
        return c["service"].approve_automation_case(c["case_id"], request={
            "transition_kind": preview["transition_kind"], "source_ticker": preview["source_ticker"],
            "successor_ticker": preview["successor_ticker"], "effective_date": preview["execute_on"],
            "outcomes": preview["outcomes"],
        })

    if reviewed:
        with pytest.raises(ValueError, match="review_confirmation_command_required"):
            legacy_approval()
        assert rows(c) == before
        result = c["service"].get_review_confirmation(transition_id)
        assert result["status"] == "scheduled" and result["packet_sha256"] == packet["packet_sha256"]
        assert result["execute_on"] == "2026-09-06"
    else:
        result = legacy_approval()
        assert result["status"] == "approved" and result["approval_authority"] == authority
        assert "review_confirmation" not in result["approved_preview"]
