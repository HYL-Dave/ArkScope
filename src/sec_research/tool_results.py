"""Whole SEC envelopes at Research serialization and reduction boundaries."""

from contextvars import ContextVar
import json

from src.tools.result_policy import ResultPolicy


SEC_TOOL_NAMES = frozenset({"list_sec_filings", "get_sec_financial_facts", "read_sec_filing"})
result_fits = ContextVar("sec_result_fits", default=None)
_KEYS = {"status", "data", "gaps", "observed_at", "coverage", "next_cursor"}


def unavailable(code):
    return dict(status="unavailable", data=[], gaps=[{"code": code}],
                observed_at=None, coverage={}, next_cursor=None)


def active_budget():
    from src.agents.config import get_agent_config
    return min(12000, get_agent_config().compaction_layer_0_budget_chars)


def valid_envelope(envelope):
    return (isinstance(envelope, dict) and set(envelope) == _KEYS
            and isinstance(envelope["status"], str)
            and envelope["status"] in {"ok", "empty", "partial", "unavailable"}
            and isinstance(envelope["data"], (dict, list))
            and isinstance(envelope["coverage"], dict)
            and isinstance(envelope["gaps"], list)
            and all(isinstance(g, dict) and isinstance(g.get("code"), str)
                    for g in envelope["gaps"])
            and (envelope["observed_at"] is None or isinstance(envelope["observed_at"], str))
            and (envelope["next_cursor"] is None or isinstance(envelope["next_cursor"], str)))


SEC_RESULT_POLICY = ResultPolicy("json", validator=valid_envelope)


def serialize_sec_result(envelope, name):
    from src.agents.shared.security import wrap_tool_result
    from src.tools.result_policy import admit_tool_result
    content = admit_tool_result(envelope, policy=SEC_RESULT_POLICY)
    return wrap_tool_result(content, name)


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
        if not valid_envelope(envelope):
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
