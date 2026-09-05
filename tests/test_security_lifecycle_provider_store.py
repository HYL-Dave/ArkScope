from __future__ import annotations

import sqlite3

import pytest

from src.security_lifecycle_schema import create_market_schema, create_profile_schema
from tests.test_security_lifecycle_provider_authority import NOW as AT, events, terminal_records
from src.security_lifecycle_listing_evidence import _evidence


def _paths(tmp_path):
    profile, market = tmp_path / "profile.db", tmp_path / "market.db"
    with sqlite3.connect(profile) as conn:
        create_profile_schema(conn)
    with sqlite3.connect(market) as conn:
        create_market_schema(conn)
    return profile, market


def test_provider_snapshot_creates_a_case_without_any_sec_observation(tmp_path):
    from src.security_lifecycle_provider_store import ProviderCheckStore
    from src.security_lifecycle_investigation import compose_security_lifecycle

    profile, market = _paths(tmp_path)
    store = ProviderCheckStore(profile)
    material = tuple(_evidence(row) for row in terminal_records()) + (events(),)
    receipt = store.record(ticker="OLD", at=AT, evidence=material, diagnostics={"massive_requests": 4})
    cases = compose_security_lifecycle(str(market), str(profile))["cases"]
    assert len(cases) == 1
    assert cases[0]["source"] == "listing_authority"
    assert cases[0]["sec_admission"] is None
    assert cases[0]["observation"]["kinds"] == [{"event_type": "listing_status_review", "effective_date": "2025-01-15"}]
    assert store.record(ticker="OLD", at=AT, evidence=material, diagnostics={"massive_requests": 4}) == receipt
    assert len(store.latest()) == 1
    before = profile.read_bytes()
    compose_security_lifecycle(str(market), str(profile))
    assert profile.read_bytes() == before


def test_corrupt_or_forged_provider_snapshot_cannot_authorize_a_run(tmp_path):
    from src.security_lifecycle_provider_store import ProviderCheckStore
    profile, _ = _paths(tmp_path)
    store = ProviderCheckStore(profile)
    store.record(ticker="OLD", at=AT, evidence=(), diagnostics={})
    with sqlite3.connect(profile) as conn:
        with pytest.raises(sqlite3.IntegrityError, match="provider_checks_append_only"):
            conn.execute("UPDATE security_lifecycle_provider_checks SET state='terminal'")
        with pytest.raises(sqlite3.IntegrityError, match="provider_checks_append_only"):
            conn.execute("DELETE FROM security_lifecycle_provider_checks")
        conn.execute("DROP TRIGGER security_lifecycle_provider_checks_no_update")
        conn.execute("UPDATE security_lifecycle_provider_checks SET state='terminal'")
    with pytest.raises(ValueError, match="provider_snapshot_digest"):
        store.latest()


def test_directory_publication_is_atomic_and_timestamps_are_canonical(tmp_path):
    from src.security_lifecycle_provider_store import ProviderCheckStore
    profile, _ = _paths(tmp_path)
    store = ProviderCheckStore(profile)
    with pytest.raises(ValueError, match="provider_snapshot_ticker"):
        store.record_many([
            {"ticker": "OLD", "at": AT, "evidence": (), "diagnostics": {}},
            {"ticker": "BAD*", "at": AT, "evidence": (), "diagnostics": {}},
        ])
    assert store.latest() == {}
    receipt = store.record(ticker="OLD", at="2026-09-05T09:00:00+08:00", evidence=(), diagnostics={})
    assert store.record(ticker="OLD", at=AT, evidence=(), diagnostics={}) == receipt
    assert store.latest()["OLD"]["at"] == AT


def test_invalid_provider_payload_is_not_silently_ignored_as_if_published(tmp_path):
    from src.security_lifecycle_provider_store import ProviderCheckStore
    profile, _ = _paths(tmp_path)
    store = ProviderCheckStore(profile)
    with pytest.raises(sqlite3.IntegrityError):
        store.record(ticker="OLD", at=AT, evidence=tuple(_evidence(row) for row in terminal_records()) * 100, diagnostics={})
    assert store.latest() == {}


def test_provider_errors_cannot_be_described_as_a_confirmed_terminal(tmp_path):
    from src.security_lifecycle_provider_store import ProviderCheckStore
    profile, _ = _paths(tmp_path)
    store = ProviderCheckStore(profile)
    store.record(ticker="OLD", at=AT, evidence=tuple(_evidence(row) for row in terminal_records()) + (events(),),
                 diagnostics={}, blockers=("massive_rate_limited",))
    result = store.latest()["OLD"]
    assert result["state"] == "unresolved"
    assert "needs confirmation" in result["observation"]["description"]


def test_provider_evidence_loader_uses_recorded_listing_material_not_sec(tmp_path, monkeypatch):
    from src.security_lifecycle_provider_store import ProviderCheckStore
    from src.security_lifecycle_investigation import compose_security_lifecycle
    from src.service import security_lifecycle_automation_scheduler as scheduler
    profile, market = _paths(tmp_path)
    monkeypatch.setattr(scheduler, "_profile_path", lambda: profile)
    evidence = tuple(_evidence(row) for row in terminal_records()) + (events(),)
    ProviderCheckStore(profile).record(ticker="OLD", at=AT, evidence=evidence, diagnostics={})
    case = compose_security_lifecycle(str(market), str(profile))["cases"][0]
    phases = []
    bundle = scheduler._load_evidence(case, at=AT, mode="live", listing_session=None, stage_callback=phases.append)
    assert len(bundle.evidence) == len(evidence)
    assert {fact.fact_type for fact in bundle.facts} == {"source_ticker"}
    assert {fact.normalized_value for fact in bundle.facts} == {"OLD"}
    assert "sec" not in phases
    assert bundle.retry_at is None


def test_real_worker_persists_and_accepts_structured_provider_terminal_evidence(tmp_path, monkeypatch):
    from tests.test_security_lifecycle_automation_worker import _Harness, _case
    from src.security_lifecycle_investigation import case_id_for, observation_fingerprint
    from src.security_lifecycle_provider_store import ProviderCheckStore
    import src.security_lifecycle_automation_worker as worker_module
    failures = []
    original_failure = worker_module._failure_code
    def capture_failure(exc, **kwargs):
        failures.append((type(exc).__name__, str(exc), kwargs))
        return original_failure(exc, **kwargs)
    monkeypatch.setattr(worker_module, "_failure_code", capture_failure)

    case = _case(terminal=True)
    case["source"] = "listing_authority"
    case["source_ref"] = "listing:OLD"
    case["case_id"] = case_id_for(case["source"], case["source_ref"], case["ticker"])
    case["observation"]["source"] = "listing_authority"
    case["observation_fingerprint_sha256"] = observation_fingerprint(case["observation"])
    harness = _Harness(tmp_path, [case])
    try:
        store = ProviderCheckStore(tmp_path / "profile_state.db")
        store.record(ticker="OLD", at=AT, evidence=tuple(_evidence(row) for row in terminal_records()) + (events(),), diagnostics={})
        case["observation"] = store.latest()["OLD"]["observation"]
        case["observation_fingerprint_sha256"] = observation_fingerprint(case["observation"])
        harness.now = AT
        harness.bundles[case["case_id"]] = store.bundle(case, at=AT)
        result = harness.worker().run(limit=1, mode="live")
        assert result["accepted"] == 1, (result, failures)
        assert result["failed"] == 0
        assert len(harness.approval_calls) == 1
        assert harness.approval_calls[0]["request"]["transition_kind"] == "terminal_delisting"
        assert harness.conn.execute("SELECT count(*) FROM security_lifecycle_evidence WHERE adapter='eodhd_symbol_directory'").fetchone()[0] == 1
    finally:
        harness.conn.close()
