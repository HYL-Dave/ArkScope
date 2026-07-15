from datetime import datetime, timezone
import sqlite3

import pytest

from src.news_normalized import models
from src.news_normalized.models import ArticleCandidate, BodyCandidate, BodyStatus
from src.news_normalized.store import NormalizedNewsStore


NOW = datetime(2026, 7, 15, 11, 30, tzinfo=timezone.utc)


def _open_store(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn, NormalizedNewsStore(conn)


def _seed(
    store: NormalizedNewsStore,
    label: str,
    *,
    published_at: str = "2026-07-01T00:00:00Z",
    provider_id: str | None = None,
    publisher: str = "DJ-N",
) -> int:
    result = store.upsert(
        ArticleCandidate(
            source="ibkr",
            provider_article_id=(
                provider_id if provider_id is not None else f"DJ-N${label}"
            ),
            title=f"Synthetic {label}",
            publisher=publisher,
            published_at=published_at,
            related_tickers=("AAPL",),
            body=BodyCandidate(status=BodyStatus.PENDING),
        )
    )
    assert result.article_id is not None
    return result.article_id


def _set_body(
    conn: sqlite3.Connection,
    article_id: int,
    *,
    status: str,
    attempts: int = 0,
    next_retry_at: str | None = None,
) -> None:
    conn.execute(
        "UPDATE news_article_bodies "
        "SET body_status=?,fetch_attempts=?,next_retry_at=? WHERE article_id=?",
        (status, attempts, next_retry_at, article_id),
    )
    conn.commit()


def test_ibkr_retry_selection_orders_due_pending_and_legacy(tmp_path):
    conn, store = _open_store(tmp_path / "news.db")
    try:
        legacy_null = _seed(store, "legacy-null")
        due = _seed(store, "due")
        legacy_malformed = _seed(store, "legacy-malformed")
        pending = _seed(store, "pending", published_at="2026-06-01T00:00:00Z")
        _set_body(conn, legacy_null, status="failed", attempts=1)
        _set_body(
            conn,
            due,
            status="failed",
            attempts=1,
            next_retry_at="2026-07-15T09:00:00Z",
        )
        _set_body(
            conn,
            legacy_malformed,
            status="failed",
            attempts=1,
            next_retry_at="not-a-time",
        )

        selection = store.select_ibkr_body_retries(now=NOW, limit=10)

        assert selection.article_ids == (
            due,
            pending,
            legacy_null,
            legacy_malformed,
        )
    finally:
        conn.close()


def test_ibkr_retry_selection_excludes_future_terminal_and_missing_identity(tmp_path):
    conn, store = _open_store(tmp_path / "news.db")
    try:
        eligible = _seed(store, "eligible")
        future = _seed(store, "future")
        _set_body(
            conn,
            future,
            status="failed",
            attempts=1,
            next_retry_at="2026-07-15T13:00:00Z",
        )
        for status in ("fetched", "empty", "unavailable", "expired"):
            terminal = _seed(store, f"terminal-{status}")
            _set_body(conn, terminal, status=status, attempts=1)
        _seed(store, "missing-provider", provider_id="")
        _seed(store, "missing-publisher", publisher="")

        selection = store.select_ibkr_body_retries(now=NOW, limit=50)

        assert selection.article_ids == (eligible,)
    finally:
        conn.close()


def test_ibkr_retry_selection_limit_does_not_truncate_backlog_counts(tmp_path):
    conn, store = _open_store(tmp_path / "news.db")
    try:
        for index in range(3):
            article_id = _seed(store, f"due-{index}")
            _set_body(
                conn,
                article_id,
                status="failed",
                attempts=1,
                next_retry_at=f"2026-07-15T0{index + 1}:00:00Z",
            )
        future = _seed(store, "future")
        _set_body(
            conn,
            future,
            status="failed",
            attempts=1,
            next_retry_at="2026-07-16T00:00:00Z",
        )

        selection = store.select_ibkr_body_retries(now=NOW, limit=1)

        assert len(selection.article_ids) == 1
        assert selection.backlog.due_now == 3
        assert selection.backlog.scheduled_later == 1
        assert store.select_ibkr_body_retries(now=NOW, limit=0).article_ids == ()
    finally:
        conn.close()


def test_ibkr_retry_backlog_reports_counts_and_earliest_retry(tmp_path):
    conn, store = _open_store(tmp_path / "news.db")
    try:
        explicit_due = _seed(store, "explicit-due")
        _set_body(
            conn,
            explicit_due,
            status="failed",
            attempts=1,
            next_retry_at="2026-07-15T11:00:00Z",
        )
        _seed(store, "never-attempted")
        legacy_due = _seed(store, "legacy-due")
        _set_body(
            conn,
            legacy_due,
            status="failed",
            attempts=1,
            next_retry_at="invalid",
        )
        for label, retry_at in (
            ("future-later", "2026-07-15T14:00:00Z"),
            ("future-earlier", "2026-07-15T12:00:00Z"),
        ):
            article_id = _seed(store, label)
            _set_body(
                conn,
                article_id,
                status="failed",
                attempts=1,
                next_retry_at=retry_at,
            )

        summary = store.summarize_ibkr_body_backlog(now=NOW)

        assert summary == models.BodyRetryBacklog(
            due_now=3,
            scheduled_later=2,
            never_attempted=1,
            earliest_next_retry_at="2026-07-15T12:00:00Z",
        )
    finally:
        conn.close()


def test_ibkr_retry_selection_survives_connection_reopen(tmp_path):
    path = tmp_path / "news.db"
    conn, store = _open_store(path)
    first_id = _seed(store, "first")
    second_id = _seed(store, "second")
    _set_body(
        conn,
        second_id,
        status="failed",
        attempts=1,
        next_retry_at="2026-07-16T00:00:00Z",
    )
    before = store.select_ibkr_body_retries(now=NOW, limit=10)
    conn.close()

    reopened, reopened_store = _open_store(path)
    try:
        after = reopened_store.select_ibkr_body_retries(now=NOW, limit=10)

        assert before == after
        assert after.article_ids == (first_id,)
    finally:
        reopened.close()


def test_ibkr_retry_selection_rejects_negative_limit_and_active_transaction(tmp_path):
    conn, store = _open_store(tmp_path / "news.db")
    try:
        with pytest.raises(ValueError, match="non-negative"):
            store.select_ibkr_body_retries(now=NOW, limit=-1)

        conn.execute("BEGIN")
        with pytest.raises(RuntimeError, match="transaction"):
            store.select_ibkr_body_retries(now=NOW, limit=1)
        assert conn.in_transaction is True
        conn.rollback()
    finally:
        conn.close()
