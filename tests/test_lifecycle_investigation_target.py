import sqlite3

import pytest

from tests.test_security_lifecycle_terminal_workflow import setup_workflow
from tests.lifecycle_investigation_fixtures import CHANNELS, synthetic_credentials


@pytest.fixture
def preflight(tmp_path):
    from src.lifecycle_investigation.target import TargetPreflight
    from tests.test_lifecycle_investigation_store import running
    c, _, _, _ = running(tmp_path)
    credentials, rows, route = synthetic_credentials()
    service = TargetPreflight(c["service"], credential_store=credentials, route_loader=lambda: route,
        market_path=c["market"], sa_path=c["sa"])
    return c, service, rows, route


def test_investigation_can_start_without_legacy_cases_or_observations(tmp_path, monkeypatch):
    from src.lifecycle_investigation.schema import install_journal
    from src.lifecycle_investigation.target import TargetPreflight
    from src.lifecycle_investigation.store import InvestigationStore
    c = setup_workflow(tmp_path, assess=False, event_available=False)
    credentials, _, route = synthetic_credentials()
    with sqlite3.connect(c["profile"]) as conn:
        install_journal(conn, at=c["now"][0])
        conn.execute("DELETE FROM security_lifecycle_cases")
    monkeypatch.setattr(c["service"]._read_service, "get_case", lambda *a: pytest.fail("legacy lookup"))
    preflight = TargetPreflight(c["service"], credential_store=credentials, route_loader=lambda: route,
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


@pytest.mark.parametrize("provider,auth", CHANNELS)
def test_current_preflight_keeps_four_channel_selection_and_independent_runtime(preflight, provider, auth):
    from src.lifecycle_investigation.runtime import InvestigationRuntime, RuntimeStore
    c, service, _, _ = preflight
    credentials, _, route = synthetic_credentials(provider=provider, auth=auth)
    service.credential_store, service.route_loader = credentials, lambda: route
    runtime = InvestigationRuntime(model_submissions=32, web_actions=18)
    RuntimeStore(c["profile"]).save(runtime)
    packet = service.prepare("OLD")
    assert packet["available"] and packet["reason"] is None
    assert packet["execution"] == {"provider": provider, "auth_mode": auth, "model": route.model, "effort": "high"}
    assert packet["credential_label"] == "Selected account"
    assert packet["limits"]["model_submissions"] == 32 and packet["limits"]["web_actions"] == 18
    assert packet["limits"]["search_enforcement"] == ("observed" if auth == "chatgpt_oauth" else "enforced")
    assert packet["limits"]["output_control"] == ("configured" if auth == "api_key" else "provider")
    assert "do-not-export" not in str(packet) and "local:7" not in str(packet)
    bound = service.validate_start("OLD", preflight_sha256=packet["preflight_sha256"])["binding"]
    assert bound["runtime"] == runtime.model_dump() and bound["selection"]["auth_mode"] == auth


@pytest.mark.parametrize("changed", ["credential", "route", "runtime"])
def test_current_preflight_reconfirmation_binds_credential_route_and_runtime(preflight, changed):
    from src.lifecycle_investigation.runtime import InvestigationRuntime, RuntimeStore
    c, service, rows, route = preflight
    packet = service.prepare("OLD")
    if changed == "credential":
        rows[0].secret = "changed-synthetic-key"
    elif changed == "route":
        route.effort = "medium"
    else:
        RuntimeStore(c["profile"]).save(InvestigationRuntime(model_submissions=32))
    with pytest.raises(ValueError, match="^investigation_preflight_changed$"):
        service.validate_start("OLD", preflight_sha256=packet["preflight_sha256"])


def test_current_preflight_never_uses_ambient_credentials_when_selection_is_inactive(preflight, monkeypatch):
    _, service, rows, _ = preflight
    rows[0].active = False
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-must-not-use")
    packet = service.prepare("OLD")
    assert not packet["available"] and packet["reason"] == "selected_credential_unavailable"


def test_current_preflight_reports_missing_journal_without_installing_it(tmp_path):
    from src.lifecycle_investigation.target import TargetPreflight
    c = setup_workflow(tmp_path, assess=False, event_available=False)
    credentials, _, route = synthetic_credentials()
    service = TargetPreflight(c["service"], credential_store=credentials, route_loader=lambda: route)
    with sqlite3.connect(c["profile"]) as conn:
        before = list(conn.execute("SELECT name,sql FROM sqlite_master"))
    packet = service.prepare("OLD")
    assert not packet["available"] and packet["reason"] == "investigation_not_installed"
    with sqlite3.connect(c["profile"]) as conn:
        assert before == list(conn.execute("SELECT name,sql FROM sqlite_master"))
