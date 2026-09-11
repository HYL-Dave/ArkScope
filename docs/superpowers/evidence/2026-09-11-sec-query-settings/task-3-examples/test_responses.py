"""Archive actual disposable HTTP responses for the Task 3 handoff."""

import json
import os
from pathlib import Path

from tests.test_sec_research_routes import profile, publish_catalog, route, stored


def test_archive_http_responses(route, profile, stored, monkeypatch):
    module, _, client = route
    monkeypatch.setattr(module, "require_db_write", lambda *args: None)
    examples = {"config_installed": client.get("/sec-research/config").json()}
    examples["config_saved"] = client.put(
        "/sec-research/config", json={"capture_budget_bytes": 1}).json()
    publish_catalog(stored, [(1, "2026-02-01", "10-K")])
    examples["config_over_budget"] = client.get("/sec-research/config").json()
    examples["filings_ok"] = client.get("/sec-research/320193/filings").json()
    examples["filings_empty"] = client.get(
        "/sec-research/320193/filings", params={"forms": "10-Q"}).json()
    examples["invalid_cursor"] = client.get(
        "/sec-research/320193/filings", params={"cursor": "!"}).json()
    publish_catalog(stored, pending=True)
    examples["filings_partial"] = client.get("/sec-research/320193/filings").json()
    assert examples["filings_ok"]["status"] == "ok"
    assert examples["filings_empty"]["status"] == "empty"
    assert examples["filings_partial"]["status"] == "partial"
    destination = Path(os.environ["ARKSCOPE_OFFLINE_TEST_WORKSPACE"]) / "responses.json"
    destination.write_text(json.dumps(examples, indent=2) + "\n")
