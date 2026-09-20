"""Request-scoped evidence missing from ib_insync's generic Ticker snapshot."""

from contextlib import contextmanager
from datetime import datetime, timezone
import logging
import math


logger = logging.getLogger(__name__)


def positive_price(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def volume_count(value):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return int(number) if math.isfinite(number) and number >= 0 and number.is_integer() else None


@contextmanager
def _observe_callbacks(wrapper, observers):
    # The installed decoder resolves wrapper methods on each message. Keep its
    # normal processing and restore even on cancellation; never patch the class.
    previous = {}
    try:
        for name, observer in observers.items():
            original = getattr(wrapper, name)
            previous[name] = (name in vars(wrapper), original)

            def forward(*args, _original=original, _observer=observer):
                _original(*args)
                _observer(*args)

            setattr(wrapper, name, forward)
        yield
    finally:
        for name, (owned, original) in reversed(tuple(previous.items())):
            if owned:
                setattr(wrapper, name, original)
            else:
                delattr(wrapper, name)


def request_quote_snapshot(ib, contract, ticker):
    """Collect a bounded, non-regulatory snapshot on this owned connection.

    A two-second observation is allowed to be partial. Ticker.time is local
    packet receipt, and Ticker.marketDataType defaults to 1 without evidence;
    neither is proof of a current trade. Capture the actual callbacks instead.
    """
    req_id = ib.client.getReqId()
    wrapper = ib.wrapper
    result = {
        "ticker": ticker.upper(), "contract_id": contract.conId,
        "currency": contract.currency, "requested_at": datetime.now(timezone.utc).isoformat(),
        "received_at": None, "market_data_type": None, "last_trade_at": None,
        "snapshot_complete": False, "provider_error_codes": [],
    }
    last_tick = None

    def market_type(request_id, value):
        if request_id == req_id and type(value) is int and value in (1, 2, 3, 4):
            result["market_data_type"] = value

    def price_tick(request_id, tick_type, price, size):
        nonlocal last_tick
        if request_id != req_id:
            return
        result["received_at"] = datetime.now(timezone.utc).isoformat()
        if tick_type in (4, 68):
            last_tick = tick_type
            result["last_trade_at"] = None

    def string_tick(request_id, tick_type, value):
        if request_id != req_id or (last_tick, tick_type) not in ((4, 45), (68, 88)):
            return
        result["last_trade_at"] = None
        try:
            if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
                return
            result["last_trade_at"] = datetime.fromtimestamp(int(value), timezone.utc).isoformat()
        except (ValueError, OverflowError, OSError):
            pass

    def completed(request_id):
        if request_id == req_id:
            result["snapshot_complete"] = True

    def error(request_id, code, message, error_contract):
        if request_id == req_id and type(code) is int and code not in result["provider_error_codes"]:
            result["provider_error_codes"].append(code)

    ticker_data = None
    ib.errorEvent += error
    try:
        with _observe_callbacks(wrapper, {
            "marketDataType": market_type, "priceSizeTick": price_tick,
            "tickString": string_tick, "tickSnapshotEnd": completed,
        }):
            ticker_data = wrapper.startTicker(req_id, contract, "mktData")
            ib.client.reqMktData(req_id, contract, "", True, False, [])
            ib.sleep(2)
            for name in ("bid", "ask", "last", "high", "low", "close"):
                result[name] = positive_price(getattr(ticker_data, name, None))
            result["volume"] = volume_count(getattr(ticker_data, "volume", None))
            if ((result["market_data_type"] in (1, 2) and last_tick == 68)
                    or (result["market_data_type"] in (3, 4) and last_tick == 4)):
                result["last_trade_at"] = None
    finally:
        ib.errorEvent -= error
        if ticker_data is not None:
            try:
                ib.client.cancelMktData(req_id)
            except Exception as exc:
                logger.warning("Quote cancellation failed (%s)", type(exc).__name__)
            finally:
                wrapper.endTicker(ticker_data, "mktData")
                wrapper.reqId2Ticker.pop(req_id, None)

    codes = set(result["provider_error_codes"])
    if codes & {354, 10089, 10091, 10168, 10186}:
        result["error"] = "ibkr_market_data_not_subscribed"
    elif codes - {10090, 10167}:
        result["error"] = "ibkr_quote_request_failed"
    elif not any(result[name] is not None for name in ("last", "bid", "ask", "close")):
        result["error"] = "ibkr_quote_no_price" if result["snapshot_complete"] else "ibkr_quote_timeout"
    if result.get("error"):
        for name in ("bid", "ask", "last", "close"):
            result[name] = None
    return result
