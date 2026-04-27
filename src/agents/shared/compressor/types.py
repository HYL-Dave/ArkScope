"""Type definitions for the compressor library (P1.4 commits 1-2).

Pure dataclasses / typed dicts with no dependency on
``src.agents.anthropic_agent`` or ``src.agents.openai_agent`` — the
library-not-runner guarantee from docs/design/P1_4_SPEC.md §1.2 #1 is
enforced at the import level by
tests/test_compressor_overflow_store.py::TestNoAgentImports.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, TypedDict


@dataclass(frozen=True)
class CompressionRecord:
    """A persisted record of a tool result that exceeded Layer 0's budget.

    See docs/design/P1_4_SPEC.md §3.1 for the contract; §3.1.1 for the
    record_id derivation.

    Attributes:
        record_id: 16 hex chars, deterministic per the
            ``(tool_name, canonical_args_hash, payload_bytes)`` triple.
        tool_name: name of the tool that produced this payload.
        args: original args dict (before canonicalization). Stored for
            human-readable debug; the hash key uses the canonical form.
        args_hash: full sha256 hex of the canonical args JSON. Carried
            alongside ``args`` so that downstream readers can verify
            the args dict has not been tampered with after persistence.
        original_size: byte count of the original payload (utf-8 encoded).
        original_payload: original payload as str. utf-8 round-trips.
        written_at: UTC ISO-8601 timestamp when the record was persisted.
    """

    record_id: str
    tool_name: str
    args: Dict[str, Any]
    args_hash: str
    original_size: int
    original_payload: str
    written_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "tool_name": self.tool_name,
            "args": self.args,
            "args_hash": self.args_hash,
            "original_size": self.original_size,
            "original_payload": self.original_payload,
            "written_at": self.written_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompressionRecord":
        return cls(
            record_id=str(data["record_id"]),
            tool_name=str(data["tool_name"]),
            args=dict(data.get("args") or {}),
            args_hash=str(data["args_hash"]),
            original_size=int(data["original_size"]),
            original_payload=str(data["original_payload"]),
            written_at=str(data["written_at"]),
        )


# ---------------------------------------------------------------------------
# Provider-neutral message projection (Layers 1-3)
# ---------------------------------------------------------------------------


class ProjectedMessage(TypedDict, total=False):
    """Provider-neutral message shape consumed by Layers 1-3.

    Adapters (commit 3+) translate Anthropic / OpenAI message lists to
    and from this projection. Compressor code only ever sees this shape,
    keeping the library decoupled from any provider SDK.

    Required keys:
        role: one of ``"user"``, ``"assistant"``, ``"tool_use"``,
            ``"tool_result"``, ``"system"``.
        content: serialised content. For ``tool_result`` rows this is
            typically a JSON string; for text rows it's plain text.

    Optional keys:
        tool_name: present on ``tool_use`` and ``tool_result`` rows.
        overflow_record_id: set by Layer 0 when this row's content was
            truncated and the original was persisted to the overflow
            store. Layers 1-3 preserve this field across compaction.
        is_compaction_summary: True for the marker-wrapped Layer 5
            summary item (commit 5; included here so Layers 1-3 know
            not to mutate it).
        original_chars: for diagnostics / `data_quality` reporting.
    """

    role: str
    content: str
    tool_name: str
    overflow_record_id: str
    is_compaction_summary: bool
    original_chars: int
