"""Four real Research dispatch boundaries over disposable SEC acquisition."""

import asyncio
import json
from pathlib import Path

import pytest

from src.tools.registry import ToolRegistry
from tests.test_sec_research_tool_service import (
    CIK, EXACT, FACTS, SUBMISSIONS, doc_tool, document_rig, tool_fixture as service_fixture,
)

NAMES = ("list_sec_filings", "get_sec_financial_facts", "read_sec_filing")
CHANNELS = ("openai", "anthropic", "chatgpt", "claude")


@pytest.fixture
def tool_fixture(tmp_path):
    return service_fixture.__wrapped__(tmp_path / "tools")


@pytest.fixture
def registry():
    result = ToolRegistry()
    result.register_all()
    return result


def unwrap(payload):
    if payload.startswith('<tool_output tool="'):
        payload = payload.split("\n", 1)[1].rsplit("\n</tool_output>", 1)[0]
    return json.loads(payload)


async def dispatch(channel, registry, name, arguments, *, timeout=5, token=None):
    if channel == "openai":
        from agents.tool_context import ToolContext
        from src.agents.openai_agent.tools import create_openai_tools
        tools = {t.name.removeprefix("tool_"): t for t in create_openai_tools(None)}
        assert name in tools, f"OpenAI inventory missing {name}"
        payload = json.dumps(arguments)
        context = ToolContext(context=None, tool_name=tools[name].name,
                              tool_call_id="offline-sec", tool_arguments=payload)
        return await tools[name].on_invoke_tool(context, payload)
    if channel == "anthropic":
        from src.agents.anthropic_agent.tools import execute_tool, get_anthropic_tools
        assert name in {t["name"] for t in get_anthropic_tools()}, f"Anthropic inventory missing {name}"
        return await asyncio.to_thread(execute_tool, name, arguments, None)
    if channel == "chatgpt":
        from src.auth_drivers.chatgpt_oauth_driver import OpenAIChatGPTOAuthDriver
        driver = OpenAIChatGPTOAuthDriver(registry=registry, per_tool_timeout_s=timeout)
        ok, result = await driver._invoke_tool(name=name, args=arguments, token=token)
        assert ok, result
        return result
    from src.auth_drivers.claude_code_sdk_driver import _invoke_bridged_tool
    result = await _invoke_bridged_tool(name=name, args=arguments, registry=registry,
        dal=None, token=token, per_tool_timeout_s=timeout)
    assert not result["is_error"], result
    return result["content"][0]["text"]


def wire(monkeypatch, service):
    from src.sec_research import runtime
    from src.tools import sec_research_tools
    monkeypatch.setattr(runtime, "build_tool_service", lambda: service)
    monkeypatch.setattr(sec_research_tools, "build_tool_service", lambda: service)


@pytest.mark.parametrize("channel", CHANNELS)
def test_each_research_transport_dispatches_three_real_sec_tools(
        channel, registry, tool_fixture, document_rig, monkeypatch):
    f = tool_fixture
    assert set(NAMES) <= set(registry.list_names())
    assert "get_sec_filings" not in registry.list_names()
    for name in NAMES:
        assert registry.get(name).category == "analysis"
        assert registry.get(name).requires_dal is False
    wire(monkeypatch, f.service)
    filings = unwrap(asyncio.run(dispatch(channel, registry, NAMES[0], dict(issuer=CIK))))
    assert len(filings["data"]) == 2
    assert filings["data"][0]["sources"][0]["object_sha256"]
    facts = unwrap(asyncio.run(dispatch(channel, registry, NAMES[1], dict(issuer=CIK))))
    assert facts["data"][0]["value"] == "1234567890123456789.123"
    assert facts["data"][0]["source"]["sha256"]
    assert f.transport.calls == [SUBMISSIONS, FACTS]
    r = document_rig
    service, acquisitions = doc_tool(r)
    wire(monkeypatch, service)
    r.enqueue(b"<p>Complete SEC passage.</p>")
    from tests.test_sec_research_document_service import FILING_ID
    index = unwrap(asyncio.run(dispatch(channel, registry, NAMES[2], dict(filing_id=FILING_ID))))
    args = dict(filing_id=FILING_ID, cursor=index["data"]["text_start_cursor"])
    text = unwrap(asyncio.run(dispatch(channel, registry, NAMES[2], args)))
    passage = text["data"]["passages"][0]
    assert passage["text"] == "Complete SEC passage."
    assert passage["citation"]["end_byte"] == len(passage["text"].encode())
    assert len(acquisitions) == 1


def test_old_catalog_tool_absent_from_all_current_skills():
    paths = list(Path("resources/skills").rglob("SKILL.md"))
    assert paths
    assert not [str(p) for p in paths if "get_sec_filings" in p.read_text()]


@pytest.mark.parametrize("channel", ("openai", "anthropic"))
def test_required_sec_omission_is_explicit(channel):
    from src.agents.shared.subagent import _filter_anthropic_tools, _filter_openai_tools
    filter_tools = _filter_openai_tools if channel == "openai" else _filter_anthropic_tools
    with pytest.raises(ValueError, match="required.*SEC|SEC.*required"):
        filter_tools([], ["list_sec_filings"])


@pytest.mark.parametrize("channel", ("openai", "anthropic"))
def test_non_sec_optional_omission_keeps_existing_semantics(channel):
    from src.agents.shared.subagent import _filter_anthropic_tools, _filter_openai_tools
    filter_tools = _filter_openai_tools if channel == "openai" else _filter_anthropic_tools
    assert filter_tools([], ["web_browse"]) == []


@pytest.mark.parametrize("channel", ("chatgpt", "claude"))
@pytest.mark.parametrize("missing", NAMES)
def test_oauth_inventory_requires_every_sec_tool(channel, missing, registry):
    from src.auth_drivers.chatgpt_oauth_driver import OpenAIChatGPTOAuthDriver
    from src.auth_drivers.claude_code_sdk_driver import build_ark_mcp_server
    registry._tools.pop(missing)
    with pytest.raises((ValueError, RuntimeError), match=missing):
        if channel == "chatgpt":
            OpenAIChatGPTOAuthDriver(registry=registry)._build_tools()
        else:
            build_ark_mcp_server(registry=registry, dal=None, token=None)


def test_chatgpt_absent_registry_is_intentionally_tool_free():
    from src.auth_drivers.chatgpt_oauth_driver import OpenAIChatGPTOAuthDriver
    assert OpenAIChatGPTOAuthDriver()._build_tools() == []


def test_chatgpt_optional_non_sec_inventory_omission_remains_optional(registry):
    from src.auth_drivers.chatgpt_oauth_driver import OpenAIChatGPTOAuthDriver
    registry._tools.pop("get_insider_trades")
    names = {t["name"] for t in OpenAIChatGPTOAuthDriver(registry=registry)._build_tools()}
    assert set(NAMES) <= names
    assert "get_insider_trades" not in names


@pytest.mark.parametrize("channel", CHANNELS)
def test_sec_transport_schemas_keep_exact_parameters_and_array_items(channel, registry):
    import inspect
    from src.tools import sec_research_tools
    if channel == "openai":
        from src.agents.openai_agent.tools import create_openai_tools
        schemas = {t.name.removeprefix("tool_"): t.params_json_schema for t in create_openai_tools(None)}
    elif channel == "anthropic":
        from src.agents.anthropic_agent.tools import get_anthropic_tools
        schemas = {t["name"]: t["input_schema"] for t in get_anthropic_tools()}
    elif channel == "chatgpt":
        from src.auth_drivers.chatgpt_oauth_driver import OpenAIChatGPTOAuthDriver
        schemas = {t["name"]: t["parameters"] for t in OpenAIChatGPTOAuthDriver(registry=registry)._build_tools()}
    else:
        from src.auth_drivers.claude_code_sdk_driver import _ark_input_schema
        schemas = {n: _ark_input_schema(registry.get(n)) for n in NAMES}
    for name in NAMES:
        assert set(schemas[name]["properties"]) == set(inspect.signature(getattr(sec_research_tools, name)).parameters)
        for field in ("forms", "metrics", "concepts", "fact_ids"):
            if field in schemas[name]["properties"]:
                prop = schemas[name]["properties"][field]
                array = next((p for p in prop.get("anyOf", [prop]) if p.get("type") == "array"), None)
                assert array["items"] == {"type": "string"}


@pytest.mark.parametrize("channel", CHANNELS)
@pytest.mark.parametrize("name", NAMES)
def test_each_transport_dispatches_closed_invalid_sec_query(channel, name, registry, tool_fixture, monkeypatch):
    f = tool_fixture
    wire(monkeypatch, f.service)
    def forbidden(*args, **kwargs):
        pytest.fail("invalid SEC arguments reached storage")
    monkeypatch.setattr(f.store, "connect", forbidden)
    arguments = dict(filing_id="invalid") if name == "read_sec_filing" else dict(issuer="CIK:bad")
    result = unwrap(asyncio.run(dispatch(channel, registry, name, arguments)))
    assert result["status"] == "unavailable"
    assert result["gaps"][0]["code"] in {"sec_research_query_invalid", "sec_issuer_invalid"}
    assert result["data"] == [] and not f.transport.calls


@pytest.mark.parametrize("channel", ["chatgpt", "claude"])
def test_oauth_sec_boundary_rejects_serialization_corruption(channel, registry, tool_fixture, monkeypatch):
    # The service remains real. Corrupt only the final bridge serialization to
    # prove the defensive reducer is selected even if an upstream boundary fails.
    import src.sec_research.tool_execution
    from src.sec_research.tool_results import SEC_RESULT_POLICY
    from src.tools import result_policy
    wire(monkeypatch, tool_fixture.service)
    original = result_policy.admit_tool_result
    def corrupt_success(result, *, policy, **kwargs):
        if policy == SEC_RESULT_POLICY and result["status"] == "ok":
            return '{"broken":'
        return original(result, policy=policy, **kwargs)
    monkeypatch.setattr(result_policy, "admit_tool_result", corrupt_success)
    result = unwrap(asyncio.run(dispatch(channel, registry, "list_sec_filings", dict(issuer=CIK))))
    assert result["status"] == "unavailable"
    assert result["gaps"] == [{"code": "sec_result_invalid"}]


@pytest.mark.parametrize("channel", CHANNELS)
def test_sec_worker_preserves_permission_rejection_before_acquisition(channel, registry, tool_fixture, monkeypatch):
    from src.api import permissions
    wire(monkeypatch, tool_fixture.service)
    def reject(*args, **kwargs):
        raise RuntimeError("PRIVATE sk-never-show-this-provider-error")
    monkeypatch.setattr(permissions, "require_db_write", reject)
    result = asyncio.run(dispatch(channel, registry, "list_sec_filings", dict(issuer=CIK)))
    assert unwrap(result)["status"] == "unavailable"
    assert "PRIVATE" not in result and "never-show" not in result
    assert not tool_fixture.acquisitions and not tool_fixture.transport.calls


def test_current_sec_skills_require_three_registered_tools(registry):
    from src.agents.shared.skills import _parse_skill_md
    paths = [
        "builtin/full-analysis", "builtin/earnings-prep", "financial-analysis/dcf-model",
        "financial-analysis/competitive-analysis", "financial-analysis/comps-analysis",
        "equity-research/earnings-analysis", "equity-research/catalyst-calendar",
    ]
    for path in paths:
        skill = _parse_skill_md(Path("resources/skills") / path / "SKILL.md")
        assert set(NAMES) <= set(skill.data_sources["required"]) <= set(registry.list_names())
