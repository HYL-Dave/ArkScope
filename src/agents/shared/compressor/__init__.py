"""Compressor library — P1.4 Phase B context compression infrastructure.

Public API exposed at the package root:

  - ``CompressionRecord`` — persisted overflow record dataclass
  - ``OverflowStore`` — session-scoped disk store for Layer 0 overflow
  - ``canonical_args_hash`` — stable sha256 hex of an args dict
  - ``compute_record_id`` — derive ``record_id`` per spec §3.1.1
  - ``is_valid_record_id`` — path-traversal guard

**Library-not-runner guarantee** (P1_4_SPEC §1.2 #1):
This package imports nothing from ``src.agents.anthropic_agent`` or
``src.agents.openai_agent``. The ast-based audit at
``tests/test_compressor_overflow_store.py::TestNoAgentImports`` enforces
this at test time so future multi-round runner work can reuse the
compressor without dragging the agent loop with it.
"""

from .overflow_store import (
    OverflowStore,
    canonical_args_hash,
    compute_record_id,
    is_valid_record_id,
)
from .types import CompressionRecord

__all__ = [
    "CompressionRecord",
    "OverflowStore",
    "canonical_args_hash",
    "compute_record_id",
    "is_valid_record_id",
]
