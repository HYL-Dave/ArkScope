import pytest

from src.auth_drivers.lifecycle_web_models import WebCredential, WebModelError
from src.auth_drivers.token_store import StoredTokenRecord
from src.security_lifecycle_web_contract import RunControl
from tests.test_lifecycle_web_claude import OUTPUT, _request, _setup


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("phase,tool_budget", [("analysis", 2), ("search", 4)])
async def test_claude_completed_result_includes_final_turn_after_tool_budget(monkeypatch, phase, tool_budget):
    mod, clients = _setup(monkeypatch, result={"num_turns": tool_budget + 1})
    request = _request(phase=phase, call_id=phase + "-1")
    control = RunControl(selection=request.selection, max_model_requests=1)
    credential = WebCredential(request.selection, token_record=StoredTokenRecord("selected-token"))
    assert (await mod.call_claude_web(request, credential, control)).output == OUTPUT
    assert clients[0].options.max_turns == tool_budget
    assert control.terminal_statuses == {request.call_id: "completed"}
    assert len(clients[0].queries) == control.model_requests == 1 and clients[0].closed


@pytest.mark.anyio
@pytest.mark.parametrize("phase,bad_turns", [("analysis", 4), ("search", 6), ("analysis", True), ("analysis", "3"), ("analysis", 0)])
async def test_claude_terminal_allowance_does_not_accept_extra_or_malformed_turns(monkeypatch, phase, bad_turns):
    mod, clients = _setup(monkeypatch, result={"num_turns": bad_turns})
    request = _request(phase=phase, call_id=phase + "-1")
    control = RunControl(selection=request.selection, max_model_requests=1)
    credential = WebCredential(request.selection, token_record=StoredTokenRecord("selected-token"))
    with pytest.raises(WebModelError, match="^model_result_incomplete$"):
        await mod.call_claude_web(request, credential, control)
    assert control.terminal_statuses == {request.call_id: "completed"}
    assert len(clients[0].queries) == 1 and clients[0].closed


@pytest.mark.anyio
async def test_claude_max_turns_error_is_not_rescued_by_terminal_allowance(monkeypatch):
    mod, clients = _setup(monkeypatch, result={"num_turns": 3, "subtype": "error_max_turns", "terminal_reason": "max_turns", "is_error": True})
    request = _request(phase="analysis", call_id="analysis-1")
    control = RunControl(selection=request.selection, max_model_requests=1)
    credential = WebCredential(request.selection, token_record=StoredTokenRecord("selected-token"))
    with pytest.raises(WebModelError, match="^model_result_incomplete$"):
        await mod.call_claude_web(request, credential, control)
    assert control.terminal_statuses == {request.call_id: "failed"}
    assert len(clients[0].queries) == 1 and clients[0].closed
