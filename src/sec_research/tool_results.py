"""Whole SEC envelopes at Research serialization and reduction boundaries."""

from contextlib import contextmanager
from contextvars import ContextVar
import json


SEC_TOOL_NAMES = frozenset({"list_sec_filings", "get_sec_financial_facts", "read_sec_filing"})
result_fits = ContextVar("sec_result_fits", default=None)
_redactor = ContextVar("sec_result_redactor", default=None)
_KEYS = {"status", "data", "gaps", "observed_at", "coverage", "next_cursor"}


def unavailable(code):
    return dict(status="unavailable", data=[], gaps=[{"code": code}],
                observed_at=None, coverage={}, next_cursor=None)


def active_budget():
    from src.agents.config import get_agent_config
    return min(12000, get_agent_config().compaction_layer_0_budget_chars)


@contextmanager
def sec_result_boundary(redact):
    token = _redactor.set(redact)
    try:
        yield
    finally:
        _redactor.reset(token)


def _safe_envelope(envelope, redact):
    # Redact structured values, not serialized JSON: token replacement must not
    # damage quoting or leave a changed passage claiming an exact byte citation.
    def visit(value):
        if isinstance(value, str):
            return redact(value)
        if isinstance(value, list):
            return [visit(item) for item in value]
        if isinstance(value, dict):
            return {redact(key): visit(item) for key, item in value.items()}
        return value
    safe = visit(envelope)
    if isinstance(envelope.get("data"), dict):
        changed = False
        for before, after in zip(envelope["data"].get("passages", []), safe["data"].get("passages", [])):
            if before.get("text") != after.get("text"):
                after["citation"].update(text_redacted=True, exact=False)
                changed = True
        if changed:
            safe["gaps"].append({"code": "sec_passage_redacted"})
            safe["coverage"]["complete"] = False
            safe["status"] = "partial"
    return safe


def serialize_sec_result(envelope, name):
    from src.agents.shared.security import wrap_tool_result
    redact = _redactor.get()
    safe = _safe_envelope(envelope, redact) if redact else envelope
    return wrap_tool_result(json.dumps(safe, ensure_ascii=True, allow_nan=False), name)


def sec_result_reducer(payload, *, budget):
    """Validate a whole envelope; never fall back to generic truncation."""
    name = None
    inner = payload
    if payload.startswith('<tool_output tool="'):
        header, separator, rest = payload.partition("\n")
        candidate = header[len('<tool_output tool="'):-2]
        if candidate in SEC_TOOL_NAMES and separator and rest.endswith("\n</tool_output>"):
            name, inner = candidate, rest[:-len("\n</tool_output>")]
    code = None
    try:
        envelope = json.loads(inner)
        if (not isinstance(envelope, dict) or set(envelope) != _KEYS
                or envelope["status"] not in {"ok", "empty", "partial", "unavailable"}
                or not isinstance(envelope["data"], (dict, list))
                or not isinstance(envelope["coverage"], dict)
                or not isinstance(envelope["gaps"], list)
                or any(not isinstance(g, dict) or not isinstance(g.get("code"), str) for g in envelope["gaps"])
                or envelope["observed_at"] is not None and not isinstance(envelope["observed_at"], str)
                or envelope["next_cursor"] is not None and not isinstance(envelope["next_cursor"], str)):
            raise ValueError
        json.dumps(envelope, allow_nan=False)
    except (ValueError, TypeError, RecursionError):
        code = "sec_result_invalid"
    if code is None and len(payload) > budget:
        code = "sec_result_too_large"
    if code is None:
        return payload, {}
    failure = unavailable(code)
    text = serialize_sec_result(failure, name) if name else json.dumps(failure)
    return text, {"failure": code}


def require_sec_inventory(available, requested=SEC_TOOL_NAMES):
    missing = sorted((set(requested) & SEC_TOOL_NAMES) - set(available))
    if missing:
        raise ValueError(f"Missing required SEC tools: {missing}")
