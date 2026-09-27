"""Disposable source observations, using the real stores and provider envelopes."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from data_sources import financial_datasets_client as fd_module
from src.tools.backends.local_market_backend import LocalMarketBackend
from tests.test_financial_datasets import MOCK_INCOME_RESPONSE, MOCK_BALANCE_RESPONSE, MOCK_CASHFLOW_RESPONSE
from tests.test_sa_company_data import capture


@pytest.fixture
def financial_local(tmp_path, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile.db"))
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(tmp_path / "market.db"))
    monkeypatch.setenv("ARKSCOPE_SA_DB", str(tmp_path / "sa.db"))
    backend = LocalMarketBackend(market_db=str(tmp_path / "market.db"))
    backend._sa_db = tmp_path / "sa.db"
    monkeypatch.setattr(fd_module, "_FILE_CACHE_DIR", tmp_path / "fd")
    monkeypatch.delenv("FINANCIAL_DATASETS_API_KEY", raising=False)
    http = Mock(side_effect=AssertionError("unexpected provider request"))
    monkeypatch.setattr(fd_module.requests, "get", http)
    sec = Mock(side_effect=AssertionError("unexpected SEC acquisition"))
    monkeypatch.setattr("data_sources.sec_edgar_financials.SECEdgarFinancials", sec)
    return SimpleNamespace(_backend=backend, get_user_profile=lambda: {}), http, sec


def sa_payload(statement="income-statement", *, ticker="AAPL", values=None):
    payload = capture(statement, ticker=ticker)
    values = values or {
        "income-statement": {"Total Revenues": "123.4", "Gross Profit": "30.0", "Operating Income": "10.0",
                             "Net Income": "5.0", "Basic EPS": "2.5", "Diluted EPS": "2.4"},
        "balance-sheet": {"Total Assets": "200.0", "Total Current Assets": "50.0",
                          "Total Liabilities": "100.0", "Total Current Liabilities": "20.0"},
        "cash-flow-statement": {"Cash from Operations": "20.0", "Cash from Investing": "(10.0)",
                                "Cash from Financing": "(5.0)"},
    }[statement]
    payload["rows"] = [{"kind": "section", "label": "Financials", "values": []}] + [
        {"kind": "data", "label": label, "values": ["", value, value, "1.0"]}
        for label, value in values.items()
    ]
    return payload


def save_fd(dal, kind="income_statement", *, age_days=200, from_file=False, change=None):
    prefix, dataset, limit, template = {
        "income_statement": ("income", "income_statements", 2, MOCK_INCOME_RESPONSE),
        "balance_sheet": ("balance", "balance_sheets", 1, MOCK_BALANCE_RESPONSE),
        "cash_flow_statement": ("cashflow", "cash_flow_statements", 2, MOCK_CASHFLOW_RESPONSE),
    }[kind]
    body = deepcopy(template)
    if change:
        change(body[dataset])
    fetched = datetime.now(timezone.utc) - timedelta(days=age_days)
    entry = {"ticker": "AAPL", "source": "financial_datasets", "fetched_at": fetched.isoformat(),
             "expires_at": (fetched + timedelta(days=180)).isoformat(),
             "data": fd_module.FinancialDatasetsClient._envelope(body, "AAPL", "annual", limit)}
    key = f"fd_v1_{prefix}_AAPL_annual_{limit}"
    if from_file:
        fd_module._FILE_CACHE_DIR.mkdir(exist_ok=True)
        (fd_module._FILE_CACHE_DIR / f"{key}.json").write_text(json.dumps(entry))
    else:
        assert dal._backend.set_financial_cache(key, entry["ticker"], entry["data"],
            source=entry["source"], fetched_at=entry["fetched_at"], expires_at=entry["expires_at"])
    return entry
