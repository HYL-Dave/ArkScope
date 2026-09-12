"""SEC registration shares the reviewed output policy across all transports."""

import asyncio
import json

import pytest

from tests.test_sec_research_tool_adapters import CHANNELS, NAMES, dispatch, registry, wire
from tests.test_sec_research_tool_service import CIK, doc_tool, document_rig, seed, tool_fixture


@pytest.mark.parametrize("name", NAMES)
def test_sec_registration_uses_closed_common_policy(name, registry):
    from src.agents.shared.output_boundary import OutputBoundaryError
    from src.tools.result_policy import admit_tool_result

    policy = registry.get(name).result_policy
    assert policy is not None, "SEC tool is missing its common output policy"
    assert callable(policy.validator), "SEC envelope must be closed, not arbitrary JSON"
    envelope = dict(status="empty", data=[], gaps=[], observed_at=None,
                    coverage={}, next_cursor=None)
    assert json.loads(admit_tool_result(envelope, policy=policy)) == envelope
    with pytest.raises(OutputBoundaryError, match="invalid_value"):
        admit_tool_result(dict(envelope, unreviewed_field=True), policy=policy)


@pytest.mark.parametrize("name", NAMES[:2])
def test_four_sec_transports_return_identical_canonical_bytes(name, registry, tool_fixture, monkeypatch):
    seed(tool_fixture)
    wire(monkeypatch, tool_fixture.service)
    results = [asyncio.run(dispatch(channel, registry, name,
               dict(issuer=CIK, freshness="stored"))) for channel in CHANNELS]
    assert len(set(results)) == 1
    assert "[REDACTED]" not in results[0]
    assert "unavailable" not in json.loads(results[0].split("\n", 1)[1].rsplit("\n", 1)[0])["status"]


def test_four_sec_transports_return_identical_document_citations(registry, document_rig, monkeypatch):
    from tests.test_sec_research_document_service import FILING_ID

    service, _ = doc_tool(document_rig)
    wire(monkeypatch, service)
    document_rig.enqueue("<p>Consolidated 391035000000 \u4e2d\u6587.</p>".encode())
    index = service.invoke("read_sec_filing", dict(filing_id=FILING_ID))
    arguments = dict(filing_id=FILING_ID, freshness="stored",
                     cursor=index["data"]["text_start_cursor"])
    results = [asyncio.run(dispatch(channel, registry, "read_sec_filing", arguments))
               for channel in CHANNELS]
    assert len(set(results)) == 1
    assert "Consolidated 391035000000 \u4e2d\u6587." in results[0]


@pytest.mark.parametrize("channel", ["chatgpt", "claude"])
def test_oauth_sec_timeout_returns_closed_result_after_owned_worker_stops(
        channel, registry, tool_fixture, monkeypatch):
    import threading
    import time
    from tests.test_sec_research_tool_adapters import unwrap

    f = tool_fixture
    wire(monkeypatch, f.service)
    stopped, finished = threading.Event(), threading.Event()
    original = f.transport.get

    def read(*args, **kwargs):
        assert stopped.wait(3), "timeout did not stop the SEC transport"
        time.sleep(0.03)
        try:
            return original(*args, **kwargs)
        finally:
            finished.set()

    monkeypatch.setattr(f.transport, "get", read)
    monkeypatch.setattr(f.transport, "close", stopped.set, raising=False)
    result = asyncio.run(dispatch(channel, registry, "list_sec_filings",
                                  dict(issuer=CIK), timeout=0.15))
    assert finished.is_set(), "OAuth returned while SEC acquisition was still running"
    assert unwrap(result)["gaps"] == [{"code": "sec_result_timeout"}]


@pytest.mark.parametrize("fails", [False, True], ids=["result", "sanitized-error"])
def test_openai_wrapper_awaits_async_handler_inside_error_boundary(fails):
    from agents.tool_context import ToolContext
    from src.agents.openai_agent.tools import function_tool

    finished = []

    @function_tool
    async def fixture_async_tool() -> str:
        await asyncio.sleep(0)
        finished.append(True)
        if fails:
            raise RuntimeError("Authorization: Bearer sk-proj-SyntheticSecret01234567890123456789")
        return "Consolidated Statements of Comprehensive Income"

    context = ToolContext(context=None, tool_name="fixture_async_tool",
                          tool_call_id="offline-async", tool_arguments="{}")
    result = asyncio.run(fixture_async_tool.on_invoke_tool(context, "{}"))
    assert isinstance(result, str), "async tool was returned without being awaited"
    assert finished == [True]
    if fails:
        assert "SyntheticSecret" not in result
    else:
        assert result == "Consolidated Statements of Comprehensive Income"
