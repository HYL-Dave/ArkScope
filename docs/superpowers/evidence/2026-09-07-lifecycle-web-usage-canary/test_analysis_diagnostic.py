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
    failures = [{"url": page.url, "status": "captured", "document_sha256": page.body_sha256,
                 "text_sha256": page.text_sha256, "capture_sha256": page.capture_sha256},
                {"url": search["sources"][1], "status": "failed", "code": "source_unavailable"}]
    call = asyncio.run(api.capture_analysis(row, search, failures))
    assert call.phase == "analysis" and call.selection == selection
    assert call.output_schema == strict_schema(WebFinding)
    assert page.text in call.prompt
    assert '"unread_sources":[{"source_id":"source-2"' in call.prompt
    assert "source_unavailable" in call.prompt
    assert "offline-search-replay" not in call.prompt
    assert RunControl(selection=selection, max_model_requests=1).model_requests == 0


@pytest.mark.parametrize("tampered", [False, True])
def test_analysis_replay_uses_exact_redirect_capture_not_new_retrieval(monkeypatch, tampered):
    from src.lifecycle_public_sources import PublicSourceReader
    from src.security_lifecycle_web_contract import validate_selection
    from tests.test_security_lifecycle_web_finding import source_page

    api = module()
    monkeypatch.setattr(PublicSourceReader, "read", lambda *args: pytest.fail("no_http_during_replay"))
    page = source_page("TravelCenters of America Inc. common stock (TA).", "https://ir.example.com/notice")
    requested = "https://ir.example.com/redirect-to-notice"
    row = {"request": api.original.public_case("2026-09-07"),
           "selection": validate_selection("anthropic", "claude_code_oauth", "claude-sonnet-5", "local:7"),
           "options": api.original.options(), "pages": {"source-1": page}}
    search = {"sources": [requested], "unresolved_conditions": []}
    receipts = [{"url": page.url, "status": "captured", "document_sha256": page.body_sha256,
                 "text_sha256": "0" * 64 if tampered else page.text_sha256, "capture_sha256": page.capture_sha256}]
    if tampered:
        with pytest.raises(ValueError, match="^capture_receipt_changed$"):
            asyncio.run(api.capture_analysis(row, search, receipts))
    else:
        call = asyncio.run(api.capture_analysis(row, search, receipts))
        assert page.text in call.prompt and page.url in call.prompt
        assert requested not in call.prompt


@pytest.mark.parametrize("owned,valid", [(True, True), (False, True), (True, False)])
def test_final_json_observation_never_asserts_host_acceptance(owned, valid):
    import json
    from tests.test_lifecycle_web_claude import SCHEMA, OUTPUT, _result
    api = module()
    observer = api.Diagnostics(SCHEMA, "owned-session", "private-token", final_json=True)
    event = observer.message(_result("owned-session" if owned else "other", num_turns=1,
        structured_output=None, result=json.dumps(OUTPUT) if valid else "not-json"))
    assert (event.get("native_output") == OUTPUT) is (owned and valid)
    if owned and valid:
        assert event["native_output_is_observation_not_host_acceptance"] is True
    elif owned:
        assert event["final_json_schema_valid"] is False and "not-json" not in str(event)


def test_amended_replay_requires_its_source_seal_before_credential_read(monkeypatch, tmp_path):
    api = module()
    def reject(*args):
        raise ValueError("offline_admitted_source_changed")
    monkeypatch.setattr(api.original, "require_sources", reject)
    monkeypatch.setattr(api.original, "selected_metadata", lambda *args: pytest.fail("credential_read_before_source_check"))
    with pytest.raises(ValueError, match="^offline_admitted_source_changed$"):
        asyncio.run(api.execute(tmp_path / "profile", tmp_path / "capture", tmp_path / "output", "0" * 64, tmp_path / "admission"))


@pytest.mark.parametrize("matching_receipts", [0, 2])
def test_live_replay_requires_unique_capture_receipt_before_credentials(monkeypatch, tmp_path, matching_receipts):
    import json
    api = module()
    admission = tmp_path / "admission"
    admission.mkdir()
    files = {"profile.sqlite": "fixture-digest"}
    receipt = {"files": files, "source_checkpoint": {"seal_sha256": "fixture-checkpoint"}}
    (admission / "verification.json").write_text(json.dumps({"analysis_capture_receipts": [receipt] * matching_receipts}))
    monkeypatch.setattr(api.original, "require_sources", lambda *args: {})
    monkeypatch.setattr(api, "snapshot", lambda *args: files)
    monkeypatch.setattr(api.original, "selected_metadata", lambda *args: pytest.fail("credential_read_before_unique_capture_binding"))
    with pytest.raises(ValueError, match="^original_capture_changed$"):
        asyncio.run(api.execute(tmp_path / "profile", tmp_path / "capture", tmp_path / "output", "0" * 64, admission))


def test_renewed_full_canary_spends_only_remaining_http_budget(monkeypatch, tmp_path):
    import renewed_full_canary as renewed
    from dataclasses import asdict
    baseline = renewed.original.options()
    monkeypatch.setattr(renewed.original, "options", renewed.original.options)
    monkeypatch.setattr(renewed.original, "CHECKPOINT", renewed.original.CHECKPOINT)
    monkeypatch.setattr(renewed.original, "prepared_plan", lambda *args: {
        "options": asdict(renewed.original.options()), "max_cli_internal_turns": {"search": 6, "analysis": 2}})
    renewed.configure(tmp_path / "admission")
    options = renewed.original.options()
    assert options.max_source_requests == 4
    assert {**asdict(options), "max_source_requests": baseline.max_source_requests} == asdict(baseline)
    plan = renewed.original.prepared_plan(None, "2026-09-07")
    assert plan["source_http_campaign_budget"] == {"limit": 8, "already_used": 4, "this_run_maximum": 4}
    assert plan["options"]["max_source_requests"] == 4
    assert plan["max_cli_tool_round_trips"] == {"search": 6, "analysis": 2}
    assert plan["max_reported_total_turns"] == {"search": 7, "analysis": 3}


@pytest.mark.parametrize("owned", [True, False])
def test_renewed_observer_keeps_native_result_distinct_from_host_acceptance(monkeypatch, tmp_path, owned):
    import claude_agent_sdk
    import json
    import renewed_full_canary as renewed
    from types import SimpleNamespace
    from tests.test_lifecycle_web_claude import SCHEMA, OUTPUT, _result
    work = tmp_path / "result"

    class Client:
        def __init__(self, *, options):
            self.options = options

        async def receive_response(self):
            yield _result(self.options.session_id if owned else "foreign-session", num_turns=3)

    monkeypatch.setattr(claude_agent_sdk, "ClaudeSDKClient", Client)
    monkeypatch.setattr(renewed, "configure", lambda *args: None)
    monkeypatch.setattr(sys, "argv", ["renewed", "--admission", str(tmp_path / "admission"), "--work", str(work)])

    def host_rejected():
        work.mkdir()
        async def observe():
            client = claude_agent_sdk.ClaudeSDKClient(options=SimpleNamespace(tools=[], session_id="owned-session",
                env={"CLAUDE_CODE_OAUTH_TOKEN": "fixture-private-token"}, output_format={"type": "json_schema", "schema": SCHEMA}))
            async for _ in client.receive_response():
                pass
        asyncio.run(observe())
        return 1
    monkeypatch.setattr(renewed.original, "main", host_rejected)
    assert renewed.main() == 1
    value = json.loads((work / "native-diagnostics.json").read_text())
    assert value["native_output_is_observation_not_host_acceptance"] is True
    result = next(event for event in value["events"] if event["kind"] == "result")
    assert result["session_matches_request"] is owned
    assert (result.get("native_output") == OUTPUT) is owned
    assert "fixture-private-token" not in str(value)
