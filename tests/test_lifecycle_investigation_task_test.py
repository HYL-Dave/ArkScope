"""One explicit connectivity/schema check through the real task's dispatcher."""

import asyncio
from types import SimpleNamespace

import pytest

from src import model_task_canary as canary
from src.auth_drivers import lifecycle_web_dispatch as dispatch
from src.auth_drivers import lifecycle_web_models as models
from src.model_discovery_cache import DiscoveryScope
from src.model_effective import ActiveCredential


TASK = "lifecycle_investigation"
CHANNELS = [
    ("anthropic", "api_key", "claude-sonnet-5"),
    ("anthropic", "claude_code_oauth", "claude-sonnet-5"),
    ("openai", "api_key", "gpt-5.6-luna"),
    ("openai", "chatgpt_oauth", "gpt-5.6-luna"),
]


def _check(monkeypatch, tmp_path, provider, auth_mode, model, *, error=None, output=None,
           terminal=True, used_tool=False, credential_error=None):
    active = ActiveCredential(provider, "local:7", auth_mode, "test-fingerprint")
    monkeypatch.setattr(canary, "resolve_active_credential", lambda *a, **kw: active)
    monkeypatch.setattr(canary, "ModelDiscoveryCache", lambda path: SimpleNamespace(
        get=lambda **kw: DiscoveryScope(status="seed_only", discovered_at=None, models=[]),
    ))
    forbidden = lambda *a, **kw: pytest.fail("different transport/billing fallback")
    monkeypatch.setattr(canary, "test_model", forbidden)
    monkeypatch.setattr(canary, "build_driver", forbidden)
    monkeypatch.setattr(canary, "run_subscription_structured_output_async", forbidden)
    credentials, calls = [], []

    def credential(selection, **kwargs):
        credentials.append(selection)
        if credential_error:
            raise models.WebModelError(credential_error)
        return models.WebCredential(selection,
            api_key="private-test-key" if auth_mode == "api_key" else None,
            token_record=SimpleNamespace(access_token="private-test-token") if auth_mode != "api_key" else None)

    async def call(request, credential, control):
        calls.append((request, credential, control))
        control.reserve_model_request(request.call_id)
        control.bind_remote_id(request.call_id, "test-remote-1")
        if used_tool:
            control.observe_web_action(request.call_id, "tool-1", "search")
        if terminal:
            control.observe_terminal(request.call_id, response_id="test-remote-1",
                status="completed", selection=request.selection)
        else:
            control.observe_transport_loss(request.call_id)
        if error:
            raise models.WebModelError(error)
        return models.ModelReply("test-remote-1", output if output is not None else {"ok": True},
                                 {"input_tokens": 8, "output_tokens": 4})

    monkeypatch.setattr(models, "resolve_web_credential", credential)
    monkeypatch.setattr(dispatch, "call_lifecycle_web_model", call)
    result = asyncio.run(canary.dispatch_task_model_test(task=TASK, provider=provider, model=model,
        effort="high", store=SimpleNamespace(db_path=tmp_path / "profile.db"), token_store=object(), timeout_s=15))
    return result, credentials, calls


@pytest.mark.parametrize(("provider", "auth_mode", "model"), CHANNELS)
def test_investigation_schema_check_uses_same_adapter_once_on_all_four_channels(monkeypatch, tmp_path, provider, auth_mode, model):
    result, credentials, calls = _check(monkeypatch, tmp_path, provider, auth_mode, model)
    assert result.status == "ok"
    assert result.task == TASK
    assert result.fallback_effort is None
    assert len(credentials) == len(calls) == 1
    request, credential, control = calls[0]
    assert request.phase == "analysis"  # No public search or source acquisition.
    assert request.selection == credential.selection == credentials[0]
    assert (request.selection.provider, request.selection.model, request.selection.auth_mode) == (provider, model, auth_mode)
    assert request.effort == "high"
    assert request.timeout_seconds == 15
    assert request.output_schema["additionalProperties"] is False
    assert control.max_model_requests == control.model_requests == 1
    assert not any(control.observed_web_actions.values())
    assert "private-test" not in result.model_dump_json()


@pytest.mark.parametrize("code", ["credential_rejected", "provider_rate_limited", "timeout", "model_output_invalid"])
@pytest.mark.parametrize(("provider", "auth_mode", "model"), CHANNELS)
def test_investigation_schema_check_never_retries_or_switches_credentials(monkeypatch, tmp_path, provider, auth_mode, model, code):
    result, credentials, calls = _check(monkeypatch, tmp_path, provider, auth_mode, model, error=code)
    assert result.status == "error"
    assert len(credentials) == len(calls) == 1
    assert result.fallback_effort is None
    assert "private-test" not in result.model_dump_json()


@pytest.mark.parametrize("output", [{"ok": False}, {"ok": True, "extra": 1}, {"ok": "true"}, {}])
def test_investigation_schema_check_does_not_accept_malformed_success(monkeypatch, tmp_path, output):
    result, _, calls = _check(monkeypatch, tmp_path, *CHANNELS[1], output=output)
    assert len(calls) == 1
    assert result.status == "error"
    assert result.error_code == "provider_call_failed"


@pytest.mark.parametrize("violation", ["missing_terminal", "unexpected_search"])
def test_investigation_schema_check_requires_completed_tool_free_witness(monkeypatch, tmp_path, violation):
    result, _, calls = _check(monkeypatch, tmp_path, *CHANNELS[1],
        terminal=violation != "missing_terminal", used_tool=violation == "unexpected_search")
    assert len(calls) == 1
    assert result.status == "error"


def test_investigation_schema_check_missing_selected_credential_never_dispatches(monkeypatch, tmp_path):
    result, credentials, calls = _check(monkeypatch, tmp_path, *CHANNELS[1], credential_error="reauth_required")
    assert len(credentials) == 1
    assert calls == []
    assert result.status == "error"
    assert result.error_code == "reauth_required"


@pytest.mark.parametrize(("provider", "auth_mode", "model"), [
    ("openai", "chatgpt_oauth", "gpt-5.3-codex-spark"),
    ("anthropic", "claude_code_oauth", "claude-fable-5-1"),
    ("anthropic", "api_key", "claude-fable-5"),
    ("openai", "api_key", "gpt-unknown-custom"),
])
def test_investigation_schema_check_cannot_bypass_model_policy(monkeypatch, tmp_path, provider, auth_mode, model):
    result, credentials, calls = _check(monkeypatch, tmp_path, provider, auth_mode, model)
    assert result.status == "unsupported"
    assert credentials == calls == []
