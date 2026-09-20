"""The live harness must prove its dispatch budget before provider access."""

import importlib.util
import json
from pathlib import Path
import sqlite3

import httpx
import pytest


@pytest.fixture
def harness():
    path = Path(__file__).resolve().parents[1] / "docs/superpowers/evidence/2026-09-08-sdk152-fixed-output/live_api_canary.py"
    spec = importlib.util.spec_from_file_location("fixed_output_canary", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("status", [200, 400, 429, 500])
def test_live_canary_counts_one_selected_request_and_never_retries(harness, monkeypatch, tmp_path, status):
    path = tmp_path / "profile.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE llm_credentials (id INTEGER, provider TEXT, auth_type TEXT, secret TEXT)")
        conn.execute("INSERT INTO llm_credentials VALUES (3,'openai','api_key','fixture-selected')")
    before = path.read_bytes()
    requests = []

    def handler(_transport, request):
        requests.append(request)
        body = json.loads(request.content)
        assert body["model"] == "gpt-5.6-luna"
        assert request.headers["authorization"] == "Bearer fixture-selected"
        return httpx.Response(status, json={
            "id": "resp_fixture", "object": "response", "created_at": 1,
            "status": "completed", "model": harness.MODEL, "error": None,
            "output": [{"type": "function_call", "id": "fc_test", "call_id": "call_test",
                        "status": "completed", "name": "emit_translation",
                        "arguments": '{"translated_text":"Revenue increased."}'}],
            "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2,
                      "private_field": "must-not-be-in-evidence"},
        })

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", handler)
    output = tmp_path / "receipt.json"
    assert harness.run(path, 3, output) is (status == 200)
    assert len(requests) == 1
    assert path.read_bytes() == before
    receipt = json.loads(output.read_text())
    assert len(receipt["requests"]) == 1
    assert receipt["requests"][0]["http_status"] == status
    assert "fixture-selected" not in output.read_text()
    assert "must-not-be-in-evidence" not in output.read_text()
    # Create-only evidence cannot accidentally authorize a repeat call.
    with pytest.raises(FileExistsError):
        harness.run(path, 3, output)
    assert len(requests) == 1


def test_live_canary_rejects_changed_second_dispatch_before_transport(harness, monkeypatch, tmp_path):
    from src import card_synthesis as cs

    path = tmp_path / "profile.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE llm_credentials (id INTEGER, provider TEXT, auth_type TEXT, secret TEXT)")
        conn.execute("INSERT INTO llm_credentials VALUES (3,'openai','api_key','fixture-selected')")
    requests = []

    def handler(_transport, request):
        requests.append(request)
        return httpx.Response(400, json={"error": {"message": "fixture rejection", "type": "invalid_request_error"}})

    def bad_retry(*args, **kwargs):
        from src.auth_drivers.live_resolver import live_openai_client
        for _ in range(2):
            try:
                live_openai_client().responses.create(model=harness.MODEL, input="test", reasoning={"effort": "low"})
            except Exception:
                pass
        raise RuntimeError("bad_retry_stopped")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", handler)
    monkeypatch.setattr(cs, "_translate_openai", bad_retry)
    output = tmp_path / "receipt.json"
    assert harness.run(path, 3, output) is False
    assert len(requests) == 1
    assert len(json.loads(output.read_text())["requests"]) == 1
