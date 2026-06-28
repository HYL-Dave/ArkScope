from contextlib import contextmanager
import sqlite3

import pytest

from src.news_normalized.models import (
    ArticleCandidate,
    BodyCandidate,
    BodyStatus,
    WriterBudget,
)
from src.news_normalized.store import NormalizedNewsStore
from src.news_normalized.writer import write_news_batch


def candidate(provider_id: str, *, ticker: str = "AAPL") -> ArticleCandidate:
    return ArticleCandidate(
        source="fakewire",
        provider_article_id=provider_id,
        title=f"Story {provider_id}",
        publisher="Fake Wire",
        published_at=f"2026-06-27T10:00:{int(provider_id[1:]):02d}Z",
        primary_ticker=ticker,
        related_tickers=(ticker,),
        content_kind="full_text",
    )


class FakeProvider:
    source = "fakewire"

    def __init__(self, rows_by_ticker, *, body_errors=()):
        self.rows_by_ticker = rows_by_ticker
        self.body_errors = set(body_errors)
        self.events = []
        self.body_calls = []

    @contextmanager
    def operation(self):
        self.events.append("operation:enter")
        try:
            yield
        finally:
            self.events.append("operation:exit")

    def fetch_articles(self, ticker, since_iso):
        self.events.append(f"metadata:{ticker}:{since_iso}")
        value = self.rows_by_ticker[ticker]
        if isinstance(value, Exception):
            raise value
        return list(value)

    def fetch_body(self, article):
        self.events.append(f"body:{article.provider_article_id}")
        self.body_calls.append(article.provider_article_id)
        if article.provider_article_id in self.body_errors:
            raise RuntimeError("body unavailable")
        return BodyCandidate(
            status=BodyStatus.FETCHED,
            raw_body=f"<p>Body {article.provider_article_id}</p>",
            raw_format="html",
            retrieval_method="provider_api",
            retrieval_source=self.source,
        )


@pytest.fixture
def store():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    yield NormalizedNewsStore(conn)
    conn.close()


def test_writer_stores_all_metadata_when_body_budget_is_exhausted(store):
    provider = FakeProvider({"AAPL": [candidate("p1"), candidate("p2")]})

    result = write_news_batch(
        store,
        provider,
        tickers=["AAPL"],
        budget=WriterBudget(max_articles=2, max_body_fetches=1),
    )

    assert result.status == "partial"
    assert result.articles_seen == 2
    assert result.articles_inserted == 2
    assert result.bodies_fetched == 1
    assert result.continuation is not None
    assert result.continuation.deferred_body_ids == ("p2",)
    assert store.conn.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0] == 2
    assert store.conn.execute(
        "SELECT COUNT(*) FROM news_article_bodies WHERE body_status='fetched'"
    ).fetchone()[0] == 1
    assert store.conn.execute(
        "SELECT COUNT(*) FROM news_articles_fts WHERE news_articles_fts MATCH 'Body'"
    ).fetchone()[0] == 1


def test_writer_resumes_saved_bodies_before_fetching_new_metadata(store):
    provider = FakeProvider({"AAPL": [candidate("p1")]})
    first = write_news_batch(
        store,
        provider,
        ["AAPL"],
        WriterBudget(max_articles=1, max_body_fetches=0),
    )
    provider.events.clear()

    second = write_news_batch(
        store,
        provider,
        ["SHOULD_NOT_RUN"],
        WriterBudget(max_articles=0, max_body_fetches=1),
        continuation=first.continuation,
    )

    assert second.status == "succeeded"
    assert second.continuation is None
    assert provider.events == ["operation:enter", "body:p1", "operation:exit"]


def test_writer_rerun_is_idempotent_and_does_not_refetch_terminal_body(store):
    provider = FakeProvider({"AAPL": [candidate("p1")]})

    first = write_news_batch(
        store, provider, ["AAPL"], WriterBudget(max_articles=10, max_body_fetches=10)
    )
    second = write_news_batch(
        store, provider, ["AAPL"], WriterBudget(max_articles=10, max_body_fetches=10)
    )

    assert first.articles_inserted == 1
    assert second.articles_inserted == 0
    assert second.continuation is None
    assert provider.body_calls == ["p1"]


def test_writer_carries_deferred_tickers_when_article_budget_is_hit(store):
    provider = FakeProvider(
        {
            "AAPL": [candidate("p1"), candidate("p2")],
            "MSFT": [candidate("p3", ticker="MSFT")],
        }
    )

    result = write_news_batch(
        store,
        provider,
        ["AAPL", "MSFT"],
        WriterBudget(max_articles=1, max_body_fetches=0),
    )

    assert result.status == "partial"
    assert result.continuation is not None
    assert result.continuation.deferred_tickers == ("AAPL", "MSFT")
    assert result.continuation.deferred_body_ids == ("p1",)


def test_writer_isolates_ticker_failures_and_records_local_telemetry(store):
    provider = FakeProvider(
        {
            "AAPL": [candidate("p1")],
            "FAIL": RuntimeError("provider unavailable"),
        }
    )

    result = write_news_batch(
        store,
        provider,
        ["AAPL", "FAIL"],
        WriterBudget(max_articles=10, max_body_fetches=10),
    )

    assert result.status == "partial"
    assert result.errors == {"FAIL": "provider unavailable"}
    rows = store.conn.execute(
        "SELECT ticker,last_error FROM provider_sync_meta "
        "WHERE provider='fakewire' AND interval='news' ORDER BY ticker"
    ).fetchall()
    assert [tuple(row) for row in rows] == [
        ("AAPL", None),
        ("FAIL", "provider unavailable"),
    ]
    run = store.conn.execute(
        "SELECT domain,status,tickers_scanned,rows_added FROM provider_sync_runs"
    ).fetchone()
    assert tuple(run) == ("news", "succeeded", 2, 1)


def test_writer_body_failure_is_resumable_and_visible_in_ticker_telemetry(store):
    provider = FakeProvider({"AAPL": [candidate("p1")]}, body_errors={"p1"})

    result = write_news_batch(
        store,
        provider,
        ["AAPL"],
        WriterBudget(max_articles=10, max_body_fetches=1),
    )

    assert result.status == "partial"
    assert result.errors == {"body:p1": "body unavailable"}
    assert result.continuation is not None
    assert result.continuation.deferred_body_ids == ("p1",)
    assert store.candidate_by_provider_id("fakewire", "p1").body.status is BodyStatus.FAILED
    meta = store.conn.execute(
        "SELECT last_error FROM provider_sync_meta "
        "WHERE provider='fakewire' AND ticker='AAPL' AND interval='news'"
    ).fetchone()
    assert meta[0] == "body unavailable"


def test_writer_resumed_body_failure_updates_original_ticker_telemetry(store):
    provider = FakeProvider({"AAPL": [candidate("p1")]})
    first = write_news_batch(
        store,
        provider,
        ["AAPL"],
        WriterBudget(max_articles=10, max_body_fetches=0),
    )
    provider.body_errors.add("p1")

    result = write_news_batch(
        store,
        provider,
        [],
        WriterBudget(max_articles=0, max_body_fetches=1),
        continuation=first.continuation,
    )

    assert result.status == "partial"
    meta = store.conn.execute(
        "SELECT last_error FROM provider_sync_meta "
        "WHERE provider='fakewire' AND ticker='AAPL' AND interval='news'"
    ).fetchone()
    assert meta[0] == "body unavailable"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_articles": -1, "max_body_fetches": 0},
        {"max_articles": 0, "max_body_fetches": -1},
    ],
)
def test_writer_budget_rejects_negative_values(kwargs):
    with pytest.raises(ValueError):
        WriterBudget(**kwargs)
