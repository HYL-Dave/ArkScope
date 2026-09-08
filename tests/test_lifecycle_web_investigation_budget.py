from dataclasses import replace

import pytest

from tests.test_lifecycle_web_preflight import setup
from tests.test_lifecycle_web_review import context
from tests.test_security_lifecycle_web_finding import public_input


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.parametrize("provider,auth", [("openai", "api_key"), ("openai", "chatgpt_oauth"),
                                          ("anthropic", "api_key"), ("anthropic", "claude_code_oauth")])
def test_only_claude_oauth_gets_the_larger_preflight_and_execution_budget(tmp_path, monkeypatch, provider, auth):
    c = context(tmp_path)
    service, _, _ = setup(c, provider=provider, auth=auth)
    monkeypatch.setattr(service, "_public_input", lambda *args, **kwargs: public_input())
    packet = service.prepare(c["case_id"], question="listing_status")
    values = service.validate_start(c["case_id"], question="listing_status", preflight_sha256=packet["preflight_sha256"])
    expanded = auth == "claude_code_oauth"
    expected = {"search_uses": 12 if expanded else 4, "sources": 8 if expanded else 4,
                "source_requests": 24 if expanded else 8, "model_timeout_seconds": 600 if expanded else 180}
    assert {key: packet["limits"][key] for key in expected} == expected
    options = values["options"]
    assert (options.max_search_uses, options.max_sources, options.max_source_requests, options.model_timeout_seconds) == tuple(expected.values())
    assert packet["limits"]["model_submissions"] == 2
    assert options.source_timeout_seconds == 180 and options.max_redirects == 2
    assert options.max_source_bytes == 32 * 1024**2 and options.max_decoded_source_bytes == 128 * 1024**2
    assert options.output_token_limit == (16384 if auth == "api_key" else None)


@pytest.mark.parametrize("field", ["max_search_uses", "max_sources", "max_source_requests", "model_timeout_seconds"])
def test_expanded_budget_cannot_change_after_the_user_confirms_preflight(tmp_path, monkeypatch, field):
    from src import lifecycle_web_preflight as mod

    c = context(tmp_path)
    service, _, _ = setup(c, provider="anthropic", auth="claude_code_oauth")
    monkeypatch.setattr(service, "_public_input", lambda *args, **kwargs: public_input())
    packet = service.prepare(c["case_id"], question="listing_status")
    original = mod.default_investigation_options

    def changed(*args, **kwargs):
        options = original(*args, **kwargs)
        return replace(options, **{field: getattr(options, field) + 1})

    monkeypatch.setattr(mod, "default_investigation_options", changed)
    with pytest.raises(ValueError, match="^web_preflight_changed$"):
        service.validate_start(c["case_id"], question="listing_status", preflight_sha256=packet["preflight_sha256"])


@pytest.mark.anyio
async def test_expanded_claude_search_allows_twelve_and_denies_the_thirteenth_before_execution():
    from src.auth_drivers.lifecycle_web_claude import WebToolGate, _tool_round_trip_limit
    from src.auth_drivers.lifecycle_web_models import ModelCall
    from src.security_lifecycle_web_contract import RunControl, validate_selection

    selected = validate_selection("anthropic", "claude_code_oauth", "claude-sonnet-5", "local:7")
    control = RunControl(selection=selected, max_model_requests=2)
    call = ModelCall(selected, "search-1", "search", "Investigate this exact security.", {"type": "object"},
        "medium", None, 12, 600)
    gate = WebToolGate(call, control, "owned-session")
    assert _tool_round_trip_limit(call) == 14
    for index in range(1, 14):
        identity = "query-" + str(index)
        result = await gate.pre_tool({"hook_event_name": "PreToolUse", "session_id": "owned-session",
            "tool_use_id": identity, "tool_name": "WebSearch", "tool_input": {"query": "public listing " + str(index)}}, identity, {})
        assert result["hookSpecificOutput"]["permissionDecision"] == ("allow" if index <= 12 else "deny")
    assert len(gate.search_reservations) == 12 and gate.failure == "search_budget_exhausted"
    assert control.stop_state != "running" and control.model_requests == 0
