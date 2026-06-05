"""Tests for the deterministic, objective EvidencePacket gatherer.

The load-bearing invariant: ArkScope LLM scores never enter the packet. These
tests prove sentiment_score/risk_score are stripped from news, the IV `signal`
judgment is dropped, the clean technical block is pure arithmetic, and one failing
source degrades into coverage rather than zeroing the packet.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from src.evidence_packet import EvidencePacket, compute_technical_evidence, gather_evidence
from src.tools.schemas import NewsArticle, NewsQueryResult, PriceBar, PriceQueryResult


def _bars(n: int = 25) -> list[PriceBar]:
    out = []
    for i in range(n):
        close = 100.0 + i
        vol = 2500 if i == n - 1 else 1000
        out.append(
            PriceBar(
                datetime=f"2026-05-{(i % 28) + 1:02d}T00:00:00+0000",
                open=close - 0.5,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                volume=vol,
            )
        )
    return out


class _FakeDAL:
    """Minimal DAL: daily bars + news rows that DO carry scores (to prove stripping)."""

    def __init__(self, bars, articles):
        self._bars = bars
        self._articles = articles

    def get_prices(self, ticker, interval, days):
        if interval == "1d":
            return PriceQueryResult(
                ticker=ticker, interval="1d", count=len(self._bars),
                bars=self._bars, date_range="2026-05-01 to 2026-05-25",
            )
        return PriceQueryResult(ticker=ticker, interval="15min", count=0, bars=[], date_range=None)

    def get_news(self, ticker, days, scored_only):
        return NewsQueryResult(
            ticker=ticker, count=len(self._articles), articles=self._articles, query_days=days,
        )


def _scored_articles() -> list[NewsArticle]:
    return [
        NewsArticle(
            date="2026-06-04", ticker="AAPL", title="Headline one", source="polygon",
            url="http://x/1", publisher="Pub", sentiment_score=4.5, risk_score=2.0,
            description="excerpt one",
        ),
        NewsArticle(
            date="2026-06-03", ticker="AAPL", title="Headline two", source="ibkr",
            url="http://x/2", publisher=None, sentiment_score=1.1, risk_score=4.9,
            description="excerpt two",
        ),
    ]


_FUNDAMENTALS = SimpleNamespace(
    roe=0.31, roa=0.18, debt_to_equity=1.4, current_ratio=1.1, revenue_growth=0.08,
    earnings_growth=0.05, gross_margin=0.46, operating_margin=0.30, net_margin=0.25,
    free_cash_flow=9.9e10, cash_and_equivalents=3e10, total_debt=1e11,
    snapshot_date="2026-03-31", data_source="sec_edgar",
)
_CONSENSUS = {
    "ticker": "AAPL",
    "recommendations": {"current": {"strongBuy": 8, "buy": 12, "hold": 5, "sell": 0, "strongSell": 0}, "trend": []},
    "earnings": {
        "history": [{"period": "2026-03", "actual": 1.5, "estimate": 1.4, "surprisePercent": 7.1}],
        "upcoming": {"date": "2026-07-25", "epsEstimate": 1.6},
    },
    "price_target": None,
}
_IV = SimpleNamespace(
    current_iv=0.45, hv_30d=0.40, vrp=0.05, iv_rank=60.0, iv_percentile=55.0,
    spot_price=124.0, history_days=120, signal="NEUTRAL",
)


def _gather(dal):
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("src.tools.analysis_tools.get_fundamentals_analysis", lambda dal, t, period="annual": _FUNDAMENTALS)
        mp.setattr("src.tools.analyst_tools.get_analyst_consensus", lambda t: _CONSENSUS)
        mp.setattr("src.tools.options_tools.get_iv_analysis", lambda dal, t: _IV)
        return gather_evidence(dal, "aapl", now_iso="2026-06-05T00:00:00Z")


# --- the score-exclusion invariant -----------------------------------------


def test_no_llm_scores_anywhere_in_packet():
    packet = _gather(_FakeDAL(_bars(), _scored_articles()))
    # The leak vector is the evidence DATA payloads. (Descriptive `note` fields
    # and the `coverage` item legitimately name the excluded columns, so we
    # assert against real evidence data only, not the human-readable docs.)
    blob = json.dumps([it.data for it in packet.items if it.source_type != "coverage"], default=str)
    assert "sentiment_score" not in blob
    assert "risk_score" not in blob
    # llm_sentiment / llm_risk pipeline columns must never appear either
    assert "llm_sentiment" not in blob
    assert "llm_risk" not in blob


def test_news_rows_are_whitelisted_fields_only():
    packet = _gather(_FakeDAL(_bars(), _scored_articles()))
    news = next(i for i in packet.items if i.source == "news_rows")
    assert news.source_type == "observed_news"
    row = news.data["rows"][0]
    assert set(row.keys()) == {"date", "ticker", "title", "source", "url", "publisher", "excerpt"}


def test_iv_signal_judgment_is_dropped():
    packet = _gather(_FakeDAL(_bars(), _scored_articles()))
    iv = next(i for i in packet.items if i.source == "iv_environment")
    assert iv.source_type == "observed_market"
    assert "signal" not in iv.data  # the get_iv_analysis judgment label is excluded
    assert iv.data["iv_rank"] == 60.0


# --- structure --------------------------------------------------------------


def test_packet_has_expected_sources_and_tags():
    packet = _gather(_FakeDAL(_bars(), _scored_articles()))
    assert packet.ticker == "AAPL"
    by_source = {i.source: i for i in packet.items}
    assert by_source["price_summary"].source_type == "observed_market"
    assert by_source["technical_metrics"].source_type == "deterministic_metric"
    assert by_source["fundamentals:sec_edgar"].source_type == "institutional"
    assert by_source["analyst_recommendations"].source_type == "provider_native"
    assert by_source["earnings_facts"].source_type == "provider_native"
    # technical derives from the price bars
    assert by_source["technical_metrics"].derived_from == [by_source["price_summary"].evidence_id]
    # coverage is last and documents the exclusion
    cov = packet.items[-1]
    assert cov.source_type == "coverage"
    assert "price" in cov.data["present"]
    assert "LLM scores" in packet.excluded_note


def test_one_failing_source_degrades_to_coverage():
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("src.tools.analysis_tools.get_fundamentals_analysis", lambda dal, t, period="annual": _FUNDAMENTALS)
        mp.setattr("src.tools.analyst_tools.get_analyst_consensus", lambda t: _CONSENSUS)

        def _boom(dal, t):
            raise RuntimeError("iv source down")

        mp.setattr("src.tools.options_tools.get_iv_analysis", _boom)
        packet = gather_evidence(_FakeDAL(_bars(), _scored_articles()), "AAPL", now_iso="2026-06-05T00:00:00Z")

    cov = packet.items[-1]
    assert "iv" in cov.data["missing"]
    assert "iv" in cov.data["errors"]
    # the rest of the packet still built
    assert any(i.source == "price_summary" for i in packet.items)


def test_sa_excluded_by_default():
    packet = _gather(_FakeDAL(_bars(), _scored_articles()))
    assert not any(i.source == "sa_digest" for i in packet.items)


def test_empty_analyst_degrades_to_coverage_not_evidence():
    # Finnhub returns the truthy no-data wrapper; analyst must land in coverage
    # 'missing', NOT as an empty provider_native item that fakes 'present'.
    empty_consensus = {
        "ticker": "AAPL",
        "recommendations": {"current": None, "trend": []},
        "earnings": {"history": [], "upcoming": None},
        "price_target": None,
    }
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("src.tools.analysis_tools.get_fundamentals_analysis", lambda dal, t, period="annual": _FUNDAMENTALS)
        mp.setattr("src.tools.analyst_tools.get_analyst_consensus", lambda t: empty_consensus)
        mp.setattr("src.tools.options_tools.get_iv_analysis", lambda dal, t: _IV)
        packet = gather_evidence(_FakeDAL(_bars(), _scored_articles()), "AAPL", now_iso="2026-06-05T00:00:00Z")

    assert not any(i.source == "analyst_recommendations" for i in packet.items)
    assert not any(i.source == "earnings_facts" for i in packet.items)
    cov = packet.items[-1]
    assert "analyst" in cov.data["missing"]
    assert "analyst" not in cov.data["present"]


def test_sa_digest_extracts_correct_fields_when_enabled():
    # Real get_sa_digest shape: comments under high_value_comments.{ticker,candidate}_mentions,
    # excerpt=preview, article date=published_date/excerpt=summary_excerpt.
    fake_digest = {
        "ticker": "AAPL",
        "window": {"start": "2026-05-22", "end": "2026-06-05", "days": 14},
        "recent_articles": [
            {"title": "A1", "published_date": "2026-06-01", "url": "http://a", "summary_excerpt": "ex"}
        ],
        "high_value_comments": {
            "ticker_mentions": [
                {"preview": "great quarter", "high_value_score": 7.5, "upvotes": 3,
                 "comment_date": "2026-06-02", "needs_verification": False}
            ],
            "candidate_mentions": [
                {"preview": "maybe", "high_value_score": 5.0, "upvotes": 1,
                 "comment_date": "2026-06-01", "needs_verification": True}
            ],
        },
    }
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("src.tools.analysis_tools.get_fundamentals_analysis", lambda dal, t, period="annual": _FUNDAMENTALS)
        mp.setattr("src.tools.analyst_tools.get_analyst_consensus", lambda t: _CONSENSUS)
        mp.setattr("src.tools.options_tools.get_iv_analysis", lambda dal, t: _IV)
        mp.setattr("src.tools.sa_digest_tools.get_sa_digest", lambda dal, t: fake_digest)
        packet = gather_evidence(
            _FakeDAL(_bars(), _scored_articles()), "AAPL",
            now_iso="2026-06-05T00:00:00Z", sa_enabled=True,
        )
    sa = next(i for i in packet.items if i.source == "sa_digest")
    assert sa.source_type == "sa_community"
    art = sa.data["recent_articles"][0]
    assert art["title"] == "A1" and art["date"] == "2026-06-01" and art["excerpt"] == "ex"
    comments = sa.data["high_value_comments"]
    assert len(comments) == 2  # ticker + candidate flattened (the old buggy key gave 0)
    assert comments[0]["excerpt"] == "great quarter" and comments[0]["high_value_score"] == 7.5
    blob = json.dumps(sa.data, default=str)
    assert "sentiment_score" not in blob and "risk_score" not in blob


# --- clean technical math ---------------------------------------------------


def test_technical_metrics_are_pure_numbers():
    tech = compute_technical_evidence(_bars(25))
    assert tech["bar_count"] == 25
    assert tech["windows_used"] == [1, 5, 20]
    # close series is 100..124: return_20d = (124/104 - 1)*100
    assert tech["return_20d_pct"] == pytest.approx(19.23, abs=0.05)
    assert tech["return_1d_pct"] == pytest.approx(0.81, abs=0.05)
    # last volume 2500 vs 20d avg 1075 = 2.33x
    assert tech["latest_volume_vs_20d_avg"] == pytest.approx(2.33, abs=0.02)
    assert tech["data_quality"]["enough_bars"] is True
    # NO judgment fields leak in
    for banned in ("signal", "action", "confidence", "trend", "bullish", "bearish", "score"):
        assert banned not in tech


def test_technical_short_series_flags_missing_windows():
    tech = compute_technical_evidence(_bars(6))
    assert tech["return_20d_pct"] is None
    assert "return_20d" in tech["data_quality"]["missing_windows"]
    assert tech["data_quality"]["enough_bars"] is False
