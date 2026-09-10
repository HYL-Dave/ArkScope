import json
import socket
import sqlite3

import pytest

from src.security_lifecycle_population import LifecyclePopulationUnavailable
from tests.test_lifecycle_web_review import context, confirm, prepare, rows


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("web_read_must_not_dispatch")
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)


def current(c):
    service = c["service"]._read_service
    listing = service.list_current_reviews(at=c["now"][0], case_id=c["case_id"])
    assert len(listing["items"]) == 1
    return service.get_current_review(listing["items"][0]["review_id"], at=c["now"][0])


@pytest.mark.parametrize("provider,auth", [("openai", "api_key"), ("openai", "chatgpt_oauth"),
                                          ("anthropic", "api_key"), ("anthropic", "claude_code_oauth")])
@pytest.mark.parametrize("with_gap", [False, True])
def test_research_and_current_detail_share_readonly_web_findings_for_every_auth(tmp_path, monkeypatch, provider, auth, with_gap):
    from src.tools import security_lifecycle_tools as tools
    from tests.test_lifecycle_web_gaps import COMPLETION, GAPS
    c = context(tmp_path, provider=provider, auth=auth, completion=COMPLETION if with_gap else None)
    before = rows(c)
    detail = current(c)
    result = detail["web_runs"][0]
    assert result["execution"] == {"provider": provider, "auth_mode": auth, "model": c["web"].read(c["run_id"])["selection"].model}
    assert result["run_id"] == c["run_id"] and result["finding"]["action"] == "terminal_delisting"
    assert result["finding"]["citations"][0]["quote"]
    assert result["model_submissions"] == 2
    assert result["source_gaps"] == (GAPS if with_gap else [])
    monkeypatch.setattr(tools, "_profile_db_path", lambda: str(c["profile"]))
    monkeypatch.setattr(tools, "resolve_market_db_path", lambda: str(c["market"]))
    monkeypatch.setattr(tools, "SecurityLifecycleReadService", lambda **kwargs: c["service"]._read_service)
    research = tools.get_security_lifecycle_review(detail["item"]["review_id"])
    assert research["status"] == "ok" and research["web_runs"] == detail["web_runs"]
    encoded = json.dumps(detail)
    for private in ("local:7", "worker-1", "header_json", "header_sha256", "page_sha256", "credential_generation", "remote_id"):
        assert private not in encoded
    assert rows(c) == before and "OLD" in c["sources"]()
    confirm(c, prepare(c))
    after = current(c)
    assert after["web_runs"] == detail["web_runs"]
    assert after["item"]["next_action"]["state"] == "applied"
    assert after["item"]["collection"]["state"] == "not_tracking"


def test_population_retains_web_sources_and_human_adoption_without_exporting_pages_or_credentials(tmp_path):
    c = context(tmp_path)
    confirm(c, prepare(c))
    before = rows(c)
    manifest = c["service"]._read_service.population_manifest(at=c["now"][0])
    web = manifest["retention"]["web_journal"]
    assert web["installed"] is True
    assert web["runs"][0]["run_id"] == c["run_id"] and web["runs"][0]["case_id"] == c["case_id"]
    assert web["acceptances"][0]["run_id"] == c["run_id"]
    assert len(web["pages"]) == 1 and len(web["pages"][0]["page_sha256"]) == 64
    assert len(web["calls"]) == 2 and web["results"][0]["run_id"] == c["run_id"]
    assert not manifest["deletion_authorized"] and not manifest["retention"]["deletion_candidates"]
    for private in ("local:7", "worker-1", "header_json", "page_json", "payload_json", "packet_json"):
        assert private not in json.dumps(web)
    assert rows(c) == before


def test_missing_journal_is_empty_but_malformed_installed_journal_is_not_silently_dropped(tmp_path):
    from tests.test_security_lifecycle_terminal_workflow import setup_workflow
    c = setup_workflow(tmp_path)
    assert current(c)["web_runs"] == []
    with sqlite3.connect(c["profile"]) as conn:
        conn.execute("CREATE TABLE lifecycle_web_runs (run_id TEXT)")
    with pytest.raises(LifecyclePopulationUnavailable):
        current(c)


def test_population_rejects_orphaned_web_adoption_dependency(tmp_path):
    from src.security_lifecycle_population import _digest, build_population_manifest, read_population_snapshot
    c = context(tmp_path)
    confirm(c, prepare(c))
    snapshot = read_population_snapshot(c["market"], c["profile"], at=c["now"][0])
    snapshot["material"]["web_journal_inventory"]["acceptances"][0]["assessment_id"] = "missing"
    snapshot["sha256"] = _digest({key: snapshot[key] for key in ("version", "at", "material")})
    with pytest.raises(LifecyclePopulationUnavailable, match="population_web_dependency_invalid"):
        build_population_manifest(snapshot)


@pytest.mark.parametrize("value", [None, [], {}, {"installed": False}])
def test_population_does_not_treat_a_malformed_web_inventory_as_absent(tmp_path, value):
    from src.security_lifecycle_population import _digest, build_population_manifest, read_population_snapshot
    c = context(tmp_path)
    snapshot = read_population_snapshot(c["market"], c["profile"], at=c["now"][0])
    snapshot["material"]["web_journal_inventory"] = value
    snapshot["sha256"] = _digest({key: snapshot[key] for key in ("version", "at", "material")})
    with pytest.raises(LifecyclePopulationUnavailable):
        build_population_manifest(snapshot)
