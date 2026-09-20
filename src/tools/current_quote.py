"""Current quote tool.

Read-through only: no persistence, no scheduling, no telemetry writes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from data_sources.ibkr_quote_snapshot import positive_price, volume_count

from .schemas import CurrentQuoteResult

if TYPE_CHECKING:
    from .data_access import DataAccessLayer


_VALID_SOURCES = {"auto", "ibkr", "local"}


def _instant(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is not None and parsed.utcoffset() is not None:
            return parsed.astimezone(timezone.utc)
    except (AttributeError, TypeError, ValueError, OverflowError):
        pass
    return None


def _timestamp(value: Any) -> str | None:
    parsed = _instant(value)
    return parsed.isoformat() if parsed is not None else None


def _local_last_bar_quote(dal: DataAccessLayer, ticker: str, max_age_seconds: int = 60) -> CurrentQuoteResult:
    t = ticker.upper()
    result = dal.get_prices(t, interval="15min", days=10)
    if not result.bars:
        result = dal.get_prices(t, interval="1d", days=365)
    if not result.bars:
        return CurrentQuoteResult(
            ticker=t,
            provider="local",
            mode="unavailable",
            max_age_seconds=max_age_seconds,
            error="no_local_price_bars",
            source_note="No stored local price bars were available.",
        )

    bar = result.bars[-1]
    close = positive_price(getattr(bar, "close", None))
    volume = volume_count(getattr(bar, "volume", None))
    if close is None:
        return CurrentQuoteResult(
            ticker=t, provider="local", mode="unavailable", max_age_seconds=max_age_seconds,
            error="invalid_local_price_bar", source_note="The latest stored close is unusable.",
        )
    return CurrentQuoteResult(
        ticker=t,
        provider="local",
        mode="local_last_bar",
        price=close,
        close=close,
        volume=volume,
        timestamp=str(getattr(bar, "datetime", "")) or None,
        stale=True,
        freshness="stale", freshness_reason="historical_bar",
        price_basis="stored_bar_close", timestamp_basis="local_bar",
        evaluated_at=datetime.now(timezone.utc).isoformat(), max_age_seconds=max_age_seconds,
        source_note="latest last stored bar close; this is not a live quote.",
    )


def _quote_from_ibkr_payload(
    ticker: str, payload: dict[str, Any], max_age_seconds: int = 60,
) -> CurrentQuoteResult:
    now = datetime.now(timezone.utc)
    bid, ask, last, close = (positive_price(payload.get(key)) for key in ("bid", "ask", "last", "close"))
    mid = (bid / 2 + ask / 2) if bid is not None and ask is not None and bid <= ask else None
    data_type = payload.get("market_data_type")
    market_type = {1: "live", 2: "frozen", 3: "delayed", 4: "delayed_frozen"}.get(
        data_type if type(data_type) is int else None, "unknown")
    trade_at = _instant(payload.get("last_trade_at"))
    codes = payload.get("provider_error_codes", [])
    codes = [code for code in codes if type(code) is int] if isinstance(codes, list) else []
    result = CurrentQuoteResult(
        ticker=ticker.upper(), provider="ibkr", mode="unavailable",
        bid=bid, ask=ask, last=last, close=close,
        volume=volume_count(payload.get("volume")),
        requested_at=_timestamp(payload.get("requested_at")),
        received_at=_timestamp(payload.get("received_at")), evaluated_at=now.isoformat(),
        last_trade_at=trade_at.isoformat() if trade_at else None,
        contract_id=payload.get("contract_id"), currency=payload.get("currency"),
        market_data_type=market_type, max_age_seconds=max_age_seconds,
        snapshot_complete=payload.get("snapshot_complete"), provider_error_codes=codes,
    )
    errors = {
        "ibkr_market_data_not_subscribed", "ibkr_quote_request_failed",
        "ibkr_quote_no_price", "ibkr_quote_timeout", "ibkr_contract_unresolved",
    }
    if payload.get("error"):
        result.error = payload["error"] if payload["error"] in errors else "ibkr_quote_request_failed"
        result.source_note = "IBKR did not return a usable request-bound quote."
        return result
    if last is not None:
        result.price, result.price_basis = last, "last_trade"
        result.timestamp = result.last_trade_at
        result.timestamp_basis = "provider_last_trade" if trade_at else None
        result.quote_age_seconds = (now - trade_at).total_seconds() if trade_at else None
    elif mid is not None:
        result.price, result.price_basis = mid, "bid_ask_midpoint"
    elif close is not None:
        result.price, result.price_basis = close, "previous_close"
    else:
        result.error = "ibkr_quote_no_price"
        result.source_note = "No positive finite last, valid bid/ask midpoint or previous close."
        return result

    result.mode = "ibkr_previous_close" if result.price_basis == "previous_close" else "ibkr_snapshot"
    age = result.quote_age_seconds
    if result.price_basis == "previous_close":
        result.stale, result.freshness_reason = True, "previous_close"
    elif market_type in {"frozen", "delayed", "delayed_frozen"}:
        result.stale, result.freshness_reason = True, market_type
    elif age is not None and age >= 0 and age > max_age_seconds:
        result.stale, result.freshness_reason = True, "price_age_exceeded"
    elif age is not None and age < 0:
        result.freshness_reason = "provider_timestamp_future"
    elif market_type == "unknown":
        result.freshness_reason = "market_data_type_unobserved"
    elif age is None:
        result.freshness_reason = "price_timestamp_unavailable"
    else:
        result.stale, result.freshness_reason = False, "within_requested_age"
    result.freshness = "unknown" if result.stale is None else ("stale" if result.stale else "fresh")
    result.source_note = (
        "Price basis, feed mode and price age are separate evidence. "
        "received_at is local receipt, not trade time; stale=null means unverified. "
        "A partial snapshot does not establish complete market-data entitlement."
    )
    return result


def _fetch_ibkr_quote(ticker: str, max_age_seconds: int = 60) -> CurrentQuoteResult:
    from data_sources.ibkr_client_id import ibkr_client_id_for
    from data_sources.ibkr_source import IBKRDataSource

    source = IBKRDataSource(client_id=ibkr_client_id_for("quotes"), readonly=True)
    try:
        source.connect()
        payload = source.get_current_quote(ticker.upper()) or {}
    finally:
        source.disconnect()
    return _quote_from_ibkr_payload(ticker, payload, max_age_seconds=max_age_seconds)


def get_current_quote(
    dal: DataAccessLayer,
    ticker: str,
    source: str = "auto",
    max_age_seconds: int = 60,
) -> CurrentQuoteResult:
    """Return a current quote or an explicitly labeled local fallback."""
    t = ticker.upper()
    if type(max_age_seconds) is not int or max_age_seconds < 0:
        return CurrentQuoteResult(ticker=t, provider=source, mode="unavailable", error="invalid_quote_max_age")
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
        return _local_last_bar_quote(dal, t, max_age_seconds)

    try:
        quote = _fetch_ibkr_quote(t, max_age_seconds=max_age_seconds)
    except Exception as exc:
        quote = CurrentQuoteResult(
            ticker=t,
            provider="ibkr",
            mode="unavailable",
            error=f"ibkr_quote_failed:{type(exc).__name__}",
            max_age_seconds=max_age_seconds,
            source_note="IBKR quote request failed.",
        )
    if quote.mode != "unavailable" or src == "ibkr":
        return quote

    fallback = _local_last_bar_quote(dal, t, max_age_seconds)
    fallback.fallback_reason = quote.error
    fallback.source_note = f"IBKR unavailable ({quote.error}); {fallback.source_note}"
    return fallback
