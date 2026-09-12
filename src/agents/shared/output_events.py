"""Exact-secret projection for one execution's public AgentEvent iterator.

Only upstream advance/close borrows the retained guard's ContextVar. Prose is
projected without diagnostic heuristics; metadata and tool inputs are checked
as strict JSON, including their canonical spelling. Unknown event fields fail
closed. Producers still own admission before callbacks, previews and storage.

Normal EOF/done flush unmatched text and thinking tails. Error, cancellation
and explicit close discard them. This wrapper closes only its own matchers,
never other streams sharing the guard. It does not capture credentials, change
provider/session behavior or translate upstream exceptions into public errors.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncIterator
from functools import wraps
import json

from src.auth_drivers.probe_harness import redact

from .events import AgentEvent, EventType
from .output_boundary import (
    OutputBoundaryError, OutputGuard, SecretStream,
    activate_output_guard, current_output_guard,
)


_STREAM_FIELDS = {EventType.text: "content", EventType.thinking_content: "thinking"}
_PROSE_FIELDS = {
    EventType.text: frozenset({"content"}),
    EventType.thinking_content: frozenset({"thinking"}),
    EventType.tool_end: frozenset({"summary"}),
    EventType.done: frozenset({"answer"}),
    EventType.error: frozenset({"error", "message", "detail"}),
}
_FIELDS = {
    EventType.thinking: frozenset({"turn", "model", "provider"}),
    EventType.text: frozenset({"content"}),
    EventType.thinking_content: frozenset({"thinking"}),
    EventType.tool_start: frozenset({"tool", "input", "call_id"}),
    EventType.tool_end: frozenset({"tool", "summary", "chars", "is_error", "call_id"}),
    EventType.done: frozenset({"answer", "tools_used", "provider", "model", "token_usage"}),
    EventType.error: frozenset({
        "error", "message", "detail", "code", "provider", "model", "turn",
        "tools_used", "token_usage", "scratchpad", "stop_details",
    }),
}
_REQUIRED = {
    EventType.text: frozenset({"content"}),
    EventType.thinking_content: frozenset({"thinking"}),
    EventType.tool_start: frozenset({"tool", "input"}),
    EventType.tool_end: frozenset({"tool"}),
    EventType.done: frozenset({"answer"}),
}


def check_output_value(value, *, guard: OutputGuard | None = None):
    """Admit and detach a complete value before callbacks, previews or storage."""
    guard = guard if guard is not None else current_output_guard() or OutputGuard()
    guard.check(value)
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
        encoded.encode("utf-8")
        guard.check(encoded)
        return json.loads(encoded)
    except OutputBoundaryError:
        raise
    except (TypeError, ValueError, RecursionError):
        raise OutputBoundaryError("invalid_value") from None


def protect_output_text(text: str) -> str:
    """Project complete public prose, without diagnostic heuristics."""
    return (current_output_guard() or OutputGuard()).prose(text)


def protect_event_stream(function):
    """Retain an execution guard without holding a scope across public yields."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        return protect_events(function(*args, **kwargs))
    return wrapped


class ProtectedEventStream(AsyncIterator[AgentEvent]):
    """Single-consumer iterator; use protect_events to avoid a second tail."""

    def __init__(self, stream: AsyncIterator[AgentEvent], *, guard: OutputGuard):
        if type(guard) is not OutputGuard or not isinstance(stream, AsyncIterator):
            raise OutputBoundaryError("invalid_value")
        self._guard = guard
        self._upstream = stream
        self._streams: dict[EventType, SecretStream] = {}
        self._timestamps: dict[EventType, float] = {}
        self._ready: deque[AgentEvent] = deque()
        self._closed = False
        self._busy = False

    @property
    def guard(self) -> OutputGuard:
        return self._guard

    def __aiter__(self) -> ProtectedEventStream:
        return self

    async def __anext__(self) -> AgentEvent:
        if self._busy:
            raise RuntimeError("event_stream_busy")
        self._busy = True
        try:
            while not self._ready and not self._closed:
                try:
                    with activate_output_guard(self._guard):
                        event = await self._upstream.__anext__()
                except StopAsyncIteration:
                    await self._close_upstream()
                    self._ready.extend(self._finish_channels())
                    break

                if type(event) is not AgentEvent or type(event.type) is not EventType:
                    raise OutputBoundaryError("invalid_value")
                if event.type in (EventType.done, EventType.error):
                    # Close before projecting the terminal: cleanup can register
                    # child credentials needed to check the final value/tails.
                    await self._close_upstream()
                    terminal = self._project(event)
                    if event.type == EventType.done:
                        self._ready.extend(self._finish_channels())
                    else:
                        self._abort_channels()
                    self._ready.append(terminal)
                else:
                    projected = self._project(event)
                    if projected is not None:
                        self._ready.append(projected)
            if self._ready:
                event = self._ready.popleft()
                # EOF tails/terminal can span consumer turns while a sibling
                # registers another credential on the same retained guard.
                return self._public_event(event.type, event.data, event.timestamp)
            raise StopAsyncIteration
        except BaseException:
            self._ready.clear()
            self._abort_channels()
            try:
                await self._close_upstream()
            except BaseException:
                pass  # Preserve the original failure/cancellation, not cleanup.
            raise
        finally:
            self._busy = False

    async def aclose(self) -> None:
        if self._busy:
            raise RuntimeError("event_stream_busy")
        self._busy = True
        try:
            self._ready.clear()
            self._abort_channels()
            await self._close_upstream()
        finally:
            self._busy = False

    async def _close_upstream(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            close = getattr(self._upstream, "aclose", None)
            if close is not None:
                async def close_with_guard():
                    with activate_output_guard(self._guard):
                        await close()

                closing = asyncio.create_task(close_with_guard())
                try:
                    await asyncio.shield(closing)
                except asyncio.CancelledError:
                    # Own this same finalizer until it settles, including after
                    # repeated cancellation; never detach it or retry aclose.
                    while not closing.done():
                        try:
                            await asyncio.shield(closing)
                        except asyncio.CancelledError:
                            pass
                        except BaseException:
                            break
                    if not closing.cancelled():
                        closing.exception()
                    raise
        finally:
            self._upstream = None

    def _abort_channels(self) -> None:
        for stream in self._streams.values():
            stream.abort()
        self._streams.clear()
        self._timestamps.clear()

    def _finish_channels(self) -> list[AgentEvent]:
        events = []
        try:
            for kind, stream in self._streams.items():
                text = stream.finish()
                if text:
                    events.append(self._public_event(kind, {_STREAM_FIELDS[kind]: text}, self._timestamps[kind]))
            return events
        finally:
            self._abort_channels()

    def _public_event(self, kind: EventType, data: dict, timestamp: float) -> AgentEvent:
        payload = check_output_value({"type": kind.value, "data": data, "timestamp": timestamp}, guard=self._guard)
        return AgentEvent(kind, payload["data"], timestamp=payload["timestamp"])

    def _project(self, event: AgentEvent) -> AgentEvent | None:
        kind, data = event.type, event.data
        if (type(data) is not dict or any(type(key) is not str for key in data)
                or type(event.timestamp) not in (int, float)):
            raise OutputBoundaryError("invalid_value")
        if kind == EventType.error and "stop_details" in data:
            # Refusals have an existing closed diagnostic shape, not arbitrary
            # metadata. Preserve that projection before admitting the event.
            details = data["stop_details"]
            data = {**data, "stop_details": {
                key: redact(self._guard.prose(details[key]))[:500]
                for key in ("type", "category", "explanation")
                if type(details) is dict and type(details.get(key)) is str
            }}
        prose_fields = _PROSE_FIELDS.get(kind, frozenset())
        metadata = check_output_value({key: value for key, value in data.items() if key not in prose_fields}, guard=self._guard)
        if data.keys() - _FIELDS[kind] or _REQUIRED.get(kind, frozenset()) - data.keys():
            raise OutputBoundaryError("invalid_value")
        for key, value in data.items():
            if key in prose_fields or key in {"tool", "call_id", "code"}:
                valid = type(value) is str
            elif key in {"provider", "model", "scratchpad"}:
                valid = value is None or type(value) is str
            elif key in {"turn", "chars"}:
                valid = type(value) is int and value >= 0
            elif key == "is_error":
                valid = type(value) is bool
            elif key in {"input", "token_usage"}:
                valid = type(value) is dict
            elif key == "tools_used":
                valid = type(value) is list and all(type(name) is str for name in value)
            else:  # stop_details is already strict-JSON checked above.
                valid = True
            if not valid:
                raise OutputBoundaryError("invalid_value")
        if kind in _STREAM_FIELDS:
            if kind not in self._streams:
                self._streams[kind] = self._guard.stream()
            self._timestamps[kind] = event.timestamp
            field = _STREAM_FIELDS[kind]
            text = self._streams[kind].feed(data[field])
            if not text:
                return None
            metadata[field] = text
        else:
            for field in prose_fields & data.keys():
                metadata[field] = self._guard.prose(data[field])
        return self._public_event(kind, metadata, event.timestamp)


def protect_events(
    stream: AsyncIterator[AgentEvent], *, guard: OutputGuard | None = None,
) -> ProtectedEventStream:
    """Reuse an exact trusted iterator only for the requested/active guard.

    With no requested or active guard, an already-protected stream keeps its
    retained guard; a raw stream gets an independent one. Subclasses are raw
    inputs, not proof that any event has been admitted.
    """
    selected = guard if guard is not None else current_output_guard()
    if selected is not None and type(selected) is not OutputGuard:
        raise OutputBoundaryError("invalid_value")
    if type(stream) is ProtectedEventStream:
        if selected is not None and stream.guard is not selected:
            raise OutputBoundaryError("invalid_value")
        return stream
    return ProtectedEventStream(stream, guard=selected if selected is not None else OutputGuard())
