"""Current quote tool.

Read-through only: no persistence, no scheduling, no telemetry writes.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from .schemas import CurrentQuoteResult

if TYPE_CHECKING:
    from .data_access import DataAccessLayer


_VALID_SOURCES = {"auto", "ibkr", "local"}


def _clean_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out) or out <= 0:
        return None
    return out


def _clean_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        out = int(value)
    except (TypeError, ValueError):
        return None
    return out if out >= 0 else None


def _local_last_bar_quote(dal: DataAccessLayer, ticker: str) -> CurrentQuoteResult:
    t = ticker.upper()
    result = dal.get_prices(t, interval="15min", days=10)
    if not result.bars:
        result = dal.get_prices(t, interval="1d", days=365)
    if not result.bars:
        return CurrentQuoteResult(
            ticker=t,
            provider="local",
            mode="unavailable",
            error="no_local_price_bars",
            source_note="No stored local price bars were available.",
        )

    bar = result.bars[-1]
    close = _clean_float(getattr(bar, "close", None))
    volume = _clean_int(getattr(bar, "volume", None))
    return CurrentQuoteResult(
        ticker=t,
        provider="local",
        mode="local_last_bar",
        price=close,
        close=close,
        volume=volume,
        timestamp=str(getattr(bar, "datetime", "")) or None,
        stale=True,
        source_note="latest last stored bar close; this is not a live quote.",
    )


def _quote_from_ibkr_payload(ticker: str, payload: dict[str, Any]) -> CurrentQuoteResult:
    bid = _clean_float(payload.get("bid"))
    ask = _clean_float(payload.get("ask"))
    last = _clean_float(payload.get("last"))
    close = _clean_float(payload.get("close"))
    mid = ((bid + ask) / 2.0) if bid is not None and ask is not None else None
    price = last or mid or close
    if price is None:
        return CurrentQuoteResult(
            ticker=ticker.upper(),
            provider="ibkr",
            mode="unavailable",
            error="ibkr_quote_no_price",
            source_note="IBKR returned a snapshot but no usable last, bid/ask midpoint, or close.",
        )
    return CurrentQuoteResult(
        ticker=ticker.upper(),
        provider="ibkr",
        mode="ibkr_snapshot",
        price=round(price, 6),
        bid=bid,
        ask=ask,
        last=last,
        close=close,
        volume=_clean_int(payload.get("volume")),
        timestamp=datetime.now(timezone.utc).isoformat(),
        stale=False,
        source_note=(
            "IBKR market-data snapshot; live vs delayed depends on account "
            "subscriptions and Gateway market-data type."
        ),
    )


def _fetch_ibkr_quote(ticker: str) -> CurrentQuoteResult:
    from data_sources.ibkr_client_id import ibkr_client_id_for
    from data_sources.ibkr_source import IBKRDataSource

    source = IBKRDataSource(client_id=ibkr_client_id_for("quotes"), readonly=True)
    try:
        source.connect()
        payload = source.get_current_quote(ticker.upper()) or {}
    finally:
        source.disconnect()
    return _quote_from_ibkr_payload(ticker, payload)


def get_current_quote(
    dal: DataAccessLayer,
    ticker: str,
    source: str = "auto",
) -> CurrentQuoteResult:
    """Return a current quote or an explicitly labeled local fallback."""
    t = ticker.upper()
    src = (source or "auto").lower()
    if src not in _VALID_SOURCES:
        return CurrentQuoteResult(
            ticker=t,
            provider=src,
            mode="unavailable",
            error="invalid_quote_source",
            source_note="source must be one of: auto, ibkr, local",
        )
    if src == "local":
        return _local_last_bar_quote(dal, t)

    try:
        quote = _fetch_ibkr_quote(t)
    except Exception as exc:
        quote = CurrentQuoteResult(
            ticker=t,
            provider="ibkr",
            mode="unavailable",
            error=f"ibkr_quote_failed:{type(exc).__name__}",
            source_note="IBKR quote request failed.",
        )
    if quote.mode != "unavailable" or src == "ibkr":
        return quote

    fallback = _local_last_bar_quote(dal, t)
    fallback.source_note = f"IBKR unavailable ({quote.error}); {fallback.source_note}"
    return fallback
