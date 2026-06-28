import sqlite3

import pytest

from src.news_normalized.models import ArticleCandidate, BodyCandidate, BodyStatus
from src.news_normalized.store import BodyConflictError, NormalizedNewsStore


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    yield connection
    connection.close()


@pytest.fixture
def store(conn):
    return NormalizedNewsStore(conn)


def candidate(
    provider_id=None,
    *,
    title="Same title",
    publisher="DJ-N",
    url="",
    published_at="2026-06-27T10:00:00Z",
    primary_ticker="AAPL",
    related_tickers=(),
    observed_at="2026-06-27T10:01:00Z",
    body_status=BodyStatus.PENDING,
    raw_body=None,
):
    return ArticleCandidate(
        source="ibkr",
        provider_article_id=provider_id,
        title=title,
        publisher=publisher,
        url=url,
        published_at=published_at,
        primary_ticker=primary_ticker,
        related_tickers=related_tickers,
        observed_at=observed_at,
        content_kind="full_text" if raw_body else "unknown",
        body=BodyCandidate(
            status=body_status,
            raw_body=raw_body,
            raw_format="html" if raw_body else None,
            retrieval_method="provider_api",
            retrieval_source="ibkr",
            fetched_at=observed_at if body_status is BodyStatus.FETCHED else None,
        ),
    )


def polygon_candidate(provider_id):
    return ArticleCandidate(
        source="polygon",
        provider_article_id=provider_id,
        title="Same title",
        publisher="Example Wire",
        url="https://example.test/reused",
        published_at="2026-06-27T10:00:00Z",
        primary_ticker="AAPL",
    )


def test_fallback_article_acquires_provider_id_without_second_row(store, conn):
    first = store.upsert(candidate())
    second = store.upsert(candidate("DJ-N$1"))
    assert first.article_id == second.article_id
    assert conn.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0] == 1
    row = conn.execute("SELECT provider_article_id FROM news_articles").fetchone()
    assert row[0] == "DJ-N$1"


def test_attached_provider_alias_resolves_same_article(store, conn):
    first = store.upsert(polygon_candidate("id-a"))
    conn.execute(
        "INSERT INTO news_article_keys"
        "(article_id,source,key_kind,key_value,created_at) VALUES (?,?,?,?,?)",
        (first.article_id, "polygon", "provider_id", "id-b", "2026-06-29T00:00:00Z"),
    )

    alias = store.candidate_by_provider_id("polygon", "id-b")
    result = store.upsert(polygon_candidate("id-b"))

    assert alias is not None
    assert result.article_id == first.article_id
    assert result.quarantined is False


def test_cross_ticker_fetch_stores_one_body_and_relations(store, conn):
    result = store.upsert(
        candidate(
            "DJ-N$2",
            related_tickers=("AAPL", "MSFT", "AAPL"),
            body_status=BodyStatus.FETCHED,
            raw_body="<p>body</p>",
        )
    )
    assert conn.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0] == 1
    relations = conn.execute(
        "SELECT ticker,relation_kind FROM news_article_tickers "
        "WHERE article_id=? ORDER BY ticker",
        (result.article_id,),
    ).fetchall()
    assert [tuple(row) for row in relations] == [
        ("AAPL", "primary"),
        ("MSFT", "related"),
    ]
    body = conn.execute(
        "SELECT body_status,raw_body,raw_ref,body_sha256,body_text "
        "FROM news_article_bodies WHERE article_id=?",
        (result.article_id,),
    ).fetchone()
    assert body["body_status"] == "fetched"
    assert body["raw_body"] == "<p>body</p>"
    assert body["raw_ref"] is None
    assert len(body["body_sha256"]) == 64
    assert body["body_text"] == "body"


def test_third_10172_becomes_terminal_unavailable(store, conn, monkeypatch):
    article = candidate("DJ-N$retry")
    result = store.upsert(article)
    conn.execute(
        "UPDATE news_article_bodies SET body_status='failed',fetch_attempts=2 "
        "WHERE article_id=?",
        (result.article_id,),
    )
    monkeypatch.setattr(
        "src.news_normalized.store._now", lambda: "2026-06-29T00:00:00Z"
    )

    store.update_body(
        article,
        BodyCandidate(
            status=BodyStatus.FAILED,
            error="IBKR news article unavailable (10172)",
            error_code=10172,
        ),
    )

    row = conn.execute(
        "SELECT body_status,fetch_attempts,last_error_code,next_retry_at,unavailable_at "
        "FROM news_article_bodies WHERE article_id=?",
        (result.article_id,),
    ).fetchone()
    assert tuple(row) == (
        "unavailable",
        3,
        10172,
        None,
        "2026-06-29T00:00:00Z",
    )


def test_10172_before_third_attempt_sets_six_hour_retry(store, conn, monkeypatch):
    article = candidate("DJ-N$retry")
    result = store.upsert(article)
    monkeypatch.setattr(
        "src.news_normalized.store._now", lambda: "2026-06-29T00:00:00Z"
    )

    store.update_body(
        article,
        BodyCandidate(
            status=BodyStatus.FAILED,
            error="IBKR news article unavailable (10172)",
            error_code=10172,
        ),
    )

    row = conn.execute(
        "SELECT body_status,fetch_attempts,last_error_code,next_retry_at "
        "FROM news_article_bodies WHERE article_id=?",
        (result.article_id,),
    ).fetchone()
    assert tuple(row) == (
        "failed",
        1,
        10172,
        "2026-06-29T06:00:00Z",
    )


def test_new_body_variant_preserves_loser_and_indexes_only_active(store, conn):
    article = candidate(
        "DJ-N$variant",
        body_status=BodyStatus.FETCHED,
        raw_body="short",
    )
    result = store.upsert(article)

    store.update_body(
        article,
        BodyCandidate(
            status=BodyStatus.FETCHED,
            raw_body="long complete provider body",
            raw_format="text",
            retrieval_method="provider_api",
            retrieval_source="ibkr",
            fetched_at="2026-06-29T01:00:00Z",
        ),
    )

    active = conn.execute(
        "SELECT raw_body FROM news_article_bodies WHERE article_id=?",
        (result.article_id,),
    ).fetchone()[0]
    cold = conn.execute(
        "SELECT raw_body FROM news_article_body_variants WHERE article_id=?",
        (result.article_id,),
    ).fetchall()
    search = conn.execute(
        "SELECT body_text FROM news_search_documents WHERE article_id=?",
        (result.article_id,),
    ).fetchone()[0]
    assert active == "long complete provider body"
    assert [row[0] for row in cold] == ["short"]
    assert search == "long complete provider body"


def test_unavailable_recovers_only_through_explicit_reprobe(store, conn):
    article = candidate("DJ-N$recover")
    result = store.upsert(article)
    conn.execute(
        "UPDATE news_article_bodies SET body_status='unavailable',fetch_attempts=3,"
        "last_error_code=10172 WHERE article_id=?",
        (result.article_id,),
    )
    fetched = BodyCandidate(
        status=BodyStatus.FETCHED,
        raw_body="recovered body",
        raw_format="text",
    )

    with pytest.raises(BodyConflictError):
        store.update_body(article, fetched)
    store.update_body(article, fetched, allow_terminal_recovery=True)

    row = conn.execute(
        "SELECT body_status,last_error_code,unavailable_at FROM news_article_bodies "
        "WHERE article_id=?",
        (result.article_id,),
    ).fetchone()
    assert tuple(row) == ("fetched", None, None)


def test_disagreeing_strong_keys_are_quarantined_without_article_mutation(store, conn):
    store.upsert(candidate("p1", url="https://example.test/a"))
    store.upsert(candidate("p2", url="https://example.test/b", title="Other"))
    before = conn.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0]
    result = store.upsert(candidate("p1", url="https://example.test/b"))
    assert result.quarantined is True
    assert result.article_id is None
    assert conn.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0] == before
    conflict = conn.execute(
        "SELECT conflict_kind,candidate_payload_json FROM news_ingest_conflicts"
    ).fetchone()
    assert conflict["conflict_kind"] == "strong_key_disagreement"
    assert "p1" in conflict["candidate_payload_json"]


def test_repeated_identity_conflict_ignores_volatile_observation_and_body_fields(
    store, conn
):
    store.upsert(candidate("p1", url="https://example.test/a"))
    store.upsert(candidate("p2", url="https://example.test/b", title="Other"))

    first = store.upsert(
        candidate(
            "p1",
            url="https://example.test/b",
            observed_at="2026-06-27T10:01:00Z",
            body_status=BodyStatus.FETCHED,
            raw_body="first volatile body",
        )
    )
    second = store.upsert(
        candidate(
            "p1",
            url="https://example.test/b",
            observed_at="2026-06-27T10:02:00Z",
            body_status=BodyStatus.FETCHED,
            raw_body="different volatile body",
        )
    )

    assert first.conflict_id == second.conflict_id
    assert conn.execute("SELECT COUNT(*) FROM news_ingest_conflicts").fetchone()[0] == 1


def test_incompatible_weak_collision_stays_separate(store, conn):
    first = store.upsert(
        candidate(body_status=BodyStatus.FETCHED, raw_body="<p>first</p>")
    )
    second = store.upsert(
        candidate(body_status=BodyStatus.FETCHED, raw_body="<p>second</p>")
    )
    assert first.article_id != second.article_id
    assert conn.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0] == 2


def test_ambiguous_weak_candidate_is_quarantined(store, conn):
    store.upsert(candidate(body_status=BodyStatus.FETCHED, raw_body="first"))
    store.upsert(candidate(body_status=BodyStatus.FETCHED, raw_body="second"))
    result = store.upsert(candidate())
    assert result.quarantined is True
    assert conn.execute(
        "SELECT conflict_kind FROM news_ingest_conflicts"
    ).fetchone()[0] == "weak_key_ambiguity"


def test_title_revisions_are_preserved_and_body_title_remains_canonical(store, conn):
    result = store.upsert(
        candidate(
            "DJ-N$3",
            title="Original",
            observed_at="2026-06-27T10:00:00Z",
            body_status=BodyStatus.FETCHED,
            raw_body="body",
        )
    )
    store.upsert(
        candidate(
            "DJ-N$3",
            title="Update: Original",
            observed_at="2026-06-27T11:00:00Z",
        )
    )
    assert conn.execute(
        "SELECT canonical_title FROM news_articles WHERE id=?", (result.article_id,)
    ).fetchone()[0] == "Original"
    titles = conn.execute(
        "SELECT title FROM news_article_titles WHERE article_id=? ORDER BY title",
        (result.article_id,),
    ).fetchall()
    assert [row[0] for row in titles] == ["Original", "Update: Original"]


def test_raw_markup_is_not_searchable_but_clean_text_is(store, conn):
    result = store.upsert(
        candidate(
            "DJ-N$4",
            title="Visible title",
            body_status=BodyStatus.FETCHED,
            raw_body="<script>rawsecret</script><p>searchable body</p>",
        )
    )
    assert [
        row[0]
        for row in conn.execute(
            "SELECT rowid FROM news_articles_fts WHERE news_articles_fts MATCH 'searchable'"
        )
    ] == [result.article_id]
    assert list(
        conn.execute(
            "SELECT rowid FROM news_articles_fts WHERE news_articles_fts MATCH 'rawsecret'"
        )
    ) == []


def test_fetched_body_cannot_be_downgraded_and_replacement_is_preserved(store, conn):
    original = candidate(
        "DJ-N$5", body_status=BodyStatus.FETCHED, raw_body="original"
    )
    store.upsert(original)
    store.upsert(candidate("DJ-N$5", body_status=BodyStatus.PENDING))
    store.upsert(
        candidate("DJ-N$5", body_status=BodyStatus.FETCHED, raw_body="different")
    )

    active = conn.execute(
        "SELECT raw_body FROM news_article_bodies"
    ).fetchone()[0]
    variants = conn.execute(
        "SELECT raw_body FROM news_article_body_variants"
    ).fetchall()
    assert active == "different"
    assert [row[0] for row in variants] == ["original"]


def test_failed_body_can_retry_to_fetched(store, conn):
    result = store.upsert(candidate("DJ-N$6", body_status=BodyStatus.FAILED))
    store.update_body(
        candidate("DJ-N$6"),
        BodyCandidate(
            status=BodyStatus.FETCHED,
            raw_body="recovered",
            raw_format="text",
            retrieval_source="ibkr",
        ),
    )
    row = conn.execute(
        "SELECT body_status,fetch_attempts,last_error FROM news_article_bodies "
        "WHERE article_id=?",
        (result.article_id,),
    ).fetchone()
    assert tuple(row) == ("fetched", 2, None)


@pytest.mark.parametrize("terminal", [BodyStatus.EMPTY, BodyStatus.EXPIRED])
def test_repeated_terminal_body_state_is_idempotent(store, conn, terminal):
    result = store.upsert(candidate("terminal", body_status=terminal))
    before = conn.execute(
        "SELECT fetch_attempts FROM news_article_bodies WHERE article_id=?",
        (result.article_id,),
    ).fetchone()[0]
    store.upsert(candidate("terminal", body_status=terminal))
    after = conn.execute(
        "SELECT fetch_attempts FROM news_article_bodies WHERE article_id=?",
        (result.article_id,),
    ).fetchone()[0]
    assert before == after == 1


def test_latest_cursor_is_source_and_ticker_scoped(store):
    store.upsert(candidate("one", published_at="2026-06-26T10:00:00Z"))
    store.upsert(
        candidate(
            "two",
            title="Second",
            published_at="2026-06-27T12:00:00Z",
            primary_ticker="MSFT",
        )
    )
    assert store.latest_cursor("ibkr", "AAPL") == "2026-06-26T10:00:00Z"
    assert store.latest_cursor("ibkr", "MSFT") == "2026-06-27T12:00:00Z"
    assert store.latest_cursor("polygon", "AAPL") is None


def test_candidate_can_be_rehydrated_by_provider_id(store):
    result = store.upsert(candidate("DJ-N$7", title="Rehydrate"))
    restored = store.candidate_by_provider_id("ibkr", "DJ-N$7")
    assert restored is not None
    assert restored.provider_article_id == "DJ-N$7"
    assert restored.title == "Rehydrate"
    assert restored.primary_ticker == "AAPL"
    assert result.article_id is not None
