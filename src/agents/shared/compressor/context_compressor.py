"""ContextCompressor orchestrator (P1.4 commit 2).

Glues Layers 0-3 + the overflow store into a single object that the
agent loop (commit 3) constructs once per session. Each method has a
config flag — disabled layers are pass-through, so partial enablement
is supported (and `compaction.enabled=false` reduces every method
to a no-op).

Stubs for Layers 4-5 are present but raise / no-op in commit 2.
Commit 5 fills in Layer 5; Layer 4 stays opt-in indefinitely.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .layers import (
    apply_layer_0,
    apply_layer_1,
    apply_layer_2,
    apply_layer_3,
    total_chars,
)
from .overflow_store import OverflowStore
from .reducers import ToolReducer
from .types import CompressionRecord, ProjectedMessage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config (mirrors compaction.* in AgentConfig — see spec §8)
# ---------------------------------------------------------------------------


@dataclass
class CompressorConfig:
    """Mirrors the ``compaction.*`` block from AgentConfig (spec §8)."""

    enabled: bool = True

    # Layer 0
    layer_0_enabled: bool = True
    layer_0_budget_chars: int = 8000

    # Layer 1
    layer_1_enabled: bool = True
    # (no threshold — Layer 1 is cheap and runs every pre-call check)

    # Layer 2
    layer_2_enabled: bool = True
    layer_2_threshold_chars: int = 100_000

    # Layer 3
    layer_3_enabled: bool = True
    layer_3_threshold_chars: int = 150_000

    # Layer 4 (provider native, opt-in — see §3.5)
    layer_4_enabled: bool = False

    # Layer 5 (LLM full compact, opt-in — fills in commit 5)
    layer_5_enabled: bool = False
    layer_5_threshold_chars: int = 250_000

    # Shared
    keep_recent_turns: int = 2
    circuit_breaker_max_failures: int = 3
    overflow_size_cap_chars: int = 32_000


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


@dataclass
class CompressionEvent:
    """Per-trigger telemetry. Useful for replay fixtures + /compaction status."""

    layer: int
    before_chars: int
    after_chars: int
    note: str = ""


class ContextCompressor:
    """Per-session compressor.

    Construct once at agent-session start; reuse across model calls.
    The class is reentrant in the sense that two instances can run on
    the same session_id without locking — but Layer 0 writes are not
    atomic across processes (out of scope for v1; spec §9 #1).
    """

    def __init__(
        self,
        *,
        session_id: str,
        overflow_dir: Path,
        config: Optional[CompressorConfig] = None,
        reducer_registry: Optional[Dict[str, ToolReducer]] = None,
    ) -> None:
        self.config = config or CompressorConfig()
        self._reducer_registry = reducer_registry  # None → use module default
        self._overflow_store = OverflowStore(Path(overflow_dir), session_id)
        self._events: List[CompressionEvent] = []
        self._layer_5_consecutive_failures = 0  # circuit breaker (commit 5)

    # -----------------------------------------------------------------
    # Properties
    # -----------------------------------------------------------------

    @property
    def session_id(self) -> str:
        return self._overflow_store.session_id

    @property
    def overflow_store(self) -> OverflowStore:
        return self._overflow_store

    @property
    def events(self) -> List[CompressionEvent]:
        return list(self._events)

    @property
    def layer_5_circuit_open(self) -> bool:
        return self._layer_5_consecutive_failures >= self.config.circuit_breaker_max_failures

    # -----------------------------------------------------------------
    # Layer 0 — call this at tool_result insertion time
    # -----------------------------------------------------------------

    def process_tool_result(
        self,
        tool_name: str,
        args: Optional[Dict[str, Any]],
        payload: str,
    ) -> Tuple[str, Optional[CompressionRecord]]:
        """Apply Layer 0 budget + overflow disk persist to one tool result.

        Returns ``(in_prompt_payload, optional_record)``. See
        :func:`apply_layer_0` for the contract; this method is a thin
        wrapper that respects ``config.enabled`` + ``layer_0_enabled``.
        """
        if not self.config.enabled or not self.config.layer_0_enabled:
            return payload, None

        return apply_layer_0(
            tool_name=tool_name,
            args=args,
            payload=payload,
            overflow_store=self._overflow_store,
            budget_chars=self.config.layer_0_budget_chars,
            registry=self._reducer_registry,
        )

    # -----------------------------------------------------------------
    # Layers 1-3 — call this before each model call
    # -----------------------------------------------------------------

    def compact_pre_call(
        self,
        messages: List[ProjectedMessage],
        *,
        scratchpad: str = "",
    ) -> List[ProjectedMessage]:
        """Run Layers 1, 2, 3 in sequence based on size thresholds.

        Each layer respects its own enabled flag. Layer 1 always runs
        when enabled (cheap minify). Layer 2 fires when total size
        exceeds ``layer_2_threshold_chars`` AND ``scratchpad`` is
        non-empty. Layer 3 fires when (after Layers 1 + 2) total size
        still exceeds ``layer_3_threshold_chars``.

        Returns a new message list; input is not mutated.
        """
        if not self.config.enabled or not messages:
            return list(messages)

        before = total_chars(messages)
        keep = self.config.keep_recent_turns

        # Layer 1: microcompact (cheap, always run when enabled)
        if self.config.layer_1_enabled:
            after = apply_layer_1(messages, keep_recent_turns=keep)
            if after != messages:
                self._events.append(CompressionEvent(
                    layer=1, before_chars=before,
                    after_chars=total_chars(after),
                    note="microcompact",
                ))
            messages = after

        # Layer 2: scratchpad reuse
        if (
            self.config.layer_2_enabled
            and scratchpad.strip()
            and total_chars(messages) > self.config.layer_2_threshold_chars
        ):
            before_2 = total_chars(messages)
            messages = apply_layer_2(
                messages, scratchpad=scratchpad, keep_recent_turns=keep,
            )
            self._events.append(CompressionEvent(
                layer=2, before_chars=before_2,
                after_chars=total_chars(messages),
                note="scratchpad_reuse",
            ))

        # Layer 3: progressive truncation
        if (
            self.config.layer_3_enabled
            and total_chars(messages) > self.config.layer_3_threshold_chars
        ):
            before_3 = total_chars(messages)
            messages = apply_layer_3(messages, keep_recent_turns=keep)
            self._events.append(CompressionEvent(
                layer=3, before_chars=before_3,
                after_chars=total_chars(messages),
                note="progressive_truncation",
            ))

        # Layer 4 (provider native) lands as a flag the agent adapter reads;
        # it's not a transformation we apply here.
        # Layer 5 (LLM full compact) is wired in commit 5.

        return messages

    # -----------------------------------------------------------------
    # CLI / test helper — NOT agent-exposed in v1 (see spec §5.1)
    # -----------------------------------------------------------------

    def get_overflow_payload(self, record_id: str) -> Optional[str]:
        """Retrieve the original payload for a record_id.

        Returns ``None`` if not found / invalid id / corrupt /
        tampered. **Not registered as an agent tool in v1** —
        callers are CLI debug + tests only (spec §5.1).
        """
        record = self._overflow_store.read(record_id)
        return record.original_payload if record else None
