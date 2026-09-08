import importlib
import json

import httpx
import pytest

from src.auth_drivers.lifecycle_web_models import ModelCall, WebCredential
from src.security_lifecycle_web_contract import RunControl, validate_selection


@pytest.fixture
def anyio_backend():
    return "asyncio"


SCHEMA = {"type": "object", "properties": {"sources": {"type": "array", "items": {"type": "string"}}},
          "required": ["sources"], "additionalProperties": False}
OUTPUT = {"sources": ["https://ir.example.com/notice"]}


@pytest.mark.anyio
@pytest.mark.parametrize("provider", ["openai", "anthropic"])
async def test_real_api_sdk_serialization_keeps_selected_key_and_basic_search(monkeypatch, provider):
    from src.auth_drivers import lifecycle_web_models as mod
    from openai import AsyncOpenAI
    from anthropic import AsyncAnthropic, DefaultAsyncHttpxClient

    # Use the HTTP types required by the installed SDK, not a lookalike client.
    http_module = (httpx if provider == "openai" else importlib.import_module(next(
        base.__module__.split(".")[0] for base in DefaultAsyncHttpxClient.__mro__ if base.__name__ == "AsyncClient")))

    model = "gpt-5.6-luna" if provider == "openai" else "claude-opus-5"
    selection = validate_selection(provider, "api_key", model, "local:7")
    call = ModelCall(selection, "search-1", "search", "Public issuer question", SCHEMA, "high", 4096, 2, 5)
    control = RunControl(selection=selection, max_model_requests=1)
    requests = []
    monkeypatch.setenv("OPENAI_CUSTOM_HEADERS", "Authorization: Bearer ambient-openai\nX-Private: ambient-value")
    monkeypatch.setenv("ANTHROPIC_CUSTOM_HEADERS", "X-Api-Key: ambient-key\nAuthorization: Bearer ambient-bearer\nX-Private: ambient-value")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "ambient-bearer")

    def respond(request):
        requests.append(request)
        if provider == "openai":
            payload = {"id": "resp-1", "created_at": 1, "object": "response", "model": model, "status": "completed",
                       "output": [{"type": "web_search_call", "id": "web-1", "status": "completed", "action": {"type": "search", "query": "Issuer Old Inc"}},
                                  {"type": "message", "id": "message-1", "role": "assistant", "status": "completed",
                                   "content": [{"type": "output_text", "text": json.dumps(OUTPUT), "annotations": []}]}],
                       "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30,
                                 "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}}}
        else:
            payload = {"id": "msg-1", "type": "message", "role": "assistant", "model": model,
                       "stop_reason": "tool_use", "stop_sequence": None,
                       "content": [{"type": "server_tool_use", "id": "web-1", "name": "web_search", "input": {"query": "Issuer Old Inc"}},
                                   {"type": "web_search_tool_result", "tool_use_id": "web-1", "content": []},
                                   {"type": "tool_use", "id": "emit-1", "name": "emit_lifecycle_result", "input": OUTPUT}],
                       "usage": {"input_tokens": 10, "output_tokens": 20}}
        return http_module.Response(200, json=payload)

    real_factory = getattr(mod, f"_{provider}_client")

    def factory(**kwargs):
        client = http_module.AsyncClient(transport=http_module.MockTransport(respond), trust_env=False)
        return real_factory(**kwargs, http_client=client)

    monkeypatch.setattr(mod, f"_{provider}_client", factory)
    result = await getattr(mod, f"call_{provider}_web")(call, WebCredential(selection, api_key="selected-key"), control)
    assert result.output == OUTPUT and result.usage == {"input_tokens": 10, "output_tokens": 20}
    assert len(requests) == 1
    assert "X-Private" not in requests[0].headers
    body = json.loads(requests[0].content)
    assert body["model"] == model
    if provider == "openai":
        assert requests[0].url == "https://api.openai.com/v1/responses"
        assert requests[0].headers["Authorization"] == "Bearer selected-key"
        assert body["max_tool_calls"] == 2
    else:
        assert requests[0].url == "https://api.anthropic.com/v1/messages"
        assert requests[0].headers["x-api-key"] == "selected-key"
        assert "Authorization" not in requests[0].headers
        assert body["tools"][0]["type"] == "web_search_20250305" and body["tools"][0]["max_uses"] == 2


@pytest.mark.anyio
async def test_actual_api_client_factories_do_not_load_ambient_auth_or_proxy(monkeypatch):
    from src.auth_drivers.lifecycle_web_models import _openai_client, _anthropic_client

    monkeypatch.setenv("OPENAI_API_KEY", "ambient-openai")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ambient-anthropic")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "ambient-bearer")
    monkeypatch.setenv("OPENAI_ORG_ID", "ambient-org")
    monkeypatch.setenv("OPENAI_PROJECT_ID", "ambient-project")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    openai = _openai_client(api_key="selected-key", max_retries=0, base_url="https://api.openai.com/v1", timeout=3)
    anthropic = _anthropic_client(api_key="selected-key", max_retries=0, base_url="https://api.anthropic.com", timeout=3)
    try:
        assert openai.api_key == "selected-key" and openai.organization == "" and openai.project == ""
        assert anthropic.api_key == "selected-key" and anthropic.auth_token is None
        assert openai.max_retries == anthropic.max_retries == 0
        assert openai._client._trust_env is anthropic._client._trust_env is False
    finally:
        await openai.close()
        await anthropic.close()
