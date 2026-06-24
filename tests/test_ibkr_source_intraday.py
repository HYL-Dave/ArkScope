from datetime import date, datetime
from types import SimpleNamespace

from data_sources import ibkr_source


class _FakeIB:
    def __init__(self):
        self.calls = []

    def isConnected(self):
        return True

    def qualifyContracts(self, contract):
        return [contract]

    def reqHistoricalData(self, contract, **kwargs):
        self.calls.append(kwargs)
        return [
            SimpleNamespace(
                date=datetime(2026, 6, 22, 9, 30),
                open=1,
                high=2,
                low=0.5,
                close=1.5,
                volume=10,
            )
        ]

    def disconnect(self):
        pass


def _source(monkeypatch):
    monkeypatch.setattr(ibkr_source, "HAS_IB_INSYNC", True)
    src = ibkr_source.IBKRDataSource(host="example", port=4001, client_id=99)
    src.REQUEST_DELAY = 0
    src._ib = _FakeIB()
    src._connected = True
    monkeypatch.setattr(src, "_create_contract", lambda ticker: object())
    return src


def test_fetch_historical_intraday_uses_explicit_eastern_end_time(monkeypatch):
    src = _source(monkeypatch)

    src.fetch_historical_intraday(["AAPL"], date(2026, 6, 22), date(2026, 6, 22))

    assert src._ib.calls[0]["endDateTime"] == "20260622 23:59:59 US/Eastern"


def test_fetch_intraday_prices_uses_explicit_eastern_end_time(monkeypatch):
    src = _source(monkeypatch)

    src.fetch_intraday_prices("AAPL", date(2026, 6, 22))

    assert src._ib.calls[0]["endDateTime"] == "20260622 23:59:59 US/Eastern"
