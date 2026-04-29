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
from typing import Any, Callable, Dict, List, Optional, Tuple

from .layers import (
    apply_layer_0,
    apply_layer_1,
    apply_layer_2,
    apply_layer_3,
    apply_layer_5,
    apply_layer_6,
    total_chars,
)
from .overflow_store import OverflowStore
from .reducers import ToolReducer
from .types import CompactionResult, CompressionRecord, ProjectedMessage

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
        summary_caller: Optional[Callable[..., Optional[str]]] = None,
        anchor_data_provider: Optional[Callable[[], Dict[str, Any]]] = None,
    ) -> None:
        self.config = config or CompressorConfig()
        self._reducer_registry = reducer_registry  # None → use module default
        self._overflow_store = OverflowStore(Path(overflow_dir), session_id)
        self._events: List[CompressionEvent] = []
        self._layer_5_consecutive_failures = 0  # circuit breaker (commit 5)
        # Layer 5 / 6 dependencies — None disables those layers cleanly.
        self._summary_caller = summary_caller
        self._anchor_data_provider = anchor_data_provider
        # /compact one-shot bypass (commit 5). Set externally; cleared
        # UNCONDITIONALLY at the top of every compact_pre_call so a
        # threshold-bypass attempt that fails (caller missing / circuit
        # open / master disabled) doesn't leak state into the next turn.
        self.force_layer_5_once: bool = False

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
        prior_summary: Optional[str] = None,
    ) -> CompactionResult:
        """Run Layers 1, 2, 3, 5, 6 in sequence based on size thresholds.

        Returns a :class:`CompactionResult`:

          - ``messages``: post-compaction projection.
          - ``replace_prefix_to``: set when Layer 5 fired (the projected
            boundary the adapter slices native messages at). ``None`` for
            1:1-body-patch paths (Layers 1-3 only).
          - ``appended_anchor``: ``True`` when Layer 6 added a tail
            anchor block.
          - ``layers_fired``: which layer numbers fired this call.

        ``force_layer_5_once`` (set externally by ``/compact``) is
        consumed at the TOP of this method and cleared UNCONDITIONALLY,
        regardless of whether Layer 5 actually fires (master disabled,
        caller missing, circuit open all leave the flag cleared so a
        rejected /compact doesn't leak state into the next turn).
        """
        # Consume the one-shot flag immediately. Per commit-5 lock #2:
        # clear regardless of L5 success / failure / threshold bypass /
        # caller missing / circuit open.
        force_layer_5 = self.force_layer_5_once
        self.force_layer_5_once = False

        if not self.config.enabled or not messages:
            return CompactionResult(messages=list(messages))

        before = total_chars(messages)
        keep = self.config.keep_recent_turns
        layers_fired: List[int] = []

        # Layer 1: microcompact (cheap, always run when enabled)
        if self.config.layer_1_enabled:
            after = apply_layer_1(messages, keep_recent_turns=keep)
            if after != messages:
                self._events.append(CompressionEvent(
                    layer=1, before_chars=before,
                    after_chars=total_chars(after),
                    note="microcompact",
                ))
                layers_fired.append(1)
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
            layers_fired.append(2)

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
            layers_fired.append(3)

        # Layer 4 (provider native) is an agent-adapter flag, not a
        # transformation we apply here.

        # Layer 5: LLM full compact. Gating per commit-5 lock #3:
        #   - master config.enabled MUST be on (already checked above)
        #   - summary_caller MUST be supplied (None disables L5)
        #   - circuit MUST be closed
        #   - either force_layer_5 (one-shot /compact) OR
        #     (layer_5_enabled AND threshold)
        replace_prefix_to: Optional[int] = None
        l5_fired = False
        if (
            self._summary_caller is not None
            and not self.layer_5_circuit_open
            and (
                force_layer_5
                or (
                    self.config.layer_5_enabled
                    and total_chars(messages) > self.config.layer_5_threshold_chars
                )
            )
        ):
            before_5 = total_chars(messages)
            new_msgs, prefix_to, success = apply_layer_5(
                messages,
                keep_recent_turns=keep,
                summary_caller=self._summary_caller,
                prior_summary=prior_summary,
            )
            if success:
                self._layer_5_consecutive_failures = 0
                messages = new_msgs
                replace_prefix_to = prefix_to
                self._events.append(CompressionEvent(
                    layer=5, before_chars=before_5,
                    after_chars=total_chars(messages),
                    note="llm_full_compact"
                          + (" (forced)" if force_layer_5 else ""),
                ))
                layers_fired.append(5)
                l5_fired = True
            else:
                self._layer_5_consecutive_failures += 1
                self._events.append(CompressionEvent(
                    layer=5, before_chars=before_5, after_chars=before_5,
                    note=f"failure_{self._layer_5_consecutive_failures}",
                ))
                # Do NOT add to layers_fired — only successful firings.
                # If circuit just opened, the next pre-call will skip L5
                # and Layer 3 already ran above (fall-back path is
                # implicit — no need to re-fire here).

        # Layer 6: post-compact anchor recovery. Runs only after L4 / L5
        # mutated the cached prefix. spec §3.7.
        appended_anchor = False
        if l5_fired and self._anchor_data_provider is not None:
            try:
                anchor_data = self._anchor_data_provider()
            except Exception as exc:
                logger.warning("anchor_data_provider raised %s — skipping L6", exc)
                anchor_data = {}
            if isinstance(anchor_data, dict) and anchor_data:
                before_6 = total_chars(messages)
                messages = apply_layer_6(messages, anchor_data=anchor_data)
                self._events.append(CompressionEvent(
                    layer=6, before_chars=before_6,
                    after_chars=total_chars(messages),
                    note="post_compact_anchor",
                ))
                layers_fired.append(6)
                appended_anchor = True

        return CompactionResult(
            messages=messages,
            replace_prefix_to=replace_prefix_to,
            appended_anchor=appended_anchor,
            layers_fired=layers_fired,
        )

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
