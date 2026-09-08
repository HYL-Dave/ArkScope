"""Real ib_insync request completion with an offline broker transport."""

import asyncio
from datetime import date
import socket

import pytest
from ib_insync import BarData, ContractDetails, Stock

from data_sources import ibkr_source


@pytest.fixture
def offline_source(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("price_diagnostics_test_must_not_use_network")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    source = ibkr_source.IBKRDataSource(host="offline", client_id=777)
    source._ensure_event_loop()
    source._ib = ibkr_source.IB()
    source._ib.client._apiReady = True
    source._connected = True
    source.REQUEST_DELAY = 0
    calls = []
    ib = source._ib

    def details(req_id, contract):
        calls.append("qualification")
        ib.wrapper.contractDetails(
            req_id,
            ContractDetails(contract=Stock(contract.symbol, "SMART", "USD", conId=123)),
        )
        ib.wrapper.contractDetailsEnd(req_id)

    def history(req_id, contract, *args):
        calls.append("history")
        ib.wrapper.historicalData(
            req_id,
            BarData(date="20260903 13:30:00 UTC",
                    open=10, high=11, low=9, close=10.5, volume=100),
        )
        ib.wrapper.historicalDataEnd(req_id, "", "")

    monkeypatch.setattr(ib.client, "reqContractDetails", details)
    monkeypatch.setattr(ib.client, "reqHistoricalData", history)
    yield source, calls
    ib.client._apiReady = False
    source.disconnect()


def fetch(source, **kwargs):
    return source.fetch_historical_intraday(
        ["LIVE"], date(2026, 9, 3), date(2026, 9, 3), **kwargs
    )


@pytest.mark.parametrize("strict", [False, True])
def test_qualification_request_error_is_not_an_unknown_contract(
    offline_source, monkeypatch, strict,
):
    source, calls = offline_source
    source._ib.RaiseRequestErrors = strict

    def rejected(req_id, contract):
        calls.append("qualification")
        source._ib.wrapper.error(req_id, 321, "PRIVATE_PROVIDER_TEXT", "")

    monkeypatch.setattr(source._ib.client, "reqContractDetails", rejected)
    with pytest.raises(ibkr_source.IBKRPriceDataError) as caught:
        fetch(source)

    assert caught.value.error_code == "ibkr_contract_qualification_failed"
    assert isinstance(caught.value.__cause__, ibkr_source.RequestError)
    assert caught.value.__cause__.code == 321
    assert "PRIVATE_PROVIDER_TEXT" not in str(caught.value)
    assert calls == ["qualification"]
    assert source._ib.RaiseRequestErrors is strict


@pytest.mark.parametrize("outcome", ["unknown", "ambiguous", "error200"])
@pytest.mark.parametrize("strict", [False, True])
def test_genuine_unresolved_contract_remains_security_definition_unavailable(
    offline_source, monkeypatch, outcome, strict,
):
    source, calls = offline_source
    source._ib.RaiseRequestErrors = strict

    def unresolved(req_id, contract):
        calls.append("qualification")
        if outcome == "error200":
            source._ib.wrapper.error(req_id, 200, "No security definition", "")
            return
        if outcome == "ambiguous":
            for con_id in (123, 456):
                source._ib.wrapper.contractDetails(
                    req_id, ContractDetails(contract=Stock("LIVE", "SMART", "USD", conId=con_id)),
                )
        source._ib.wrapper.contractDetailsEnd(req_id)

    monkeypatch.setattr(source._ib.client, "reqContractDetails", unresolved)
    with pytest.raises(ibkr_source.IBKRSecurityDefinitionUnavailable):
        fetch(source)

    assert calls == ["qualification"]
    assert source._ib.RaiseRequestErrors is strict


@pytest.mark.parametrize("error_code", [162, 200, 321])
@pytest.mark.parametrize("strict", [False, True])
def test_history_request_errors_preserve_history_phase(
    offline_source, monkeypatch, error_code, strict,
):
    source, calls = offline_source
    source._ib.RaiseRequestErrors = strict

    def rejected(req_id, contract, *args):
        calls.append("history")
        source._ib.wrapper.error(req_id, error_code, "PRIVATE_PROVIDER_TEXT", "")

    monkeypatch.setattr(source._ib.client, "reqHistoricalData", rejected)
    with pytest.raises(ibkr_source.IBKRHistoricalDataRequestFailed) as caught:
        fetch(source)

    assert caught.value.__cause__.code == error_code
    assert calls == ["qualification", "history"]
    assert source._ib.RaiseRequestErrors is strict


@pytest.mark.parametrize("phase", ["qualification", "history"])
@pytest.mark.parametrize("exception", [TimeoutError, ConnectionError])
def test_transport_exceptions_keep_the_phase(offline_source, monkeypatch, phase, exception):
    source, calls = offline_source

    async def failed(*args, **kwargs):
        raise exception("PRIVATE_PROVIDER_TEXT")

    method = "qualifyContractsAsync" if phase == "qualification" else "reqHistoricalDataAsync"
    monkeypatch.setattr(source._ib, method, failed)
    with pytest.raises(ibkr_source.IBKRPriceDataError) as caught:
        fetch(source)

    assert caught.value.error_code == {
        "qualification": "ibkr_contract_qualification_failed",
        "history": "ibkr_historical_data_request_failed",
    }[phase]
    assert isinstance(caught.value.__cause__, exception)
    assert source._ib.RaiseRequestErrors is False


@pytest.mark.parametrize("strict", [False, True])
def test_success_restores_setting_and_does_not_change_another_connection(offline_source, strict):
    source, calls = offline_source
    source._ib.RaiseRequestErrors = strict
    other = ibkr_source.IB()
    states = []

    def runner(kind, context, operation, args, kwargs):
        states.append((source._ib.RaiseRequestErrors, other.RaiseRequestErrors))
        return operation(*args, **kwargs)

    result = fetch(source, request_runner=runner)

    assert [bar.close for bar in result["LIVE"]] == [10.5]
    assert calls == ["qualification", "history"]
    assert states == [(strict, False), (strict, False)]
    assert source._ib.RaiseRequestErrors is strict
    assert other.RaiseRequestErrors is False


def test_successful_empty_history_is_not_a_request_failure(offline_source, monkeypatch):
    source, calls = offline_source
    monkeypatch.setattr(
        source._ib.client, "reqHistoricalData",
        lambda req_id, *args: source._ib.wrapper.historicalDataEnd(req_id, "", ""),
    )

    assert fetch(source) == {"LIVE": []}
    assert source._ib.RaiseRequestErrors is False


def test_cancellation_restores_request_error_setting(offline_source, monkeypatch):
    source, calls = offline_source

    async def cancelled(*args, **kwargs):
        raise asyncio.CancelledError()

    monkeypatch.setattr(source._ib, "qualifyContractsAsync", cancelled)
    with pytest.raises(asyncio.CancelledError):
        fetch(source)

    assert source._ib.RaiseRequestErrors is False
