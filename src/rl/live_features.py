"""Live feature frame builder for post-training RL inference (Phase B1a).

Produces a single-day ``features_df`` matching the training CSV schema:

    columns = ["date", "tic", "close", *tech_indicator_list, llm_sentiment_col]
    rows    = one per ticker, in ``ticker_order``

The day frame feeds directly into :func:`src.rl.inference.predict_from_frame`.

Adapter boundary:
  - PriceAdapter       — returns multi-day OHLCV for enough lookback
  - SentimentAdapter   — returns {ticker: score} for the target day
  Tests substitute fakes; production CLI uses the concrete IBKR / Parquet
  adapters defined at the bottom of this file.

Validation policy (strict, matching training convention):
  - every ticker in ``ticker_order`` MUST have a close and every indicator
  - a missing close or indicator raises; we do NOT silently ffill/bfill
  - sentiment MAY be missing for a ticker; it is filled with
    ``sentiment_missing_fill`` (default 0), matching training's treatment
    of tickers with no same-day news

Indicator computation reuses ``training.preprocessor.FeatureEngineer`` so
that live inference and training call the exact same stockstats pipeline.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Mapping, Protocol, Sequence

import pandas as pd

_OHLCV_COLUMNS = ("date", "tic", "open", "high", "low", "close", "volume")


class PriceAdapter(Protocol):
    """Supplies daily OHLCV bars for a range of dates."""

    def fetch_daily_ohlcv(
        self,
        tickers: Sequence[str],
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """Return a DataFrame with columns exactly matching ``_OHLCV_COLUMNS``.

        ``date`` may be either ISO string or datetime; it will be normalized.
        Rows with missing values are acceptable — validation of the target
        date happens downstream, not inside the adapter.
        """
        ...


class SentimentAdapter(Protocol):
    """Supplies per-ticker sentiment score for a single day."""

    def fetch_day_sentiment(
        self,
        tickers: Sequence[str],
        date: str,
    ) -> Mapping[str, float]:
        """Return a mapping {ticker: score} for ``date``.

        Tickers absent from the mapping are treated as "no news"; the builder
        fills them with ``sentiment_missing_fill`` (training convention).
        """
        ...


def _compute_indicators(
    prices: pd.DataFrame, tech_indicator_list: Sequence[str]
) -> pd.DataFrame:
    """Attach indicator columns using the same FeatureEngineer as training."""
    from training.preprocessor import FeatureEngineer

    fe = FeatureEngineer(
        use_technical_indicator=True,
        tech_indicator_list=list(tech_indicator_list),
        use_vix=False,
        use_turbulence=False,
        user_defined_feature=False,
    )
    return fe.preprocess_data(prices)


def _resolve_start_date(target_date: str, lookback_days: int) -> str:
    """Compute an ISO start date ``lookback_days`` before ``target_date``."""
    d = datetime.strptime(target_date, "%Y-%m-%d").date()
    return (d - timedelta(days=lookback_days)).isoformat()


def build_live_features(
    target_date: str,
    ticker_order: Sequence[str],
    price_adapter: PriceAdapter,
    sentiment_adapter: SentimentAdapter,
    tech_indicator_list: Sequence[str],
    *,
    lookback_days: int = 90,
    sentiment_missing_fill: float = 0.0,
    llm_sentiment_col: str = "llm_sentiment",
) -> pd.DataFrame:
    """Build a single-day features_df for live inference.

    Args:
        target_date: ISO date (YYYY-MM-DD). Must fall on a trading day;
            the adapter is responsible for returning a row for this date.
        ticker_order: The exact 143-element list from the model's metadata.
            Output frame is reindexed to this order; missing tickers raise.
        price_adapter: Source of daily OHLCV with enough lookback.
        sentiment_adapter: Source of daily sentiment for each ticker.
        tech_indicator_list: Indicator names (matching training config).
        lookback_days: Days of history to fetch before ``target_date``.
            Default 90 covers the 60-SMA warmup window comfortably.
        sentiment_missing_fill: Value for tickers with no news on target_date.
        llm_sentiment_col: Output column name for sentiment.

    Returns:
        DataFrame with columns [date, tic, close, *indicators, llm_sentiment]
        and exactly ``len(ticker_order)`` rows in ``ticker_order`` sequence.

    Raises:
        ValueError: if any ticker is missing close or an indicator, or the
            target_date has no rows in the price adapter's output.
    """
    if len(ticker_order) == 0:
        raise ValueError("ticker_order must be non-empty")

    start_date = _resolve_start_date(target_date, lookback_days)
    prices = price_adapter.fetch_daily_ohlcv(
        list(ticker_order), start_date, target_date
    )

    missing_cols = [c for c in _OHLCV_COLUMNS if c not in prices.columns]
    if missing_cols:
        raise ValueError(
            f"PriceAdapter output missing columns: {missing_cols}. "
            f"Expected: {list(_OHLCV_COLUMNS)}"
        )

    prices = prices.copy()
    prices["date"] = pd.to_datetime(prices["date"]).dt.strftime("%Y-%m-%d")

    enriched = _compute_indicators(prices, tech_indicator_list)
    day = enriched[enriched["date"] == target_date].copy()
    if day.empty:
        raise ValueError(
            f"No rows for target_date {target_date} after indicator compute. "
            f"Price adapter may not have returned bars for this date "
            f"(is it a trading day?)."
        )

    sent_map = sentiment_adapter.fetch_day_sentiment(list(ticker_order), target_date)
    day[llm_sentiment_col] = (
        day["tic"].map(lambda t: sent_map.get(t, sentiment_missing_fill))
    )

    required = ["date", "tic", "close"] + list(tech_indicator_list) + [llm_sentiment_col]
    missing_cols = [c for c in required if c not in day.columns]
    if missing_cols:
        raise ValueError(
            f"Enriched day frame missing columns: {missing_cols}. "
            f"Check that tech_indicator_list matches what FeatureEngineer "
            f"produces."
        )

    day = day[required]
    day = day.set_index("tic").reindex(list(ticker_order))
    missing_tickers = day.index[day["close"].isna()].tolist()
    if missing_tickers:
        raise ValueError(
            f"Missing close for {len(missing_tickers)} ticker(s): "
            f"{missing_tickers[:10]}"
            f"{'...' if len(missing_tickers) > 10 else ''}"
        )

    for ind in tech_indicator_list:
        bad = day.index[day[ind].isna()].tolist()
        if bad:
            raise ValueError(
                f"Missing indicator '{ind}' for {len(bad)} ticker(s): "
                f"{bad[:10]}{'...' if len(bad) > 10 else ''}. "
                f"Increase lookback_days?"
            )

    day = day.reset_index()
    day["date"] = target_date
    return day[required]


# ─────────────────────────────────────────────────────────────
# Concrete adapters (not covered by tests — require external resources)
# ─────────────────────────────────────────────────────────────


class IBKRDailyPriceAdapter:
    """Live adapter — fetches daily bars from IBKR TWS/Gateway.

    Reuses :func:`training.data_prep.prepare_training_data._fetch_ibkr_daily`
    so the same ticker mapping (BRK.B → BRK B, delisted skips) and
    connection setup as training are applied.

    Construction does not connect; ``fetch_daily_ohlcv`` connects on demand.
    """

    def fetch_daily_ohlcv(
        self,
        tickers: Sequence[str],
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        from training.data_prep.prepare_training_data import _fetch_ibkr_daily

        return _fetch_ibkr_daily(list(tickers), start_date, end_date)


class ParquetSentimentAdapter:
    """Reads Polygon monthly parquets with the same coalesce priority training uses.

    Training rule (see ``prepare_training_data._load_polygon_scores``):
      1. For each article, take the first non-null score in priority order:
         ``sentiment_gpt_5_4_xhigh`` → ``sentiment_gpt_5_2_xhigh``
      2. Group by (date, ticker), take daily mean, round to int
      3. Missing daily groups → treated as no-news (filled at caller)
    """

    def __init__(
        self,
        base_dir: str = "data/news/raw/polygon",
        priority_cols: Sequence[str] = (
            "sentiment_gpt_5_4_xhigh",
            "sentiment_gpt_5_2_xhigh",
        ),
    ):
        self.base_dir = Path(base_dir)
        self.priority_cols = list(priority_cols)

    def fetch_day_sentiment(
        self, tickers: Sequence[str], date: str
    ) -> Mapping[str, float]:
        if not self.base_dir.exists():
            raise FileNotFoundError(
                f"Parquet base_dir does not exist: {self.base_dir}"
            )

        target = datetime.strptime(date, "%Y-%m-%d").date()
        year_month = target.strftime("%Y-%m")
        year_dir = self.base_dir / str(target.year)
        if not year_dir.exists():
            return {}

        candidate_path = year_dir / f"{year_month}.parquet"
        if not candidate_path.exists():
            return {}

        import pyarrow.parquet as pq

        schema_cols = pq.read_schema(str(candidate_path)).names
        available = [c for c in self.priority_cols if c in schema_cols]
        if not available:
            return {}

        read_cols = ["published_at", "ticker"] + available
        df = pd.read_parquet(str(candidate_path), columns=read_cols)

        score_series = pd.array([pd.NA] * len(df), dtype="Float64")
        for col in self.priority_cols:
            if col in df.columns:
                mask = pd.isna(score_series)
                score_series[mask] = df.loc[mask, col].values
        df["_score"] = score_series

        df["Date"] = pd.to_datetime(df["published_at"]).dt.tz_localize(None).dt.date
        day_df = df[df["Date"] == target]
        tickers_set = set(tickers)
        day_df = day_df[day_df["ticker"].isin(tickers_set)]
        if day_df.empty:
            return {}

        grouped = day_df.groupby("ticker")["_score"].mean()
        grouped = grouped.dropna().round().astype(int)
        return grouped.to_dict()