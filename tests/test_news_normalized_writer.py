from contextlib import contextmanager
import sqlite3

import pytest

from src.market_data_admin import (
    _NEWS_SCHEMA,
    _ensure_news_fts_triggers,
    _ensure_news_hash_unique,
)
from src.news_identity import canonical_article_hash
from src.news_normalized.models import (
    ArticleCandidate,
    BodyCandidate,
    BodyStatus,
    WriterBudget,
    WriterContinuation,
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

    def __init__(self, rows_by_ticker, *, body_errors=(), on_fetch_body=None):
        self.rows_by_ticker = rows_by_ticker
        self.body_errors = set(body_errors)
        self.on_fetch_body = on_fetch_body
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
        if self.on_fetch_body is not None:
            self.on_fetch_body(article)
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


def ensure_legacy_news_schema(conn):
    conn.executescript(_NEWS_SCHEMA)
    _ensure_news_hash_unique(conn)
    _ensure_news_fts_triggers(conn)
    conn.commit()


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


def test_writer_defers_failed_body_until_next_retry_at(store):
    article = candidate("p1")
    result = store.upsert(article)
    store.conn.execute(
        "UPDATE news_article_bodies SET body_status='failed',fetch_attempts=1,"
        "next_retry_at='2099-01-01T00:00:00Z' WHERE article_id=?",
        (result.article_id,),
    )
    provider = FakeProvider({})

    outcome = write_news_batch(
        store,
        provider,
        [],
        WriterBudget(max_articles=0, max_body_fetches=1),
        continuation=WriterContinuation(deferred_body_ids=("p1",)),
    )

    assert provider.body_calls == []
    assert outcome.status == "partial"
    assert outcome.continuation is not None
    assert outcome.continuation.deferred_body_ids == ("p1",)


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


def test_projection_enabled_writes_two_legacy_rows_and_counts_inserted(store):
    ensure_legacy_news_schema(store.conn)
    provider = FakeProvider(
        {
            "AAPL": [
                ArticleCandidate(
                    source="fakewire",
                    provider_article_id="p1",
                    title="Cross ticker story",
                    publisher="Fake Wire",
                    published_at="2026-06-27T10:00:01Z",
                    primary_ticker="AAPL",
                    related_tickers=("MSFT",),
                    content_kind="headline_only",
                )
            ]
        }
    )

    result = write_news_batch(
        store,
        provider,
        ["AAPL"],
        WriterBudget(max_articles=1, max_body_fetches=0),
        project_legacy=True,
    )

    assert result.status == "partial"
    assert result.articles_inserted == 1
    assert result.legacy_rows_inserted == 2
    assert result.legacy_rows_updated == 0
    assert result.projection_skipped_no_ticker == 0
    legacy_rows = store.conn.execute(
        "SELECT ticker,title,description,source FROM news ORDER BY ticker"
    ).fetchall()
    assert [tuple(row) for row in legacy_rows] == [
        ("AAPL", "Cross ticker story", "", "fakewire"),
        ("MSFT", "Cross ticker story", "", "fakewire"),
    ]
    assert store.conn.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0] == 1


def test_projection_enabled_counts_skipped_untickered_article(store):
    ensure_legacy_news_schema(store.conn)
    provider = FakeProvider(
        {
            "AAPL": [
                ArticleCandidate(
                    source="fakewire",
                    provider_article_id="p1",
                    title="Untickered story",
                    publisher="Fake Wire",
                    published_at="2026-06-27T10:00:01Z",
                    content_kind="headline_only",
                )
            ]
        }
    )

    result = write_news_batch(
        store,
        provider,
        ["AAPL"],
        WriterBudget(max_articles=1, max_body_fetches=0),
        project_legacy=True,
    )

    assert result.articles_inserted == 1
    assert result.legacy_rows_inserted == 0
    assert result.legacy_rows_updated == 0
    assert result.projection_skipped_no_ticker == 1
    assert store.conn.execute("SELECT COUNT(*) FROM news").fetchone()[0] == 0
    assert store.conn.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0] == 1


def test_projection_failure_is_atomic_for_normalized_and_legacy_rows(store):
    ensure_legacy_news_schema(store.conn)
    article = ArticleCandidate(
        source="fakewire",
        provider_article_id="p1",
        title="Conflicting projection story",
        publisher="Fake Wire",
        published_at="2026-06-27T10:00:01Z",
        primary_ticker="AAPL",
        related_tickers=("MSFT",),
        content_kind="headline_only",
    )
    conflicting_hash = canonical_article_hash(
        "MSFT", "Conflicting projection story", "2026-06-27T10:00:01Z"
    )
    store.conn.execute(
        "INSERT INTO news "
        "(ticker,title,description,url,publisher,source,published_at,article_hash) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (
            "TSLA",
            "Different owner",
            "legacy owner",
            "",
            "Other Wire",
            "fakewire",
            "2026-06-27T10:00:01+0000",
            conflicting_hash,
        ),
    )
    store.conn.commit()
    provider = FakeProvider({"AAPL": [article]})

    result = write_news_batch(
        store,
        provider,
        ["AAPL"],
        WriterBudget(max_articles=1, max_body_fetches=0),
        project_legacy=True,
    )

    assert result.status == "partial"
    assert result.articles_inserted == 0
    assert result.legacy_rows_inserted == 0
    assert "AAPL" in result.errors
    assert store.conn.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0] == 0
    projected_count = store.conn.execute(
        "SELECT COUNT(*) FROM news WHERE ticker IN ('AAPL','MSFT')"
    ).fetchone()[0]
    assert projected_count == 0
    assert store.conn.execute("SELECT COUNT(*) FROM news").fetchone()[0] == 1


def test_projection_disabled_leaves_legacy_news_empty(store):
    ensure_legacy_news_schema(store.conn)
    provider = FakeProvider({"AAPL": [candidate("p1")]})

    result = write_news_batch(
        store,
        provider,
        ["AAPL"],
        WriterBudget(max_articles=1, max_body_fetches=0),
        project_legacy=False,
    )

    assert result.articles_inserted == 1
    assert result.legacy_rows_inserted == 0
    assert result.legacy_rows_updated == 0
    assert result.projection_skipped_no_ticker == 0
    assert store.conn.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0] == 1
    assert store.conn.execute("SELECT COUNT(*) FROM news").fetchone()[0] == 0


def test_projection_body_fetch_refreshes_legacy_description_in_second_transaction(store):
    ensure_legacy_news_schema(store.conn)
    body_transactions = []
    provider = FakeProvider(
        {"AAPL": [candidate("p1")]},
        on_fetch_body=lambda _article: body_transactions.append(store.conn.in_transaction),
    )

    result = write_news_batch(
        store,
        provider,
        ["AAPL"],
        WriterBudget(max_articles=1, max_body_fetches=1),
        project_legacy=True,
    )

    assert body_transactions == [False]
    assert result.status == "succeeded"
    assert result.bodies_fetched == 1
    assert result.legacy_rows_inserted == 1
    assert result.legacy_rows_updated == 1
    description = store.conn.execute("SELECT description FROM news").fetchone()[0]
    assert description == "Body p1"


def test_projection_body_fetch_failure_preserves_committed_metadata_projection(store):
    ensure_legacy_news_schema(store.conn)
    provider = FakeProvider({"AAPL": [candidate("p1")]}, body_errors={"p1"})

    result = write_news_batch(
        store,
        provider,
        ["AAPL"],
        WriterBudget(max_articles=1, max_body_fetches=1),
        project_legacy=True,
    )

    assert result.status == "partial"
    assert result.errors == {"body:p1": "body unavailable"}
    assert result.articles_inserted == 1
    assert result.legacy_rows_inserted == 1
    assert result.legacy_rows_updated == 0
    assert store.conn.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0] == 1
    legacy = store.conn.execute(
        "SELECT ticker,title,description FROM news"
    ).fetchone()
    assert tuple(legacy) == ("AAPL", "Story p1", "")
    assert (
        store.candidate_by_provider_id("fakewire", "p1").body.status
        is BodyStatus.FAILED
    )


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
