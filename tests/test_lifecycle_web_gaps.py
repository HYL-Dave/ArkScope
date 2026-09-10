import json
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.lifecycle_web_projection import project_web_run
from src.lifecycle_web_schema import WebJournalError
from src.security_lifecycle_review import packet_digest, project_packet
from tests.test_lifecycle_web_review import context, confirm, prepare, rows
from tests.test_security_lifecycle_web_finding import finding_payload


URL = "https://financial-news.example.com/old-listing-update"
GAPS = [{"url": URL, "reason": "source_unavailable"}]
COMPLETION = {"source_failures": {"source-2": "source_unavailable"},
              "source_failure_urls": {"source-2": URL}, "source_requests": 2}


@pytest.mark.parametrize("provider,auth", [("openai", "api_key"), ("openai", "chatgpt_oauth"),
                                          ("anthropic", "api_key"), ("anthropic", "claude_code_oauth")])
@pytest.mark.parametrize("kind", ["terminal_delisting", "symbol_continuation"])
def test_gap_disclosure_follows_finding_review_and_explicit_human_receipt(tmp_path, provider, auth, kind):
    c = context(tmp_path, provider=provider, auth=auth, kind=kind, completion=COMPLETION)
    before = rows(c)
    run = c["web"].read(c["run_id"])
    assert run["source_failure_urls"] == COMPLETION["source_failure_urls"]
    public = project_web_run(run, at=c["now"][0])
    packet = prepare(c)
    assert packet["ready"] and packet["block_reasons"] == []
    assert public["source_gaps"] == packet["source_gaps"] == project_packet(packet)["source_gaps"] == GAPS
    assert rows(c) == before and "OLD" in c["sources"]()
    result = confirm(c, packet)
    assert result["status"] == "applied"
    assert ("NEW" in c["sources"]()) == (kind == "symbol_continuation")
    assert "OLD" not in c["sources"]() and "LIVE" in c["sources"]()
    with sqlite3.connect(c["profile"]) as conn:
        receipt, actor = conn.execute("SELECT packet_json,actor FROM lifecycle_web_acceptances").fetchone()
        assert actor == "attended_user" and json.loads(receipt)["source_gaps"] == GAPS
        assert conn.execute("SELECT author,acceptance_authority FROM security_lifecycle_assessments").fetchone() == ("human", "human")
    after = rows(c)
    assert confirm(c, packet)["status"] == "already_applied" and rows(c) == after


@pytest.mark.parametrize("change", ["omitted", "empty", "reason", "url"])
def test_confirmation_rejects_a_different_gap_disclosure_without_any_write(tmp_path, change):
    from src.lifecycle_web_review import confirm as adopt
    c = context(tmp_path, completion=COMPLETION)
    packet = prepare(c)
    if change == "omitted":
        packet.pop("source_gaps")
    elif change == "empty":
        packet["source_gaps"] = []
    else:
        packet["source_gaps"][0][change] = "source_timeout" if change == "reason" else "https://different.example.com/notice"
    packet["packet_sha256"] = packet_digest(packet)
    before = rows(c)
    with pytest.raises((ValueError, RuntimeError), match="review_changed"):
        adopt(c["service"], c["run_id"], packet_sha256=packet["packet_sha256"], action=packet["action"],
              options=c["options"], before_write=lambda: None, acknowledge_source_gaps=True)
    assert rows(c) == before and "OLD" in c["sources"]()


@pytest.mark.parametrize("acknowledgement", ["omitted", False, None, 1, "true"])
def test_old_or_malformed_confirmation_cannot_apply_unshown_gaps(tmp_path, monkeypatch, acknowledgement):
    from src.api.routes import lifecycle_investigation as api
    c = context(tmp_path, completion=COMPLETION)
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
        assert rows(c) == before and "OLD" in c["sources"]()
        accepted = client.post(route + "/confirm", json={**body, "acknowledge_source_gaps": True})
        assert accepted.status_code == 200 and accepted.json()["status"] == "applied", accepted.text
        assert "OLD" not in c["sources"]() and "LIVE" in c["sources"]()


@pytest.mark.parametrize("acknowledgement", [False, None, 1, "true"])
def test_direct_adoption_requires_literal_gap_acknowledgement(tmp_path, acknowledgement):
    from src.lifecycle_web_review import confirm as adopt
    c = context(tmp_path, completion=COMPLETION)
    packet = prepare(c)
    before = rows(c)
    with pytest.raises(WebJournalError, match="web_source_gaps_not_acknowledged"):
        adopt(c["service"], c["run_id"], packet_sha256=packet["packet_sha256"], action=packet["action"],
              options=c["options"], before_write=lambda: None, acknowledge_source_gaps=acknowledgement)
    assert rows(c) == before and "OLD" in c["sources"]()


@pytest.mark.parametrize("failed", [False, True])
def test_gap_acknowledgement_never_substitutes_for_a_completed_investigation(tmp_path, failed):
    from src.lifecycle_web_review import confirm as adopt
    c = context(tmp_path)
    row = c["web"].read(c["run_id"])
    identity = c["web"].start(case_id=c["case_id"], observation_sha256=row["observation_sha256"], request=row["request"],
        selection=row["selection"], options=row["options"], owner="worker-2", request_key="no-finding")["run_id"]
    if failed:
        c["web"].fail(identity, owner="worker-2", code="source_read_incomplete", control=c["web"].control(identity, owner="worker-2"))
    before = rows(c)
    with pytest.raises(ValueError, match="web_finding_not_complete"):
        adopt(c["service"], identity, packet_sha256="a" * 64, action="terminal_delisting", options=c["options"],
              before_write=lambda: None, acknowledge_source_gaps=True)
    assert rows(c) == before and "OLD" in c["sources"]()


@pytest.mark.parametrize("change,reason", [
    ({"contradictions": ["The exchange reports continued trading."]}, "material_contradiction"),
    ({"unresolved_conditions": ["The effective date cannot be established."]}, "finding_incomplete"),
    ({"effective_date": None, "effective_date_text": None}, "effective_date_missing"),
    ({"source_ticker": "OTHER"}, "security_identity_mismatch"),
    ({"citations": []}, "source_passage_missing"),
])
def test_disclosed_read_gap_does_not_override_missing_essential_proof(tmp_path, change, reason):
    c = context(tmp_path, completion={**COMPLETION, "payload": finding_payload(**change)})
    before = rows(c)
    packet = prepare(c)
    assert not packet["ready"] and reason in packet["block_reasons"]
    assert packet["source_gaps"] == GAPS
    assert packet["action"] is None
    assert rows(c) == before and "OLD" in c["sources"]()


@pytest.mark.parametrize("urls", [None, [], {}, {"source-3": URL}, {"source-2": None},
                                 {"source-2": "https://127.0.0.1/private"},
                                 {"source-2": "https://user:secret@example.com/private"}])
def test_present_malformed_gap_metadata_is_not_treated_as_legacy_absence(tmp_path, urls):
    with pytest.raises(WebJournalError, match="web_source_gaps_invalid"):
        context(tmp_path, completion={**COMPLETION, "source_failure_urls": urls})


@pytest.mark.parametrize("value", [None, [], {}, {"source-2": "http://plain.example.com/notice"}])
def test_reopened_journal_rejects_malformed_gap_urls_even_with_a_valid_payload_hash(tmp_path, value):
    from src.lifecycle_web_schema import TRIGGERS
    from src.lifecycle_web_store import _json, _sha
    c = context(tmp_path, completion=COMPLETION)
    with c["web"].connection(write=True) as conn:
        saved = json.loads(conn.execute("SELECT payload_json FROM lifecycle_web_results").fetchone()[0])
        saved["source_failure_urls"] = value
        trigger = "lifecycle_web_results_update_immutable"
        conn.execute("DROP TRIGGER " + trigger)
        conn.execute("UPDATE lifecycle_web_results SET payload_json=?,result_sha256=?", (_json(saved), _sha(saved)))
        conn.execute(TRIGGERS[trigger])
    with pytest.raises(WebJournalError, match="web_source_gaps_invalid"):
        c["web"].read(c["run_id"])
    assert "OLD" in c["sources"]()


@pytest.mark.parametrize("failures,urls", [
    ({"source-1": "source_unavailable"}, {"source-1": URL}),
    ({"source-2": "source_unavailable", "source-3": "source_read_timeout"}, {"source-2": URL, "source-3": URL + "-second"}),
    ({"source-2": "raw exception: token=not-public"}, {"source-2": URL}),
    ({2: "source_unavailable"}, {2: URL}),
    ({"source-2": None}, {"source-2": URL}),
])
def test_gap_metadata_cannot_relabel_read_pages_exceed_source_count_or_export_raw_errors(tmp_path, failures, urls):
    with pytest.raises(WebJournalError, match="web_source_gaps_invalid"):
        context(tmp_path, completion={**COMPLETION, "source_failures": failures, "source_failure_urls": urls})


@pytest.mark.parametrize("strip", [False, True])
def test_central_writer_rechecks_gap_disclosure_even_if_an_acceptance_is_resigned(tmp_path, monkeypatch, strip):
    from src import lifecycle_web_review as mod
    from src.ticker_identity_transition import TickerIdentityTransitionStore
    c = context(tmp_path, future=True, completion=COMPLETION)
    result = confirm(c, prepare(c))
    read_acceptance = mod.acceptance_for

    def changed(conn, assessment_id):
        accepted = read_acceptance(conn, assessment_id)
        packet = accepted["packet"]
        if strip:
            packet.pop("source_gaps")
        else:
            packet["source_gaps"] = []
        accepted["packet_sha256"] = packet["packet_sha256"] = packet_digest(packet)
        return accepted

    with sqlite3.connect(c["profile"]) as conn:
        store = TickerIdentityTransitionStore(conn, clock=lambda: c["now"][0])
        preview = store.get(result["transition_id"])["approved_preview"]
        assert store._provider_guard(preview, at=c["now"][0], automation=False) == ()
        monkeypatch.setattr(mod, "acceptance_for", changed)
        # No confirmation argument here: the stored disclosure must stand on
        # its own at the writer, not merely rely on a UI-supplied digest.
        assessment = mod.SecurityLifecycleInvestigationStore(conn).get_assessment(preview["assessment_id"])
        blockers = mod.web_transition_guard(conn, assessment=assessment, observation_sha256=preview["observation_fingerprint_sha256"],
            transition_kind=preview["transition_kind"], successor_ticker=preview["successor_ticker"], at=c["now"][0])
        assert "web_acceptance_invalid" in blockers
    assert "OLD" in c["sources"]()


def test_current_active_otc_evidence_still_vetoes_attended_adoption_with_read_gaps(tmp_path):
    from src.security_lifecycle_listing_evidence import _evidence
    from tests.test_security_lifecycle_provider_authority import record
    c = context(tmp_path, completion=COMPLETION)
    c["checks"].record(ticker="OLD", at=c["now"][0], evidence=[_evidence(record("massive_reference", "active", market="otc"))],
                       diagnostics={}, blockers=("massive_unavailable",))
    packet = prepare(c)
    assert not packet["ready"] and "web_active_listing_conflict" in packet["block_reasons"]
    assert packet["source_gaps"] == GAPS and "OLD" in c["sources"]()


def test_legacy_read_gap_is_visible_without_inventing_a_source_url(tmp_path):
    c = context(tmp_path, completion={"source_failures": {"source-2": "source_unavailable"}, "source_requests": 2})
    packet = prepare(c)
    assert packet["ready"] and packet["source_gaps"] == [{"url": None, "reason": "source_unavailable"}]
    assert project_web_run(c["web"].read(c["run_id"]), at=c["now"][0])["source_gaps"] == packet["source_gaps"]
    assert confirm(c, packet)["status"] == "applied"


def test_no_gaps_is_an_empty_list_not_unknown_and_no_extra_internal_fields_escape(tmp_path):
    c = context(tmp_path, completion={"source_failure_urls": {}})
    run = project_web_run(c["web"].read(c["run_id"]), at=c["now"][0])
    assert run["source_gaps"] == [] and project_packet(prepare(c))["source_gaps"] == []
    c2 = context(tmp_path / "with-gap", completion=COMPLETION)
    material = project_packet(prepare(c2))
    assert material["source_gaps"] == GAPS
    assert set(material["source_gaps"][0]) == {"url", "reason"}
    assert "source_failure_urls" not in material and "source_failures" not in material and "web" not in material
