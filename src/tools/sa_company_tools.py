"""Local-only access to source-labeled SA company observations."""

from copy import deepcopy
import re
from typing import Literal, Optional

from src.data_source_routing import DataSourcePolicyFailure, load_route
from src.sa.company_data import CompanyDataFailure, PATHS, VIEWS, require, symbol
from src.sa.company_research import DATASETS, ROUTES
from src.sa.company_store import read_capture


def get_sa_company_data(
    dal,
    ticker: str,
    statement: Optional[Literal["income_statement", "balance_sheet", "cash_flow_statement"]] = None,
    view: Optional[Literal["annual", "quarterly", "snapshot"]] = None,
    currency: Optional[str] = None,
    observation_id: Optional[str] = None,
    row_offset: int = 0,
    row_limit: int = 20,
    column_offset: int = 0,
    column_limit: int = 4,
    dataset: Literal["financials", "valuation", "peers", "estimates", "revisions"] = "financials",
    table: Optional[str] = None,
):
    """Read an existing browser-captured table. No refresh, fallback or paid API.

    Numbers remain in the provider's displayed scale; financial unit_note
    includes the per-share exception. Research tables separate judgments and
    forecasts from filing facts. Month labels do not establish fiscal end days.
    An observation ID pins subsequent pages and reopens the same source values.
    """
    try:
        ticker = symbol(ticker)
        require(type(dataset) is str and dataset in {"financials", *DATASETS}, "sa_company_dataset_invalid")
        require(table is None or (type(table) is str and bool(table)), "sa_company_table_invalid")
        if dataset == "financials":
            statement = "income_statement" if statement is None else statement
            view = "annual" if view is None else view
            currency = "USD" if currency is None else currency
            require(type(statement) is str and statement in PATHS.values(), "sa_company_statement_invalid")
            require(type(view) is str and view in VIEWS.values(), "sa_company_view_unsupported")
            require(type(currency) is str and bool(re.fullmatch(r"[A-Z]{3}", currency)), "sa_company_currency_invalid")
            require(table is None, "sa_company_table_invalid")
        else:
            require(statement is None, "sa_company_statement_invalid")
            require(currency is None, "sa_company_currency_invalid")
            require(view is None or view == DATASETS[dataset][2], "sa_company_view_unsupported")
            statement, view, currency = dataset, DATASETS[dataset][2], "DISPLAY"
        require(observation_id is None or (type(observation_id) is str
                and bool(re.fullmatch(r"[a-f0-9]{64}", observation_id))), "sa_company_observation_id_invalid")
        for offset in (row_offset, column_offset):
            require(type(offset) is int and 0 <= offset < 2**63, "sa_company_pagination_invalid")
        for limit in (row_limit, column_limit):
            require(type(limit) is int and 0 < limit < 2**63, "sa_company_pagination_invalid")
        route = load_route(ROUTES.get(dataset, "sa_company_financials"), dal)
        route.candidates("seeking_alpha")
        backend = getattr(dal, "_backend", None)
        path = getattr(backend, "_sa_db", None)
        result = read_capture(ticker, statement, view, currency, observation_id=observation_id, db_path=path)
        if result is None:
            page_path = next(path for path, name in PATHS.items() if name == statement) if dataset == "financials" else DATASETS[dataset][0]
            return {"status": "unavailable", "error_code": "sa_company_capture_missing", "ticker": ticker,
                    "provider": "seeking_alpha", "dataset": dataset, "statement": statement, "view": view, "currency": currency,
                    "capture_url": f"https://seekingalpha.com/symbol/{ticker}/{page_path}",
                    "required_action": "capture_company_page_in_sa_extension", "retrieval": "stored"}
        result = deepcopy(result)
        result.setdefault("dataset", "financials")
        if dataset != "financials":
            tables = result.pop("tables")
            result["available_tables"] = [{"id": t["id"], "title": t["title"], "row_count": len(t["rows"]),
                                           "column_count": len(t["columns"])} for t in tables]
            selected = next((t for t in tables if t["id"] == table), None) if table is not None else tables[0]
            if selected is None:
                return {"status": "unavailable", "error_code": "sa_company_table_missing", "provider": "seeking_alpha",
                        "retrieval": "stored", "observation_id": result["observation_id"], "available_tables": result["available_tables"]}
            result.update(selected_table=selected["id"], table_title=selected["title"], rows=selected["rows"], columns=selected["columns"])
            if "earnings_basis" in selected:
                result["earnings_basis"] = selected["earnings_basis"]
        rows, columns = result["rows"], result["columns"]
        result["rows"] = rows[row_offset:row_offset + row_limit]
        result["columns"] = columns[column_offset:column_offset + column_limit]
        for row in result["rows"]:
            row["cells"] = row["cells"][column_offset:column_offset + column_limit]
        result.update(status="ok", retrieval="stored", source_route=route.describe("seeking_alpha", "seeking_alpha"),
                      pagination={"row_offset": row_offset, "row_count": len(result["rows"]), "total_rows": len(rows),
                                  "column_offset": column_offset, "column_count": len(result["columns"]),
                                  "total_columns": len(columns),
                                  "next_row_offset": row_offset + row_limit if row_offset + row_limit < len(rows) else None,
                                  "next_column_offset": column_offset + column_limit if column_offset + column_limit < len(columns) else None})
        return result
    except (CompanyDataFailure, DataSourcePolicyFailure) as exc:
        return {"status": "unavailable", "error_code": exc.code, "provider": "seeking_alpha", "retrieval": "stored"}
