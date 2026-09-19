"""One fixed-card selection; only its closed receipt may leave memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict

from src.agents.config import get_agent_config
from src.auth_drivers.runtime_binding import RuntimeAuthBinding, capture_runtime_auth
from src.model_capabilities import model_execution_admission_detail
from src.model_routing import TaskRoute, default_model_for


class ExecutionReceipt(BaseModel):
    """ArkScope's sent selection, not provider-attested identity. Nulls are legacy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str | None = None
    model: str | None = None
    effort: str | None = None
    auth_mode: Literal["api_key", "chatgpt_oauth", "claude_code_oauth"] | None = None


class CardExecutionAdmissionError(ValueError):
    """Preserve the closed model/task/auth admission detail through HTTP mapping."""

    def __init__(self, detail: dict[str, str]):
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class CardExecution:
    task: str
    provider: str
    model: str
    effort: str
    auth: RuntimeAuthBinding = field(repr=False, compare=False)

    @property
    def receipt(self) -> ExecutionReceipt:
        return ExecutionReceipt(
            provider=self.provider, model=self.model, effort=self.effort,
            auth_mode=self.auth.auth_mode,
        )


def capture_card_execution(
    task: str, route: TaskRoute, *, provider: str | None = None,
    model: str | None = None,
) -> CardExecution:
    """Snapshot the supplied complete route and auth, before gathering/scheduling.

    Deliberate cross-provider overrides retain the existing provider defaults.
    This function never re-reads the task route or substitutes after a failure.
    """
    provider = (provider or route.provider).lower()
    if provider not in ("openai", "anthropic"):
        raise CardExecutionAdmissionError({"code": "unknown_provider", "field": "provider"})
    if provider == route.provider:
        model, effort = model or route.model, route.effort
    else:
        if task == "card_synthesis":
            config = get_agent_config()
            model = model or getattr(config, f"{provider}_model_advanced")
            effort = "high"
        else:
            model = model or default_model_for(provider, task)
            effort = "medium"
    detail = model_execution_admission_detail(model, task=task)
    if detail is not None:
        raise CardExecutionAdmissionError(detail)
    return CardExecution(task, provider, model, effort, capture_runtime_auth(provider))
