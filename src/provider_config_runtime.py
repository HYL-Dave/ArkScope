"""Runtime state for provider-config authority failures.

This state is process-local. It keeps the desktop sidecar useful when the
profile DB is unavailable: read-only setup/status surfaces remain up, but
provider work is refused until the app-managed provider config store is reachable.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException


@dataclass(frozen=True)
class ProviderConfigSetupState:
    required: bool
    code: str | None = None
    reason: str | None = None

    def as_dict(self) -> dict[str, str | bool | None]:
        return {"required": self.required, "code": self.code, "reason": self.reason}


_STATE = ProviderConfigSetupState(required=False)


def mark_provider_config_setup_required(reason: str) -> None:
    global _STATE
    _STATE = ProviderConfigSetupState(
        required=True,
        code="provider_config_setup_required",
        reason=reason[:500],
    )


def clear_provider_config_setup_required() -> None:
    global _STATE
    _STATE = ProviderConfigSetupState(required=False)


def provider_config_setup_state() -> ProviderConfigSetupState:
    return _STATE


def require_provider_config_ready(operation: str) -> None:
    state = provider_config_setup_state()
    if not state.required:
        return
    raise HTTPException(
        status_code=503,
        detail={
            "code": "provider_config_setup_required",
            "status": "needs_setup",
            "operation": operation,
            "reason": state.reason,
        },
    )
