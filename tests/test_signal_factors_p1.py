"""Tests for P1.1 multi-factor signal exposure.

Coverage:
  - get_signal_factors rich shape (factors list + data_quality + composite)
  - factor-rank universe dedup, single global anchor, missing-data routing,
    top-N truncation, factor enum + caveats
  - factor=volume_spike maps to VOLUME_SPIKE factor_type, NOT the
    synthesizer's input bucket name volume_anomaly
  - News df is preloaded ONCE per factor-rank call (no per-ticker re-read)
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi import HTTPException

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.api.routes.signals import (
    _FACTOR_NAME_TO_TYPE,
    _missing_reason,
    _rank_value_for,
    _resolve_universe,
    factor_rank,
)
from src.tools.data_access import DataAccessLayer
from src.tools.signal_tools import FACTOR_TYPES, get_signal_factors


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def dal():
    return DataAccessLayer(base_path=project_root)


def _factors_result(
    *,
    ticker: str = "NVDA",
    sector: str = "Technology",
    composite_score: float = 0.42,
    action: str = "BUY",
    confidence: float = 0.6,
    risk_level: int = 3,
    factor_rows=None,
    news_count: int = 50,
    scored_news_count: int = 45,
    missing_factors=None,
    errors=None,
):
    return {
        "ticker": ticker,
        "as_of_date": "2026-04-25",
        "sector": sector,
        "data_quality": {
            "news_count": news_count,
            "scored_news_count": scored_news_count,
            "missing_factors": list(missing_factors or []),
            "errors": list(errors or []),
        },
        "factors": list(factor_rows or [
            {"factor_type": "SECTOR_MOMENTUM", "impact": 0.4, "weight": 0.25,
             "contribution": 0.1, "details": {}},
            {"factor_type": "VOLUME_SPIKE", "impact": 0.6, "weight": 0.15,
             "contribution": 0.09, "details": {}},
        ]),
        "composite": {
            "score": composite_score,
            "action": action,
            "confidence": confidence,
            "risk_level": risk_level,
            "reasoning": "test",
        },
    }


# ---------------------------------------------------------------------------
# get_signal_factors — real synthesizer shape
# ---------------------------------------------------------------------------


class TestGetSignalFactorsShape:
    def test_returns_rich_shape(self, dal):
        result = get_signal_factors(dal, ticker="NVDA", days=9999)
        for key in ("ticker", "as_of_date", "sector", "data_quality",
                    "factors", "composite"):
            assert key in result, f"missing key: {key}"

    def test_data_quality_block_carries_counts(self, dal):
        result = get_signal_factors(dal, ticker="NVDA", days=9999)
        dq = result["data_quality"]
        for key in ("news_count", "scored_news_count", "missing_factors", "errors"):
            assert key in dq
        assert isinstance(dq["news_count"], int)
        assert isinstance(dq["scored_news_count"], int)
        # scored_news_count cannot exceed news_count
        assert dq["scored_news_count"] <= dq["news_count"]

    def test_factor_rows_carry_value_weight_contribution(self, dal):
        result = get_signal_factors(dal, ticker="NVDA", days=9999)
        for f in result["factors"]:
            assert {"factor_type", "impact", "weight", "contribution", "details"} <= f.keys()
            assert f["factor_type"] in FACTOR_TYPES
            # SignalSynthesizer's `impact` is already the score_delta it
            # added to composite_score (i.e. already weighted), so
            # contribution == impact. Multiplying by weight again would
            # double-count and break additivity below.
            assert abs(f["contribution"] - f["impact"]) < 1e-3

    def test_contributions_sum_to_composite_score(self, dal):
        """Per-factor contributions must be additive — sum ≈ composite_score.

        This is the explainability contract: a caller who sees
        ``contribution`` should be able to add them up and recover
        ``composite.score``. If the math drifts, the breakdown stops
        being trustworthy.
        """
        result = get_signal_factors(dal, ticker="NVDA", days=9999)
        if not result["factors"]:
            pytest.skip("synthesizer emitted no factors for this fixture")
        total = sum(f["contribution"] for f in result["factors"])
        assert abs(total - result["composite"]["score"]) < 1e-2

    def test_composite_uses_recommendation_vocabulary(self, dal):
        result = get_signal_factors(dal, ticker="NVDA", days=9999)
        comp = result["composite"]
        for key in ("score", "action", "confidence", "risk_level", "reasoning"):
            assert key in comp
        assert comp["action"] in ("STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL")
        assert 0 <= comp["confidence"] <= 1
        assert 1 <= comp["risk_level"] <= 5

    def test_no_news_case_marks_factors_missing(self, dal):
        """Ticker with no historical news → missing_factors populated, no false neutral."""
        result = get_signal_factors(dal, ticker="ZZZZ_NONEXIST", days=30)
        dq = result["data_quality"]
        assert dq["news_count"] == 0
        # All four input-factor-types should be flagged missing.
        assert "SECTOR_MOMENTUM" in dq["missing_factors"] or \
               "SENTIMENT_ANOMALY" in dq["missing_factors"] or \
               "VOLUME_SPIKE" in dq["missing_factors"] or \
               "EVENT_CHAIN" in dq["missing_factors"]

    def test_fixed_as_of_date_round_trips(self, dal):
        """Caller-supplied anchor must come back unchanged in the result."""
        result = get_signal_factors(
            dal, ticker="NVDA", days=9999, as_of_date="2026-01-15"
        )
        assert result["as_of_date"] == "2026-01-15"


# ---------------------------------------------------------------------------
# Pure logic — factor name mapping
# ---------------------------------------------------------------------------


class TestFactorNameMapping:
    def test_volume_spike_maps_to_VOLUME_SPIKE_factor_type(self):
        """Critical: don't confuse the synthesizer's input bucket name
        ``volume_anomaly`` with the OUTPUT factor_type ``VOLUME_SPIKE``."""
        assert _FACTOR_NAME_TO_TYPE["volume_spike"] == "VOLUME_SPIKE"
        assert "volume_anomaly" not in _FACTOR_NAME_TO_TYPE

    def test_event_chain_uses_singular_factor_type(self):
        """Synthesizer emits ``EVENT_CHAIN`` (singular), not ``EVENT_CHAINS``."""
        assert _FACTOR_NAME_TO_TYPE["event_chain"] == "EVENT_CHAIN"

    def test_composite_has_no_factor_type(self):
        assert _FACTOR_NAME_TO_TYPE["composite"] is None

    def test_rank_value_for_composite(self):
        result = _factors_result(composite_score=0.5)
        assert _rank_value_for("composite", result) == 0.5

    def test_rank_value_for_volume_spike_pulls_VOLUME_SPIKE_contribution(self):
        result = _factors_result(factor_rows=[
            {"factor_type": "VOLUME_SPIKE", "impact": 0.8, "weight": 0.15,
             "contribution": 0.12, "details": {}},
        ])
        assert _rank_value_for("volume_spike", result) == 0.12

    def test_rank_value_returns_none_when_factor_absent(self):
        result = _factors_result(factor_rows=[
            {"factor_type": "SECTOR_MOMENTUM", "impact": 0.4, "weight": 0.25,
             "contribution": 0.1, "details": {}},
        ])
        assert _rank_value_for("volume_spike", result) is None


# ---------------------------------------------------------------------------
# Missing-reason classifier
# ---------------------------------------------------------------------------


class TestMissingReason:
    def test_no_news_returns_no_news_in_window(self):
        result = _factors_result(news_count=0, scored_news_count=0)
        assert _missing_reason(result, "composite") == "no_news_in_window"

    def test_unscored_news_only_returns_no_scored_news(self):
        result = _factors_result(news_count=10, scored_news_count=0)
        assert _missing_reason(result, "composite") == "no_scored_news"

    def test_specific_factor_missing(self):
        result = _factors_result(missing_factors=["VOLUME_SPIKE"])
        assert _missing_reason(result, "volume_spike") == "factor_not_computed:volume_spike"

    def test_healthy_returns_none(self):
        result = _factors_result()
        assert _missing_reason(result, "composite") is None


# ---------------------------------------------------------------------------
# Universe resolution & dedup
# ---------------------------------------------------------------------------


class TestResolveUniverse:
    def test_watchlist_is_uppercased_and_deduped(self):
        dal = MagicMock()
        dal.get_watchlist.return_value = SimpleNamespace(
            tickers=["nvda", "AMD", "nvda", "  TSLA  "]
        )
        out = _resolve_universe(dal, "watchlist")
        assert out == ["NVDA", "AMD", "TSLA"]

    def test_alpha_picks_dedupes_repeated_picks(self):
        """Same symbol picked across cycles (e.g. EAT, MFC, STRL) → one row."""
        dal = MagicMock()
        dal.get_sa_portfolio.return_value = [
            {"symbol": "EAT", "picked_date": "2024-05-01"},
            {"symbol": "EAT", "picked_date": "2025-08-15"},  # duplicate
            {"symbol": "MFC", "picked_date": "2024-06-01"},
            {"symbol": "STRL", "picked_date": "2024-07-01"},
        ]
        out = _resolve_universe(dal, "alpha_picks")
        assert out == ["EAT", "MFC", "STRL"]

    def test_unknown_universe_raises_422(self):
        with pytest.raises(HTTPException) as exc:
            _resolve_universe(MagicMock(), "russell_2000")
        assert exc.value.status_code == 422


# ---------------------------------------------------------------------------
# /signals/factor-rank — orchestration
# ---------------------------------------------------------------------------


class TestFactorRankRoute:
    @staticmethod
    def _setup_dal_with_universe(tickers):
        dal = MagicMock()
        dal.get_watchlist.return_value = SimpleNamespace(tickers=list(tickers))
        return dal

    @staticmethod
    def _fake_news_df():
        return pd.DataFrame({
            "date": pd.to_datetime(["2026-04-20", "2026-04-23", "2026-04-25"]),
            "ticker": ["NVDA", "AMD", "TSLA"],
            "title": ["beat", "guidance", "FDA"],
            "llm_sentiment": [4.2, 3.8, 2.5],
            "llm_risk": [2.0, 2.5, 4.0],
            "source": ["x", "x", "x"],
            "event_type": ["earnings", "guidance", "fda"],
        })

    def test_invalid_factor_returns_422(self):
        dal = self._setup_dal_with_universe(["NVDA"])
        with pytest.raises(HTTPException) as exc:
            factor_rank(
                universe="watchlist", factor="quality",
                top=20, days=30, as_of_date=None, dal=dal,
            )
        assert exc.value.status_code == 422

    def test_invalid_universe_returns_422(self):
        dal = self._setup_dal_with_universe(["NVDA"])
        with pytest.raises(HTTPException) as exc:
            factor_rank(
                universe="russell_2000", factor="composite",
                top=20, days=30, as_of_date=None, dal=dal,
            )
        assert exc.value.status_code == 422

    def test_news_df_preloaded_once_for_whole_universe(self, monkeypatch):
        """Critical: per-ticker calls must reuse the shared df."""
        dal = self._setup_dal_with_universe(["NVDA", "AMD", "TSLA"])
        prepare_calls = {"count": 0}
        gsf_calls = []

        def fake_prepare(_dal, ticker=None, days=30, scored_only=True):
            prepare_calls["count"] += 1
            return self._fake_news_df()

        def fake_gsf(_dal, ticker, **kwargs):
            gsf_calls.append({"ticker": ticker, "news_df_id": id(kwargs.get("news_df"))})
            return _factors_result(ticker=ticker, composite_score=0.1)

        monkeypatch.setattr(
            "src.api.routes.signals._prepare_news_df_for_signals", fake_prepare
        )
        monkeypatch.setattr("src.api.routes.signals.get_signal_factors", fake_gsf)

        factor_rank(
            universe="watchlist", factor="composite",
            top=20, days=30, as_of_date=None, dal=dal,
        )

        assert prepare_calls["count"] == 1, "news_df was re-read per ticker"
        # All 3 per-ticker calls receive the SAME news_df object.
        assert len({c["news_df_id"] for c in gsf_calls}) == 1
        assert {c["ticker"] for c in gsf_calls} == {"NVDA", "AMD", "TSLA"}

    def test_single_global_anchor_used_across_all_tickers(self, monkeypatch):
        dal = self._setup_dal_with_universe(["NVDA", "AMD"])
        anchors_seen = []

        monkeypatch.setattr(
            "src.api.routes.signals._prepare_news_df_for_signals",
            lambda *a, **k: self._fake_news_df(),
        )

        def fake_gsf(_dal, ticker, *, as_of_date, **_):
            anchors_seen.append(as_of_date)
            return _factors_result(ticker=ticker)

        monkeypatch.setattr("src.api.routes.signals.get_signal_factors", fake_gsf)

        result = factor_rank(
            universe="watchlist", factor="composite",
            top=20, days=30, as_of_date=None, dal=dal,
        )
        assert len(set(anchors_seen)) == 1, "tickers used different anchors"
        assert anchors_seen[0] == result["as_of_date"]
        # Default anchor = max(date) of fake_news_df = 2026-04-25.
        assert result["as_of_date"].startswith("2026-04-25")

    def test_explicit_as_of_date_round_trips(self, monkeypatch):
        dal = self._setup_dal_with_universe(["NVDA"])
        monkeypatch.setattr(
            "src.api.routes.signals._prepare_news_df_for_signals",
            lambda *a, **k: self._fake_news_df(),
        )
        monkeypatch.setattr(
            "src.api.routes.signals.get_signal_factors",
            lambda *a, **k: _factors_result(),
        )
        result = factor_rank(
            universe="watchlist", factor="composite",
            top=20, days=30, as_of_date="2026-01-15", dal=dal,
        )
        assert result["as_of_date"] == "2026-01-15"

    def test_missing_data_tickers_carry_reason(self, monkeypatch):
        dal = self._setup_dal_with_universe(["NVDA", "ZZZZ"])
        monkeypatch.setattr(
            "src.api.routes.signals._prepare_news_df_for_signals",
            lambda *a, **k: self._fake_news_df(),
        )

        def fake_gsf(_dal, ticker, **kwargs):
            if ticker == "ZZZZ":
                return _factors_result(
                    ticker="ZZZZ", news_count=0, scored_news_count=0,
                )
            return _factors_result(ticker=ticker, composite_score=0.4)

        monkeypatch.setattr("src.api.routes.signals.get_signal_factors", fake_gsf)
        result = factor_rank(
            universe="watchlist", factor="composite",
            top=20, days=30, as_of_date=None, dal=dal,
        )
        assert result["ticker_count_total"] == 2
        assert result["ticker_count_ranked"] == 1
        assert result["ticker_count_missing_data"] == 1
        assert {m["ticker"] for m in result["missing_data_tickers"]} == {"ZZZZ"}
        assert result["missing_data_tickers"][0]["reason"] == "no_news_in_window"
        # No-data ticker NEVER appears in the ranked list.
        assert "ZZZZ" not in {r["ticker"] for r in result["ranked"]}

    def test_top_n_truncates_and_assigns_ranks(self, monkeypatch):
        dal = self._setup_dal_with_universe(["A", "B", "C", "D", "E"])
        monkeypatch.setattr(
            "src.api.routes.signals._prepare_news_df_for_signals",
            lambda *a, **k: self._fake_news_df(),
        )

        scores = {"A": 0.1, "B": 0.5, "C": 0.3, "D": 0.4, "E": 0.2}

        def fake_gsf(_dal, ticker, **kwargs):
            return _factors_result(ticker=ticker, composite_score=scores[ticker])

        monkeypatch.setattr("src.api.routes.signals.get_signal_factors", fake_gsf)
        result = factor_rank(
            universe="watchlist", factor="composite",
            top=3, days=30, as_of_date=None, dal=dal,
        )
        # Ranked descending by score: B(.5), D(.4), C(.3), E(.2), A(.1)
        assert [r["ticker"] for r in result["ranked"]] == ["B", "D", "C"]
        assert [r["rank"] for r in result["ranked"]] == [1, 2, 3]
        # Even with top=3, ticker_count_ranked reports the full ranked count.
        assert result["ticker_count_ranked"] == 5

    def test_factor_volume_spike_routes_to_VOLUME_SPIKE_contribution(self, monkeypatch):
        """Ensure rank=volume_spike uses VOLUME_SPIKE factor_type, not the
        synthesizer's input bucket volume_anomaly."""
        dal = self._setup_dal_with_universe(["A", "B"])
        monkeypatch.setattr(
            "src.api.routes.signals._prepare_news_df_for_signals",
            lambda *a, **k: self._fake_news_df(),
        )
        rows_per_ticker = {
            "A": [{"factor_type": "VOLUME_SPIKE", "impact": 0.8, "weight": 0.15,
                   "contribution": 0.12, "details": {}}],
            "B": [{"factor_type": "VOLUME_SPIKE", "impact": 0.3, "weight": 0.15,
                   "contribution": 0.045, "details": {}}],
        }

        def fake_gsf(_dal, ticker, **kwargs):
            return _factors_result(ticker=ticker, factor_rows=rows_per_ticker[ticker])

        monkeypatch.setattr("src.api.routes.signals.get_signal_factors", fake_gsf)
        result = factor_rank(
            universe="watchlist", factor="volume_spike",
            top=10, days=30, as_of_date=None, dal=dal,
        )
        assert [r["ticker"] for r in result["ranked"]] == ["A", "B"]
        assert result["ranked"][0]["score"] == 0.12

    def test_sector_momentum_response_carries_sector_caveat(self, monkeypatch):
        dal = self._setup_dal_with_universe(["NVDA"])
        monkeypatch.setattr(
            "src.api.routes.signals._prepare_news_df_for_signals",
            lambda *a, **k: self._fake_news_df(),
        )
        monkeypatch.setattr(
            "src.api.routes.signals.get_signal_factors",
            lambda *a, **k: _factors_result(factor_rows=[
                {"factor_type": "SECTOR_MOMENTUM", "impact": 0.4, "weight": 0.25,
                 "contribution": 0.1, "details": {}},
            ]),
        )
        result = factor_rank(
            universe="watchlist", factor="sector_momentum",
            top=10, days=30, as_of_date=None, dal=dal,
        )
        notes = " ".join(result["notes"])
        assert "sector-shared" in notes.lower() or "shared across" in notes.lower()

    def test_empty_universe_returns_empty_result(self):
        dal = MagicMock()
        dal.get_watchlist.return_value = SimpleNamespace(tickers=[])
        result = factor_rank(
            universe="watchlist", factor="composite",
            top=20, days=30, as_of_date=None, dal=dal,
        )
        assert result["ticker_count_total"] == 0
        assert result["ranked"] == []

    def test_alpha_picks_universe_dedup_inside_route(self, monkeypatch):
        dal = MagicMock()
        dal.get_sa_portfolio.return_value = [
            {"symbol": "EAT", "picked_date": "2024-05-01"},
            {"symbol": "EAT", "picked_date": "2025-08-15"},
            {"symbol": "MFC", "picked_date": "2024-06-01"},
        ]
        monkeypatch.setattr(
            "src.api.routes.signals._prepare_news_df_for_signals",
            lambda *a, **k: self._fake_news_df(),
        )
        seen = []

        def fake_gsf(_dal, ticker, **kwargs):
            seen.append(ticker)
            return _factors_result(ticker=ticker)

        monkeypatch.setattr("src.api.routes.signals.get_signal_factors", fake_gsf)
        result = factor_rank(
            universe="alpha_picks", factor="composite",
            top=20, days=30, as_of_date=None, dal=dal,
        )
        assert seen == ["EAT", "MFC"]
        assert result["ticker_count_total"] == 2


# ---------------------------------------------------------------------------
# /signals/factor-rank routing — real HTTP via TestClient
# ---------------------------------------------------------------------------


class TestFactorRankHTTPRouting:
    """Direct-call tests bypass Starlette routing. This class hits the
    actual app so a misordered route declaration (static /factor-rank
    after dynamic /{ticker}) is caught — Starlette would otherwise
    capture the request as ticker=\"factor-rank\" and dispatch to
    signal_for_ticker.
    """

    @staticmethod
    def _fake_news_df():
        return pd.DataFrame({
            "date": pd.to_datetime(["2026-04-23", "2026-04-25"]),
            "ticker": ["NVDA", "AMD"],
            "title": ["beat", "guidance"],
            "llm_sentiment": [4.2, 3.8],
            "llm_risk": [2.0, 2.5],
            "source": ["x", "x"],
            "event_type": ["earnings", "guidance"],
        })

    def test_factor_rank_route_not_shadowed_by_ticker_route(self, monkeypatch):
        from fastapi.testclient import TestClient
        from src.api.app import create_app
        from src.api.dependencies import get_dal

        dal = MagicMock()
        dal.get_watchlist.return_value = SimpleNamespace(tickers=["NVDA", "AMD"])

        monkeypatch.setattr(
            "src.api.routes.signals._prepare_news_df_for_signals",
            lambda *a, **k: self._fake_news_df(),
        )
        monkeypatch.setattr(
            "src.api.routes.signals.get_signal_factors",
            lambda *a, **k: _factors_result(ticker=kwa(a, k, "ticker")),
        )

        app = create_app()
        app.dependency_overrides[get_dal] = lambda: dal
        try:
            with TestClient(app) as client:
                r = client.get(
                    "/signals/factor-rank?universe=watchlist&factor=composite&top=5"
                )
            assert r.status_code == 200, r.text
            body = r.json()
            # Shape produced by factor_rank, NOT TradingSignal:
            assert "ranked" in body
            assert "missing_data_tickers" in body
            assert "ticker_count_total" in body
            assert body["universe"] == "watchlist"
            assert body["factor"] == "composite"
            # TradingSignal-only keys must not appear at top level.
            assert "composite_score" not in body
            assert "action" not in body
        finally:
            app.dependency_overrides.clear()

    def test_factor_rank_invalid_factor_returns_422_via_http(self, monkeypatch):
        from fastapi.testclient import TestClient
        from src.api.app import create_app
        from src.api.dependencies import get_dal

        dal = MagicMock()
        dal.get_watchlist.return_value = SimpleNamespace(tickers=["NVDA"])

        app = create_app()
        app.dependency_overrides[get_dal] = lambda: dal
        try:
            with TestClient(app) as client:
                r = client.get("/signals/factor-rank?factor=quality")
            assert r.status_code == 422
        finally:
            app.dependency_overrides.clear()


def kwa(args, kwargs, name):
    """Pull a positional-or-keyword arg from a lambda's *args/**kwargs."""
    if name in kwargs:
        return kwargs[name]
    # signal_tools.get_signal_factors signature: (dal, ticker, ...)
    if name == "ticker" and len(args) >= 2:
        return args[1]
    return None