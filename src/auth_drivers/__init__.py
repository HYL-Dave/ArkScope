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
from .api_key_drivers import (
    AnthropicApiKeyDriver,
    MissingCredentialError,
    OpenAIApiKeyDriver,
)
from .factory import NotImplementedDriver, build_driver
from .token_store import (
    KeyringTokenStore,
    PlaintextTokenStore,
    StoredTokenRecord,
    get_token_store,
)

__all__ = [
    "AnthropicApiKeyDriver",
    "AuthDriver",
    "AuthMode",
    "DiscoveredModel",
    "KeyringTokenStore",
    "MissingCredentialError",
    "NotImplementedDriver",
    "OpenAIApiKeyDriver",
    "build_driver",
    "LLMRequest",
    "LLMResponse",
    "ModelDiscoveryResult",
    "ModelTestResult",
    "PlaintextTokenStore",
    "Provider",
    "ResearchProviderDriver",
    "StoredTokenRecord",
    "TokenUsage",
    "get_token_store",
]
