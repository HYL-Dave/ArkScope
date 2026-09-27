"""Bounded projection of selected local candidates, not a provider entitlement probe."""

from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from data_sources import financial_datasets_client as fd_module
from src.data_source_routing import DataSourcePolicyFailure, load_route
from src.fundamentals.contracts import FinancialQuery
from src.fundamentals.reuse import instant
from src.fundamentals import read_service
from src.sa_capture_store import resolve_sa_db_path
from src.market_data_admin import resolve_market_db_path


def _rows(path, table, sql, parameters=()):
    path = Path(path).expanduser().resolve()
    if not path.exists():
        return
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
            yield from conn.execute(sql, parameters)


def _fd_candidate(row, period, *, key=None):
    if not isinstance(row, dict) or row.get("source", "financial_datasets") != "financial_datasets":
        return None
    ticker = FinancialQuery(ticker=row.get("ticker"), period=period).ticker
    fetched, expires = instant(row.get("fetched_at")), instant(row.get("expires_at"))
    if fetched is None or expires is None or expires < fetched or fetched > datetime.now(timezone.utc):
        raise ValueError("invalid acquisition identity")
    data = row.get("data")
    if isinstance(data, str):
        data = json.loads(data)
    versioned = isinstance(data, dict) and "fd_cache_version" in data
    if versioned:
        if (type(data.get("fd_cache_version")) is not int or data["fd_cache_version"] != 1
                or data.get("ticker") != ticker or type(data.get("requested_limit")) is not int
                or data["requested_limit"] < 1):
            raise ValueError("invalid envelope")
        if data.get("period") != period:
            return None
        limit = data["requested_limit"]
        payload = data.get("payload")
    else:
        payload, limit = data, None
    for prefix, dataset in (("income", "income_statements"), ("balance", "balance_sheets"),
                            ("cashflow", "cash_flow_statements")):
        if fd_module._valid_rows(payload, dataset, ticker, period):
            expected = f"fd_v1_{prefix}_{ticker}_{period}_{limit}" if versioned else f"{prefix}_{ticker}_{period}"
            if key is not None and key != expected:
                raise ValueError("cache identity mismatch")
            return ticker
    raise ValueError("not retained statements")


def financial_coverage(dal=None, *, tickers=None, period="annual", source="auto", currency="USD", offset=0, limit=25):
    result = dict(status="ok", scope="configured_local_candidates", candidate_count=0, items=[],
                  offset=offset, next_offset=None, gaps=[])
    try:
        query = FinancialQuery(ticker="COVERAGE", period=period, source=source, currency=currency)
        if (type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100
                or tickers is not None and type(tickers) is not list):
            raise ValueError("pagination or ticker list")
        explicit = {FinancialQuery(ticker=t).ticker for t in tickers} if tickers is not None else None
    except (ValueError, TypeError):
        return {**result, "status": "unavailable", "gaps": [{"provider": "financials", "code": "financial_query_invalid"}]}
    if dal is None:
        from src.tools.data_access import DataAccessLayer
        dal = DataAccessLayer()
    try:
        sources = load_route("fundamentals_analysis", dal).candidates(source)
    except DataSourcePolicyFailure as exc:
        return {**result, "status": "unavailable", "gaps": [{"provider": "financials", "code": exc.code}]}
    candidates = set() if explicit is None else explicit
    backend = getattr(dal, "_backend", None)

    def failure(provider, code):
        gap = dict(provider=provider, code=code)
        if gap not in result["gaps"]:
            result["gaps"].append(gap)

    def collect_fd(row, key):
        try:
            ticker = _fd_candidate(row, period, key=key)
            if ticker:
                candidates.add(ticker)
        except (ValueError, TypeError, KeyError):
            failure("financial_datasets", "financial_inventory_entry_invalid")

    if explicit is None and "seeking_alpha" in sources:
        try:
            path = getattr(backend, "_sa_db", None) or resolve_sa_db_path()
            for row in _rows(path, "sa_company_observations",
                    "SELECT DISTINCT ticker FROM sa_company_observations WHERE period_view=? AND currency=? "
                    "AND statement IN ('income_statement','balance_sheet','cash_flow_statement')", (period, currency)):
                try:
                    candidates.add(FinancialQuery(ticker=row["ticker"]).ticker)
                except (ValueError, TypeError):
                    failure("seeking_alpha", "financial_inventory_entry_invalid")
        except (OSError, sqlite3.Error, TypeError):
            failure("seeking_alpha", "financial_inventory_unavailable")
    if explicit is None and "financial_datasets" in sources:
        try:
            path = getattr(backend, "_market_db", None) or resolve_market_db_path()
            for row in _rows(path, "financial_cache", "SELECT * FROM financial_cache WHERE source='financial_datasets'"):
                collect_fd(dict(row), row["cache_key"])
        except (OSError, sqlite3.Error, TypeError):
            failure("financial_datasets", "financial_inventory_unavailable")
        try:
            for path in fd_module._FILE_CACHE_DIR.glob("*.json"):
                try:
                    collect_fd(json.loads(path.read_text()), path.stem)
                except (OSError, ValueError, UnicodeError):
                    failure("financial_datasets", "financial_inventory_entry_invalid")
        except OSError:
            failure("financial_datasets", "financial_inventory_unavailable")
    ordered = sorted(candidates)
    result["candidate_count"] = len(ordered)
    for ticker in ordered[offset:offset + limit]:
        item = read_service.read_financials(dal, query.model_copy(update={"ticker": ticker})).coverage
        result["items"].append(item.model_dump())
    if offset + limit < len(ordered):
        result["next_offset"] = offset + limit
    if result["gaps"] or any(item["status"] != "ok" for item in result["items"]):
        result["status"] = "partial"
    return result
