"""Read-only comparison of explicitly separated, already acquired financial data."""

from datetime import date
from hashlib import sha256
import json
import re
from typing import Literal, Optional

from src.data_source_routing import DataSourcePolicyFailure, load_route
from src.fundamentals.adapters import read_fd_statements
from src.fundamentals.contracts import FinancialQuery
from src.fundamentals.source_comparison import METRICS, comparison_rows, fd_records, sa_records
from src.sa.company_data import CompanyDataFailure, canonical_json, query_symbol
from src.sa.company_store import read_capture


PROVIDERS = ("seeking_alpha", "financial_datasets")
STATEMENTS = {"income_statement": "income_statements", "balance_sheet": "balance_sheet",
              "cash_flow_statement": "cash_flow_statements"}


def _digest(value):
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


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
            records = sa_records(body, period)
        else:
            retained = read_fd_statements(dal, FinancialQuery(ticker=ticker, source=provider,
                statement=statement, period=period, currency=currency, freshness="stored"))
            statements = retained.statements.get(statement, [])
            source["source_observations"] = [item.model_dump() for item in retained.observations]
            source["gaps"] = [item.model_dump() for item in retained.gaps]
            if not statements:
                source["error_code"] = (retained.gaps[0].code if retained.gaps else
                                        "financial_comparison_stored_statement_missing")
                return source
            source["content_sha256"] = _digest([item.model_dump() for item in statements])
            source["source_url"] = None  # Old cache has no citation-level source pointer.
            records = fd_records(statements, period)
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
    sources: Optional[list[Literal["seeking_alpha", "financial_datasets"]]] = None,
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
        ticker = query_symbol(ticker)
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
            sources = list(dict.fromkeys((*load_route("sa_company_financials", dal).providers,
                                           *load_route("fundamentals_analysis", dal).providers)))
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
