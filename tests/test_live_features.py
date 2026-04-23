"""Tests for Phase B1a live feature frame builder.

Uses fake adapters supplying synthetic OHLCV + sentiment so tests do not
depend on IBKR, DB, or parquet files. The concrete IBKRDailyPriceAdapter
and ParquetSentimentAdapter are NOT covered here — they require external
resources and should be exercised as manual smoke via a CLI.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
import pytest

from src.rl.live_features import build_live_features
from training.config import INDICATORS


def _synthetic_ohlcv(tickers, start_date, end_date, seed=7):
    """Produce a deterministic OHLCV DataFrame with smooth price drift.

    Deterministic so tests are stable; smooth enough that stockstats
    indicators (RSI/MACD/etc.) do not blow up to NaN with modest lookback.
    """
    rng = np.random.default_rng(seed)
    d0 = datetime.strptime(start_date, "%Y-%m-%d").date()
    d1 = datetime.strptime(end_date, "%Y-%m-%d").date()
    dates = [(d0 + timedelta(days=i)).isoformat()
             for i in range((d1 - d0).days + 1)]
    dates = [d for d in dates
             if datetime.strptime(d, "%Y-%m-%d").weekday() < 5]  # weekdays only

    rows = []
    for tic in tickers:
        base = 100.0 + rng.uniform(-10, 30)
        prices = base * np.cumprod(1 + rng.normal(0.0005, 0.012, len(dates)))
        for i, dt in enumerate(dates):
            c = float(prices[i])
            rows.append({
                "date": dt,
                "tic": tic,
                "open": c * (1 + rng.normal(0, 0.002)),
                "high": c * (1 + abs(rng.normal(0, 0.005))),
                "low":  c * (1 - abs(rng.normal(0, 0.005))),
                "close": c,
                "volume": int(rng.integers(1_000_000, 10_000_000)),
            })
    return pd.DataFrame(rows)


class FakePriceAdapter:
    def __init__(self, df: pd.DataFrame):
        self._df = df
        self.last_call: tuple | None = None

    def fetch_daily_ohlcv(self, tickers, start_date, end_date):
        self.last_call = (tuple(tickers), start_date, end_date)
        df = self._df[self._df["tic"].isin(tickers)].copy()
        df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]
        return df.sort_values(["date", "tic"]).reset_index(drop=True)


class FakeSentimentAdapter:
    def __init__(self, mapping: Mapping[str, float]):
        self._mapping = dict(mapping)

    def fetch_day_sentiment(self, tickers, date):
        # Only return requested tickers we have; missing ones left absent.
        return {t: v for t, v in self._mapping.items() if t in tickers}


@pytest.fixture
def tickers():
    return ("AAPL", "MSFT", "NVDA")


@pytest.fixture
def ohlcv(tickers):
    return _synthetic_ohlcv(tickers, "2026-01-01", "2026-04-15")


@pytest.fixture
def price_adapter(ohlcv):
    return FakePriceAdapter(ohlcv)


def test_happy_path_produces_schema_compliant_frame(tickers, price_adapter):
    sentiment = FakeSentimentAdapter({"AAPL": 4, "MSFT": 2, "NVDA": 5})

    frame = build_live_features(
        target_date="2026-04-15",
        ticker_order=tickers,
        price_adapter=price_adapter,
        sentiment_adapter=sentiment,
        tech_indicator_list=INDICATORS,
        lookback_days=90,
    )

    expected_cols = ["date", "tic"] + ["close"] + list(INDICATORS) + ["llm_sentiment"]
    assert list(frame.columns) == expected_cols
    assert list(frame["tic"]) == list(tickers)
    assert (frame["date"] == "2026-04-15").all()
    assert frame.notna().all().all()


def test_ticker_order_matches_metadata_even_when_price_df_is_shuffled(tickers, ohlcv):
    # Shuffle the OHLCV rows to test that builder enforces ticker_order
    shuffled = ohlcv.sample(frac=1, random_state=1).reset_index(drop=True)
    adapter = FakePriceAdapter(shuffled)
    sentiment = FakeSentimentAdapter({"AAPL": 3, "MSFT": 3, "NVDA": 3})

    frame = build_live_features(
        target_date="2026-04-15",
        ticker_order=("NVDA", "AAPL", "MSFT"),  # different from alphabetical
        price_adapter=adapter,
        sentiment_adapter=sentiment,
        tech_indicator_list=INDICATORS,
        lookback_days=90,
    )
    assert list(frame["tic"]) == ["NVDA", "AAPL", "MSFT"]


def test_missing_sentiment_fills_default(tickers, price_adapter):
    # NVDA missing from sentiment map
    sentiment = FakeSentimentAdapter({"AAPL": 4, "MSFT": 2})

    frame = build_live_features(
        target_date="2026-04-15",
        ticker_order=tickers,
        price_adapter=price_adapter,
        sentiment_adapter=sentiment,
        tech_indicator_list=INDICATORS,
        lookback_days=90,
        sentiment_missing_fill=0,
    )
    by_tic = frame.set_index("tic")["llm_sentiment"]
    assert by_tic["AAPL"] == 4
    assert by_tic["MSFT"] == 2
    assert by_tic["NVDA"] == 0  # filled, not NaN


def test_missing_ticker_in_prices_raises(tickers, ohlcv):
    # Drop NVDA entirely from OHLCV
    partial = ohlcv[ohlcv["tic"] != "NVDA"].reset_index(drop=True)
    adapter = FakePriceAdapter(partial)
    sentiment = FakeSentimentAdapter({"AAPL": 4, "MSFT": 2, "NVDA": 5})

    with pytest.raises(ValueError, match="Missing close"):
        build_live_features(
            target_date="2026-04-15",
            ticker_order=tickers,
            price_adapter=adapter,
            sentiment_adapter=sentiment,
            tech_indicator_list=INDICATORS,
            lookback_days=90,
        )


def test_target_date_has_no_rows_raises(tickers, price_adapter):
    # target_date falls on a weekend (in the synthetic data we skipped weekends)
    # 2026-04-18 is a Saturday; ohlcv has no rows for it.
    sentiment = FakeSentimentAdapter({"AAPL": 3, "MSFT": 3, "NVDA": 3})
    with pytest.raises(ValueError, match="No rows for target_date"):
        build_live_features(
            target_date="2026-04-18",
            ticker_order=tickers,
            price_adapter=price_adapter,
            sentiment_adapter=sentiment,
            tech_indicator_list=INDICATORS,
            lookback_days=30,
        )


def test_adapter_called_with_ticker_order_and_resolved_start_date(tickers, price_adapter):
    sentiment = FakeSentimentAdapter({"AAPL": 3, "MSFT": 3, "NVDA": 3})
    build_live_features(
        target_date="2026-04-15",
        ticker_order=tickers,
        price_adapter=price_adapter,
        sentiment_adapter=sentiment,
        tech_indicator_list=INDICATORS,
        lookback_days=90,
    )
    called_tickers, called_start, called_end = price_adapter.last_call
    assert called_tickers == tickers
    assert called_end == "2026-04-15"
    # 90 days before 2026-04-15 is 2026-01-15
    assert called_start == "2026-01-15"


def test_empty_ticker_order_raises(price_adapter):
    sentiment = FakeSentimentAdapter({})
    with pytest.raises(ValueError, match="ticker_order must be non-empty"):
        build_live_features(
            target_date="2026-04-15",
            ticker_order=(),
            price_adapter=price_adapter,
            sentiment_adapter=sentiment,
            tech_indicator_list=INDICATORS,
        )


def test_price_adapter_missing_columns_raises(tickers):
    class BadAdapter:
        def fetch_daily_ohlcv(self, tickers, start_date, end_date):
            return pd.DataFrame({"date": ["2026-04-15"], "tic": ["AAPL"]})

    sentiment = FakeSentimentAdapter({"AAPL": 3})
    with pytest.raises(ValueError, match="missing columns"):
        build_live_features(
            target_date="2026-04-15",
            ticker_order=("AAPL",),
            price_adapter=BadAdapter(),
            sentiment_adapter=sentiment,
            tech_indicator_list=INDICATORS,
        )