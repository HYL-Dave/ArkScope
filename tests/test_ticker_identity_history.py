"""Historical explanation at the real API boundary, without current/provider work."""

import json
from pathlib import Path
import sqlite3

import pytest

from src.ticker_identity_transition import TransitionOptions, TickerIdentityTransitionStore
from tests.test_security_lifecycle_review import deny_network, rows
from tests.test_security_lifecycle_review_routes import client
from tests.test_security_lifecycle_terminal_workflow import setup_workflow


def publisher_date_fixture(monkeypatch, value):
    from tests import test_lifecycle_investigation_review as owner
    original = owner.corpus
    def corpus(*args, **kwargs):
        path = original(*args, **kwargs)
        with sqlite3.connect(path) as conn:
            conn.execute("UPDATE news_articles SET published_at=?", (value,))
        return path
    monkeypatch.setattr(owner, "corpus", corpus)


def legacy(c):
    options = TransitionOptions(execute_on=c["ended"])
    preview = c["service"].preview_case(c["case_id"], options=options)
    transition = c["service"].approve_case(c["case_id"], options=options,
        preview_sha256=preview["preview_sha256"], before_write=lambda: None)
    assert c["service"].execute_transition(transition["transition_id"],
        preview_sha256=preview["preview_sha256"], before_write=lambda: None)["status"] == "applied"
    return transition


def history(c, monkeypatch):
    response = client(c, monkeypatch, []).get("/security-lifecycle/transition-activity")
    assert response.status_code == 200, response.text
    return response.json()["items"]


def damage_saved_rows(conn, table, statement, parameters=()):
    triggers = conn.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name=?", (table,)).fetchall()
    for name, _ in triggers:
        conn.execute(f'DROP TRIGGER "{name}"')
    conn.execute(statement, parameters)
    for _, sql in triggers:
        conn.execute(sql)


@pytest.mark.parametrize("ticker,ended", [("ARCH", "2025-01-15"), ("LTHM", "2024-01-05"), ("TA", "2023-05-16")])
def test_legacy_attended_history_explains_original_provider_evidence_not_latest_check(tmp_path, monkeypatch, ticker, ended):
    c = setup_workflow(tmp_path, ticker=ticker, ended=ended, event_available=False)
    legacy(c)
    c["checks"].record(ticker=ticker, at="2026-09-07T01:00:00Z", evidence=(), diagnostics={}, blockers=("massive_unavailable",))
    before = rows(c)
    decision = history(c, monkeypatch)[0].get("decision")
    assert decision is not None, "History drops the recorded assessment and provider provenance"
    assert decision["summary"] == "Reviewed explicit delisting with current trading checks; no acquirer alias is authorized."
    assert decision["impact"] == "Stop collection, preserve history."
    assert decision["method"] == "provider_review"
    assert decision["approval_authority"] == "attended_user"
    assert decision["model"] is None
    assert decision["event_date"] == ended
    assert decision["observed_at"] == "2026-09-05T01:00:00Z"
    assert {source["name"] for source in decision["sources"]} == {"Massive", "EODHD", "Nasdaq"}
    assert {source["listing_status"] for source in decision["sources"]} >= {"inactive", "not_found"}
    assert all(source["ticker"] == ticker for source in decision["sources"])
    assert any("Continuation could not be checked; this does not prove that no successor exists." in note for note in decision["limitations"])
    assert decision["gaps"] == ["legacy_assessment_unsealed"]
    assert rows(c) == before
    assert not any(key in json.dumps(decision) for key in ("sha256", "credential_id", "evidence_id", "source_locator", "run_id"))


def test_approved_review_snapshot_survives_later_assessment_and_source_changes(tmp_path, monkeypatch):
    from tests.test_security_lifecycle_review import context, prepare, confirm
    c = context(tmp_path)
    packet = prepare(c)
    confirm(c, packet)
    with sqlite3.connect(c["profile"]) as conn:
        conn.execute("UPDATE security_lifecycle_assessments SET conclusion='Different later text',impact_summary='Different effect'")
    c["checks"].record(ticker="OLD", at="2026-09-07T01:00:00Z", evidence=(), diagnostics={}, blockers=())
    before = rows(c)
    decision = history(c, monkeypatch)[0].get("decision")
    assert decision is not None
    assert decision["summary"] == "Reviewed explicit delisting with current trading checks; no acquirer alias is authorized."
    assert decision["impact"] == "Stop collection, preserve history."
    assert {source["name"] for source in decision["sources"]} == {"Massive", "EODHD", "Nasdaq"}
    assert rows(c) == before


@pytest.mark.parametrize("provider,auth,model", [
    ("anthropic", "claude_code_oauth", "claude-sonnet-5"), ("anthropic", "api_key", "claude-sonnet-5"),
    ("openai", "chatgpt_oauth", "gpt-5.6-luna"), ("openai", "api_key", "gpt-5.6-luna"),
])
def test_target_investigation_history_names_the_recorded_model_and_cited_news_only(tmp_path, monkeypatch, provider, auth, model):
    from tests.test_lifecycle_investigation_review import context
    from src.lifecycle_web_review import prepare, confirm
    c = context(tmp_path, provider=provider, auth=auth)
    options = TransitionOptions(execute_on=None)
    packet = prepare(c["service"], c["run_id"], options=options)
    assert confirm(c["service"], c["run_id"], packet_sha256=packet["packet_sha256"], action=packet["action"],
        options=options, before_write=lambda: None)["status"] == "applied"
    def forbidden(*args, **kwargs):
        raise AssertionError("History must not re-run source parsing or current model admission")
    monkeypatch.setattr("src.lifecycle_investigation.adoption.validated_read", forbidden)
    monkeypatch.setattr("src.lifecycle_investigation.adoption.as_adoption", forbidden)
    monkeypatch.setattr("src.security_lifecycle_web_contract.validate_selection", forbidden)
    before = rows(c)
    decision = history(c, monkeypatch)[0].get("decision")
    assert decision is not None
    assert decision["summary"] == "The common stock no longer trades."
    assert decision["method"] == "llm_investigation"
    assert decision["approval_authority"] == "attended_user"
    assert decision["model"] == {"provider": provider, "auth_mode": auth, "model": model}
    assert decision["event_date"] == "2026-09-01"
    assert len(decision["sources"]) == 1, "Citations to different passages of one article are one source"
    assert decision["sources"][0]["kind"] == "local_news"
    assert decision["sources"][0]["url"] == "https://issuer.example/notice"
    assert decision["gaps"] == []
    assert rows(c) == before
    assert not any(key in json.dumps(decision) for key in ("credential_id", "remote_id", "sha256", "passage_id", "run_id"))


def test_legacy_web_investigation_history_preserves_auth_model_and_source_link(tmp_path, monkeypatch):
    from tests.test_lifecycle_web_review import context, prepare, confirm
    c = context(tmp_path, provider="anthropic", auth="claude_code_oauth")
    confirm(c, prepare(c))
    monkeypatch.setattr("src.lifecycle_web_store.LifecycleWebStore._decode_page",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("Do not parse full source bodies in history")))
    before = rows(c)
    decision = history(c, monkeypatch)[0].get("decision")
    assert decision is not None
    assert decision["method"] == "llm_investigation"
    assert decision["model"] == {"provider": "anthropic", "model": "claude-sonnet-5", "auth_mode": "claude_code_oauth"}
    assert decision["summary"] == "The old NASDAQ listing ended; no claim is made about a replacement."
    assert decision["sources"][0]["url"] == "https://ir.example.com/notice"
    assert decision["sources"][0]["observed_at"] == "2026-09-06T01:00:00Z"
    assert rows(c) == before


def test_acknowledgement_and_reversal_keep_original_explanation(tmp_path, monkeypatch):
    c = setup_workflow(tmp_path)
    transition = legacy(c)
    item = history(c, monkeypatch)[0]
    assert item.get("decision") is not None
    browser = client(c, monkeypatch, [])
    response = browser.post(f"/security-lifecycle/transition-activity/{item['activity_id']}/acknowledge")
    assert response.status_code == 200, response.text
    assert response.json()["decision"] == item["decision"]
    with sqlite3.connect(c["profile"]) as conn:
        assert TickerIdentityTransitionStore(conn).reverse(transition["transition_id"], trigger="attended_user")["status"] == "reversed"
    assert [row["activity_type"] for row in history(c, monkeypatch)] == ["reversed", "applied"]
    assert all(row["decision"] == item["decision"] for row in history(c, monkeypatch))


def test_missing_bound_provider_receipt_does_not_borrow_a_later_receipt(tmp_path, monkeypatch):
    c = setup_workflow(tmp_path)
    legacy(c)
    with sqlite3.connect(c["profile"]) as conn:
        damage_saved_rows(conn, "security_lifecycle_provider_checks", "DELETE FROM security_lifecycle_provider_checks")
    c["checks"].record(ticker="OLD", at="2026-09-07T01:00:00Z", evidence=c["material"], diagnostics={})
    decision = history(c, monkeypatch)[0].get("decision")
    assert decision is not None
    assert decision["summary"] is not None
    assert decision["sources"] == []
    assert decision["observed_at"] is None
    assert decision["gaps"] == ["legacy_assessment_unsealed", "sources_missing"]


def test_unsealed_legacy_assessment_is_qualified_even_when_its_fingerprint_still_matches(tmp_path, monkeypatch):
    c = setup_workflow(tmp_path)
    legacy(c)
    before = history(c, monkeypatch)[0]["decision"]
    assert "legacy_assessment_unsealed" in before["gaps"]
    with sqlite3.connect(c["profile"]) as conn:
        conn.execute("UPDATE security_lifecycle_assessments SET conclusion='Replacement explanation',effective_date='2025-06-01'")
    after = history(c, monkeypatch)[0]["decision"]
    assert "legacy_assessment_unsealed" in after["gaps"]
    assert after["summary"] == "Replacement explanation"
    assert after["sources"] == before["sources"]


@pytest.mark.parametrize("bad", ["[]", "null", '"bad"', '{"snapshot_format":1,"observation":[]}'])
def test_malformed_unbound_provider_observation_cannot_poison_bound_history(tmp_path, monkeypatch, bad):
    c = setup_workflow(tmp_path)
    legacy(c)
    before = history(c, monkeypatch)[0]["decision"]
    c["checks"].record(ticker="OLD", at="2026-09-07T01:00:00Z", evidence=(), diagnostics={})
    with sqlite3.connect(c["profile"]) as conn:
        damage_saved_rows(conn, "security_lifecycle_provider_checks",
            "UPDATE security_lifecycle_provider_checks SET observation_json=? WHERE rowid=(SELECT max(rowid) FROM security_lifecycle_provider_checks)", (bad,))
    assert history(c, monkeypatch)[0]["decision"] == before


@pytest.mark.parametrize("field,value", [("url", "https://unrelated.example/forged"),
    ("retrieved_at", "2026-09-06T02:00:00Z"), ("text_sha256", "f" * 64), ("body_sha256", "f" * 64)])
def test_legacy_web_source_metadata_must_match_the_approved_passage_digest(tmp_path, monkeypatch, field, value):
    from tests.test_lifecycle_web_review import context, prepare, confirm
    c = context(tmp_path, provider="anthropic", auth="claude_code_oauth")
    confirm(c, prepare(c))
    with sqlite3.connect(c["profile"]) as conn:
        damage_saved_rows(conn, "lifecycle_web_pages",
            "UPDATE lifecycle_web_pages SET page_json=json_set(page_json,?,?)", (f"$.{field}", value))
    decision = history(c, monkeypatch)[0]["decision"]
    assert decision["summary"] == "The old NASDAQ listing ended; no claim is made about a replacement."
    assert decision["sources"] == []
    assert decision["gaps"] == ["sources_missing"]


@pytest.mark.parametrize("published", ["September 1, 2026", "Sep 1, 2026 08:30 ET"])
def test_history_preserves_valid_publisher_date_text_from_the_real_investigation(tmp_path, monkeypatch, published):
    from tests.test_lifecycle_investigation_review import context
    from src.lifecycle_web_review import prepare, confirm
    publisher_date_fixture(monkeypatch, published)
    c = context(tmp_path, provider="anthropic", auth="claude_code_oauth")
    options = TransitionOptions(execute_on=None)
    packet = prepare(c["service"], c["run_id"], options=options)
    confirm(c["service"], c["run_id"], packet_sha256=packet["packet_sha256"], action=packet["action"], options=options, before_write=lambda: None)
    decision = history(c, monkeypatch)[0]["decision"]
    assert decision["gaps"] == []
    assert decision["sources"][0]["published_at"] == published


def test_damaged_approval_does_not_erase_activity_or_offer_a_fabricated_explanation(tmp_path, monkeypatch):
    from tests.test_security_lifecycle_review import context, prepare, confirm
    c = context(tmp_path)
    confirm(c, prepare(c))
    with sqlite3.connect(c["profile"]) as conn:
        value = json.loads(conn.execute("SELECT approved_preview_json FROM ticker_identity_transitions").fetchone()[0])
        value["review_confirmation"]["packet"]["finding"]["conclusion"] = "Unbound false story"
        conn.execute("UPDATE ticker_identity_transitions SET approved_preview_json=?", (json.dumps(value),))
    before = rows(c)
    result = history(c, monkeypatch)
    assert len(result) == 1 and result[0]["activity_type"] == "applied"
    assert result[0].get("decision") is not None
    assert result[0]["decision"]["summary"] is None
    assert result[0]["decision"]["gaps"] == ["record_invalid"]
    assert "Unbound false story" not in json.dumps(result)
    assert rows(c) == before


@pytest.mark.parametrize("lane", ("provider", "llm"))
def test_shared_frontend_fixture_is_owned_by_real_persisted_history(tmp_path, monkeypatch, lane):
    if lane == "provider":
        c = setup_workflow(tmp_path, event_available=False)
        legacy(c)
    else:
        from tests.test_lifecycle_investigation_review import context
        from src.lifecycle_web_review import prepare, confirm
        publisher_date_fixture(monkeypatch, "September 1, 2026")
        c = context(tmp_path, provider="anthropic", auth="claude_code_oauth")
        options = TransitionOptions(execute_on=None)
        packet = prepare(c["service"], c["run_id"], options=options)
        confirm(c["service"], c["run_id"], packet_sha256=packet["packet_sha256"], action=packet["action"],
            options=options, before_write=lambda: None)
    expected = json.loads((Path(__file__).parent / "fixtures/ticker_history_decisions_v1.json").read_text())[lane]
    assert history(c, monkeypatch)[0]["decision"] == expected
