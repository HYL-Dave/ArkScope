from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage
from src.auth_drivers.token_store import StoredTokenRecord


class _FakeStream:
    def __init__(self, events):
        self._events = list(events)
        self.closed = False

    def __iter__(self):
        return iter(self._events)

    def close(self):
        self.closed = True


class _FakeResponses:
    def __init__(self, stream):
        self.stream = stream
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.stream


class _FakeOpenAIClient:
    def __init__(self, stream):
        self.responses = _FakeResponses(stream)
        self.closed = False

    def close(self):
        self.closed = True


def _schema():
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
    }


def test_chatgpt_oauth_structured_output_uses_subscription_backend_and_closes(monkeypatch):
    from src.auth_drivers import subscription_structured_output as mod

    stream = _FakeStream(
        [
            {
                "type": "response.output_item.done",
                "item": {
                    "type": "function_call",
                    "name": "emit_check",
                    "call_id": "call-1",
                    "arguments": json.dumps({"ok": True}),
                },
            },
            {"type": "response.completed", "response": {"output": []}},
        ]
    )
    client = _FakeOpenAIClient(stream)
    built = {}

    def fake_client(token, base_url, timeout_s):
        built.update(token=token, base_url=base_url, timeout_s=timeout_s)
        return client

    refreshed = []

    def fake_refresh(*, credential_id, token_store):
        refreshed.append((credential_id, token_store))
        return StoredTokenRecord(access_token="fresh-oauth-token")

    token_store = object()
    monkeypatch.setattr(mod, "_openai_client", fake_client)
    monkeypatch.setattr(mod, "_refresh_chatgpt_token", fake_refresh)

    result = mod.run_subscription_structured_output(
        provider="openai",
        auth_mode="chatgpt_oauth",
        credential_id="local:7",
        model="gpt-5.4-mini",
        system="Return one structured result.",
        user="Check availability.",
        output_name="emit_check",
        output_description="Emit the check.",
        schema=_schema(),
        effort="high",
        token_store=token_store,
    )

    assert result == {"ok": True}
    assert refreshed == [("local:7", token_store)]
    assert built == {
        "token": "fresh-oauth-token",
        "base_url": "https://chatgpt.com/backend-api/codex",
        "timeout_s": 90.0,
    }
    assert client.responses.calls == [
        {
            "model": "gpt-5.4-mini",
            "input": [{"role": "user", "content": "Check availability."}],
            "instructions": "Return one structured result.",
            "tools": [
                {
                    "type": "function",
                    "name": "emit_check",
                    "description": "Emit the check.",
                    "parameters": _schema(),
                }
            ],
            "reasoning": {"effort": "high"},
            "stream": True,
            "store": False,
        }
    ]
    assert stream.closed is True
    assert client.closed is True


def test_chatgpt_oauth_default_effort_is_omitted(monkeypatch):
    from src.auth_drivers import subscription_structured_output as mod

    stream = _FakeStream(
        [
            {
                "type": "response.function_call_arguments.done",
                "call_id": "call-1",
                "arguments": json.dumps({"ok": True}),
            },
            {
                "type": "response.output_item.done",
                "item": {
                    "type": "function_call",
                    "name": "emit_check",
                    "call_id": "call-1",
                },
            },
            {"type": "response.completed", "response": {"output": []}},
        ]
    )
    client = _FakeOpenAIClient(stream)
    monkeypatch.setattr(mod, "_openai_client", lambda token, base_url, timeout_s: client)
    monkeypatch.setattr(
        mod,
        "_refresh_chatgpt_token",
        lambda **kwargs: StoredTokenRecord(access_token="fresh-oauth-token"),
    )

    result = mod.run_subscription_structured_output(
        provider="openai",
        auth_mode="chatgpt_oauth",
        credential_id="local:7",
        model="gpt-5.4-mini",
        system="sys",
        user="user",
        output_name="emit_check",
        output_description="desc",
        schema=_schema(),
        effort="default",
        token_store=object(),
    )

    assert result == {"ok": True}
    assert "reasoning" not in client.responses.calls[0]
    assert "max_output_tokens" not in client.responses.calls[0]


class _FakeTokenStore:
    def __init__(self, record):
        self.record = record
        self.loads = []

    def load(self, *, provider, auth_mode, credential_id):
        self.loads.append((provider, auth_mode, credential_id))
        return self.record


def test_claude_oauth_structured_output_uses_locked_agent_sdk_options(tmp_path, monkeypatch):
    from src.auth_drivers import subscription_structured_output as mod

    captured = {"closed": False}

    async def fake_query(*, prompt, options):
        captured.update(prompt=prompt, options=options)
        try:
            yield ResultMessage(
                subtype="success",
                duration_ms=1,
                duration_api_ms=1,
                is_error=False,
                num_turns=1,
                session_id="session-1",
                result=None,
                structured_output={"ok": True},
            )
        finally:
            captured["closed"] = True

    config_dir = tmp_path / "claude-config"
    config_dir.mkdir()
    monkeypatch.setattr(mod, "_claude_query", fake_query)
    monkeypatch.setattr(mod.tempfile, "mkdtemp", lambda **kwargs: str(config_dir))
    store = _FakeTokenStore(StoredTokenRecord(access_token="claude-setup-token"))

    result = mod.run_subscription_structured_output(
        provider="anthropic",
        auth_mode="claude_code_oauth",
        credential_id="local:2",
        model="claude-sonnet-5",
        system="Return one structured result.",
        user="Check availability.",
        output_name="emit_check",
        output_description="Emit the check.",
        schema=_schema(),
        effort="high",
        token_store=store,
        timeout_s=12,
    )

    assert result == {"ok": True}
    assert store.loads == [("anthropic", "claude_code_oauth", "local:2")]
    assert captured["prompt"] == "Check availability."
    options = captured["options"]
    assert options.model == "claude-sonnet-5"
    assert options.effort == "high"
    assert options.system_prompt == "Return one structured result."
    assert options.output_format == {"type": "json_schema", "schema": _schema()}
    assert options.tools == []
    assert options.allowed_tools == []
    assert options.mcp_servers == {}
    assert options.setting_sources == []
    assert options.strict_mcp_config is True
    assert options.permission_mode == "dontAsk"
    assert options.max_turns == 1
    assert options.env["CLAUDE_CODE_OAUTH_TOKEN"] == "claude-setup-token"
    assert options.env["ANTHROPIC_API_KEY"] == ""
    assert options.env["CLAUDE_CONFIG_DIR"] == str(config_dir)
    assert captured["closed"] is True
    assert Path(config_dir).exists() is False


def test_chatgpt_oauth_requires_the_named_function_call_and_still_closes(monkeypatch):
    from src.auth_drivers import subscription_structured_output as mod

    stream = _FakeStream([{"type": "response.completed", "response": {"output": []}}])
    client = _FakeOpenAIClient(stream)
    monkeypatch.setattr(mod, "_openai_client", lambda token, base_url, timeout_s: client)
    monkeypatch.setattr(
        mod,
        "_refresh_chatgpt_token",
        lambda **kwargs: StoredTokenRecord(access_token="fresh-oauth-token"),
    )

    with pytest.raises(mod.SubscriptionStructuredOutputError) as caught:
        mod.run_subscription_structured_output(
            provider="openai",
            auth_mode="chatgpt_oauth",
            credential_id="local:7",
            model="gpt-5.4-mini",
            system="sys",
            user="user",
            output_name="emit_check",
            output_description="desc",
            schema=_schema(),
            token_store=object(),
        )

    assert caught.value.code == "provider_call_failed"
    assert "emit_check" in str(caught.value)
    assert stream.closed is True and client.closed is True


def test_subscription_provider_error_redacts_the_oauth_token(monkeypatch):
    from src.auth_drivers import subscription_structured_output as mod

    secret = "oauth-super-secret-token-1234567890"

    class _BoomResponses:
        def create(self, **kwargs):
            raise RuntimeError(f"denied bearer {secret}")

    class _BoomClient:
        responses = _BoomResponses()

        def close(self):
            return None

    monkeypatch.setattr(mod, "_openai_client", lambda token, base_url, timeout_s: _BoomClient())
    monkeypatch.setattr(
        mod,
        "_refresh_chatgpt_token",
        lambda **kwargs: StoredTokenRecord(access_token=secret),
    )

    with pytest.raises(mod.SubscriptionStructuredOutputError) as caught:
        mod.run_subscription_structured_output(
            provider="openai",
            auth_mode="chatgpt_oauth",
            credential_id="local:7",
            model="gpt-5.4-mini",
            system="sys",
            user="user",
            output_name="emit_check",
            output_description="desc",
            schema=_schema(),
            token_store=object(),
        )

    assert caught.value.code == "provider_call_failed"
    assert secret not in str(caught.value)
    assert "REDACTED" in str(caught.value)


def test_claude_oauth_missing_token_is_reauth_and_never_starts_sdk(monkeypatch):
    from src.auth_drivers import subscription_structured_output as mod

    async def forbidden_query(**kwargs):
        raise AssertionError("Claude SDK must not start without a token")
        yield  # pragma: no cover

    monkeypatch.setattr(mod, "_claude_query", forbidden_query)
    store = _FakeTokenStore(None)

    with pytest.raises(mod.SubscriptionStructuredOutputError) as caught:
        mod.run_subscription_structured_output(
            provider="anthropic",
            auth_mode="claude_code_oauth",
            credential_id="local:2",
            model="claude-sonnet-5",
            system="sys",
            user="user",
            output_name="emit_check",
            output_description="desc",
            schema=_schema(),
            token_store=store,
        )

    assert caught.value.code == "reauth_required"
    assert store.loads == [("anthropic", "claude_code_oauth", "local:2")]


def test_cross_provider_subscription_auth_is_rejected_before_token_access():
    from src.auth_drivers import subscription_structured_output as mod

    with pytest.raises(mod.SubscriptionStructuredOutputError) as caught:
        mod.run_subscription_structured_output(
            provider="openai",
            auth_mode="claude_code_oauth",
            credential_id="local:2",
            model="gpt-5.4-mini",
            system="sys",
            user="user",
            output_name="emit_check",
            output_description="desc",
            schema=_schema(),
            token_store=object(),
        )

    assert caught.value.code == "task_auth_mode_unsupported"


def test_claude_sync_adapter_is_safe_when_caller_already_has_an_event_loop(
    tmp_path, monkeypatch
):
    from src.auth_drivers import subscription_structured_output as mod

    async def fake_query(*, prompt, options):
        yield ResultMessage(
            subtype="success",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="session-async-host",
            structured_output={"ok": True},
        )

    monkeypatch.setattr(mod, "_claude_query", fake_query)
    store = _FakeTokenStore(StoredTokenRecord(access_token="claude-setup-token"))

    async def invoke_from_async_host():
        return mod.run_subscription_structured_output(
            provider="anthropic",
            auth_mode="claude_code_oauth",
            credential_id="local:2",
            model="claude-sonnet-5",
            system="sys",
            user="user",
            output_name="emit_check",
            output_description="desc",
            schema=_schema(),
            token_store=store,
            timeout_s=2,
        )

    assert asyncio.run(invoke_from_async_host()) == {"ok": True}
