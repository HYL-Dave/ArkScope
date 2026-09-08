import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

import pytest


def module():
    directory = Path(__file__).parent
    sys.path.insert(0, str(directory))
    spec = importlib.util.spec_from_file_location("web_claude_live", directory / "claude_canary.py")
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def credentials(path, rows):
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE llm_credentials (id INTEGER PRIMARY KEY, provider TEXT, auth_type TEXT, active INTEGER, updated_at TEXT, expires_at TEXT, secret TEXT)")
        conn.executemany("INSERT INTO llm_credentials VALUES (?,?,?,?,?,?,?)", rows)


def row(identity=7, active=1):
    return (identity, "anthropic", "claude_code_oauth", active, "2026-09-01", None, "NEVER_READ_THIS")


def test_canary_selects_only_unique_active_claude_oauth_without_secret(tmp_path):
    api = module()
    path = tmp_path / "profile.sqlite"
    credentials(path, [row(), row(8, 0), (9, "anthropic", "api_key", 0, "old", None, "private-api-key")])
    before = path.read_bytes()
    selected = api.selected_metadata(path)
    assert selected["id"] == 7
    assert "secret" not in selected
    assert "NEVER_READ_THIS" not in str(selected)
    assert path.read_bytes() == before


@pytest.mark.parametrize("rows", [[], [row(7, 0)], [row(), row(8)]])
def test_canary_ambiguous_or_inactive_credentials_cannot_fall_back(tmp_path, rows):
    api = module()
    path = tmp_path / "profile.sqlite"
    credentials(path, rows)
    with pytest.raises(ValueError, match="active_claude_oauth_ambiguous"):
        api.selected_metadata(path)


def test_canary_observer_records_literal_auth_and_actual_model_not_raw_message():
    api = module()
    from claude_agent_sdk import SystemMessage
    message = SystemMessage(subtype="init", data={
        "apiKeySource": "none", "model": "claude-sonnet-5", "tools": ["WebSearch", "StructuredOutput"],
        "mcp_servers": [], "session_id": "private-session", "token": "private-token",
    })
    observed = api.message_witness(message)
    assert observed["api_key_source"] == "none"
    assert observed["model"] == "claude-sonnet-5"
    assert observed["tools"] == ["WebSearch", "StructuredOutput"]
    assert "private" not in str(observed)


def test_canary_observer_does_not_sanitize_absent_auth_into_none_literal():
    api = module()
    from claude_agent_sdk import SystemMessage
    for value, expected in [({}, "absent"), ({"apiKeySource": None}, "null")]:
        observed = api.message_witness(SystemMessage(subtype="init", data=value))
        assert observed["api_key_source"] == expected
        assert observed["api_key_source"] != "none"


def test_canary_budget_is_search_plus_analysis_not_generic_retry():
    api = module()
    value = api.options()
    assert value.max_search_uses == 4
    assert value.max_sources == 4 and value.max_source_requests == 8
    assert value.model_timeout_seconds == 180 and value.source_timeout_seconds == 45
    assert value.output_token_limit is None
    assert api.public_case("2026-09-07").ticker == "TA"
    assert api.public_case("2026-09-07").issuer_name == "TravelCenters of America Inc."


def test_canary_sec_contact_query_cannot_read_api_keys(tmp_path):
    api = module()
    path = tmp_path / "profile.sqlite"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE data_provider_config(provider TEXT,field TEXT,value TEXT)")
        conn.executemany("INSERT INTO data_provider_config VALUES (?,?,?)", [
            ("sec_edgar", "user_agent", "ArkScope contact@example.org"),
            ("massive", "api_key", "do-not-use-this-key"),
        ])
    assert api.sec_contact(path) == "ArkScope contact@example.org"
    with sqlite3.connect(path) as conn:
        conn.execute("DELETE FROM data_provider_config WHERE provider='sec_edgar'")
    assert api.sec_contact(path) is None


def test_canary_full_temporary_journal_rehearsal_counts_both_phases_and_source(monkeypatch, tmp_path):
    api = module()
    import claude_agent_sdk
    from claude_agent_sdk import AssistantMessage, ResultMessage, SystemMessage, ToolUseBlock
    from src.auth_drivers import token_store
    from src.lifecycle_public_sources import PublicSourceReader
    from src.security_lifecycle_web_finding import WebFinding
    from tests.test_security_lifecycle_web_finding import finding_payload, source_page
    profile = tmp_path / "production-fixture.sqlite"
    credentials(profile, [row()])
    with sqlite3.connect(profile) as conn:
        conn.execute("CREATE TABLE data_provider_config(provider TEXT,field TEXT,value TEXT)")
    before = profile.read_bytes()
    notice = "TravelCenters of America Inc. Class A common stock (TA) was delisted from NASDAQ effective September 1, 2026."
    payload = finding_payload(source_ticker="TA", issuer_name="TravelCenters of America Inc.", citations=[{
        "source_id": "source-1", "quote": notice, "supports": ["security_identity", "listing_ended", "effective_date"]}])
    payload = WebFinding.model_validate(payload).model_dump()

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
        async def disconnect(self):
            pass
        async def interrupt(self):
            pass
        async def receive_response(self):
            options = self.options
            session = options.session_id
            yield SystemMessage(subtype="init", data={"session_id": session, "apiKeySource": "none", "model": options.model,
                "tools": list(options.tools) + ["StructuredOutput"], "mcp_servers": []})
            if options.tools:
                decision = await options.hooks["PreToolUse"][0].hooks[0]({"hook_event_name": "PreToolUse", "session_id": session,
                    "tool_name": "WebSearch", "tool_input": {"query": "public TA fixture"}, "tool_use_id": "web-1"}, "web-1", {})
                assert decision["hookSpecificOutput"]["permissionDecision"] == "allow"
                yield AssistantMessage(model=options.model, content=[ToolUseBlock(id="web-1", name="WebSearch", input={"query": "public TA fixture"})])
            output = {"sources": ["https://ir.example.com/notice"], "unresolved_conditions": []} if options.tools else payload
            yield ResultMessage(subtype="success", duration_ms=1, duration_api_ms=1, is_error=False, num_turns=2,
                session_id=session, terminal_reason="completed", structured_output=output,
                usage={"input_tokens": 10, "output_tokens": 20}, model_usage={options.model: {"inputTokens": 10, "outputTokens": 20}})

    def read(self, url):
        self._request_count += 1
        return source_page(notice, url)
    monkeypatch.setattr(token_store, "get_token_store", lambda **kwargs: Tokens())
    monkeypatch.setattr(claude_agent_sdk, "ClaudeSDKClient", OfflineClient)
    monkeypatch.setattr(PublicSourceReader, "read", read)
    plan = api.prepared_plan(profile, "2026-09-07")
    work = tmp_path / "offline-canary"
    assert api.execute(profile, plan, work) == 0
    metrics = json.loads((work / "metrics.json").read_text())
    result = json.loads((work / "result.json").read_text())
    assert metrics["sdk_query_submissions"] == metrics["journal_model_submissions"] == 2
    assert metrics["source_http_requests"] == 1
    assert metrics["source_reads"][0]["document_sha256"] == source_page(notice).body_sha256
    assert result["finding"]["action"] == "terminal_delisting"
    assert metrics["human_assessments_created"] == metrics["human_adoptions_created"] == 0
    assert metrics["token_loads"] == 1
    assert all(row["events"][0]["api_key_source"] == "none" for row in metrics["sessions"])
    assert "private-fixture-token" not in (work / "metrics.json").read_text()
    assert profile.read_bytes() == before
