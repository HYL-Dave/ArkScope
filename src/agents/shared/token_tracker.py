"""
Token usage tracker for agent sessions.

Tracks per-turn and cumulative token usage across OpenAI and Anthropic API calls.
This is Phase 1 of the agent evolution roadmap — prerequisite for context management.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TurnUsage:
    """Token usage for a single API call."""

    turn: int
    provider: str  # "openai" or "anthropic"
    model: str
    input_tokens: int
    output_tokens: int
    timestamp: float = field(default_factory=time.time)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class TokenTracker:
    """
    Cumulative token usage tracker for an agent session.

    Usage:
        tracker = TokenTracker()

        # Anthropic — record after each messages.create() call
        response = client.messages.create(...)
        tracker.record_anthropic(response, model="claude-opus-4-6")

        # OpenAI — record after Runner.run() completes
        result = await Runner.run(agent, ...)
        tracker.record_openai_result(result, model="gpt-5.2")

        # Inspect
        print(tracker.total_input_tokens)
        print(tracker.summary())
    """

    def __init__(self) -> None:
        self._turns: List[TurnUsage] = []

    # ── Recording ──────────────────────────────────────────────

    def record(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> TurnUsage:
        """Record token usage for one API call."""
        usage = TurnUsage(
            turn=len(self._turns) + 1,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        self._turns.append(usage)
        return usage

    def record_anthropic(self, response: Any, model: str = "") -> Optional[TurnUsage]:
        """
        Record usage from an Anthropic messages.create() response.

        The response object has .usage with .input_tokens and .output_tokens.
        """
        usage = getattr(response, "usage", None)
        if usage is None:
            return None
        return self.record(
            provider="anthropic",
            model=model or getattr(response, "model", "unknown"),
            input_tokens=getattr(usage, "input_tokens", 0),
            output_tokens=getattr(usage, "output_tokens", 0),
        )

    def record_openai_result(self, result: Any, model: str = "") -> List[TurnUsage]:
        """
        Record usage from an OpenAI Agents SDK RunResult.

        Extracts usage from result.raw_responses, each of which may have .usage.
        """
        recorded = []
        raw_responses = getattr(result, "raw_responses", None)
        if not raw_responses:
            return recorded

        for resp in raw_responses:
            usage = getattr(resp, "usage", None)
            if usage is None:
                continue
            turn = self.record(
                provider="openai",
                model=model or getattr(resp, "model", "unknown"),
                input_tokens=getattr(usage, "input_tokens", 0)
                or getattr(usage, "prompt_tokens", 0),
                output_tokens=getattr(usage, "output_tokens", 0)
                or getattr(usage, "completion_tokens", 0),
            )
            recorded.append(turn)
        return recorded

    # ── Aggregated properties ──────────────────────────────────

    @property
    def total_input_tokens(self) -> int:
        return sum(t.input_tokens for t in self._turns)

    @property
    def total_output_tokens(self) -> int:
        return sum(t.output_tokens for t in self._turns)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def turn_count(self) -> int:
        return len(self._turns)

    @property
    def turns(self) -> List[TurnUsage]:
        return list(self._turns)

    @property
    def last_input_tokens(self) -> int:
        """Input tokens of the most recent turn (indicates current context size)."""
        if not self._turns:
            return 0
        return self._turns[-1].input_tokens

    # ── Summary ────────────────────────────────────────────────

    def summary(self) -> Dict[str, Any]:
        """Return a summary dict suitable for inclusion in agent response."""
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "turn_count": self.turn_count,
            "last_input_tokens": self.last_input_tokens,
        }

    def __repr__(self) -> str:
        return (
            f"TokenTracker(turns={self.turn_count}, "
            f"total={self.total_tokens:,})"
        )