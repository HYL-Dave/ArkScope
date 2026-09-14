"""Request-target contracts across direct, normalized REST, and strict IBKR."""

from contextlib import closing
from datetime import date, datetime, timedelta, timezone
import sqlite3
from types import SimpleNamespace

import pytest

from src import news_providers
from src.news_normalized import ibkr_runtime, provider_adapters


NOW = datetime(2026, 9, 14, 12, 34, 56, tzinfo=timezone.utc)
ROUTES = (
    "direct-polygon",
    "direct-finnhub",
    "normalized-polygon",
    "normalized-finnhub",
    "ibkr",
)


class FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)


class Collector:
    def __init__(self):
        self.calls = []

    def fetch_news_range(self, ticker, start, end, **kwargs):
        self.calls.append({"ticker": ticker, "start": start, "end": end, **kwargs})
        return [{"ticker": ticker}]

    def fetch_news(self, ticker, start, end):
        return self.fetch_news_range(ticker, start, end)

    def parse_article(self, raw, *args):
        return SimpleNamespace(
            article_id=f"{raw['ticker']}-1",
            ticker=raw["ticker"],
            title=f"{raw['ticker']} reports results",
            published_at="2026-09-13T10:00:00Z",
            description="Reported revenue",
            content="",
            url=f"https://example.test/news/{raw['ticker']}/1",
            publisher="Provider",
        )


class StrictIBKRSource:
    def __init__(self):
        self.calls = []
        self.has_more = False
        self.published_at = "2026-09-13T10:00:00Z"

    def get_news_providers_strict(self):
        return [{"code": "BZ"}]

    def fetch_news_page_strict(self, ticker, **kwargs):
        self.calls.append({"ticker": ticker, **kwargs})
        return SimpleNamespace(
            has_more=self.has_more,
            articles=[SimpleNamespace(
                source="BZ",
                description="[Article ID: BZ$1]",
                ticker=ticker,
                title="Company reports results",
                published_date=self.published_at,
            )],
        )


def _adapter(route, monkeypatch):
    monkeypatch.setattr(news_providers, "datetime", FrozenDatetime)
    monkeypatch.setattr(ibkr_runtime, "datetime", FrozenDatetime)
    if route == "ibkr":
        source = StrictIBKRSource()
        gateway = ibkr_runtime.IBKRRuntimeGateway(source)
        return gateway.fetch_headlines, source.calls
    lane, source = route.split("-")
    collector = Collector()
    if lane == "direct":
        provider = news_providers.make_news_provider(source, collector=collector)
        return provider.fetch_news, collector.calls
    cls = (provider_adapters.PolygonNormalizedProvider if source == "polygon"
           else provider_adapters.FinnhubNormalizedProvider)
    provider = cls(collector, now_fn=lambda: NOW)
    return provider.fetch_articles, collector.calls


def _assert_window(route, call, start):
    if route == "ibkr":
        assert call["start_dt"] == start
        assert call["end_dt"] == NOW
    else:
        assert call["start"] == start.date()
        assert call["end"] == NOW.date()


@pytest.mark.parametrize("route", ROUTES)
def test_new_source_ticker_requests_fourteen_days(route, monkeypatch):
    fetch, calls = _adapter(route, monkeypatch)
    rows = list(fetch("AAPL", None))
    assert len(rows) == 1
    assert len(calls) == 1
    assert calls[0]["ticker"] == "AAPL"
    _assert_window(
        route, calls[0], datetime(2026, 8, 31, 12, 34, 56, tzinfo=timezone.utc)
    )


@pytest.mark.parametrize("route", ROUTES)
def test_all_adapters_consult_shared_policy_at_request_time(route, monkeypatch):
    from src import news_collection_policy

    fetch, calls = _adapter(route, monkeypatch)
    assert news_collection_policy.INITIAL_NEWS_LOOKBACK == timedelta(days=14)
    monkeypatch.setattr(
        news_collection_policy, "INITIAL_NEWS_LOOKBACK", timedelta(days=3)
    )
    assert len(list(fetch("AAPL", None))) == 1
    _assert_window(
        route, calls[0], datetime(2026, 9, 11, 12, 34, 56, tzinfo=timezone.utc)
    )


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("cursor", ["", "not-a-date", "2026-02-30T00:00:00Z"])
def test_unusable_cursor_uses_the_shared_initial_target(route, cursor, monkeypatch):
    fetch, calls = _adapter(route, monkeypatch)
    assert len(list(fetch("AAPL", cursor))) == 1
    _assert_window(
        route, calls[0], datetime(2026, 8, 31, 12, 34, 56, tzinfo=timezone.utc)
    )


@pytest.mark.parametrize("route", ROUTES)
@pytest.mark.parametrize("cursor", [
    "2026-09-12T20:30:00+08:00",
    "2026-07-01T08:30:15Z",
    "2026-09-12",
])
def test_saved_cursor_is_not_replaced_or_clamped_to_initial_target(
    route, cursor, monkeypatch,
):
    fetch, calls = _adapter(route, monkeypatch)
    assert len(list(fetch("AAPL", cursor))) == 1
    parsed = datetime.fromisoformat(cursor.replace("Z", "+00:00"))
    expected = (parsed.astimezone(timezone.utc) if parsed.tzinfo
                else parsed.replace(tzinfo=timezone.utc))
    _assert_window(route, calls[0], expected)
    if route == "normalized-polygon":
        assert calls[0]["start_timestamp"] == parsed


@pytest.mark.parametrize("source", ["polygon", "finnhub"])
def test_direct_writer_bootstraps_new_ticker_and_source_without_losing_dedup(
    source, tmp_path, monkeypatch,
):
    from src.news_direct import backfill_news_direct

    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))
    monkeypatch.setattr(news_providers, "datetime", FrozenDatetime)
    db = str(tmp_path / "news.db")
    collector = Collector()
    provider = news_providers.make_news_provider(source, collector=collector)

    first = backfill_news_direct(["AAPL"], source=source, provider=provider, db_path=db)
    second = backfill_news_direct(
        ["AAPL", "MSFT"], source=source, provider=provider, db_path=db,
    )
    assert first["errors"] == second["errors"] == {}
    assert first["articles_added"] == second["articles_added"] == 1
    assert [(call["ticker"], call["start"]) for call in collector.calls] == [
        ("AAPL", date(2026, 8, 31)),
        ("AAPL", date(2026, 9, 13)),
        ("MSFT", date(2026, 8, 31)),
    ]
    with closing(sqlite3.connect(db)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM news").fetchone()[0] == 2

    other_source = "finnhub" if source == "polygon" else "polygon"
    other_collector = Collector()
    result = backfill_news_direct(
        ["AAPL"], source=other_source, db_path=db,
        provider=news_providers.make_news_provider(other_source, collector=other_collector),
    )
    assert result["errors"] == {}
    assert other_collector.calls[0]["start"] == date(2026, 8, 31)


@pytest.mark.parametrize("source", ["polygon", "finnhub"])
def test_normalized_writer_bootstraps_new_ticker_and_source_without_losing_dedup(
    source,
):
    from src.news_normalized.models import WriterBudget
    from src.news_normalized.store import NormalizedNewsStore
    from src.news_normalized.writer import write_news_batch

    classes = {
        "polygon": provider_adapters.PolygonNormalizedProvider,
        "finnhub": provider_adapters.FinnhubNormalizedProvider,
    }
    collector = Collector()
    provider = classes[source](collector, now_fn=lambda: NOW)
    budget = WriterBudget(max_articles=10, max_body_fetches=10)
    with closing(sqlite3.connect(":memory:")) as conn:
        conn.row_factory = sqlite3.Row
        store = NormalizedNewsStore(conn)
        first = write_news_batch(store, provider, ["AAPL"], budget)
        second = write_news_batch(store, provider, ["AAPL", "MSFT"], budget)
        assert first.status == second.status == "succeeded"
        assert first.articles_inserted == second.articles_inserted == 1
        assert [(call["ticker"], call["start"]) for call in collector.calls] == [
            ("AAPL", date(2026, 8, 31)),
            ("AAPL", date(2026, 9, 13)),
            ("MSFT", date(2026, 8, 31)),
        ]
        assert conn.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0] == 2
        other_source = "finnhub" if source == "polygon" else "polygon"
        other_collector = Collector()
        result = write_news_batch(
            store, classes[other_source](other_collector, now_fn=lambda: NOW),
            ["AAPL"], budget,
        )
        assert result.status == "succeeded"
        assert other_collector.calls[0]["start"] == date(2026, 8, 31)


@pytest.mark.parametrize("has_more, error", [
    (True, "ibkr_news_window_incomplete"),
    (None, "ibkr_news_completion_unknown"),
])
def test_ibkr_seven_day_response_does_not_prove_fourteen_day_completion(
    has_more, error, monkeypatch,
):
    monkeypatch.setattr(ibkr_runtime, "datetime", FrozenDatetime)
    source = StrictIBKRSource()
    source.has_more = has_more
    source.published_at = "2026-09-07T12:34:56Z"
    gateway = ibkr_runtime.IBKRRuntimeGateway(source)
    assert gateway.discover_news_provider_codes() == frozenset({"BZ"})
    rows = gateway.fetch_headlines("AAPL", None)
    assert next(rows).article_id == "BZ$1"
    with pytest.raises(ibkr_runtime.IBKRNewsCoverageIncomplete, match=f"^{error}$"):
        next(rows)
    assert len(source.calls) == 1
    assert source.calls[0]["providers"] == "BZ"
    assert gateway.headline_coverage_counts() == {
        "headline_pages_requested": 1,
        "headline_saturated_tickers": int(has_more is True),
        "headline_incomplete_tickers": 1,
    }


def test_ibkr_no_entitled_providers_does_not_request_the_larger_window(monkeypatch):
    source = StrictIBKRSource()
    monkeypatch.setattr(source, "get_news_providers_strict", lambda: [])
    gateway = ibkr_runtime.IBKRRuntimeGateway(source)
    assert gateway.discover_news_provider_codes() == frozenset()
    assert list(gateway.fetch_headlines("AAPL", None)) == []
    assert source.calls == []


def test_non_strict_ibkr_fallback_remains_source_owned():
    calls = []

    class Source:
        def fetch_news(self, tickers, **kwargs):
            calls.append((tickers, kwargs))
            return []

    gateway = ibkr_runtime.IBKRRuntimeGateway(Source())
    assert list(gateway.fetch_headlines("AAPL", None)) == []
    assert list(gateway.fetch_headlines("AAPL", "2026-07-01T08:30:15Z")) == []
    assert [call[1]["start_date"] for call in calls] == [None, date(2026, 7, 1)]
