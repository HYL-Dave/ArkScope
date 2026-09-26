"""App ticker aliases resolve only at SA query boundaries, never inside captures."""

import asyncio
from copy import deepcopy
from hashlib import sha256
import sqlite3

import pytest

from src.sa.company_data import CompanyDataFailure, symbol
from src.sa.company_store import read_capture, save_capture
from src.tools.sa_company_tools import get_sa_company_data
from tests.test_sa_company_data import capture, local
from tests.test_sa_company_research import research_capture


PAGES = [
    ("financials", path, view, "USD")
    for path in ("income-statement", "balance-sheet", "cash-flow-statement")
    for view in ("annual", "quarterly")
] + [
    ("valuation", "valuation/metrics", "snapshot", "DISPLAY"),
    ("peers", "peers/comparison", "snapshot", "DISPLAY"),
    ("estimates", "earnings/estimates", "annual", "DISPLAY"),
    ("revisions", "earnings/revisions", "annual", "DISPLAY"),
]


@pytest.fixture(autouse=True)
def no_provider_requests(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("SA symbol resolution must not contact a provider")

    monkeypatch.setattr("requests.sessions.Session.request", forbidden)


def provider_capture(dataset, path, view):
    if dataset == "financials":
        payload = capture(path, ticker="BRK.B")
        if view == "quarterly":
            payload["controls"]["period"] = "Quarterly"
            del payload["headers"][2]
            for row in payload["rows"][1:]:
                del row["values"][1]
        return payload
    payload = research_capture(dataset)
    payload.update(ticker="BRK.B", source_url=f"https://seekingalpha.com/symbol/BRK.B/{path}",
                   title=payload["title"].replace("AMD", "BRK.B"), heading="BRK.B - Example")
    for table in payload["tables"]:
        for header in table["headers"]:
            header.update(id=header["id"].replace("AMD", "BRK.B"), label=header["label"].replace("AMD", "BRK.B"))
    return payload


@pytest.mark.parametrize("dataset,path,view,currency", PAGES)
@pytest.mark.parametrize("ticker", ["BRK B", "BRK.B", "BRK-B"])
def test_all_company_pages_reopen_under_app_aliases(local, dataset, path, view, currency, ticker):
    dal, db = local
    payload = provider_capture(dataset, path, view)
    original = deepcopy(payload)
    receipt = save_capture(payload)
    before = sha256(db.read_bytes()).hexdigest()
    statement = path.replace("-", "_") if dataset == "financials" else dataset
    stored = read_capture(ticker, statement, view, currency, observation_id=receipt["observation_id"], db_path=db)
    assert stored is not None
    assert stored["ticker"] == "BRK.B" and stored["source_url"] == f"https://seekingalpha.com/symbol/BRK.B/{path}"
    assert stored["observation_id"] == receipt["observation_id"]
    kwargs = {"statement": statement, "view": view} if dataset == "financials" else {"dataset": dataset}
    result = get_sa_company_data(dal, ticker, observation_id=receipt["observation_id"], **kwargs)
    assert result["status"] == "ok" and result["ticker"] == "BRK.B"
    assert result["source_url"] == stored["source_url"] and result["provider"] == "seeking_alpha"
    assert result["observation_id"] == receipt["observation_id"]
    assert result["first_captured_at"] == payload["captured_at"]
    assert result["last_captured_at"] == payload["captured_at"]
    if dataset == "financials":
        assert result["rows"][0]["cells"][0]["raw"] == payload["rows"][1]["values"][1]
    else:
        assert result["rows"][0]["cells"][0]["raw"] == payload["tables"][0]["rows"][0]["values"][0]
    if dataset == "peers":
        assert [column["label"] for column in result["columns"]] == ["BRK.B", "INTC"]
    assert payload == original
    assert sha256(db.read_bytes()).hexdigest() == before
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT ticker, COUNT(*) FROM sa_company_observations GROUP BY ticker").fetchall() == [("BRK.B", 1)]


@pytest.mark.parametrize("dataset,path,view,currency", [PAGES[0], *PAGES[6:]])
@pytest.mark.parametrize("channel", ["openai", "anthropic", "chatgpt", "claude"])
def test_canonical_company_reads_reach_all_tool_channels(local, dataset, path, view, currency, channel):
    from tests.test_freshness_tool_channels import invoke
    from tests.test_sec_research_tool_adapters import unwrap

    dal, db = local
    receipt = save_capture(provider_capture(dataset, path, view))
    before = sha256(db.read_bytes()).hexdigest()
    result = unwrap(asyncio.run(invoke(channel, "get_sa_company_data", {
        "ticker": "BRK B", "dataset": dataset, "observation_id": receipt["observation_id"],
        "row_limit": 1, "column_limit": 1,
    }, dal)))
    assert result["status"] == "ok" and result["retrieval"] == "stored"
    assert result["ticker"] == "BRK.B" and result["provider"] == "seeking_alpha"
    assert result["source_url"] == f"https://seekingalpha.com/symbol/BRK.B/{path}"
    assert result["observation_id"] == receipt["observation_id"]
    assert sha256(db.read_bytes()).hexdigest() == before


@pytest.mark.parametrize("dataset,path,view,currency", PAGES)
def test_missing_canonical_capture_reports_provider_url_without_creating_database(local, dataset, path, view, currency):
    dal, db = local
    kwargs = {"statement": path.replace("-", "_"), "view": view} if dataset == "financials" else {"dataset": dataset}
    result = get_sa_company_data(dal, "BRK B", **kwargs)
    assert result["error_code"] == "sa_company_capture_missing"
    assert result["ticker"] == "BRK.B" and result["capture_url"] == f"https://seekingalpha.com/symbol/BRK.B/{path}"
    assert not db.exists()


@pytest.mark.parametrize("dataset,path,view,currency", [PAGES[0], *PAGES[6:]])
@pytest.mark.parametrize("alias", ["BRK B", "BRK-B"])
def test_query_alias_does_not_relax_source_capture_identity(local, dataset, path, view, currency, alias):
    payload = provider_capture(dataset, path, view)
    payload["ticker"] = alias
    with pytest.raises(CompanyDataFailure):
        save_capture(payload)
    assert not local[1].exists()


def test_source_symbol_validator_stays_strict():
    with pytest.raises(CompanyDataFailure, match="sa_company_ticker_invalid"):
        symbol("BRK B")
    assert symbol("BRK-B") == "BRK-B"


@pytest.mark.parametrize("ticker", ["BRK A", "BF B", "BRK/B", "BRK  B", "BRK\tB", "", None, []])
def test_unmapped_queries_do_not_guess_provider_symbols(local, ticker):
    result = get_sa_company_data(local[0], ticker)
    assert result["error_code"] == "sa_company_ticker_invalid"
    assert not local[1].exists()


def test_alias_cannot_reopen_a_different_company_observation(local):
    receipt = save_capture(capture(ticker="AMD"))
    assert read_capture("BRK B", "income_statement", "annual", "USD", observation_id=receipt["observation_id"], db_path=local[1]) is None
    result = get_sa_company_data(local[0], "BRK B", observation_id=receipt["observation_id"])
    assert result["error_code"] == "sa_company_capture_missing"
