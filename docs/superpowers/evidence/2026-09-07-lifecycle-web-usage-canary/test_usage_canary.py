"""Provider-free rehearsal of the new one-shot harness, not live evidence."""

import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

import pytest


PACKET = Path(__file__).resolve().parent
OLD = PACKET.parent / "2026-09-07-lifecycle-web-sonnet-canary"


def load(name, path):
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def module():
    return load("usage_canary", PACKET / "claude_canary.py")


def checkpoint(api, monkeypatch, tmp_path):
    helper = load("sealed_sonnet_helpers", OLD / "test_sonnet_canary.py")
    root, packet, seal = helper.fixture_source_checkpoint(tmp_path)
    monkeypatch.setattr(api, "ROOT", root)
    monkeypatch.setattr(api, "CHECKPOINT", packet)
    monkeypatch.setattr(api, "CHECKPOINT_SEAL", seal)


def test_canary_source_admission_precedes_any_credential_metadata_read(monkeypatch):
    api = module()
    def rejected():
        raise ValueError("offline_checkpoint_changed")
    monkeypatch.setattr(api, "source_identity", rejected)
    monkeypatch.setattr(api, "selected_metadata", lambda path: pytest.fail("production_metadata_read_before_source_admission"))
    with pytest.raises(ValueError, match="^offline_checkpoint_changed$"):
        api.prepared_plan(Path("unused.sqlite"), "2026-09-07")


def test_canary_requires_explicit_new_checkpoint_not_reused_authority(monkeypatch):
    api = module()
    assert api.CHECKPOINT.name == "2026-09-07-lifecycle-web-usage"
    assert api.CHECKPOINT_SEAL is None
    with pytest.raises(ValueError, match="^explicit_offline_checkpoint_required$"):
        api.source_identity()


def test_canary_limits_match_current_source_envelope_without_token_truncation():
    api = module()
    limits = api.options()
    assert limits.max_source_bytes == 32 * 1024**2
    assert limits.max_decoded_source_bytes == 128 * 1024**2
    assert limits.source_timeout_seconds == limits.model_timeout_seconds == 180
    assert limits.max_sources == 4 and limits.max_source_requests == 8 and limits.max_redirects == 2
    assert limits.max_search_uses == 4 and limits.output_token_limit is None and limits.effort == "medium"
    assert api.public_case("2026-09-07").security_class == "common stock"
    assert api.public_case("2026-09-07").venue == "NASDAQ"


@pytest.mark.parametrize("failure", [None, "source", "analysis"])
def test_canary_real_controller_keeps_usage_hook_and_exact_budget_without_live_calls(monkeypatch, tmp_path, failure):
    from claude_agent_sdk import AssistantMessage, ResultMessage, SystemMessage, ToolUseBlock
    import claude_agent_sdk
    from src.auth_drivers import token_store
    from src.lifecycle_public_sources import PublicSourceReader, SourceReadError, SourceReadObservation
    from src.security_lifecycle_web_finding import WebFinding
    from tests.test_security_lifecycle_web_finding import finding_payload, source_page

    api = module()
    checkpoint(api, monkeypatch, tmp_path)
    helper = load("original_harness_helpers", OLD.parent / "2026-09-07-lifecycle-web-oauth-canary/test_live_harness.py")
    profile = tmp_path / "production-fixture.sqlite"
    helper.credentials(profile, [helper.row()])
    with sqlite3.connect(profile) as conn:
        conn.execute("CREATE TABLE data_provider_config(provider TEXT,field TEXT,value TEXT)")
    original = profile.read_bytes()
    notice = "TravelCenters of America Inc. common stock (TA) was delisted from NASDAQ effective September 1, 2026."
    finding = WebFinding.model_validate(finding_payload(source_ticker="TA", issuer_name="TravelCenters of America Inc.", security_class="common stock", citations=[{
        "source_id": "source-1", "quote": notice, "supports": ["security_identity", "listing_ended", "effective_date"]}])).model_dump()
    queries = []

    class Tokens:
        backend = "offline_fixture"
        def load(self, **kwargs):
            assert kwargs == {"provider": "anthropic", "auth_mode": "claude_code_oauth", "credential_id": "local:7"}
            return token_store.StoredTokenRecord("private-fixture-token")

    class OfflineClient:
        def __init__(self, *, options):
            self.options = options
        async def connect(self):
            pass
        async def query(self, prompt, **kwargs):
            assert kwargs["session_id"] == self.options.session_id
            queries.append("search" if self.options.tools else "analysis")
        async def disconnect(self):
            pass
        async def interrupt(self):
            pass
        async def receive_response(self):
            options = self.options
            session = options.session_id
            yield SystemMessage(subtype="init", data={"session_id": session, "apiKeySource": "none", "model": options.model,
                "tools": list(options.tools) + ["StructuredOutput"], "mcp_servers": []})
            search = bool(options.tools)
            if search:
                result = await options.hooks["PreToolUse"][0].hooks[0]({"hook_event_name": "PreToolUse", "session_id": session,
                    "tool_name": "WebSearch", "tool_input": {"query": "TA common stock listing fixture"}, "tool_use_id": "web-1"}, "web-1", {})
                assert result["hookSpecificOutput"]["permissionDecision"] == "allow"
                yield AssistantMessage(model=options.model, content=[ToolUseBlock(id="web-1", name="WebSearch", input={"query": "TA fixture"})])
            output = {"sources": ["https://ir.example.com/notice"], "unresolved_conditions": []} if search else finding
            failed = not search and failure == "analysis"
            yield ResultMessage(subtype="error_during_execution" if failed else "success", duration_ms=1, duration_api_ms=1,
                is_error=failed, num_turns=2, session_id=session, terminal_reason="completed", structured_output=output,
                usage={"input_tokens": 4, "output_tokens": 1036}, model_usage={options.model: {
                    "inputTokens": 29706 if search else 300, "outputTokens": 3228 if search else 400,
                    "cacheReadInputTokens": 3354, "cacheCreationInputTokens": 3976, "webSearchRequests": 2 if search else 0}})

    def read(self, url):
        self._request_count += 1
        self._observations.append(SourceReadObservation(self._request_count, 503 if failure == "source" else 200,
            "content_length", "identity", 200, 200, 200, "source_http_error" if failure == "source" else "captured"))
        if failure == "source":
            raise SourceReadError("source_http_error")
        return source_page(notice, url)

    monkeypatch.setattr(token_store, "get_token_store", lambda **kwargs: Tokens())
    monkeypatch.setattr(claude_agent_sdk, "ClaudeSDKClient", OfflineClient)
    monkeypatch.setattr(PublicSourceReader, "read", read)
    plan = api.prepared_plan(profile, "2026-09-07")
    work = tmp_path / "rehearsal"
    assert api.execute(profile, plan, work) == (0 if failure is None else 1)
    value = json.loads((work / "result.json").read_text())
    metrics = json.loads((work / "metrics.json").read_text())
    expected_queries = ["search"] if failure == "source" else ["search", "analysis"]
    assert queries == expected_queries
    assert metrics["sdk_query_submissions"] == metrics["journal_model_submissions"] == len(expected_queries)
    assert metrics["source_http_requests"] == metrics["token_loads"] == 1
    assert metrics["source_reads"][0]["observations"][0]["request_index"] == 1
    assert metrics["source_reads"][0]["observations"][0]["received_body_bytes"] == 200
    assert metrics["human_assessments_created"] == metrics["human_adoptions_created"] == 0
    report = value["usage_report"]
    assert report["recorded_submissions"] == (2 if failure is None else 1)
    assert report["phases"][0]["input_tokens"] == 29706
    assert report["phases"][0]["output_tokens"] == 3228
    assert report["phases"][0]["cache_read_input_tokens"] == 3354
    assert report["phases"][0]["cache_creation_input_tokens"] == 3976
    assert report["coverage"] == ("partial" if failure == "analysis" else "complete")
    assert report["known_subtotal"]["input_tokens"] == (30006 if failure is None else 29706)
    assert report["totals"]["input_tokens"] == (None if failure == "analysis" else report["known_subtotal"]["input_tokens"])
    for session in metrics["sessions"]:
        assert session["helper_model_overrides"] == {"current": "claude-sonnet-5", "legacy": "claude-sonnet-5"}
        assert session["events"][0]["api_key_source"] == "none"
        assert all(event["session_matches_request"] for event in session["events"] if event["kind"] in {"init", "result"})
    assert metrics["phase_replies"][0]["usage_observation"]["basis"] == "claude_model_usage"
    assert "private-fixture-token" not in json.dumps([value, metrics, plan])
    assert profile.read_bytes() == original


@pytest.mark.parametrize("change", ["source", "seal", "resurrection"])
def test_canary_checkpoint_drift_stops_before_runtime_or_profile(monkeypatch, tmp_path, change):
    api = module()
    checkpoint(api, monkeypatch, tmp_path)
    if change == "source":
        (api.ROOT / "owned.py").write_text("changed")
    elif change == "seal":
        monkeypatch.setattr(api, "CHECKPOINT_SEAL", "0" * 64)
    else:
        (api.ROOT / "removed.py").write_text("resurrected")
    monkeypatch.setattr(api, "selected_metadata", lambda path: pytest.fail("production_profile_read"))
    with pytest.raises(ValueError, match="^offline_(admitted_source|checkpoint)_changed$"):
        api.prepared_plan(Path("unused.sqlite"), "2026-09-07")
