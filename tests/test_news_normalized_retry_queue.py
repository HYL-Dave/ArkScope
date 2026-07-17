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
    last_attempt_at: str | None = None,
    last_error: str | None = None,
    last_error_code: int | None = None,
    unavailable_at: str | None = None,
) -> None:
    conn.execute(
        "UPDATE news_article_bodies "
        "SET body_status=?,fetch_attempts=?,next_retry_at=?,last_attempt_at=?,"
        "last_error=?,last_error_code=?,unavailable_at=? WHERE article_id=?",
        (
            status,
            attempts,
            next_retry_at,
            last_attempt_at,
            last_error,
            last_error_code,
            unavailable_at,
            article_id,
        ),
    )
    conn.commit()


def _body_row(conn: sqlite3.Connection, article_id: int) -> dict:
    row = conn.execute(
        "SELECT * FROM news_article_bodies WHERE article_id=?",
        (article_id,),
    ).fetchone()
    assert row is not None
    return dict(row)


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


def test_reconcile_ibkr_10172_policy_terminalizes_matching_rows_and_preserves_evidence(
    tmp_path,
):
    conn, store = _open_store(tmp_path / "news.db")
    try:
        article_id = _seed(store, "matching")
        _set_body(
            conn,
            article_id,
            status="failed",
            attempts=2,
            next_retry_at="2026-07-15T09:00:00Z",
            last_attempt_at="2026-07-15T03:00:00Z",
            last_error="IBKR news article unavailable (10172)",
            last_error_code=10172,
        )
        conn.execute(
            "UPDATE news_article_bodies SET raw_body=?,raw_ref=?,raw_format=?,"
            "body_text=?,body_sha256=?,cleaner_version=?,retrieval_method=?,"
            "retrieval_source=?,source_url=?,fetched_at=?,cleaned_at=?,clean_error=? "
            "WHERE article_id=?",
            (
                "protected raw",
                "protected-ref",
                "text",
                "protected clean",
                "a" * 64,
                "v-test",
                "provider_api",
                "ibkr",
                "https://example.test/protected",
                "2026-07-15T02:00:00Z",
                "2026-07-15T02:01:00Z",
                "protected-clean-error",
                article_id,
            ),
        )
        conn.commit()
        article_before = dict(
            conn.execute(
                "SELECT * FROM news_articles WHERE id=?",
                (article_id,),
            ).fetchone()
        )
        body_before = _body_row(conn, article_id)

        changed = store.reconcile_ibkr_10172_retry_policy(
            now=NOW,
            available_provider_codes=frozenset({"DJ-N"}),
        )

        article_after = dict(
            conn.execute(
                "SELECT * FROM news_articles WHERE id=?",
                (article_id,),
            ).fetchone()
        )
        body_after = _body_row(conn, article_id)
        expected_body = {
            **body_before,
            "body_status": "unavailable",
            "next_retry_at": None,
            "unavailable_at": "2026-07-15T03:00:00Z",
        }
        assert changed == 1
        assert article_after == article_before
        assert body_after == expected_body
    finally:
        conn.close()


def test_reconcile_ibkr_10172_policy_ignores_other_states_sources_and_entitlement(
    tmp_path,
):
    conn, store = _open_store(tmp_path / "news.db")
    try:
        blocked = _seed(
            store,
            "blocked",
            provider_id="FLY$blocked",
            publisher="FLY",
        )
        polygon = store.upsert(
            ArticleCandidate(
                source="polygon",
                provider_article_id="polygon-typed",
                title="Synthetic polygon typed",
                publisher="DJ-N",
                published_at="2026-07-01T00:00:00Z",
                related_tickers=("AAPL",),
                body=BodyCandidate(status=BodyStatus.PENDING),
            )
        ).article_id
        generic = _seed(store, "generic")
        first_attempt = _seed(store, "first-attempt")
        pending = _seed(store, "pending")
        fetched = _seed(store, "fetched")
        terminal = _seed(store, "terminal")
        assert polygon is not None

        for article_id in (blocked, polygon):
            _set_body(
                conn,
                article_id,
                status="failed",
                attempts=2,
                next_retry_at="2026-07-15T09:00:00Z",
                last_attempt_at="2026-07-15T03:00:00Z",
                last_error="IBKR news article unavailable (10172)",
                last_error_code=10172,
            )
        _set_body(
            conn,
            generic,
            status="failed",
            attempts=3,
            next_retry_at="2026-07-15T09:00:00Z",
            last_error="generic provider failure",
            last_error_code=999,
        )
        _set_body(
            conn,
            first_attempt,
            status="failed",
            attempts=1,
            next_retry_at="2026-07-15T09:00:00Z",
            last_error="IBKR news article unavailable (10172)",
            last_error_code=10172,
        )
        _set_body(conn, pending, status="pending")
        _set_body(
            conn,
            fetched,
            status="fetched",
            attempts=2,
            last_error="IBKR news article unavailable (10172)",
            last_error_code=10172,
        )
        _set_body(
            conn,
            terminal,
            status="unavailable",
            attempts=2,
            last_attempt_at="2026-07-15T03:00:00Z",
            last_error="IBKR news article unavailable (10172)",
            last_error_code=10172,
            unavailable_at="2026-07-15T03:00:00Z",
        )
        article_ids = (
            blocked,
            polygon,
            generic,
            first_attempt,
            pending,
            fetched,
            terminal,
        )
        before = {article_id: _body_row(conn, article_id) for article_id in article_ids}

        changed = store.reconcile_ibkr_10172_retry_policy(
            now=NOW,
            available_provider_codes=frozenset({"DJ-N"}),
        )

        after = {article_id: _body_row(conn, article_id) for article_id in article_ids}
        assert changed == 0
        assert after == before
    finally:
        conn.close()


def test_reconcile_ibkr_10172_policy_is_idempotent_and_removes_backlog(tmp_path):
    conn, store = _open_store(tmp_path / "news.db")
    try:
        article_id = _seed(store, "idempotent")
        _set_body(
            conn,
            article_id,
            status="failed",
            attempts=2,
            next_retry_at="2026-07-15T09:00:00Z",
            last_attempt_at="",
            last_error="IBKR news article unavailable (10172)",
            last_error_code=10172,
        )
        before = store.summarize_ibkr_body_backlog(
            now=NOW,
            available_provider_codes=frozenset({"DJ-N"}),
        )

        first = store.reconcile_ibkr_10172_retry_policy(
            now=NOW,
            available_provider_codes=frozenset({"DJ-N"}),
        )
        after_first = _body_row(conn, article_id)
        backlog_after = store.summarize_ibkr_body_backlog(
            now=NOW,
            available_provider_codes=frozenset({"DJ-N"}),
        )
        second = store.reconcile_ibkr_10172_retry_policy(
            now=NOW,
            available_provider_codes=frozenset({"DJ-N"}),
        )

        assert before.due_now == 1
        assert first == 1
        assert after_first["body_status"] == "unavailable"
        assert after_first["next_retry_at"] is None
        assert after_first["unavailable_at"] == "2026-07-15T11:30:00Z"
        assert backlog_after.due_now == 0
        assert backlog_after.scheduled_later == 0
        assert second == 0
        assert _body_row(conn, article_id) == after_first
    finally:
        conn.close()


def test_reconcile_ibkr_10172_policy_rejects_active_transaction_and_rolls_back_failure(
    tmp_path,
):
    conn, store = _open_store(tmp_path / "news.db")
    try:
        article_id = _seed(store, "rollback")
        _set_body(
            conn,
            article_id,
            status="failed",
            attempts=2,
            next_retry_at="2026-07-15T09:00:00Z",
            last_attempt_at="2026-07-15T03:00:00Z",
            last_error="IBKR news article unavailable (10172)",
            last_error_code=10172,
        )

        conn.execute("BEGIN")
        with pytest.raises(RuntimeError, match="transaction"):
            store.reconcile_ibkr_10172_retry_policy(
                now=NOW,
                available_provider_codes=frozenset({"DJ-N"}),
            )
        assert conn.in_transaction is True
        conn.rollback()

        before = _body_row(conn, article_id)
        conn.executescript(
            "CREATE TRIGGER reject_10172_reconcile "
            "BEFORE UPDATE OF body_status ON news_article_bodies "
            f"WHEN OLD.article_id={article_id} "
            "BEGIN SELECT RAISE(ABORT, 'injected reconcile failure'); END;"
        )
        with pytest.raises(sqlite3.IntegrityError, match="injected"):
            store.reconcile_ibkr_10172_retry_policy(
                now=NOW,
                available_provider_codes=frozenset({"DJ-N"}),
            )

        assert conn.in_transaction is False
        assert _body_row(conn, article_id) == before
    finally:
        conn.close()


def test_entitlement_filter_excludes_unavailable_provider_and_counts_it(tmp_path):
    conn, store = _open_store(tmp_path / "news.db")
    try:
        entitled = _seed(store, "entitled", publisher="DJ-N")
        _seed(
            store,
            "blocked",
            provider_id="FLY$blocked",
            publisher="FLY",
        )

        selection = store.select_ibkr_body_retries(
            now=NOW,
            limit=10,
            available_provider_codes=frozenset({"DJ-N"}),
        )

        assert selection.article_ids == (entitled,)
        assert selection.backlog.due_now == 1
        assert selection.backlog.never_attempted == 1
        assert selection.backlog.provider_not_entitled == 1
    finally:
        conn.close()


def test_provider_access_return_reenters_same_rows_under_existing_limit(tmp_path):
    conn, store = _open_store(tmp_path / "news.db")
    try:
        first = _seed(
            store,
            "first",
            provider_id="FLY$first",
            publisher="FLY",
        )
        second = _seed(
            store,
            "second",
            provider_id="FLY$second",
            publisher="FLY",
        )

        blocked = store.select_ibkr_body_retries(
            now=NOW,
            limit=1,
            available_provider_codes=frozenset({"DJ-N"}),
        )
        restored = store.select_ibkr_body_retries(
            now=NOW,
            limit=1,
            available_provider_codes=frozenset({"DJ-N", "FLY"}),
        )

        assert blocked.article_ids == ()
        assert blocked.backlog.provider_not_entitled == 2
        assert restored.article_ids == (first,)
        assert restored.backlog.due_now == 2
        assert restored.backlog.provider_not_entitled == 0
        assert second not in restored.article_ids
    finally:
        conn.close()


def test_entitlement_filter_does_not_reclassify_terminal_10172(tmp_path):
    conn, store = _open_store(tmp_path / "news.db")
    try:
        terminal = _seed(
            store,
            "terminal",
            provider_id="FLY$terminal",
            publisher="FLY",
        )
        _set_body(conn, terminal, status="unavailable", attempts=2)

        summary = store.summarize_ibkr_body_backlog(
            now=NOW,
            available_provider_codes=frozenset({"DJ-N"}),
        )

        assert summary.provider_not_entitled == 0
        assert summary.due_now == 0
        assert summary.scheduled_later == 0
        assert summary.never_attempted == 0
    finally:
        conn.close()
