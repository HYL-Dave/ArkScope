"""
JSONL-based decision logging for agent sessions (Scratchpad).

Records every step of an agent execution — init, tool calls, tool results,
and final answer — as append-only JSONL for crash-safety and audit trails.

This is Phase 2 of the agent evolution roadmap.
Design borrows from Beads project: hash-based IDs, JSONL format.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default base directory for scratchpad files
_DEFAULT_BASE_DIR = Path("data/agent_scratchpad")


def _make_session_id(query: str, timestamp: float) -> str:
    """Generate a short hash-based session ID from query + timestamp."""
    raw = f"{query}:{timestamp}"
    return hashlib.sha256(raw.encode()).hexdigest()[:8]


def _truncate(text: str, max_len: int = 500) -> str:
    """Truncate text for logging, preserving useful prefix."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"... [{len(text) - max_len} chars truncated]"


class Scratchpad:
    """
    Append-only JSONL logger for one agent session.

    Usage::

        pad = Scratchpad(query="分析 NVDA 近期走勢", provider="anthropic", model="claude-sonnet-4")

        # During agent loop
        pad.log_tool_call("get_ticker_news", {"ticker": "NVDA", "days": 30}, token_usage={...})
        pad.log_tool_result("get_ticker_news", result_summary="5 articles found", chars=2400)
        pad.log_final_answer("NVDA shows...", token_usage={...})

        pad.close()

    File format: one JSON object per line in
    ``data/agent_scratchpad/YYYY-MM-DD-HHMMSS_{session_id}.jsonl``
    """

    def __init__(
        self,
        query: str,
        provider: str,
        model: str,
        base_dir: Optional[Path] = None,
        enabled: bool = True,
    ) -> None:
        self.query = query
        self.provider = provider
        self.model = model
        self.enabled = enabled
        self._start_time = time.time()
        self.session_id = _make_session_id(query, self._start_time)
        self._event_seq = 0
        self._file = None
        self._filepath: Optional[Path] = None

        if not enabled:
            return

        base = base_dir or _DEFAULT_BASE_DIR
        base.mkdir(parents=True, exist_ok=True)

        ts = datetime.fromtimestamp(self._start_time, tz=timezone.utc)
        filename = f"{ts.strftime('%Y-%m-%d-%H%M%S')}_{self.session_id}.jsonl"
        self._filepath = base / filename

        try:
            self._file = open(self._filepath, "a", encoding="utf-8")
        except OSError as e:
            logger.warning(f"Scratchpad: cannot open {self._filepath}: {e}")
            self.enabled = False
            return

        # Write init event
        self._write_event("init", {
            "query": query,
            "provider": provider,
            "model": model,
        })

    # ── Public API ─────────────────────────────────────────────

    def log_tool_call(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        token_usage: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record that the agent decided to call a tool."""
        self._write_event("tool_call", {
            "tool": tool_name,
            "input": _safe_serialize(tool_input),
        }, token_usage=token_usage)

    def log_tool_result(
        self,
        tool_name: str,
        result_summary: str = "",
        chars: int = 0,
    ) -> None:
        """Record a tool result (summary only, not full content)."""
        self._write_event("tool_result", {
            "tool": tool_name,
            "summary": _truncate(result_summary, 200),
            "result_chars": chars,
        })

    def log_final_answer(
        self,
        answer: str,
        token_usage: Optional[Dict[str, Any]] = None,
        tools_used: Optional[List[str]] = None,
    ) -> None:
        """Record the agent's final answer and session summary."""
        elapsed = time.time() - self._start_time
        self._write_event("final_answer", {
            "answer_preview": _truncate(answer, 300),
            "answer_chars": len(answer),
            "tools_used": tools_used or [],
            "elapsed_seconds": round(elapsed, 2),
        }, token_usage=token_usage)

    def log_max_turns(
        self,
        token_usage: Optional[Dict[str, Any]] = None,
        tools_used: Optional[List[str]] = None,
    ) -> None:
        """Record that max tool calls was reached."""
        elapsed = time.time() - self._start_time
        self._write_event("max_turns", {
            "tools_used": tools_used or [],
            "elapsed_seconds": round(elapsed, 2),
        }, token_usage=token_usage)

    def close(self) -> None:
        """Flush and close the JSONL file."""
        if self._file and not self._file.closed:
            self._file.close()

    @property
    def filepath(self) -> Optional[Path]:
        return self._filepath

    # ── Internal ───────────────────────────────────────────────

    def _write_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        token_usage: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append one JSONL line. Flush immediately for crash-safety."""
        if not self.enabled or not self._file:
            return

        self._event_seq += 1
        entry = {
            "seq": self._event_seq,
            "type": event_type,
            "ts": datetime.now(timezone.utc).isoformat(),
            "session": self.session_id,
            "data": data,
        }
        if token_usage:
            entry["token_usage"] = token_usage

        try:
            self._file.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._file.flush()
        except OSError as e:
            logger.warning(f"Scratchpad write error: {e}")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def __repr__(self) -> str:
        return f"Scratchpad(session={self.session_id}, events={self._event_seq})"


def _safe_serialize(obj: Any) -> Any:
    """Make an object JSON-safe by converting non-serializable types to strings."""
    if isinstance(obj, dict):
        return {k: _safe_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(v) for v in obj]
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    return str(obj)


def read_scratchpad(filepath: Path) -> List[Dict[str, Any]]:
    """Read all events from a scratchpad JSONL file."""
    events = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events