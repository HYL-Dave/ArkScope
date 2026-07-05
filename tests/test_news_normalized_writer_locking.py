import sqlite3
from contextlib import contextmanager

import pytest

from src.news_normalized.models import (
    ArticleCandidate,
    BodyCandidate,
    BodyStatus,
    WriterBudget,
)
from src.news_normalized.store import NormalizedNewsStore
from src.news_normalized.writer import write_news_batch


class _FakeProvider:
    source = "polygon"

    def __init__(self, lock_state, events):
        self._lock_state = lock_state
        self._events = events

    def fetch_articles(self, ticker, since):
        self._events.append(("fetch_articles", ticker, self._lock_state["held"]))
        assert self._lock_state["held"] is False
        return [
            ArticleCandidate(
                source="polygon",
                provider_article_id=f"{ticker}-1",
                title=f"{ticker} headline",
                url=f"https://example.test/{ticker}/1",
                published_at="2026-07-05T12:00:00Z",
                primary_ticker=ticker,
                related_tickers=(ticker,),
                body=BodyCandidate(status=BodyStatus.PENDING),
            )
        ]

    def fetch_body(self, candidate):
        self._events.append(("fetch_body", candidate.provider_article_id, self._lock_state["held"]))
        assert self._lock_state["held"] is False
        return BodyCandidate(status=BodyStatus.FETCHED, raw_body="<p>body</p>", raw_format="html")


@contextmanager
def _tracking_lock(lock_state, events):
    assert lock_state["held"] is False
    lock_state["held"] = True
    events.append(("lock_enter", None, True))
    try:
        yield
    finally:
        events.append(("lock_exit", None, True))
        lock_state["held"] = False


def test_write_news_batch_fetches_outside_injected_write_lock(tmp_path):
    db = tmp_path / "market_data.db"
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    store = NormalizedNewsStore(conn)
    lock_state = {"held": False}
    events = []

    result = write_news_batch(
        store,
        _FakeProvider(lock_state, events),
        ["AAPL"],
        WriterBudget(max_articles=10, max_body_fetches=10),
        project_legacy=False,
        write_lock_factory=lambda: _tracking_lock(lock_state, events),
    )

    conn.close()
    assert result.status == "succeeded"
    assert ("fetch_articles", "AAPL", False) in events
    assert ("fetch_body", "AAPL-1", False) in events
    assert any(event[0] == "lock_enter" for event in events)


class _OneArticleProvider:
    source = "polygon"

    def fetch_articles(self, ticker, since):
        return [
            ArticleCandidate(
                source="polygon",
                provider_article_id=f"{ticker}-1",
                title=f"{ticker} headline",
                url=f"https://example.test/{ticker}/1",
                published_at="2026-07-05T12:00:00Z",
                primary_ticker=ticker,
                related_tickers=(ticker,),
                body=BodyCandidate(status=BodyStatus.PENDING),
            )
        ]

    def fetch_body(self, candidate):
        return BodyCandidate(status=BodyStatus.FETCHED, raw_body="<p>body</p>", raw_format="html")


def _flaky_lock_factory(busy_calls):
    """Succeed on every acquisition except the given 1-based call numbers, which
    raise the exact market_write_lock contention error."""
    calls = {"n": 0}

    @contextmanager
    def factory():
        calls["n"] += 1
        if calls["n"] in busy_calls:
            raise TimeoutError("market_data.db write lock busy (timeout)")
        yield

    return factory


def _store(tmp_path):
    conn = sqlite3.connect(tmp_path / "market_data.db")
    conn.row_factory = sqlite3.Row
    return conn, NormalizedNewsStore(conn)


def test_lock_busy_during_article_upsert_aborts_batch(tmp_path):
    """Write-phase lock contention must raise so run_source classifies it as a
    retryable skipped_lock_busy — never be swallowed into per-article errors as
    a durable partial result (P1: reviewer repro 2026-07-05)."""
    conn, store = _store(tmp_path)
    # acquisition 1 = run-start telemetry, acquisition 2 = first article upsert
    with pytest.raises(TimeoutError, match="market_data.db write lock busy"):
        write_news_batch(
            store,
            _OneArticleProvider(),
            ["AAPL"],
            WriterBudget(max_articles=10, max_body_fetches=10),
            project_legacy=True,
            write_lock_factory=_flaky_lock_factory({2}),
        )
    conn.close()


def test_lock_busy_during_body_update_aborts_batch(tmp_path):
    conn, store = _store(tmp_path)
    # acquisition 1 = run-start, 2 = article upsert, 3 = body update
    with pytest.raises(TimeoutError, match="market_data.db write lock busy"):
        write_news_batch(
            store,
            _OneArticleProvider(),
            ["AAPL"],
            WriterBudget(max_articles=10, max_body_fetches=10),
            project_legacy=False,
            write_lock_factory=_flaky_lock_factory({3}),
        )
    conn.close()


def test_lock_busy_during_deferred_body_resume_aborts_batch(tmp_path):
    conn, store = _store(tmp_path)
    first = write_news_batch(
        store,
        _OneArticleProvider(),
        ["AAPL"],
        WriterBudget(max_articles=10, max_body_fetches=0),
        project_legacy=False,
        write_lock_factory=_flaky_lock_factory(set()),
    )
    assert first.continuation is not None
    assert first.continuation.deferred_body_ids == ("AAPL-1",)

    # resume run: acquisition 1 = run-start, 2 = deferred body update
    with pytest.raises(TimeoutError, match="market_data.db write lock busy"):
        write_news_batch(
            store,
            _OneArticleProvider(),
            [],
            WriterBudget(max_articles=10, max_body_fetches=10),
            continuation=first.continuation,
            project_legacy=False,
            write_lock_factory=_flaky_lock_factory({2}),
        )
    conn.close()
