import hashlib
import sqlite3

import pytest

import src.news_identity as ni
from src.market_data_admin import (
    _NEWS_SCHEMA,
    _ensure_news_fts_triggers,
    _ensure_news_hash_unique,
)
from src.news_identity import canonical_article_hash


@pytest.fixture
def conn():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(_NEWS_SCHEMA)
    _ensure_news_hash_unique(db)
    _ensure_news_fts_triggers(db)
    yield db
    db.close()


def _insert(
    conn,
    *,
    row_id,
    ticker="HAPN",
    title="T",
    published_at="2026-06-01T12:00:00+0000",
    article_hash=None,
    description="",
    url="",
    publisher="",
    source="ibkr",
    sentiment_score=None,
    sentiment_source=None,
    sentiment_scale=None,
):
    conn.execute(
        "INSERT INTO news "
        "(id,ticker,title,description,url,publisher,source,published_at,article_hash,"
        "sentiment_score,sentiment_source,sentiment_scale) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            row_id,
            ticker,
            title,
            description,
            url,
            publisher,
            source,
            published_at,
            article_hash or canonical_article_hash(ticker, title, published_at),
            sentiment_score,
            sentiment_source,
            sentiment_scale,
        ),
    )
    conn.commit()


def test_canonical_article_hash_uses_verbatim_ticker_title_and_date10():
    assert canonical_article_hash(
        "HAPN", "Title With Case ", "2026-06-27T23:59:59+0000"
    ) == hashlib.sha256(b"HAPN|Title With Case |2026-06-27").hexdigest()


def test_direct_and_migration_share_the_same_hash_function():
    import src.news_providers as providers

    assert providers.canonical_article_hash is canonical_article_hash


def test_plan_classifies_unowned_stale_hash_as_update(conn):
    stale = canonical_article_hash("LC", "T", "2026-06-01")
    _insert(conn, row_id=1, article_hash=stale)

    plan = ni.plan_news_identity_repair(conn)

    assert [(u.row_id, u.old_hash, u.target_hash, u.target_ticker) for u in plan.updates] == [
        (1, stale, canonical_article_hash("HAPN", "T", "2026-06-01"), "HAPN")
    ]
    assert plan.collisions == ()


def test_plan_finds_canonical_owner_outside_only_ids(conn):
    stale = canonical_article_hash("LC", "T", "2026-06-01")
    target = canonical_article_hash("HAPN", "T", "2026-06-01")
    _insert(conn, row_id=1, article_hash=stale)
    _insert(conn, row_id=2, article_hash=target)

    plan = ni.plan_news_identity_repair(conn, only_ids={1})

    assert plan.updates == ()
    assert [(c.stale_id, c.target_id, c.target_hash) for c in plan.collisions] == [
        (1, 2, target)
    ]


def test_plan_same_target_without_canonical_owner_uses_lowest_id(conn):
    _insert(conn, row_id=7, article_hash="a" * 64)
    _insert(conn, row_id=3, article_hash="b" * 64)

    plan = ni.plan_news_identity_repair(conn)

    assert [(u.row_id, u.target_hash) for u in plan.updates] == [
        (3, canonical_article_hash("HAPN", "T", "2026-06-01"))
    ]
    assert [(c.stale_id, c.target_id) for c in plan.collisions] == [(7, 3)]


def test_plan_fingerprint_covers_merge_content(conn):
    _insert(conn, row_id=1, article_hash=canonical_article_hash("LC", "T", "2026-06-01"))
    _insert(conn, row_id=2)
    first = ni.plan_news_identity_repair(conn)

    conn.execute("UPDATE news SET description='richer' WHERE id=1")
    conn.commit()
    second = ni.plan_news_identity_repair(conn)

    assert len(first.collisions) == len(second.collisions) == 1
    assert first.fingerprint != second.fingerprint


def test_apply_updates_hash_without_deleting_noncollision(conn):
    stale = canonical_article_hash("LC", "T", "2026-06-01")
    _insert(conn, row_id=1, article_hash=stale)

    result = ni.apply_news_identity_plan(conn, ni.plan_news_identity_repair(conn))

    row = conn.execute("SELECT id,ticker,article_hash FROM news").fetchone()
    assert tuple(row) == (1, "HAPN", canonical_article_hash("HAPN", "T", "2026-06-01"))
    assert result == {"updated": 1, "deleted": 0, "merged_fields": 0}


def test_apply_keeps_canonical_id_and_fills_missing_description(conn):
    _insert(
        conn,
        row_id=1,
        article_hash=canonical_article_hash("LC", "T", "2026-06-01"),
        description="rich historical description",
    )
    _insert(conn, row_id=2, description="")

    result = ni.apply_news_identity_plan(conn, ni.plan_news_identity_repair(conn))

    rows = conn.execute("SELECT id,description FROM news ORDER BY id").fetchall()
    assert [tuple(row) for row in rows] == [(2, "rich historical description")]
    assert result == {"updated": 0, "deleted": 1, "merged_fields": 1}


def test_apply_never_overwrites_nonempty_canonical_fields(conn):
    _insert(
        conn,
        row_id=1,
        article_hash=canonical_article_hash("LC", "T", "2026-06-01"),
        description="stale description",
        url="https://old",
    )
    _insert(conn, row_id=2, description="canonical description", url="https://canonical")

    ni.apply_news_identity_plan(conn, ni.plan_news_identity_repair(conn))

    row = conn.execute("SELECT id,description,url FROM news").fetchone()
    assert tuple(row) == (2, "canonical description", "https://canonical")


def test_apply_merges_missing_sentiment_fields(conn):
    _insert(
        conn,
        row_id=1,
        article_hash=canonical_article_hash("LC", "T", "2026-06-01"),
        sentiment_score=4.0,
        sentiment_source="local",
        sentiment_scale="1-5",
    )
    _insert(conn, row_id=2)

    ni.apply_news_identity_plan(conn, ni.plan_news_identity_repair(conn))

    row = conn.execute(
        "SELECT id,sentiment_score,sentiment_source,sentiment_scale FROM news"
    ).fetchone()
    assert tuple(row) == (2, 4.0, "local", "1-5")


def test_apply_preserves_canonical_source_and_published_at(conn):
    stale_time = "2026-06-01T12:00:00+0000"
    canonical_time = "2026-06-01T13:00:00+0000"
    _insert(
        conn,
        row_id=1,
        source="ibkr",
        published_at=stale_time,
        article_hash=canonical_article_hash("LC", "T", stale_time),
    )
    _insert(conn, row_id=2, source="polygon", published_at=canonical_time)

    ni.apply_news_identity_plan(conn, ni.plan_news_identity_repair(conn))

    row = conn.execute("SELECT id,source,published_at FROM news").fetchone()
    assert tuple(row) == (2, "polygon", canonical_time)


def test_apply_collision_keeps_fts_in_sync(conn):
    _insert(
        conn,
        row_id=1,
        article_hash=canonical_article_hash("LC", "T", "2026-06-01"),
        description="uniquearchivephrase",
    )
    _insert(conn, row_id=2)

    ni.apply_news_identity_plan(conn, ni.plan_news_identity_repair(conn))

    hits = conn.execute(
        "SELECT n.id FROM news_fts f JOIN news n ON n.id=f.rowid "
        "WHERE news_fts MATCH 'uniquearchivephrase'"
    ).fetchall()
    assert [row[0] for row in hits] == [2]
    assert conn.execute("SELECT COUNT(*) FROM news").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM news_fts").fetchone()[0] == 1


def test_apply_is_zero_change_on_second_plan(conn):
    _insert(
        conn,
        row_id=1,
        article_hash=canonical_article_hash("LC", "T", "2026-06-01"),
    )
    ni.apply_news_identity_plan(conn, ni.plan_news_identity_repair(conn))

    second = ni.plan_news_identity_repair(conn)

    assert second.updates == ()
    assert second.collisions == ()


def test_validate_news_identity_reports_clean_repaired_store(conn):
    _insert(
        conn,
        row_id=1,
        article_hash=canonical_article_hash("LC", "T", "2026-06-01"),
    )
    ni.apply_news_identity_plan(conn, ni.plan_news_identity_repair(conn))

    assert ni.validate_news_identity(conn) == {
        "news_rows": 1,
        "fts_rows": 1,
        "hash_mismatches": 0,
        "duplicate_hash_groups": 0,
        "semantic_duplicate_groups": 0,
        "fts_missing": 0,
        "fts_orphans": 0,
    }
