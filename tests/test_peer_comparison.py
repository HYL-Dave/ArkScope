"""
Tests for peer comparison tool (Batch 2b).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ============================================================
# Helper to create mock DetailedFinancials
# ============================================================

def _mock_financials(ticker, **overrides):
    """Create a mock DetailedFinancials object."""
    from src.tools.schemas import DetailedFinancials

    defaults = {
        "ticker": ticker,
        "data_source": "sec_edgar",
        "report_date": "2025-12-31",
        "valuation_price_basis": {
            "available": True,
            "source": "local_market_db",
            "interval": "15min",
            "required_market_date": "2026-07-31",
            "market_date": "2026-07-31",
            "timestamp": "2026-07-31T19:45:00+00:00",
            "price": 100.0,
            "empty_reason": None,
        },
        "pe_ratio": 30.0,
        "ev_to_ebitda": 25.0,
        "ev_to_revenue": 10.0,
        "ps_ratio": 8.0,
        "pb_ratio": 5.0,
        "peg_ratio": 1.5,
        "fcf_yield": 0.03,
        "gross_margin": 0.60,
        "operating_margin": 0.30,
        "net_margin": 0.20,
        "roe": 0.25,
        "roic": 0.20,
        "revenue_growth": 0.15,
        "earnings_growth": 0.10,
        "debt_to_equity": 0.5,
        "current_ratio": 2.0,
        "rule_of_40": 45.0,
        "rd_to_revenue": 0.10,
    }
    from src.tools.analysis_tools import _COMPARISON_METRICS
    defaults["metric_basis"] = {field: {"report_period": "2025-12-31", "period": "annual", "currency": "USD"}
                               for field, _, _ in _COMPARISON_METRICS}
    defaults.update(overrides)
    return DetailedFinancials(**defaults)


def test_real_calculator_emits_tech_bases_accepted_by_peer_statistics(monkeypatch):
    from tests.test_sec_metric_input_basis import entry, extractor, results
    from src.tools.analysis_tools import get_peer_comparison
    from src.tools.schemas import DetailedFinancials

    _, _, calc = results(extractor({
        "Assets": [entry(200), entry(180,end="2024-12-31",fy=2024)],
        "Revenues": [entry(120,start="2025-01-01"), entry(100,start="2024-01-01",end="2024-12-31",fy=2024)],
        "ResearchAndDevelopmentExpense": [entry(12,start="2025-01-01")],
        "NetCashProvidedByUsedInOperatingActivities": [entry(30,start="2025-01-01")],
        "PaymentsToAcquirePropertyPlantAndEquipment": [entry(0,start="2025-01-01")],
    }))
    metrics, tech = calc.get_static_metrics_dict(), calc.get_tech_metrics()
    assert tech["rd_to_revenue"] == 0.1 and tech["rule_of_40"] == 45
    def financials(dal, ticker):
        return DetailedFinancials(ticker=ticker, data_source="sec_edgar", metric_basis=metrics["metric_basis"],
                                  rd_to_revenue=tech["rd_to_revenue"], rule_of_40=tech["rule_of_40"])
    monkeypatch.setattr("src.tools.analysis_tools.get_detailed_financials", financials)
    result = get_peer_comparison(object(), tickers=["A","B"])
    assert result["sector_stats"]["rd_to_revenue"]["count"] == 2
    assert result["sector_stats"]["rule_of_40"]["count"] == 2


# ============================================================
# Sector detection
# ============================================================

class TestSectorDetection:
    """Test auto-detection of sector from sectors.yaml."""

    def test_nvda_found_in_ai_chips(self):
        from src.tools.analysis_tools import get_peer_comparison

        mock_dal = MagicMock()
        mock_dal.get_all_sectors.return_value = {
            "AI_CHIPS": ["NVDA", "AMD", "AVGO"],
            "AI_SOFTWARE": ["MSFT", "GOOGL"],
        }
        mock_dal.get_sector_tickers.return_value = ["NVDA", "AMD", "AVGO"]

        with patch("src.tools.analysis_tools.get_detailed_financials") as mock_gdf:
            mock_gdf.side_effect = lambda dal, t: _mock_financials(t)
            result = get_peer_comparison(mock_dal, ticker="NVDA")

        assert result["sector"] == "AI_CHIPS"
        assert result["target_ticker"] == "NVDA"
        assert result["peer_count"] == 3

    def test_unknown_ticker(self):
        from src.tools.analysis_tools import get_peer_comparison

        mock_dal = MagicMock()
        mock_dal.get_all_sectors.return_value = {
            "AI_CHIPS": ["NVDA", "AMD"],
        }

        result = get_peer_comparison(mock_dal, ticker="ZZZZ")
        assert "error" in result

    def test_no_args_returns_error(self):
        from src.tools.analysis_tools import get_peer_comparison

        mock_dal = MagicMock()
        result = get_peer_comparison(mock_dal)
        assert "error" in result


# ============================================================
# Comparison matrix
# ============================================================

class TestComparisonMatrix:
    """Test comparison matrix structure and content."""

    def _run_comparison(self, tickers_data):
        from src.tools.analysis_tools import get_peer_comparison

        mock_dal = MagicMock()

        with patch("src.tools.analysis_tools.get_detailed_financials") as mock_gdf:
            mock_gdf.side_effect = lambda dal, t: tickers_data[t]
            result = get_peer_comparison(
                mock_dal, tickers=list(tickers_data.keys())
            )
        return result

    def test_matrix_has_all_peers(self):
        data = {
            "AAPL": _mock_financials("AAPL", pe_ratio=28.0),
            "MSFT": _mock_financials("MSFT", pe_ratio=32.0),
            "GOOGL": _mock_financials("GOOGL", pe_ratio=22.0),
        }
        result = self._run_comparison(data)
        assert "comparison_matrix" in result
        assert set(result["comparison_matrix"].keys()) == {"AAPL", "MSFT", "GOOGL"}

    def test_matrix_contains_metrics(self):
        data = {
            "A": _mock_financials("A", gross_margin=0.70),
            "B": _mock_financials("B", gross_margin=0.50),
        }
        result = self._run_comparison(data)
        assert result["comparison_matrix"]["A"]["gross_margin"] == 0.70
        assert result["comparison_matrix"]["B"]["gross_margin"] == 0.50

    def test_sector_stats_computed(self):
        data = {
            "A": _mock_financials("A", pe_ratio=20.0),
            "B": _mock_financials("B", pe_ratio=30.0),
            "C": _mock_financials("C", pe_ratio=40.0),
        }
        result = self._run_comparison(data)
        stats = result["sector_stats"]["pe_ratio"]
        assert stats["median"] == 30.0
        assert stats["count"] == 3

    def test_handles_none_values(self):
        data = {
            "A": _mock_financials("A", pe_ratio=20.0, peg_ratio=None),
            "B": _mock_financials("B", pe_ratio=30.0, peg_ratio=None),
        }
        result = self._run_comparison(data)
        assert result["sector_stats"]["peg_ratio"]["count"] == 0

    @pytest.mark.parametrize("change", [{"report_period": "2024-12-31"}, {"currency": "EUR"},
                                       {"period": "quarterly"}])
    def test_mismatched_metric_basis_keeps_raw_values_but_not_statistics(self, change):
        a, b = _mock_financials("A"), _mock_financials("B")
        b.metric_basis["debt_to_equity"].update(change)
        result = self._run_comparison({"A": a, "B": b})
        assert result["comparison_matrix"]["A"]["debt_to_equity"] == 0.5
        assert result["sector_stats"]["debt_to_equity"]["count"] == 0
        assert result["comparison_gaps"]["debt_to_equity"]["code"] == "metric_basis_mismatch"

    def test_unknown_basis_is_not_permission_to_rank(self):
        result = self._run_comparison({"A": _mock_financials("A", metric_basis={}), "B": _mock_financials("B")})
        assert result["sector_stats"]["roe"]["count"] == 0
        assert result["comparison_gaps"]["roe"]["code"] == "metric_basis_unavailable"

    def test_different_market_dates_cannot_be_ranked_together(self):
        a, b = _mock_financials("A"), _mock_financials("B")
        b.valuation_price_basis.market_date = "2026-07-30"
        result = self._run_comparison({"A": a, "B": b})
        assert result["sector_stats"]["pe_ratio"]["count"] == 0
        assert result["comparison_gaps"]["pe_ratio"]["code"] == "market_basis_mismatch"
        assert result["sector_stats"]["roe"]["count"] == 2


# ============================================================
# Rankings
# ============================================================

class TestPercentileRanking:
    """Test percentile ranking calculations."""

    def test_ranking_with_target(self):
        from src.tools.analysis_tools import get_peer_comparison

        mock_dal = MagicMock()
        mock_dal.get_all_sectors.return_value = {
            "TEST": ["A", "B", "C", "D", "E"],
        }
        mock_dal.get_sector_tickers.return_value = ["A", "B", "C", "D", "E"]

        financials = {
            "A": _mock_financials("A", pe_ratio=10.0, gross_margin=0.80),
            "B": _mock_financials("B", pe_ratio=20.0, gross_margin=0.60),
            "C": _mock_financials("C", pe_ratio=30.0, gross_margin=0.40),
            "D": _mock_financials("D", pe_ratio=40.0, gross_margin=0.20),
            "E": _mock_financials("E", pe_ratio=50.0, gross_margin=0.10),
        }

        with patch("src.tools.analysis_tools.get_detailed_financials") as mock_gdf:
            mock_gdf.side_effect = lambda dal, t: financials[t]
            result = get_peer_comparison(mock_dal, ticker="A")

        rankings = result["rankings"]

        # A has lowest PE (10.0) — rank 1 for lower-is-better
        assert rankings["pe_ratio"]["rank"] == 1
        assert rankings["pe_ratio"]["direction"] == "lower_first"

        # A has highest gross margin (0.80) — rank 1 for higher-is-better
        assert rankings["gross_margin"]["rank"] == 1
        assert rankings["gross_margin"]["direction"] == "higher_first"

    def test_no_rankings_without_target(self):
        from src.tools.analysis_tools import get_peer_comparison

        mock_dal = MagicMock()
        with patch("src.tools.analysis_tools.get_detailed_financials") as mock_gdf:
            mock_gdf.side_effect = lambda dal, t: _mock_financials(t)
            result = get_peer_comparison(
                mock_dal, tickers=["A", "B"]
            )

        # No target → no rankings
        assert result["rankings"] is None


# ============================================================
# Explicit inputs
# ============================================================

class TestExplicitInputs:
    """Test explicit ticker list and sector inputs."""

    def test_explicit_tickers(self):
        from src.tools.analysis_tools import get_peer_comparison

        mock_dal = MagicMock()
        with patch("src.tools.analysis_tools.get_detailed_financials") as mock_gdf:
            mock_gdf.side_effect = lambda dal, t: _mock_financials(t)
            result = get_peer_comparison(
                mock_dal, ticker="X", tickers=["X", "Y", "Z"]
            )

        assert result["sector"] == "custom"
        assert result["target_ticker"] == "X"
        assert result["peer_count"] == 3

    def test_sector_only(self):
        from src.tools.analysis_tools import get_peer_comparison

        mock_dal = MagicMock()
        mock_dal.get_sector_tickers.return_value = ["NVDA", "AMD"]

        with patch("src.tools.analysis_tools.get_detailed_financials") as mock_gdf:
            mock_gdf.side_effect = lambda dal, t: _mock_financials(t)
            result = get_peer_comparison(mock_dal, sector="AI_CHIPS")

        assert result["sector"] == "AI_CHIPS"
        assert result["target_ticker"] is None
        assert result["rankings"] is None
        assert result["peer_count"] == 2


# ============================================================
# Error handling
# ============================================================

class TestErrorHandling:
    """Test graceful error handling."""

    def test_partial_failures(self):
        from src.tools.analysis_tools import get_peer_comparison

        mock_dal = MagicMock()
        mock_dal.get_sector_tickers.return_value = ["A", "B", "FAIL"]

        def side_effect(dal, t):
            if t == "FAIL":
                raise RuntimeError("SEC EDGAR timeout")
            return _mock_financials(t)

        with patch("src.tools.analysis_tools.get_detailed_financials") as mock_gdf:
            mock_gdf.side_effect = side_effect
            result = get_peer_comparison(mock_dal, sector="TEST")

        assert result["peer_count"] == 2
        assert "FAIL" in result["data_quality"]["peers_failed"]

    def test_all_failures(self):
        from src.tools.analysis_tools import get_peer_comparison

        mock_dal = MagicMock()
        mock_dal.get_sector_tickers.return_value = ["A", "B"]

        with patch("src.tools.analysis_tools.get_detailed_financials") as mock_gdf:
            mock_gdf.side_effect = RuntimeError("Network error")
            result = get_peer_comparison(mock_dal, sector="TEST")

        assert "error" in result


# ============================================================
# Data quality
# ============================================================

class TestDataQuality:
    """Test data quality reporting."""

    def test_data_quality_fields(self):
        from src.tools.analysis_tools import get_peer_comparison

        mock_dal = MagicMock()
        with patch("src.tools.analysis_tools.get_detailed_financials") as mock_gdf:
            mock_gdf.side_effect = lambda dal, t: _mock_financials(t)
            result = get_peer_comparison(mock_dal, tickers=["A", "B"])

        dq = result["data_quality"]
        assert dq["peers_with_data"] == 2
        assert dq["peers_failed"] == []
        assert dq["data_source"] == "sec_edgar"

    def test_unavailable_valuation_prices_are_counted_named_and_excluded(self):
        from src.tools.analysis_tools import get_peer_comparison

        mock_dal = MagicMock()
        financials = {
            "ALPHA": _mock_financials("ALPHA", pe_ratio=20.0),
            "BETA": _mock_financials("BETA", pe_ratio=40.0),
            "GAMMA": _mock_financials(
                "GAMMA",
                valuation_price_basis={
                    "available": False,
                    "source": None,
                    "interval": None,
                    "required_market_date": "2026-07-31",
                    "market_date": None,
                    "timestamp": None,
                    "price": None,
                    "empty_reason": "no_qualified_price",
                },
                market_cap=None,
                enterprise_value=None,
                pe_ratio=None,
                pb_ratio=None,
                ps_ratio=None,
                ev_to_ebitda=None,
                ev_to_revenue=None,
                fcf_yield=None,
                peg_ratio=None,
                gross_margin=0.55,
            ),
        }

        with patch("src.tools.analysis_tools.get_detailed_financials") as mock_gdf:
            mock_gdf.side_effect = lambda _dal, peer: financials[peer]
            result = get_peer_comparison(
                mock_dal,
                ticker="ALPHA",
                tickers=["GAMMA", "BETA", "ALPHA"],
            )

        assert result["peer_count"] == 3
        assert result["comparison_matrix"]["GAMMA"]["gross_margin"] == 0.55
        assert result["comparison_matrix"]["GAMMA"]["pe_ratio"] is None
        assert result["sector_stats"]["pe_ratio"] == {
            "median": 30.0,
            "mean": 30.0,
            "count": 2,
        }
        assert result["rankings"]["pe_ratio"]["rank"] == 1
        assert result["rankings"]["pe_ratio"]["of"] == 2
        assert result["data_quality"] == {
            "peers_with_data": 3,
            "peers_failed": [],
            "data_source": "sec_edgar",
            "valuation_price_unavailable_count": 1,
            "valuation_price_unavailable_tickers": ["GAMMA"],
            "valuation_price_empty_reason_counts": {
                "no_qualified_price": 1,
            },
        }


# ============================================================
# Live tests (skip without network)
# ============================================================

class TestLivePeerComparison:
    @pytest.mark.skipif(
        True,  # Set to False to run manually
        reason="Live SEC EDGAR test — run manually"
    )
    def test_nvda_peer_comparison(self):
        from src.tools.data_access import DataAccessLayer
        from src.tools.analysis_tools import get_peer_comparison

        dal = DataAccessLayer()
        result = get_peer_comparison(dal, ticker="NVDA")
        assert result["sector"] == "AI_CHIPS"
        assert result["peer_count"] >= 3
        assert "NVDA" in result["comparison_matrix"]
        assert result["rankings"] is not None
