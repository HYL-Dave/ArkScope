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
