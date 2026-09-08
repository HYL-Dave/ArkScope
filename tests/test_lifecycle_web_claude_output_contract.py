import json

import pytest

from src.auth_drivers.lifecycle_web_models import WebCredential, WebModelError
from src.auth_drivers.token_store import StoredTokenRecord
from src.security_lifecycle_web_contract import RunControl
from tests.test_lifecycle_web_claude import OUTPUT, SCHEMA, _request, _setup


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_claude_analysis_prompt_binds_exact_schema_without_repair_or_more_tools(monkeypatch):
    mod, clients = _setup(monkeypatch)
    request = _request(phase="analysis", call_id="analysis-1", prompt="Public evidence only; do not invoke any tool.")
    control = RunControl(selection=request.selection, max_model_requests=1)
    credential = WebCredential(request.selection, token_record=StoredTokenRecord("selected-token"))
    result = await mod.call_claude_web(request, credential, control)
    options = clients[0].options
    instructions, separator, schema = options.system_prompt.partition("\nOutput schema:\n")
    assert separator and json.loads(schema) == request.output_schema == SCHEMA
    assert options.output_format is None
    assert "final response" in instructions and "one JSON object" in instructions
    assert "Do not wrap the object in a function call" in instructions
    assert options.tools == [] and "WebSearch" in options.disallowed_tools
    assert options.max_turns == 2 and len(clients[0].queries) == control.model_requests == 1
    assert clients[0].queries[0][0] == request.prompt and result.output == OUTPUT


@pytest.mark.anyio
async def test_claude_search_keeps_its_existing_prompt_and_tool_budget(monkeypatch):
    mod, clients = _setup(monkeypatch)
    request = _request()
    control = RunControl(selection=request.selection, max_model_requests=1)
    credential = WebCredential(request.selection, token_record=StoredTokenRecord("selected-token"))
    await mod.call_claude_web(request, credential, control)
    options = clients[0].options
    assert options.system_prompt == "Investigate only the supplied public listing question. Return structured source candidates or findings. Do not perform unrelated tasks."
    assert options.tools == ["WebSearch"] and options.max_turns == request.max_search_uses + 2


@pytest.mark.anyio
@pytest.mark.parametrize("wrapped", [
    {"$FUNCTION_NAME": "StructuredOutput", "$PARAMETER_NAME": OUTPUT},
    {"result": OUTPUT},
])
async def test_claude_analysis_never_unwraps_invalid_provider_arguments(monkeypatch, wrapped):
    mod, clients = _setup(monkeypatch, result={"result": json.dumps(wrapped)})
    request = _request(phase="analysis", call_id="analysis-1")
    control = RunControl(selection=request.selection, max_model_requests=1)
    credential = WebCredential(request.selection, token_record=StoredTokenRecord("selected-token"))
    with pytest.raises(WebModelError, match="^model_output_invalid$"):
        await mod.call_claude_web(request, credential, control)
    assert len(clients[0].queries) == control.model_requests == 1
    assert control.terminal_statuses == {"analysis-1": "completed"}
    assert clients[0].closed and clients[0].options.fallback_model is None
