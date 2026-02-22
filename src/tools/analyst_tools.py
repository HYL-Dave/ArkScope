"""
Analyst consensus tools (Phase 11b).

Provides get_analyst_consensus() using Finnhub free API endpoints:
- /stock/recommendation  (analyst buy/sell/hold distribution)
- /stock/earnings        (last 4 quarters actual vs estimate)
- /calendar/earnings     (upcoming earnings date + estimates)
- /stock/price-target    (premium — graceful fallback to null)
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# ── Finnhub session (lazy-init) ──────────────────────────────

_session: Optional[requests.Session] = None
_api_key: Optional[str] = None

_FINNHUB_BASE = "https://finnhub.io/api/v1"


def _get_finnhub_session() -> tuple[requests.Session, str]:
    """Lazy-init requests session and read FINNHUB_API_KEY from env."""
    global _session, _api_key
    if _session is None:
        _api_key = os.environ.get("FINNHUB_API_KEY", "")
        if not _api_key:
            raise ValueError(
                "FINNHUB_API_KEY not set in environment. "
                "Get a free key at https://finnhub.io/"
            )
        adapter = requests.adapters.HTTPAdapter(pool_maxsize=20)
        _session = requests.Session()
        _session.mount("https://", adapter)
        _session.headers.update({"X-Finnhub-Token": _api_key})
    return _session, _api_key


def _finnhub_get(endpoint: str, params: Optional[Dict] = None) -> Optional[Any]:
    """
    GET https://finnhub.io/api/v1{endpoint}.

    Returns parsed JSON on success, None on 403 (premium endpoint) or error.
    """
    session, api_key = _get_finnhub_session()
    url = f"{_FINNHUB_BASE}{endpoint}"
    try:
        resp = session.get(url, params=params or {}, timeout=10)
        if resp.status_code == 403:
            logger.debug("Finnhub %s returned 403 (premium), skipping", endpoint)
            return None
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.warning("Finnhub %s request failed: %s", endpoint, e)
        return None


# ── Individual fetch functions ───────────────────────────────

def _fetch_recommendations(ticker: str) -> Dict[str, Any]:
    """Fetch analyst recommendation trends from /stock/recommendation."""
    data = _finnhub_get("/stock/recommendation", {"symbol": ticker})
    if not data:
        return {"current": None, "trend": []}

    # Data comes sorted newest-first
    current = None
    trend = []
    for i, entry in enumerate(data[:4]):
        rec = {
            "strongBuy": entry.get("strongBuy", 0),
            "buy": entry.get("buy", 0),
            "hold": entry.get("hold", 0),
            "sell": entry.get("sell", 0),
            "strongSell": entry.get("strongSell", 0),
            "period": entry.get("period", ""),
        }
        if i == 0:
            current = rec
        else:
            trend.append(rec)

    return {"current": current, "trend": trend}


def _fetch_earnings_history(ticker: str) -> List[Dict[str, Any]]:
    """Fetch last 4 quarters earnings from /stock/earnings."""
    data = _finnhub_get("/stock/earnings", {"symbol": ticker})
    if not data:
        return []

    history = []
    for entry in data[:4]:
        history.append({
            "period": entry.get("period", ""),
            "actual": entry.get("actual"),
            "estimate": entry.get("estimate"),
            "surprisePercent": entry.get("surprisePercent"),
        })
    return history


def _fetch_upcoming_earnings(ticker: str) -> Optional[Dict[str, Any]]:
    """Fetch upcoming earnings from /calendar/earnings."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    data = _finnhub_get("/calendar/earnings", {"symbol": ticker, "from": now})

    if not data or not isinstance(data, dict):
        return None

    earnings_list = data.get("earningsCalendar", [])
    if not earnings_list:
        return None

    # Pick the soonest upcoming entry for this ticker
    for entry in earnings_list:
        if entry.get("symbol", "").upper() == ticker.upper():
            return {
                "date": entry.get("date", ""),
                "hour": entry.get("hour", ""),
                "epsEstimate": entry.get("epsEstimate"),
                "revenueEstimate": entry.get("revenueEstimate"),
            }
    return None


def _fetch_price_target(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Fetch analyst price targets from /stock/price-target.

    This is a premium endpoint — returns None if 403.
    """
    data = _finnhub_get("/stock/price-target", {"symbol": ticker})
    if not data or not isinstance(data, dict):
        return None

    # Only return if there's actual data
    if data.get("targetHigh") is None and data.get("targetMean") is None:
        return None

    return {
        "targetHigh": data.get("targetHigh"),
        "targetLow": data.get("targetLow"),
        "targetMean": data.get("targetMean"),
        "targetMedian": data.get("targetMedian"),
        "lastUpdated": data.get("lastUpdated", ""),
    }


# ── Main tool function ──────────────────────────────────────

def get_analyst_consensus(ticker: str) -> Dict[str, Any]:
    """
    Get analyst consensus data for a ticker.

    Aggregates:
    - Analyst recommendation distribution (buy/hold/sell) + trend
    - Earnings history (last 4 quarters actual vs estimate)
    - Upcoming earnings date and estimates
    - Price target (premium, null if unavailable)

    Returns a dict with all data, suitable for JSON serialization.
    """
    ticker = ticker.upper()
    recommendations = _fetch_recommendations(ticker)
    earnings_history = _fetch_earnings_history(ticker)
    upcoming = _fetch_upcoming_earnings(ticker)
    price_target = _fetch_price_target(ticker)

    return {
        "ticker": ticker,
        "recommendations": recommendations,
        "earnings": {
            "history": earnings_history,
            "upcoming": upcoming,
        },
        "price_target": price_target,
    }