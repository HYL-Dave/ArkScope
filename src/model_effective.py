"""Per-task effective model view (P2.7): registry ∩ discovery ∩ executability.

The picker's default list is the intersection of three independent facts:
1. the model is default-visibility in the code registry (picker policy),
2. the ACTIVE credential for that task's provider has actually SEEN it
   (discovery cache, fingerprint-scoped),
3. the (task, auth_mode) pair can actually execute it (fail-closed contract
   grounded in live_resolver behavior: cards use sync SDK clients that resolve
   api_key only; api_key_pool is unwired for direct calls; AI research streams
   through api_key or the provider's own OAuth driver).

Everything else the user might still legitimately choose (advanced-visibility
previous generation, custom ids, the saved route's pin, seed candidates on
channels with no live listing) lands in `advanced` with an explicit badge —
shown on demand, never silently promoted to verified.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.model_capabilities import ModelCapability, all_models, capability_for
from src.model_discovery_cache import ModelDiscoveryCache

_CARD_TASKS = ("card_synthesis", "card_translation")
_TASKS = ("card_synthesis", "card_translation", "ai_research")
_PROVIDERS = ("openai", "anthropic")


@dataclass(frozen=True)
class ActiveCredential:
    provider: str
    credential_id: str
    auth_mode: str
    secret_fingerprint: str


def task_capability_ok(task: str, capability: ModelCapability) -> bool:
    """Can the model itself satisfy ``task``? Auth is deliberately separate."""
    if not capability.runtime_ready:
        return False
    if task in _CARD_TASKS:
        return capability.supports_tool_calling and capability.supports_structured_output
    if task == "ai_research":
        return capability.supports_tool_calling
    return False


def _task_auth_mode_ok(task: str, provider: str, auth_mode: str | None) -> bool:
    if auth_mode is None:
        return False
    if task in _CARD_TASKS:
        # Sync SDK clients resolve a single api_key only.
        return auth_mode == "api_key"
    if task == "ai_research":
        return (
            auth_mode == "api_key"
            or (provider == "anthropic" and auth_mode == "claude_code_oauth")
            or (provider == "openai" and auth_mode == "chatgpt_oauth")
        )
    return False


def task_auth_executable(
    task: str, provider: str, auth_mode: str | None, capability: ModelCapability
) -> bool:
    """Can (task, provider, auth_mode) actually execute this model? Fail closed."""
    return (
        capability.provider == provider
        and _task_auth_mode_ok(task, provider, auth_mode)
        and task_capability_ok(task, capability)
    )


def _provider_execution(
    task: str, provider: str, credential: ActiveCredential | None,
) -> tuple[bool, str | None]:
    if credential is None:
        return False, "missing_active_credential"
    if not _task_auth_mode_ok(task, provider, credential.auth_mode):
        return False, "task_auth_mode_unsupported"
    return True, None


def _model_eligibility(
    *,
    task: str,
    provider: str,
    provider_reason: str | None,
    capability: ModelCapability | None,
) -> tuple[bool, str | None]:
    if provider_reason is not None:
        return False, provider_reason
    if capability is None:
        return True, "model_not_in_registry"
    if capability.provider != provider or not task_capability_ok(task, capability):
        return False, "task_capability_missing"
    return True, None


def _v2_entry(
    *,
    model_id: str,
    label: str,
    status: str,
    visible_to_credential: bool | None,
    task: str,
    provider: str,
    provider_reason: str | None,
    capability: ModelCapability | None,
) -> dict[str, Any]:
    eligible, reason = _model_eligibility(
        task=task,
        provider=provider,
        provider_reason=provider_reason,
        capability=capability,
    )
    return {
        "id": model_id,
        "label": label,
        "status": status,
        "visible_to_credential": visible_to_credential,
        "eligible": eligible,
        "reason_code": reason,
        "thinking_mode": capability.thinking_mode if capability is not None else "none",
    }


def effective_model_view_v2(
    *,
    cache: ModelDiscoveryCache,
    routes: dict[str, Any],
    credentials: dict[str, ActiveCredential | None],
) -> dict[str, Any]:
    """Build the provider-indexed effective picker from one scope read/provider."""
    scopes: dict[str, dict[str, Any]] = {}
    providers_out: dict[str, Any] = {}
    for provider in _PROVIDERS:
        credential = credentials.get(provider)
        if credential is None:
            scopes[provider] = {
                "status": "never_discovered",
                "discovered_at": None,
                "real_ids": set(),
                "canonical_ids": set(),
                "real_default_by_capability": {},
            }
            providers_out[provider] = None
            continue
        scope = cache.get(
            provider=provider,
            auth_mode=credential.auth_mode,
            credential_id=credential.credential_id,
            secret_fingerprint=credential.secret_fingerprint,
        )
        real_ids = {model.model_id for model in scope.models}
        canonical_ids: set[str] = set()
        real_default_by_capability: dict[str, str] = {}
        for model_id in sorted(real_ids):
            capability = capability_for(model_id)
            if capability is None or capability.provider != provider:
                continue
            canonical_ids.add(capability.id)
            if capability.picker_visibility == "default":
                real_default_by_capability.setdefault(capability.id, model_id)
        scopes[provider] = {
            "status": scope.status,
            "discovered_at": scope.discovered_at,
            "real_ids": real_ids,
            "canonical_ids": canonical_ids,
            "real_default_by_capability": real_default_by_capability,
        }
        providers_out[provider] = {
            "credential_id": credential.credential_id,
            "auth_mode": credential.auth_mode,
        }

    tasks_out: dict[str, Any] = {}
    for task in _TASKS:
        route = routes.get(task)
        current_provider = getattr(route, "provider", None) or "anthropic"
        route_model = getattr(route, "model", "") or ""
        provider_blocks: dict[str, Any] = {}
        for provider in _PROVIDERS:
            credential = credentials.get(provider)
            scope = scopes[provider]
            provider_ok, provider_reason = _provider_execution(task, provider, credential)
            scope_status = scope["status"]
            if scope_status == "ok":
                visible_for = lambda cap: cap.id in scope["canonical_ids"]
            else:
                visible_for = lambda _cap: None

            entries: list[dict[str, Any]] = []
            seen_ids: set[str] = set()

            if scope_status == "ok":
                for capability_id, real_id in sorted(scope["real_default_by_capability"].items()):
                    capability = capability_for(capability_id)
                    if capability is None:
                        continue
                    entries.append(_v2_entry(
                        model_id=real_id,
                        label=capability.label,
                        status="visible",
                        visible_to_credential=True,
                        task=task,
                        provider=provider,
                        provider_reason=provider_reason,
                        capability=capability,
                    ))
                    seen_ids.add(real_id)
            else:
                for capability in all_models(provider):
                    if capability.picker_visibility != "default":
                        continue
                    entries.append(_v2_entry(
                        model_id=capability.id,
                        label=capability.label,
                        status="seed",
                        visible_to_credential=None,
                        task=task,
                        provider=provider,
                        provider_reason=provider_reason,
                        capability=capability,
                    ))
                    seen_ids.add(capability.id)

            for capability in all_models(provider):
                if capability.picker_visibility != "advanced":
                    continue
                entries.append(_v2_entry(
                    model_id=capability.id,
                    label=capability.label,
                    status="advanced",
                    visible_to_credential=visible_for(capability),
                    task=task,
                    provider=provider,
                    provider_reason=provider_reason,
                    capability=capability,
                ))
                seen_ids.add(capability.id)

            if provider == current_provider and route_model and route_model not in seen_ids:
                capability = capability_for(route_model)
                if scope_status == "ok":
                    route_visible = (
                        capability.id in scope["canonical_ids"]
                        if capability is not None
                        else route_model in scope["real_ids"]
                    )
                else:
                    route_visible = None
                entries.append(_v2_entry(
                    model_id=route_model,
                    label=capability.label if capability is not None else route_model,
                    status="route",
                    visible_to_credential=route_visible,
                    task=task,
                    provider=provider,
                    provider_reason=provider_reason,
                    capability=capability,
                ))

            provider_blocks[provider] = {
                "executable": provider_ok,
                "reason_code": provider_reason,
                "models": entries,
                "cache_state": scope_status,
                "discovered_at": scope["discovered_at"],
            }
        tasks_out[task] = {
            "current_provider": current_provider,
            "providers": provider_blocks,
        }
    return {"providers": providers_out, "tasks": tasks_out}


def legacy_effective_alias(v2: dict[str, Any]) -> dict[str, Any]:
    """Fold one already-computed v2 view into the P2.7 compatibility shape."""
    tasks_out: dict[str, Any] = {}
    for task, task_block in v2["tasks"].items():
        block = task_block["providers"][task_block["current_provider"]]
        tasks_out[task] = {
            "verified": [
                {"id": entry["id"], "label": entry["label"], "badge": None}
                for entry in block["models"]
                if entry["status"] == "visible" and entry["eligible"]
            ],
            "advanced": [
                {"id": entry["id"], "label": entry["label"], "badge": entry["status"]}
                for entry in block["models"]
                if entry["status"] in {"advanced", "seed", "route"}
            ],
            "cache_state": block["cache_state"],
            "discovered_at": block["discovered_at"],
        }
    return {"tasks": tasks_out}


def effective_model_view(
    *,
    cache: ModelDiscoveryCache,
    routes: dict[str, Any],
    credentials: dict[str, ActiveCredential | None],
) -> dict[str, Any]:
    """Legacy task-level alias, derived from the provider-indexed v2 view."""
    return legacy_effective_alias(
        effective_model_view_v2(cache=cache, routes=routes, credentials=credentials),
    )
