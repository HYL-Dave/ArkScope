import socket
import sqlite3

import pytest

from tests.test_security_lifecycle_terminal_workflow import setup_workflow


@pytest.mark.parametrize("ended", ("2023-05-15", "2025-01-15"))
def test_structured_provider_review_needs_no_llm_or_new_provider_read_and_keeps_confirmation_separate(tmp_path, monkeypatch, ended):
    from src.lifecycle_investigation.provider_review import provider_decision, prepare_provider_review
    from src.ticker_identity_transition import TransitionOptions
    c = setup_workflow(tmp_path, assess=False, ended=ended, event_available=False)
    monkeypatch.setattr(socket.socket, "connect", lambda *a: pytest.fail("cached preparation contacted a provider"))
    before = c["profile"].read_bytes()
    decision = provider_decision(c["service"], "OLD")
    assert decision["listing_state"] == "inactive" and decision["action"] == "terminal_delisting"
    assert decision["continuation_state"] == "unavailable"
    assert c["profile"].read_bytes() == before
    calls = []
    packet = prepare_provider_review(c["service"], "OLD", check_sha256=decision["check_sha256"],
        options=TransitionOptions(execute_on=None), before_write=lambda: calls.append(True))
    assert packet["ready"] and packet["action"] == "terminal_delisting", packet
    assert calls and "OLD" in c["sources"]()
    with sqlite3.connect(c["profile"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM ticker_identity_transitions").fetchone()[0] == 0
        assert conn.execute("SELECT DISTINCT source FROM security_lifecycle_cases").fetchall() == [("listing_authority",)]
        readiness, = conn.execute("SELECT action_readiness FROM security_lifecycle_automation_runs").fetchone()
        assert readiness == ("transition_eligible" if ended >= "2025-01-01" else "not_applicable")
    receipt = c["service"].confirm_review(packet["case_id"], assessment_id=packet["assessment_id"], packet_sha256=packet["packet_sha256"],
        action=packet["action"], options=TransitionOptions(**packet["options"]), before_write=lambda: None)
    assert receipt["status"] == "applied"
    assert "OLD" not in c["sources"]() and "LIVE" in c["sources"]()


@pytest.mark.parametrize("change", ("active", "unavailable", "changed_digest", "permission"))
def test_provider_preparation_refuses_unproven_or_changed_evidence_without_tracking_writes(tmp_path, change):
    from src.lifecycle_investigation.provider_review import provider_decision, prepare_provider_review
    from src.ticker_identity_transition import TransitionOptions
    from tests.test_security_lifecycle_population import active
    c = setup_workflow(tmp_path, assess=False)
    decision = provider_decision(c["service"], "OLD")
    if change in {"active", "unavailable"}:
        c["now"][0] = "2026-09-08T01:00:00Z"
        c["checks"].record(ticker="OLD", at=c["now"][0], evidence=(active("OLD", at=c["now"][0]),) if change == "active" else (), diagnostics={})
        decision = provider_decision(c["service"], "OLD")
        assert decision["action"] is None
    digest = "0" * 64 if change == "changed_digest" else decision["check_sha256"]
    def permission():
        if change == "permission":
            raise ValueError("writes_disabled")
    before = c["profile"].read_bytes()
    with pytest.raises(ValueError, match="provider_review_ineligible|provider_snapshot_changed|writes_disabled"):
        prepare_provider_review(c["service"], "OLD", check_sha256=digest, options=TransitionOptions(execute_on=None), before_write=permission)
    assert c["profile"].read_bytes() == before
    assert "OLD" in c["sources"]()


def test_confirmed_same_security_provider_rename_reuses_the_writer_and_preview_is_repeatable(tmp_path):
    from src.lifecycle_investigation.provider_review import provider_decision, prepare_provider_review
    from src.security_lifecycle_listing_evidence import _evidence
    from src.ticker_identity_transition import TransitionOptions
    from tests.test_security_lifecycle_provider_authority import FIGI, events, record, terminal_records
    c = setup_workflow(tmp_path, assess=False)
    c["now"][0] = "2026-09-05T01:00:01Z"
    material = tuple(_evidence(row) for row in (*terminal_records(), record("massive_reference", "active", ticker="NEW", figi=FIGI)))
    material += (events((("OLD", "NEW", "2026-06-22"),)),)
    c["checks"].record(ticker="OLD", at=c["now"][0], evidence=material, diagnostics={})
    decision = provider_decision(c["service"], "OLD")
    assert decision["action"] == "symbol_continuation" and decision["successor_ticker"] == "NEW"
    options = TransitionOptions(execute_on=None)
    packet = prepare_provider_review(c["service"], "OLD", check_sha256=decision["check_sha256"], options=options, before_write=lambda: None)
    again = prepare_provider_review(c["service"], "OLD", check_sha256=decision["check_sha256"], options=options, before_write=lambda: None)
    assert packet["ready"] and packet["action"] == "symbol_continuation", packet
    assert again["packet_sha256"] == packet["packet_sha256"]
    with sqlite3.connect(c["sa"]) as conn:
        history = tuple(conn.iterdump())
    result = c["service"].confirm_review(packet["case_id"], assessment_id=packet["assessment_id"], packet_sha256=packet["packet_sha256"],
        action=packet["action"], options=TransitionOptions(**packet["options"]), before_write=lambda: None)
    assert result["status"] == "applied"
    assert "OLD" not in c["sources"]() and {"NEW", "LIVE"} <= set(c["sources"]())
    with sqlite3.connect(c["sa"]) as conn:
        assert tuple(conn.iterdump()) == history
