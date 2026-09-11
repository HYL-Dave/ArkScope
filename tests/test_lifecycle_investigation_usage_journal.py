"""Current usage belongs to durable calls, never inferred remote success."""

from dataclasses import replace
import json
import sqlite3

import pytest

from src.auth_drivers.lifecycle_web_models import WebModelError
from src.lifecycle_investigation.agent import run_agent
from src.lifecycle_investigation.store import InvestigationStore
from src.lifecycle_journal_codec import canonical_json, digest_json
from tests.lifecycle_investigation_fixtures import controller, wait_done
from tests.test_lifecycle_investigation_agent import choose, completed
from tests.test_lifecycle_investigation_findings import payload
from tests.test_ticker_identity_history import damage_saved_rows


def usage_run(tmp_path, *, outcome="complete"):
    calls = []
    async def model(call, credential, control):
        calls.append(call)
        if len(calls) == 1:
            reply = completed(call, control, "not JSON", error="model_output_invalid")
            if outcome == "partial":
                reply = replace(reply, usage={"input_tokens": None, "output_tokens": None})
            return reply
        if outcome in {"lost", "failed"}:
            if outcome == "lost":
                control.reserve_model_request(call.call_id)
                control.bind_remote_id(call.call_id, "lost-remote")
                control.observe_transport_loss(call.call_id)
            raise WebModelError("provider_call_failed")
        material = json.loads(call.prompt.split("\nMATERIAL\n")[1])
        return completed(call, control, choose("conclude", finding=payload(material["sources"][0]["passages"])))
    async def runner(*args, **kwargs):
        return await run_agent(*args, **kwargs, model=model)
    service, store, loads, binding = controller(tmp_path, runner=runner)
    try:
        identity = service.start(binding=binding, request_key="usage-case")["run_id"]
        projected = wait_done(service, identity)
        assert len(calls) == 2 and len(loads) == 1
        return store, identity, projected
    finally:
        service.close()


@pytest.mark.parametrize("outcome,status,tokens", [
    ("complete", "succeeded", (20, 40)), ("partial", "succeeded", (None, None)),
    ("lost", "remote_outcome_unknown", (None, None)), ("failed", "failed", (10, 20)),
])
def test_current_usage_retains_known_or_unknown_totals_and_truthful_remote_outcome(tmp_path, outcome, status, tokens):
    store, identity, projected = usage_run(tmp_path, outcome=outcome)
    row = InvestigationStore(store.path).read(identity)
    assert projected["status"] == row["status"] == status
    assert (projected["stats"]["input_tokens"], projected["stats"]["output_tokens"]) == tokens
    results = [step["payload"] for step in row["steps"] if step["kind"] == "model_result"]
    calls = {call["call_id"]: call for call in row["calls"]}
    assert all(calls[result["call_id"]]["remote_id"] == result["remote_id"] for result in results)
    assert all(calls[result["call_id"]]["terminal"] == "completed" for result in results)
    assert all(result["usage_observation"] is None for result in results)
    assert row["result"]["validated"] is None if outcome in {"lost", "failed"} else projected["action"] == "terminal_delisting"
    if outcome == "lost":
        assert calls["step-2"] == {"call_id": "step-2", "remote_id": "lost-remote", "terminal": None}
    with sqlite3.connect(store.path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM lifecycle_investigation_acceptances").fetchone()[0] == 0


@pytest.mark.parametrize("mutation", ["remote_id", "unknown_call", "duplicate", "malformed_usage", "malformed_observation", "aggregate"])
def test_current_reopened_usage_rechecks_call_binding_and_integrity(tmp_path, mutation):
    store, identity, projected = usage_run(tmp_path)
    assert projected["status"] == "succeeded"
    with sqlite3.connect(store.path) as conn:
        if mutation == "aggregate":
            raw = conn.execute("SELECT payload_json FROM lifecycle_investigation_results WHERE run_id=?", (identity,)).fetchone()[0]
            material = json.loads(raw)
            material["stats"]["input_tokens"] = 999
            damage_saved_rows(conn, "lifecycle_investigation_results",
                "UPDATE lifecycle_investigation_results SET payload_json=?,payload_sha256=? WHERE run_id=?",
                (canonical_json(material), digest_json(material), identity))
        else:
            ordinal, raw, at = conn.execute("SELECT ordinal,payload_json,created_at FROM lifecycle_investigation_steps WHERE run_id=? AND kind='model_result' ORDER BY ordinal LIMIT 1", (identity,)).fetchone()
            material = json.loads(raw)
            if mutation == "remote_id":
                material["remote_id"] = "unbound-remote"
            elif mutation == "unknown_call":
                material["call_id"] = "unbound-call"
            elif mutation == "malformed_usage":
                material["usage"] = {"input_tokens": True, "output_tokens": 20}
            elif mutation == "malformed_observation":
                material["usage_observation"] = {"basis": "adapter_report", "values": {}, "secret": "private-token"}
            if mutation == "duplicate":
                ordinal = conn.execute("SELECT MAX(ordinal)+1 FROM lifecycle_investigation_steps WHERE run_id=?", (identity,)).fetchone()[0]
                conn.execute("INSERT INTO lifecycle_investigation_steps VALUES (?,?,?,?,?,?)",
                    (identity, ordinal, "model_result", canonical_json(material), digest_json(material), at))
            else:
                damage_saved_rows(conn, "lifecycle_investigation_steps",
                    "UPDATE lifecycle_investigation_steps SET payload_json=?,payload_sha256=? WHERE run_id=? AND ordinal=?",
                    (canonical_json(material), digest_json(material), identity, ordinal))
    with pytest.raises(ValueError, match="^investigation_integrity$"):
        InvestigationStore(store.path).read(identity, include_sources=False)
