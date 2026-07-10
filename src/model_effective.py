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


@dataclass(frozen=True)
class ActiveCredential:
    provider: str
    credential_id: str
    auth_mode: str
    secret_fingerprint: str


def task_auth_executable(
    task: str, provider: str, auth_mode: str | None, capability: ModelCapability
) -> bool:
    """Can (task, provider, auth_mode) actually execute this model? Fail closed."""
    if capability.provider != provider or not capability.runtime_ready:
        return False
    if auth_mode is None:
        return False
    if task in _CARD_TASKS:
        # Sync SDK clients: live_resolver resolves DB api_key or env fallback
        # only; OAuth fails closed; api_key_pool is unwired for direct calls.
        if auth_mode != "api_key":
            return False
        return capability.supports_tool_calling and capability.supports_structured_output
    if task == "ai_research":
        if auth_mode == "api_key":
            return capability.supports_tool_calling
        if auth_mode == "claude_code_oauth":
            return provider == "anthropic" and capability.supports_tool_calling
        if auth_mode == "chatgpt_oauth":
            return provider == "openai" and capability.supports_tool_calling
        return False  # api_key_pool / unknown modes
    return False


def _entry(cap_or_id: ModelCapability | str, badge: str | None) -> dict[str, Any]:
    if isinstance(cap_or_id, str):
        return {"id": cap_or_id, "label": cap_or_id, "badge": badge}
    return {"id": cap_or_id.id, "label": cap_or_id.label, "badge": badge}


def effective_model_view(
    *,
    cache: ModelDiscoveryCache,
    routes: dict[str, Any],
    credentials: dict[str, ActiveCredential | None],
) -> dict[str, Any]:
    """Build the per-task verified/advanced partition for the Settings picker."""
    tasks_out: dict[str, Any] = {}
    for task in _TASKS:
        route = routes.get(task)
        provider = getattr(route, "provider", None) or "anthropic"
        route_model = getattr(route, "model", "") or ""
        cred = credentials.get(provider)

        if cred is None:
            scope_status, discovered_at, visible_ids = "never_discovered", None, set()
        else:
            scope = cache.get(
                provider=provider,
                auth_mode=cred.auth_mode,
                credential_id=cred.credential_id,
                secret_fingerprint=cred.secret_fingerprint,
            )
            scope_status = scope.status
            discovered_at = scope.discovered_at
            visible_ids = {m.model_id for m in scope.models}

        auth_mode = cred.auth_mode if cred else None
        verified: list[dict[str, Any]] = []
        advanced: list[dict[str, Any]] = []
        seen: set[str] = set()

        # Verified: walk the DISCOVERED ids (providers return dated snapshots —
        # review MF4), classify each via capability_for, and keep the provider's
        # REAL executable id in the option. Registry-unknown ids never enter
        # here or advanced (review MF5) — the custom input / route pin is their
        # only path.
        canonical_verified: set[str] = set()
        for model_id in sorted(visible_ids):
            cap = capability_for(model_id)
            if cap is None or cap.id in canonical_verified:
                continue
            if cap.picker_visibility == "default" \
                    and task_auth_executable(task, provider, auth_mode, cap):
                entry = _entry(cap, None)
                entry["id"] = model_id       # the id the provider actually serves
                verified.append(entry)
                canonical_verified.add(cap.id)
                seen.add(model_id)

        # Advanced: previous-generation path (advanced visibility) always
        # offered; default-visibility models surface as seeds ONLY when the
        # channel cannot live-list (seed_only) or was never discovered —
        # pinned_only models never appear here.
        for cap in all_models(provider):
            if cap.id in canonical_verified or cap.id in seen:
                continue
            if cap.picker_visibility == "advanced":
                advanced.append(_entry(cap, "advanced"))
                seen.add(cap.id)
            elif cap.picker_visibility == "default" and scope_status in (
                "seed_only", "never_discovered",
            ):
                advanced.append(_entry(cap, "seed"))
                seen.add(cap.id)

        # The saved route model is ALWAYS selectable (flagged, never hidden).
        if route_model and route_model not in seen \
                and not any(m["id"] == route_model for m in verified):
            advanced.append(_entry(
                capability_for(route_model) or route_model, "route",
            ))
            # keep the route entry's id stable even when a registry label exists
            advanced[-1]["id"] = route_model

        tasks_out[task] = {
            "verified": verified,
            "advanced": advanced,
            "cache_state": scope_status,
            "discovered_at": discovered_at,
        }
    return {"tasks": tasks_out}
