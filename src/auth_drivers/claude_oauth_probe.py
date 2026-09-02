"""One-call Settings probe for Claude setup-token subscription credentials.

The probe reuses the shipped structured-output adapter so runtime admission,
bundled-CLI selection, child-environment isolation, and ``apiKeySource``
verification cannot drift from the real fixed-task path.
"""

from __future__ import annotations

from typing import Any, Callable

from .probe_harness import run_probe
from .subscription_structured_output import run_subscription_structured_output

_PROBE_NAME = "Claude subscription auth source and structured output"
_PROBE_SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
    "additionalProperties": False,
}


def _run_subscription_probe(
    *,
    credential_id: str,
    token_store: Any,
    structured_output_fn: Callable[..., dict[str, Any]],
) -> tuple[bool, str]:
    payload = structured_output_fn(
        provider="anthropic",
        auth_mode="claude_code_oauth",
        credential_id=credential_id,
        model="claude-sonnet-5",
        system="Return the requested structured credential-probe result only.",
        user="Set ok to true. Do not use tools.",
        output_name="claude_subscription_probe",
        output_description="A bounded Claude subscription credential check.",
        schema=_PROBE_SCHEMA,
        effort="low",
        token_store=token_store,
        timeout_s=120.0,
    )
    if payload != {"ok": True}:
        return False, "unexpected structured result"
    return True, "verified subscription auth source and structured result"


def run_claude_code_oauth_probe(
    *,
    credential_id: str,
    token_store: Any,
    structured_output_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run one bounded Claude subscription call; never retry or fall back."""
    call = structured_output_fn or run_subscription_structured_output
    result = run_probe(
        _PROBE_NAME,
        expected="subscription source verified and structured result returned",
        fn=lambda: _run_subscription_probe(
            credential_id=credential_id,
            token_store=token_store,
            structured_output_fn=call,
        ),
    )
    return {"passed": bool(result.passed), "probes": [result.model_dump()]}
