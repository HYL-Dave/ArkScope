"""Read-only comparison of explicitly separated, already acquired financial data."""

from datetime import date
from hashlib import sha256
import json
import re
from typing import Literal, Optional

from src.data_source_routing import DataSourcePolicyFailure, load_route
from src.fundamentals.cache import fundamentals_analysis_cache_key, validate_positive_annual_sec_payload
from src.fundamentals.reuse import policy, read_entry
from src.fundamentals.source_comparison import METRICS, comparison_rows
from src.sa.company_data import CompanyDataFailure, canonical_json, symbol
from src.sa.company_store import read_capture


PROVIDERS = ("seeking_alpha", "sec_edgar", "financial_datasets")
STATEMENTS = {"income_statement": "income_statements", "balance_sheet": "balance_sheet",
              "cash_flow_statement": "cash_flow_statements"}


def _digest(value):
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _stored_statements(dal, provider, ticker, statement, period):
    """Read existing owners without invoking the legacy ratio calculator."""
    backend = getattr(dal, "_backend", None)
    if provider == "sec_edgar":
        observation = read_entry(backend, fundamentals_analysis_cache_key(ticker, period), provider, ticker,
                                 lambda data: validate_positive_annual_sec_payload(data, ticker=ticker), None)
        if observation is None:
            return [], []
        statements = getattr(observation.data, STATEMENTS[statement]) or []
        return statements, [observation.describe(provider, STATEMENTS[statement], policy("stored", None))]
    from data_sources.financial_datasets_client import FinancialDatasetsClient
    from data_sources.financial_datasets_governance import FinancialDatasetsFailure
    from src.tools.analysis_tools import _sec_to_financial_statement

    client = FinancialDatasetsClient(cache_backend=backend)
    reader = {"income_statement": client.get_income_statements, "balance_sheet": client.get_balance_sheets,
              "cash_flow_statement": client.get_cash_flow_statements}[statement]
    limit = 1 if statement == "balance_sheet" else 4 if period == "quarterly" else 2
    try:
        statements = reader(ticker, period=period, limit=limit, freshness="stored")
    except FinancialDatasetsFailure as exc:
        raise DataSourcePolicyFailure(exc.code) from exc
    return [_sec_to_financial_statement(item) for item in statements], client.observations


def _read_source(dal, provider, ticker, statement, period, currency):
    source = dict(provider=provider, status="unavailable", records=[], available_months=[],
                  historical_reopen_supported=provider == "seeking_alpha")
    try:
        route = load_route("sa_company_financials" if provider == "seeking_alpha" else "fundamentals_analysis", dal)
        route.candidates(provider)
        source["source_route"] = route.describe(provider, provider)
        if provider == "seeking_alpha":
            path = getattr(getattr(dal, "_backend", None), "_sa_db", None)
            body = read_capture(ticker, statement, period, currency, db_path=path)
            if body is None:
                source["error_code"] = "sa_company_capture_missing"
                return source
            source.update(observation_id=body["observation_id"], content_sha256=body["observation_id"],
                          source_url=body["source_url"], fetched_at=body["last_captured_at"],
                          unit_note=body["unit_note"])
            records = [dict(end_month=column["end_month"], period_end=None, currency=body["currency"],
                            rows=body["rows"], column_index=i, unit_note=body["unit_note"])
                       for i, column in enumerate(body["columns"]) if column["kind"] == period and column["end_month"]]
        else:
            statements, descriptions = _stored_statements(dal, provider, ticker, statement, period)
            if not statements:
                source["error_code"] = "financial_comparison_stored_statement_missing"
                return source
            source["content_sha256"] = _digest([item.model_dump() for item in statements])
            source["source_observations"] = descriptions
            source["source_url"] = None  # Old cache has no citation-level source pointer.
            records = []
            for item in statements:
                if item.period_type != period or date.fromisoformat(item.report_period).isoformat() != item.report_period:
                    continue
                declared_currency = item.currency if isinstance(item.currency, str) and re.fullmatch(r"[A-Z]{3}", item.currency) else None
                records.append(dict(end_month=item.report_period[:7], period_end=item.report_period,
                                    currency=declared_currency, data=item.data))
        source.update(status="ok", records=records, available_months=sorted({r["end_month"] for r in records}, reverse=True))
    except (CompanyDataFailure, DataSourcePolicyFailure) as exc:
        source["error_code"] = exc.code
    except (ValueError, TypeError, KeyError, AttributeError):
        source["error_code"] = "financial_comparison_observation_invalid"
    return source


def compare_financial_sources(
    dal, ticker: str,
    statement: Literal["income_statement", "balance_sheet", "cash_flow_statement"] = "income_statement",
    period: Literal["annual", "quarterly"] = "annual",
    sources: Optional[list[Literal["seeking_alpha", "sec_edgar", "financial_datasets"]]] = None,
    end_month: Optional[str] = None, currency: str = "USD",
    row_offset: int = 0, row_limit: int = 3, comparison_id: Optional[str] = None,
):
    """Compare retained statement rows without acquisition, source fallback or spending.

    Optional end_month selects a displayed period, not an invented fiscal day.
    Otherwise use the latest common month among available sources. Deltas are
    descriptive, never an accounting-equivalence or materiality verdict. Missing
    currency and conflicting precise dates prohibit arithmetic. No ratios, TTM,
    forecasts or grades are mixed into financial facts. Pin comparison_id across
    pages: mutable old provider caches cannot promise historical reopening.
    """
    base = dict(status="unavailable", retrieval="stored", comparison_kind="financial_sources")
    try:
        ticker = symbol(ticker)
        valid = (type(statement) is str and statement in METRICS and period in ("annual", "quarterly")
                 and type(currency) is str and re.fullmatch(r"[A-Z]{3}", currency)
                 and (sources is None or type(sources) is list and len(sources) >= 2
                      and all(type(p) is str and p in PROVIDERS for p in sources) and len(set(sources)) == len(sources))
                 and all(type(v) is int and 0 <= v < 2**63 for v in (row_offset, row_limit)) and row_limit > 0
                 and (comparison_id is None or type(comparison_id) is str and re.fullmatch(r"[a-f0-9]{64}", comparison_id)))
        if not valid or end_month is not None and (type(end_month) is not str or not re.fullmatch(r"\d{4}-\d{2}", end_month)
                                                  or date.fromisoformat(end_month + "-01").strftime("%Y-%m") != end_month):
            raise ValueError("query")
    except (CompanyDataFailure, ValueError, TypeError):
        return {**base, "error_code": "financial_comparison_query_invalid"}
    if sources is None:
        try:
            sources = list(load_route("sa_company_financials", dal).providers) + list(load_route("fundamentals_analysis", dal).providers)
        except DataSourcePolicyFailure as exc:
            return {**base, "error_code": exc.code}
    observations = [_read_source(dal, p, ticker, statement, period, currency) for p in sources]
    public_sources = [{k: v for k, v in source.items() if k != "records"} for source in observations]
    base.update(ticker=ticker, statement=statement, period=period, sources=public_sources, rows=[],
                period_selection="explicit_month" if end_month is not None else "latest_common_stored_month")
    if len(sources) < 2:
        return {**base, "error_code": "financial_comparison_requires_two_sources"}
    available = [set(source["available_months"]) for source in observations if source["available_months"]]
    if end_month is None:
        common = set.intersection(*available) if available else set()
        if not common:
            return {**base, "error_code": "financial_comparison_period_unavailable"}
        end_month = max(common)
    identity = _digest(dict(ticker=ticker, statement=statement, period=period, end_month=end_month, currency=currency,
                            sources=[{k: s.get(k) for k in ("provider", "status", "content_sha256", "error_code")}
                                     for s in public_sources]))
    if comparison_id is not None and identity != comparison_id:
        return {**base, "error_code": "financial_comparison_changed", "comparison_id": identity}
    rows = comparison_rows(observations, statement, end_month)
    comparable = sum(pair["status"] != "not_comparable" for row in rows for pair in row["comparisons"])
    incomplete = any(pair["status"] == "not_comparable" for row in rows for pair in row["comparisons"])
    return {**base, "status": "partial" if incomplete else "ok", "end_month": end_month, "comparison_id": identity,
            "selection": "no_authority_selected", "comparable_pairs": comparable,
            "rows": rows[row_offset:row_offset + row_limit],
            "pagination": {"row_offset": row_offset, "total_rows": len(rows),
                           "next_row_offset": row_offset + row_limit if row_offset + row_limit < len(rows) else None}}


def comparison_result_reducer(payload, *, budget):
    prefix, suffix = '<tool_output tool="compare_financial_sources">\n', '\n</tool_output>'
    wrapped = payload.startswith(prefix) and payload.endswith(suffix)
    try:
        value = json.loads(payload[len(prefix):-len(suffix)] if wrapped else payload)
        if (type(value) is not dict or value.get("comparison_kind") != "financial_sources"
                or value.get("status") not in {"ok", "partial", "unavailable"}):
            raise ValueError("result")
        canonical_json(value)
        if len(payload) <= budget:
            return payload, {}
        failure = dict(status="unavailable", comparison_kind="financial_sources",
                       error_code="financial_comparison_page_too_large", comparison_id=value.get("comparison_id"),
                       required_action="repeat_same_comparison_with_smaller_page")
    except (ValueError, TypeError, RecursionError):
        failure = dict(status="unavailable", comparison_kind="financial_sources", error_code="financial_comparison_result_invalid")
    result = canonical_json(failure)
    return (prefix + result + suffix if wrapped else result), {"failure": failure["error_code"]}
