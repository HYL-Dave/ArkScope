import importlib.util
import json
from pathlib import Path
import sqlite3

import pytest


def module():
    path = Path(__file__).with_name("read_inventory.py")
    spec = importlib.util.spec_from_file_location("web_live_inventory", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def fixture_db(path):
    with sqlite3.connect(path) as conn:
        conn.executescript("""
            CREATE TABLE llm_credentials (id INTEGER PRIMARY KEY, provider TEXT,
                auth_type TEXT, active INTEGER, updated_at TEXT, expires_at TEXT, secret TEXT);
            INSERT INTO llm_credentials VALUES
                (7,'anthropic','claude_code_oauth',1,'2026-09-01',NULL,'secret-never-read');
            CREATE TABLE security_lifecycle_cases (case_id TEXT, source TEXT, source_ref TEXT, ticker TEXT);
            INSERT INTO security_lifecycle_cases VALUES ('case-1','sec_edgar','private-source-ref','OLD');
        """)


def test_inventory_allows_only_explicit_metadata_and_denies_secret_and_writes(tmp_path):
    api = module()
    path = tmp_path / "profile.sqlite"
    fixture_db(path)
    before = path.read_bytes()
    with api.read_connection(path) as (conn, reads):
        assert tuple(conn.execute("SELECT provider,auth_type,active FROM llm_credentials").fetchone()) == (
            "anthropic", "claude_code_oauth", 1)
        for query in ("SELECT secret FROM llm_credentials", "SELECT * FROM llm_credentials",
                      "UPDATE llm_credentials SET active=0", "CREATE TABLE surprise(x)",
                      "PRAGMA query_only=OFF", "ATTACH ':memory:' AS extra"):
            with pytest.raises(sqlite3.DatabaseError):
                conn.execute(query)
        assert ("llm_credentials", "secret") not in reads
    assert path.read_bytes() == before


def test_case_correspondence_counts_all_observations_without_exposing_refs():
    api = module()
    cases = [("sec_edgar", "private-source-ref", "OLD"), ("listing_authority", "listing:OLD", "OLD")]
    observations = [("sec_edgar", "private-source-ref", "OLD"), ("sec_edgar", "other-ref", "NEW")]
    result = api.correspondence(cases, observations, {"OLD"})
    assert result["market_only_count"] == 1
    assert result["case_without_observation_count"] == 0
    assert result["provider_case_count"] == 1
    assert result["expected_provider_observation_count"] == 1
    assert result["market_observation_count"] == 2
    assert result["case_count"] == 2
    assert "private-source-ref" not in json.dumps(result)
    assert "other-ref" not in json.dumps(result)


def test_inventory_missing_store_never_creates_database(tmp_path):
    api = module()
    path = tmp_path / "missing.sqlite"
    with pytest.raises(sqlite3.OperationalError):
        with api.read_connection(path):
            pass
    assert not path.exists()


def test_inventory_artifact_is_create_only(tmp_path):
    api = module()
    path = tmp_path / "inventory.json"
    api.write_new_json(path, {"status": "first"})
    with pytest.raises(FileExistsError):
        api.write_new_json(path, {"status": "replaced"})
    assert json.loads(path.read_text()) == {"status": "first"}
