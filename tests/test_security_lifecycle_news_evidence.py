from __future__ import annotations

import hashlib
import inspect
import sqlite3


def _context():
    from src.security_lifecycle_sec_evidence import build_identity_context

    return build_identity_context(
        case_id="case-hapn",
        observation={
            "ticker": "HAPN",
            "cik": "0001409970",
            "issuer_name": "Happify Network, Inc.",
            "filing_date": "2026-06-27",
            "source_ref": "0001409970-26-000131",
            "filing_form": "8-K",
            "filing_items": ["3.01"],
            "event_kinds": ["listing_status_review"],
        },
        ticker_aliases=("LC", "HAPN"),
        ibkr_conids=(112233,),
    )


def _normalized_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE news_articles (
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            provider_article_id TEXT,
            canonical_title TEXT NOT NULL,
            publisher TEXT,
            url TEXT,
            published_at TEXT NOT NULL,
            content_kind TEXT NOT NULL,
            language TEXT,
            story_group_id TEXT,
            archived_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE news_article_tickers (
            article_id INTEGER NOT NULL REFERENCES news_articles(id),
            ticker TEXT NOT NULL,
            relation_kind TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            PRIMARY KEY(article_id,ticker)
        );
        CREATE TABLE news_article_bodies (
            article_id INTEGER PRIMARY KEY REFERENCES news_articles(id),
            body_status TEXT NOT NULL,
            raw_body TEXT,
            raw_ref TEXT,
            raw_format TEXT,
            body_text TEXT,
            body_sha256 TEXT,
            cleaner_version TEXT,
            retrieval_method TEXT,
            retrieval_source TEXT,
            source_url TEXT,
            fetch_attempts INTEGER NOT NULL,
            last_attempt_at TEXT,
            next_retry_at TEXT,
            fetched_at TEXT,
            last_error TEXT,
            last_error_code INTEGER,
            unavailable_at TEXT,
            cleaned_at TEXT,
            clean_error TEXT
        );
        """
    )
    return conn


def _sa_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE sa_market_news (
            id INTEGER PRIMARY KEY,
            news_id TEXT NOT NULL UNIQUE,
            url TEXT NOT NULL,
            title TEXT NOT NULL,
            published_at TEXT,
            published_text TEXT,
            category TEXT,
            summary TEXT,
            comments_count INTEGER,
            raw_data TEXT,
            body_markdown TEXT,
            detail_fetched_at TEXT,
            fetched_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE sa_market_news_tickers (
            news_row_id INTEGER NOT NULL REFERENCES sa_market_news(id),
            ticker TEXT NOT NULL,
            PRIMARY KEY(news_row_id,ticker)
        );
        """
    )
    return conn


def _insert_normalized(
    conn,
    *,
    row_id=1,
    ticker="LC",
    published_at="2026-06-28T12:00:00Z",
    publisher="Reuters",
    source="polygon",
    title="LC adopts HAPN symbol",
    body="LC will trade as HAPN on Nasdaq.",
    url=None,
):
    conn.execute(
        "INSERT INTO news_articles VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            row_id,
            source,
            f"provider-{row_id}",
            title,
            publisher,
            url or f"https://news.example/{row_id}",
            published_at,
            "full_text",
            "en",
            None,
            None,
            published_at,
            published_at,
        ),
    )
    conn.execute(
        "INSERT INTO news_article_tickers VALUES (?,?,?,?,?)",
        (row_id, ticker, "primary", published_at, published_at),
    )
    conn.execute(
        "INSERT INTO news_article_bodies "
        "(article_id,body_status,body_text,fetch_attempts) VALUES (?,?,?,?)",
        (row_id, "fetched", body, 1),
    )
    conn.commit()


def _insert_sa(
    conn,
    *,
    row_id=1,
    ticker="HAPN",
    published_at="2026-06-29T12:00:00Z",
    title="HAPN begins Nasdaq trading",
    body="The issuer changed its symbol from LC to HAPN.",
):
    conn.execute(
        "INSERT INTO sa_market_news "
        "(id,news_id,url,title,published_at,summary,body_markdown) VALUES (?,?,?,?,?,?,?)",
        (
            row_id,
            f"sa-{row_id}",
            f"https://seekingalpha.com/news/{row_id}",
            title,
            published_at,
            body[:80],
            body,
        ),
    )
    conn.execute(
        "INSERT INTO sa_market_news_tickers VALUES (?,?)", (row_id, ticker)
    )
    conn.commit()


def _read(normalized, sa, **kwargs):
    from src.security_lifecycle_news_evidence import read_local_publisher_evidence

    return read_local_publisher_evidence(
        normalized_conn=normalized,
        sa_conn=sa,
        context=_context(),
        start_date="2026-05-28",
        end_date="2026-08-11",
        retrieved_at="2026-08-25T01:02:03Z",
        **kwargs,
    )


def test_news_adapter_requires_explicit_borrowed_connections_and_never_creates_schema():
    import src.security_lifecycle_news_evidence as module
    from src.security_lifecycle_news_evidence import read_local_publisher_evidence

    signature = inspect.signature(read_local_publisher_evidence)
    assert signature.parameters["normalized_conn"].default is inspect.Parameter.empty
    assert signature.parameters["sa_conn"].default is inspect.Parameter.empty
    assert all(param.kind is inspect.Parameter.KEYWORD_ONLY for param in signature.parameters.values())
    source = inspect.getsource(module)
    assert "sqlite3.connect" not in source
    assert "CREATE TABLE" not in source

    normalized = _normalized_conn()
    sa = _sa_conn()
    before = (
        normalized.total_changes,
        sa.total_changes,
        tuple(normalized.execute("SELECT name,sql FROM sqlite_master ORDER BY name")),
        tuple(sa.execute("SELECT name,sql FROM sqlite_master ORDER BY name")),
    )
    assert _read(normalized, sa).evidence == ()
    after = (
        normalized.total_changes,
        sa.total_changes,
        tuple(normalized.execute("SELECT name,sql FROM sqlite_master ORDER BY name")),
        tuple(sa.execute("SELECT name,sql FROM sqlite_master ORDER BY name")),
    )
    assert after == before


def test_news_adapter_reads_normalized_and_sa_rows_with_identity_and_date_bounds():
    normalized = _normalized_conn()
    sa = _sa_conn()
    _insert_normalized(normalized, row_id=1, ticker="LC")
    _insert_normalized(normalized, row_id=2, ticker="OTHER")
    _insert_normalized(normalized, row_id=3, ticker="HAPN", published_at="2025-01-01T00:00:00Z")
    _insert_sa(sa, row_id=1, ticker="HAPN")
    _insert_sa(sa, row_id=2, ticker="OTHER")

    result = _read(normalized, sa)

    assert result.blockers == ()
    assert {(item.source_locator["table"], item.source_locator["row_id"]) for item in result.evidence} == {
        ("news_articles", 1),
        ("sa_market_news", 1),
    }
    assert {item.source_locator["matched_tickers"] for item in result.evidence} == {
        ("HAPN",),
        ("LC",),
    }


def test_news_adapter_distinguishes_unavailable_schema_from_honest_empty():
    normalized = _normalized_conn()
    sa = _sa_conn()
    assert _read(normalized, sa).blockers == ()

    missing = sqlite3.connect(":memory:")
    result = _read(missing, sa)
    assert result.evidence == ()
    assert result.blockers == ("internal_news_schema_mismatch",)

    missing.close()
    result = _read(missing, sa)
    assert result.evidence == ()
    assert result.blockers == ("internal_news_unavailable",)


def test_news_adapter_bounds_rows_excerpts_and_preserves_original_provenance():
    normalized = _normalized_conn()
    sa = _sa_conn()
    for row_id in range(1, 5):
        _insert_normalized(
            normalized,
            row_id=row_id,
            published_at=f"2026-06-{20 + row_id:02d}T12:00:00Z",
            publisher=f"Wire {row_id}",
            body=f"Original {row_id} " + ("x" * 500),
        )

    result = _read(normalized, sa, max_rows=2, max_excerpt_bytes=64)

    assert len(result.evidence) == 2
    assert [item.publisher for item in result.evidence] == ["Wire 4", "Wire 3"]
    assert all(len(item.excerpt.encode()) <= 64 for item in result.evidence)
    assert result.evidence[0].excerpt.startswith("Original 4 ")
    assert result.evidence[0].source_url == "https://news.example/4"
    assert result.evidence[0].source_locator["provider_source"] == "polygon"
    assert result.truncated is True


def test_news_adapter_hashes_the_canonical_excerpt_when_truncation_ends_on_whitespace():
    from src.security_lifecycle_fact_kernel import _normalize_evidence

    normalized = _normalized_conn()
    sa = _sa_conn()
    _insert_normalized(
        normalized,
        body=("x" * 63) + "\ncontent beyond the boundary",
    )

    result = _read(normalized, sa, max_excerpt_bytes=64)

    evidence = result.evidence[0]
    assert len(evidence.excerpt.encode()) == 63
    assert evidence.excerpt == evidence.excerpt.strip()
    assert evidence.content_sha256 == hashlib.sha256(
        evidence.excerpt.encode()
    ).hexdigest()
    assert _normalize_evidence(result.evidence)[0].excerpt == evidence.excerpt


def test_news_adapter_rejects_invalid_urls_without_rejecting_the_evidence():
    from src.security_lifecycle_fact_kernel import _normalize_evidence

    normalized = _normalized_conn()
    sa = _sa_conn()
    _insert_normalized(
        normalized,
        row_id=1,
        url="http://news.example/insecure",
    )
    _insert_normalized(
        normalized,
        row_id=2,
        url="https://news.example/" + ("x" * 1000),
    )
    _insert_normalized(
        normalized,
        row_id=3,
        url="https://news.example/invalid\0path",
    )

    result = _read(normalized, sa)
    persisted = _normalize_evidence(result.evidence)
    by_row = {item.source_locator["row_id"]: item for item in result.evidence}

    assert len(persisted) == 3
    assert by_row[1].source_url is None
    assert by_row[1].source_locator["source_url_status"] == "rejected_non_https"
    assert by_row[2].source_url is None
    assert by_row[2].source_locator["source_url_status"] == "rejected_too_long"
    assert by_row[3].source_url is None
    assert by_row[3].source_locator["source_url_status"] == "rejected_invalid"


def test_all_news_publishers_count_as_one_publisher_family():
    normalized = _normalized_conn()
    sa = _sa_conn()
    _insert_normalized(normalized, row_id=1, publisher="Reuters")
    _insert_normalized(normalized, row_id=2, publisher="Dow Jones")
    _insert_sa(sa, row_id=1)

    result = _read(normalized, sa)

    assert {item.publisher for item in result.evidence} == {
        "Reuters",
        "Dow Jones",
        "Seeking Alpha",
    }
    assert result.source_families == ("publisher",)
    assert result.corroboration_family_count == 1
