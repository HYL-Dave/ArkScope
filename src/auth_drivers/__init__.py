"""LLM auth drivers (S0 — interface only). See docs/design/LLM_AUTH_DRIVER_PLAN.md."""

from src.model_credentials import DiscoveredModel, ModelDiscoveryResult, ModelTestResult

from .protocol import (
    AuthDriver,
    AuthMode,
    LLMRequest,
    LLMResponse,
    Provider,
    ResearchProviderDriver,
    TokenUsage,
)

__all__ = [
    "AuthDriver",
    "AuthMode",
    "DiscoveredModel",
    "LLMRequest",
    "LLMResponse",
    "ModelDiscoveryResult",
    "ModelTestResult",
    "Provider",
    "ResearchProviderDriver",
    "TokenUsage",
]
