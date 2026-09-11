"""Complete input accounting before any lifecycle reclassification or deletion."""

from dataclasses import replace
import hashlib
import json
import socket
import sqlite3
import sys

import pytest

from src.security_lifecycle import LifecycleObservation, ObservationKind, SecurityLifecycleStore
from src.security_lifecycle_investigation import (
    SecurityLifecycleInvestigationStore, case_id_for, observation_fingerprint,
)
from src.security_lifecycle_listing_evidence import _evidence
from src.security_lifecycle_provider_store import ProviderCheckStore
from src.security_lifecycle_schema import create_market_schema, create_profile_schema
from tests.test_security_lifecycle_provider_authority import FIGI, NOW, record, terminal_records


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("population_read_must_not_use_network")
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)


def stores(tmp_path):
    market, profile = tmp_path / "market.db", tmp_path / "profile.db"
    with sqlite3.connect(market) as conn:
        create_market_schema(conn)
    with sqlite3.connect(profile) as conn:
        create_profile_schema(conn)
    return market, profile


def sec(market, ticker, ref, *, cik="0000000001", form="8-K", filing_date="2026-09-04"):
    with sqlite3.connect(market) as conn:
        store = SecurityLifecycleStore(conn)
        store.upsert_observation(LifecycleObservation(
            ticker=ticker, cik=cik, issuer_name="Synthetic issuer", filing_date=filing_date,
            source="sec_edgar", source_ref=ref, filing_form=form, filing_items=("3.01",),
            evidence_url="https://www.sec.gov/Archives/fixture/filing.htm", description="Listing notice.",
            observed_at=NOW, kinds=(ObservationKind("listing_removal_notice"),),
        ))
        return store.get_observation("sec_edgar", ref, ticker)


def persist(profile, observation):
    with sqlite3.connect(profile) as conn:
        return SecurityLifecycleInvestigationStore(conn).ensure_case(
            source=observation["source"], source_ref=observation["source_ref"], ticker=observation["ticker"], at=NOW)


def active(ticker, *, figi=FIGI, venue="XNYS", security_type="CS", at=NOW):
    return _evidence(replace(record("massive_reference", "active", ticker=ticker, figi=figi),
                             primary_exchange=venue, security_type=security_type, issuer_cik="0000000001", retrieved_at=at))


def terminal(ticker):
    return tuple(_evidence(replace(row, ticker=ticker)) for row in terminal_records())


def manifest(market, profile, *, at=NOW):
    from src.security_lifecycle_population import read_population_manifest
    return read_population_manifest(market, profile, at=at)


def review_for(result, case_id):
    return next(row for row in result["reviews"] if case_id in row["case_ids"])


@pytest.mark.parametrize("journal_installed", (False, True))
def test_population_material_contains_only_current_reference_owners(tmp_path, journal_installed):
    from src.lifecycle_investigation.schema import install_journal
    from src.security_lifecycle_population import build_population_manifest, read_population_snapshot

    market, profile = stores(tmp_path)
    persist(profile, sec(market, "OLD", "retained"))
    if journal_installed:
        with sqlite3.connect(profile) as conn:
            install_journal(conn, at=NOW)
    snapshot = read_population_snapshot(market, profile, at=NOW)
    assert set(snapshot["material"]) == {"market_observations", "profile_tables", "identity_tables", "composed_cases", "schemas"}
    retention = build_population_manifest(snapshot)["retention"]
    assert "web_journal" not in retention
    assert retention["table_counts"]["security_lifecycle_cases"] == 1


@pytest.mark.parametrize("field", ("web_journal_inventory", "unreviewed_retention"))
def test_population_manifest_rejects_unexpected_material_even_when_sealed(tmp_path, field):
    from src.security_lifecycle_population import LifecyclePopulationUnavailable, build_population_manifest, read_population_snapshot

    market, profile = stores(tmp_path)
    snapshot = read_population_snapshot(market, profile, at=NOW)
    snapshot["material"][field] = {"installed": False, "runs": [], "calls": [], "actions": [], "pages": [], "results": [], "acceptances": []}
    unsigned = {key: snapshot[key] for key in ("version", "at", "material")}
    snapshot["sha256"] = hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()).hexdigest()
    with pytest.raises(LifecyclePopulationUnavailable, match="population_material_invalid"):
        build_population_manifest(snapshot)


@pytest.mark.parametrize("journal_installed", (False, True))
def test_population_manifest_accounts_for_all_three_input_populations(tmp_path, journal_installed):
    from src.lifecycle_investigation.schema import install_journal

    market, profile = stores(tmp_path)
    matched = persist(profile, sec(market, "MIX", "matched"))
    observation_only = sec(market, "NEW", "not-persisted")
    missing = persist(profile, {"source": "sec_edgar", "source_ref": "gone", "ticker": "GONE"})
    checks = ProviderCheckStore(profile)
    checks.record(ticker="RECOVER", at=NOW, evidence=(), diagnostics={})
    later = "2026-09-05T01:01:00Z"
    checks.record(ticker="RECOVER", at=later, evidence=(active("RECOVER", at=later),), diagnostics={})
    checks.record(ticker="LIVE", at=NOW, evidence=(active("LIVE"),), diagnostics={})
    checks.record(ticker="MIX", at=NOW, evidence=terminal("MIX"), diagnostics={})
    if journal_installed:
        with sqlite3.connect(profile) as conn:
            install_journal(conn, at=NOW)
    result = manifest(market, profile, at=later)
    provider_id = case_id_for("listing_authority", "listing:MIX", "MIX")
    recovered_id = case_id_for("listing_authority", "listing:RECOVER", "RECOVER")

    assert result["counts"] == {
        "market_observations": 2, "profile_cases": 2, "provider_checks": 4,
        "provider_latest": 3, "provider_projected_observations": 2,
        "composed_cases": 5, "legacy_visible_cases": 4, "legacy_screened_cases": 0,
        "current_reviews": 4, "history_reviews": 1, "coverage_only_tickers": 1,
    }
    assert result["sec_reconciliation"] == {
        "matched": [matched],
        "observation_only": [case_id_for("sec_edgar", "not-persisted", observation_only["ticker"])],
        "case_only": [missing],
    }
    assert result["provider_reconciliation"]["virtual"] == sorted([provider_id, recovered_id])
    assert len(result["input_mappings"]) == 8
    assert len({(row["population"], row["input_id"]) for row in result["input_mappings"]}) == 8
    assert all(row["destination"] and row["reason"] for row in result["input_mappings"])
    assert review_for(result, missing)["reason"] == "source_missing"
    assert review_for(result, provider_id)["finding"] == "old_listing_inactive"
    assert review_for(result, recovered_id)["bucket"] == "history"
    assert review_for(result, recovered_id)["finding"] == "active"
    assert result["coverage_only"] == ["LIVE"]
    assert result["automatic_actions"] == []
    assert result["deletion_authorized"] is False


@pytest.mark.parametrize("journal_installed", (False, True))
def test_raw_audit_composition_is_complete_and_read_only(tmp_path, monkeypatch, journal_installed):
    import src.security_lifecycle_investigation as investigation
    from src.lifecycle_investigation.schema import install_journal

    market, profile = stores(tmp_path)
    matched = persist(profile, sec(market, "MATCHED", "matched"))
    sec(market, "UNSAVED", "unsaved")
    missing = persist(profile, {"source": "sec_edgar", "source_ref": "gone", "ticker": "GONE"})
    if journal_installed:
        with sqlite3.connect(profile) as conn:
            install_journal(conn, at=NOW)
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in (market, profile)}
    original = sqlite3.connect

    def connect(path, *args, **kwargs):
        assert "mode=ro" in str(path)
        conn = original(path, *args, **kwargs)
        conn.execute("PRAGMA query_only=ON")
        return conn

    monkeypatch.setattr(sqlite3, "connect", connect)
    audit = getattr(investigation, "compose_security_lifecycle_audit", None)
    assert callable(audit), "raw accounting needs its own explicit read-only composition"
    cases = audit(str(market), str(profile))["cases"]
    assert {case["case_id"] for case in cases} == {matched, missing, case_id_for("sec_edgar", "unsaved", "UNSAVED")}
    assert investigation.compose_security_lifecycle(str(market), str(profile))["cases"] == []
    assert {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in (market, profile)} == before


def test_equal_population_counts_do_not_prove_equal_case_keys(tmp_path):
    market, profile = stores(tmp_path)
    matched = persist(profile, sec(market, "SAME", "same"))
    sec(market, "NEW", "new")
    missing = persist(profile, {"source": "sec_edgar", "source_ref": "old", "ticker": "OLD"})
    result = manifest(market, profile)
    assert result["counts"]["market_observations"] == result["counts"]["profile_cases"] == 2
    assert result["sec_reconciliation"] == {
        "matched": [matched], "observation_only": [case_id_for("sec_edgar", "new", "NEW")], "case_only": [missing],
    }
    assert review_for(result, missing)["bucket"] == "current"


def test_equal_sec_sets_need_no_orphan_remediation(tmp_path):
    market, profile = stores(tmp_path)
    cases = [persist(profile, sec(market, ticker, ticker)) for ticker in ("FIRST", "SECOND")]
    result = manifest(market, profile)
    assert result["sec_reconciliation"] == {"matched": sorted(cases), "observation_only": [], "case_only": []}
    assert result["counts"]["composed_cases"] == 2
    assert result["automatic_actions"] == []
    assert len(result["input_mappings"]) == 4


def test_first_provider_assessment_persists_same_review_not_a_second_security(tmp_path):
    market, profile = stores(tmp_path)
    checks = ProviderCheckStore(profile)
    checks.record(ticker="OLD", at=NOW, evidence=terminal("OLD"), diagnostics={})
    before = manifest(market, profile)
    observation = checks.latest()["OLD"]["observation"]
    case_id = case_id_for("listing_authority", "listing:OLD", "OLD")
    with sqlite3.connect(profile) as conn:
        store = SecurityLifecycleInvestigationStore(conn)
        assessment = store.create_assessment(
            case_id=case_id, case_identity=observation, relevance="direct_tracked_security", confidence="high",
            author="human", conclusion="A draft, not consent.", impact_summary="Review removal.", outcomes=("listing_ended",),
            citations=({"reference_kind": "observation", "cited_content_sha256": observation_fingerprint(observation)},),
            observation_fingerprint_sha256=observation_fingerprint(observation), at=NOW,
        )
    after = manifest(market, profile)
    assert len(before["reviews"]) == len(after["reviews"]) == 1
    assert review_for(before, case_id)["review_id"] == review_for(after, case_id)["review_id"]
    assert after["provider_reconciliation"] == {"virtual": [], "persisted": [case_id], "case_only": []}
    assert after["counts"]["profile_cases"] == 1
    assert after["retention"]["assessment_ids"] == [assessment]
    assert after["automatic_actions"] == []


def test_old_accepted_assessment_never_screens_out_a_source_missing_question(tmp_path):
    market, profile = stores(tmp_path)
    observation = sec(market, "OLD", "old")
    case_id = persist(profile, observation)
    fingerprint = observation_fingerprint(observation)
    with sqlite3.connect(profile) as conn:
        store = SecurityLifecycleInvestigationStore(conn)
        assessment = store.create_assessment(
            case_id=case_id, relevance="direct_tracked_security", confidence="high", author="human",
            conclusion="Previously accepted.", impact_summary="No new authority.", outcomes=("no_tracked_security_change",),
            citations=({"reference_kind": "observation", "cited_content_sha256": fingerprint},),
            observation_fingerprint_sha256=fingerprint, at=NOW,
        )
        store.accept_assessment(assessment, observation_fingerprint_sha256=fingerprint, acceptance_authority="human", at=NOW)
    with sqlite3.connect(market) as conn:
        conn.execute("DELETE FROM security_lifecycle_observation_kinds")
        conn.execute("DELETE FROM security_lifecycle_observations")
    result = manifest(market, profile)
    review = review_for(result, case_id)
    assert (review["bucket"], review["finding"], review["reason"]) == ("current", "unresolved", "source_missing")
    assert result["retention"]["assessment_ids"] == [assessment]
    assert result["automatic_actions"] == []


def test_population_reads_neither_create_stores_nor_read_credentials(tmp_path, monkeypatch):
    from src.security_lifecycle_population import LifecyclePopulationUnavailable
    missing = tmp_path / "absent"
    with pytest.raises(LifecyclePopulationUnavailable, match="population_store_unavailable"):
        manifest(missing / "market.db", missing / "profile.db")
    assert not missing.exists()
    market, profile = stores(tmp_path)
    persist(profile, sec(market, "OLD", "old"))
    with sqlite3.connect(profile) as conn:
        conn.execute("CREATE TABLE private_credentials(secret TEXT)")
        conn.execute("INSERT INTO private_credentials VALUES ('never-read-this')")
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in (market, profile)}
    original = sqlite3.connect
    def connect(path, *args, **kwargs):
        assert "mode=ro" in str(path)
        conn = original(path, *args, **kwargs)
        def authorizer(action, first, second, database, trigger):
            if action == sqlite3.SQLITE_READ and first == "private_credentials":
                pytest.fail("unrelated_credential_read")
            assert action not in {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE}
            return sqlite3.SQLITE_OK
        conn.set_authorizer(authorizer)
        return conn
    monkeypatch.setattr(sqlite3, "connect", connect)
    result = manifest(market, profile)
    assert {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in before} == before
    assert "never-read-this" not in json.dumps(result)
    assert str(tmp_path) not in json.dumps(result)


@pytest.mark.parametrize("target", ("market", "profile"))
def test_population_capture_rejects_cross_store_changes_without_blocking_writers(tmp_path, monkeypatch, target):
    from src import security_lifecycle_population as population
    market, profile = stores(tmp_path)
    persist(profile, sec(market, "OLD", "old"))
    for path in (market, profile):
        with sqlite3.connect(path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
    original = population._capture
    writes = []
    def changed(*args, **kwargs):
        value = original(*args, **kwargs)
        if target == "profile":
            persist(profile, {"source": "sec_edgar", "source_ref": "new", "ticker": "NEW"})
        else:
            sec(market, "NEW", "new")
        writes.append("committed")
        return value
    monkeypatch.setattr(population, "_capture", changed)
    with pytest.raises(population.LifecyclePopulationUnavailable, match="population_snapshot_changed"):
        manifest(market, profile)
    assert writes == ["committed"]
    monkeypatch.setattr(population, "_capture", original)
    result = manifest(market, profile)
    assert result["counts"]["profile_cases"] == (2 if target == "profile" else 1)
    difference = "case_only" if target == "profile" else "observation_only"
    assert case_id_for("sec_edgar", "new", "NEW") in result["sec_reconciliation"][difference]


def bind_listing(profile, observation, evidence, *, fingerprint=None, extra_facts=()):
    from src.security_lifecycle_fact_kernel import AutomationEvidence, AutomationFact, SecurityLifecycleFactKernel
    case_id = persist(profile, observation)
    values = (("source_ticker", observation["ticker"]), ("issuer_cik", observation["cik"]), ("security_class", "common_stock"), *extra_facts)
    text = " ".join(value for _, value in values)
    proof = AutomationEvidence(
        evidence_id="regulator", source_family="regulator", adapter="sec_edgar", kind="regulator_excerpt",
        excerpt=text, content_sha256=hashlib.sha256(text.encode()).hexdigest(),
        source_url="https://www.sec.gov/Archives/fixture/filing.htm", source_document_sha256="c" * 64,
        source_locator={"accession": observation["source_ref"]}, evidence_dedupe_key="regulator", retrieved_at=NOW,
    )
    facts = []
    for kind, value in values:
        start = text.index(value)
        facts.append(AutomationFact(
            evidence_id="regulator", fact_type=kind, normalized_value=value, source_span_start=start,
            source_span_end=start + len(value), cited_text_sha256=hashlib.sha256(value.encode()).hexdigest(),
            extractor_rule_id="population.fixture", extractor_rule_version="1",
        ))
    with sqlite3.connect(profile) as conn:
        kernel = SecurityLifecycleFactKernel(SecurityLifecycleInvestigationStore(conn))
        claim = kernel.reserve_run(
            case_id=case_id, observation_fingerprint_sha256=fingerprint or observation_fingerprint(observation),
            policy_version="population-test", mode="historical", execution_revision="1", execution_owner_id="fixture",
            query_context={}, diagnostics={}, at=NOW,
        )
        kernel.complete_run(run_id=claim.run_id, evidence=(*evidence, proof), facts=facts, blockers=(),
            decision_tier="review_suggested", action_readiness="not_applicable", retry_at=None, diagnostics={}, at=NOW)
    return case_id


def test_proven_current_security_consolidates_without_counting_a_new_security(tmp_path):
    market, profile = stores(tmp_path)
    one = sec(market, "SAME", "one")
    two = sec(market, "SAME", "two")
    evidence = active("SAME")
    first = bind_listing(profile, one, (evidence,))
    second = bind_listing(profile, two, (evidence,))
    ProviderCheckStore(profile).record(ticker="SAME", at=NOW, evidence=(evidence,), diagnostics={})
    result = manifest(market, profile)
    assert result["counts"]["composed_cases"] == 2
    assert len(result["reviews"]) == 1
    review = result["reviews"][0]
    assert set(review["case_ids"]) == {first, second, case_id_for("listing_authority", "listing:SAME", "SAME")}
    assert (review["bucket"], review["finding"]) == ("history", "active")
    assert len({row["review_id"] for row in result["input_mappings"]}) == 1
    assert result["automatic_actions"] == []


@pytest.mark.parametrize("difference", ("share_class", "market", "venue", "reused_symbol", "wrong_observation", "old_filing", "conflicting_identity"))
def test_consolidation_rejects_issuer_only_or_unproven_listing_identity(tmp_path, difference):
    market, profile = stores(tmp_path)
    old = sec(market, "SAME", "old", filing_date="2010-05-06" if difference == "old_filing" else "2026-09-04")
    changed = {
        "share_class": {"security_type": "PFD"}, "venue": {"venue": "XNAS"},
        "reused_symbol": {"figi": "BBG000B9XRY4"},
    }.get(difference, {})
    bound = active("SAME", **changed)
    if difference == "market":
        bound = _evidence(replace(record("massive_reference", "active", ticker="SAME", figi=FIGI, market="otc"),
            primary_exchange="XNYS", security_type="CS", issuer_cik="0000000001"))
    evidence = (bound, active("SAME", figi="BBG000B9XRY4")) if difference == "conflicting_identity" else (bound,)
    case_id = bind_listing(profile, old, evidence, fingerprint="a" * 64 if difference == "wrong_observation" else None)
    ProviderCheckStore(profile).record(ticker="SAME", at=NOW, evidence=(active("SAME"),), diagnostics={})
    result = manifest(market, profile)
    review = review_for(result, case_id)
    assert review["case_ids"] == [case_id]
    assert (review["bucket"], review["finding"]) == ("current", "unresolved")
    assert result["coverage_only"] == ["SAME"]


def test_always_active_snapshot_must_not_claim_current_health_after_expiry(tmp_path):
    market, profile = stores(tmp_path)
    ProviderCheckStore(profile).record(ticker="LIVE", at=NOW, evidence=(active("LIVE"),), diagnostics={})
    before = manifest(market, profile)
    assert before["coverage_only"] == ["LIVE"] and before["reviews"] == []
    expired = manifest(market, profile, at="2026-09-10T01:00:00Z")
    assert expired["coverage_only"] == []
    assert expired["counts"]["composed_cases"] == 0
    assert expired["counts"]["current_reviews"] == 1
    assert expired["reviews"][0]["listing_reasons"] == ["listing_directory_stale"]
    assert expired["input_mappings"][0]["destination"] == "current"


def test_provider_latest_uses_store_order_for_equal_timestamps(tmp_path):
    market, profile = stores(tmp_path)
    checks = ProviderCheckStore(profile)
    checks.record(ticker="LIVE", at=NOW, evidence=(active("LIVE"),), diagnostics={})
    checks.record(ticker="LIVE", at=NOW, evidence=(), diagnostics={})
    result = manifest(market, profile)
    assert result["counts"]["provider_checks"] == 2
    assert result["reviews"][0]["finding"] == "unresolved"
    assert sorted(row["destination"] for row in result["input_mappings"]) == ["current", "history"]


@pytest.mark.parametrize("part", ("at", "market_observations", "profile_tables", "composed_cases", "identity_tables"))
def test_manifest_builder_rejects_changed_snapshot_and_replays_without_stores(tmp_path, monkeypatch, part):
    from src.security_lifecycle_population import read_population_snapshot, build_population_manifest, LifecyclePopulationUnavailable
    market, profile = stores(tmp_path)
    persist(profile, sec(market, "ONE", "one"))
    snapshot = read_population_snapshot(market, profile, at=NOW)
    expected = build_population_manifest(snapshot)
    def denied(*args, **kwargs):
        pytest.fail("pure_manifest_must_not_open_stores")
    monkeypatch.setattr(sqlite3, "connect", denied)
    assert build_population_manifest(snapshot) == expected
    if part == "at":
        snapshot["at"] = "2026-09-06T01:00:00Z"
    else:
        snapshot["material"][part] = {"tampered": True}
    with pytest.raises(LifecyclePopulationUnavailable, match="population_snapshot_digest"):
        build_population_manifest(snapshot)


def test_read_service_population_uses_only_explicit_stores(tmp_path):
    from src.tools.security_lifecycle_tools import SecurityLifecycleReadService
    market, profile = stores(tmp_path)
    persist(profile, sec(market, "ONE", "one"))
    def denied():
        pytest.fail("population_inventory_must_not_resolve_global_sources")
    service = SecurityLifecycleReadService(market_db_path=str(market), profile_db_path=str(profile), source_loader=denied)
    assert service.population_manifest(at=NOW) == manifest(market, profile)


@pytest.mark.parametrize("timeline,expected_bucket,expected_reason", (
    (False, "current", "continuation_followup_pending"), (True, "history", "removal_applied"),
))
@pytest.mark.parametrize("at", (NOW, "2026-09-10T01:00:00Z"))
def test_actual_removal_receipt_does_not_erase_unresolved_continuation(tmp_path, timeline, expected_bucket, expected_reason, at):
    from tests.test_security_lifecycle_terminal_workflow import setup_workflow
    from src.ticker_identity_transition import TransitionOptions
    c = setup_workflow(tmp_path, event_available=timeline)
    options = TransitionOptions(execute_on=c["ended"])
    preview = c["service"].preview_case(c["case_id"], options=options)
    approved = c["service"].approve_case(c["case_id"], options=options, preview_sha256=preview["preview_sha256"], before_write=lambda: None)
    result = c["service"].execute_transition(approved["transition_id"], preview_sha256=preview["preview_sha256"], before_write=lambda: None)
    assert result["status"] == "applied"
    before = c["sources"]()
    value = manifest(c["market"], c["profile"], at=at)
    review = review_for(value, c["case_id"])
    assert (review["bucket"], review["reason"]) == (expected_bucket, expected_reason)
    assert review["finding"] == "old_listing_inactive"
    assert review["action_state"] == "applied"
    assert review["listing_basis"] == ("observation" if at == NOW else "applied_receipt")
    assert review["transition_ids"] == [approved["transition_id"]]
    receipt = value["retention"]["transitions"][0]
    assert receipt["transition_id"] == approved["transition_id"]
    assert receipt["assessment_id"] in value["retention"]["assessment_ids"]
    assert receipt["approved_preview_sha256"] == preview["preview_sha256"]
    assert receipt["attempt_ids"] and receipt["activity_ids"]
    assert c["sources"]() == before == {"LIVE": ("manual_lists",)}
    assert value["automatic_actions"] == [] and value["retention"]["deletion_candidates"] == []


def test_bound_active_listing_does_not_erase_future_regulator_event(tmp_path):
    market, profile = stores(tmp_path)
    observation = sec(market, "SAME", "pending")
    with sqlite3.connect(market) as conn:
        conn.execute("UPDATE security_lifecycle_observation_kinds SET effective_date='2026-09-20'")
        observation = SecurityLifecycleStore(conn).get_observation("sec_edgar", "pending", "SAME")
    case_id = bind_listing(profile, observation, (active("SAME"),))
    ProviderCheckStore(profile).record(ticker="SAME", at=NOW, evidence=(active("SAME"),), diagnostics={})
    result = manifest(market, profile)
    assert len(result["reviews"]) == 1
    review = review_for(result, case_id)
    assert review["listing_state"] == "active"
    assert (review["bucket"], review["finding"], review["reason"]) == ("current", "unresolved", "regulator_event_pending")
    assert result["automatic_actions"] == []


@pytest.mark.parametrize("extra", (("successor_ticker", "NEW"), ("effective_date", "2026-09-20"), ("destination_venue", "OTC")))
def test_bound_active_listing_keeps_unresolved_identity_facts(tmp_path, extra):
    market, profile = stores(tmp_path)
    observation = sec(market, "SAME", "one")
    case_id = bind_listing(profile, observation, (active("SAME"),), extra_facts=(extra,))
    ProviderCheckStore(profile).record(ticker="SAME", at=NOW, evidence=(active("SAME"),), diagnostics={})
    review = review_for(manifest(market, profile), case_id)
    assert (review["bucket"], review["finding"]) == ("current", "unresolved")
    assert review["reason"] in {"regulator_identity_question", "regulator_event_pending"}


@pytest.mark.parametrize("change", ("missing_regulator_fact", "different_cik", "failed_latest_run"))
def test_listing_snapshot_alone_does_not_bind_a_sec_security(tmp_path, change):
    market, profile = stores(tmp_path)
    observation = sec(market, "SAME", "one", cik="0000000002" if change == "different_cik" else "0000000001")
    case_id = bind_listing(profile, observation, (active("SAME"),))
    with sqlite3.connect(profile) as conn:
        if change == "missing_regulator_fact":
            conn.execute("DELETE FROM security_lifecycle_automation_facts WHERE fact_type='security_class'")
        elif change == "failed_latest_run":
            from src.security_lifecycle_fact_kernel import SecurityLifecycleFactKernel
            kernel = SecurityLifecycleFactKernel(SecurityLifecycleInvestigationStore(conn))
            claim = kernel.reserve_run(case_id=case_id, observation_fingerprint_sha256=observation_fingerprint(observation),
                policy_version="population-test-2", mode="historical", execution_revision="2", execution_owner_id="fixture",
                query_context={}, diagnostics={}, at="2026-09-05T01:00:01Z")
            kernel.fail_run(run_id=claim.run_id, failure_code="source_payload_invalid", diagnostics={}, at="2026-09-05T01:00:02Z")
    ProviderCheckStore(profile).record(ticker="SAME", at=NOW, evidence=(active("SAME"),), diagnostics={})
    result = manifest(market, profile, at="2026-09-05T01:00:03Z")
    assert review_for(result, case_id)["case_ids"] == [case_id]
    assert review_for(result, case_id)["finding"] == "unresolved"
    assert result["coverage_only"] == ["SAME"]


@pytest.mark.parametrize("target", ("market", "profile"))
def test_population_capture_rejects_replaced_database_file(tmp_path, monkeypatch, target):
    from src import security_lifecycle_population as population
    market, profile = stores(tmp_path)
    original = population._capture
    def replaced(*args, **kwargs):
        value = original(*args, **kwargs)
        path = market if target == "market" else profile
        clone = path.with_suffix(".new")
        with sqlite3.connect(path) as source, sqlite3.connect(clone) as destination:
            source.backup(destination)
        clone.replace(path)
        return value
    monkeypatch.setattr(population, "_capture", replaced)
    with pytest.raises(population.LifecyclePopulationUnavailable, match="population_snapshot_changed"):
        manifest(market, profile)


@pytest.mark.parametrize("target", ("market", "profile"))
def test_population_requires_installed_exact_schemas(tmp_path, target):
    from src.security_lifecycle_population import LifecyclePopulationUnavailable
    market, profile = stores(tmp_path)
    path = market if target == "market" else profile
    with sqlite3.connect(path) as conn:
        table = "security_lifecycle_observations" if target == "market" else "security_lifecycle_cases"
        conn.execute(f"ALTER TABLE {table} ADD COLUMN undeclared TEXT")
    with pytest.raises(LifecyclePopulationUnavailable, match="population_schema_invalid"):
        manifest(market, profile)


def test_unrelated_profile_write_invalidates_only_the_read_not_the_writer(tmp_path, monkeypatch):
    from src import security_lifecycle_population as population
    market, profile = stores(tmp_path)
    with sqlite3.connect(profile) as conn:
        conn.execute("CREATE TABLE unrelated_sa_sync(value INTEGER)")
    original = population._capture
    def changed(*args, **kwargs):
        value = original(*args, **kwargs)
        with sqlite3.connect(profile) as conn:
            conn.execute("INSERT INTO unrelated_sa_sync VALUES (1)")
        return value
    monkeypatch.setattr(population, "_capture", changed)
    with pytest.raises(population.LifecyclePopulationUnavailable, match="population_snapshot_changed"):
        manifest(market, profile)
    with sqlite3.connect(profile) as conn:
        assert conn.execute("SELECT value FROM unrelated_sa_sync").fetchall() == [(1,)]


def test_retention_inventories_actual_evidence_and_translations_without_prose(tmp_path):
    market, profile = stores(tmp_path)
    observation = sec(market, "SAME", "one")
    case_id = bind_listing(profile, observation, (active("SAME"),))
    with sqlite3.connect(profile) as conn:
        store = SecurityLifecycleInvestigationStore(conn)
        evidence = next(row for row in store.list_evidence(case_id) if row["source_family"] == "regulator")
        assessment = store.create_assessment(case_id=case_id, relevance="direct_tracked_security", confidence="high", author="human",
            conclusion="A retained assessment", impact_summary="No consent", outcomes=("undetermined",),
            citations=({"reference_kind": "evidence", "evidence_id": evidence["evidence_id"], "cited_content_sha256": evidence["content_sha256"]},),
            observation_fingerprint_sha256=observation_fingerprint(observation), at=NOW)
        conn.execute("INSERT INTO security_lifecycle_evidence_translations VALUES (?,?,?,?,?,?,?,?)",
            (evidence["evidence_id"], evidence["content_sha256"], "zh-Hant", "Private fixture translation", "openai", "fixture", "fixture", NOW))
    retention = manifest(market, profile)["retention"]
    assert retention["assessment_ids"] == [assessment]
    assert retention["referenced_evidence_ids"] == [evidence["evidence_id"]]
    assert len(retention["fact_dependencies"]) == 3
    assert retention["translation_dependencies"] == [{"evidence_id": evidence["evidence_id"], "content_sha256": evidence["content_sha256"], "locale": "zh-Hant"}]
    assert "Private fixture translation" not in json.dumps(retention)
    assert evidence["excerpt"] not in json.dumps(retention)


def test_receipt_digest_corruption_never_becomes_a_historical_success(tmp_path):
    from tests.test_security_lifecycle_terminal_workflow import setup_workflow
    from src.security_lifecycle_population import LifecyclePopulationUnavailable
    from src.ticker_identity_transition import TransitionOptions
    c = setup_workflow(tmp_path)
    options = TransitionOptions(execute_on=c["ended"])
    preview = c["service"].preview_case(c["case_id"], options=options)
    c["service"].approve_case(c["case_id"], options=options, preview_sha256=preview["preview_sha256"], before_write=lambda: None)
    with sqlite3.connect(c["profile"]) as conn:
        conn.execute("UPDATE ticker_identity_transitions SET approved_preview_sha256=?", ("a" * 64,))
    with pytest.raises(LifecyclePopulationUnavailable, match="population_receipt_invalid"):
        manifest(c["market"], c["profile"])


def test_dangling_evidence_dependency_blocks_population_cleanup(tmp_path):
    from src.security_lifecycle_population import LifecyclePopulationUnavailable, read_population_snapshot, build_population_manifest
    market, profile = stores(tmp_path)
    observation = sec(market, "SAME", "one")
    case_id = bind_listing(profile, observation, (active("SAME"),))
    snapshot = read_population_snapshot(market, profile, at=NOW)
    with sqlite3.connect(profile) as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("UPDATE security_lifecycle_automation_facts SET evidence_id='missing' WHERE case_id=?", (case_id,))
    with pytest.raises(LifecyclePopulationUnavailable, match="population_schema_invalid"):
        manifest(market, profile)
    snapshot["material"]["profile_tables"]["security_lifecycle_automation_facts"][0]["evidence_id"] = "missing"
    unsigned = {key: snapshot[key] for key in ("version", "at", "material")}
    snapshot["sha256"] = hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()).hexdigest()
    with pytest.raises(LifecyclePopulationUnavailable, match="population_dependency_invalid"):
        build_population_manifest(snapshot)


def test_legacy_screened_cases_are_counted_and_reclassified_not_dropped(tmp_path):
    from src.sa_tracking_memberships import SaTrackingMembershipStore
    market, profile = stores(tmp_path)
    case_id = persist(profile, sec(market, "ONE", "one"))
    with sqlite3.connect(profile) as conn:
        SaTrackingMembershipStore.install(conn)
    value = manifest(market, profile)
    assert value["counts"]["composed_cases"] == 1
    assert value["counts"]["legacy_visible_cases"] == 0
    assert value["counts"]["legacy_screened_cases"] == 1
    assert review_for(value, case_id)["bucket"] == "current"
    assert len(value["input_mappings"]) == 2


@pytest.mark.parametrize("state", ("approved", "needs_review"))
def test_approval_is_not_reported_as_an_applied_removal(tmp_path, state):
    from tests.test_security_lifecycle_terminal_workflow import setup_workflow
    from src.ticker_identity_transition import TransitionOptions
    c = setup_workflow(tmp_path)
    options = TransitionOptions(execute_on=c["ended"])
    preview = c["service"].preview_case(c["case_id"], options=options)
    c["service"].approve_case(c["case_id"], options=options, preview_sha256=preview["preview_sha256"], before_write=lambda: None)
    if state == "needs_review":
        c["now"][0] = "2026-09-10T01:00:00Z"
        with sqlite3.connect(c["profile"]) as conn:
            transition_id = conn.execute("SELECT transition_id FROM ticker_identity_transitions").fetchone()[0]
        assert c["service"].execute_transition(transition_id, preview_sha256=preview["preview_sha256"], before_write=lambda: None)["status"] == "blocked"
    review = review_for(manifest(c["market"], c["profile"], at=c["now"][0]), c["case_id"])
    assert review["bucket"] == "current" and review["action_state"] == state
    assert review["reason"] == ("action_pending" if state == "approved" else "action_needs_review")
    assert review["collection_state"] == "not_observed"
    assert "OLD" in c["sources"]()


def test_reused_provider_ticker_retains_distinct_historical_identity(tmp_path):
    market, profile = stores(tmp_path)
    checks = ProviderCheckStore(profile)
    checks.record(ticker="SAME", at=NOW, evidence=(active("SAME"),), diagnostics={})
    later = "2026-09-05T01:01:00Z"
    checks.record(ticker="SAME", at=later, evidence=(active("SAME", figi="BBG000B9XRY4", at=later),), diagnostics={})
    value = manifest(market, profile, at=later)
    assert value["counts"]["provider_checks"] == 2
    assert value["coverage_only"] == []
    assert len(value["reviews"]) == 2
    assert len({row["review_id"] for row in value["input_mappings"]}) == 2
    assert {row["reason"] for row in value["reviews"]} == {"superseded_listing_identity", "listing_identity_changed"}
    assert sorted(row["bucket"] for row in value["reviews"]) == ["current", "history"]
    persist(profile, checks.latest()["SAME"]["observation"])
    persisted = manifest(market, profile, at=later)
    assert sorted(row["review_id"] for row in value["reviews"]) == sorted(row["review_id"] for row in persisted["reviews"])


def test_old_retirement_receipt_does_not_describe_reused_ticker_as_removed(tmp_path, monkeypatch):
    from tests import test_security_lifecycle_terminal_workflow as workflow
    from src.ticker_identity_transition import TransitionOptions
    material = tuple(replace(row, primary_exchange="XNYS", security_type="CS", issuer_cik="0000000001") for row in terminal_records())
    monkeypatch.setattr(workflow, "terminal_records", lambda: material)
    c = workflow.setup_workflow(tmp_path)
    options = TransitionOptions(execute_on=c["ended"])
    preview = c["service"].preview_case(c["case_id"], options=options)
    approved = c["service"].approve_case(c["case_id"], options=options, preview_sha256=preview["preview_sha256"], before_write=lambda: None)
    assert c["service"].execute_transition(approved["transition_id"], preview_sha256=preview["preview_sha256"], before_write=lambda: None)["status"] == "applied"
    later = "2026-09-05T01:01:00Z"
    c["checks"].record(ticker="OLD", at=later, evidence=(active("OLD", figi="BBG000B9XRY4", at=later),), diagnostics={})
    value = manifest(c["market"], c["profile"], at=later)
    assert len(value["reviews"]) == 2
    current = next(row for row in value["reviews"] if row["bucket"] == "current")
    historical = next(row for row in value["reviews"] if row["bucket"] == "history")
    assert current["reason"] == "listing_identity_changed" and current["action_state"] == "none"
    assert current["transition_ids"] == []
    assert historical["action_state"] == "applied" and historical["transition_ids"] == [approved["transition_id"]]
    assert value["retention"]["transitions"][0]["review_id"] == historical["review_id"]
    assert "OLD" not in c["sources"]()


@pytest.mark.parametrize("field,invalid", (("identity_tables", []), ("profile_tables", []), ("schemas", None)))
def test_sealed_but_malformed_population_shape_is_a_typed_failure(tmp_path, field, invalid):
    from src.security_lifecycle_population import LifecyclePopulationUnavailable, read_population_snapshot, build_population_manifest
    market, profile = stores(tmp_path)
    snapshot = read_population_snapshot(market, profile, at=NOW)
    snapshot["material"][field] = invalid
    unsigned = {key: snapshot[key] for key in ("version", "at", "material")}
    snapshot["sha256"] = hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()).hexdigest()
    with pytest.raises(LifecyclePopulationUnavailable, match="population_material_invalid"):
        build_population_manifest(snapshot)


def test_provider_source_missing_is_not_recovered_by_a_different_source_ref(tmp_path):
    market, profile = stores(tmp_path)
    missing = persist(profile, {"source": "listing_authority", "source_ref": "unavailable-reference", "ticker": "SAME"})
    ProviderCheckStore(profile).record(ticker="SAME", at=NOW, evidence=(active("SAME"),), diagnostics={})
    value = manifest(market, profile)
    review = review_for(value, missing)
    assert (review["bucket"], review["finding"], review["reason"]) == ("current", "unresolved", "source_missing")
    assert review["case_ids"] == [missing]
    assert value["provider_reconciliation"]["case_only"] == [missing]
    assert value["coverage_only"] == ["SAME"]


def test_old_applied_listing_does_not_override_a_later_contradiction_after_expiry(tmp_path, monkeypatch):
    from tests import test_security_lifecycle_terminal_workflow as workflow
    from src.ticker_identity_transition import TransitionOptions
    material = tuple(replace(row, primary_exchange="XNYS", security_type="CS", issuer_cik="0000000001") for row in terminal_records())
    monkeypatch.setattr(workflow, "terminal_records", lambda: material)
    c = workflow.setup_workflow(tmp_path)
    options = TransitionOptions(execute_on=c["ended"])
    preview = c["service"].preview_case(c["case_id"], options=options)
    approved = c["service"].approve_case(c["case_id"], options=options, preview_sha256=preview["preview_sha256"], before_write=lambda: None)
    assert c["service"].execute_transition(approved["transition_id"], preview_sha256=preview["preview_sha256"], before_write=lambda: None)["status"] == "applied"
    later = "2026-09-05T01:01:00Z"
    c["checks"].record(ticker="OLD", at=later, evidence=(active("OLD", at=later),), diagnostics={})
    value = manifest(c["market"], c["profile"], at="2026-09-10T01:00:00Z")
    assert len(value["reviews"]) == 1
    review = value["reviews"][0]
    assert (review["bucket"], review["finding"], review["reason"]) == ("current", "unresolved", "listing_recheck_required")
    assert review["listing_basis"] == "observation"
    assert review["action_state"] == "applied" and review["collection_state"] == "not_observed"


@pytest.mark.parametrize("target", ("market", "profile"))
@pytest.mark.parametrize("suffix", (
    "#selected", "%23selected", " with spaces",
    pytest.param("?mode=rw&ignored=", marks=pytest.mark.skipif(sys.platform == "win32", reason="Query characters are not Windows filenames")),
))
def test_population_capture_uses_literal_store_paths(tmp_path, target, suffix):
    market, profile = stores(tmp_path)
    base = market if target == "market" else profile
    selected = base.with_name(base.name + suffix)
    decoy = base.with_name(base.name + "#selected") if suffix == "%23selected" else base
    create = create_market_schema if target == "market" else create_profile_schema
    for path, ticker in ((selected, "RIGHT"), (decoy, "WRONG")):
        if not path.exists():
            with sqlite3.connect(path) as conn:
                create(conn)
        if target == "market":
            sec(path, ticker, "fixture")
        else:
            persist(path, {"source": "sec_edgar", "source_ref": "fixture", "ticker": ticker})
    result = manifest(selected if target == "market" else market, selected if target == "profile" else profile)
    assert [row["tickers"] for row in result["reviews"]] == [["RIGHT"]]
    assert result["counts"]["market_observations" if target == "market" else "profile_cases"] == 1


@pytest.mark.skipif(sys.platform == "win32", reason="Query characters are not Windows filenames")
@pytest.mark.parametrize("target", ("market", "profile"))
def test_population_capture_never_interprets_uri_options_or_creates_other_store(tmp_path, target):
    market, profile = stores(tmp_path)
    other = tmp_path / "literal.db"
    selected = other.with_name(other.name + "?mode=rwc&ignored=")
    with sqlite3.connect(selected) as conn:
        (create_market_schema if target == "market" else create_profile_schema)(conn)
    try:
        result = manifest(selected if target == "market" else market, selected if target == "profile" else profile)
        assert result["reviews"] == []
    finally:
        assert not other.exists(), "An input filename must not become SQLite URI options"
