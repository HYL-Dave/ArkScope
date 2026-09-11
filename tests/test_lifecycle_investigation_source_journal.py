"""Retained current sources, supplied passages, and cooperative final validation."""

import json
import sqlite3

import pytest

from src.lifecycle_investigation import agent
from src.lifecycle_investigation.store import InvestigationStore
from src.lifecycle_journal_codec import canonical_json, digest_json
from tests.lifecycle_investigation_fixtures import controller, wait_done
from tests.test_lifecycle_investigation_agent import choose, completed
from tests.test_lifecycle_investigation_findings import NOTICE, payload
from tests.test_lifecycle_investigation_review import context, prepare
from tests.test_ticker_identity_history import damage_saved_rows


def test_current_journal_preserves_full_unicode_source_and_supplied_passages_after_reopen(tmp_path):
    body = "Public appendix \U00020000\u4e2d.\n" * 15000 + NOTICE
    async def model(call, credential, control):
        material = json.loads(call.prompt.split("\nMATERIAL\n")[1])
        parts = material["sources"][0]["passages"]
        identity = next(part for part in parts if "Issuer Old Inc" in part["text"])
        event = next(part for part in parts if "Trading in" in part["text"])
        assert len(call.prompt) < len(body) / 3
        return completed(call, control, choose("conclude", finding=payload([identity, event])))
    c = context(tmp_path, body=body, model=model)
    row = InvestigationStore(c["profile"]).read(c["run_id"])
    assert row["sources"]["source-1"]["text"] == body
    requested = [step["payload"] for step in row["steps"] if step["kind"] == "model_request"][-1]
    assert set(row["result"]["supplied_passages"]) == set(requested["supplied_passages"])
    assert {item["passage_id"] for item in row["result"]["validated"]["passages"]} <= set(requested["supplied_passages"])
    with sqlite3.connect(c["profile"]) as conn:
        raw, digest = conn.execute("SELECT payload_json,payload_sha256 FROM lifecycle_investigation_sources").fetchone()
        assert json.loads(raw)["text"] == body and digest == digest_json(json.loads(raw))
    assert prepare(c)["ready"]


@pytest.mark.parametrize("change", ["payload_digest", "source_digest", "source_text"])
def test_current_adoption_rejects_changed_source_or_capture_digest(tmp_path, change):
    c = context(tmp_path)
    with sqlite3.connect(c["profile"]) as conn:
        material = json.loads(conn.execute("SELECT payload_json FROM lifecycle_investigation_sources").fetchone()[0])
        if change == "source_digest":
            material["text_sha256"] = "0" * 64
        elif change == "source_text":
            material["text"] += "\nContrary new material."
        digest = "0" * 64 if change == "payload_digest" else digest_json(material)
        damage_saved_rows(conn, "lifecycle_investigation_sources",
            "UPDATE lifecycle_investigation_sources SET payload_json=?,payload_sha256=?", (canonical_json(material), digest))
    with pytest.raises(ValueError, match="investigation_integrity|source_integrity"):
        prepare(c)
    assert "OLD" in c["sources"]()


@pytest.mark.parametrize("supplied", [[], ["source-999:p1"], None])
def test_current_adoption_requires_citations_from_the_recorded_model_context(tmp_path, supplied):
    c = context(tmp_path)
    with sqlite3.connect(c["profile"]) as conn:
        ordinal, raw = conn.execute("SELECT ordinal,payload_json FROM lifecycle_investigation_steps WHERE kind='model_request' ORDER BY ordinal DESC LIMIT 1").fetchone()
        material = json.loads(raw)
        material["supplied_passages"] = supplied
        damage_saved_rows(conn, "lifecycle_investigation_steps",
            "UPDATE lifecycle_investigation_steps SET payload_json=?,payload_sha256=? WHERE ordinal=?",
            (canonical_json(material), digest_json(material), ordinal))
    with pytest.raises(ValueError, match="investigation_integrity"):
        prepare(c)
    assert "OLD" in c["sources"]()


@pytest.mark.parametrize("cancel", [False, True])
def test_current_agent_final_source_validation_allows_heartbeat_and_running_cancellation(tmp_path, monkeypatch, cancel):
    service, store, _, binding = controller(tmp_path)
    original, observed = agent.validate_finding, []
    def validate(*args, **kwargs):
        with sqlite3.connect(store.path) as conn:
            identity, owner = conn.execute("SELECT run_id,owner FROM lifecycle_investigation_jobs WHERE status='running'").fetchone()
        assert store.heartbeat(identity, owner=owner) is False
        if cancel:
            service.cancel(identity)
        observed.append(True)
        return original(*args, **kwargs)
    monkeypatch.setattr(agent, "validate_finding", validate)
    try:
        identity = service.start(binding=binding, request_key="current-validation")["run_id"]
        result = wait_done(service, identity)
        assert result["status"] == ("cancelled" if cancel else "succeeded"), result
        assert result["action"] == (None if cancel else "terminal_delisting")
        assert observed == [True]
        row = store.read(identity)
        assert all(call["terminal"] == "completed" for call in row["calls"])
        assert row["sources"]["source-1"]["text"] == NOTICE
        with sqlite3.connect(store.path) as conn:
            assert conn.execute("SELECT COUNT(*) FROM lifecycle_investigation_acceptances").fetchone()[0] == 0
    finally:
        service.close()
