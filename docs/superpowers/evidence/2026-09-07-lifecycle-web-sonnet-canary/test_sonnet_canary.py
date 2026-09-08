import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest
from claude_agent_sdk import ResultMessage, SystemMessage


PACKET = Path(__file__).resolve().parent
PRIOR = PACKET.parent / "2026-09-07-lifecycle-web-oauth-canary"


def load(name, path):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def module():
    return load("renewed_sonnet_canary", PACKET / "claude_canary.py")


def result(session="owned", **changes):
    return ResultMessage(**{
        "subtype": "success", "duration_ms": 1, "duration_api_ms": 1,
        "is_error": False, "num_turns": 2, "session_id": session,
        "terminal_reason": "completed", "model_usage": {"claude-sonnet-5": {
            "inputTokens": 31, "outputTokens": 17, "cacheReadInputTokens": 9,
            "cacheCreationInputTokens": 5, "webSearchRequests": 2}}, **changes,
    })


@pytest.mark.parametrize("session,expected", [("owned", True), ("foreign", False), (None, False)])
@pytest.mark.parametrize("kind", ["init", "result"])
def test_canary_records_session_binding_without_exporting_ids(session, expected, kind):
    api = module()
    message = (SystemMessage(subtype="init", data={"session_id": session,
        "apiKeySource": "none", "model": "claude-sonnet-5", "tools": [], "mcp_servers": []})
        if kind == "init" else result(session))
    value = api.message_witness(message, "owned")
    assert value["session_matches_request"] is expected
    assert "owned" not in json.dumps(value) and "foreign" not in json.dumps(value)


def test_canary_retains_per_model_counts_instead_of_just_a_pass_flag():
    api = module()
    value = api.message_witness(result(), "owned")
    assert value["model_usage"] == {"shape": "object", "models": [{
        "model": "claude-sonnet-5", "shape": "object", "input_tokens": 31,
        "output_tokens": 17, "cache_read_input_tokens": 9,
        "cache_creation_input_tokens": 5, "web_search_requests": 2, "invalid_fields": [],
    }]}
    mixed = result(model_usage={"claude-sonnet-5": {}, "claude-haiku-4-5-20251001": {}})
    assert api.message_witness(mixed, "owned")["model_usage_models"] == ["claude-sonnet-5", "claude-haiku-4-5-20251001"]


@pytest.mark.parametrize("value,shape", [(None, "absent"), ([], "invalid"), ({}, "object")])
def test_canary_usage_absence_and_invalid_shape_do_not_claim_zero_use(value, shape):
    api = module()
    assert api.usage_witness(value) == {"shape": shape, "models": []}


def test_canary_missing_or_malformed_counts_are_not_fabricated_or_leaked():
    api = module()
    row = api.usage_witness({"claude-sonnet-5": {"inputTokens": "private-value", "outputTokens": True,
        "cacheReadInputTokens": -1, "ignored": "private-value"}})["models"][0]
    assert row["input_tokens"] is None and row["output_tokens"] is None
    assert row["cache_read_input_tokens"] is None and row["web_search_requests"] is None
    assert row["invalid_fields"] == ["input_tokens", "output_tokens", "cache_read_input_tokens"]
    assert "private-value" not in str(row)


def fixture_source_checkpoint(tmp_path):
    root = tmp_path / "source"
    checkpoint = tmp_path / "checkpoint"
    root.mkdir()
    checkpoint.mkdir()
    (root / "owned.py").write_text("original")
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = {"files": {"owned.py": sha(root / "owned.py")}, "deleted_files": ["removed.py"]}
    (checkpoint / "source-manifest.json").write_text(json.dumps(manifest))
    (checkpoint / "files.sha256.json").write_text(json.dumps({"files": {
        "source-manifest.json": sha(checkpoint / "source-manifest.json")}}))
    return root, checkpoint, sha(checkpoint / "files.sha256.json")


def test_canary_source_guard_rejects_changed_or_resurrected_inputs(tmp_path):
    api = module()
    root, checkpoint, seal = fixture_source_checkpoint(tmp_path)
    assert api.require_sources(root, checkpoint, seal)["matched_files"] == 1
    (root / "owned.py").write_text("changed")
    with pytest.raises(ValueError, match="offline_admitted_source_changed"):
        api.require_sources(root, checkpoint, seal)
    (root / "owned.py").write_text("original")
    (root / "removed.py").write_text("resurrected")
    with pytest.raises(ValueError, match="offline_admitted_source_changed"):
        api.require_sources(root, checkpoint, seal)
    with pytest.raises(ValueError, match="offline_checkpoint_changed"):
        api.require_sources(root, checkpoint, "0" * 64)


def test_canary_complete_offline_rehearsal_preserves_selected_auth_and_new_witnesses(monkeypatch, tmp_path):
    api = module()
    root, checkpoint, seal = fixture_source_checkpoint(tmp_path)
    monkeypatch.setattr(api, "ROOT", root)
    monkeypatch.setattr(api, "CHECKPOINT", checkpoint)
    monkeypatch.setattr(api, "CHECKPOINT_SEAL", seal)
    helpers = load("prior_canary_test_helpers", PRIOR / "test_live_harness.py")
    monkeypatch.setattr(helpers, "module", lambda: api)
    helpers.test_canary_full_temporary_journal_rehearsal_counts_both_phases_and_source(monkeypatch, tmp_path)
    metrics = json.loads((tmp_path / "offline-canary/metrics.json").read_text())
    for session in metrics["sessions"]:
        assert session["helper_model_overrides"] == {"current": "claude-sonnet-5", "legacy": "claude-sonnet-5"}
        for event in session["events"]:
            if event["kind"] in {"init", "result"}:
                assert event["session_matches_request"] is True
            if event["kind"] == "result":
                assert event["model_usage"]["models"][0]["input_tokens"] == 10
    assert metrics["selected_metadata_unchanged"] is True


def test_executed_canary_plan_cannot_be_reused_after_source_correction():
    api = module()
    with pytest.raises(ValueError, match="^offline_admitted_source_changed$"):
        api.source_identity()
