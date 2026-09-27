"""Financial evidence crosses model boundaries whole or as an explicit page refusal."""

import json
import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.agents.shared.compressor.reducers import get_reducer
from src.sa.company_store import save_capture
from tests.financial_read_fixtures import financial_local, sa_payload
from tests.test_common_financial_read import read, route, SA
from tests.test_freshness_tool_channels import invoke
from tests.test_sec_research_tool_adapters import unwrap


@pytest.mark.parametrize("wrapped", [False, True])
@pytest.mark.parametrize("budget", [800, 100000])
def test_compressed_financial_read_preserves_basis_or_returns_gap(wrapped, budget):
    value = {"status": "ok", "read_id": "a" * 64, "data_source": "seeking_alpha",
             "metric_basis": {"gross_margin": {"precision": "provider_display_rounded"}},
             "read_gaps": [], "income_statements": [{"data": {"revenue": "12345678901234567890.12"},
                 "value_metadata": {"revenue": {"raw": "9" * 20000}}}]}
    payload = json.dumps(value)
    prefix, suffix = '<tool_output tool="get_fundamentals_analysis">\n', '\n</tool_output>'
    if wrapped:
        payload = prefix + payload + suffix
    result, meta = get_reducer("tool_get_fundamentals_analysis")(payload, budget=budget)
    decoded = json.loads(result[len(prefix):-len(suffix)] if wrapped else result)
    if budget == 100000:
        assert decoded == value and meta == {}
    else:
        assert decoded == {"status": "unavailable", "error_code": "financial_read_page_too_large",
                           "read_id": value["read_id"], "required_action": "repeat_same_read_with_smaller_page"}
        assert len(result) <= budget


def test_malformed_financial_output_never_becomes_truncated_numbers():
    result, _ = get_reducer("get_fundamentals_analysis")('{"revenue":123456', budget=800)
    assert json.loads(result)["error_code"] == "financial_read_result_invalid"


@pytest.mark.parametrize("channel", ["openai", "anthropic", "chatgpt", "claude"])
def test_all_financial_query_pins_and_precision_survive_channels(financial_local, channel):
    dal, http, sec = financial_local
    receipt = save_capture(sa_payload())
    arguments = dict(ticker="AAPL", source=SA, statement="income_statement", period="annual", currency="USD",
                     freshness="stored", observation_id=receipt["observation_id"], end_month="2025-12",
                     period_offset=0, period_limit=1)
    expected = read(dal, **arguments)
    arguments["read_id"] = expected.read_id
    result = unwrap(asyncio.run(invoke(channel, "get_fundamentals_analysis", arguments, dal)))
    assert result["status"] == "ok", result
    assert result["read_id"] == expected.read_id
    assert result["income_statements"][0]["period_precision"] == "month"
    assert result["metric_basis"]["gross_margin"]["precision"] == "provider_display_rounded"
    assert result["source_observations"][0]["fetched_at"] == expected.source_observations[0]["fetched_at"]
    http.assert_not_called()
    sec.assert_not_called()


@pytest.mark.parametrize("channel", ["openai", "anthropic", "chatgpt", "claude"])
def test_disabled_route_and_refresh_source_validation_survive_channels(financial_local, channel):
    dal, http, _ = financial_local
    route([])
    result = unwrap(asyncio.run(invoke(channel, "get_fundamentals_analysis", {
        "ticker": "AAPL", "freshness": "stored", "source": "auto"}, dal)))
    assert result["read_gaps"][0]["code"] == "data_source_route_disabled"
    result = unwrap(asyncio.run(invoke(channel, "get_fundamentals_analysis", {
        "ticker": "AAPL", "freshness": "refresh", "source": "auto"}, dal)))
    assert result["read_gaps"][0]["code"] == "financial_refresh_source_required"
    http.assert_not_called()


@pytest.mark.parametrize("wrapped", [False, True])
def test_financial_overflow_storage_failure_still_cannot_admit_sliced_json(wrapped):
    from src.agents.shared.compressor.layers import apply_layer_0
    payload = json.dumps({"status": "ok", "read_id": "a" * 64, "income_statements": ["x" * 20000]})
    prefix, suffix = '<tool_output tool="get_fundamentals_analysis">\n', '\n</tool_output>'
    if wrapped:
        payload = prefix + payload + suffix
    result, _ = apply_layer_0(tool_name="get_fundamentals_analysis", args={}, payload=payload,
        overflow_store=SimpleNamespace(write=Mock(side_effect=OSError())), budget_chars=800)
    result = result[len(prefix):-len(suffix)] if wrapped else result
    assert json.loads(result)["error_code"] == "financial_read_page_too_large"


def test_retired_detailed_and_peer_paths_do_not_acquire(financial_local, monkeypatch):
    from src.tools.analysis_tools import get_detailed_financials, get_peer_comparison
    dal, http, sec = financial_local
    forbidden = Mock(side_effect=AssertionError("unported financial operation must not acquire"))
    monkeypatch.setattr("data_sources.financial_metrics_calculator.FinancialMetricsCalculator", forbidden)
    monkeypatch.setattr("src.tools.analyst_tools._finnhub_get", forbidden)
    result = get_detailed_financials(dal, "AAPL").model_dump()
    assert result["status"] == "unavailable" and result["error_code"] == "financial_operation_not_ported"
    assert result["data_source"] == "none" and result["metric_gaps"]
    peers = get_peer_comparison(dal, tickers=["AAPL", "AMD"])
    assert peers["status"] == "unavailable" and peers["error_code"] == "financial_operation_not_ported"
    assert not peers.get("rankings") and not peers.get("comparison_matrix")
    forbidden.assert_not_called()
    http.assert_not_called()
    sec.assert_not_called()


def test_evidence_packet_keeps_sa_month_and_basis(financial_local, monkeypatch):
    from src.evidence_packet import gather_evidence
    save_capture(sa_payload())
    monkeypatch.setattr("src.tools.analyst_tools.get_analyst_consensus", lambda *_: {})
    packet = gather_evidence(financial_local[0], "AAPL", now_iso="2026-09-27T00:00:00+00:00")
    item = next(item for item in packet.items if item.source == "fundamentals:seeking_alpha")
    assert item.as_of is None
    assert item.data["metric_basis"]["gross_margin"]["end_month"] == "2025-12"
    assert item.data["metric_gaps"]["revenue_growth"] == "exact_period_identity_unavailable"
    assert item.data["source_observations"][0]["freshness_mode"] == "stored"
    assert item.data["read_id"]


def test_freshness_tool_uses_financial_coverage_not_expiry(financial_local, monkeypatch):
    from src.tools.freshness import check_data_freshness
    dal, http, _ = financial_local
    save_capture(sa_payload())
    monkeypatch.setattr(dal._backend, "query_health_stats", Mock(side_effect=RuntimeError("market read failed")))
    result = check_data_freshness(dal)
    assert "seeking_alpha" in result and "2025-12" in result and "mapping_not_reviewed" in result
    assert "fundamentals_cache" not in result and "expired" not in result
    http.assert_not_called()


@pytest.mark.parametrize("channel", ["openai", "anthropic", "chatgpt", "claude"])
@pytest.mark.parametrize("invalid", [{"period_limit": True}, {"period_offset": "1"}, {"unreviewed": True}])
def test_invalid_page_or_unknown_argument_never_starts_financial_access(channel, invalid, monkeypatch):
    access = Mock(side_effect=AssertionError("invalid query must not read or acquire"))
    monkeypatch.setattr("src.fundamentals.read_service.read_financials", access)
    result = asyncio.run(invoke(channel, "get_fundamentals_analysis", {
        "ticker": "AAPL", "freshness": "stored", **invalid}, object(), allow_errors=True))
    assert result and any(word in result.lower() for word in ("invalid", "error", "unknown", "unexpected keyword"))
    access.assert_not_called()
