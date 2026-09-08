"""One selected transport per call, including both subscription channels."""

from src.auth_drivers.lifecycle_web_models import ModelCall, ModelReply, WebCredential, WebModelError
from src.security_lifecycle_web_contract import RunControl, channel_contract


async def call_lifecycle_web_model(call: ModelCall, credential: WebCredential, control: RunControl) -> ModelReply:
    call.__post_init__()
    if call.selection != credential.selection or call.selection != control.selection:
        raise WebModelError("execution_identity_changed")
    channel = channel_contract(call.selection.provider, call.selection.auth_mode)
    if channel.transport == "openai_responses":
        from src.auth_drivers.lifecycle_web_models import call_openai_web
        return await call_openai_web(call, credential, control)
    if channel.transport == "anthropic_messages":
        from src.auth_drivers.lifecycle_web_models import call_anthropic_web
        return await call_anthropic_web(call, credential, control)
    if channel.transport == "codex_app_server":
        from src.auth_drivers.lifecycle_web_codex import call_codex_web
        return await call_codex_web(call, credential, control)
    if channel.transport == "claude_agent_sdk":
        from src.auth_drivers.lifecycle_web_claude import call_claude_web
        return await call_claude_web(call, credential, control)
    raise WebModelError("web_auth_unsupported")
