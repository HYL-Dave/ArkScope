"""LLM auth driver contracts, concrete API-key drivers and factory."""

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
from .factory import build_driver
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
