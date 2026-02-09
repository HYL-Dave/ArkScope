"""
Agent event types for streaming progress from agent loops.

Defines EventType enum and AgentEvent dataclass used by run_query_stream()
to yield intermediate progress events (thinking, tool_start, tool_end, done).

This is Phase 4 of the agent evolution roadmap.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict


class EventType(str, Enum):
    """Event types emitted during agent execution."""

    thinking = "thinking"                  # API call started, model is processing
    thinking_content = "thinking_content"  # Model's thinking text (extended thinking)
    text = "text"                          # Intermediate text from model (before tool calls)
    tool_start = "tool_start"              # Tool execution begins
    tool_end = "tool_end"                  # Tool execution finished (with result summary)
    error = "error"                        # Error during execution
    done = "done"                          # Final answer + session summary


@dataclass
class AgentEvent:
    """
    A single event emitted during agent execution.

    Used by ``run_query_stream()`` to yield progress updates.
    Consumers include the HTTP SSE endpoint and potentially the CLI.
    """

    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_sse(self) -> str:
        """Format as a Server-Sent Event data line."""
        payload = {"type": self.type.value, "data": self.data}
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to plain dict for serialization."""
        return {
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp,
        }