"""Keep retained-evidence pages whole at every model output boundary."""

from functools import partial
import hashlib
import json
import re

from src.tools.result_policy import MAX_OUTPUT_BYTES


RETAINED_READ_TOOLS = frozenset({
    "get_sa_article_detail", "get_sa_comment_focus", "get_portfolio_holdings",
})
_RECOVERY = {
    "get_sa_article_detail": ("sa_article", "retry_same_snapshot_with_smaller_body_comment_or_text_page"),
    "get_sa_comment_focus": ("sa_comment_focus", "reduce_limit_or_window_days"),
    "get_portfolio_holdings": ("portfolio", "retry_same_snapshot_with_smaller_page_or_select_account"),
}


class RetainedReadFailure(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def require(condition, code):
    if not condition:
        raise RetainedReadFailure(code)


def page_integer(value, *, minimum=0):
    return type(value) is int and minimum <= value < 2**63


def valid_snapshot_id(value):
    return value is None or (type(value) is str and re.fullmatch(r"[a-f0-9]{64}", value) is not None)


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))


def content_id(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _page_failure(tool_name, value, reason):
    prefix, action = _RECOVERY[tool_name]
    result = {"status": "unavailable", "error_code": f"{prefix}_{reason}",
              "retrieval": "stored", "required_action": action}
    for key in ("provider", "source", "article_id", "snapshot_id"):
        if isinstance(value.get(key), str) and len(value[key]) <= 256:
            result[key] = value[key]
    return result


def bounded_result(tool_name, value):
    if len(canonical_json(value).encode("utf-8")) > MAX_OUTPUT_BYTES:
        return _page_failure(tool_name, value, "page_too_large")
    return value


def _reduce(tool_name, payload, *, budget):
    inner, prefix, suffix = payload, "", ""
    match = re.fullmatch(r'(<tool_output tool="[^"]+">\n)(.*)(\n</tool_output>)', payload, re.DOTALL)
    if match:
        prefix, inner, suffix = match.groups()
    try:
        value = json.loads(inner)
        if not isinstance(value, dict) or value.get("status") not in {"ok", "unavailable"}:
            raise ValueError("invalid retained read")
        canonical_json(value)
        if len(payload) <= budget:
            return payload, {}
        failure = _page_failure(tool_name, value, "page_too_large")
    except (ValueError, TypeError, RecursionError):
        failure = _page_failure(tool_name, {}, "result_invalid")
    return prefix + canonical_json(failure) + suffix, {"failure": failure["error_code"]}


def retained_read_reducer(tool_name):
    return partial(_reduce, tool_name.removeprefix("tool_"))
