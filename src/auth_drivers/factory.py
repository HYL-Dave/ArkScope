"""Resolve concrete auth drivers without changing provider or credential mode."""

from __future__ import annotations

from typing import Any, Optional

from .protocol import AuthDriver

# Provider-specific allowed modes — NOT a cartesian product. The product matrix
# is api_key + the provider's OWN OAuth mode; api_key_pool stays as an
# internal/env-compat mode (NOT a primary "create credential" UI mode). A
# provider's wrong OAuth mode (openai+claude_code_oauth, anthropic+chatgpt_oauth)
# is rejected, never silently accepted.
_ALLOWED_MODES = {
    "openai": frozenset({"api_key", "api_key_pool", "chatgpt_oauth"}),
    "anthropic": frozenset({"api_key", "api_key_pool", "claude_code_oauth"}),
}


def build_driver(
    *,
    provider: str,
    auth_mode: str,
    credential: Any = None,
    token_store: Optional[Any] = None,
    registry: Any = None,
    dal: Any = None,
    max_turns: Optional[int] = None,
    timeout_s: Optional[float] = None,
    per_tool_timeout_s: Optional[float] = None,
    observation_store: Optional[Any] = None,
) -> AuthDriver:
    """Build the selected driver; reject unknown modes and cross-provider OAuth."""
    if provider not in _ALLOWED_MODES:
        raise ValueError(f"unknown provider: {provider!r} (expected one of {sorted(_ALLOWED_MODES)})")
    known_modes = frozenset().union(*_ALLOWED_MODES.values())
    if auth_mode not in known_modes:
        raise ValueError(f"unknown auth_mode: {auth_mode!r} (expected one of {sorted(known_modes)})")
    if auth_mode not in _ALLOWED_MODES[provider]:
        raise ValueError(
            f"auth_mode {auth_mode!r} is not valid for provider {provider!r} "
            f"(allowed: {sorted(_ALLOWED_MODES[provider])})"
        )
    if auth_mode in ("api_key", "api_key_pool"):
        from .api_key_drivers import AnthropicApiKeyDriver, OpenAIApiKeyDriver

        secret = getattr(credential, "secret", None)
        cid = f"local:{credential.id}" if credential is not None and getattr(credential, "id", None) is not None else None
        cls = OpenAIApiKeyDriver if provider == "openai" else AnthropicApiKeyDriver
        return cls(api_key=secret, auth_mode=auth_mode, credential_id=cid)
    # Research injects registry/dal for the in-process bridge. This SDK driver
    # owns bundled-binary admission; external PATH CLIs are not a transport.
    if provider == "anthropic" and auth_mode == "claude_code_oauth":
        from .claude_code_sdk_driver import AnthropicClaudeCodeSdkDriver
        from .oauth_status import default_oauth_observation_store

        return AnthropicClaudeCodeSdkDriver(
            credential=credential, token_store=token_store, registry=registry, dal=dal,
            observation_store=(
                observation_store
                if observation_store is not None
                else default_oauth_observation_store()
            ),
            **({"max_turns": max_turns} if max_turns is not None else {}),
            **({"timeout_s": timeout_s} if timeout_s is not None else {}),
            **({"per_tool_timeout_s": per_tool_timeout_s} if per_tool_timeout_s is not None else {}),
        )
    # ChatGPT Research uses its Responses stream, independently of the API-key SDK.
    if provider == "openai" and auth_mode == "chatgpt_oauth":
        from .chatgpt_oauth_driver import OpenAIChatGPTOAuthDriver

        return OpenAIChatGPTOAuthDriver(
            credential=credential,
            token_store=token_store,
            registry=registry,
            dal=dal,
            **({"max_turns": max_turns} if max_turns is not None else {}),
            **({"timeout_s": timeout_s} if timeout_s is not None else {}),
            **({"per_tool_timeout_s": per_tool_timeout_s} if per_tool_timeout_s is not None else {}),
        )
    raise RuntimeError(f"unhandled admitted driver: {provider}/{auth_mode}")
