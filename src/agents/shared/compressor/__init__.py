"""Compressor library — P1.4 Phase B context compression infrastructure.

Public API:

  - **Layer 0 building blocks**:
    :class:`OverflowStore`, :class:`CompressionRecord`,
    :func:`canonical_args_hash`, :func:`compute_record_id`,
    :func:`is_valid_record_id`.

  - **Layers 0-3 implementations** (pure functions):
    :func:`apply_layer_0`, :func:`apply_layer_1`,
    :func:`apply_layer_2`, :func:`apply_layer_3`,
    :func:`total_chars`.

  - **Reducers**:
    :data:`ToolReducer`, :func:`truncate_with_marker`,
    :func:`web_result_reducer`, :func:`option_chain_reducer`,
    :func:`iv_history_reducer`, :func:`python_output_reducer`,
    :func:`get_reducer`, :func:`register_reducer`,
    :func:`default_registry`.

  - **Transcript / boundary helpers**:
    :func:`find_recent_boundary`,
    :func:`format_messages_as_transcript`.

  - **Orchestrator**:
    :class:`ContextCompressor`, :class:`CompressorConfig`,
    :class:`CompressionEvent`.

  - **Types**:
    :class:`ProjectedMessage`.

**Library-not-runner guarantee** (P1_4_SPEC §1.2 #1):
This package imports nothing from ``src.agents.anthropic_agent`` or
``src.agents.openai_agent``. The ast-based audit at
``tests/test_compressor_overflow_store.py::TestNoAgentImports`` enforces
this at test time so future multi-round runner work can reuse the
compressor without dragging the agent loop with it.
"""

from .context_compressor import (
    CompressionEvent,
    CompressorConfig,
    ContextCompressor,
)
from .layers import (
    apply_layer_0,
    apply_layer_1,
    apply_layer_2,
    apply_layer_3,
    total_chars,
)
from .overflow_store import (
    OverflowStore,
    canonical_args_hash,
    compute_record_id,
    is_valid_record_id,
)
from .reducers import (
    ToolReducer,
    default_registry,
    get_reducer,
    iv_history_reducer,
    option_chain_reducer,
    python_output_reducer,
    register_reducer,
    tavily_search_reducer,
    truncate_with_marker,
    web_result_reducer,  # backwards-compat alias for tavily_search_reducer
)
from .transcript import find_recent_boundary, format_messages_as_transcript
from .types import CompressionRecord, ProjectedMessage

__all__ = [
    # Types
    "CompressionRecord",
    "ProjectedMessage",
    # Overflow store
    "OverflowStore",
    "canonical_args_hash",
    "compute_record_id",
    "is_valid_record_id",
    # Reducers
    "ToolReducer",
    "default_registry",
    "get_reducer",
    "iv_history_reducer",
    "option_chain_reducer",
    "python_output_reducer",
    "register_reducer",
    "tavily_search_reducer",
    "truncate_with_marker",
    "web_result_reducer",
    # Layers
    "apply_layer_0",
    "apply_layer_1",
    "apply_layer_2",
    "apply_layer_3",
    "total_chars",
    # Transcript
    "find_recent_boundary",
    "format_messages_as_transcript",
    # Orchestrator
    "CompressionEvent",
    "CompressorConfig",
    "ContextCompressor",
]
