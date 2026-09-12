"""Trusted tool-result contracts, separate from lossy diagnostic redaction.

JSON uses exact builtin types plus explicit date/datetime/finite Decimal and
Pydantic field normalization. Root strings require a text policy. Keys are
ASCII-case folded with spaces, tabs, CR/LF, '-' and '_' removed ONLY for the
credential-name check; successful data is never rewritten.

Unknown-auth rejection recognizes case-insensitive Authorization: or
Proxy-Authorization: headers with Bearer plus an RFC6750 token literal;
sk-ant-api03-/sk-ant-oat01-/sk-proj- plus >=20 key characters;
legacy sk- plus >=32 alphanumerics; and gh[pousr]_ plus >=36 alphanumerics.
These forms require a non-word left boundary. This is not an entropy/length
heuristic for arbitrary data, nor detection of arbitrary unknown secrets.

Budgets count root depth as zero, mapping keys as nodes, and UTF-8 JSON bytes
(including escaping and punctuation). Pydantic fields are visited progressively
instead of recursively dumping an unbounded model first. Field exclusions and
allowed extras are honored; custom serializers/computed fields are not implicit
output authority and require a tool to return its explicitly prepared data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
import json
import math
import re
from typing import Any, Callable, Literal

from pydantic import BaseModel

from src.agents.shared.output_boundary import (
    OutputBoundaryError, OutputGuard, current_output_guard,
)


MAX_JSON_DEPTH = 64
MAX_JSON_NODES = 1_000_000
MAX_OUTPUT_BYTES = 32 * 1024**2
_STRING_CHUNK = 65_536
_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")
_SEPARATORS = str.maketrans("", "", "_- \t\r\n")
_CREDENTIAL_KEYS = frozenset({
    "authorization", "proxyauthorization", "xapikey", "apikey", "accesstoken",
    "refreshtoken", "idtoken", "clientsecret", "password", "privatekey",
})
_AUTH_LITERAL = re.compile(
    r"(?<![A-Za-z0-9_])(?:"
    r"(?i:(?:Proxy-)?Authorization:[ \t]*Bearer)[ \t]+[A-Za-z0-9._~+/-]+=*|"
    r"sk-(?:ant-(?:api03|oat01)-|proj-)[A-Za-z0-9_-]{20,}|"
    r"sk-[A-Za-z0-9]{32,}|gh[pousr]_[A-Za-z0-9]{36,})"
)


@dataclass(frozen=True)
class ResultPolicy:
    kind: Literal["json", "text"]
    validator: Callable[[Any], bool] | None = field(default=None, repr=False)


PUBLIC_JSON = ResultPolicy("json")
PUBLIC_TEXT = ResultPolicy("text")


class _Budget:
    def __init__(self):
        self.nodes = 0
        self.bytes = 0

    def node(self, depth):
        self.nodes += 1
        if depth > MAX_JSON_DEPTH or self.nodes > MAX_JSON_NODES:
            raise OutputBoundaryError("value_limit")

    def add(self, size):
        self.bytes += size
        if self.bytes > MAX_OUTPUT_BYTES:
            raise OutputBoundaryError("value_limit")

    def string(self, value, *, json_string=True):
        if json_string:
            self.add(2)
        for offset in range(0, len(value), _STRING_CHUNK):
            chunk = value[offset:offset + _STRING_CHUNK]
            if json_string:
                chunk = json.encoder.encode_basestring(chunk)[1:-1]
            self.add(len(chunk.encode("utf-8")))
        if _AUTH_LITERAL.search(value):
            raise OutputBoundaryError("invalid_value")


def _model_items(value):
    model_type = type(value)
    decorators = model_type.__pydantic_decorators__
    if decorators.model_serializers or decorators.field_serializers or model_type.model_computed_fields:
        raise OutputBoundaryError("invalid_value")
    for key, child in BaseModel.__iter__(value):
        definition = model_type.model_fields.get(key)
        if definition is not None and definition.exclude:
            continue
        yield key, child


def _normalize(value):
    budget = _Budget()
    active = set()

    def visit(item, depth):
        budget.node(depth)
        kind = type(item)
        if kind is Decimal:
            if not item.is_finite():
                raise OutputBoundaryError("invalid_value")
            if Decimal.__sizeof__(item) > MAX_OUTPUT_BYTES:
                raise OutputBoundaryError("value_limit")
            item, kind = str(item), str
        elif kind in (date, datetime):
            item, kind = item.isoformat(), str
        if kind is str:
            budget.string(item)
        elif item is None:
            budget.add(4)
        elif kind is bool:
            budget.add(4 if item else 5)
        elif kind is int:
            if item.bit_length() > MAX_OUTPUT_BYTES * 4:
                raise OutputBoundaryError("value_limit")
            budget.add(len(str(item)))
        elif kind is float:
            if not math.isfinite(item):
                raise OutputBoundaryError("invalid_value")
            budget.add(len(json.dumps(item, allow_nan=False)))
        elif kind in (dict, list) or isinstance(item, BaseModel):
            identity = id(item)
            if identity in active:
                raise OutputBoundaryError("invalid_value")
            active.add(identity)
            budget.add(2)
            try:
                if kind is list:
                    result = []
                    for index, child in enumerate(item):
                        if index:
                            budget.add(1)
                        result.append(visit(child, depth + 1))
                else:
                    result = {}
                    items = item.items() if kind is dict else _model_items(item)
                    for index, (key, child) in enumerate(items):
                        budget.node(depth + 1)
                        if type(key) is not str:
                            raise OutputBoundaryError("invalid_value")
                        budget.string(key)
                        if key.translate(_LOWER).translate(_SEPARATORS) in _CREDENTIAL_KEYS:
                            raise OutputBoundaryError("invalid_value")
                        budget.add(2 if index else 1)
                        result[key] = visit(child, depth + 1)
                return result
            finally:
                active.remove(identity)
        else:
            raise OutputBoundaryError("invalid_value")
        return item

    return visit(value, 0)


def _encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))


def admit_tool_result(result, *, policy, guard=None) -> str:
    """Admit a detached canonical value, or raise a content-free closed error."""
    try:
        if type(policy) is not ResultPolicy or type(policy.kind) is not str or policy.kind not in ("json", "text"):
            raise OutputBoundaryError("invalid_value")
        validator = policy.validator
        if validator is not None and not callable(validator):
            raise OutputBoundaryError("invalid_value")
        guard = guard if guard is not None else current_output_guard()
        guard = guard if guard is not None else OutputGuard()
        if type(guard) is not OutputGuard:
            raise OutputBoundaryError("invalid_value")
        if policy.kind == "text":
            if type(result) is not str:
                raise OutputBoundaryError("invalid_value")
            _Budget().string(result, json_string=False)
            normalized = encoded = result
        else:
            if type(result) is str:
                raise OutputBoundaryError("invalid_value")
            normalized = _normalize(result)
            encoded = _encode(normalized)
        guard.check(normalized)
        guard.check(encoded)
        if validator is not None:
            try:
                verdict = validator(normalized)
            except Exception:
                raise OutputBoundaryError("invalid_value") from None
            if verdict is not True:
                raise OutputBoundaryError("invalid_value")
            # Return the immutable pre-callback bytes, and reject any mutation.
            after = _encode(_normalize(normalized)) if policy.kind == "json" else normalized
            if after != encoded:
                raise OutputBoundaryError("invalid_value")
        return encoded
    except OutputBoundaryError:
        raise
    except Exception:
        raise OutputBoundaryError("invalid_value") from None


def serialize_tool_result(result, *, tool_name) -> str:
    """Resolve reviewed code metadata, never an output-supplied policy label."""
    if type(tool_name) is not str:
        raise OutputBoundaryError("invalid_value")
    if tool_name == "delegate_to_subagent":
        policy = PUBLIC_JSON
    else:
        from src.tools.registry import create_default_registry

        tool = create_default_registry().get(tool_name)
        policy = tool.result_policy if tool is not None else None
    return admit_tool_result(result, policy=policy)


def tool_output_guard(token=None):
    """Use only active credentials and the bearer already captured by a callback."""
    guard = current_output_guard()
    guard = guard if guard is not None else OutputGuard()
    guard.add_secret(token)
    return guard


def sanitize_tool_error(error, *, token=None) -> str:
    """Sanitize inside native wrappers, before SDK error logging or truncation."""
    if type(error) is OutputBoundaryError:
        return error.code
    from src.auth_drivers.runtime_binding import sanitize_runtime_error

    try:
        detail = error if type(error) is str else str(error)
        detail = tool_output_guard(token).prose(detail)
        return sanitize_runtime_error(detail)
    except Exception:
        return "unavailable error detail"
