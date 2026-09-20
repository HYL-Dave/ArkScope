"""Quote acquisition time must not impersonate the selected price's time."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.tools import current_quote as module


NOW = datetime(2026, 9, 18, 15, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def quote_clock(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW if tz else NOW.replace(tzinfo=None)

    monkeypatch.setattr(module, "datetime", Clock)


def payload(**changes):
    return {
        "last": 101.25, "bid": 101.0, "ask": 101.5, "close": 99.0,
        "market_data_type": 1,
        "last_trade_at": (NOW - timedelta(seconds=10)).isoformat(),
        "requested_at": (NOW - timedelta(seconds=2)).isoformat(),
        "received_at": NOW.isoformat(), "contract_id": 100, "currency": "USD",
        **changes,
    }


def test_previous_close_is_historical_without_a_fabricated_timestamp():
    result = module._quote_from_ibkr_payload("AAPL", payload(last=None, bid=None, ask=None))
    assert result.price == 99.0
    assert result.mode == "ibkr_previous_close"
    assert result.price_basis == "previous_close"
    assert result.stale is True
    assert result.timestamp is None
    assert result.received_at == NOW.isoformat()


@pytest.mark.parametrize("changes", [
    {"market_data_type": None}, {"market_data_type": True},
    {"last_trade_at": None}, {"last_trade_at": "2026-09-18T15:00:00"},
    {"last_trade_at": (NOW + timedelta(seconds=1)).isoformat()},
])
def test_missing_or_untrustworthy_time_or_mode_never_claims_freshness(changes):
    result = module._quote_from_ibkr_payload("AAPL", payload(**changes))
    assert result.stale is None
    assert result.freshness == "unknown"


@pytest.mark.parametrize("data_type,label", [(2, "frozen"), (3, "delayed"), (4, "delayed_frozen")])
def test_non_live_feed_cannot_be_relabelled_current(data_type, label):
    result = module._quote_from_ibkr_payload("AAPL", payload(market_data_type=data_type))
    assert result.market_data_type == label
    assert result.stale is True
    assert result.freshness == "stale"


def test_provider_trade_time_and_operator_age_are_distinct_from_receipt():
    result = module._quote_from_ibkr_payload("AAPL", payload(), max_age_seconds=20)
    assert result.timestamp == payload()["last_trade_at"]
    assert result.timestamp_basis == "provider_last_trade"
    assert result.quote_age_seconds == 10
    assert result.max_age_seconds == 20
    assert result.stale is False
    assert result.freshness == "fresh"
    assert result.contract_id == 100 and result.currency == "USD"
    assert module._quote_from_ibkr_payload("AAPL", payload(), max_age_seconds=5).stale is True


def test_midpoint_has_no_invented_exchange_timestamp():
    result = module._quote_from_ibkr_payload("AAPL", payload(last=None))
    assert result.price == 101.25
    assert result.price_basis == "bid_ask_midpoint"
    assert result.timestamp is None and result.stale is None


@pytest.mark.parametrize("changes", [
    {"bid": 103, "ask": 101}, {"bid": None}, {"ask": None},
    {"bid": True}, {"ask": float("inf")},
])
def test_invalid_midpoint_does_not_make_a_price(changes):
    result = module._quote_from_ibkr_payload("AAPL", payload(last=None, close=None, **changes))
    assert result.price is None and result.mode == "unavailable"
    assert result.stale is None


@pytest.mark.parametrize("value", [True, False, 0, -1, float("nan"), float("inf"), "bad", 10**1000])
def test_invalid_last_does_not_mask_valid_previous_close(value):
    result = module._quote_from_ibkr_payload("AAPL", payload(last=value, bid=None, ask=None))
    assert result.price == 99.0 and result.price_basis == "previous_close"


@pytest.mark.parametrize("max_age", [-1, True, 1.5, None, "60"])
def test_invalid_age_policy_prevents_acquisition(monkeypatch, max_age):
    acquire = Mock()
    monkeypatch.setattr(module, "_fetch_ibkr_quote", acquire)
    result = module.get_current_quote(object(), "AAPL", max_age_seconds=max_age)
    assert result.error == "invalid_quote_max_age"
    acquire.assert_not_called()


@pytest.fixture
def wire_source(monkeypatch):
    from ib_insync import IB, Stock
    from data_sources.ibkr_source import IBKRDataSource

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ib = IB()
    contract = Stock("AAPL", "SMART", "USD", conId=100)
    source = IBKRDataSource()
    source._ib = ib
    monkeypatch.setattr(source, "_ensure_connected", lambda: None)
    monkeypatch.setattr(source, "_rate_limit_wait", lambda: None)
    monkeypatch.setattr(source, "_create_contract", lambda ticker: contract)
    monkeypatch.setattr(ib, "qualifyContracts", lambda value: [value])
    monkeypatch.setattr(ib.client, "getReqId", lambda: 42)
    send, cancel = Mock(), Mock()
    monkeypatch.setattr(ib.client, "reqMktData", send)
    monkeypatch.setattr(ib.client, "cancelMktData", cancel)
    yield source, ib, send, cancel, contract
    ib.disconnect()
    loop.close()
    asyncio.set_event_loop(None)


def test_real_sdk_callbacks_preserve_trade_time_and_request_identity(wire_source, monkeypatch):
    source, ib, send, cancel, contract = wire_source
    before = dict(ib.wrapper.__dict__)

    def receive(_seconds):
        ib.wrapper.tcpDataArrived()
        ib.wrapper.marketDataType(42, 1)
        ib.wrapper.priceSizeTick(42, 4, 101.25, 5)
        # The installed decoder calls wrapper.tickString dynamically.
        ib.client.decoder.wrap("tickString", [int, int, str])(
            ["46", "1", "42", "45", str(int(NOW.timestamp()))])
        ib.wrapper.tcpDataProcessed()

    monkeypatch.setattr(ib, "sleep", receive)
    result = source.get_current_quote("AAPL")
    assert result["market_data_type"] == 1
    assert result["last_trade_at"] == NOW.isoformat()
    assert result["contract_id"] == 100
    assert result["snapshot_complete"] is False
    assert result["received_at"] != result["last_trade_at"]
    assert send.call_args.args[3:5] == (True, False)
    cancel.assert_called_once_with(42)
    assert 42 not in ib.wrapper.reqId2Ticker
    for method in ("marketDataType", "tickString", "priceSizeTick", "tickSnapshotEnd"):
        assert ib.wrapper.__dict__.get(method) == before.get(method)


def test_sdk_default_live_value_is_not_market_data_evidence(wire_source, monkeypatch):
    source, ib, _, cancel, _ = wire_source
    monkeypatch.setattr(ib, "sleep", lambda _: ib.wrapper.priceSizeTick(42, 9, 99.0, 0))
    result = source.get_current_quote("AAPL")
    assert result["market_data_type"] is None
    assert result["last_trade_at"] is None
    cancel.assert_called_once_with(42)


@pytest.mark.parametrize("req_id,expected", [(42, "ibkr_market_data_not_subscribed"), (999, "ibkr_quote_timeout")])
def test_entitlement_errors_are_bound_to_request(wire_source, monkeypatch, req_id, expected):
    source, ib, _, cancel, contract = wire_source
    monkeypatch.setattr(ib, "sleep", lambda _: ib.errorEvent.emit(req_id, 354, "private provider text", contract))
    result = source.get_current_quote("AAPL")
    assert result["error"] == expected
    assert "private provider text" not in str(result)
    cancel.assert_called_once_with(42)


def test_cancelled_snapshot_releases_request_and_propagates(wire_source, monkeypatch):
    source, ib, _, cancel, _ = wire_source
    def cancelled(_):
        raise asyncio.CancelledError()
    monkeypatch.setattr(ib, "sleep", cancelled)
    with pytest.raises(asyncio.CancelledError):
        source.get_current_quote("AAPL")
    cancel.assert_called_once_with(42)
    assert 42 not in ib.wrapper.reqId2Ticker


@pytest.mark.parametrize("tick,stamp,mode,expected", [
    (68, 88, 3, True), (4, 45, 1, True), (68, 45, 3, False),
    (4, 88, 1, False), (68, 88, 1, False), (4, 45, 3, False),
])
def test_trade_timestamp_must_match_price_tick_and_feed(wire_source, monkeypatch, tick, stamp, mode, expected):
    source, ib, _, _, _ = wire_source
    def receive(_):
        ib.wrapper.marketDataType(42, mode)
        ib.wrapper.priceSizeTick(42, tick, 100, 1)
        ib.wrapper.tickString(42, stamp, str(int(NOW.timestamp())))
        ib.wrapper.tickString(999, stamp, str(int(NOW.timestamp()) + 99))
        ib.wrapper.tickSnapshotEnd(42)
    monkeypatch.setattr(ib, "sleep", receive)
    result = source.get_current_quote("AAPL")
    assert result["last_trade_at"] == (NOW.isoformat() if expected else None)
    assert result["snapshot_complete"] is True


def test_new_price_does_not_inherit_an_older_timestamp(wire_source, monkeypatch):
    source, ib, _, _, _ = wire_source
    def receive(_):
        ib.wrapper.marketDataType(42, 1)
        ib.wrapper.priceSizeTick(42, 4, 100, 1)
        ib.wrapper.tickString(42, 45, str(int(NOW.timestamp())))
        ib.wrapper.priceSizeTick(42, 4, 101, 1)
    monkeypatch.setattr(ib, "sleep", receive)
    result = source.get_current_quote("AAPL")
    assert result["last"] == 101
    assert result["last_trade_at"] is None


def test_qualification_is_bounded_and_timeout_setting_is_restored(wire_source, monkeypatch):
    source, ib, send, cancel, _ = wire_source
    ib.RequestTimeout = 0
    def timeout(_):
        assert ib.RequestTimeout == source.timeout
        raise TimeoutError()
    monkeypatch.setattr(ib, "qualifyContracts", timeout)
    assert source.get_current_quote("AAPL")["error"] == "ibkr_quote_timeout"
    assert ib.RequestTimeout == 0
    send.assert_not_called()
    cancel.assert_not_called()


@pytest.mark.parametrize("value", ["NaN", "-1", "1.5", "99999999999999999999999", "bad"])
def test_bad_wire_time_remains_unknown(wire_source, monkeypatch, value):
    source, ib, _, _, _ = wire_source
    def receive(_):
        ib.wrapper.priceSizeTick(42, 4, 100, 1)
        ib.wrapper.tickString(42, 45, value)
    monkeypatch.setattr(ib, "sleep", receive)
    assert source.get_current_quote("AAPL")["last_trade_at"] is None


def test_acquisition_exception_disconnects_owned_connection(monkeypatch):
    source = Mock()
    source.get_current_quote.side_effect = RuntimeError("private")
    monkeypatch.setattr("data_sources.ibkr_source.IBKRDataSource", Mock(return_value=source))
    result = module.get_current_quote(object(), "AAPL", source="ibkr")
    source.disconnect.assert_called_once()
    assert result.mode == "unavailable" and result.stale is None


def test_historical_fallback_preserves_entitlement_refusal(monkeypatch):
    from tests.test_current_quote_tools import _FakeDAL, _bar

    monkeypatch.setattr(module, "_fetch_ibkr_quote", lambda ticker, **kwargs:
        module._quote_from_ibkr_payload(ticker, {"error": "ibkr_market_data_not_subscribed"}))
    dal = _FakeDAL([_bar()])
    result = module.get_current_quote(dal, "AAPL")
    assert result.fallback_reason == "ibkr_market_data_not_subscribed"
    assert result.price_basis == "stored_bar_close" and result.stale is True


def test_true_source_metadata_reaches_tool_without_replacing_trade_time(wire_source, monkeypatch):
    source, ib, _, _, _ = wire_source
    def receive(_):
        ib.wrapper.marketDataType(42, 1)
        ib.wrapper.priceSizeTick(42, 4, 101, 1)
        ib.wrapper.tickString(42, 45, str(int((NOW - timedelta(seconds=10)).timestamp())))
    monkeypatch.setattr(ib, "sleep", receive)
    raw = source.get_current_quote("AAPL")
    result = module._quote_from_ibkr_payload("AAPL", raw)
    assert result.timestamp == (NOW - timedelta(seconds=10)).isoformat()
    assert result.received_at == raw["received_at"]
    assert result.stale is False
    assert result.snapshot_complete is False
