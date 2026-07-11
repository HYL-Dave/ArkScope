"""Bounded, task-aware model verification for the Settings Models surface.

The dispatcher deliberately has no research/thread persistence dependency. It
checks credential, auth-mode, model capability, and discovery visibility before
making one explicit provider call.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel

from src.agents.shared.events import EventType
from src.auth_drivers.api_key_drivers import MissingCredentialError
from src.auth_drivers.factory import build_driver
from src.auth_drivers.probe_harness import redact
from src.auth_drivers.protocol import LLMRequest
from src.model_capabilities import capability_for
from src.model_credentials import resolve_active_credential, test_model
from src.model_discovery_cache import ModelDiscoveryCache
from src.model_effective import task_capability_ok
from src.model_routing import model_provider

_CARD_TASKS = frozenset({"card_synthesis", "card_translation"})


class TaskModelTestResult(BaseModel):
    task: str
    provider: str
    model: str
    effort: str
    auth_mode: str | None
    credential_id: str | None
    status: Literal["ok", "error", "unsupported"]
    error_code: str | None = None
    latency_ms: int | None = None
    tested_at: str
    fallback_effort: str | None = None
    warning: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(value: Any) -> str | None:
    if value is None:
        return None
    return redact(str(value))[:500]


def _result(
    *,
    task: str,
    provider: str,
    model: str,
    effort: str,
    active: Any,
    status: Literal["ok", "error", "unsupported"],
    error_code: str | None = None,
    latency_ms: int | None = None,
    fallback_effort: str | None = None,
    warning: Any = None,
) -> TaskModelTestResult:
    return TaskModelTestResult(
        task=task,
        provider=provider,
        model=model,
        effort=effort,
        auth_mode=getattr(active, "auth_mode", None),
        credential_id=getattr(active, "credential_id", None),
        status=status,
        error_code=error_code,
        latency_ms=latency_ms,
        tested_at=_now(),
        fallback_effort=fallback_effort,
        warning=_safe_text(warning),
    )


def _visibility_matches(requested_model: str, discovered_model: str) -> bool:
    requested = capability_for(requested_model)
    discovered = capability_for(discovered_model)
    if requested is not None and discovered is not None:
        return requested.id == discovered.id
    return requested_model == discovered_model


def _auth_veto(task: str, auth_mode: str) -> str | None:
    if auth_mode == "api_key_pool":
        return "task_test_unsupported"
    if task in _CARD_TASKS and auth_mode in {"chatgpt_oauth", "claude_code_oauth"}:
        return "task_auth_mode_unsupported"
    if task == "ai_research" and auth_mode == "claude_code_oauth":
        return "task_test_unsupported"
    if auth_mode not in {"api_key", "chatgpt_oauth"}:
        return "task_test_unsupported"
    return None


async def _run_oauth_canary(
    *,
    task: str,
    provider: str,
    model: str,
    effort: str,
    active: Any,
    store: Any,
    token_store: Any,
    timeout_s: float,
) -> TaskModelTestResult:
    started = time.perf_counter()
    stream = None
    try:
        credential = store.get(active.credential_id)
        if credential is None:
            return _result(
                task=task, provider=provider, model=model, effort=effort,
                active=active, status="error", error_code="missing_active_credential",
                warning="The active OAuth credential no longer exists.",
            )
        driver_timeout = min(max(float(timeout_s), 0.001), 45.0)
        driver = build_driver(
            provider=provider,
            auth_mode=active.auth_mode,
            credential=credential,
            token_store=token_store,
            registry=None,
            dal=None,
            max_turns=1,
            timeout_s=driver_timeout,
        )
        request = LLMRequest(
            model=model,
            instructions="This is a bounded availability check. Reply with exactly OK.",
            input_messages=[{"role": "user", "content": "Reply with exactly OK."}],
            reasoning_effort=None if effort == "default" else effort,
            max_output_tokens=16,
            tools=[],
        )
        stream = driver.stream_llm(request)

        async def consume():
            async for event in stream:
                if event.type in {EventType.tool_start, EventType.tool_end}:
                    return "unsupported", "task_test_unsupported", (
                        "The model attempted to use a tool during the bounded test."
                    )
                if event.type == EventType.error:
                    code = event.data.get("code")
                    error_code = "reauth_required" if code == "reauth_required" else "provider_call_failed"
                    detail = event.data.get("error") or event.data.get("message") or "Provider call failed."
                    return "error", error_code, detail
                if event.type == EventType.done:
                    return "ok", None, None
            return "error", "provider_call_failed", "Provider stream ended without a terminal result."

        status, error_code, warning = await asyncio.wait_for(consume(), timeout=timeout_s)
        return _result(
            task=task, provider=provider, model=model, effort=effort,
            active=active, status=status, error_code=error_code,
            latency_ms=round((time.perf_counter() - started) * 1000), warning=warning,
        )
    except MissingCredentialError as exc:
        return _result(
            task=task, provider=provider, model=model, effort=effort,
            active=active, status="error", error_code="reauth_required",
            latency_ms=round((time.perf_counter() - started) * 1000), warning=exc,
        )
    except asyncio.TimeoutError:
        return _result(
            task=task, provider=provider, model=model, effort=effort,
            active=active, status="error", error_code="provider_call_failed",
            latency_ms=round((time.perf_counter() - started) * 1000),
            warning=f"Model test timed out after {timeout_s:g} seconds.",
        )
    except Exception as exc:  # noqa: BLE001 - endpoint must return a classified result
        return _result(
            task=task, provider=provider, model=model, effort=effort,
            active=active, status="error", error_code="provider_call_failed",
            latency_ms=round((time.perf_counter() - started) * 1000), warning=exc,
        )
    finally:
        closer = getattr(stream, "aclose", None)
        if closer is not None:
            try:
                await closer()
            except Exception:  # noqa: BLE001 - teardown cannot replace the classified result
                pass


async def dispatch_task_model_test(
    *,
    task: str,
    provider: str,
    model: str,
    effort: str,
    store: Any,
    token_store: Any,
    timeout_s: float = 45.0,
) -> TaskModelTestResult:
    """Run one bounded test using the fixed five-step dispatch precedence."""
    active = resolve_active_credential(provider, store)
    if active is None or active.provider != provider:
        return _result(
            task=task, provider=provider, model=model, effort=effort,
            active=None, status="error", error_code="missing_active_credential",
            warning="No active credential is configured for this provider.",
        )

    auth_error = _auth_veto(task, active.auth_mode)
    if auth_error is not None:
        return _result(
            task=task, provider=provider, model=model, effort=effort,
            active=active, status="unsupported", error_code=auth_error,
        )

    capability = capability_for(model)
    inferred_provider = model_provider(model)
    if (
        inferred_provider is not None and inferred_provider != provider
    ) or (
        capability is not None
        and (capability.provider != provider or not task_capability_ok(task, capability))
    ):
        return _result(
            task=task, provider=provider, model=model, effort=effort,
            active=active, status="unsupported", error_code="task_capability_missing",
        )

    try:
        scope = ModelDiscoveryCache(store.db_path).get(
            provider=provider,
            auth_mode=active.auth_mode,
            credential_id=active.credential_id,
            secret_fingerprint=active.secret_fingerprint,
        )
    except Exception as exc:  # noqa: BLE001 - no billed call when visibility is unknown
        return _result(
            task=task, provider=provider, model=model, effort=effort,
            active=active, status="error", error_code="discovery_unavailable", warning=exc,
        )
    if scope.status == "ok" and not any(
        _visibility_matches(model, item.model_id) for item in scope.models
    ):
        return _result(
            task=task, provider=provider, model=model, effort=effort,
            active=active, status="unsupported", error_code="model_not_visible",
        )

    if active.auth_mode == "api_key":
        raw = test_model(
            provider,
            model,
            effort=effort,
            credential_id=active.credential_id,
            store=store,
        )
        if raw.status == "ok":
            return _result(
                task=task, provider=provider, model=model, effort=effort,
                active=active, status="ok", latency_ms=raw.latency_ms,
                fallback_effort=raw.fallback_effort, warning=raw.warning,
            )
        code = (
            "missing_active_credential"
            if raw.status == "missing_credential"
            else "provider_call_failed"
        )
        return _result(
            task=task, provider=provider, model=model, effort=effort,
            active=active, status="error", error_code=code,
            latency_ms=raw.latency_ms, fallback_effort=raw.fallback_effort,
            warning=raw.error or raw.warning,
        )

    return await _run_oauth_canary(
        task=task,
        provider=provider,
        model=model,
        effort=effort,
        active=active,
        store=store,
        token_store=token_store,
        timeout_s=timeout_s,
    )
