"""
Price tool functions (3 tools).

4. get_ticker_prices     — Query OHLCV price bars
5. get_price_change      — Calculate price change metrics
6. get_sector_performance — Sector-level performance summary
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from .data_access import DataAccessLayer

from .schemas import PriceQueryResult

logger = logging.getLogger(__name__)


def _resample_to_daily_result(result_15m: PriceQueryResult) -> PriceQueryResult:
    """Resample 15min bars to daily OHLCV."""
    from collections import defaultdict
    from .schemas import PriceBar

    daily_data = defaultdict(lambda: {"bars": []})

    for bar in result_15m.bars:
        # Extract date portion
        date = bar.datetime[:10]
        daily_data[date]["bars"].append(bar)

    daily_bars = []
    for date in sorted(daily_data.keys()):
        bars = daily_data[date]["bars"]
        if not bars:
            continue
        daily_bars.append(PriceBar(
            datetime=f"{date}T00:00:00+0000",
            open=bars[0].open,
            high=max(b.high for b in bars),
            low=min(b.low for b in bars),
            close=bars[-1].close,
            volume=sum(b.volume for b in bars),
        ))

    date_range = None
    if daily_bars:
        date_range = f"{daily_bars[0].datetime[:10]} to {daily_bars[-1].datetime[:10]}"

    return PriceQueryResult(
        ticker=result_15m.ticker,
        interval="1d",
        count=len(daily_bars),
        bars=daily_bars,
        date_range=date_range,
    )


def get_ticker_prices(
    dal: DataAccessLayer,
    ticker: str,
    interval: str = "15min",
    days: int = 30,
) -> PriceQueryResult:
    """
    Get OHLCV price bars for a ticker.

    Args:
        dal: DataAccessLayer instance
        ticker: Stock ticker symbol
        interval: Bar interval (15min, 1h, 1d)
        days: Lookback period in days

    Returns:
        PriceQueryResult with bars, count, and date range
    """
    return dal.get_prices(ticker=ticker, interval=interval, days=days)


def get_price_change(
    dal: DataAccessLayer,
    ticker: str,
    days: int = 7,
) -> dict:
    """
    Calculate price change metrics over a period.

    Args:
        dal: DataAccessLayer instance
        ticker: Stock ticker symbol
        days: Lookback period in days

    Returns:
        Dict with:
            ticker, days, latest_close, period_open,
            change_pct, period_high, period_low,
            high_low_range_pct, total_volume, bar_count
    """
    # Try daily first, fall back to 15min resampled
    result = dal.get_prices(ticker=ticker, interval="1d", days=days)

    if not result.bars:
        # DatabaseBackend may not have daily data; use 15min and resample
        result_15m = dal.get_prices(ticker=ticker, interval="15min", days=days)
        if result_15m.bars:
            result = _resample_to_daily_result(result_15m)

    if not result.bars:
        return {
            "ticker": ticker.upper(),
            "days": days,
            "bar_count": 0,
            "error": "No price data available",
        }

    bars = result.bars
    latest_close = bars[-1].close
    period_open = bars[0].open
    period_high = max(b.high for b in bars)
    period_low = min(b.low for b in bars)
    total_volume = sum(b.volume for b in bars)

    change_pct = ((latest_close - period_open) / period_open * 100) if period_open else 0
    range_pct = ((period_high - period_low) / period_low * 100) if period_low else 0

    return {
        "ticker": ticker.upper(),
        "days": days,
        "bar_count": len(bars),
        "latest_close": round(latest_close, 2),
        "period_open": round(period_open, 2),
        "change_pct": round(change_pct, 2),
        "period_high": round(period_high, 2),
        "period_low": round(period_low, 2),
        "high_low_range_pct": round(range_pct, 2),
        "total_volume": total_volume,
        "date_range": result.date_range,
    }


def get_sector_performance(
    dal: DataAccessLayer,
    sector: str,
    days: int = 7,
) -> dict:
    """
    Calculate sector-level performance by averaging constituent tickers.

    Args:
        dal: DataAccessLayer instance
        sector: Sector name (e.g. 'AI_CHIPS', 'FINTECH')
        days: Lookback period in days

    Returns:
        Dict with:
            sector, days, ticker_count, avg_change_pct,
            best_ticker, worst_ticker, ticker_details
    """
    tickers = dal.get_sector_tickers(sector)
    if not tickers:
        return {
            "sector": sector,
            "days": days,
            "error": f"Unknown sector: {sector}",
        }

    # Get price data for available tickers
    available = set(dal.get_available_tickers("prices"))
    ticker_details: List[dict] = []

    for t in tickers:
        if t not in available:
            continue
        change = get_price_change(dal, t, days)
        if "error" not in change and change.get("bar_count", 0) > 0:
            ticker_details.append({
                "ticker": t,
                "change_pct": change["change_pct"],
                "latest_close": change["latest_close"],
                "volume": change["total_volume"],
            })

    if not ticker_details:
        return {
            "sector": sector,
            "days": days,
            "ticker_count": 0,
            "error": "No price data available for sector tickers",
        }

    changes = [d["change_pct"] for d in ticker_details]
    avg_change = sum(changes) / len(changes)

    best = max(ticker_details, key=lambda x: x["change_pct"])
    worst = min(ticker_details, key=lambda x: x["change_pct"])

    return {
        "sector": sector,
        "days": days,
        "ticker_count": len(ticker_details),
        "avg_change_pct": round(avg_change, 2),
        "median_change_pct": round(sorted(changes)[len(changes) // 2], 2),
        "best_ticker": best["ticker"],
        "best_change_pct": best["change_pct"],
        "worst_ticker": worst["ticker"],
        "worst_change_pct": worst["change_pct"],
        "ticker_details": ticker_details,
    }