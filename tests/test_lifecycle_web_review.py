from dataclasses import replace
import json
import sqlite3

import pytest

from src.lifecycle_web_schema import install_web_journal
from src.lifecycle_web_store import LifecycleWebStore
from src.profile_state import ProfileStateStore
from src.security_lifecycle_investigation import SecurityLifecycleInvestigationStore, observation_fingerprint
from src.security_lifecycle_web_contract import validate_selection
from src.ticker_identity_transition import TransitionOptions, TickerIdentityTransitionStore
from tests.test_security_lifecycle_terminal_workflow import setup_workflow
from tests.test_security_lifecycle_web_finding import NOTICE, finding_payload, public_input, source_page
from tests.test_lifecycle_web_store import _options


def context(tmp_path, *, auth="api_key", provider=None, kind="terminal_delisting", future=False, sec_case=False,
            completion=None):
    c = setup_workflow(tmp_path, assess=False, event_available=False)
    c["now"][0] = "2026-09-06T01:00:00Z"
    # Missing structured checks are the reason for Web investigation, not a
    # requirement that must become successful before a human can confirm.
    c["checks"].record(ticker="OLD", at=c["now"][0], evidence=(), diagnostics={}, blockers=("massive_unavailable",))
    observation = c["checks"].latest()["OLD"]["observation"]
    if sec_case:
        from src.security_lifecycle import LifecycleObservation, ObservationKind, SecurityLifecycleStore
        with sqlite3.connect(c["market"]) as conn:
            SecurityLifecycleStore(conn).upsert_observation(LifecycleObservation(ticker="OLD", cik="0000012345", issuer_name="Issuer Old Inc",
                filing_date="2026-09-01", source="sec_edgar", source_ref="0000012345-26-000042", filing_form="8-K", filing_items=("3.01",),
                evidence_url="https://www.sec.gov/Archives/example/old.htm", description="Listing status under review.", observed_at=c["now"][0],
                kinds=(ObservationKind("listing_removal_notice", "2026-09-01"),)))
            observation = SecurityLifecycleStore(conn).get_observation("sec_edgar", "0000012345-26-000042", "OLD")
        with sqlite3.connect(c["profile"]) as conn:
            c["case_id"] = SecurityLifecycleInvestigationStore(conn).ensure_case(source="sec_edgar", source_ref="0000012345-26-000042", ticker="OLD", at=c["now"][0])
    fingerprint = observation_fingerprint(observation)
    with sqlite3.connect(c["profile"]) as conn:
        install_web_journal(conn, at=c["now"][0])
    store = LifecycleWebStore(c["profile"], clock=lambda: c["now"][0])
    provider = provider or ("anthropic" if auth == "claude_code_oauth" else "openai")
    selected = validate_selection(provider, auth, "claude-sonnet-5" if provider == "anthropic" else "gpt-5.6-luna", "local:7")
    request = public_input().model_copy(update={"composite_figi": None})
    run = store.start(case_id=c["case_id"], observation_sha256=fingerprint, request=request, selection=selected,
                      options=_options(auth), owner="worker-1", request_key="click-1")
    identity = run["run_id"]
    control = store.control(identity, owner="worker-1")
    for phase in ("search", "analysis"):
        control.reserve_model_request(phase + "-1")
        control.bind_remote_id(phase + "-1", phase)
        control.observe_terminal(phase + "-1", response_id=phase, status="completed", selection=selected)
    payload, notice = finding_payload(), NOTICE
    if kind == "symbol_continuation":
        notice = "Issuer Old Inc OLD Class A common stock on NASDAQ changes its ticker from OLD to NEW for the same security effective September 1, 2026."
        payload.update(event_kind="symbol_continuation", successor_ticker="NEW")
        payload["citations"][0]["supports"] = ["security_identity", "same_security_continuation", "effective_date"]
    if future:
        notice = notice.replace("September 1, 2026", "September 7, 2026")
        payload.update(timing="scheduled", effective_date="2026-09-07", effective_date_text="September 7, 2026")
    payload["citations"][0]["quote"] = notice
    store.add_page(identity, owner="worker-1", source_id="source-1", page=source_page(notice))
    store.complete(identity, owner="worker-1", **{"payload": payload, "source_failures": {},
        "usage": {"input_tokens": 20, "output_tokens": 40}, "source_requests": 1, **(completion or {})})
    c.update(web=store, run_id=identity, options=TransitionOptions(execute_on=payload["effective_date"]), action=kind)
    return c


def prepare(c):
    from src.lifecycle_web_review import prepare
    return prepare(c["service"], c["run_id"], options=c["options"])


def confirm(c, packet, *, before_write=lambda: None):
    from src.lifecycle_web_review import confirm
    return confirm(c["service"], c["run_id"], packet_sha256=packet["packet_sha256"],
                   action=packet["action"], options=c["options"], before_write=before_write,
                   acknowledge_source_gaps=bool(packet.get("source_gaps")))


def rows(c):
    with sqlite3.connect(c["profile"]) as conn:
        return tuple(conn.iterdump())


def test_web_review_preparation_never_creates_a_human_assessment_or_tracking_change(tmp_path):
    c = context(tmp_path)
    before = rows(c)
    packet = prepare(c)
    assert packet["ready"], packet["block_reasons"]
    assert packet["lane"] == "web" and packet["action"] == "terminal_delisting"
    assert packet["web"]["run_id"] == c["run_id"]
    assert rows(c) == before
    assert "OLD" in c["sources"]()


@pytest.mark.parametrize("provider,auth", [("openai", "api_key"), ("openai", "chatgpt_oauth"),
                                          ("anthropic", "api_key"), ("anthropic", "claude_code_oauth")])
@pytest.mark.parametrize("kind", ["terminal_delisting", "symbol_continuation"])
def test_web_confirmation_uses_existing_atomic_writer_without_requiring_provider_success(tmp_path, provider, auth, kind):
    c = context(tmp_path, provider=provider, auth=auth, kind=kind)
    packet = prepare(c)
    assert packet["ready"], packet["block_reasons"]
    result = confirm(c, packet)
    assert result["status"] == "applied" and result["current_effects_match"] is True
    assert ("NEW" in c["sources"]()) == (kind == "symbol_continuation")
    assert "OLD" not in c["sources"]() and "LIVE" in c["sources"]()
    with sqlite3.connect(c["profile"]) as conn:
        author, authority = conn.execute("SELECT author,acceptance_authority FROM security_lifecycle_assessments").fetchone()
        assert (author, authority) == ("human", "human")
        linked = conn.execute("SELECT run_id,actor,packet_sha256 FROM lifecycle_web_acceptances").fetchone()
        assert linked == (c["run_id"], "attended_user", packet["packet_sha256"])
        receipt = json.loads(conn.execute("SELECT approved_preview_json FROM ticker_identity_transitions").fetchone()[0])
        assert receipt["review_confirmation"]["packet"]["web"]["execution"]["auth_mode"] == auth
        assert conn.execute("SELECT COUNT(*) FROM security_lifecycle_investigation_runs").fetchone()[0] == 0
    before = rows(c)
    assert confirm(c, packet)["status"] == "already_applied"
    assert rows(c) == before


@pytest.mark.parametrize("change", ["membership", "new_observation", "evidence", "future_lease", "open_position"])
def test_web_confirmation_rejects_changed_material_without_partial_human_adoption(tmp_path, change):
    c = context(tmp_path)
    packet = prepare(c)
    if change == "membership":
        ProfileStateStore(c["profile"]).import_lists([{"name": "New", "kind": "custom", "tickers": ["OLD"]}])
    elif change == "new_observation":
        c["checks"].record(ticker="OLD", at="2026-09-06T01:01:00Z", evidence=(), diagnostics={}, blockers=("massive_unavailable",))
        c["now"][0] = "2026-09-06T01:01:00Z"
    elif change == "evidence":
        with sqlite3.connect(c["profile"]) as conn:
            SecurityLifecycleInvestigationStore(conn).add_evidence(case_id=c["case_id"], run_id=None, kind="manual_text", adapter="manual",
                excerpt="Contradictory evidence", source_url=None, title=None, publisher=None, domain=None, source_published_at=None,
                retrieved_at=None, mime_type=None, document_status=None, at=c["now"][0])
    elif change == "future_lease":
        c["now"][0] = "2026-09-10T01:00:00Z"
    else:
        # Use the same authoritative open-position source as ordinary review.
        c["service"]._read_service.sources_by_ticker = lambda: {"OLD": ("manual_lists", "portfolio_open"), "LIVE": ("manual_lists",)}
    before = rows(c)
    with pytest.raises((ValueError, RuntimeError), match="review_changed|web_review_ineligible"):
        confirm(c, packet)
    assert rows(c) == before and "OLD" in c["sources"]()


def test_current_active_otc_veto_is_not_lost_when_other_provider_requests_failed(tmp_path):
    from src.security_lifecycle_listing_evidence import _evidence
    from tests.test_security_lifecycle_provider_authority import record
    c = context(tmp_path)
    c["checks"].record(ticker="OLD", at=c["now"][0], evidence=[_evidence(record("massive_reference", "active", market="otc"))],
                       diagnostics={}, blockers=("massive_unavailable",))
    packet = prepare(c)
    assert packet["ready"] is False and "web_active_listing_conflict" in packet["block_reasons"]
    assert "OLD" in c["sources"]()


def test_future_web_action_is_scheduled_and_rechecked_before_applying(tmp_path):
    c = context(tmp_path, future=True)
    packet = prepare(c)
    result = confirm(c, packet)
    assert result["status"] == "scheduled" and "OLD" in c["sources"]()
    c["now"][0] = "2026-09-07T15:00:00Z"
    with sqlite3.connect(c["profile"]) as conn:
        digest = conn.execute("SELECT approved_preview_sha256 FROM ticker_identity_transitions WHERE transition_id=?", (result["transition_id"],)).fetchone()[0]
    applied = c["service"].execute_transition(result["transition_id"], preview_sha256=digest, before_write=lambda: None)
    assert applied["status"] == "applied" and "OLD" not in c["sources"]()


def test_web_adoption_cannot_survive_an_approval_failure_in_a_partial_transaction(tmp_path, monkeypatch):
    c = context(tmp_path)
    packet = prepare(c)
    before = rows(c)
    def fail(*args, **kwargs):
        raise RuntimeError("approval_failed")
    monkeypatch.setattr(TickerIdentityTransitionStore, "_approve", fail)
    with pytest.raises(RuntimeError, match="approval_failed"):
        confirm(c, packet)
    assert rows(c) == before


def test_unrelated_sa_refresh_and_other_ticker_edits_do_not_block_web_review(tmp_path):
    c = context(tmp_path)
    packet = prepare(c)
    ProfileStateStore(c["profile"]).import_lists([{"name": "Other", "kind": "custom", "tickers": ["OTHER"]}])
    c["tracking"].reconcile(({**c["observed"], "observed_at": "2026-09-06T01:01:00Z"},), at="2026-09-06T01:01:00Z")
    assert confirm(c, packet)["status"] == "applied"
    assert set(c["sources"]()) == {"LIVE", "OTHER"}


@pytest.mark.parametrize("kind", ["terminal_delisting", "symbol_continuation"])
def test_unretained_sec_case_cannot_start_new_adoption_but_keeps_audit_material(tmp_path, kind):
    from src.security_lifecycle_investigation import compose_security_lifecycle_audit

    c = context(tmp_path, sec_case=True, kind=kind)
    before = rows(c)
    with pytest.raises(KeyError, match="case_not_found"):
        prepare(c)
    assert rows(c) == before and "OLD" in c["sources"]()
    assert c["web"].read(c["run_id"])["status"] == "succeeded"
    assert c["case_id"] in {case["case_id"] for case in compose_security_lifecycle_audit(str(c["market"]), str(c["profile"]))["cases"]}


@pytest.mark.parametrize("mutation", ["strip_confirmation", "edit_finding", "automation"])
def test_central_writer_rejects_forged_web_authority_even_with_recomputed_preview_digest(tmp_path, mutation):
    from src.ticker_identity_transition import profile_snapshot_sha256
    c = context(tmp_path, future=True)
    packet = prepare(c)
    result = confirm(c, packet)
    c["now"][0] = "2026-09-07T15:00:00Z"
    with sqlite3.connect(c["profile"]) as conn:
        store = TickerIdentityTransitionStore(conn, clock=lambda: c["now"][0])
        transition = store.get(result["transition_id"])
        preview = transition["approved_preview"]
        if mutation == "strip_confirmation":
            preview.pop("review_confirmation")
        elif mutation == "edit_finding":
            conn.execute("UPDATE security_lifecycle_assessments SET effective_date='2026-08-01' WHERE assessment_id=?", (transition["assessment_id"],))
        preview["preview_sha256"] = profile_snapshot_sha256(preview)
        blockers = store._provider_guard(preview, at=c["now"][0], automation=mutation == "automation")
        assert "web_acceptance_required" in blockers or "web_acceptance_invalid" in blockers
    assert "OLD" in c["sources"]()


def test_stale_provider_state_after_web_approval_blocks_the_real_due_writer(tmp_path):
    from src.security_lifecycle_listing_evidence import _evidence
    from tests.test_security_lifecycle_provider_authority import record
    c = context(tmp_path, future=True)
    packet = prepare(c)
    result = confirm(c, packet)
    with sqlite3.connect(c["profile"]) as conn:
        digest = conn.execute("SELECT approved_preview_sha256 FROM ticker_identity_transitions WHERE transition_id=?", (result["transition_id"],)).fetchone()[0]
    c["now"][0] = "2026-09-07T15:00:00Z"
    c["checks"].record(ticker="OLD", at=c["now"][0], evidence=[_evidence(replace(record("massive_reference", "active", market="otc"), retrieved_at=c["now"][0]))], diagnostics={})
    result = c["service"].execute_transition(result["transition_id"], preview_sha256=digest, before_write=lambda: None)
    assert result["status"] == "blocked" and "OLD" in c["sources"]()


def test_web_applied_receipt_can_reverse_without_erasing_investigation_or_reenrolling_on_sa_refresh(tmp_path):
    c = context(tmp_path)
    result = confirm(c, prepare(c))
    c["tracking"].reconcile(({**c["observed"], "observed_at": "2026-09-06T01:01:00Z"},), at="2026-09-06T01:01:00Z")
    assert "OLD" not in c["sources"]()
    reversed_result = c["service"].reverse_transition(result["transition_id"], before_write=lambda: None)
    assert reversed_result["status"] == "reversed"
    assert "OLD" in c["sources"]() and c["web"].read(c["run_id"])["status"] == "succeeded"
