import asyncio
import importlib.util
from pathlib import Path
import sys

import pytest
from claude_agent_sdk import AssistantMessage, ToolResultBlock, ToolUseBlock, UserMessage


def module():
    path = Path(__file__).with_name("diagnose_analysis.py")
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("analysis_diagnostic", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


@pytest.mark.parametrize("payload,valid", [({"count": 1}, True), ({"count": "one"}, False), ({}, False)])
def test_diagnostic_records_real_schema_errors_without_tool_values(payload, valid):
    api = module()
    schema = {"type": "object", "properties": {"count": {"type": "integer"}}, "required": ["count"]}
    observer = api.Diagnostics(schema, "private-session", "private-token")
    message = AssistantMessage(model="claude-sonnet-5", content=[ToolUseBlock("tool-private", "StructuredOutput", payload)])
    result = observer.message(message)
    assert result["structured_output_attempts"][0]["schema_valid"] is valid
    assert bool(result["structured_output_attempts"][0]["schema_errors"]) is not valid
    assert "tool-private" not in str(result)


def test_diagnostic_accepts_only_owned_output_tool_results_and_scrubs_auth():
    api = module()
    observer = api.Diagnostics({"type": "object"}, "private-session", "private-token")
    observer.message(AssistantMessage(model="claude-sonnet-5", content=[ToolUseBlock("tool-private", "StructuredOutput", {})]))
    result = observer.message(UserMessage(content=[
        ToolResultBlock("tool-private", "private-session private-token tool-private validation error", True),
        ToolResultBlock("unowned", "unrelated-content", True),
    ]))
    assert len(result["owned_tool_results"]) == 1
    assert result["owned_tool_results"][0]["is_error"] is True
    assert "validation error" in result["owned_tool_results"][0]["content"]
    assert not any(secret in str(result) for secret in ("private-session", "private-token", "tool-private", "unrelated-content"))


def test_replay_builds_actual_analysis_call_without_source_or_model_dispatch(monkeypatch):
    from src import security_lifecycle_web_pipeline as pipeline
    from src.lifecycle_public_sources import PublicSourceReader
    from src.security_lifecycle_web_contract import RunControl, validate_selection
    from src.security_lifecycle_web_finding import WebFinding, strict_schema
    from tests.test_security_lifecycle_web_finding import source_page

    api = module()
    monkeypatch.setattr(PublicSourceReader, "read", lambda *args: pytest.fail("no_http_during_replay"))
    monkeypatch.setattr(pipeline, "call_lifecycle_web_model", lambda *args: pytest.fail("no_live_model_during_capture"))
    selection = validate_selection("anthropic", "claude_code_oauth", "claude-sonnet-5", "local:7")
    page = source_page("TravelCenters of America Inc. common stock (TA).", "https://ir.example.com/notice")
    row = {"request": api.original.public_case("2026-09-07"), "selection": selection,
           "options": api.original.options(), "pages": {"source-1": page}}
    search = {"sources": [page.url, "https://ir.example.com/unread"], "unresolved_conditions": []}
    failures = [{"url": search["sources"][1], "status": "failed", "code": "source_unavailable"}]
    call = asyncio.run(api.capture_analysis(row, search, failures))
    assert call.phase == "analysis" and call.selection == selection
    assert call.output_schema == strict_schema(WebFinding)
    assert page.text in call.prompt
    assert '"unread_sources":[{"source_id":"source-2"' in call.prompt
    assert "source_unavailable" in call.prompt
    assert "offline-search-replay" not in call.prompt
    assert RunControl(selection=selection, max_model_requests=1).model_requests == 0
