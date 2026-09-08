from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.auth_drivers.lifecycle_web_models import WebCredential, WebModelError
from src.auth_drivers.token_store import StoredTokenRecord
from src.security_lifecycle_web_contract import RunControl
from tests.test_lifecycle_web_claude import _request, _setup


@pytest.fixture
def anyio_backend():
    return "asyncio"


MODEL_COUNTS = {
    "inputTokens": 29706, "outputTokens": 3228,
    "cacheCreationInputTokens": 3976, "cacheReadInputTokens": 3354,
    "webSearchRequests": 2,
}


@pytest.mark.anyio
async def test_claude_web_uses_reported_model_totals_not_main_loop_or_sum_of_scopes(monkeypatch):
    mod, clients = _setup(monkeypatch, result={
        "num_turns": 4, "usage": {"input_tokens": 4, "output_tokens": 1036},
        "model_usage": {"claude-opus-5": MODEL_COUNTS},
    })
    call = _request(max_search_uses=4)
    control = RunControl(selection=call.selection, max_model_requests=2)
    reply = await mod.call_claude_web(call, WebCredential(call.selection, token_record=StoredTokenRecord("synthetic")), control)
    assert reply.usage == {"input_tokens": 29706, "output_tokens": 3228}
    assert reply.usage_observation == {
        "basis": "claude_model_usage",
        "values": {"input_tokens": 29706, "output_tokens": 3228, "cache_creation_input_tokens": 3976,
                   "cache_read_input_tokens": 3354, "web_search_requests": 2},
        "main_loop": {"input_tokens": 4, "output_tokens": 1036, "cache_creation_input_tokens": None,
                      "cache_read_input_tokens": None, "web_search_requests": None},
    }
    assert len(clients) == 1 and len(clients[0].queries) == 1 and control.all_requests_terminal


@pytest.mark.anyio
@pytest.mark.parametrize("aggregate", [None, {}, {"claude-opus-5": {}}])
async def test_missing_model_aggregate_does_not_fall_back_to_main_loop_usage(monkeypatch, aggregate):
    mod, clients = _setup(monkeypatch, result={"model_usage": aggregate})
    call = _request()
    control = RunControl(selection=call.selection, max_model_requests=2)
    reply = await mod.call_claude_web(call, WebCredential(call.selection, token_record=StoredTokenRecord("synthetic")), control)
    assert reply.usage == {"input_tokens": None, "output_tokens": None}
    assert reply.usage_observation["main_loop"]["input_tokens"] == 100
    assert clients[0].closed and control.all_requests_terminal


@pytest.mark.anyio
@pytest.mark.parametrize("value", [True, "10", -1, 1.5, 2**53, []])
async def test_malformed_reported_model_counter_is_not_silently_unknown(monkeypatch, value):
    mod, clients = _setup(monkeypatch, result={"model_usage": {"claude-opus-5": {**MODEL_COUNTS, "inputTokens": value}}})
    call = _request()
    control = RunControl(selection=call.selection, max_model_requests=2)
    with pytest.raises(WebModelError, match="^model_usage_invalid$"):
        await mod.call_claude_web(call, WebCredential(call.selection, token_record=StoredTokenRecord("synthetic")), control)
    assert control.terminal_statuses == {"search-1": "completed"}
    assert clients[0].closed and len(clients[0].queries) == 1


@pytest.mark.anyio
async def test_reported_zero_is_not_replaced_by_nonzero_main_loop(monkeypatch):
    mod, _ = _setup(monkeypatch, result={"model_usage": {"claude-opus-5": dict.fromkeys(MODEL_COUNTS, 0)}})
    call = _request()
    control = RunControl(selection=call.selection, max_model_requests=2)
    reply = await mod.call_claude_web(call, WebCredential(call.selection, token_record=StoredTokenRecord("synthetic")), control)
    assert reply.usage == {"input_tokens": 0, "output_tokens": 0}


@pytest.mark.anyio
async def test_other_model_usage_still_refuses_before_accepting_counters(monkeypatch):
    mod, clients = _setup(monkeypatch, result={"model_usage": {"claude-haiku-4-5-20251001": MODEL_COUNTS}})
    call = _request()
    control = RunControl(selection=call.selection, max_model_requests=2)
    with pytest.raises(WebModelError, match="^execution_identity_changed$"):
        await mod.call_claude_web(call, WebCredential(call.selection, token_record=StoredTokenRecord("synthetic")), control)
    assert control.all_requests_terminal and len(clients[0].queries) == 1


@pytest.mark.anyio
async def test_sonnet_live_counter_shape_replays_through_actual_sdk_parser_without_dispatch(monkeypatch):
    from claude_agent_sdk import ClaudeSDKClient
    from src.auth_drivers import lifecycle_web_claude as mod
    from src.security_lifecycle_web_contract import validate_selection
    from tests.test_lifecycle_web_claude_wire import Peer

    class UsagePeer(Peer):
        async def read_messages(self):
            async for message in super().read_messages():
                if message["type"] == "result":
                    message.update(num_turns=4, usage={"input_tokens": 4, "output_tokens": 1036},
                                   modelUsage={"claude-sonnet-5": {**MODEL_COUNTS, "costUSD": 0.123}})
                yield message

    peers = []
    def client(options):
        peer = UsagePeer(options, False)
        peers.append(peer)
        return ClaudeSDKClient(options=options, transport=peer)
    monkeypatch.setattr(mod, "_client", client)
    monkeypatch.setattr(mod, "require_reviewed_claude_agent_runtime", lambda: SimpleNamespace(cli_path=Path("/reviewed/bundled/claude")))
    call = replace(_request(max_search_uses=4), selection=validate_selection("anthropic", "claude_code_oauth", "claude-sonnet-5", "local:7"))
    control = RunControl(selection=call.selection, max_model_requests=2)
    reply = await mod.call_claude_web(call, WebCredential(call.selection, token_record=StoredTokenRecord("synthetic")), control)
    assert reply.usage == {"input_tokens": 29706, "output_tokens": 3228}
    assert reply.usage_observation["main_loop"]["input_tokens"] == 4
    assert reply.usage_observation["values"]["cache_creation_input_tokens"] == 3976
    assert reply.usage_observation["values"]["web_search_requests"] == 2
    assert "costUSD" not in str(reply.usage_observation)
    assert control.model_requests == 1 and control.all_requests_terminal
    assert len(peers) == 1 and peers[0].closed
    assert len([wire for wire in peers[0].writes if wire["type"] == "user"]) == 1


@pytest.mark.anyio
@pytest.mark.parametrize("counter", ["inputTokens", "outputTokens", "cacheCreationInputTokens", "cacheReadInputTokens", "webSearchRequests"])
async def test_each_missing_aggregate_field_remains_unknown_without_hiding_other_fields(monkeypatch, counter):
    from src.auth_drivers.lifecycle_web_usage import COUNTER_FIELDS

    values = {**MODEL_COUNTS}
    del values[counter]
    mod, _ = _setup(monkeypatch, result={"model_usage": {"claude-opus-5": values}})
    call = _request()
    control = RunControl(selection=call.selection, max_model_requests=2)
    reply = await mod.call_claude_web(call, WebCredential(call.selection, token_record=StoredTokenRecord("synthetic")), control)
    assert reply.usage_observation["values"] == {field: values.get(key) for field, key in zip(COUNTER_FIELDS, MODEL_COUNTS)}


def test_model_rows_sum_only_equal_scopes_and_missing_row_is_not_zero():
    from src.auth_drivers.lifecycle_web_usage import claude_usage_observation

    message = SimpleNamespace(usage={"input_tokens": 999, "output_tokens": 888}, model_usage={
        "claude-opus-5": {"inputTokens": 10, "outputTokens": 20},
        "CLAUDE-OPUS-5": {"inputTokens": 5},
    })
    result = claude_usage_observation(message, "claude-opus-5")
    assert result["values"]["input_tokens"] == 15 and result["values"]["output_tokens"] is None
    message.model_usage["CLAUDE-OPUS-5"]["inputTokens"] = 2**53 - 1
    with pytest.raises(WebModelError, match="^model_usage_invalid$"):
        claude_usage_observation(message, "claude-opus-5")


@pytest.mark.parametrize("main_loop", [False, [], 0, {"input_tokens": "4"}, {"output_tokens": -1}])
def test_present_malformed_main_loop_is_not_silently_dropped(main_loop):
    from src.auth_drivers.lifecycle_web_usage import claude_usage_observation

    with pytest.raises(WebModelError, match="^model_usage_invalid$"):
        claude_usage_observation(SimpleNamespace(usage=main_loop, model_usage={"claude-opus-5": MODEL_COUNTS}), "claude-opus-5")
