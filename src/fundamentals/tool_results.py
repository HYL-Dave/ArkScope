"""Never present prose-truncated financial numbers as a usable observation."""

import json
import re

from src.tools.retained_read_results import canonical_json
from src.data_source_routing import DataSourcePolicyFailure
from src.fundamentals.settings import load_settings


def _page_metadata(value):
    """Project redundant inventory only; retain all returned facts and metric inputs."""
    if not isinstance(value.get("pagination"), dict):
        return False
    fields = {"income_statement": "income_statements", "balance_sheet": "balance_sheet",
              "cash_flow_statement": "cash_flow_statements"}
    pages = {kind: value.get(field) or [] for kind, field in fields.items()}
    coverage = value.get("coverage")
    if isinstance(coverage, dict) and isinstance(coverage.get("statements"), dict):
        coverage.setdefault("retained_period_counts", {
            kind: len(rows) for kind, rows in coverage["statements"].items()})
        coverage["metadata_scope"] = "returned_page"
        for kind, rows in coverage["statements"].items():
            identities = {(row.get("observation_id"), row.get("report_period"), row.get("column_index"))
                          for row in pages.get(kind, [])}
            coverage["statements"][kind] = [row for row in rows if (
                row.get("observation_id"), row.get("report_period"), row.get("column_index")) in identities]
    for observation in value.get("source_observations", []):
        periods = observation.get("report_periods", [])
        observation.setdefault("retained_period_count", len(periods))
        observation["report_periods_scope"] = "returned_page"
        page_periods = {row.get("report_period") or row.get("end_month")
                        for row in pages.get(observation.get("dataset"), [])}
        observation["report_periods"] = [period for period in periods if period in page_periods]
    return True


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
        if _page_metadata(value):
            paged = prefix + canonical_json(value) + suffix
            if len(paged) <= budget:
                return paged, {"metadata_scope": "returned_page"}
        pagination = value.get("pagination") or {}
        action = ("repeat_same_read_with_smaller_page" if pagination.get("limit", 0) > 1
                  else "increase_financial_tool_output_setting")
        failure = dict(status="unavailable", error_code="financial_read_page_too_large", read_id=value.get("read_id"),
                       required_action=action)
    except (ValueError, TypeError, AttributeError, RecursionError):
        failure = dict(status="unavailable", error_code="financial_read_result_invalid")
    return prefix + canonical_json(failure) + suffix, {"failure": failure["error_code"]}
