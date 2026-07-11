from __future__ import annotations

import asyncio
import inspect
from dataclasses import replace
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.agents.shared.events import AgentEvent, EventType
from src.auth_drivers.api_key_drivers import MissingCredentialError
from src.model_capabilities import all_models, capability_for
from src.model_credentials import ModelTestResult
from src.model_discovery_cache import CachedModel, DiscoveryScope
from src.model_effective import ActiveCredential, task_auth_executable, task_capability_ok


def _active(auth_mode: str = "api_key", provider: str = "openai") -> ActiveCredential:
    return ActiveCredential(
        provider=provider,
        credential_id="local:7",
        auth_mode=auth_mode,
        secret_fingerprint="oauth" if "oauth" in auth_mode else "abc123",
    )


class _Store:
    def __init__(self, path, row=None):
        self.db_path = path
        self._row = row or SimpleNamespace(
            id=7,
            provider="openai",
            auth_type="chatgpt_oauth",
            secret=None,
        )

    def get(self, credential_id):
        assert credential_id == "local:7"
        return self._row


class _Cache:
    def __init__(self, scope=None, error: Exception | None = None):
        self.scope = scope or DiscoveryScope(
            status="never_discovered", discovered_at=None, models=[]
        )
        self.error = error
        self.calls = []

    def get(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.scope


class _Stream:
    def __init__(self, events=(), *, error: Exception | None = None, hang=False):
        self.events = list(events)
        self.error = error
        self.hang = hang
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.error:
            error, self.error = self.error, None
            raise error
        if self.hang:
            await asyncio.sleep(60)
        if not self.events:
            raise StopAsyncIteration
        return self.events.pop(0)

    async def aclose(self):
        self.closed = True


class _Driver:
    def __init__(self, stream: _Stream):
        self.stream = stream
        self.requests = []

    def stream_llm(self, request):
        self.requests.append(request)
        return self.stream


_DEFAULT_ACTIVE = object()


def _run(monkeypatch, tmp_path, *, active=_DEFAULT_ACTIVE, cache=None, api_result=None,
         stream=None, driver_error=None, task="ai_research", provider="openai",
         model="gpt-5.4-mini", effort="low", timeout_s=0.05):
    import src.model_task_test as mt

    active = _active() if active is _DEFAULT_ACTIVE else active
    cache = cache or _Cache()
    calls = {"api": [], "driver": []}
    monkeypatch.setattr(mt, "resolve_active_credential", lambda *_a, **_kw: active)
    monkeypatch.setattr(mt, "ModelDiscoveryCache", lambda _path: cache)

    def fake_api_test(*args, **kwargs):
        calls["api"].append((args, kwargs))
        return api_result or ModelTestResult(
            provider=provider,
            credential_id=active.credential_id if active else None,
            model=model,
            effort=effort,
            status="ok",
            latency_ms=12,
        )

    def fake_driver(**kwargs):
        calls["driver"].append(kwargs)
        if driver_error:
            raise driver_error
        return _Driver(stream or _Stream([AgentEvent(EventType.done, {"answer": "ok"})]))

    monkeypatch.setattr(mt, "test_model", fake_api_test)
    monkeypatch.setattr(mt, "build_driver", fake_driver)
    result = asyncio.run(mt.dispatch_task_model_test(
        task=task,
        provider=provider,
        model=model,
        effort=effort,
        store=_Store(tmp_path / "profile_state.db"),
        token_store=object(),
        timeout_s=timeout_s,
    ))
    return result, calls, cache


def test_dispatch_matrix_zero_call_arms(monkeypatch, tmp_path):
    cases = [
        (None, "card_synthesis", "openai", "missing_active_credential"),
        (_active("api_key_pool"), "ai_research", "openai", "task_test_unsupported"),
        (_active("chatgpt_oauth"), "card_synthesis", "openai", "task_auth_mode_unsupported"),
        (_active("claude_code_oauth", "anthropic"), "card_synthesis", "anthropic", "task_auth_mode_unsupported"),
        (_active("claude_code_oauth", "anthropic"), "ai_research", "anthropic", "task_test_unsupported"),
    ]
    for active, task, provider, code in cases:
        result, calls, _ = _run(
            monkeypatch, tmp_path, active=active, task=task, provider=provider,
            model="claude-opus-4-8" if provider == "anthropic" else "gpt-5.4-mini",
        )
        assert result.error_code == code
        assert calls == {"api": [], "driver": []}


def test_model_axis_zero_call_vetoes(monkeypatch, tmp_path):
    result, calls, _ = _run(
        monkeypatch, tmp_path, provider="anthropic", model="gpt-5.4-mini",
        active=_active("api_key", "anthropic"),
    )
    assert result.error_code == "task_capability_missing"
    assert calls == {"api": [], "driver": []}

    import src.model_task_test as mt

    real = capability_for("gpt-5.4-mini")
    monkeypatch.setattr(
        mt, "capability_for",
        lambda model: replace(real, supports_tool_calling=False) if model == real.id else real,
    )
    result, calls, _ = _run(monkeypatch, tmp_path, model=real.id)
    assert result.error_code == "task_capability_missing"
    assert calls == {"api": [], "driver": []}

    monkeypatch.setattr(mt, "capability_for", capability_for)
    scope = DiscoveryScope(
        status="ok", discovered_at="2026-07-11T00:00:00Z",
        models=[CachedModel("gpt-5.6-sol", "Sol", "provider_api")],
    )
    result, calls, _ = _run(monkeypatch, tmp_path, cache=_Cache(scope), model="gpt-5.4-mini")
    assert result.error_code == "model_not_visible"
    assert calls == {"api": [], "driver": []}

    result, calls, _ = _run(monkeypatch, tmp_path, cache=_Cache(scope), model="gpt-5.6")
    assert result.status == "ok"
    assert len(calls["api"]) == 1


def test_dispatch_precedence_auth_before_capability(monkeypatch, tmp_path):
    result, calls, _ = _run(
        monkeypatch, tmp_path,
        active=_active("chatgpt_oauth"), task="card_synthesis", model="gpt-5.4-mini",
    )
    assert result.error_code == "task_auth_mode_unsupported"
    assert calls == {"api": [], "driver": []}

    for capability in all_models():
        for task in ("card_synthesis", "card_translation", "ai_research"):
            assert task_capability_ok(task, capability) == task_auth_executable(
                task, capability.provider, "api_key", capability
            )


@pytest.mark.parametrize("state", ["seed_only", "never_discovered"])
def test_seed_channels_never_visibility_veto(monkeypatch, tmp_path, state):
    scope = DiscoveryScope(status=state, discovered_at=None, models=[])
    result, calls, _ = _run(
        monkeypatch, tmp_path, active=_active("chatgpt_oauth"),
        cache=_Cache(scope), model="gpt-custom-next",
    )
    assert result.status == "ok"
    assert len(calls["driver"]) == 1


@pytest.mark.parametrize("auth_mode", ["api_key", "chatgpt_oauth"])
def test_cache_read_failure_is_discovery_unavailable_for_all_auth_modes(
    monkeypatch, tmp_path, auth_mode
):
    result, calls, _ = _run(
        monkeypatch, tmp_path, active=_active(auth_mode),
        cache=_Cache(error=OSError("locked")),
    )
    assert result.error_code == "discovery_unavailable"
    assert calls == {"api": [], "driver": []}


def test_api_key_arm_reuses_test_model_and_translates(monkeypatch, tmp_path):
    ok = ModelTestResult(
        provider="openai", credential_id="local:7", model="gpt-5.4-mini",
        effort="low", status="ok", latency_ms=23, fallback_effort="default",
        warning="effort fallback",
    )
    result, calls, _ = _run(monkeypatch, tmp_path, api_result=ok)
    assert result.status == "ok"
    assert result.latency_ms == 23 and result.fallback_effort == "default"
    assert calls["api"][0][1]["credential_id"] == "local:7"

    for status, expected in [
        ("missing_credential", "missing_active_credential"),
        ("error", "provider_call_failed"),
    ]:
        raw = ModelTestResult(
            provider="openai", credential_id="local:7", model="gpt-5.4-mini",
            effort="low", status=status, error="provider refused",
        )
        result, _, _ = _run(monkeypatch, tmp_path, api_result=raw)
        assert result.error_code == expected


def test_oauth_research_canary_bounds(monkeypatch, tmp_path):
    stream = _Stream([AgentEvent(EventType.done, {"answer": "ok"})])
    result, calls, _ = _run(
        monkeypatch, tmp_path, active=_active("chatgpt_oauth"), stream=stream,
    )
    assert result.status == "ok" and result.tested_at
    built = calls["driver"][0]
    assert built["max_turns"] == 1
    assert built["registry"] is None and built["dal"] is None
    assert built["timeout_s"] <= 45


def test_oauth_canary_reauth_and_model_not_found(monkeypatch, tmp_path):
    reauth = _Stream([AgentEvent(EventType.error, {
        "code": "reauth_required", "error": "log in again",
    })])
    result, _, _ = _run(
        monkeypatch, tmp_path, active=_active("chatgpt_oauth"), stream=reauth,
    )
    assert result.error_code == "reauth_required"

    failed = _Stream([AgentEvent(EventType.error, {"error": "Model not found"})])
    result, _, _ = _run(
        monkeypatch, tmp_path, active=_active("chatgpt_oauth"), stream=failed,
    )
    assert result.error_code == "provider_call_failed"
    assert "Model not found" in (result.warning or "")


def test_oauth_canary_tool_event_aborts_unsupported(monkeypatch, tmp_path):
    stream = _Stream([AgentEvent(EventType.tool_start, {"tool": "get_quote"})])
    result, _, _ = _run(
        monkeypatch, tmp_path, active=_active("chatgpt_oauth"), stream=stream,
    )
    assert result.error_code == "task_test_unsupported"
    assert stream.closed is True


@pytest.mark.parametrize(
    ("stream", "driver_error", "expected"),
    [
        (_Stream(hang=True), None, "provider_call_failed"),
        (_Stream(error=MissingCredentialError("missing")), None, "reauth_required"),
        (_Stream(error=RuntimeError("boom")), None, "provider_call_failed"),
        (None, RuntimeError("build failed"), "provider_call_failed"),
    ],
)
def test_canary_timeout_and_bare_raise_never_500(
    monkeypatch, tmp_path, stream, driver_error, expected
):
    result, _, _ = _run(
        monkeypatch, tmp_path, active=_active("chatgpt_oauth"),
        stream=stream, driver_error=driver_error, timeout_s=0.001,
    )
    assert result.error_code == expected
    if stream is not None:
        assert stream.closed is True


def test_dispatch_module_has_no_persistence_dependencies():
    import src.model_task_test as mt

    source = inspect.getsource(mt)
    assert "ResearchRun" not in source
    assert "ThreadStore" not in source
    assert "append_message" not in source


def test_no_secret_in_response(monkeypatch, tmp_path):
    secret = "sk-proj-this-must-never-escape-1234567890"
    stream = _Stream([AgentEvent(EventType.error, {"error": f"denied {secret}"})])
    result, _, _ = _run(
        monkeypatch, tmp_path, active=_active("chatgpt_oauth"), stream=stream,
    )
    assert secret not in result.model_dump_json()
    assert "REDACTED" in result.model_dump_json()


def test_task_test_route_shape(monkeypatch, tmp_path):
    from src.api.routes import config_routes as cr

    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    paths = {getattr(route, "path", None) for route in cr.router.routes}
    assert "/config/model-task-test" in paths

    with pytest.raises(ValidationError):
        cr.TaskModelTestRequest(
            task="unknown", provider="openai", model="gpt-5.4-mini", effort="low"
        )
    with pytest.raises(ValidationError):
        cr.TaskModelTestRequest(
            task="ai_research", provider="other", model="gpt-5.4-mini", effort="low"
        )

    expected = {
        "task", "provider", "model", "effort", "auth_mode", "credential_id",
        "status", "error_code", "latency_ms", "tested_at", "fallback_effort", "warning",
    }
    monkeypatch.setattr(
        cr, "dispatch_task_model_test",
        lambda **_kw: asyncio.sleep(0, result=SimpleNamespace(
            model_dump=lambda: {key: None for key in expected}
        )),
    )
    out = cr.run_task_model_test(
        cr.TaskModelTestRequest(
            task="ai_research", provider="openai", model="gpt-5.4-mini", effort="low"
        ),
        store=_Store(tmp_path / "profile_state.db"),
        token_store=object(),
    )
    assert set(out) == expected
