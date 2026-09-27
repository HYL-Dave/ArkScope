"""Never present prose-truncated financial numbers as a usable observation."""

import json
import re

from src.tools.retained_read_results import canonical_json

# Statement cells carry their source, units, periods and precision together.
FINANCIAL_BRIDGE_BUDGET = 48_000


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
        if len(payload) <= budget:
            return payload, {}
        failure = dict(status="unavailable", error_code="financial_read_page_too_large", read_id=value.get("read_id"),
                       required_action="repeat_same_read_with_smaller_page")
    except (ValueError, TypeError, RecursionError):
        failure = dict(status="unavailable", error_code="financial_read_result_invalid")
    return prefix + canonical_json(failure) + suffix, {"failure": failure["error_code"]}
