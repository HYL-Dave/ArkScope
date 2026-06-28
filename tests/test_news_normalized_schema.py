import sqlite3

import pytest

import src.news_normalized.schema as schema_module
from src.news_normalized.models import BodyCandidate, BodyStatus
from src.news_normalized.schema import ensure_news_normalized_schema


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys=ON")
    yield connection
    connection.close()


def _article(conn, *, source="ibkr", provider_id=None, title="Title"):
    cursor = conn.execute(
        "INSERT INTO news_articles "
        "(source,provider_article_id,canonical_title,published_at,created_at,updated_at) "
        "VALUES (?,?,?,?,?,?)",
        (source, provider_id, title, "2026-06-27T10:00:00Z", "now", "now"),
    )
    return cursor.lastrowid


def _key(conn, article_id, source, kind, value):
    conn.execute(
        "INSERT INTO news_article_keys "
        "(article_id,source,key_kind,key_value,created_at) VALUES (?,?,?,?,?)",
        (article_id, source, kind, value, "now"),
    )


def test_schema_is_idempotent_and_has_all_normalized_tables(conn):
    ensure_news_normalized_schema(conn)
    ensure_news_normalized_schema(conn)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
        )
    }
    assert {
        "news_articles",
        "news_article_keys",
        "news_article_tickers",
        "news_article_titles",
        "news_article_bodies",
        "news_article_body_variants",
        "news_search_documents",
        "news_articles_fts",
        "news_ingest_conflicts",
        "news_normalization_runs",
        "news_legacy_migration_map",
    } <= tables


def test_strong_keys_are_unique_but_weak_fallback_collisions_are_allowed(conn):
    ensure_news_normalized_schema(conn)
    first = _article(conn)
    second = _article(conn, title="Other")
    _key(conn, first, "ibkr", "fallback", "same")
    _key(conn, second, "ibkr", "fallback", "same")
    _key(conn, first, "ibkr", "provider_id", "DJ-N$1")
    with pytest.raises(sqlite3.IntegrityError):
        _key(conn, second, "ibkr", "provider_id", "DJ-N$1")


def test_provider_article_id_is_unique_per_source_when_present(conn):
    ensure_news_normalized_schema(conn)
    _article(conn, source="ibkr", provider_id="same")
    _article(conn, source="polygon", provider_id="same")
    with pytest.raises(sqlite3.IntegrityError):
        _article(conn, source="ibkr", provider_id="same")
    _article(conn, source="ibkr", provider_id=None)
    _article(conn, source="ibkr", provider_id=None)


def test_body_status_check_and_raw_ref_column(conn):
    ensure_news_normalized_schema(conn)
    article_id = _article(conn)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(news_article_bodies)")}
    assert {
        "raw_body",
        "raw_ref",
        "body_text",
        "body_sha256",
        "last_error_code",
        "unavailable_at",
    } <= columns
    conn.execute(
        "INSERT INTO news_article_bodies(article_id,body_status,raw_ref) VALUES (?,?,?)",
        (article_id, "fetched", "cold://body/1"),
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO news_article_bodies(article_id,body_status) VALUES (?,?)",
            (_article(conn, title="Bad"), "guessed_expired"),
        )


def test_body_model_has_unavailable_and_structured_retry_fields():
    body = BodyCandidate(
        status=BodyStatus.UNAVAILABLE,
        error_code=10172,
        fetch_attempts=3,
        next_retry_at=None,
    )

    assert body.status.value == "unavailable"
    assert body.error_code == 10172
    assert body.fetch_attempts == 3


def test_legacy_migration_map_does_not_reference_legacy_news(conn):
    ensure_news_normalized_schema(conn)

    targets = {
        row[2]
        for row in conn.execute("PRAGMA foreign_key_list(news_legacy_migration_map)")
    }

    assert "news" not in targets
    assert {"news_articles", "news_normalization_runs"} <= targets


def test_migration_schema_helper_opens_one_rollbackable_transaction(conn):
    schema_module.begin_news_normalized_schema_transaction(conn)

    assert conn.in_transaction is True
    assert conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name='news_articles'"
    ).fetchone()[0] == 1
    conn.rollback()
    assert conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name='news_articles'"
    ).fetchone()[0] == 0


def test_foreign_keys_cascade_article_children(conn):
    ensure_news_normalized_schema(conn)
    article_id = _article(conn)
    _key(conn, article_id, "ibkr", "fallback", "f")
    conn.execute(
        "INSERT INTO news_article_tickers VALUES (?,?,?,?,?)",
        (article_id, "AAPL", "primary", "now", "now"),
    )
    conn.execute(
        "INSERT INTO news_article_titles "
        "(article_id,title,normalized_title,observed_with_body) VALUES (?,?,?,?)",
        (article_id, "Title", "title", 0),
    )
    conn.execute("DELETE FROM news_articles WHERE id=?", (article_id,))
    assert conn.execute("SELECT COUNT(*) FROM news_article_keys").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM news_article_tickers").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM news_article_titles").fetchone()[0] == 0


def test_search_projection_triggers_insert_update_delete_fts(conn):
    ensure_news_normalized_schema(conn)
    article_id = _article(conn)
    conn.execute(
        "INSERT INTO news_search_documents(article_id,title,body_text) VALUES (?,?,?)",
        (article_id, "Alpha", "clean body"),
    )
    assert conn.execute(
        "SELECT rowid FROM news_articles_fts WHERE news_articles_fts MATCH 'Alpha'"
    ).fetchall() == [(article_id,)]
    conn.execute(
        "UPDATE news_search_documents SET title=?,body_text=? WHERE article_id=?",
        ("Beta", "revised text", article_id),
    )
    assert conn.execute(
        "SELECT rowid FROM news_articles_fts WHERE news_articles_fts MATCH 'Alpha'"
    ).fetchall() == []
    assert conn.execute(
        "SELECT rowid FROM news_articles_fts WHERE news_articles_fts MATCH 'revised'"
    ).fetchall() == [(article_id,)]
    conn.execute("DELETE FROM news_search_documents WHERE article_id=?", (article_id,))
    assert conn.execute("SELECT rowid FROM news_articles_fts").fetchall() == []


def test_relation_and_conflict_status_checks(conn):
    ensure_news_normalized_schema(conn)
    article_id = _article(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO news_article_tickers VALUES (?,?,?,?,?)",
            (article_id, "AAPL", "owner", "now", "now"),
        )
    conn.execute(
        "INSERT INTO news_ingest_conflicts "
        "(source,conflict_kind,candidate_fingerprint,candidate_payload_json,status,created_at) "
        "VALUES (?,?,?,?,?,?)",
        ("ibkr", "weak_ambiguity", "abc", "{}", "open", "now"),
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO news_ingest_conflicts "
            "(source,conflict_kind,candidate_fingerprint,candidate_payload_json,status,created_at) "
            "VALUES (?,?,?,?,?,?)",
            ("ibkr", "weak_ambiguity", "def", "{}", "invalid", "now"),
        )
