"""Gap disclosure is bound to the real current agent, review, and attended receipt."""

from copy import deepcopy
import json
import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from src.lifecycle_investigation import review
from src.lifecycle_investigation.controller import project_job
from src.lifecycle_investigation.store import JournalError
from src.lifecycle_journal_codec import canonical_json, digest_json
from src.lifecycle_public_sources import PublicSourceReader
from src.security_lifecycle_review import packet_digest, project_packet
from src.ticker_identity_transition import TransitionOptions
from tests.test_lifecycle_investigation_agent import choose, completed
from tests.test_lifecycle_investigation_findings import payload
from tests.test_lifecycle_investigation_review import context, prepare, confirm, rows
from tests.test_lifecycle_public_sources import Response, _reader
from tests.test_ticker_identity_history import damage_saved_rows


URL = "https://issuer.example/supplement"
GAPS = [{"url": URL, "reason": "source_unavailable"}]
CHANNELS = [("openai", "api_key"), ("openai", "chatgpt_oauth"),
            ("anthropic", "api_key"), ("anthropic", "claude_code_oauth")]


def gap_context(tmp_path, monkeypatch, *, kind="terminal_delisting", finding_edit=lambda value: value, **kwargs):
    _, connections, _, _ = _reader(monkeypatch, [Response(status=403, headers={"Set-Cookie": "private-cookie"})])
    calls = []
    async def model(call, credential, control):
        calls.append(call)
        if len(calls) == 1:
            return completed(call, control, choose("search_web", query="OLD listing supplement"))
        if call.phase == "search":
            return completed(call, control, {"sources": [URL], "unresolved_conditions": []})
        if len(calls) == 3:
            return completed(call, control, choose("read_url", url=URL))
        material = json.loads(call.prompt.split("\nMATERIAL\n")[1])
        assert material["source_gaps"] == [{**GAPS[0], "corpus": None}]
        finding = payload(material["sources"][0]["passages"])
        if kind == "symbol_continuation":
            finding.update(event_kind="symbol_continuation", successor_ticker="NEW")
            finding["citations"][-1]["supports"] = ["same_security_continuation", "effective_date"]
        return completed(call, control, choose("conclude", finding=finding_edit(finding)))
    c = context(tmp_path, kind=kind, model=model, reader_factory=PublicSourceReader, **kwargs)
    assert len(connections) == 1 and all(conn.closed for conn in connections)
    return c


@pytest.mark.parametrize("provider,auth", CHANNELS)
@pytest.mark.parametrize("kind", ["terminal_delisting", "symbol_continuation"])
def test_current_gap_disclosure_follows_finding_review_and_explicit_receipt(tmp_path, monkeypatch, provider, auth, kind):
    c = gap_context(tmp_path, monkeypatch, provider=provider, auth=auth, kind=kind)
    before = rows(c)
    public = project_job(c["investigation"].read(c["run_id"]), at=c["now"][0])
    packet = prepare(c)
    assert packet["ready"] and packet["source_gaps"] == project_packet(packet)["source_gaps"] == GAPS
    assert public["gaps"] == [{**GAPS[0], "corpus": None}]
    assert "private-cookie" not in json.dumps(public)
    assert rows(c) == before and "OLD" in c["sources"]()
    assert confirm(c, packet, acknowledge_source_gaps=True)["status"] == "applied"
    assert ("NEW" in c["sources"]()) is (kind == "symbol_continuation")
    assert "OLD" not in c["sources"]() and "LIVE" in c["sources"]()
    with sqlite3.connect(c["profile"]) as conn:
        receipt, actor = conn.execute("SELECT packet_json,actor FROM lifecycle_investigation_acceptances").fetchone()
        assert actor == "attended_user" and json.loads(receipt)["source_gaps"] == GAPS
        assert conn.execute("SELECT author,acceptance_authority FROM security_lifecycle_assessments").fetchone() == ("human", "human")
    after = rows(c)
    assert confirm(c, packet, acknowledge_source_gaps=True)["status"] == "already_applied"
    assert rows(c) == after


@pytest.mark.parametrize("change", ["omitted", "empty", "reason", "url"])
def test_current_confirmation_rejects_different_gap_disclosure_without_write(tmp_path, monkeypatch, change):
    c = gap_context(tmp_path, monkeypatch)
    packet = prepare(c)
    if change == "omitted":
        packet.pop("source_gaps")
    elif change == "empty":
        packet["source_gaps"] = []
    else:
        packet["source_gaps"][0][change] = "source_read_timeout" if change == "reason" else "https://other.example/notice"
    packet["packet_sha256"] = packet_digest(packet)
    before = rows(c)
    with pytest.raises((ValueError, RuntimeError), match="review_changed"):
        confirm(c, packet, acknowledge_source_gaps=True)
    assert rows(c) == before


@pytest.mark.parametrize("acknowledgement", [False, None, 1, "true"])
def test_current_direct_adoption_requires_literal_gap_acknowledgement(tmp_path, monkeypatch, acknowledgement):
    c = gap_context(tmp_path, monkeypatch)
    packet = prepare(c)
    before = rows(c)
    with pytest.raises(JournalError, match="^web_source_gaps_not_acknowledged$"):
        confirm(c, packet, acknowledge_source_gaps=acknowledgement)
    assert rows(c) == before


@pytest.mark.parametrize("acknowledgement", ["omitted", False, None, 1, "true"])
def test_current_confirmation_api_cannot_apply_unacknowledged_gaps(tmp_path, monkeypatch, acknowledgement):
    from src.api.routes import lifecycle_investigation as api
    c = gap_context(tmp_path, monkeypatch)
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[api.get_ticker_identity_service] = lambda: c["service"]
    monkeypatch.setattr(api, "require_db_write", lambda *args: None)
    monkeypatch.setattr(api, "require_profile_state_write", lambda *args: None)
    with TestClient(app) as client:
        route = f"/security-lifecycle/investigations/runs/{c['run_id']}"
        packet = client.get(route + "/review").json()
        assert packet["ready"] and packet["source_gaps"] == GAPS
        body = {"packet_sha256": packet["packet_sha256"], "action": packet["action"], **packet["options"]}
        if acknowledgement != "omitted":
            body["acknowledge_source_gaps"] = acknowledgement
        before = rows(c)
        response = client.post(route + "/confirm", json=body)
        assert response.status_code == (409 if acknowledgement in ("omitted", False) else 422), response.text
        if acknowledgement in ("omitted", False):
            assert response.json()["detail"]["code"] == "web_source_gaps_not_acknowledged"
        assert rows(c) == before
        accepted = client.post(route + "/confirm", json={**body, "acknowledge_source_gaps": True})
        assert accepted.status_code == 200 and accepted.json()["status"] == "applied", accepted.text


@pytest.mark.parametrize("failed", [False, True])
def test_current_gap_acknowledgement_never_substitutes_for_completed_finding(tmp_path, failed):
    from tests.test_lifecycle_investigation_store import running
    c, store, identity, _ = running(tmp_path)
    if failed:
        store.finish(identity, owner="worker", status="failed", failure_code="source_unavailable")
    before = rows(c)
    with pytest.raises(ValueError, match="^web_finding_not_complete$"):
        review.confirm(c["service"], identity, packet_sha256="a" * 64, action="terminal_delisting",
            options=TransitionOptions(execute_on=None), before_write=lambda: None, acknowledge_source_gaps=True)
    assert rows(c) == before


@pytest.mark.parametrize("change,reason", [
    ({"contradictions": ["The exchange reports continued trading."]}, "material_contradiction"),
    ({"unresolved_conditions": ["Trading status remains uncertain."]}, "finding_incomplete"),
    ({"source_ticker": "OTHER"}, "security_identity_mismatch"),
    ({"citations": []}, "source_passage_missing"),
])
def test_current_disclosed_gap_does_not_override_missing_essential_proof(tmp_path, monkeypatch, change, reason):
    c = gap_context(tmp_path, monkeypatch, finding_edit=lambda value: {**value, **change}, expected_status="incomplete")
    row = c["investigation"].read(c["run_id"])
    assert row["result"]["validated"]["action"] is None
    assert reason in row["result"]["validated"]["block_reasons"]
    assert row["result"]["gaps"] == [{**GAPS[0], "corpus": None}]
    before = rows(c)
    with pytest.raises(ValueError, match="^web_finding_not_complete$"):
        review.confirm(c["service"], c["run_id"], packet_sha256="a" * 64, action="terminal_delisting",
            options=c["options"], before_write=lambda: None, acknowledge_source_gaps=True)
    assert rows(c) == before and "OLD" in c["sources"]()


@pytest.mark.parametrize("strip", [False, True])
def test_current_writer_rechecks_gap_disclosure_even_when_acceptance_is_resigned(tmp_path, monkeypatch, strip):
    from src.security_lifecycle_investigation import SecurityLifecycleInvestigationStore
    from src.ticker_identity_transition import TickerIdentityTransitionStore
    c = gap_context(tmp_path, monkeypatch, future=True)
    result = confirm(c, prepare(c), acknowledge_source_gaps=True)
    read_acceptance = review.acceptance_for
    def changed(conn, assessment_id):
        accepted = deepcopy(read_acceptance(conn, assessment_id))
        packet = accepted["packet"]
        packet.pop("source_gaps") if strip else packet.update(source_gaps=[])
        accepted["packet_sha256"] = packet["packet_sha256"] = packet_digest(packet)
        return accepted
    with sqlite3.connect(c["profile"]) as conn:
        store = TickerIdentityTransitionStore(conn, clock=lambda: c["now"][0])
        preview = store.get(result["transition_id"])["approved_preview"]
        assert store._provider_guard(preview, at=c["now"][0], automation=False) == ()
        monkeypatch.setattr(review, "acceptance_for", changed)
        assessment = SecurityLifecycleInvestigationStore(conn).get_assessment(preview["assessment_id"])
        blockers = review.investigation_transition_guard(conn, assessment=assessment,
            observation_sha256=preview["observation_fingerprint_sha256"], transition_kind=preview["transition_kind"],
            successor_ticker=preview["successor_ticker"], at=c["now"][0])
        assert "web_acceptance_invalid" in blockers
    assert "OLD" in c["sources"]()


@pytest.mark.parametrize("value", [None, {}, [{"url": "https://user:secret@example.com/private", "reason": "source_unavailable", "corpus": None}],
    [{"url": URL, "reason": "raw error: private-token", "corpus": None}]])
def test_current_adoption_rejects_malformed_saved_gaps_even_with_valid_payload_hash(tmp_path, monkeypatch, value):
    c = gap_context(tmp_path, monkeypatch)
    with sqlite3.connect(c["profile"]) as conn:
        saved = json.loads(conn.execute("SELECT payload_json FROM lifecycle_investigation_results").fetchone()[0])
        saved["gaps"] = value
        damage_saved_rows(conn, "lifecycle_investigation_results",
            "UPDATE lifecycle_investigation_results SET payload_json=?,payload_sha256=?", (canonical_json(saved), digest_json(saved)))
    before = rows(c)
    with pytest.raises(ValueError, match="investigation_integrity|web_source_gaps_invalid"):
        prepare(c)
    assert rows(c) == before and "OLD" in c["sources"]()


def test_current_gap_acknowledgement_never_waives_active_provider_evidence(tmp_path, monkeypatch):
    from tests.test_security_lifecycle_population import active
    c = gap_context(tmp_path, monkeypatch)
    packet = prepare(c)
    c["checks"].record(ticker="OLD", at="2026-09-08T01:00:01Z",
        evidence=(active("OLD", at="2026-09-08T01:00:01Z"),), diagnostics={})
    c["now"][0] = "2026-09-08T01:00:02Z"
    fresh = prepare(c)
    assert not fresh["ready"] and "web_active_listing_conflict" in fresh["block_reasons"]
    assert fresh["source_gaps"] == GAPS
    before = rows(c)
    with pytest.raises((ValueError, RuntimeError), match="review_changed"):
        confirm(c, packet, acknowledge_source_gaps=True)
    assert rows(c) == before and "OLD" in c["sources"]()


def test_current_review_has_empty_gaps_without_internal_source_fields(tmp_path):
    c = context(tmp_path)
    packet = project_packet(prepare(c))
    assert packet["source_gaps"] == []
    assert not {"source_failure_urls", "source_failures", "web"} & set(packet)
