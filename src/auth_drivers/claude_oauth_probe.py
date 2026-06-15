"""P3 probe — Claude setup-token (claude_code_oauth) — S4 Step 3.

Falsifiable proof of the C≠D distinction (LLM_AUTH_DRIVER_PLAN.md §9):
  P3a: `claude -p` with CLAUDE_CODE_OAUTH_TOKEN set (ANTHROPIC_API_KEY unset)
       completes → the subscription/Agent-SDK route works.
  P3b: passing the SAME token as a raw Anthropic() x-api-key is REJECTED → the
       setup-token is NOT an api.anthropic.com API key (so it must route via the
       CLI/Agent SDK, never the raw Messages API).

Both side effects are injectable (cli_fn / raw_sdk_fn) so the route + tests can
run without a live token. Results flow through the redacted probe harness — a
token can never leak into a ProbeResult, even from an exception. No persistence.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any, Callable

from .probe_harness import run_probe

_CLI_NAME = "P3a: claude -p works with the setup-token"
_SDK_NAME = "P3b: raw Anthropic SDK rejects the setup-token as x-api-key"


def _default_cli_probe(token: str) -> tuple[bool, str]:
    """Run `claude -p` with the OAuth token in env (ANTHROPIC_API_KEY unset), like
    code_generator._call_claude_cli(use_api_key=False). PASS = rc 0 with output.
    Returns SHAPE only (never the model output — the harness redacts regardless)."""
    if not shutil.which("claude"):
        return False, "claude CLI not installed (npm i -g @anthropic-ai/claude-code)"
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)  # force the subscription/OAuth path
    env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    proc = subprocess.run(
        ["claude", "-p", "--output-format", "text", "--max-turns", "1",
         "Reply with exactly: OK. Do not use any tools."],
        capture_output=True, text=True, env=env, timeout=120,
    )
    if proc.returncode == 0 and proc.stdout.strip():
        return True, f"claude -p exited rc=0 with {len(proc.stdout.strip())} chars of output"
    return False, f"claude -p exited rc={proc.returncode}; stderr: {proc.stderr}"


def _anthropic_client(token: str) -> Any:  # seam for tests
    from anthropic import Anthropic

    return Anthropic(api_key=token)


def _default_raw_sdk_reject_probe(token: str) -> tuple[bool, str]:
    """Pass the setup-token to the raw Anthropic SDK as an api_key. PASS = the
    call is REJECTED (proves the token is not an API key). If the call SUCCEEDS,
    the C≠D invariant is violated → FAIL."""
    try:
        client = _anthropic_client(token)
        client.messages.create(
            model="claude-haiku-4-5", max_tokens=1,
            messages=[{"role": "user", "content": "ping"}],
        )
    except Exception as exc:  # noqa: BLE001 — any rejection is the expected outcome
        return True, f"raw SDK rejected the token ({type(exc).__name__})"
    return False, "raw SDK ACCEPTED the setup-token as an API key — C≠D invariant violated"


def run_claude_code_oauth_probe(
    token: str,
    *,
    cli_fn: Callable[[], Any] | None = None,
    raw_sdk_fn: Callable[[], Any] | None = None,
) -> dict:
    """Run P3a + P3b through the redacted harness. Returns
    {passed: bool, probes: [<ProbeResult dict>, ...]} — never the token."""
    cli_fn = cli_fn or (lambda: _default_cli_probe(token))
    raw_sdk_fn = raw_sdk_fn or (lambda: _default_raw_sdk_reject_probe(token))
    p3a = run_probe(_CLI_NAME, expected="claude -p completes (rc 0, output)", fn=cli_fn)
    p3b = run_probe(_SDK_NAME, expected="rejected — token is not an API key", fn=raw_sdk_fn)
    return {"passed": bool(p3a.passed and p3b.passed), "probes": [p3a.model_dump(), p3b.model_dump()]}
