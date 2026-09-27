"""The unported peer path must not rank incomplete or legacy financial results."""

import pytest
from unittest.mock import Mock


def test_direct_calculator_keeps_reviewed_tech_inputs():
    from tests.test_sec_metric_input_basis import entry, extractor, results
    _, _, calc = results(extractor({
        "Assets": [entry(200), entry(180,end="2024-12-31",fy=2024)],
        "Revenues": [entry(120,start="2025-01-01"), entry(100,start="2024-01-01",end="2024-12-31",fy=2024)],
        "ResearchAndDevelopmentExpense": [entry(12,start="2025-01-01")],
        "NetCashProvidedByUsedInOperatingActivities": [entry(30,start="2025-01-01")],
        "PaymentsToAcquirePropertyPlantAndEquipment": [entry(0,start="2025-01-01")],
    }))
    metrics, tech = calc.get_static_metrics_dict(), calc.get_tech_metrics()
    assert tech["rd_to_revenue"] == 0.1 and tech["rule_of_40"] == 45
    assert metrics["metric_basis"]["rd_to_revenue"]
    assert metrics["metric_basis"]["rule_of_40"]


@pytest.mark.parametrize("arguments", [{}, {"ticker": "NVDA"}, {"sector": "AI Chips"},
    {"tickers": ["AAPL", "AMD"]}, {"ticker": "UNKNOWN"}, {"tickers": []}])
def test_unported_peer_results_are_unavailable_without_reads_or_acquisition(monkeypatch, arguments):
    from src.tools.analysis_tools import get_peer_comparison
    forbidden = Mock(side_effect=AssertionError("peer operation is not ported"))
    monkeypatch.setattr("src.tools.analysis_tools.get_detailed_financials", forbidden)
    monkeypatch.setattr("requests.sessions.Session.request", forbidden)
    result = get_peer_comparison(object(), **arguments)
    assert result["status"] == "unavailable"
    assert result["error_code"] == "financial_operation_not_ported"
    assert result["peer_count"] == 0
    assert result["rankings"] is None and result["sector_stats"] == {}
    assert result["comparison_matrix"] == {} and result["comparison_gaps"]
    forbidden.assert_not_called()
