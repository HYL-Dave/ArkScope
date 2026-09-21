"""Stored provider observations remain distinct, aligned and non-authoritative."""

import asyncio
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.fundamentals.cache import fundamentals_analysis_cache_key
from src.sa.company_store import save_capture
from src.tools.financial_comparison_tools import compare_financial_sources
from src.tools.schemas import FinancialStatement, FundamentalsResult
from tests.test_financial_local_reuse import local
from tests.test_sa_company_data import capture


@pytest.fixture
def sources(local, tmp_path, monkeypatch):
    dal, http, sec = local
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile.db"))
    monkeypatch.setenv("ARKSCOPE_SA_DB", str(tmp_path / "sa.db"))
    dal._backend._sa_db = tmp_path / "sa.db"
    payload = capture(ticker="AAPL")
    payload["rows"][1]["values"][2] = "123.4"
    payload["rows"][2]["values"][2] = "10.0"
    payload["rows"][3]["values"][2] = "2.50"
    save_capture(payload)
    save_sec(dal)
    return dal, http, sec


def save_sec(dal, *, currency="USD", end="2025-12-27", revenue=123_440_000, period="annual"):
    fetched = datetime.now(timezone.utc) - timedelta(days=2)
    statement = FinancialStatement(report_period=end, fiscal_period="2025-FY", period_type=period,
                                   currency=currency, data={"revenue": revenue, "net_income": 10_000_000,
                                                            "earnings_per_share": 2.5})
    result = FundamentalsResult(ticker="AAPL", data_source="sec_edgar", snapshot_date=end,
                                income_statements=[statement])
    assert dal._backend.set_financial_cache(
        fundamentals_analysis_cache_key("AAPL", period), "AAPL", result.model_dump(), source="sec_edgar",
        fetched_at=fetched.isoformat(), expires_at=(fetched + timedelta(days=90)).isoformat(),
    )


def compare(dal, **kwargs):
    return compare_financial_sources(dal, "AAPL", sources=["seeking_alpha", "sec_edgar"], **kwargs)


def metric(result, name):
    return next(row for row in result["rows"] if row["metric"] == name)


def test_new_statements_keep_currency_without_inventing_it_for_legacy_rows():
    from data_sources.sec_edgar_financials import IncomeStatement
    from src.tools.analysis_tools import _sec_to_financial_statement

    source = IncomeStatement("AAPL", "2025-12-27", "2025-FY", "annual", "EUR", revenue=1)
    assert _sec_to_financial_statement(source).currency == "EUR"
    assert FinancialStatement(report_period="2025-12-27", period_type="annual", data={}).currency is None


def test_scale_rounding_and_period_precision_are_explicit(sources):
    result = compare(sources[0], row_limit=100)
    assert result["retrieval"] == "stored" and result["end_month"] == "2025-12"
    assert result["period_selection"] == "latest_common_stored_month"
    revenue = metric(result, "revenue")
    left, right = revenue["values"]
    assert (left["raw"], left["normalized_value"], left["scale"]) == ("123.4", "123400000", "1000000")
    assert left["period_end"] is None and right["period_end"] == "2025-12-27"
    pair = revenue["comparisons"][0]
    assert pair["difference_right_minus_left"] == "40000"
    assert pair["status"] == "rounding_compatible"
    assert pair["basis"] == "displayed_period_month"
    assert "exact_period_unverified" in pair["limitations"]
    assert "accounting_definition_unverified" in pair["limitations"]
    assert metric(result, "earnings_per_share")["values"][0]["normalized_value"] == "2.5"
    assert metric(result, "earnings_per_share")["values"][0]["unit"] == "USD/share"
    assert result["sources"][0]["observation_id"]
    assert result["sources"][0]["source_url"].endswith("/AAPL/income-statement")
    assert result["sources"][0]["unit_note"] == "In Millions of United States Dollar (USD) except per share items"
    assert result["sources"][1]["content_sha256"]
    assert result["sources"][1]["historical_reopen_supported"] is False


def test_larger_difference_is_not_explained_by_invented_restatement_or_gaap(sources):
    save_sec(sources[0], revenue=140_000_000)
    pair = metric(compare(sources[0]), "revenue")["comparisons"][0]
    assert pair["status"] == "difference_unexplained"
    assert pair["difference_right_minus_left"] == "16600000"
    assert pair["cause"] is None and pair["materiality_assessment"] is None


@pytest.mark.parametrize("currency,reason", [(None, "currency_unknown"), ("EUR", "currency_mismatch")])
def test_currency_gaps_block_arithmetic_not_source_visibility(sources, currency, reason):
    save_sec(sources[0], currency=currency)
    row = metric(compare(sources[0]), "revenue")
    assert all(v["normalized_value"] is not None for v in row["values"])
    pair = row["comparisons"][0]
    assert pair["status"] == "not_comparable" and reason in pair["reasons"]
    assert pair["difference_right_minus_left"] is None


def test_different_months_never_compare_latest_against_latest(sources):
    save_sec(sources[0], end="2025-09-27")
    result = compare(sources[0])
    assert result["status"] == "unavailable" and result["error_code"] == "financial_comparison_period_unavailable"
    assert result["rows"] == []
    assert result["sources"][1]["available_months"] == ["2025-09"]
    chosen = compare(sources[0], end_month="2025-12")
    assert chosen["period_selection"] == "explicit_month"
    row = metric(chosen, "revenue")
    assert row["values"][1]["status"] == "period_missing"
    assert row["comparisons"][0]["status"] == "not_comparable"


def test_ttm_is_not_a_substitute_for_a_requested_financial_period(sources):
    result = compare(sources[0], end_month="2026-01")
    assert all(v["normalized_value"] is None for row in result["rows"] for v in row["values"])
    assert all("2026-01" not in s["available_months"] for s in result["sources"])


def test_quarterly_statements_do_not_reuse_an_annual_capture_or_cache(sources):
    save_sec(sources[0], period="quarterly")
    result = compare(sources[0], period="quarterly", end_month="2025-12")
    row = metric(result, "revenue")
    assert row["values"][0]["status"] == "source_unavailable"
    assert row["values"][1]["normalized_value"] == "123440000"
    assert row["comparisons"][0]["difference_right_minus_left"] is None


def test_no_cross_statement_fill_and_no_legacy_ratio_comparison(sources):
    result = compare(sources[0], statement="balance_sheet", end_month="2025-12", row_limit=100)
    assert all(v["normalized_value"] is None for row in result["rows"] for v in row["values"])
    assert "total_debt" not in {row["metric"] for row in result["rows"]}  # No liabilities-as-debt.
    assert not {"debt_to_equity", "roe", "pe_ratio"} & {row["metric"] for row in result["rows"]}


def test_comparison_is_read_only_and_never_constructs_acquisition(sources, monkeypatch, tmp_path):
    dal, http, sec = sources
    paths = [p for p in tmp_path.rglob("*") if p.is_file()]
    before = {p: sha256(p.read_bytes()).hexdigest() for p in paths}
    forbidden = Mock(side_effect=AssertionError("comparison must not acquire or write"))
    monkeypatch.setattr(dal._backend, "set_financial_cache", forbidden)
    monkeypatch.setattr("src.sa_capture_store.connect", forbidden)
    result = compare(dal)
    assert result["rows"]
    assert {p: sha256(p.read_bytes()).hexdigest() for p in paths} == before
    added = set(p for p in tmp_path.rglob("*") if p.is_file()) - set(paths)
    # SQLite's read-only WAL coordination may create empty sidecars, not data.
    assert all(p.name.endswith(("-wal", "-shm")) for p in added)
    assert all(p.stat().st_size == 0 for p in added if p.name.endswith("-wal"))
    http.assert_not_called()
    sec.assert_not_called()
    forbidden.assert_not_called()


def test_disabled_source_stays_disabled_even_when_its_capture_exists(sources):
    from src.data_provider_config import DataProviderConfigStore
    import os

    config = DataProviderConfigStore(os.environ["ARKSCOPE_PROFILE_DB"])
    config.set_setting("data_sources.route.sa_company_financials", "[]")
    result = compare(sources[0], end_month="2025-12")
    assert result["sources"][0]["error_code"] == "data_source_not_selected"
    assert all(row["values"][0]["normalized_value"] is None for row in result["rows"])


def save_fd_statement(dal, *, end="2025-12-27", currency="USD", revenue=123_440_000, duplicates=False):
    from data_sources.financial_datasets_client import FinancialDatasetsClient

    row = {"ticker": "AAPL", "report_period": end, "fiscal_period": "2025-FY", "period": "annual",
           "currency": currency, "revenue": revenue}
    rows = [row, {**row, "revenue": revenue + 1}] if duplicates else [row]
    fetched = datetime.now(timezone.utc) - timedelta(days=2)
    body = FinancialDatasetsClient._envelope({"income_statements": rows}, "AAPL", "annual", 2)
    assert dal._backend.set_financial_cache("fd_v1_income_AAPL_annual_2", "AAPL", body, source="financial_datasets",
        fetched_at=fetched.isoformat(), expires_at=(fetched + timedelta(days=180)).isoformat())


def test_fd_comparison_needs_neither_paid_authority_nor_other_statements(sources, monkeypatch):
    dal, http, sec = sources
    save_fd_statement(dal)
    forbidden = Mock(side_effect=AssertionError("comparison must not invoke ratio or acquisition paths"))
    monkeypatch.setattr("src.tools.analysis_tools.get_fundamentals_analysis", forbidden)
    monkeypatch.delenv("FINANCIAL_DATASETS_API_KEY", raising=False)
    result = compare_financial_sources(dal, "AAPL")
    assert [s["provider"] for s in result["sources"]] == ["seeking_alpha", "sec_edgar", "financial_datasets"]
    revenue = metric(result, "revenue")
    assert len(revenue["comparisons"]) == 3
    assert revenue["comparisons"][2]["basis"] == "period_end"
    assert revenue["comparisons"][2]["status"] == "same_displayed_value"
    assert result["sources"][2]["source_observations"][0]["freshness_mode"] == "stored"
    assert len(json.dumps(result)) < 12000  # The default page fits the OAuth bridge.
    http.assert_not_called(); sec.assert_not_called(); forbidden.assert_not_called()


def test_conflicting_exact_days_and_ambiguous_provider_periods_do_not_get_deltas(sources):
    dal = sources[0]
    save_fd_statement(dal, end="2025-12-31")
    result = compare_financial_sources(dal, "AAPL", sources=["sec_edgar", "financial_datasets"])
    assert metric(result, "revenue")["comparisons"][0]["reasons"] == ["period_end_mismatch"]
    save_fd_statement(dal, duplicates=True)
    result = compare_financial_sources(dal, "AAPL", sources=["sec_edgar", "financial_datasets"])
    assert metric(result, "revenue")["values"][1]["status"] == "period_ambiguous"
    assert metric(result, "revenue")["comparisons"][0]["difference_right_minus_left"] is None


@pytest.mark.parametrize("left,right", [(0, 1), (-1, -2), (1e-308, 1e308), (1e308, 1e-308)])
def test_zero_negative_and_extreme_finite_values_do_not_break_decimal_boundary(sources, left, right):
    dal = sources[0]
    save_sec(dal, revenue=left)
    save_fd_statement(dal, revenue=right)
    result = compare_financial_sources(dal, "AAPL", sources=["sec_edgar", "financial_datasets"])
    pair = metric(result, "revenue")["comparisons"][0]
    assert pair["difference_right_minus_left"] is not None
    assert (pair["relative_difference_pct"] is None) == (left == 0)
    assert "NaN" not in json.dumps(pair) and "Infinity" not in json.dumps(pair)


def test_unknown_sa_row_is_not_filled_from_a_similar_label():
    # The capture baseline is independent; the comparator must not select this
    # similarly named row as if it were the recognized Net Income row.
    from src.sa.company_data import normalize_capture
    from src.fundamentals.source_comparison import source_value
    body = normalize_capture(capture(ticker="AAPL"))["body"]
    body["rows"][1]["label"] = "Net Income to Company"
    source = {"provider": "seeking_alpha", "status": "ok", "records": [{
        "end_month": "2025-12", "period_end": None, "currency": "USD", "rows": body["rows"],
        "unit_note": body["unit_note"], "column_index": 1}]}
    assert source_value(source, "net_income", "Net Income", "money", "2025-12")["status"] == "metric_missing"


@pytest.mark.parametrize("kwargs", [{"period": "ttm"}, {"sources": []}, {"sources": ["sec_edgar"]},
                                   {"sources": ["sec_edgar", "sec_edgar"]}, {"sources": ["unknown", "sec_edgar"]},
                                   {"end_month": "2025-13"}, {"end_month": "2025-12-31"},
                                   {"row_limit": True}, {"row_offset": -1}])
def test_bad_queries_are_rejected_before_reading_any_store(sources, monkeypatch, kwargs):
    forbidden = Mock(side_effect=AssertionError("bad query must not read"))
    monkeypatch.setattr("src.tools.financial_comparison_tools.load_route", forbidden)
    assert compare_financial_sources(sources[0], "AAPL", **kwargs)["error_code"] == "financial_comparison_query_invalid"
    forbidden.assert_not_called()


@pytest.mark.parametrize("channel", ["openai", "anthropic", "chatgpt", "claude"])
def test_all_model_channels_preserve_qualified_differences(sources, channel):
    from tests.test_freshness_tool_channels import invoke
    from tests.test_sec_research_tool_adapters import unwrap

    result = unwrap(asyncio.run(invoke(channel, "compare_financial_sources", {
        "ticker": "AAPL", "sources": ["seeking_alpha", "sec_edgar"], "row_limit": 1,
    }, sources[0])))
    assert result["retrieval"] == "stored" and len(result["rows"]) == 1
    assert result["rows"][0]["comparisons"][0]["status"] == "rounding_compatible"
    assert result["pagination"]["next_row_offset"] == 1


def test_same_content_pagination_detects_changed_provider_cache(sources):
    first = compare(sources[0], row_limit=1)
    same = compare(sources[0], row_offset=1, row_limit=1, comparison_id=first["comparison_id"])
    assert same["comparison_id"] == first["comparison_id"]
    save_sec(sources[0], revenue=150_000_000)
    changed = compare(sources[0], row_offset=1, comparison_id=first["comparison_id"])
    assert changed["status"] == "unavailable" and changed["error_code"] == "financial_comparison_changed"
    assert not changed.get("rows")


@pytest.mark.parametrize("wrapped", [False, True])
def test_compressor_never_slices_source_or_comparability_metadata(sources, wrapped):
    from src.agents.shared.compressor.layers import apply_layer_0

    payload = json.dumps(compare(sources[0], row_limit=100))
    if wrapped:
        payload = '<tool_output tool="compare_financial_sources">\n' + payload + '\n</tool_output>'
    reduced, _ = apply_layer_0(tool_name="compare_financial_sources", args={}, payload=payload,
                               overflow_store=SimpleNamespace(write=Mock(side_effect=OSError())), budget_chars=900)
    if wrapped:
        reduced = reduced.split("\n", 1)[1].rsplit("\n", 1)[0]
    value = json.loads(reduced)
    assert value["error_code"] == "financial_comparison_page_too_large"
    assert "rows" not in value
