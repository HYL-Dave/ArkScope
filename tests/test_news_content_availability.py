from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest

from src.news_content_availability import (
    RECOVERY_CAPABLE_BODY_SOURCES,
    classify_news_content,
    empty_content_counts,
    news_content_sql,
)
from src.news_normalized.schema import ensure_news_normalized_schema
from src.tools.backends.sqlite_backend import SqliteBackend


@pytest.mark.parametrize(
    ("body_status", "source", "expected_availability", "expected_recovery"),
    (
        ("fetched", "finnhub", "full", None),
        ("pending", "ibkr", "headline_only", "retryable"),
        ("failed", "ibkr", "headline_only", "retryable"),
        ("pending", "finnhub", "headline_only", "terminal"),
        ("failed", "polygon", "headline_only", "terminal"),
        ("empty", "polygon", "headline_only", "terminal"),
        ("unavailable", "ibkr", "headline_only", "terminal"),
        ("expired", "ibkr", "headline_only", "terminal"),
        (None, None, "unknown", None),
    ),
    ids=(
        "fetched",
        "pending-retryable",
        "failed-retryable",
        "pending-no-recovery",
        "failed-no-recovery",
        "empty",
        "unavailable",
        "expired",
        "unmapped",
    ),
)
def test_classify_news_content(
    body_status: str | None,
    source: str | None,
    expected_availability: str,
    expected_recovery: str | None,
) -> None:
    assert classify_news_content(body_status, source) == (
        expected_availability,
        expected_recovery,
    )


def test_recovery_capable_sources_are_exactly_ibkr() -> None:
    assert RECOVERY_CAPABLE_BODY_SOURCES == frozenset({"ibkr"})

    first = empty_content_counts()
    second = empty_content_counts()
    assert first == second == {"full": 0, "headline_only": 0, "unknown": 0}
    assert first is not second
    first["full"] = 1
    assert second["full"] == 0


def _seed_legacy_feed(path: Path, rows: list[tuple]) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE news (
                id INTEGER PRIMARY KEY,
                ticker TEXT,
                title TEXT,
                description TEXT,
                url TEXT,
                publisher TEXT,
                source TEXT,
                published_at TEXT,
                article_hash TEXT
            );
            CREATE VIRTUAL TABLE news_fts USING fts5(
                title,
                description,
                content='news',
                content_rowid='id',
                tokenize='porter unicode61'
            );
            """
        )
        conn.executemany("INSERT INTO news VALUES (?,?,?,?,?,?,?,?,?)", rows)
        conn.execute("INSERT INTO news_fts(news_fts) VALUES('rebuild')")
        conn.commit()
    finally:
        conn.close()


def _seed_content_feed(tmp_path: Path, name: str = "content.db") -> Path:
    newest = f"{date.today().isoformat()}T12:00:00+0000"
    recent = f"{(date.today() - timedelta(days=1)).isoformat()}T12:00:00+0000"
    older = f"{(date.today() - timedelta(days=20)).isoformat()}T12:00:00+0000"
    db = tmp_path / name
    rows = [
        (1, "AAPL", "Apple full report", "legacy full summary", "u1", "P1", "finnhub", newest, "h1"),
        (2, "AAPL", "Apple retry pending", "", "u2", "P2", "ibkr", recent, "h2"),
        (3, "AAPL", "Apple retry failed", "", "u3", "P3", "ibkr", recent, "h3"),
        (4, "NVDA", "Nvidia beacon headline", "", "u4", "P4", "finnhub", recent, "h4"),
        (5, "NVDA", "Nvidia polygon failed", "", "u5", "P5", "polygon", recent, "h5"),
        (6, "MSFT", "Microsoft empty body", "", "u6", "P6", "polygon", recent, "h6"),
        (7, "MSFT", "Microsoft unavailable body", "", "u7", "P7", "ibkr", recent, "h7"),
        (8, "TSLA", "Tesla expired body", "", "u8", "P8", "ibkr", recent, "h8"),
        (9, "AAPL", "Apple legacy unknown", "", "u9", "P9", "finnhub", older, "h9"),
    ]
    _seed_legacy_feed(db, rows)

    conn = sqlite3.connect(db)
    try:
        ensure_news_normalized_schema(conn)
        conn.execute(
            "INSERT INTO news_normalization_runs "
            "(id,policy_version,input_fingerprint,resolved_fingerprint,"
            "rejection_evidence_fingerprint,counts_json,backup_path,applied_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (1, "test", "input", "resolved", "reject", "{}", "backup.db", "now"),
        )
        normalized = [
            (101, "finnhub", "Apple full report", newest, "fetched", "normalizedonlyburiedterm"),
            (102, "ibkr", "Apple retry pending", recent, "pending", None),
            (103, "ibkr", "Apple retry failed", recent, "failed", None),
            (104, "finnhub", "Nvidia beacon headline", recent, "pending", None),
            (105, "polygon", "Nvidia polygon failed", recent, "failed", None),
            (106, "polygon", "Microsoft empty body", recent, "empty", None),
            (107, "ibkr", "Microsoft unavailable body", recent, "unavailable", None),
            (108, "ibkr", "Tesla expired body", recent, "expired", None),
        ]
        conn.executemany(
            "INSERT INTO news_articles "
            "(id,source,canonical_title,published_at,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?)",
            [(article_id, source, title, published_at, "now", "now")
             for article_id, source, title, published_at, _, _ in normalized],
        )
        conn.executemany(
            "INSERT INTO news_article_bodies(article_id,body_status,body_text) "
            "VALUES (?,?,?)",
            [(article_id, status, body_text)
             for article_id, _, _, _, status, body_text in normalized],
        )
        for legacy_id in (1, 3, 5, 7):
            conn.execute(
                "INSERT INTO news_legacy_migration_map "
                "(legacy_news_id,article_id,resolution_kind,migration_run_id,"
                "migration_fingerprint) VALUES (?,?,?,?,?)",
                (legacy_id, 100 + legacy_id, "mapped", 1, "resolved"),
            )
        for legacy_id in (2, 4, 6, 8):
            conn.execute(
                "INSERT INTO news_legacy_projection_map "
                "(article_id,ticker,legacy_news_id,projected_at) VALUES (?,?,?,?)",
                (100 + legacy_id, rows[legacy_id - 1][1], legacy_id, "now"),
            )
        # Both maps may contain a legacy row; migration authority wins.
        conn.execute(
            "INSERT INTO news_legacy_projection_map "
            "(article_id,ticker,legacy_news_id,projected_at) VALUES (?,?,?,?)",
            (106, "AAPL", 1, "now"),
        )
        conn.commit()
    finally:
        conn.close()
    return db


def test_feed_classifies_all_statuses_through_both_maps_without_duplicate_rows(
    tmp_path: Path,
) -> None:
    db = _seed_content_feed(tmp_path)

    feed = SqliteBackend(db).query_news_feed(days=30, limit=50)

    assert feed["total"] == 9
    assert feed["content_counts"] == {
        "full": 1,
        "headline_only": 7,
        "unknown": 1,
    }
    assert len(feed["items"]) == 9
    by_title = {row["title"]: row for row in feed["items"]}
    assert len(by_title) == 9
    assert (by_title["Apple full report"]["content_availability"],
            by_title["Apple full report"]["content_recovery"]) == ("full", None)
    assert (by_title["Apple retry pending"]["content_availability"],
            by_title["Apple retry pending"]["content_recovery"]) == (
                "headline_only", "retryable")
    assert (by_title["Apple retry failed"]["content_availability"],
            by_title["Apple retry failed"]["content_recovery"]) == (
                "headline_only", "retryable")
    assert (by_title["Nvidia beacon headline"]["content_availability"],
            by_title["Nvidia beacon headline"]["content_recovery"]) == (
                "headline_only", "terminal")
    assert (by_title["Nvidia polygon failed"]["content_availability"],
            by_title["Nvidia polygon failed"]["content_recovery"]) == (
                "headline_only", "terminal")
    for title in (
        "Microsoft empty body",
        "Microsoft unavailable body",
        "Tesla expired body",
    ):
        assert (by_title[title]["content_availability"],
                by_title[title]["content_recovery"]) == (
                    "headline_only", "terminal")
    assert (by_title["Apple legacy unknown"]["content_availability"],
            by_title["Apple legacy unknown"]["content_recovery"]) == (
                "unknown", None)


def test_content_filter_precedes_total_facets_and_pagination_with_stable_order(
    tmp_path: Path,
) -> None:
    backend = SqliteBackend(_seed_content_feed(tmp_path))
    statements: list[str] = []
    original_connect = backend._connect

    def traced_connect() -> sqlite3.Connection:
        conn = original_connect()
        conn.set_trace_callback(statements.append)
        return conn

    backend._connect = traced_connect  # type: ignore[method-assign]

    first = backend.query_news_feed(content="headline_only", days=30, limit=2)
    second = backend.query_news_feed(
        content="headline_only", days=30, limit=2, offset=2)

    item_statements = [
        statement
        for statement in statements
        if statement.lstrip().startswith("SELECT n.published_at,")
    ]
    availability_sql, _ = news_content_sql("b.body_status", "a.source")
    assert len(item_statements) == 2
    for statement, expected_offset in zip(item_statements, (0, 2), strict=True):
        assert f"AND ({availability_sql}) = 'headline_only'" in statement
        assert f"LIMIT 2 OFFSET {expected_offset}" in statement

    assert first["total"] == second["total"] == 7
    assert first["sources"] == {"finnhub": 1, "ibkr": 4, "polygon": 2}
    assert list(first["days"].values()) == [7]
    assert [row["title"] for row in first["items"]] == [
        "Tesla expired body",
        "Microsoft unavailable body",
    ]
    assert [row["title"] for row in second["items"]] == [
        "Microsoft empty body",
        "Nvidia polygon failed",
    ]
    assert {row["title"] for row in first["items"]}.isdisjoint(
        {row["title"] for row in second["items"]}
    )
    assert backend.query_news_feed(content="full", days=30)["total"] == 1
    assert backend.query_news_feed(content="unknown", days=30)["total"] == 1


def test_content_counts_ignore_only_content_axis_and_respect_other_filters(
    tmp_path: Path,
) -> None:
    backend = SqliteBackend(_seed_content_feed(tmp_path))
    statements: list[str] = []
    original_connect = backend._connect

    def traced_connect() -> sqlite3.Connection:
        conn = original_connect()
        conn.set_trace_callback(statements.append)
        return conn

    backend._connect = traced_connect  # type: ignore[method-assign]

    apple = backend.query_news_feed(
        q="apple", ticker="AAPL", content="headline_only", days=30)
    assert apple["total"] == 2
    assert apple["content_counts"] == {
        "full": 1,
        "headline_only": 2,
        "unknown": 1,
    }
    normalized_join_statements = [
        statement
        for statement in statements
        if "JOIN news_legacy_migration_map" in statement
        or "JOIN news_legacy_projection_map" in statement
    ]
    assert len(normalized_join_statements) <= 2

    backend._connect = original_connect  # type: ignore[method-assign]

    finnhub = backend.query_news_feed(
        source="finnhub", content="headline_only", days=30)
    assert finnhub["total"] == 1
    assert finnhub["content_counts"] == {
        "full": 1,
        "headline_only": 1,
        "unknown": 1,
    }

    recent = backend.query_news_feed(days=7)
    assert recent["content_counts"] == {
        "full": 1,
        "headline_only": 7,
        "unknown": 0,
    }


def test_missing_or_partial_normalized_schema_degrades_affected_rows_to_unknown(
    tmp_path: Path,
) -> None:
    recent = f"{(date.today() - timedelta(days=1)).isoformat()}T12:00:00+0000"
    legacy_only = tmp_path / "legacy-only.db"
    _seed_legacy_feed(
        legacy_only,
        [(1, "AAPL", "Legacy only", "", "u", "P", "finnhub", recent, "h")],
    )

    legacy_feed = SqliteBackend(legacy_only).query_news_feed(days=30)
    assert legacy_feed["available"] is True
    assert legacy_feed["content_counts"] == {
        "full": 0,
        "headline_only": 0,
        "unknown": 1,
    }
    assert legacy_feed["items"][0]["content_availability"] == "unknown"

    partial = _seed_content_feed(tmp_path, "partial.db")
    conn = sqlite3.connect(partial)
    try:
        conn.execute("DROP TABLE news_legacy_projection_map")
        conn.commit()
    finally:
        conn.close()

    partial_feed = SqliteBackend(partial).query_news_feed(days=30)
    assert partial_feed["available"] is True
    assert partial_feed["content_counts"] == {
        "full": 1,
        "headline_only": 3,
        "unknown": 5,
    }


def test_headline_only_search_uses_existing_legacy_title_and_description_only(
    tmp_path: Path,
) -> None:
    backend = SqliteBackend(_seed_content_feed(tmp_path))

    title_hit = backend.query_news_feed(
        q="beacon", content="headline_only", days=30)
    normalized_body_only_term = backend.query_news_feed(
        q="normalizedonlyburiedterm", content="all", days=30)

    assert title_hit["total"] == 1
    assert title_hit["items"][0]["title"] == "Nvidia beacon headline"
    assert normalized_body_only_term["total"] == 0


def test_unavailable_feed_returns_additive_zero_shape(tmp_path: Path) -> None:
    db = tmp_path / "bare.db"
    sqlite3.connect(db).close()

    feed = SqliteBackend(db).query_news_feed()

    assert feed == {
        "available": False,
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
