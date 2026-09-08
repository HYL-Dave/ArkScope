import sqlite3

import pytest

from tests.test_security_lifecycle_terminal_workflow import setup_workflow
from tests.test_lifecycle_web_preflight import setup


def test_investigation_can_start_without_legacy_cases_or_observations(tmp_path, monkeypatch):
    from src.lifecycle_investigation.schema import install_journal
    from src.lifecycle_investigation.target import TargetPreflight
    from src.lifecycle_investigation.store import InvestigationStore
    c = setup_workflow(tmp_path, assess=False, event_available=False)
    old, credentials, route = setup(c)
    with sqlite3.connect(c["profile"]) as conn:
        install_journal(conn, at=c["now"][0])
        conn.execute("DELETE FROM security_lifecycle_cases")
    monkeypatch.setattr(c["service"]._read_service, "get_case", lambda *a: pytest.fail("legacy lookup"))
    preflight = TargetPreflight(c["service"], credential_store=old.credential_store, route_loader=lambda: route,
        market_path=c["market"], sa_path=c["sa"])
    public = preflight.prepare("OLD")
    assert public["available"], public
    bound = preflight.validate_start("OLD", preflight_sha256=public["preflight_sha256"])
    run = InvestigationStore(c["profile"], clock=lambda: c["now"][0]).start(**bound, request_key="click", owner="worker")
    assert run["created"]
    with sqlite3.connect(c["profile"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM security_lifecycle_cases").fetchone()[0] == 0


def test_manual_only_target_does_not_require_sa_pick_history(tmp_path):
    from src.lifecycle_investigation.target import target_snapshot
    c = setup_workflow(tmp_path, assess=False, event_available=False)
    target = target_snapshot(c["service"], "LIVE", market_path=c["market"], sa_path=None)
    assert target.ticker == "LIVE"
    assert target.issuer_name is None
    assert target.identity_status == "needs_lookup"


def test_only_current_target_can_start_and_public_snapshot_excludes_private_fields(tmp_path):
    from src.lifecycle_investigation.target import target_snapshot
    c = setup_workflow(tmp_path, assess=False, event_available=False)
    with pytest.raises(ValueError, match="target_not_tracked"):
        target_snapshot(c["service"], "UNKNOWN", market_path=c["market"], sa_path=c["sa"])
    target = target_snapshot(c["service"], "OLD", market_path=c["market"], sa_path=c["sa"])
    assert not {"holdings", "notes", "source_ref", "case_id", "credential_id"}.intersection(target.model_dump())


def test_provider_context_preserves_authority_time_and_never_exports_locators(tmp_path):
    from src.lifecycle_investigation.target import provider_observations
    c = setup_workflow(tmp_path, assess=False, event_available=False)
    with sqlite3.connect(c["profile"]) as conn:
        public, digest = provider_observations(conn, "OLD")
    assert public["observed_at"] == c["now"][0]
    assert {row["provider"] for row in public["listings"]} == {"massive", "eodhd", "nasdaq"}
    assert len(digest) == 64
    assert all(row["observed_at"] and "source_locator" not in row and "credential_id" not in row for row in public["listings"])


def test_different_historical_sa_company_labels_require_lookup_not_an_identity_veto(tmp_path):
    from src.lifecycle_investigation.target import target_snapshot
    c = setup_workflow(tmp_path, assess=False, event_available=False)
    with sqlite3.connect(c["sa"]) as conn:
        for day, company in (("2023-01-01", "Issuer Old Inc"), ("2024-01-01", "Issuer Old")):
            conn.execute("INSERT INTO sa_pick_lineages(symbol_key,picked_date,created_at) VALUES('OLD',?,'2026-09-08')", (day,))
            lineage = conn.execute("SELECT lineage_id FROM sa_pick_lineages WHERE picked_date=?", (day,)).fetchone()[0]
            conn.execute("INSERT INTO sa_alpha_picks(symbol,company,picked_date,lineage_id,fetched_at) VALUES('OLD',?,?,?,'2026-09-08')", (company, day, lineage))
    target = target_snapshot(c["service"], "OLD", sa_path=c["sa"])
    assert target.issuer_name is None
    assert target.identity_status == "needs_lookup"
    assert target.composite_figi is not None
