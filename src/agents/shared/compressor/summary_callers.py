"""Layer 5 summary callers (P1.4 commit 5).

Pluggable interface for "give me a summary of this transcript". The
default implementation calls Anthropic's cheap-tier model directly via
the SDK (no agent runner involved — library-not-runner guarantee from
spec §1.2 #1).

OpenAI caller is intentionally NOT included in commit 5: the OpenAI
agent path runs through the agents-SDK Runner and does not currently
build messages locally (so ContextManager doesn't see those messages
either). Wiring an OpenAISummaryCaller without a corresponding agent
hook would be a dead adapter — added when the unified runner work
needs it, not before.

Failure semantics: any exception during the LLM call is caught and
logged; the caller returns ``None``. Caller failure ↔ ContextCompressor
increments the circuit-breaker counter; 3 consecutive Nones disable
Layer 5 for the session.
"""

from __future__ import annotations

import logging
from typing import Optional, Protocol

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class SummaryCaller(Protocol):
    """Pluggable LLM call for Layer 5.

    Implementations MUST:
      - return the summary text on success
      - return ``None`` on any failure (catch + log; do not raise)
      - apply NO content transformations beyond what the LLM produced
        (caller is dumb pipe; the prompt + cap_summary in
        :mod:`summary_prompt` handle policy)
    """

    def __call__(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> Optional[str]: ...


# ---------------------------------------------------------------------------
# Anthropic implementation
# ---------------------------------------------------------------------------


# Default summary model — cheap tier (Sonnet, not Opus). spec §8 lock.
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-6"

# Output cap for the summary call. The prompt asks for ≤2000 words; we
# leave headroom for thinking tokens + output. 8K tokens ≈ 6K words is
# more than enough for a legal-sized summary.
DEFAULT_ANTHROPIC_MAX_TOKENS = 8_000


class AnthropicSummaryCaller:
    """Call Anthropic's cheap-tier model to produce a Layer 5 summary.

    Uses streaming (``client.messages.stream``) to dodge the SDK's
    non-streaming ``max_tokens > 21333`` ValueError. We never reach
    that limit at 8K tokens, but streaming is the safer default and
    the response shape is the same.
    """

    def __init__(
        self,
        *,
        model: str = DEFAULT_ANTHROPIC_MODEL,
        max_tokens: int = DEFAULT_ANTHROPIC_MAX_TOKENS,
        client: Optional[object] = None,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self._client = client  # tests inject a fake; production lazily builds

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise RuntimeError(
                "anthropic SDK not installed — cannot run Layer 5 summary call"
            ) from exc
        from src.auth_drivers.live_resolver import live_anthropic_client
        self._client = live_anthropic_client()
        return self._client

    def __call__(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> Optional[str]:
        try:
            client = self._get_client()
            with client.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            ) as stream:
                response = stream.get_final_message()
        except Exception as exc:
            logger.warning(
                "Layer 5 Anthropic summary call failed (model=%s): %s",
                self.model, exc,
            )
            return None

        # Concatenate all text blocks. Thinking blocks (if any) are
        # ignored — the summarizer's reasoning is not the summary.
        parts = []
        for block in getattr(response, "content", []) or []:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                parts.append(text)
        result = "".join(parts).strip()
        if not result:
            logger.warning("Layer 5 summary call returned empty text")
            return None
        return result


# ---------------------------------------------------------------------------
# Test helpers (no production use)
# ---------------------------------------------------------------------------


class FakeSummaryCaller:
    """Test helper. Returns a queued sequence of values; ``None`` simulates
    a failure for circuit-breaker testing.

    Usage::

        caller = FakeSummaryCaller(["summary v1", None, "summary v2"])
        # First call returns "summary v1", second returns None (failure),
        # third returns "summary v2". Subsequent calls raise IndexError
        # so tests catch unexpected over-invocation.
    """

    def __init__(self, queued):
        self._queue = list(queued)
        self.calls: list[dict] = []

    def __call__(self, *, system_prompt: str, user_prompt: str) -> Optional[str]:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        if not self._queue:
            raise IndexError("FakeSummaryCaller queue exhausted")
        return self._queue.pop(0)