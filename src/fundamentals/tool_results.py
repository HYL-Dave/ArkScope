"""Never present prose-truncated financial numbers as a usable observation."""

import json
import re

from src.tools.retained_read_results import canonical_json
from src.data_source_routing import DataSourcePolicyFailure
from src.fundamentals.settings import load_settings


def apply_financial_result_budget(payload: str, dal=None) -> str:
    """Run after secret admission; invalid profile settings do not bypass the cap."""
    try:
        budget = load_settings(dal).tool_output_chars
    except DataSourcePolicyFailure as exc:
        from src.agents.shared.security import wrap_tool_result

        failure = canonical_json(dict(status="unavailable", error_code=exc.code))
        return wrap_tool_result(failure, "get_fundamentals_analysis") if payload.startswith("<tool_output ") else failure
    return financial_result_reducer(payload, budget=budget)[0]


def financial_result_reducer(payload: str, *, budget: int) -> tuple[str, dict]:
    inner, prefix, suffix = payload, "", ""
    match = re.fullmatch(r'(<tool_output tool="(?:tool_)?get_fundamentals_analysis">\n)(.*)(\n</tool_output>)',
                         payload, re.DOTALL)
    if match:
        prefix, inner, suffix = match.groups()
    try:
        value = json.loads(inner)
        if not isinstance(value, dict) or value.get("status") not in {"ok", "partial", "unavailable"}:
            raise ValueError("financial result")
        canonical_json(value)
        if budget == 0 or len(payload) <= budget:
            return payload, {}
        failure = dict(status="unavailable", error_code="financial_read_page_too_large", read_id=value.get("read_id"),
                       required_action="repeat_same_read_with_smaller_page")
    except (ValueError, TypeError, RecursionError):
        failure = dict(status="unavailable", error_code="financial_read_result_invalid")
    return prefix + canonical_json(failure) + suffix, {"failure": failure["error_code"]}
