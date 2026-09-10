"""Current operator truth over the complete population, not the old SEC queue."""

import hashlib
import json
import socket
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from src.profile_state import ProfileStateStore
from src.security_lifecycle_provider_store import ProviderCheckStore
from src.security_lifecycle_listing_evidence import _evidence
from src.tools.security_lifecycle_tools import SecurityLifecycleReadService
from tests.test_security_lifecycle_population import active, persist, sec, stores, terminal
from tests.test_security_lifecycle_provider_authority import NOW, terminal_records
from tests.test_security_lifecycle_review import context, prepare, confirm


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("current_review_must_not_use_network")
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)


def reader(market, profile, sources):
    return SecurityLifecycleReadService(market_db_path=str(market), profile_db_path=str(profile), source_loader=sources)


def current(c, **kwargs):
    return reader(c["market"], c["profile"], c["sources"]).list_current_reviews(at=c["now"][0], **kwargs)


def test_current_reviews_account_for_unpersisted_missing_and_recovered_cases(tmp_path):
    market, profile = stores(tmp_path)
    sec(market, "NEW", "unpersisted")
    missing = persist(profile, {"source": "sec_edgar", "source_ref": "gone", "ticker": "GONE"})
    checks = ProviderCheckStore(profile)
    checks.record(ticker="OLD", at=NOW, evidence=terminal("OLD"), diagnostics={})
    checks.record(ticker="RECOVER", at=NOW, evidence=(), diagnostics={})
    later = "2026-09-05T01:01:00Z"
    checks.record(ticker="RECOVER", at=later, evidence=(active("RECOVER", at=later),), diagnostics={})
    checks.record(ticker="LIVE", at=NOW, evidence=(active("LIVE"),), diagnostics={})
    checks.record(ticker="UNTRACKED", at=NOW, evidence=(active("UNTRACKED"),), diagnostics={})
    service = reader(market, profile, lambda: {t: ("manual_lists",) for t in ("NEW", "GONE", "OLD", "RECOVER", "LIVE", "UNSEEN")})
    result = service.list_current_reviews(at=later)
    assert result["version"] == 1
    assert result["source_context"] == "available"
    assert result["coverage"] == {"tracked": 6, "confirmed_active": 2, "unconfirmed": 4}
    assert result["counts"] == {"attention": 3, "history": 1}
    assert result["page"] == {"offset": 0, "limit": 50, "total": 3}
    by_ticker = {row["ticker"]: row for row in result["items"]}
    assert set(by_ticker) == {"NEW", "GONE", "OLD"}
    assert by_ticker["GONE"]["case_ids"] == [missing]
    assert by_ticker["GONE"]["reason"] == "source_missing"
    assert by_ticker["GONE"]["next_action"]["kind"] == "recheck"
    assert by_ticker["OLD"]["finding"] == "old_listing_inactive"
    assert by_ticker["OLD"]["next_action"]["kind"] == "recheck"  # No persisted assessment yet.
    assert by_ticker["OLD"]["collection"] == {"state": "tracking", "sources": ["manual_lists"]}
    assert by_ticker["NEW"]["issuer_name"] == "Synthetic issuer"
    history = service.list_current_reviews(at=later, view="history")
    assert [row["ticker"] for row in history["items"]] == ["RECOVER"]
    assert history["items"][0]["finding"] == "active"
    assert history["items"][0]["next_action"]["kind"] == "none"


def test_current_review_and_list_share_one_closed_projection(tmp_path):
    c = context(tmp_path)
    service = reader(c["market"], c["profile"], c["sources"])
    row = service.list_current_reviews(at=NOW)["items"][0]
    assert set(row) == {"review_id", "case_ids", "ticker", "issuer_name", "bucket", "finding", "reason", "collection",
                        "listing", "continuation", "observed_at", "next_check_at", "diagnostics", "next_action", "source_checks", "source_notices"}
    assert row["next_action"]["kind"] == "review_removal"
    assert row["next_action"]["assessment_id"] == c["assessment_id"]
    assert row["next_action"]["state"] == "not_prepared"
    assert service.get_current_review(row["review_id"], at=NOW) == {"version": 1, "as_of": NOW, "item": row, "web_runs": []}
    text = json.dumps(row)
    for private in ("snapshot_sha256", "source_locator", "_ordinal", "canonical_payload", "decision_provenance", "BBG", "source_ref"):
        assert private not in text
    assert {check["provider"] for check in row["source_checks"]} == {"massive", "eodhd", "nasdaq"}
    assert sorted((check["check"], check["status"]) for check in row["source_checks"] if check["provider"] == "massive") == [
        ("delisting", "inactive"), ("otc", "not_found"), ("stocks", "not_found")]


def test_applied_removal_keeps_unresolved_continuation_in_attention(tmp_path):
    c = context(tmp_path)
    receipt = confirm(c, prepare(c))
    result = current(c)
    assert result["counts"] == {"attention": 1, "history": 0}
    row = result["items"][0]
    assert row["reason"] == "continuation_followup_pending"
    assert row["collection"] == {"state": "not_tracking", "sources": []}
    assert row["next_action"]["state"] == "applied"
    assert row["next_action"]["current_effects_match"] is True
    assert row["next_action"]["transition_id"] == receipt["transition_id"]
    assert row["next_action"]["kind"] == "recheck"
    assert row["continuation"]["state"] == "unavailable"
    assert "continuation" in row["diagnostics"]["missing_checks"]


def test_current_projection_checks_actual_effects_not_just_applied_status(tmp_path):
    c = context(tmp_path)
    confirm(c, prepare(c))
    ProfileStateStore(c["profile"]).set_universe_hidden("OLD", False)
    row = current(c)["items"][0]
    assert row["next_action"]["state"] == "applied_state_changed"
    assert row["next_action"]["current_effects_match"] is False
    assert row["next_action"]["can_reverse"] is False
    assert row["reason"] == "applied_state_changed"
    assert row["bucket"] == "attention"


def test_prepared_or_accepted_assessment_is_not_confirmation(tmp_path):
    c = context(tmp_path, accepted=True)
    prepare(c)
    row = current(c)["items"][0]
    assert row["next_action"]["state"] == "not_prepared"
    assert row["next_action"]["transition_id"] is None
    assert row["collection"]["state"] == "tracking"


def test_changed_observation_does_not_offer_an_old_assessment_as_current(tmp_path):
    c = context(tmp_path)
    c["checks"].record(ticker="OLD", at="2026-09-05T01:01:00Z", evidence=c["material"], diagnostics={})
    c["now"][0] = "2026-09-05T01:01:00Z"
    row = current(c)["items"][0]
    assert row["finding"] == "old_listing_inactive"
    assert row["next_action"]["assessment_id"] is None
    assert row["next_action"]["kind"] == "recheck"


def test_current_sources_unknown_is_not_an_empty_healthy_universe(tmp_path):
    market, profile = stores(tmp_path)
    sec(market, "OLD", "old")
    result = reader(market, profile, lambda: None).list_current_reviews(at=NOW)
    assert result["source_context"] == "unavailable"
    assert result["coverage"] == {"tracked": None, "confirmed_active": None, "unconfirmed": None}
    assert result["items"][0]["collection"] == {"state": "unavailable", "sources": []}


@pytest.mark.parametrize("bad", ({"OLD": "manual_lists"}, {"OLD": ["invented"]}, {"OLD": None}, [], {"OLD": []}))
def test_malformed_collection_sources_are_rejected_not_coerced(tmp_path, bad):
    from src.security_lifecycle_population import LifecyclePopulationUnavailable
    market, profile = stores(tmp_path)
    sec(market, "OLD", "old")
    with pytest.raises(LifecyclePopulationUnavailable, match="current_sources_invalid"):
        reader(market, profile, lambda: bad).list_current_reviews(at=NOW)


def test_current_review_read_creates_no_files_or_writes_and_never_reads_keys(tmp_path, monkeypatch):
    market, profile = stores(tmp_path)
    sec(market, "OLD", "old")
    with sqlite3.connect(profile) as conn:
        conn.execute("CREATE TABLE private_credentials(secret TEXT)")
        conn.execute("INSERT INTO private_credentials VALUES ('never-read-this')")
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (market, profile)}
    connect = sqlite3.connect
    def readonly(path, *args, **kwargs):
        assert "mode=ro" in str(path)
        conn = connect(path, *args, **kwargs)
        def authorizer(action, first, second, database, trigger):
            assert not (action == sqlite3.SQLITE_READ and first == "private_credentials")
            assert action not in {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE}
            return sqlite3.SQLITE_OK
        conn.set_authorizer(authorizer)
        return conn
    monkeypatch.setattr(sqlite3, "connect", readonly)
    row = reader(market, profile, lambda: {"OLD": ("manual_lists",)}).list_current_reviews(at=NOW)["items"][0]
    assert row["next_check_at"] is None
    assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (market, profile)}


def test_current_review_filters_paginate_without_hiding_population_counts(tmp_path):
    market, profile = stores(tmp_path)
    for ticker in ("AAA", "BBB", "CCC"):
        sec(market, ticker, ticker)
    service = reader(market, profile, lambda: {})
    result = service.list_current_reviews(at=NOW, limit=1, offset=1)
    assert result["counts"] == {"attention": 3, "history": 0}
    assert result["page"] == {"offset": 1, "limit": 1, "total": 3}
    assert [row["ticker"] for row in result["items"]] == ["BBB"]
    result = service.list_current_reviews(at=NOW, ticker="C")
    assert [row["ticker"] for row in result["items"]] == ["CCC"]
    assert result["page"]["total"] == 1
    assert result["counts"]["attention"] == 3
    with pytest.raises(KeyError):
        service.get_current_review("slpr_" + "0" * 64, at=NOW)


@pytest.mark.parametrize("options", ({"view": "invented"}, {"limit": 0}, {"limit": 201}, {"offset": -1}, {"limit": True}))
def test_current_review_rejects_invalid_read_options(tmp_path, options):
    market, profile = stores(tmp_path)
    with pytest.raises(ValueError):
        reader(market, profile, lambda: {}).list_current_reviews(at=NOW, **options)


@pytest.mark.parametrize("at", ("2026-09-05T01:00:00Z", "2026-11-01T03:30:00Z", "2027-03-14T04:30:00Z"))
def test_current_review_scheduled_state_uses_new_york_not_utc(tmp_path, at):
    from src.ticker_identity_transition import TransitionOptions
    from tests.test_security_lifecycle_review import reclock
    c = context(tmp_path)
    reclock(c, at)
    c["options"] = TransitionOptions(execute_on=at[:10])
    assert confirm(c, prepare(c))["status"] == "scheduled"
    row = current(c)["items"][0]
    assert row["next_action"]["state"] == "scheduled"
    assert row["next_action"]["kind"] == "none"
    assert row["next_action"]["current_effects_match"] is None
    assert row["reason"] == "action_scheduled"
    assert row["collection"]["state"] == "tracking"
    c["now"][0] = at[:10] + "T13:00:00Z"
    due = current(c)["items"][0]
    assert due["next_action"]["state"] == "approved"
    assert due["next_action"]["kind"] == "resume"
    assert due["reason"] == "action_pending"


@pytest.mark.parametrize("status", ("blocked", "cancelled", "reversed"))
def test_current_review_does_not_misreport_stopped_action_as_applied(tmp_path, monkeypatch, status):
    from tests.test_security_lifecycle_review import stage_approval
    c = context(tmp_path)
    packet, transition_id = stage_approval(c, monkeypatch)
    if status == "blocked":
        ProfileStateStore(c["profile"]).import_lists([{"name": "New", "kind": "custom", "tickers": ["OLD"]}])
        assert confirm(c, packet)["status"] == "blocked"
    elif status == "cancelled":
        c["service"].cancel_transition(transition_id, before_write=lambda: None)
    else:
        confirm(c, packet)
        c["service"].reverse_transition(transition_id, before_write=lambda: None)
    row = current(c)["items"][0]
    assert row["next_action"]["state"] == status
    assert row["next_action"]["kind"] == "recheck"
    assert row["next_action"]["current_effects_match"] is None
    assert row["collection"]["state"] == "tracking"
    if status == "blocked":
        assert row["next_action"]["block_reasons"]


def test_source_loader_changes_invalidate_the_read_instead_of_mixing_collection_states(tmp_path):
    from src.security_lifecycle_population import LifecyclePopulationUnavailable
    market, profile = stores(tmp_path)
    sec(market, "OLD", "old")
    values = iter([{"OLD": ("manual_lists",)}, {}])
    with pytest.raises(LifecyclePopulationUnavailable, match="current_snapshot_changed"):
        reader(market, profile, lambda: next(values)).list_current_reviews(at=NOW)


def test_new_source_observation_between_population_and_receipt_read_is_rejected(tmp_path, monkeypatch):
    from src import security_lifecycle_current as module
    c = context(tmp_path)
    original = module._project
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        c["checks"].record(ticker="OLD", at="2026-09-05T01:01:00Z", evidence=c["material"], diagnostics={})
        return result
    monkeypatch.setattr(module, "_project", changed)
    with pytest.raises(module.LifecyclePopulationUnavailable, match="current_snapshot_changed"):
        current(c)


def test_reused_ticker_current_tracking_is_not_assigned_to_historical_security(tmp_path):
    market, profile = stores(tmp_path)
    checks = ProviderCheckStore(profile)
    material = tuple(_evidence(replace(row, primary_exchange="XNYS", security_type="CS", issuer_cik="0000000001")) for row in terminal_records())
    checks.record(ticker="OLD", at=NOW, evidence=material, diagnostics={})
    later = "2026-09-05T01:01:00Z"
    checks.record(ticker="OLD", at=later, evidence=(active("OLD", figi="BBG000B9XRY4", at=later),), diagnostics={})
    service = reader(market, profile, lambda: {"OLD": ("manual_lists",)})
    new = service.list_current_reviews(at=later)["items"][0]
    old = service.list_current_reviews(at=later, view="history")["items"][0]
    assert new["review_id"] != old["review_id"]
    assert new["reason"] == "listing_identity_changed" and new["collection"]["state"] == "tracking"
    assert old["collection"] == {"state": "historical", "sources": []}
    assert old["next_action"]["kind"] == "none"
    assert new["source_checks"][0]["status"] == "active"
    assert any(check["status"] == "inactive" for check in old["source_checks"])


@pytest.mark.parametrize("suffix", ("#literal", "%23literal", " with spaces"))
def test_current_receipt_read_uses_the_literal_selected_database(tmp_path, suffix):
    c = context(tmp_path)
    confirm(c, prepare(c))
    selected = c["profile"].with_name(c["profile"].name + suffix)
    with sqlite3.connect(c["profile"]) as source, sqlite3.connect(selected) as target:
        source.backup(target)
    row = reader(c["market"], selected, lambda: {"LIVE": ("manual_lists",)}).list_current_reviews(at=NOW)["items"][0]
    assert row["next_action"]["state"] == "applied"


def test_bad_confirmation_receipt_never_becomes_displayed_success(tmp_path):
    from src.security_lifecycle_population import LifecyclePopulationUnavailable
    from src.ticker_identity_transition import profile_snapshot_sha256
    c = context(tmp_path)
    confirm(c, prepare(c))
    with sqlite3.connect(c["profile"]) as conn:
        value = json.loads(conn.execute("SELECT approved_preview_json FROM ticker_identity_transitions").fetchone()[0])
        value["review_confirmation"]["actor"] = "automation_policy"
        value["preview_sha256"] = profile_snapshot_sha256(value)
        conn.execute("UPDATE ticker_identity_transitions SET approved_preview_json=?,approved_preview_sha256=?", (json.dumps(value), value["preview_sha256"]))
    with pytest.raises(LifecyclePopulationUnavailable):
        current(c)


def test_always_active_coverage_expires_instead_of_staying_green(tmp_path):
    market, profile = stores(tmp_path)
    ProviderCheckStore(profile).record(ticker="LIVE", at=NOW, evidence=(active("LIVE"),), diagnostics={})
    result = reader(market, profile, lambda: {"LIVE": ("manual_lists",)}).list_current_reviews(at="2026-09-15T01:00:00Z")
    assert result["coverage"] == {"tracked": 1, "confirmed_active": 0, "unconfirmed": 1}
    assert result["items"][0]["finding"] == "unresolved"


def test_research_reads_exactly_the_same_current_projection_and_no_mutation_tool(tmp_path, monkeypatch):
    from src.tools import security_lifecycle_tools as tools
    from src.tools.registry import create_default_registry
    c = context(tmp_path)
    service = reader(c["market"], c["profile"], c["sources"])
    original_list, original_get = service.list_current_reviews, service.get_current_review
    expected = original_list(at=NOW)
    monkeypatch.setattr(service, "list_current_reviews", lambda **kwargs: original_list(at=NOW, **kwargs))
    monkeypatch.setattr(service, "get_current_review", lambda review_id: original_get(review_id, at=NOW))
    monkeypatch.setattr(tools, "SecurityLifecycleReadService", lambda **kwargs: service)
    payload = tools.list_security_lifecycle_reviews()
    assert payload == {"status": "ok", **expected}
    review_id = payload["items"][0]["review_id"]
    assert tools.get_security_lifecycle_review(review_id) == {"status": "ok", **original_get(review_id, at=NOW)}
    registry = create_default_registry()
    assert registry.get("list_security_lifecycle_cases") is None
    assert registry.get("get_security_lifecycle_case") is None
    assert registry.get("confirm_security_lifecycle_review") is None


def test_current_source_checks_keep_both_nasdaq_directories_identifiable(tmp_path):
    row = current(context(tmp_path))["items"][0]
    assert {check["directory"] for check in row["source_checks"] if check["provider"] == "nasdaq"} == {
        "nasdaq_listed", "other_listed"}
    assert all(check["directory"] is None for check in row["source_checks"] if check["provider"] != "nasdaq")


def test_current_action_keeps_the_receipt_kind_for_an_honest_resume_prompt(tmp_path, monkeypatch):
    from tests.test_security_lifecycle_review import stage_approval
    c = context(tmp_path)
    stage_approval(c, monkeypatch)
    row = current(c)["items"][0]
    assert row["next_action"]["kind"] == "resume"
    assert row["next_action"]["transition_kind"] == "terminal_delisting"


def test_current_case_deep_link_resolves_history_outside_the_visible_page(tmp_path):
    from src.security_lifecycle_investigation import case_id_for
    market, profile = stores(tmp_path)
    for i in range(55):
        sec(market, f"A{i}", f"filing-{i}")
    checks = ProviderCheckStore(profile)
    checks.record(ticker="RECOVER", at=NOW, evidence=(), diagnostics={})
    later = "2026-09-05T01:01:00Z"
    checks.record(ticker="RECOVER", at=later, evidence=(active("RECOVER", at=later),), diagnostics={})
    service = reader(market, profile, lambda: {})
    case_id = case_id_for("listing_authority", "listing:RECOVER", "RECOVER")
    assert len(service.list_current_reviews(at=later)["items"]) == 50
    resolved = service.list_current_reviews(at=later, case_id=case_id)
    assert len(resolved["items"]) == 1
    assert resolved["items"][0]["bucket"] == "history"
    assert case_id in resolved["items"][0]["case_ids"]
    assert resolved["page"]["total"] == 1
    assert service.list_current_reviews(at=later, case_id="not-present")["items"] == []


def test_sec_only_review_retains_the_actual_observation_time(tmp_path):
    market, profile = stores(tmp_path)
    sec(market, "OLD", "old")
    result = reader(market, profile, lambda: {}).list_current_reviews(at=NOW)
    assert result["items"][0]["observed_at"] == NOW
    assert result["items"][0]["source_notices"] == [{"form": "8-K", "filed_on": "2026-09-04", "text": "Listing notice.",
        "url": "https://www.sec.gov/Archives/fixture/filing.htm"}]
    assert result["items"][0]["next_action"]["kind"] == "recheck"


def current_contract_fixture(tmp_path):
    from src.security_lifecycle_review import project_packet
    c = context(tmp_path)
    attention = current(c)
    packet = prepare(c)
    confirmation = confirm(c, packet)
    def stable(value):
        if isinstance(value, dict):
            replacements = {"assessment_id": "sla_" + "a" * 32, "transition_id": "slt_" + "b" * 32,
                            "packet_sha256": "c" * 64, "preview_sha256": "c" * 64,
                            "activity_id": "slta_" + "a" * 32, "state_sha256": "d" * 64, "decision_provenance_sha256": "e" * 64}
            return {key: replacements[key] if key in replacements and item is not None else stable(item)
                    for key, item in value.items()}
        if isinstance(value, list):
            return [stable(item) for item in value]
        return value
    return stable({"attention": attention, "packet": project_packet(packet), "confirmation": confirmation, "applied": current(c),
                   "activity": c["service"].list_transition_activity(limit=50)})


def test_frontend_fixture_is_owned_by_the_real_persisted_workflow(tmp_path):
    expected = json.loads((Path(__file__).parent / "fixtures/lifecycle_current_v1.json").read_text())
    assert current_contract_fixture(tmp_path) == expected


@pytest.mark.parametrize("suffix", ("#literal", "%23literal", " with spaces"))
def test_lazy_audit_uses_the_same_literal_database_as_current_review(tmp_path, suffix):
    c = context(tmp_path)
    confirm(c, prepare(c))
    selected = c["profile"].with_name(c["profile"].name + suffix)
    with sqlite3.connect(c["profile"]) as source, sqlite3.connect(selected) as target:
        source.backup(target)
    c["profile"].unlink()
    audit = reader(c["market"], selected, lambda: {}).get_case_audit(c["case_id"])
    assert audit["case_id"] == c["case_id"]
    assert audit["assessment_history"][0]["status"] == "accepted"


@pytest.mark.parametrize("field", ("reason", "state"))
def test_current_closed_vocabulary_is_enforced_before_api_or_research(tmp_path, monkeypatch, field):
    from src import security_lifecycle_current as module
    from src.security_lifecycle_population import LifecyclePopulationUnavailable
    c = context(tmp_path)
    if field == "reason":
        original = module.build_population_manifest
        def invalid(*args, **kwargs):
            result = original(*args, **kwargs)
            result["reviews"][0]["reason"] = "unreviewed_reason"
            return result
        monkeypatch.setattr(module, "build_population_manifest", invalid)
    else:
        original = module._action
        def invalid(*args, **kwargs):
            result, case, assessment = original(*args, **kwargs)
            return {**result, "state": "unreviewed_state"}, case, assessment
        monkeypatch.setattr(module, "_action", invalid)
    with pytest.raises(LifecyclePopulationUnavailable, match="current_vocabulary_invalid"):
        current(c)
