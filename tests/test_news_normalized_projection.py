import sqlite3
from types import SimpleNamespace

import pytest

import src.news_direct as news_direct
import src.news_providers as news_providers
from src.market_data_admin import (
    _NEWS_SCHEMA,
    _ensure_news_fts_triggers,
    _ensure_news_hash_unique,
)
from src.news_identity import canonical_article_hash
from src.news_normalized.legacy_projection import (
    LegacyProjectionConflict,
    project_article_uncommitted,
)
from src.news_normalized.models import ArticleCandidate, BodyCandidate, BodyStatus
from src.news_normalized.store import NormalizedNewsStore


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(_NEWS_SCHEMA)
    _ensure_news_hash_unique(connection)
    _ensure_news_fts_triggers(connection)
    yield connection
    connection.close()


@pytest.fixture
def store(conn):
    return NormalizedNewsStore(conn)


def article(
    provider_id="provider-1",
    *,
    source="polygon",
    title="Apple expands AI server program",
    publisher="Example Wire",
    url="https://example.test/apple-ai",
    published_at="2026-06-24T09:30:00-04:00",
    primary_ticker="AAPL",
    related_tickers=("MSFT",),
    raw_body=(
        "<article><p>Apple **expanded** its AI server program.</p>"
        "<p>Microsoft was named as a cloud partner.</p></article>"
    ),
):
    return ArticleCandidate(
        source=source,
        provider_article_id=provider_id,
        title=title,
        publisher=publisher,
        url=url,
        published_at=published_at,
        primary_ticker=primary_ticker,
        related_tickers=related_tickers,
        observed_at="2026-06-24T13:31:00Z",
        content_kind="full_text" if raw_body else "unknown",
        body=BodyCandidate(
            status=BodyStatus.FETCHED if raw_body else BodyStatus.PENDING,
            raw_body=raw_body,
            raw_format="html" if raw_body else None,
            retrieval_method="provider_api",
            retrieval_source=source,
            fetched_at="2026-06-24T13:31:00Z" if raw_body else None,
        ),
    )


def _projected_news(conn):
    return [
        dict(row)
        for row in conn.execute(
            "SELECT id,ticker,title,description,url,publisher,source,published_at,"
            "article_hash FROM news ORDER BY ticker"
        ).fetchall()
    ]


def _map_rows(conn):
    return [
        dict(row)
        for row in conn.execute(
            "SELECT article_id,ticker,legacy_news_id,projected_at "
            "FROM news_legacy_projection_map ORDER BY ticker"
        ).fetchall()
    ]


def _fts_match_count(conn, query):
    return conn.execute(
        "SELECT COUNT(*) FROM news_fts WHERE news_fts MATCH ?", (query,)
    ).fetchone()[0]


def _direct_writer_expected_row(candidate, ticker):
    raw = news_providers._article_to_raw(
        SimpleNamespace(
            ticker=ticker,
            title=candidate.title,
            description=candidate.body.raw_body or "",
            content="",
            url=candidate.url,
            publisher=candidate.publisher,
            published_at=candidate.published_at,
        )
    )
    return news_direct._article_row(raw, candidate.source)


def test_projects_one_normalized_article_to_one_legacy_row_per_ticker(store, conn):
    candidate = article()
    article_id = store.upsert(candidate).article_id

    result = project_article_uncommitted(conn, article_id)

    rows = _projected_news(conn)
    assert result.inserted == 2
    assert result.updated == 0
    assert [row["ticker"] for row in rows] == ["AAPL", "MSFT"]
    assert len(_map_rows(conn)) == 2
    assert all(row["title"] == "Apple expands AI server program" for row in rows)
    assert all(row["source"] == "polygon" for row in rows)
    assert all(row["published_at"] == "2026-06-24T13:30:00+0000" for row in rows)
    assert all(len(row["description"]) <= 500 for row in rows)
    assert all("<" not in row["description"] and "**" not in row["description"] for row in rows)
    assert all("Apple expanded its AI server program." in row["description"] for row in rows)
    assert {
        row["ticker"]: row["article_hash"] for row in rows
    } == {
        "AAPL": canonical_article_hash(
            "AAPL", "Apple expands AI server program", candidate.published_at
        ),
        "MSFT": canonical_article_hash(
            "MSFT", "Apple expands AI server program", candidate.published_at
        ),
    }
    assert _fts_match_count(conn, "server") == 2
    assert _fts_match_count(conn, "partner") == 2


def test_projection_rerun_is_noop_for_unchanged_mapped_rows(store, conn, monkeypatch):
    now = ["2026-06-24T13:31:00Z"]
    monkeypatch.setattr(
        "src.news_normalized.legacy_projection._now", lambda: now[0]
    )
    article_id = store.upsert(article()).article_id
    first = project_article_uncommitted(conn, article_id)
    first_ids = {row["ticker"]: row["id"] for row in _projected_news(conn)}
    first_rows = _projected_news(conn)
    first_map = _map_rows(conn)

    now[0] = "2026-06-24T13:32:00Z"
    second = project_article_uncommitted(conn, article_id)

    assert first.inserted == 2
    assert second.inserted == 0
    assert second.updated == 0
    assert conn.execute("SELECT COUNT(*) FROM news").fetchone()[0] == 2
    assert _projected_news(conn) == first_rows
    assert _map_rows(conn) == first_map
    assert {row["ticker"]: row["id"] for row in _projected_news(conn)} == first_ids
    assert [row["legacy_news_id"] for row in _map_rows(conn)] == [
        first_ids["AAPL"],
        first_ids["MSFT"],
    ]


def test_projection_updates_title_and_body_corrections_in_mapped_rows(store, conn, monkeypatch):
    now = ["2026-06-24T13:31:00Z"]
    monkeypatch.setattr(
        "src.news_normalized.legacy_projection._now", lambda: now[0]
    )
    article_id = store.upsert(article()).article_id
    project_article_uncommitted(conn, article_id)
    original_ids = {row["ticker"]: row["id"] for row in _projected_news(conn)}
    original_projection_times = {
        row["ticker"]: row["projected_at"] for row in _map_rows(conn)
    }

    conn.execute(
        "UPDATE news_articles SET canonical_title=?,updated_at=? WHERE id=?",
        (
            "Apple expands corrected server program",
            "2026-06-24T14:00:00Z",
            article_id,
        ),
    )
    conn.execute(
        "UPDATE news_article_bodies SET body_text=? WHERE article_id=?",
        (
            "Corrected clean body mentions rackscale accelerators and partner capacity.",
            article_id,
        ),
    )
    now[0] = "2026-06-24T14:01:00Z"
    result = project_article_uncommitted(conn, article_id)

    rows = _projected_news(conn)
    assert result.inserted == 0
    assert result.updated == 2
    assert {row["ticker"]: row["id"] for row in rows} == original_ids
    assert {row["title"] for row in rows} == {"Apple expands corrected server program"}
    assert all("rackscale accelerators" in row["description"] for row in rows)
    assert all(
        row["article_hash"]
        == canonical_article_hash(
            row["ticker"], row["title"], "2026-06-24T09:30:00-04:00"
        )
        for row in rows
    )
    assert {
        row["ticker"]: row["projected_at"] for row in _map_rows(conn)
    } == {
        ticker: "2026-06-24T14:01:00Z" for ticker in original_projection_times
    }
    assert _fts_match_count(conn, "rackscale") == 2
    assert _fts_match_count(conn, "expanded") == 2
    assert _fts_match_count(conn, "partner") == 2


def test_article_without_tickers_is_skipped_without_legacy_writes(store, conn):
    article_id = store.upsert(
        article(provider_id="untickered", primary_ticker=None, related_tickers=())
    ).article_id

    result = project_article_uncommitted(conn, article_id)

    assert result.skipped_no_ticker == 1
    assert result.inserted == 0
    assert result.updated == 0
    assert conn.execute("SELECT COUNT(*) FROM news").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM news_legacy_projection_map").fetchone()[0] == 0


def test_incompatible_legacy_hash_ownership_raises_and_caller_can_roll_back(store, conn):
    article_id = store.upsert(article()).article_id
    published = "2026-06-24T13:30:00+0000"
    owned_hash = canonical_article_hash(
        "MSFT", "Apple expands AI server program", published
    )
    conn.execute(
        "INSERT INTO news "
        "(ticker,title,description,url,publisher,source,published_at,article_hash) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (
            "TSLA",
            "Different article owns the hash",
            "legacy owner",
            "https://example.test/conflict",
            "Other Wire",
            "finnhub",
            published,
            owned_hash,
        ),
    )
    conn.commit()

    conn.execute("BEGIN IMMEDIATE")
    conn.execute(
        "INSERT INTO news "
        "(ticker,title,description,url,publisher,source,published_at,article_hash) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (
            "ZZZ",
            "caller pending row",
            "pending",
            "",
            "",
            "polygon",
            published,
            "caller-pending-hash",
        ),
    )
    with pytest.raises(LegacyProjectionConflict):
        project_article_uncommitted(conn, article_id)
    conn.rollback()

    assert (
        conn.execute("SELECT COUNT(*) FROM news WHERE ticker='ZZZ'").fetchone()[0]
        == 0
    )
    assert (
        conn.execute("SELECT COUNT(*) FROM news WHERE ticker='AAPL'").fetchone()[0]
        == 0
    )
    assert conn.execute("SELECT COUNT(*) FROM news_legacy_projection_map").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM news").fetchone()[0] == 1


def test_adopts_existing_compatible_legacy_row_and_fts_stays_consistent(store, conn):
    article_id = store.upsert(
        article(
            provider_id="adopt-me",
            title="Finnhub-compatible adoption",
            source="finnhub",
            url="https://example.test/finnhub-compatible",
            publisher="Finnhub Wire",
            primary_ticker="AAPL",
            related_tickers=(),
            published_at="2026-06-25T15:00:00Z",
            raw_body="Finnhub body before normalized projection.",
        )
    ).article_id
    published = "2026-06-25T15:00:00+0000"
    legacy_hash = canonical_article_hash(
        "AAPL", "Finnhub-compatible adoption", published
    )
    conn.execute(
        "INSERT INTO news "
        "(ticker,title,description,url,publisher,source,published_at,article_hash) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (
            "AAPL",
            "Finnhub-compatible adoption",
            "old description",
            "https://example.test/finnhub-compatible",
            "Finnhub Wire",
            "finnhub",
            published,
            legacy_hash,
        ),
    )
    legacy_id = conn.execute("SELECT id FROM news").fetchone()[0]

    result = project_article_uncommitted(conn, article_id)
    rows = _projected_news(conn)

    assert result.inserted == 0
    assert result.updated == 1
    assert len(rows) == 1
    assert rows[0]["id"] == legacy_id
    assert rows[0]["description"] == "Finnhub body before normalized projection."
    assert _map_rows(conn)[0]["legacy_news_id"] == legacy_id
    assert _fts_match_count(conn, "normalized") == 1
    conn.execute("DELETE FROM news WHERE id=?", (legacy_id,))
    assert _fts_match_count(conn, "normalized") == 0


def test_adopts_cross_source_duplicate_legacy_row_for_same_ticker_title_date(
    store, conn
):
    title = "Market indexes close out June with a tech-fueled rally"
    polygon_article_id = store.upsert(
        article(
            provider_id="polygon-cross-source-owner",
            title=title,
            source="polygon",
            url="https://www.fool.com/investing/2026/06/30/market-indexes/",
            publisher="Motley Fool",
            primary_ticker="AAPL",
            related_tickers=(),
            published_at="2026-06-30T17:11:25+0000",
            raw_body="Polygon already projected this syndicated article.",
        )
    ).article_id
    first = project_article_uncommitted(conn, polygon_article_id)
    legacy_id = conn.execute("SELECT id FROM news").fetchone()[0]

    finnhub_article_id = store.upsert(
        article(
            provider_id="finnhub-cross-source-duplicate",
            title=title,
            source="finnhub",
            url="https://finnhub.io/api/news?id=cross-source",
            publisher="Finnhub",
            primary_ticker="AAPL",
            related_tickers=(),
            published_at="2026-06-30T17:31:25Z",
            raw_body="Finnhub summary for the same syndicated article.",
        )
    ).article_id

    result = project_article_uncommitted(conn, finnhub_article_id)

    assert first.inserted == 1
    assert result.inserted == 0
    assert result.updated == 0
    rows = _projected_news(conn)
    assert len(rows) == 1
    assert rows[0]["id"] == legacy_id
    assert rows[0]["source"] == "polygon"
    assert rows[0]["description"] == "Polygon already projected this syndicated article."
    assert _map_rows(conn) == [
        {
            "article_id": polygon_article_id,
            "ticker": "AAPL",
            "legacy_news_id": legacy_id,
            "projected_at": _map_rows(conn)[0]["projected_at"],
        }
    ]


def test_adopts_same_source_duplicate_legacy_row_already_mapped_to_other_article(
    store, conn
):
    title = "IBKR duplicate headline"
    first_article_id = store.upsert(
        article(
            provider_id="ibkr-duplicate-owner",
            title=title,
            source="ibkr",
            url="https://ibkr.example.test/owner",
            publisher="IBKR",
            primary_ticker="AAPL",
            related_tickers=(),
            published_at="2026-06-30T20:39:00Z",
            raw_body="First IBKR body.",
        )
    ).article_id
    first = project_article_uncommitted(conn, first_article_id)
    legacy_id = conn.execute("SELECT id FROM news").fetchone()[0]

    duplicate_article_id = store.upsert(
        article(
            provider_id="ibkr-duplicate-second-id",
            title=title,
            source="ibkr",
            url="https://ibkr.example.test/duplicate",
            publisher="IBKR",
            primary_ticker="AAPL",
            related_tickers=(),
            published_at="2026-06-30T20:40:00Z",
            raw_body="Second IBKR body for the same legacy hash.",
        )
    ).article_id

    result = project_article_uncommitted(conn, duplicate_article_id)

    assert first.inserted == 1
    assert result.inserted == 0
    assert result.updated == 0
    rows = _projected_news(conn)
    assert len(rows) == 1
    assert rows[0]["id"] == legacy_id
    assert rows[0]["description"] == "First IBKR body."
    map_rows = _map_rows(conn)
    assert len(map_rows) == 1
    assert map_rows[0]["article_id"] == first_article_id
    assert map_rows[0]["legacy_news_id"] == legacy_id


@pytest.mark.parametrize(
    ("candidate", "ticker"),
    [
        (
            article(
                provider_id="poly-parity",
                source="polygon",
                title="Polygon parity article",
                publisher="Polygon Publisher",
                url="https://example.test/polygon-parity",
                published_at="2026-06-26T09:31:45-04:00",
                primary_ticker="AAPL",
                related_tickers=(),
                raw_body="Polygon projected body.",
            ),
            "AAPL",
        ),
        (
            article(
                provider_id="finn-parity",
                source="finnhub",
                title="Finnhub parity article",
                publisher="Finnhub Publisher",
                url="https://example.test/finnhub-parity",
                published_at="2026-06-26T13:31:45Z",
                primary_ticker="MSFT",
                related_tickers=(),
                raw_body="Finnhub projected body.",
            ),
            "MSFT",
        ),
        (
            article(
                provider_id="poly-boundary-parity",
                source="polygon",
                title="Polygon boundary parity article",
                publisher="Polygon Publisher",
                url="https://example.test/polygon-boundary-parity",
                published_at="2026-06-26T23:30:00-04:00",
                primary_ticker="AAPL",
                related_tickers=(),
                raw_body="Polygon boundary projected body.",
            ),
            "AAPL",
        ),
    ],
)
def test_polygon_and_finnhub_projection_matches_direct_writer_row(
    store, conn, candidate, ticker
):
    article_id = store.upsert(candidate).article_id

    result = project_article_uncommitted(conn, article_id)

    row = _projected_news(conn)[0]
    assert result.inserted == 1
    assert (
        row["ticker"],
        row["title"],
        row["description"],
        row["url"],
        row["publisher"],
        row["source"],
        row["published_at"],
        row["article_hash"],
    ) == _direct_writer_expected_row(candidate, ticker)


def test_direct_writer_hash_parity_preserves_provider_date_across_utc_boundary(
    store, conn
):
    candidate = article(
        provider_id="utc-boundary",
        source="polygon",
        title="Late session article crosses UTC date",
        publisher="Polygon Publisher",
        url="https://example.test/utc-boundary",
        published_at="2026-06-26T23:30:00-04:00",
        primary_ticker="AAPL",
        related_tickers=(),
        raw_body="Late session projected body.",
    )
    article_id = store.upsert(candidate).article_id

    result = project_article_uncommitted(conn, article_id)

    row = _projected_news(conn)[0]
    expected = _direct_writer_expected_row(candidate, "AAPL")
    assert result.inserted == 1
    assert row["published_at"] == "2026-06-27T03:30:00+0000"
    assert expected[6] == "2026-06-27T03:30:00+0000"
    assert row["article_hash"] == expected[7]
    assert expected[7] == canonical_article_hash(
        "AAPL", "Late session article crosses UTC date", "2026-06-26T23:30:00-04:00"
    )
    assert expected[7] != canonical_article_hash(
        "AAPL", "Late session article crosses UTC date", row["published_at"]
    )
