"""
SEC data tools — direct SEC EDGAR access (no API key needed).

Phase 11a: Bridges existing data_sources/ SEC modules into the agent tool layer.

Decision (2026-02-15):
- get_sec_filings: replaces empty DAL implementation with direct EDGAR access
- get_insider_trades: new tool, fully structured Form 4 data (high signal, low tokens)
- get_earnings_releases: NOT bridged (raw text dump, poor token efficiency)
  → see AGENT_EVOLUTION_TRACKER.md Phase 11a for full rationale
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def get_sec_filings(
    ticker: str,
    filing_types: Optional[List[str]] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Get SEC filings metadata (10-K, 10-Q, 8-K, etc.) for a ticker.

    Returns filing type, date, URL, and accession number — metadata only,
    not the filing content itself. Use the URL to access full filings.

    Args:
        ticker: Stock ticker symbol (e.g. NVDA, AAPL)
        filing_types: Filter by filing types (e.g. ['10-K', '10-Q'])
        limit: Maximum number of filings to return (default: 10)

    Returns:
        List of dicts with: cik, accession_number, filing_type, report_date,
        ticker, url, xbrl_url
    """
    from data_sources.sec_edgar_financials import get_filings_list
    try:
        return get_filings_list(ticker, filing_types=filing_types, limit=limit)
    except Exception as e:
        logger.error(f"SEC filings error for {ticker}: {e}")
        return []


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