from dataclasses import replace

import pytest

from src.auth_drivers.lifecycle_web_models import ModelCall, ModelReply, WebCredential, WebModelError
from src.auth_drivers.token_store import StoredTokenRecord
from src.security_lifecycle_web_contract import ExecutionSelection, RunControl, validate_selection


@pytest.fixture
def anyio_backend():
    return "asyncio"


CHANNELS = [("openai", "api_key", "lifecycle_web_models", "call_openai_web"),
            ("openai", "chatgpt_oauth", "lifecycle_web_codex", "call_codex_web"),
            ("anthropic", "api_key", "lifecycle_web_models", "call_anthropic_web"),
            ("anthropic", "claude_code_oauth", "lifecycle_web_claude", "call_claude_web")]


@pytest.mark.anyio
@pytest.mark.parametrize("provider,auth,module,function", CHANNELS)
@pytest.mark.parametrize("fail", [False, True])
async def test_four_channel_dispatch_never_changes_selected_transport(monkeypatch, provider, auth, module, function, fail):
    import importlib
    from src.auth_drivers.lifecycle_web_dispatch import call_lifecycle_web_model

    called = []
    selection = validate_selection(provider, auth, "gpt-5.6-luna" if provider == "openai" else "claude-opus-5", "local:7")
    call = ModelCall(selection, "call-1", "search", "public question", {"type": "object", "properties": {}, "additionalProperties": False},
                     "high", 4096 if auth == "api_key" else None, 1, 3)
    control = RunControl(selection=selection, max_model_requests=1)
    credential = WebCredential(selection, api_key="selected-key") if auth == "api_key" else WebCredential(selection, token_record=StoredTokenRecord("selected-token"))

    def function_for(name):
        async def adapter(actual_call, actual_credential, actual_control):
            called.append(name)
            assert (actual_call, actual_credential, actual_control) == (call, credential, control)
            if fail:
                raise WebModelError("provider_rate_limited")
            return ModelReply("remote-1", {}, {"input_tokens": 1, "output_tokens": 2})
        return adapter

    for _, _, other_module, other_function in CHANNELS:
        monkeypatch.setattr(importlib.import_module(f"src.auth_drivers.{other_module}"), other_function, function_for(other_function))
    if fail:
        with pytest.raises(WebModelError, match="provider_rate_limited"):
            await call_lifecycle_web_model(call, credential, control)
    else:
        assert (await call_lifecycle_web_model(call, credential, control)).output == {}
    assert called == [function]


@pytest.mark.anyio
async def test_unknown_auth_dispatch_has_no_api_default():
    from src.auth_drivers.lifecycle_web_dispatch import call_lifecycle_web_model
    from src.security_lifecycle_web_contract import WebContractError

    selection = validate_selection("openai", "api_key", "gpt-5.6-luna", "local:7")
    call = ModelCall(selection, "call-1", "analysis", "public question", {"type": "object"}, "high", 4096, 1, 3)
    object.__setattr__(call, "selection", ExecutionSelection("openai", "unknown", "gpt-5.6-luna", "local:7"))
    with pytest.raises(WebContractError, match="web_auth_unsupported"):
        await call_lifecycle_web_model(call, WebCredential(selection, api_key="selected-key"), RunControl(selection=selection, max_model_requests=1))
