"""Financial coverage is source-observed evidence, independent of price storage."""

import json
import sqlite3

import pytest

from src.sa.company_store import save_capture
from tests.financial_read_fixtures import financial_local, sa_payload, save_fd
from tests.test_common_financial_read import files, route, read, SA, FD


def coverage(dal=None, **kwargs):
    from src.fundamentals.coverage import financial_coverage
    return financial_coverage(dal, **kwargs)


def test_market_absent_does_not_hide_sa(financial_local, tmp_path):
    from src.market_data_admin import local_ticker_coverage
    from src.tools.data_coverage_tools import get_ticker_data_coverage
    dal, http, sec = financial_local
    save_capture(sa_payload())
    before = files(tmp_path)
    expected = read(dal).coverage.model_dump()
    default = coverage()
    assert default["candidate_count"] == 1 and default["scope"] == "configured_local_candidates"
    assert default["items"] == [expected]
    diagnostics = get_ticker_data_coverage("AAPL")
    assert diagnostics["financials"] == expected and diagnostics["market_db"]["exists"] is False
    local = local_ticker_coverage("AAPL")
    assert local["financials"] == expected and local["fundamentals"] is True and local["exists"] is False
    assert files(tmp_path) == before and not (tmp_path / "market.db").exists()
    http.assert_not_called()
    sec.assert_not_called()


def test_price_news_failure_does_not_erase_financials(financial_local, tmp_path):
    from src.market_data_admin import local_ticker_coverage
    from src.tools.data_coverage_tools import get_ticker_data_coverage
    dal, _, _ = financial_local
    save_capture(sa_payload())
    (tmp_path / "market.db").write_bytes(b"malformed market database")
    result = coverage(dal)
    assert result["status"] == "partial" and result["items"][0]["selected_source"] == SA
    assert any(g["code"] == "financial_inventory_unavailable" for g in result["gaps"])
    assert get_ticker_data_coverage("AAPL")["financials"]["selected_source"] == SA
    assert local_ticker_coverage("AAPL")["financials"]["selected_source"] == SA


@pytest.mark.parametrize("from_file", [True, False])
def test_coverage_not_ttl_or_sec_row_counts(financial_local, from_file):
    from tests.test_data_source_routing import save_sec
    dal, http, _ = financial_local
    save_sec(dal._backend)
    save_fd(dal, from_file=from_file)
    result = coverage(dal)
    assert result["candidate_count"] == 1
    item, = result["items"]
    assert item["selected_source"] == FD and item["statements"]["income_statement"][0]["end_month"] == "2025-09"
    assert not any("expired" in key or "valid_count" in key for key in result)
    http.assert_not_called()


def test_candidate_inventory_respects_routes_and_pages_only_selected_candidates(financial_local, monkeypatch):
    from src.fundamentals import read_service
    dal, _, _ = financial_local
    for ticker in ("AMD", "AAPL", "MSFT"):
        save_capture(sa_payload(ticker=ticker))
    route([FD])
    assert coverage(dal)["candidate_count"] == 0
    route([SA])
    calls = []
    original = read_service.read_financials
    def observed(dal, query):
        calls.append(query.ticker)
        return original(dal, query)
    monkeypatch.setattr(read_service, "read_financials", observed)
    result = coverage(dal, offset=1, limit=1)
    assert result["candidate_count"] == 3 and result["next_offset"] == 2 and result["offset"] == 1
    assert calls == ["AMD"] and result["items"][0]["ticker"] == "AMD"


def test_malformed_inventory_rows_are_not_claimed_as_covered(financial_local, tmp_path):
    dal, _, _ = financial_local
    save_fd(dal, from_file=True)
    root = tmp_path / "fd"
    (root / "junk.json").write_text("{bad json")
    (root / "fake.json").write_text(json.dumps({"ticker": "FAKE", "source": FD, "data": {}}))
    (root / "not-fd.json").write_text(json.dumps({"ticker": "NO", "source": "sec_edgar"}))
    result = coverage(dal)
    assert result["candidate_count"] == 1 and result["items"][0]["ticker"] == "AAPL"
    assert result["status"] == "partial" and result["gaps"]


def test_corrupt_sa_candidate_is_not_hidden_or_certified(financial_local, tmp_path):
    dal, _, _ = financial_local
    save_capture(sa_payload())
    with sqlite3.connect(tmp_path / "sa.db") as conn:
        conn.execute("UPDATE sa_company_observations SET body_json='{}'")
    result = coverage(dal)
    assert result["candidate_count"] == 1 and result["items"][0]["status"] == "unavailable"
    assert any(g["code"] == "sa_company_observation_invalid" for g in result["items"][0]["gaps"])


def test_explicit_tickers_are_unique_requested_scope_not_storage_claim(financial_local):
    result = coverage(financial_local[0], tickers=["aapl", "AAPL", "AMD"], limit=1)
    assert result["candidate_count"] == 2 and result["items"][0]["status"] == "unavailable"
    assert result["next_offset"] == 1


@pytest.mark.parametrize("kwargs", [{"limit": 0}, {"limit": 101}, {"limit": True}, {"offset": -1},
                                     {"source": "sec_edgar"}, {"period": "monthly"}, {"tickers": "AAPL"}])
def test_invalid_inventory_queries_are_typed(financial_local, kwargs):
    result = coverage(financial_local[0], **kwargs)
    assert result["status"] == "unavailable" and result["gaps"][0]["code"] == "financial_query_invalid"


def test_missing_tables_are_empty_not_failures(financial_local, tmp_path):
    with sqlite3.connect(tmp_path / "sa.db") as conn:
        conn.execute("CREATE TABLE unrelated (id)")
    result = coverage(financial_local[0])
    assert result["status"] == "ok" and result["candidate_count"] == 0 and not result["gaps"]


def test_coverage_preserves_acquisition_time_and_display_units(financial_local):
    payload = sa_payload()
    save_capture(payload)
    row = coverage(financial_local[0])["items"][0]["statements"]["income_statement"][0]
    assert row["fetched_at"] == payload["captured_at"]
    assert row["unit_note"] == payload["unit_note"]
    assert row["value_precision"] == ["provider_display_rounded"]
