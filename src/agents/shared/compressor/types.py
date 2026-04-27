"""Type definitions for the compressor library (P1.4 commit 1).

Pure dataclasses with no dependency on src.agents.anthropic_agent or
src.agents.openai_agent — the library-not-runner guarantee from
docs/design/P1_4_SPEC.md §1.2 #1 is enforced at the import level by
tests/test_compressor_overflow_store.py::TestNoAgentImports.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


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