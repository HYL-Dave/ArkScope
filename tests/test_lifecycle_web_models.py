import asyncio
from dataclasses import replace
from types import SimpleNamespace

import pytest

from src.security_lifecycle_web_contract import RunControl, validate_selection


SCHEMA = {"type": "object", "additionalProperties": False,
          "properties": {"sources": {"type": "array", "items": {"type": "string"}}},
          "required": ["sources"]}
PAYLOAD = {"sources": ["https://ir.example.com/notice"]}


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _selection(provider="openai", auth="api_key"):
    return validate_selection(provider, auth, "gpt-5.6-luna" if provider == "openai" else "claude-opus-5", "local:7")


def _request(provider="openai", auth="api_key", **overrides):
    from src.auth_drivers.lifecycle_web_models import ModelCall

    return ModelCall(selection=_selection(provider, auth), call_id="search-1", phase="search",
                     prompt="Public issuer and listing question", output_schema=SCHEMA,
                     effort="high", output_token_limit=4096, max_search_uses=3,
                     timeout_seconds=5.0, **overrides)


class RecordStore:
    def __init__(self, row):
        self.row = row
        self.calls = []

    def get(self, key):
        self.calls.append(key)
        return self.row


class TokenStore:
    def __init__(self, record):
        self.record = record
        self.calls = []

    def load(self, **kwargs):
        self.calls.append(kwargs)
        return self.record


def test_credentials_bind_exact_profile_row_and_never_use_environment(monkeypatch):
    from src.auth_drivers.lifecycle_web_models import resolve_web_credential, WebModelError

    monkeypatch.setenv("OPENAI_API_KEY", "ambient-must-not-be-used")
    selection = _selection()
    row = SimpleNamespace(id=7, provider="openai", auth_type="api_key", secret="selected-key")
    store = RecordStore(row)
    credential = resolve_web_credential(selection, store=store, token_store=TokenStore(None))
    assert credential.api_key == "selected-key" and credential.token_record is None
    assert store.calls == ["local:7"]
    assert "selected-key" not in repr(credential)
    for invalid in (None, SimpleNamespace(**{**vars(row), "id": 8}),
                    SimpleNamespace(**{**vars(row), "provider": "anthropic"}),
                    SimpleNamespace(**{**vars(row), "auth_type": "chatgpt_oauth"}),
                    SimpleNamespace(**{**vars(row), "secret": None})):
        with pytest.raises(WebModelError):
            resolve_web_credential(selection, store=RecordStore(invalid), token_store=TokenStore(None))


@pytest.mark.parametrize("provider,auth", [("openai", "chatgpt_oauth"), ("anthropic", "claude_code_oauth")])
def test_oauth_credential_reads_only_the_exact_token_scope(provider, auth):
    from src.auth_drivers.lifecycle_web_models import resolve_web_credential, WebModelError
    from src.auth_drivers.token_store import StoredTokenRecord

    token = StoredTokenRecord(access_token="selected-token")
    tokens = TokenStore(token)
    row = SimpleNamespace(id=7, provider=provider, auth_type=auth, secret=None)
    value = resolve_web_credential(_selection(provider, auth), store=RecordStore(row), token_store=tokens)
    assert value.token_record is token and value.api_key is None
    assert tokens.calls == [{"provider": provider, "auth_mode": auth, "credential_id": "local:7"}]
    assert "selected-token" not in repr(value)
    token.expires_at = "2000-01-01T00:00:00Z"
    with pytest.raises(WebModelError, match="reauth_required"):
        resolve_web_credential(_selection(provider, auth), store=RecordStore(row), token_store=tokens)


def test_explicit_web_launch_refreshes_only_the_selected_expired_chatgpt_token_once():
    from src.auth_drivers.lifecycle_web_models import resolve_web_credential
    from src.auth_drivers.token_store import StoredTokenRecord
    row = SimpleNamespace(id=7, provider="openai", auth_type="chatgpt_oauth", secret=None)
    tokens = TokenStore(StoredTokenRecord(access_token="old-token", expires_at="2000-01-01T00:00:00Z"))
    fresh = StoredTokenRecord(access_token="new-token", expires_at="2099-01-01T00:00:00Z")
    calls = []
    def refresh(**kwargs):
        calls.append(kwargs)
        return fresh
    result = resolve_web_credential(_selection("openai", "chatgpt_oauth"), store=RecordStore(row), token_store=tokens, refresh_chatgpt=refresh)
    assert result.token_record is fresh and result.api_key is None
    assert calls == [{"credential_id": "local:7", "token_store": tokens}]
    assert "new-token" not in repr(result)
    tokens.record = fresh
    resolve_web_credential(_selection("openai", "chatgpt_oauth"), store=RecordStore(row), token_store=tokens, refresh_chatgpt=refresh)
    assert len(calls) == 1


@pytest.mark.parametrize("auth,expires", [("claude_code_oauth", "2000-01-01T00:00:00Z"), ("chatgpt_oauth", "malformed")])
def test_web_refresh_cannot_repair_another_auth_channel_or_malformed_expiry(auth, expires):
    from src.auth_drivers.lifecycle_web_models import resolve_web_credential, WebModelError
    from src.auth_drivers.token_store import StoredTokenRecord
    provider = "openai" if auth == "chatgpt_oauth" else "anthropic"
    row = SimpleNamespace(id=7, provider=provider, auth_type=auth, secret=None)
    def unexpected(**kwargs):
        raise AssertionError("not_this_auth_scope")
    with pytest.raises(WebModelError, match="reauth_required"):
        resolve_web_credential(_selection(provider, auth), store=RecordStore(row),
            token_store=TokenStore(StoredTokenRecord(access_token="old-token", expires_at=expires)), refresh_chatgpt=unexpected)


def test_web_refresh_failure_is_redacted_and_never_uses_old_token_or_api_key():
    from src.auth_drivers.lifecycle_web_models import resolve_web_credential, WebModelError
    from src.auth_drivers.token_store import StoredTokenRecord
    row = SimpleNamespace(id=7, provider="openai", auth_type="chatgpt_oauth", secret="must-not-use-this-api-key")
    tokens = TokenStore(StoredTokenRecord(access_token="old-token", expires_at="2000-01-01T00:00:00Z"))
    calls = []
    def refresh(**kwargs):
        calls.append(kwargs)
        raise RuntimeError("secret-in-upstream-error")
    with pytest.raises(WebModelError, match="^selected_credential_unavailable$"):
        resolve_web_credential(_selection("openai", "chatgpt_oauth"), store=RecordStore(row), token_store=tokens, refresh_chatgpt=refresh)
    assert len(calls) == 1


@pytest.mark.parametrize("changed", [
    {"phase": "other"}, {"effort": "imaginary"}, {"max_search_uses": 0},
    {"output_token_limit": True}, {"timeout_seconds": float("nan")},
    {"output_schema": {"type": "not-json-schema"}},
])
def test_model_call_is_validated_before_client_creation(changed):
    from src.auth_drivers.lifecycle_web_models import WebModelError

    with pytest.raises(WebModelError):
        replace(_request(), **changed)


class OpenAIResponses:
    def __init__(self, result=None, *, error=None, cancel_result=None):
        self.calls = []
        self.result = result or _openai_result()
        self.error = error
        self.cancel_result = cancel_result

    async def create(self, **kwargs):
        self.calls.append(("create", kwargs))
        if self.error:
            raise self.error
        return self.result

    async def retrieve(self, response_id, **kwargs):
        self.calls.append(("retrieve", response_id))
        return self.result

    async def cancel(self, response_id, **kwargs):
        self.calls.append(("cancel", response_id))
        return self.cancel_result or self.result


def _openai_result(**overrides):
    return SimpleNamespace(**{
        "id": "resp-1", "model": "gpt-5.6-luna", "status": "completed",
        "output": [SimpleNamespace(type="web_search_call", id="web-1", status="completed",
                                   action=SimpleNamespace(type="search"))],
        "output_text": '{"sources":["https://ir.example.com/notice"]}',
        "usage": SimpleNamespace(input_tokens=100, output_tokens=50), **overrides,
    })


class Client:
    def __init__(self, *, responses=None, messages=None):
        self.responses = responses
        self.messages = messages
        self.closed = False

    async def close(self):
        self.closed = True


def _credential(request):
    from src.auth_drivers.lifecycle_web_models import WebCredential

    return WebCredential(selection=request.selection, api_key="selected-key")


@pytest.mark.anyio
async def test_openai_web_uses_native_bound_exact_key_and_no_sdk_retry(monkeypatch):
    from src.auth_drivers import lifecycle_web_models as mod

    request = _request()
    control = RunControl(selection=request.selection, max_model_requests=2)
    responses = OpenAIResponses()
    client = Client(responses=responses)
    arguments = []
    monkeypatch.setattr(mod, "_openai_client", lambda **kw: (arguments.append(kw), client)[1])
    reply = await mod.call_openai_web(request, _credential(request), control)
    assert reply.output == PAYLOAD and reply.remote_id == "resp-1"
    assert reply.usage == {"input_tokens": 100, "output_tokens": 50}
    assert control.terminal_statuses == {"search-1": "completed"}
    assert control.observed_web_actions == {"search": 1, "open_page": 0, "find_in_page": 0}
    assert len(arguments) == 1 and arguments[0]["api_key"] == "selected-key"
    assert arguments[0]["max_retries"] == 0
    assert arguments[0]["base_url"] == "https://api.openai.com/v1"
    call = responses.calls[0][1]
    assert call["model"] == request.selection.model
    assert call["tools"] == [{"type": "web_search"}] and call["max_tool_calls"] == 3
    assert call["reasoning"] == {"effort": "high"}
    assert call["background"] is True and call["store"] is True
    assert call["max_output_tokens"] == 4096
    assert call["text"]["format"]["schema"] == SCHEMA
    assert client.closed and len(responses.calls) == 1


@pytest.mark.anyio
@pytest.mark.parametrize("provider", ["openai", "anthropic"])
async def test_analysis_phase_does_not_keep_search_tools(monkeypatch, provider):
    from src.auth_drivers import lifecycle_web_models as mod

    request = replace(_request(provider), phase="analysis", call_id="analysis-1")
    control = RunControl(selection=request.selection, max_model_requests=1)
    if provider == "openai":
        calls = OpenAIResponses(_openai_result(output=[]))
        client = Client(responses=calls)
    else:
        calls = AnthropicMessages(_anthropic_result(content=[_emission()]))
        client = Client(messages=calls)
    monkeypatch.setattr(mod, f"_{provider}_client", lambda **kw: client)
    result = await getattr(mod, f"call_{provider}_web")(request, _credential(request), control)
    assert result.output == PAYLOAD
    payload = calls.calls[0][1]
    assert not any(tool.get("type", "").startswith("web_search") for tool in payload.get("tools", []))


@pytest.mark.anyio
@pytest.mark.parametrize("result,code", [
    (_openai_result(model="gpt-5.6-terra"), "execution_identity_changed"),
    (_openai_result(status="incomplete"), "model_result_incomplete"),
    (_openai_result(output_text="not-json"), "model_output_invalid"),
    (_openai_result(output_text='{"sources":[],"write_profile":true}'), "model_output_invalid"),
    (_openai_result(output=[SimpleNamespace(type="function_call", id="bad")]), "unexpected_tool_activity"),
])
async def test_openai_web_rejects_incomplete_or_changed_execution_without_fallback(monkeypatch, result, code):
    from src.auth_drivers import lifecycle_web_models as mod

    request = _request()
    control = RunControl(selection=request.selection, max_model_requests=2)
    responses = OpenAIResponses(result)
    client = Client(responses=responses)
    monkeypatch.setattr(mod, "_openai_client", lambda **kw: client)
    with pytest.raises(mod.WebModelError, match=code):
        await mod.call_openai_web(request, _credential(request), control)
    assert client.closed and len(responses.calls) == 1 and control.model_requests == 1


@pytest.mark.anyio
async def test_failed_openai_dispatch_with_no_response_id_is_unknown_and_not_retried(monkeypatch):
    from src.auth_drivers import lifecycle_web_models as mod

    request = _request()
    control = RunControl(selection=request.selection, max_model_requests=2)
    responses = OpenAIResponses(error=RuntimeError("selected-key provider details"))
    client = Client(responses=responses)
    monkeypatch.setattr(mod, "_openai_client", lambda **kw: client)
    with pytest.raises(mod.WebModelError, match="provider_call_failed") as error:
        await mod.call_openai_web(request, _credential(request), control)
    assert "selected-key" not in str(error.value)
    assert control.stop_state == "remote_outcome_unknown"
    assert len(responses.calls) == 1 and client.closed


@pytest.mark.anyio
@pytest.mark.parametrize("terminal", [True, False])
async def test_openai_cancel_requires_terminal_readback(monkeypatch, terminal):
    from src.auth_drivers import lifecycle_web_models as mod

    request = _request()
    control = RunControl(selection=request.selection, max_model_requests=2)
    responses = OpenAIResponses(_openai_result(status="in_progress"),
                               cancel_result=_openai_result(status="cancelled" if terminal else "in_progress"))
    original = responses.create

    async def create(**kwargs):
        result = await original(**kwargs)
        control.request_stop()
        return result

    responses.create = create
    client = Client(responses=responses)
    monkeypatch.setattr(mod, "_openai_client", lambda **kw: client)
    monkeypatch.setattr(mod, "_STOP_GRACE_SECONDS", 0.03)
    with pytest.raises(mod.WebModelError, match="stop_requested"):
        await mod.call_openai_web(request, _credential(request), control)
    assert control.stop_state == ("cancelled" if terminal else "remote_outcome_unknown")
    assert [name for name, _ in responses.calls].count("create") == 1
    assert [name for name, _ in responses.calls].count("cancel") == 1
    assert client.closed


def _emission(**changes):
    return SimpleNamespace(**{"type": "tool_use", "name": "emit_lifecycle_result", "id": "emit-1", "input": PAYLOAD, **changes})


def _anthropic_result(**changes):
    return SimpleNamespace(**{
        "id": "msg-1", "model": "claude-opus-5", "stop_reason": "tool_use",
        "content": [SimpleNamespace(type="server_tool_use", name="web_search", id="web-1"),
                    SimpleNamespace(type="web_search_tool_result", tool_use_id="web-1", content=[]), _emission()],
        "usage": SimpleNamespace(input_tokens=100, output_tokens=50), **changes,
    })


class AnthropicMessages:
    def __init__(self, result=None, *, error=None):
        self.result = result or _anthropic_result()
        self.calls = []
        self.error = error

    async def create(self, **kwargs):
        self.calls.append(("create", kwargs))
        if self.error:
            raise self.error
        return self.result


@pytest.mark.anyio
async def test_anthropic_web_uses_basic_search_not_code_execution_and_no_retry(monkeypatch):
    from src.auth_drivers import lifecycle_web_models as mod

    request = _request("anthropic")
    control = RunControl(selection=request.selection, max_model_requests=1)
    messages = AnthropicMessages()
    client = Client(messages=messages)
    arguments = []
    monkeypatch.setattr(mod, "_anthropic_client", lambda **kw: (arguments.append(kw), client)[1])
    reply = await mod.call_anthropic_web(request, _credential(request), control)
    assert reply.output == PAYLOAD and reply.remote_id == "msg-1"
    assert control.terminal_statuses == {"search-1": "completed"}
    call = messages.calls[0][1]
    assert call["tools"][0] == {"type": "web_search_20250305", "name": "web_search", "max_uses": 3}
    assert call["tools"][1]["name"] == "emit_lifecycle_result" and call["tools"][1]["strict"] is True
    assert call["tool_choice"] == {"type": "auto"}
    assert call["output_config"] == {"effort": "high"}
    assert call["model"] == request.selection.model and call["max_tokens"] == 4096
    assert arguments[0]["max_retries"] == 0 and arguments[0]["api_key"] == "selected-key"
    assert arguments[0]["base_url"] == "https://api.anthropic.com"
    assert client.closed and len(messages.calls) == 1


@pytest.mark.anyio
@pytest.mark.parametrize("result,code", [
    (_anthropic_result(model="claude-sonnet-5"), "execution_identity_changed"),
    (_anthropic_result(stop_reason="pause_turn"), "model_result_incomplete"),
    (_anthropic_result(stop_reason="max_tokens"), "model_result_incomplete"),
    (_anthropic_result(stop_reason="refusal"), "provider_refused"),
    (_anthropic_result(content=[_emission(name="Bash")]), "unexpected_tool_activity"),
    (_anthropic_result(content=[_emission(input={"sources": 5})]), "model_output_invalid"),
    (_anthropic_result(content=[SimpleNamespace(type="web_search_tool_result", tool_use_id="web-1",
                                              content=SimpleNamespace(type="web_search_tool_result_error", error_code="max_uses_exceeded"))]), "search_budget_exhausted"),
])
async def test_anthropic_web_refuses_tool_errors_pauses_and_wrong_model(monkeypatch, result, code):
    from src.auth_drivers import lifecycle_web_models as mod

    request = _request("anthropic")
    control = RunControl(selection=request.selection, max_model_requests=2)
    messages = AnthropicMessages(result)
    client = Client(messages=messages)
    monkeypatch.setattr(mod, "_anthropic_client", lambda **kw: client)
    with pytest.raises(mod.WebModelError, match=code):
        await mod.call_anthropic_web(request, _credential(request), control)
    assert len(messages.calls) == 1 and client.closed


@pytest.mark.anyio
async def test_anthropic_transport_cancellation_is_not_remote_terminal(monkeypatch):
    from src.auth_drivers import lifecycle_web_models as mod

    request = _request("anthropic")
    control = RunControl(selection=request.selection, max_model_requests=2)
    entered = asyncio.Event()
    messages = AnthropicMessages()

    async def blocked(**kwargs):
        messages.calls.append(("create", kwargs))
        entered.set()
        await asyncio.Event().wait()

    messages.create = blocked
    client = Client(messages=messages)
    monkeypatch.setattr(mod, "_anthropic_client", lambda **kw: client)
    task = asyncio.create_task(mod.call_anthropic_web(request, _credential(request), control))
    await entered.wait()
    control.request_stop()
    with pytest.raises(mod.WebModelError, match="stop_requested"):
        await asyncio.wait_for(task, 1)
    assert control.stop_state == "remote_outcome_unknown" and client.closed
    assert len(messages.calls) == 1
