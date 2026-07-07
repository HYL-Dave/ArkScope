from types import SimpleNamespace

from src.tools.current_quote import get_current_quote


class _FakeDAL:
    def __init__(self, bars):
        self._bars = bars
        self.calls = []

    def get_prices(self, ticker, interval="15min", days=30):
        self.calls.append((ticker, interval, days))
        return SimpleNamespace(
            ticker=ticker.upper(),
            interval=interval,
            count=len(self._bars),
            bars=self._bars,
        )


def _bar(ts="2026-07-07T14:45:00+00:00", close=123.45):
    return SimpleNamespace(
        datetime=ts,
        close=close,
        open=120.0,
        high=124.0,
        low=119.5,
        volume=1000,
    )


def test_local_quote_returns_explicit_last_bar():
    dal = _FakeDAL([_bar()])

    result = get_current_quote(dal, "nvda", source="local")

    assert result.ticker == "NVDA"
    assert result.provider == "local"
    assert result.mode == "local_last_bar"
    assert result.price == 123.45
    assert result.close == 123.45
    assert result.timestamp == "2026-07-07T14:45:00+00:00"
    assert result.stale is True
    assert "last stored bar" in result.source_note
    assert dal.calls == [("NVDA", "15min", 10)]


def test_local_quote_unavailable_when_no_bars():
    result = get_current_quote(_FakeDAL([]), "MSFT", source="local")

    assert result.ticker == "MSFT"
    assert result.provider == "local"
    assert result.mode == "unavailable"
    assert result.price is None
    assert result.error == "no_local_price_bars"


def test_ibkr_quote_uses_quotes_client_id_and_disconnects(monkeypatch):
    import src.tools.current_quote as mod

    seen = {}

    class _FakeIBKR:
        def __init__(self, **kwargs):
            seen["init"] = kwargs

        def connect(self):
            seen["connected"] = True

        def get_current_quote(self, ticker):
            seen["ticker"] = ticker
            return {
                "bid": 100.0,
                "ask": 102.0,
                "last": 101.25,
                "close": 99.5,
                "volume": 1234,
            }

        def disconnect(self):
            seen["disconnected"] = True

    monkeypatch.setattr(
        "data_sources.ibkr_client_id.ibkr_client_id_for",
        lambda domain: 606 if domain == "quotes" else -1,
    )
    monkeypatch.setattr("data_sources.ibkr_source.IBKRDataSource", _FakeIBKR)

    result = mod.get_current_quote(_FakeDAL([]), "aapl", source="ibkr")

    assert seen["init"] == {"client_id": 606, "readonly": True}
    assert seen["connected"] is True
    assert seen["ticker"] == "AAPL"
    assert seen["disconnected"] is True
    assert result.provider == "ibkr"
    assert result.mode == "ibkr_snapshot"
    assert result.price == 101.25
    assert result.bid == 100.0
    assert result.ask == 102.0
    assert result.volume == 1234


def test_auto_falls_back_to_local_when_ibkr_unavailable(monkeypatch):
    import src.tools.current_quote as mod

    monkeypatch.setattr(
        mod,
        "_fetch_ibkr_quote",
        lambda ticker: (_ for _ in ()).throw(RuntimeError("gateway down")),
    )

    result = mod.get_current_quote(_FakeDAL([_bar(close=88.0)]), "aapl", source="auto")

    assert result.provider == "local"
    assert result.mode == "local_last_bar"
    assert result.price == 88.0
    assert "ibkr_quote_failed" in result.source_note


def test_strict_ibkr_does_not_fallback(monkeypatch):
    import src.tools.current_quote as mod

    monkeypatch.setattr(
        mod,
        "_fetch_ibkr_quote",
        lambda ticker: (_ for _ in ()).throw(RuntimeError("gateway down")),
    )

    result = mod.get_current_quote(_FakeDAL([_bar(close=88.0)]), "aapl", source="ibkr")

    assert result.provider == "ibkr"
    assert result.mode == "unavailable"
    assert result.price is None
    assert result.error == "ibkr_quote_failed:RuntimeError"
