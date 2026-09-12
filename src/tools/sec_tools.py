"""
SEC data tools — direct SEC EDGAR access (no API key needed).

Phase 11a: Bridges existing data_sources/ SEC modules into the agent tool layer.

Decision (2026-02-15):
- get_insider_trades: new tool, fully structured Form 4 data (high signal, low tokens)
- get_earnings_releases: NOT bridged (raw text dump, poor token efficiency)
"""

from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def get_insider_trades(
    ticker: str,
    limit: int = 10,
) -> Dict[str, Any]:
    """
    Get recent insider trades (SEC Form 4) for a ticker.

    Fully parsed and structured: insider name, title, transaction date,
    shares bought/sold, price, and holdings before/after.

    Args:
        ticker: Stock ticker symbol (e.g. AAPL, NVDA)
        limit: Maximum number of trades to return (default: 10)

    Returns:
        Dict with ticker, count, and trades list. Each trade has:
        name, title, transaction_date, transaction_shares (negative=sale),
        transaction_price_per_share, shares_owned_after_transaction, etc.
    """
    from data_sources.sec_insider_trades import get_insider_trades as _fetch
    try:
        trades = _fetch(ticker, limit=limit)
    except Exception as e:
        logger.error(f"Insider trades error for {ticker}: {e}")
        trades = []
    return {
        "ticker": ticker.upper(),
        "count": len(trades),
        "trades": trades,
    }
