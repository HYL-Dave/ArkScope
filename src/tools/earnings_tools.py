"""
Earnings impact analysis tool (Batch 3c).

Provides get_earnings_impact() — quantifies historical earnings price reactions:
- Earnings-day price moves (close-to-close)
- Average absolute move, directional bias
- Surprise correlation (beat → up, miss → down)
- Expected move estimation
- Pre/post earnings drift (5-day)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from .data_access import DataAccessLayer

logger = logging.getLogger(__name__)

_DRIFT_WINDOW = 5  # trading days before/after earnings
_DATE_TOLERANCE = 5  # trading days tolerance for matching earnings to price data


def _find_nearest_price_index(
    dates: List[str], target_date: str, tolerance: int = _DATE_TOLERANCE,
) -> Optional[int]:
    """
    Find index in dates list nearest to target_date, within tolerance.

    dates: sorted list of date strings (YYYY-MM-DD).
    target_date: YYYY-MM-DD to match.
    """
    best_idx = None
    best_diff = float("inf")

    for i, d in enumerate(dates):
        try:
            diff = abs(
                (datetime.strptime(d, "%Y-%m-%d") - datetime.strptime(target_date, "%Y-%m-%d")).days
            )
        except ValueError:
            continue

        if diff < best_diff:
            best_diff = diff
            best_idx = i

    if best_idx is not None and best_diff <= tolerance:
        return best_idx
    return None


def _compute_move(
    closes: List[float], dates: List[str], idx: int,
) -> Optional[Dict[str, Any]]:
    """Compute earnings-day move and pre/post drift around index."""
    if idx < 1 or idx >= len(closes):
        return None

    # Earnings day move (close-to-close)
    prev_close = closes[idx - 1]
    earnings_close = closes[idx]
    if prev_close <= 0:
        return None

    day_move_pct = (earnings_close - prev_close) / prev_close * 100

    # Pre-drift: 5 days before earnings
    pre_start = max(0, idx - _DRIFT_WINDOW - 1)
    pre_drift_pct = None
    if pre_start < idx - 1 and closes[pre_start] > 0:
        pre_drift_pct = (closes[idx - 1] - closes[pre_start]) / closes[pre_start] * 100

    # Post-drift: 5 days after earnings
    post_end = min(len(closes) - 1, idx + _DRIFT_WINDOW)
    post_drift_pct = None
    if post_end > idx and earnings_close > 0:
        post_drift_pct = (closes[post_end] - earnings_close) / earnings_close * 100

    return {
        "earnings_day_move_pct": round(day_move_pct, 2),
        "pre_drift_5d_pct": round(pre_drift_pct, 2) if pre_drift_pct is not None else None,
        "post_drift_5d_pct": round(post_drift_pct, 2) if post_drift_pct is not None else None,
    }


# ── Main tool function ──────────────────────────────────────


def get_earnings_impact(
    dal: "DataAccessLayer",
    ticker: str,
    quarters: int = 4,
) -> Dict[str, Any]:
    """
    Analyze historical earnings price reactions for a ticker.

    Combines Finnhub earnings history (actual vs estimate) with price data
    to quantify earnings-day moves, drift, and surprise correlation.

    Args:
        dal: DataAccessLayer instance.
        ticker: Stock ticker symbol.
        quarters: Number of past quarters to analyze (max: 4 on free tier).

    Returns:
        Dict with historical_moves, summary, surprise_analysis, expected_move.
    """
    from .analyst_tools import get_analyst_consensus

    ticker = ticker.upper()
    quarters = min(quarters, 4)

    # Get earnings data from Finnhub
    try:
        consensus = get_analyst_consensus(ticker)
    except Exception as e:
        return {"error": f"Failed to get earnings data: {e}", "ticker": ticker}

    earnings_data = consensus.get("earnings", {})
    history = earnings_data.get("history", [])
    upcoming = earnings_data.get("upcoming")

    if not history:
        return {
            "error": "No earnings history available from Finnhub",
            "ticker": ticker,
        }

    # Get price data (1 year to cover 4 quarters)
    try:
        pr = dal.get_prices(ticker, interval="1d", days=365)
        if not pr.bars:
            return {"error": "No price data available", "ticker": ticker}
    except Exception as e:
        return {"error": f"Failed to get price data: {e}", "ticker": ticker}

    # Build price arrays
    dates = [bar.datetime[:10] for bar in pr.bars]
    closes = [bar.close for bar in pr.bars]
    latest_close = closes[-1] if closes else 0

    # Process each earnings quarter
    historical_moves = []
    for entry in history[:quarters]:
        period = entry.get("period", "")
        if not period:
            continue

        # Find the earnings date in price data
        idx = _find_nearest_price_index(dates, period)
        if idx is None:
            continue

        # Compute price moves
        moves = _compute_move(closes, dates, idx)
        if moves is None:
            continue

        actual = entry.get("actual")
        estimate = entry.get("estimate")
        surprise_pct = entry.get("surprisePercent")

        # Classify beat/miss
        if surprise_pct is not None and surprise_pct > 0:
            beat_miss = "beat"
        elif surprise_pct is not None and surprise_pct < 0:
            beat_miss = "miss"
        elif surprise_pct is not None:
            beat_miss = "meet"
        else:
            beat_miss = None

        historical_moves.append({
            "period": period,
            "actual_eps": actual,
            "estimate_eps": estimate,
            "surprise_pct": round(surprise_pct, 2) if surprise_pct is not None else None,
            "beat_miss": beat_miss,
            **moves,
        })

    if not historical_moves:
        return {
            "error": "Could not match any earnings dates to price data",
            "ticker": ticker,
        }

    # Summary statistics
    day_moves = [m["earnings_day_move_pct"] for m in historical_moves]
    abs_moves = [abs(m) for m in day_moves]
    up_count = sum(1 for m in day_moves if m > 0)
    down_count = sum(1 for m in day_moves if m < 0)

    pre_drifts = [m["pre_drift_5d_pct"] for m in historical_moves if m["pre_drift_5d_pct"] is not None]
    post_drifts = [m["post_drift_5d_pct"] for m in historical_moves if m["post_drift_5d_pct"] is not None]

    summary = {
        "avg_absolute_move_pct": round(sum(abs_moves) / len(abs_moves), 2) if abs_moves else 0,
        "max_move_pct": round(max(day_moves), 2) if day_moves else 0,
        "min_move_pct": round(min(day_moves), 2) if day_moves else 0,
        "up_count": up_count,
        "down_count": down_count,
        "up_ratio": round(up_count / len(day_moves), 2) if day_moves else 0,
        "avg_pre_drift_5d_pct": round(sum(pre_drifts) / len(pre_drifts), 2) if pre_drifts else None,
        "avg_post_drift_5d_pct": round(sum(post_drifts) / len(post_drifts), 2) if post_drifts else None,
    }

    # Surprise analysis
    beats = [m for m in historical_moves if m.get("beat_miss") == "beat"]
    misses = [m for m in historical_moves if m.get("beat_miss") == "miss"]
    meets = [m for m in historical_moves if m.get("beat_miss") == "meet"]

    beat_up = sum(1 for m in beats if m["earnings_day_move_pct"] > 0)
    miss_down = sum(1 for m in misses if m["earnings_day_move_pct"] < 0)

    beat_up_ratio = round(beat_up / len(beats), 2) if beats else None
    miss_down_ratio = round(miss_down / len(misses), 2) if misses else None

    # Surprise is predictive if > 60% of beats go up AND > 60% of misses go down
    surprise_predictive = (
        (beat_up_ratio is not None and beat_up_ratio > 0.6)
        or (miss_down_ratio is not None and miss_down_ratio > 0.6)
    )

    surprise_analysis = {
        "beats": len(beats),
        "misses": len(misses),
        "meets": len(meets),
        "beat_up_ratio": beat_up_ratio,
        "miss_down_ratio": miss_down_ratio,
        "surprise_predictive": surprise_predictive,
    }

    # Expected move
    avg_abs_move = summary["avg_absolute_move_pct"]
    expected_move = {
        "expected_move_pct": avg_abs_move,
        "expected_move_dollars": round(latest_close * avg_abs_move / 100, 2) if latest_close > 0 else None,
        "based_on": f"historical_avg_{len(historical_moves)}q",
    }

    return {
        "ticker": ticker,
        "quarters_analyzed": len(historical_moves),
        "upcoming_earnings": upcoming,
        "historical_moves": historical_moves,
        "summary": summary,
        "surprise_analysis": surprise_analysis,
        "expected_move": expected_move,
    }
