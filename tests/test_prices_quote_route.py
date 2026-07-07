from src.api.routes import prices as route
from src.tools.schemas import CurrentQuoteResult


def test_quote_route_returns_model_dump(monkeypatch):
    seen = {}

    def fake_quote(dal, ticker, source="auto"):
        seen.update({"dal": dal, "ticker": ticker, "source": source})
        return CurrentQuoteResult(
            ticker="NVDA",
            provider="ibkr",
            mode="ibkr_snapshot",
            price=123.45,
            source_note="fake",
        )

    monkeypatch.setattr(route, "get_current_quote", fake_quote)

    out = route.current_quote("nvda", source="ibkr", dal=object())

    assert seen["ticker"] == "nvda"
    assert seen["source"] == "ibkr"
    assert out["ticker"] == "NVDA"
    assert out["mode"] == "ibkr_snapshot"
    assert out["price"] == 123.45
