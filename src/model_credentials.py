"""Provider credential status, model discovery, and live model tests.

Secrets stay outside the UI. This module reads API keys from the current
environment/config/.env, returns only masked labels, and only uses API-key
credentials for live discovery/tests. OAuth/setup-token credential types are
represented so the Settings UI can model them, but they are not treated as
direct API credentials until their provider-specific flow is implemented.
"""

from __future__ import annotations

import os
import time
from typing import Literal

import httpx
from pydantic import BaseModel

from src.env_keys import ensure_env_loaded
from src.model_routing import MODEL_CATALOG, Provider

CredentialAuthType = Literal["api_key", "api_key_pool", "oauth", "setup_token"]
DiscoveryStatus = Literal["ok", "missing_credential", "unsupported", "error"]


class ProviderCredential(BaseModel):
    id: str
    provider: Provider
    auth_type: CredentialAuthType
    label: str
    source: str
    available: bool
    masked: str | None = None
    can_discover_models: bool = False
    can_test_models: bool = False
    notes: str = ""


class DiscoveredModel(BaseModel):
    id: str
    provider: Provider
    label: str
    source: Literal["provider_api", "seed"]


class ModelDiscoveryResult(BaseModel):
    provider: Provider
    credential_id: str | None
    status: DiscoveryStatus
    models: list[DiscoveredModel]
    error: str | None = None
    source_url: str | None = None


class ModelTestResult(BaseModel):
    provider: Provider
    credential_id: str | None
    model: str
    effort: str
    status: Literal["ok", "missing_credential", "error"]
    latency_ms: int | None = None
    error: str | None = None
    warning: str | None = None
    fallback_effort: str | None = None


class _ResolvedCredential(BaseModel):
    id: str
    provider: Provider
    auth_type: CredentialAuthType
    secret: str | None = None


def _mask_secret(value: str) -> str:
    if len(value) <= 10:
        return "••••"
    return f"{value[:4]}…{value[-4:]}"


def _split_key_pool(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _seed_models(provider: Provider) -> list[DiscoveredModel]:
    return [
        DiscoveredModel(id=m.id, provider=provider, label=m.label, source="seed")
        for m in MODEL_CATALOG
        if m.provider == provider
    ]


def looks_like_effort_error(exc: Exception) -> bool:
    """Heuristic for provider errors caused by an unsupported effort parameter."""
    text = str(exc).lower()
    needles = (
        "effort",
        "reasoning_effort",
        "output_config",
        "thinking",
        "unsupported parameter",
        "unknown parameter",
        "invalid parameter",
        "extra inputs are not permitted",
    )
    return any(needle in text for needle in needles)


def provider_credentials() -> dict[Provider, list[ProviderCredential]]:
    """Return masked credential inventory grouped by provider."""
    ensure_env_loaded()
    out: dict[Provider, list[ProviderCredential]] = {"anthropic": [], "openai": []}

    def add_api_key(provider: Provider, env_name: str, label: str) -> None:
        value = os.environ.get(env_name, "").strip()
        out[provider].append(
            ProviderCredential(
                id=f"{provider}:{env_name}",
                provider=provider,
                auth_type="api_key",
                label=label,
                source=env_name,
                available=bool(value),
                masked=_mask_secret(value) if value else None,
                can_discover_models=bool(value),
                can_test_models=bool(value),
                notes="Direct provider API key from environment/config/.env.",
            )
        )

    def add_key_pool(provider: Provider, env_name: str) -> None:
        for idx, value in enumerate(_split_key_pool(os.environ.get(env_name))):
            out[provider].append(
                ProviderCredential(
                    id=f"{provider}:{env_name}:{idx}",
                    provider=provider,
                    auth_type="api_key_pool",
                    label=f"{env_name}[{idx}]",
                    source=env_name,
                    available=True,
                    masked=_mask_secret(value),
                    can_discover_models=True,
                    can_test_models=True,
                    notes="Direct provider API key from a comma-separated key pool.",
                )
            )

    add_api_key("openai", "OPENAI_API_KEY", "OpenAI API key")
    add_key_pool("openai", "OPENAI_API_KEYS")
    add_api_key("anthropic", "ANTHROPIC_API_KEY", "Anthropic API key")
    add_key_pool("anthropic", "ANTHROPIC_API_KEYS")

    for provider, env_name, auth_type, notes in [
        (
            "openai",
            "OPENAI_OAUTH_TOKEN",
            "oauth",
            "OAuth token placeholder. Not used for direct OpenAI API model discovery/test in v0.",
        ),
        (
            "anthropic",
            "ANTHROPIC_OAUTH_TOKEN",
            "oauth",
            "OAuth token placeholder. Not used for direct Anthropic API model discovery/test in v0.",
        ),
        (
            "anthropic",
            "ANTHROPIC_SETUP_TOKEN",
            "setup_token",
            "Setup-token placeholder for future Claude flows; not a direct API key in v0.",
        ),
    ]:
        value = os.environ.get(env_name, "").strip()
        out[provider].append(
            ProviderCredential(
                id=f"{provider}:{env_name}",
                provider=provider,  # type: ignore[arg-type]
                auth_type=auth_type,  # type: ignore[arg-type]
                label=env_name,
                source=env_name,
                available=bool(value),
                masked=_mask_secret(value) if value else None,
                can_discover_models=False,
                can_test_models=False,
                notes=notes,
            )
        )

    return out


def _resolve_api_credential(provider: Provider, credential_id: str | None) -> _ResolvedCredential | None:
    ensure_env_loaded()
    creds = provider_credentials()[provider]
    usable = [c for c in creds if c.available and c.can_test_models]
    selected = next((c for c in usable if c.id == credential_id), None) if credential_id else (usable[0] if usable else None)
    if not selected:
        return None

    if selected.auth_type == "api_key":
        secret = os.environ.get(selected.source, "").strip()
    elif selected.auth_type == "api_key_pool":
        try:
            idx = int(selected.id.rsplit(":", 1)[-1])
        except ValueError:
            return None
        secret = _split_key_pool(os.environ.get(selected.source))[idx]
    else:
        return None
    return _ResolvedCredential(
        id=selected.id,
        provider=provider,
        auth_type=selected.auth_type,
        secret=secret,
    )


def discover_models(provider: Provider, credential_id: str | None = None) -> ModelDiscoveryResult:
    """Discover models for a provider/key when supported; fall back to seeds."""
    cred = _resolve_api_credential(provider, credential_id)
    if not cred or not cred.secret:
        return ModelDiscoveryResult(
            provider=provider,
            credential_id=credential_id,
            status="missing_credential",
            models=_seed_models(provider),
            error="No direct API-key credential is available for model discovery.",
        )

    try:
        if provider == "openai":
            from openai import OpenAI

            client = OpenAI(api_key=cred.secret, timeout=15)
            data = client.models.list()
            models = [
                DiscoveredModel(id=item.id, provider="openai", label=item.id, source="provider_api")
                for item in data.data
            ]
            return ModelDiscoveryResult(
                provider=provider,
                credential_id=cred.id,
                status="ok",
                models=sorted(models, key=lambda m: m.id),
                source_url="https://platform.openai.com/docs/api-reference/models/list",
            )
        headers = {"x-api-key": cred.secret, "anthropic-version": "2023-06-01"}
        resp = httpx.get("https://api.anthropic.com/v1/models", headers=headers, timeout=15)
        resp.raise_for_status()
        payload = resp.json()
        items = payload.get("data", [])
        models = [
            DiscoveredModel(
                id=item.get("id", ""),
                provider="anthropic",
                label=item.get("display_name") or item.get("id", ""),
                source="provider_api",
            )
            for item in items
            if item.get("id")
        ]
        return ModelDiscoveryResult(
            provider=provider,
            credential_id=cred.id,
            status="ok",
            models=sorted(models, key=lambda m: m.id),
            source_url="https://docs.anthropic.com/en/api/models-list",
        )
    except Exception as exc:  # pragma: no cover - live provider variability
        return ModelDiscoveryResult(
            provider=provider,
            credential_id=cred.id,
            status="error",
            models=_seed_models(provider),
            error=str(exc),
        )


def test_model(
    provider: Provider,
    model: str,
    effort: str = "default",
    credential_id: str | None = None,
) -> ModelTestResult:
    """Run a tiny paid provider call to verify credential/model/effort access."""
    cred = _resolve_api_credential(provider, credential_id)
    if not cred or not cred.secret:
        return ModelTestResult(
            provider=provider,
            credential_id=credential_id,
            model=model,
            effort=effort,
            status="missing_credential",
            error="No direct API-key credential is available for this test.",
        )

    started = time.perf_counter()

    def ok_result(*, warning: str | None = None, fallback_effort: str | None = None) -> ModelTestResult:
        return ModelTestResult(
            provider=provider,
            credential_id=cred.id,
            model=model,
            effort=effort,
            status="ok",
            latency_ms=round((time.perf_counter() - started) * 1000),
            warning=warning,
            fallback_effort=fallback_effort,
        )

    def run_once(selected_effort: str) -> None:
        if provider == "openai":
            from openai import OpenAI

            kwargs = {}
            if selected_effort != "default":
                kwargs["reasoning_effort"] = selected_effort
            client = OpenAI(api_key=cred.secret, timeout=30)
            client.chat.completions.create(
                model=model,
                max_completion_tokens=16,
                messages=[{"role": "user", "content": "Reply with OK."}],
                **kwargs,
            )
            return

        from anthropic import Anthropic

        kwargs = {}
        if selected_effort != "default":
            kwargs["output_config"] = {"effort": selected_effort}
        client = Anthropic(api_key=cred.secret, timeout=30)
        client.messages.create(
            model=model,
            max_tokens=16,
            messages=[{"role": "user", "content": "Reply with OK."}],
            **kwargs,
        )

    try:
        run_once(effort)
        return ok_result()
    except Exception as exc:  # pragma: no cover - live provider variability
        if effort != "default" and looks_like_effort_error(exc):
            try:
                run_once("default")
                return ok_result(
                    warning=(
                        f"Provider rejected effort '{effort}', but the model worked "
                        "after falling back to provider default."
                    ),
                    fallback_effort="default",
                )
            except Exception as fallback_exc:
                exc = fallback_exc
        return ModelTestResult(
            provider=provider,
            credential_id=cred.id,
            model=model,
            effort=effort,
            status="error",
            latency_ms=round((time.perf_counter() - started) * 1000),
            error=str(exc),
        )
