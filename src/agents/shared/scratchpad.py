"""
JSONL-based decision logging for agent sessions (Scratchpad + ChatHistory).

Scratchpad: per-session JSONL with full tool results (like Dexter's scratchpad).
ChatHistory: append-only JSONL of Q&A pairs (like Dexter's messages).

Design borrows from Dexter (.dexter/scratchpad + .dexter/messages) and
Beads project (hash-based IDs, JSONL format).
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

# Default directories
_DEFAULT_BASE_DIR = Path("data/agent_scratchpad")
_DEFAULT_CHAT_HISTORY_PATH = Path("data/chat_history.jsonl")  # legacy single-file
_CHAT_HISTORY_DIR = Path("data/chat_history")


def _make_session_id(query: str, timestamp: float) -> str:
    """Generate a short hash-based session ID from query + timestamp."""
    raw = f"{query}:{timestamp}"
    return hashlib.sha256(raw.encode()).hexdigest()[:8]


def _try_parse_json(text: str) -> Any:
    """Try to parse a string as JSON; return original string on failure."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


class Scratchpad:
    """
    Append-only JSONL logger for one agent session.

    Stores full tool results (not truncated) for debugging and audit.

    Usage::

        pad = Scratchpad(query="分析 NVDA 近期走勢", provider="anthropic", model="claude-sonnet-4")

        # During agent loop — one event per tool execution (args + result)
        result = execute_tool(tool_name, tool_input)
        pad.log_tool_result("get_ticker_news", result_data=result, tool_input=tool_input)

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
        """Record that the agent decided to call a tool (before execution).

        For providers where tool results are not available (e.g. OpenAI SDK),
        use this to at least record the tool invocation.
        For Anthropic, prefer log_tool_result() with tool_input for a
        combined event after execution.
        """
        self._write_event("tool_call", {
            "tool": tool_name,
            "input": _safe_serialize(tool_input),
        }, token_usage=token_usage)

    def log_tool_result(
        self,
        tool_name: str,
        result_data: str = "",
        tool_input: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a tool execution with full result (like Dexter's scratchpad).

        Stores complete result data for debugging. If tool_input is provided,
        creates a combined event with both args and result.
        """
        data: Dict[str, Any] = {"tool": tool_name}
        if tool_input is not None:
            data["args"] = _safe_serialize(tool_input)
        data["result"] = _try_parse_json(result_data)
        data["result_chars"] = len(result_data) if isinstance(result_data, str) else 0
        self._write_event("tool_result", data)

    def log_final_answer(
        self,
        answer: str,
        token_usage: Optional[Dict[str, Any]] = None,
        tools_used: Optional[List[str]] = None,
    ) -> None:
        """Record the agent's final answer (full, not truncated)."""
        elapsed = time.time() - self._start_time
        self._write_event("final_answer", {
            "answer": answer,
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

    def log_error(
        self,
        error_type: str,
        message: str,
        traceback_str: Optional[str] = None,
        turn: Optional[int] = None,
        tools_used: Optional[List[str]] = None,
        token_usage: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record an error that terminated the agent session.

        This provides structured error logging so failures are traceable
        ("失敗也可追"). Captures exception type, message, optional traceback,
        which turn failed, tools used so far, and cumulative token usage.
        """
        elapsed = time.time() - self._start_time
        data: Dict[str, Any] = {
            "error_type": error_type,
            "message": message[:2000],
            "tools_used": tools_used or [],
            "elapsed_seconds": round(elapsed, 2),
        }
        if traceback_str:
            data["traceback"] = traceback_str[:5000]
        if turn is not None:
            data["turn"] = turn
        self._write_event("error", data, token_usage=token_usage)

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


# ── ChatHistory ────────────────────────────────────────────────


class ChatHistory:
    """Per-session JSONL log of Q&A pairs with tool detail.

    Each session creates a separate file in ``data/chat_history/``.
    Each entry is one complete user question + agent response pair,
    including tool call details, tickers, and token usage.

    Usage::

        history = ChatHistory.create_session()
        history.append(
            user_message="分析 NVDA",
            agent_response="NVDA 近期表現強勁...",
            provider="anthropic",
            model="claude-opus-4-6",
            tools_used=["get_ticker_news"],
            elapsed_seconds=12.5,
            tickers=["NVDA"],
            tool_calls_detail=[{"name": "get_ticker_news", "params": {"ticker": "NVDA"}, "result_preview": "..."}],
            token_usage={"input": 1000, "output": 500},
        )

        entries = history.read_session()
    """

    def __init__(self, path: Optional[Path] = None, session_id: Optional[str] = None) -> None:
        if path is not None:
            self._path = path
        elif session_id is not None:
            self._path = _CHAT_HISTORY_DIR / f"{session_id}.jsonl"
        else:
            # Legacy fallback — single file
            self._path = _DEFAULT_CHAT_HISTORY_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._session_id = session_id

    @classmethod
    def create_session(cls) -> "ChatHistory":
        """Create a new per-session ChatHistory with timestamp-based ID."""
        session_id = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        return cls(session_id=session_id)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def session_id(self) -> Optional[str]:
        return self._session_id

    def append(
        self,
        user_message: str,
        agent_response: str,
        provider: str,
        model: str,
        tools_used: Optional[List[str]] = None,
        elapsed_seconds: Optional[float] = None,
        tickers: Optional[List[str]] = None,
        tool_calls_detail: Optional[List[Dict[str, Any]]] = None,
        token_usage: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append a Q&A pair to the chat history."""
        entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "userMessage": user_message,
            "agentResponse": agent_response,
            "provider": provider,
            "model": model,
        }
        if tools_used:
            entry["tools_used"] = tools_used
        if elapsed_seconds is not None:
            entry["elapsed_seconds"] = round(elapsed_seconds, 2)
        if tickers:
            entry["tickers"] = sorted(set(tickers))
        if tool_calls_detail:
            entry["tool_calls_detail"] = tool_calls_detail
        if token_usage:
            entry["token_usage"] = token_usage

        try:
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as e:
            logger.warning(f"ChatHistory write error: {e}")

    def read_session(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Read entries from this session's file."""
        return self._read_file(self._path, limit)

    @classmethod
    def read_recent(cls, path: Optional[Path] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Read the most recent N entries (legacy single-file compat)."""
        p = path or _DEFAULT_CHAT_HISTORY_PATH
        return cls._read_file(p, limit)

    @staticmethod
    def _read_file(p: Path, limit: int) -> List[Dict[str, Any]]:
        if not p.exists():
            return []
        entries: List[Dict[str, Any]] = []
        try:
            with open(p, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except OSError:
            return []
        return entries[-limit:]


# ── Utility functions ──────────────────────────────────────────


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