"""Ephemeral exact-secret output checks, independent of auth and result policy.

Representations are case-sensitive, single-step transforms of a captured str:
raw; JSON string contents (ensure_ascii False/True, without surrounding quotes);
UTF-8 URL quote (safe '/' and ''), quote_plus (safe ''); UTF-8 standard/URL-safe
base64, each padded/unpadded. At most ten distinct forms per secret. No recursive
encoding, URL percent-case folding, Unicode normalization, or unknown-secret
detection is implied. None/empty credentials are absent; short ones are exact.

check(value) -> None accepts ONLY exact built-in JSON types: str, dict with str
keys, list, int, finite float, bool and None. Keys count toward traversal/text
budgets. It does not serialize, mutate, check numeric spellings, deny credential
field names, or choose a tool policy. Callers must separately validate policy
and check the actual canonical serialized representation before emitting it.

Streaming retains at most the longest representation minus one raw code point.
Overlapping/touching matches coalesce. Normal finish preserves unmatched secret
prefixes at EOF; abort/error/cancellation discard pending text. Exact credential
coincidences still favor secrecy. A marker/marker-edge collision raises
redaction_marker_conflict, never emits an unsafe marker. Trusted error codes
can themselves coincide with extremely short synthetic secrets; codes are not
derived from rejected content and are not an unknown-secret safety guarantee.

Register credentials BEFORE provider use. Each check/internal stream slice
takes a lock-protected pattern snapshot; streams rescan their bounded pending
suffix, never freezing patterns at creation. Newly registered secrets cannot
retroactively protect already emitted text or discarded history. Registration
and matcher publication support shared guards across threads; each stream is
single-consumer and its owner must sequence feed/finish/abort.
Context managers are synchronous and must exit before yielding to a consumer.
activate_output_guard borrows a retained guard; output_scope owns root stream
cleanup. ContextVar propagation to child tasks is normal Python propagation;
unrelated executions must open their own default-isolated output_scope.
"""

from __future__ import annotations

import base64
from collections import deque
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
import json
import math
from threading import RLock
from urllib.parse import quote, quote_plus
from weakref import WeakSet


MAX_SECRETS = 64
MAX_SECRET_CHARS = 4096
MAX_REPRESENTATIONS = MAX_SECRETS * 10
MAX_REPRESENTATION_CHARS = MAX_SECRET_CHARS * 12
MAX_TOTAL_REPRESENTATION_CHARS = 262_144
MAX_JSON_DEPTH = 64  # Root depth is zero.
MAX_JSON_NODES = 1_000_000  # Includes containers, leaves and mapping keys.
MAX_TEXT_CHARS = 32 * 1024**2  # Aggregate string/key code points per check/prose.
MAX_STREAM_CHUNK_CHARS = MAX_TEXT_CHARS  # No aggregate stream length limit.
_STREAM_SLICE_CHARS = 65_536
REDACTION_MARKER = "[REDACTED]"

_ERROR_CODES = frozenset({
    "output_boundary_error", "known_secret", "invalid_secret", "secret_limit",
    "representation_limit", "invalid_value", "value_limit", "stream_closed",
    "redaction_marker_conflict", "not_serializable", "no_output_scope",
})


class OutputBoundaryError(ValueError):
    """Only a bounded trusted code, never a rejected value or its repr."""

    def __init__(self, code: str):
        self.code = code if type(code) is str and code in _ERROR_CODES else "output_boundary_error"
        super().__init__(self.code)


class _Ephemeral:
    __slots__ = ()

    def __repr__(self) -> str:
        return f"<{type(self).__name__}>"

    def __getstate__(self):
        raise OutputBoundaryError("not_serializable")

    def __reduce__(self):
        raise OutputBoundaryError("not_serializable")

    def __reduce_ex__(self, protocol):
        raise OutputBoundaryError("not_serializable")


def _representations(secret: str) -> frozenset[str]:
    try:
        raw = secret.encode("utf-8")
    except UnicodeEncodeError:
        raise OutputBoundaryError("invalid_secret") from None
    standard = base64.b64encode(raw).decode("ascii")
    urlsafe = base64.urlsafe_b64encode(raw).decode("ascii")
    return frozenset((
        secret,
        json.dumps(secret, ensure_ascii=False)[1:-1],
        json.dumps(secret, ensure_ascii=True)[1:-1],
        quote(secret), quote(secret, safe=""), quote_plus(secret),
        standard, standard.rstrip("="), urlsafe, urlsafe.rstrip("="),
    ))


def _safe_marker(patterns: Iterable[str]) -> bool:
    for pattern in patterns:
        if pattern in REDACTION_MARKER:
            return False
        # A marker must not create a new exact match at either raw-text edge.
        for size in range(1, min(len(pattern), len(REDACTION_MARKER)) + 1):
            if (pattern[:size] == REDACTION_MARKER[-size:]
                    or pattern[-size:] == REDACTION_MARKER[:size]):
                return False
    return True


def _merge_span(spans: list[tuple[int, int]], start: int, end: int) -> None:
    while spans and spans[-1][1] >= start:
        previous_start, previous_end = spans.pop()
        start, end = min(start, previous_start), max(end, previous_end)
    spans.append((start, end))


class _Matcher(_Ephemeral):
    """A bounded literal trie with failure links; offsets are raw code points."""

    __slots__ = ("edges", "failure", "matched")

    def __init__(self, patterns: Iterable[str]):
        self.edges: list[dict[str, int]] = [{}]
        self.failure = [0]
        self.matched = [0]
        for pattern in patterns:
            state = 0
            for char in pattern:
                if char not in self.edges[state]:
                    self.edges[state][char] = len(self.edges)
                    self.edges.append({})
                    self.failure.append(0)
                    self.matched.append(0)
                state = self.edges[state][char]
            self.matched[state] = len(pattern)
        queue = deque(self.edges[0].values())
        while queue:
            state = queue.popleft()
            for char, child in self.edges[state].items():
                fallback = self.failure[state]
                while fallback and char not in self.edges[fallback]:
                    fallback = self.failure[fallback]
                self.failure[child] = self.edges[fallback].get(char, 0)
                self.matched[child] = max(self.matched[child], self.matched[self.failure[child]])
                queue.append(child)

    def _step(self, state: int, char: str) -> int:
        while state and char not in self.edges[state]:
            state = self.failure[state]
        return self.edges[state].get(char, 0)

    def contains(self, text: str) -> bool:
        if not self.edges[0]:
            return False
        state = 0
        for char in text:
            state = self._step(state, char)
            if self.matched[state]:
                return True
        return False

    def scan(self, text: str) -> list[tuple[int, int]]:
        spans: list[tuple[int, int]] = []
        state = 0
        if self.edges[0]:
            for end, char in enumerate(text, 1):
                state = self._step(state, char)
                if self.matched[state]:
                    _merge_span(spans, end - self.matched[state], end)
        return spans


class OutputGuard(_Ephemeral):
    """Execution-local captured credentials. No store, environment or I/O access."""

    __slots__ = ("_secrets", "_patterns", "_longest", "_marker_safe", "_matcher", "_streams", "_lock")

    def __init__(self, secrets: Iterable[str | None] = ()):
        self._lock = RLock()
        self._secrets: set[str] = set()
        self._patterns: frozenset[str] = frozenset()
        self._longest = 0
        self._marker_safe = True
        self._matcher: _Matcher | None = None
        self._streams: WeakSet[SecretStream] = WeakSet()
        if isinstance(secrets, (str, bytes)):
            raise OutputBoundaryError("invalid_secret")
        for secret in secrets:
            self.add_secret(secret)

    def add_secret(self, secret: str | None) -> None:
        """Atomically add one credential; None/empty are absent, duplicates free."""
        if secret is None:
            return
        if type(secret) is not str:
            raise OutputBoundaryError("invalid_secret")
        if not secret:
            return
        with self._lock:
            if secret in self._secrets:
                return
            if len(secret) > MAX_SECRET_CHARS or len(self._secrets) >= MAX_SECRETS:
                raise OutputBoundaryError("secret_limit")
            patterns = self._patterns | _representations(secret)
            longest = max(map(len, patterns))
            if (len(patterns) > MAX_REPRESENTATIONS
                    or longest > MAX_REPRESENTATION_CHARS
                    or sum(map(len, patterns)) > MAX_TOTAL_REPRESENTATION_CHARS):
                raise OutputBoundaryError("representation_limit")
            self._secrets.add(secret)
            self._patterns = patterns
            self._longest = longest
            self._marker_safe = _safe_marker(patterns)
            self._matcher = None

    def _get_matcher(self) -> _Matcher:
        with self._lock:
            if self._matcher is None:
                self._matcher = _Matcher(self._patterns)
            return self._matcher

    def check(self, value: object) -> None:
        """Read-only recursive exact check of bounded strict JSON; returns None."""
        nodes = 0
        text_chars = 0
        active: set[int] = set()
        matcher = self._get_matcher()

        def visit(item: object, depth: int) -> None:
            nonlocal nodes, text_chars
            nodes += 1
            if nodes > MAX_JSON_NODES or depth > MAX_JSON_DEPTH:
                raise OutputBoundaryError("value_limit")
            kind = type(item)
            if kind is str:
                text_chars += len(item)
                if text_chars > MAX_TEXT_CHARS:
                    raise OutputBoundaryError("value_limit")
                if matcher.contains(item):
                    raise OutputBoundaryError("known_secret")
            elif item is None or kind in (bool, int):
                return
            elif kind is float:
                if not math.isfinite(item):
                    raise OutputBoundaryError("invalid_value")
            elif kind in (list, dict):
                identity = id(item)
                if identity in active:
                    raise OutputBoundaryError("invalid_value")
                active.add(identity)
                try:
                    if kind is dict:
                        for key, child in item.items():
                            if type(key) is not str:
                                raise OutputBoundaryError("invalid_value")
                            visit(key, depth + 1)
                            visit(child, depth + 1)
                    else:
                        for child in item:
                            visit(child, depth + 1)
                finally:
                    active.remove(identity)
            else:
                raise OutputBoundaryError("invalid_value")

        visit(value, 0)

    def prose(self, text: str) -> str:
        """Display projection, not an immutable quotation or source capture."""
        if type(text) is not str:
            raise OutputBoundaryError("invalid_value")
        if len(text) > MAX_TEXT_CHARS:
            raise OutputBoundaryError("value_limit")
        stream = self.stream()
        try:
            parts = [stream.feed(text[start:start + MAX_STREAM_CHUNK_CHARS])
                     for start in range(0, len(text), MAX_STREAM_CHUNK_CHARS)]
            parts.append(stream.finish())
            return "".join(parts)
        finally:
            stream.abort()

    def stream(self) -> SecretStream:
        return SecretStream(self)

    def _abort_streams(self) -> None:
        with self._lock:
            streams = tuple(self._streams)
        for stream in streams:
            stream.abort()


class SecretStream(_Ephemeral):
    """Single-consumer stream; feed/finish emit only safe raw-offset projections."""

    __slots__ = ("_guard", "_pending", "_covered", "_redacting", "_closed", "__weakref__")

    def __init__(self, guard: OutputGuard):
        self._guard = guard
        self._pending = ""
        self._covered = 0
        self._redacting = False
        self._closed = False
        with guard._lock:
            guard._streams.add(self)

    def feed(self, text: str) -> str:
        if self._closed:
            raise OutputBoundaryError("stream_closed")
        try:
            if type(text) is not str:
                raise OutputBoundaryError("invalid_value")
            if len(text) > MAX_STREAM_CHUNK_CHARS:
                raise OutputBoundaryError("value_limit")
            if not text:
                return self._process("", final=False)
            return "".join(
                self._process(text[start:start + _STREAM_SLICE_CHARS], final=False)
                for start in range(0, len(text), _STREAM_SLICE_CHARS)
            )
        except BaseException:
            self.abort()
            raise

    def finish(self) -> str:
        """Close normally, preserving unmatched EOF prefixes; repeat is empty."""
        if self._closed:
            return ""
        try:
            return self._process("", final=True)
        finally:
            self.abort()

    def abort(self) -> None:
        """Discard raw suffix on cancellation/error, idempotently."""
        self._pending = ""
        self._covered = 0
        self._redacting = False
        self._closed = True
        with self._guard._lock:
            self._guard._streams.discard(self)

    def _process(self, text: str, *, final: bool) -> str:
        data = self._pending + text
        with self._guard._lock:
            matcher = self._guard._get_matcher()
            longest = self._guard._longest
            marker_safe = self._guard._marker_safe
        matches = matcher.scan(data)
        spans = [(0, self._covered)] if self._covered else []
        for start, end in matches:
            _merge_span(spans, start, end)
        cut = len(data) if final else max(0, len(data) - max(0, longest - 1))
        if not cut:
            self._pending = data
            return ""
        parts: list[str] = []
        position = 0
        covered = 0
        redacting = False
        for start, end in spans:
            if start >= cut:
                break
            parts.append(data[position:start])
            if start or not self._redacting:
                if not marker_safe:
                    raise OutputBoundaryError("redaction_marker_conflict")
                parts.append(REDACTION_MARKER)
            position = min(end, cut)
            if end >= cut:
                covered = end - cut
                redacting = True
                break
        if position < cut:
            parts.append(data[position:cut])
        self._pending = data[cut:]
        self._covered = covered
        self._redacting = redacting
        return "".join(parts)


_CURRENT: ContextVar[OutputGuard | None] = ContextVar("output_guard", default=None)


def current_output_guard() -> OutputGuard | None:
    return _CURRENT.get()


def remember_output_secret(secret: str | None) -> None:
    guard = current_output_guard()
    if guard is None:
        raise OutputBoundaryError("no_output_scope")
    guard.add_secret(secret)


@contextmanager
def activate_output_guard(guard: OutputGuard) -> Iterator[OutputGuard]:
    """Borrow a retained guard for one operation; no auth lookup or cleanup.

    Exit before publicly yielding. Reactivate for each upstream anext/aclose.
    The caller owns stream finish/abort when borrowing rather than scoping.
    """
    if type(guard) is not OutputGuard:
        raise OutputBoundaryError("invalid_value")
    token = _CURRENT.set(guard)
    try:
        yield guard
    finally:
        _CURRENT.reset(token)


@contextmanager
def output_scope(*secrets: str | None, inherit: bool = False) -> Iterator[OutputGuard]:
    """Isolated root by default; inherit=True shares an active execution guard.

    Child additions survive inherited scope exit. Owned roots abort unfinished
    streams on every exit; borrowed scopes do not. Never span a public yield.
    """
    if type(inherit) is not bool:
        raise OutputBoundaryError("invalid_value")
    parent = current_output_guard() if inherit else None
    guard = parent if parent is not None else OutputGuard()
    for secret in secrets:
        guard.add_secret(secret)
    try:
        with activate_output_guard(guard):
            yield guard
    finally:
        if parent is None:
            guard._abort_streams()
