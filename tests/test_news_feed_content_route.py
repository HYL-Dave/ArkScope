from __future__ import annotations

from pathlib import Path

from src.api.routes.news import news_feed
from src.tools.backends.db_backend import DatabaseBackend
from src.tools.backends.local_market_backend import LocalMarketDatabaseBackend


def _empty_feed(*, available: bool = True) -> dict:
    return {
        "available": available,
        "items": [],
        "total": 0,
        "sources": {},
        "days": {},
        "content_counts": {
            "full": 0,
            "headline_only": 0,
            "unknown": 0,
        },
    }


def test_news_feed_route_forwards_content_to_dal() -> None:
    class Dal:
        kwargs: dict | None = None

        def get_news_feed(self, **kwargs):
            self.kwargs = kwargs
            return _empty_feed()

    dal = Dal()

    result = news_feed(
        q="earnings",
        ticker="NVDA",
        source="finnhub",
        content="headline_only",
        days=30,
        limit=25,
        offset=5,
        dal=dal,
    )

    assert result == _empty_feed()
    assert dal.kwargs == {
        "q": "earnings",
        "ticker": "NVDA",
        "source": "finnhub",
        "content": "headline_only",
        "days": 30,
        "limit": 25,
        "offset": 5,
    }


def test_local_backend_propagates_content_without_postgres_fallback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    backend = LocalMarketDatabaseBackend(
        "postgresql://poisoned/arkscope",
        market_db=str(tmp_path / "market.db"),
        strict=True,
    )
    recorded: dict = {}

    def local_feed(**kwargs):
        recorded.update(kwargs)
        return _empty_feed()

    def pg_boom(self, **kwargs):
        raise AssertionError("PostgreSQL fallback called")

    monkeypatch.setattr(backend._market, "query_news_feed", local_feed)
    monkeypatch.setattr(DatabaseBackend, "query_news_feed", pg_boom)

    result = backend.query_news_feed(
        q="apple",
        ticker="AAPL",
        source="polygon",
        content="headline_only",
        days=7,
        limit=10,
        offset=2,
    )

    assert result == _empty_feed()
    assert recorded == {
        "q": "apple",
        "ticker": "AAPL",
        "source": "polygon",
        "content": "headline_only",
        "days": 7,
        "limit": 10,
        "offset": 2,
    }
