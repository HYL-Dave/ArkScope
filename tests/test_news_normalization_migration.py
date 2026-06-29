import json
import sqlite3
from pathlib import Path
import subprocess
import sys

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.news_identity import canonical_article_hash
from src.news_normalized.identity import normalize_identity_text, normalize_stable_url, normalize_timestamp
from src.news_normalized.migration import (
    MigrationPlanDriftError,
    build_resolved_plan,
    inventory_inputs,
    iter_legacy_news,
    iter_parquet_news,
    plan_news_normalization,
    require_expected_counts,
)
from src.news_normalized.migration_policy import (
    BodyEvidenceRef,
    LegacyEvidence,
    PolicyGroup,
    reject_weak_legacy,
    resolve_body_variants,
    resolve_polygon_shared_url,
    resolve_timestamp_drift,
    N7_POLICY_VERSION,
)
from src.news_normalized.models import KeyKind


def policy_group(
    *,
    source="polygon",
    provider_ids=("id",),
    titles=("Same",),
    urls=("https://example.test/shared",),
    published_at=("2026-06-29T10:00:00Z",),
    tickers=("AAPL",),
    sentiment_values=(),
    bodies=(),
):
    return PolicyGroup(
        source=source,
        identity=f"synthetic:{provider_ids[0]}",
        provider_ids=tuple(provider_ids),
        normalized_titles=tuple(normalize_identity_text(item) for item in titles),
        normalized_urls=tuple(normalize_stable_url(item) for item in urls),
        publication_dates=tuple(
            normalize_timestamp(item)[:10] for item in published_at
        ),
        published_at=tuple(published_at),
        tickers=tuple(tickers),
        sentiment_values=tuple(sentiment_values),
        body_refs=tuple(bodies),
    )


def legacy_evidence(*, legacy_id, ticker, sentiment):
    return LegacyEvidence(
        legacy_news_id=legacy_id,
        canonical_ticker=ticker,
        sentiment_value=sentiment,
    )


def body_ref(*, digest, clean_length, raw_length):
    return BodyEvidenceRef(
        source_path="synthetic.parquet",
        row_group=0,
        row_index=0,
        body_sha256=digest,
        raw_length=raw_length,
        clean_length=clean_length,
        cleaner_ok=True,
        fetched_at=None,
    )


def test_same_provider_id_title_url_with_different_times_is_timestamp_drift():
    group = policy_group(
        source="finnhub",
        provider_ids=("synthetic-id",),
        titles=("Same title",),
        urls=("https://example.test/story",),
        published_at=("2026-01-01T00:00:00Z", "2026-06-01T00:00:00Z"),
    )
    resolved = resolve_timestamp_drift(group)
    assert resolved.canonical_published_at == "2026-01-01T00:00:00Z"
    assert resolved.resolution_kind == "provider_timestamp_drift"


def test_same_polygon_url_title_and_day_merges_provider_groups():
    groups = (
        policy_group(source="polygon", provider_ids=("id-a",), titles=("Same",)),
        policy_group(source="polygon", provider_ids=("id-b",), titles=("Same",)),
    )
    resolved = resolve_polygon_shared_url(groups)
    assert resolved.action == "merge"
    assert resolved.canonical_provider_id == "id-a"
    assert resolved.provider_ids == ("id-a", "id-b")
    assert all(key.kind is not KeyKind.URL for key in resolved.identity_keys)


def test_polygon_shared_url_with_different_metadata_stays_separate():
    groups = (
        policy_group(source="polygon", provider_ids=("id-a",), titles=("First",)),
        policy_group(source="polygon", provider_ids=("id-b",), titles=("Second",)),
    )
    resolved = resolve_polygon_shared_url(groups)
    assert resolved.action == "demote"
    assert len(resolved.groups) == 2
    assert all(
        key.kind is not KeyKind.URL
        for group in resolved.groups
        for key in group.identity_keys
    )


def test_weak_ambiguity_reports_unique_legacy_evidence():
    rejected = reject_weak_legacy(
        legacy_evidence(legacy_id=42, ticker="UNIQUE", sentiment=4.0),
        candidates=(
            policy_group(tickers=("AAPL",), sentiment_values=(3.0,)),
            policy_group(tickers=("MSFT",), sentiment_values=(3.0,)),
        ),
    )
    assert rejected.ticker_unique is True
    assert rejected.sentiment_present is True
    assert rejected.sentiment_unique is True


def test_body_variants_choose_one_active_and_keep_other_digests():
    bodies = (
        body_ref(digest="a" * 64, clean_length=5, raw_length=5),
        body_ref(digest="b" * 64, clean_length=20, raw_length=20),
    )
    active, cold = resolve_body_variants(bodies)
    assert active.body_sha256 == "b" * 64
    assert [item.body_sha256 for item in cold] == ["a" * 64]


def test_migration_policy_has_no_live_audit_allowlist():
    policy = Path("src/news_normalized/migration_policy.py").read_text()
    forbidden = ("DJ-N$", "DJ-RTA$", "api.polygon.io/v2/reference/news")
    assert not any(item in policy for item in forbidden)


def _legacy_db(path: Path):
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE news ("
        "id INTEGER PRIMARY KEY,ticker TEXT,title TEXT,description TEXT,url TEXT,"
        "publisher TEXT,source TEXT,published_at TEXT,article_hash TEXT,"
        "sentiment_score REAL,sentiment_source TEXT,sentiment_scale TEXT)"
    )
    rows = [
        (1, "AAPL", "Shared", "", "", "DJ-N", "ibkr", "2026-06-27T10:00:00Z"),
        (2, "MSFT", "Shared", "", "", "DJ-N", "ibkr", "2026-06-27T10:00:00Z"),
        (3, "NVDA", "Fallback only", "", "", "Polygon", "polygon", "2026-06-27T11:00:00Z"),
        (4, "IBM", "IBKR fallback", "", "", "DJ-N", "ibkr", "2026-06-27T13:00:00Z"),
    ]
    conn.executemany(
        "INSERT INTO news "
        "(id,ticker,title,description,url,publisher,source,published_at,article_hash) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        [
            row
            + (canonical_article_hash(row[1], row[2], row[7]),)
            for row in rows
        ],
    )
    conn.commit()
    conn.close()


def _parquet(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(
        [
            {
                "article_id": "DJ-N$1",
                "ticker": "AAPL",
                "title": "Shared",
                "published_at": "2026-06-27T10:00:00Z",
                "source_api": "ibkr",
                "description": "",
                "content": "full body",
                "url": "",
                "publisher": "DJ-N",
                "related_tickers": '["AAPL","MSFT"]',
                "collected_at": "2026-06-27T10:01:00Z",
                "content_status": "fetched",
                "content_fetch_attempts": 1,
                "content_fetched_at": "2026-06-27T10:01:00Z",
            },
            {
                "article_id": "DJ-N$1",
                "ticker": "MSFT",
                "title": "Shared",
                "published_at": "2026-06-27T10:00:00Z",
                "source_api": "ibkr",
                "description": "",
                "content": "",
                "url": "",
                "publisher": "DJ-N",
                "related_tickers": '["AAPL","MSFT"]',
                "collected_at": "2026-06-27T10:02:00Z",
                "content_status": "pending",
                "content_fetch_attempts": 0,
                "content_fetched_at": "",
            },
            {
                "article_id": "DJ-N$2",
                "ticker": "TSLA",
                "title": "Missing",
                "published_at": "2026-06-27T12:00:00Z",
                "source_api": "ibkr",
                "description": "",
                "content": "",
                "url": "",
                "publisher": "DJ-N",
                "related_tickers": "bad-json",
                "collected_at": "2026-06-27T12:01:00Z",
                "content_status": "failed",
                "content_fetch_attempts": 1,
                "content_fetched_at": "",
            },
        ]
    )
    pq.write_table(table, path)


def _snapshot_inputs(db, paths):
    return tuple(
        (str(path.resolve()), path.stat().st_size, path.stat().st_mtime_ns, path.stat().st_ino)
        for path in (Path(db), *(Path(item) for item in paths))
    )


def _weak_rejection_fixture(tmp_path):
    db = tmp_path / "market.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE news ("
        "id INTEGER PRIMARY KEY,ticker TEXT,title TEXT,description TEXT,url TEXT,"
        "publisher TEXT,source TEXT,published_at TEXT,article_hash TEXT,"
        "sentiment_score REAL,sentiment_source TEXT,sentiment_scale TEXT)"
    )
    published = "2026-06-27T10:00:00Z"
    rows = (
        (1, "AAPL", 3.0, ""),
        (2, "UNIQUE", 4.0, ""),
        (3, "AAPL", 3.0, "https://example.test/a"),
        (4, "MSFT", 3.0, "https://example.test/b"),
    )
    for legacy_id, ticker, sentiment, url in rows:
        conn.execute(
            "INSERT INTO news VALUES (?,?,?,?,?,?,?,?,?,?,NULL,NULL)",
            (
                legacy_id,
                ticker,
                "Ambiguous",
                "",
                url,
                "Wire",
                "ibkr",
                published,
                canonical_article_hash(ticker, "Ambiguous", published),
                sentiment,
            ),
        )
    conn.commit()
    conn.close()

    parquet = tmp_path / "raw" / "ibkr" / "2026" / "weak.parquet"
    parquet.parent.mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "article_id": provider_id,
                    "ticker": "AAPL",
                    "title": "Ambiguous",
                    "published_at": published,
                    "source_api": "ibkr",
                    "description": "",
                    "content": "",
                    "url": f"https://example.test/{suffix}",
                    "publisher": "Wire",
                    "related_tickers": '["AAPL"]',
                }
                for provider_id, suffix in (("synthetic-a", "a"), ("synthetic-b", "b"))
            ]
        ),
        parquet,
    )
    return db, [parquet]


def test_resolved_preview_has_all_three_fingerprints(tmp_path):
    db = tmp_path / "market.db"
    _legacy_db(db)
    parquet = tmp_path / "raw" / "ibkr" / "2026" / "input.parquet"
    _parquet(parquet)

    preview = plan_news_normalization(db, [parquet])

    assert len(preview.input_fingerprint) == 64
    assert preview.policy_version == N7_POLICY_VERSION
    assert len(preview.resolved_fingerprint) == 64
    assert len(preview.rejection_evidence.fingerprint) == 64


def test_rejection_summary_counts_unique_ticker_and_sentiment(tmp_path):
    db, paths = _weak_rejection_fixture(tmp_path)

    summary = plan_news_normalization(db, paths).rejection_evidence

    assert summary.rejected_rows == 2
    assert summary.rows_with_unique_ticker == 1
    assert summary.unique_ticker_relations == 1
    assert summary.rows_with_sentiment == 2
    assert summary.rows_with_unique_sentiment == 1


def test_rejection_fingerprint_changes_with_unique_evidence(tmp_path):
    db, paths = _weak_rejection_fixture(tmp_path)
    first = plan_news_normalization(db, paths).rejection_evidence.fingerprint
    conn = sqlite3.connect(db)
    conn.execute("UPDATE news SET ticker='UNIQUE2' WHERE id=2")
    conn.commit()
    conn.close()

    second = plan_news_normalization(db, paths).rejection_evidence.fingerprint

    assert second != first


def test_resolved_fingerprint_is_input_order_independent(tmp_path):
    db = tmp_path / "market.db"
    _legacy_db(db)
    first_path = tmp_path / "raw" / "ibkr" / "2026" / "a.parquet"
    second_path = tmp_path / "raw" / "ibkr" / "2026" / "b.parquet"
    _parquet(first_path)
    _parquet(second_path)

    first = plan_news_normalization(db, [first_path, second_path])
    second = plan_news_normalization(db, [second_path, first_path])

    assert second.resolved_fingerprint == first.resolved_fingerprint


def test_resolved_preview_is_zero_mutation(tmp_path):
    db = tmp_path / "market.db"
    _legacy_db(db)
    parquet = tmp_path / "raw" / "ibkr" / "2026" / "input.parquet"
    _parquet(parquet)
    before = _snapshot_inputs(db, [parquet])

    plan = build_resolved_plan(db, [parquet])

    assert _snapshot_inputs(db, [parquet]) == before
    assert plan.preview.would_apply is True
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    count = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name LIKE 'news_article%'"
    ).fetchone()[0]
    conn.close()
    assert count == 0


def test_failed_article_without_attempts_blocks_apply(tmp_path):
    """A resolved article that is failed with zero fetch attempts violates the
    apply-time body-state invariant (validate_applied_plan rejects
    ``body_status='failed' AND fetch_attempts=0``). The preview must block it
    rather than defer the failure to the live apply transaction."""
    db = tmp_path / "market.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE news ("
        "id INTEGER PRIMARY KEY,ticker TEXT,title TEXT,description TEXT,url TEXT,"
        "publisher TEXT,source TEXT,published_at TEXT,article_hash TEXT,"
        "sentiment_score REAL,sentiment_source TEXT,sentiment_scale TEXT)"
    )
    conn.commit()
    conn.close()
    parquet = tmp_path / "raw" / "ibkr" / "2026" / "failed.parquet"
    parquet.parent.mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "article_id": "failed-no-attempts",
                    "ticker": "AAPL",
                    "title": "Failed brief",
                    "published_at": "2026-06-27T10:00:00Z",
                    "source_api": "ibkr",
                    "description": "",
                    "content": "",
                    "url": "https://example.test/failed",
                    "publisher": "Wire",
                    "related_tickers": '["AAPL"]',
                    "content_status": "failed",
                    "content_fetch_attempts": 0,
                }
            ]
        ),
        parquet,
    )

    plan = build_resolved_plan(db, [parquet])

    # Precondition: the single article is failed via content_status, with no
    # body and no recorded attempts.
    article = plan.articles[0]
    assert article.body_status.value == "failed"
    assert article.fetch_attempts == 0
    # The preview must refuse to apply and name the offending article.
    assert plan.preview.would_apply is False
    assert any(
        blocker.kind == "body_failed_without_attempts"
        for blocker in plan.preview.remaining_blockers
    )


def test_polygon_demoted_url_uses_unique_ticker_mention_not_weak_rejection(tmp_path):
    db = tmp_path / "market.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE news ("
        "id INTEGER PRIMARY KEY,ticker TEXT,title TEXT,description TEXT,url TEXT,"
        "publisher TEXT,source TEXT,published_at TEXT,article_hash TEXT,"
        "sentiment_score REAL,sentiment_source TEXT,sentiment_scale TEXT)"
    )
    published = "2026-06-27T10:00:00Z"
    conn.execute(
        "INSERT INTO news VALUES (1,'AAPL','Shared','','https://example.test/reused',"
        "'Wire','polygon',?,?,NULL,NULL,NULL)",
        (published, canonical_article_hash("AAPL", "Shared", published)),
    )
    conn.commit()
    conn.close()
    parquet = tmp_path / "raw" / "polygon" / "2026" / "input.parquet"
    parquet.parent.mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "article_id": "id-a",
                    "ticker": "AAPL",
                    "title": title,
                    "published_at": published,
                    "source_api": "polygon",
                    "url": "https://example.test/reused",
                    "publisher": "Wire",
                    "related_tickers": '["AAPL"]',
                }
                for title in ("Shared", "Revised")
            ]
            + [
                {
                    "article_id": "id-b",
                    "ticker": "MSFT",
                    "title": "Shared",
                    "published_at": published,
                    "source_api": "polygon",
                    "url": "https://example.test/reused",
                    "publisher": "Wire",
                    "related_tickers": '["MSFT"]',
                }
            ]
        ),
        parquet,
    )

    preview = plan_news_normalization(db, [parquet])

    assert preview.counts["polygon_url_demotions"] == 1
    assert preview.rejection_evidence.rejected_rows == 0
    assert preview.counts["legacy_mapped"] == 1


def test_polygon_distinct_urls_with_same_metadata_preserve_articles_and_reject_legacy(
    tmp_path,
):
    db = tmp_path / "market.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE news ("
        "id INTEGER PRIMARY KEY,ticker TEXT,title TEXT,description TEXT,url TEXT,"
        "publisher TEXT,source TEXT,published_at TEXT,article_hash TEXT,"
        "sentiment_score REAL,sentiment_source TEXT,sentiment_scale TEXT)"
    )
    published = "2026-06-27T10:00:00Z"
    conn.execute(
        "INSERT INTO news VALUES (1,'AAPL','Same','','','Wire','polygon',?,?,"
        "NULL,NULL,NULL)",
        (published, canonical_article_hash("AAPL", "Same", published)),
    )
    conn.commit()
    conn.close()
    parquet = tmp_path / "raw" / "polygon" / "2026" / "input.parquet"
    parquet.parent.mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "article_id": provider_id,
                    "ticker": "AAPL",
                    "title": "Same",
                    "published_at": published,
                    "source_api": "polygon",
                    "url": f"https://example.test/{suffix}",
                    "publisher": "Wire",
                    "related_tickers": '["AAPL"]',
                }
                for provider_id, suffix in (("id-a", "a"), ("id-b", "b"))
            ]
        ),
        parquet,
    )

    preview = plan_news_normalization(db, [parquet])

    assert preview.sources["polygon"].planned_articles == 2
    assert preview.rejection_evidence.rejected_rows == 1
    assert preview.counts["legacy_mapped"] == 0
    assert preview.would_apply is True


def test_resolved_preview_blocks_duplicate_non_polygon_strong_url(tmp_path):
    db = tmp_path / "market.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE news ("
        "id INTEGER PRIMARY KEY,ticker TEXT,title TEXT,description TEXT,url TEXT,"
        "publisher TEXT,source TEXT,published_at TEXT,article_hash TEXT,"
        "sentiment_score REAL,sentiment_source TEXT,sentiment_scale TEXT)"
    )
    conn.commit()
    conn.close()
    parquet = tmp_path / "raw" / "finnhub" / "2026" / "input.parquet"
    parquet.parent.mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "article_id": provider_id,
                    "ticker": "AAPL",
                    "title": title,
                    "published_at": published,
                    "source_api": "finnhub",
                    "url": "https://example.test/reused",
                    "publisher": "Wire",
                }
                for provider_id, title, published in (
                    ("id-a", "First", "2026-06-27T10:00:00Z"),
                    ("id-b", "Second", "2026-06-28T10:00:00Z"),
                )
            ]
        ),
        parquet,
    )

    preview = plan_news_normalization(db, [parquet])

    assert preview.would_apply is False
    assert [item.kind for item in preview.remaining_blockers] == [
        "strong_key_multiple_owners"
    ]


def test_reviewed_expected_counts_refuse_rejection_drift(tmp_path):
    db, paths = _weak_rejection_fixture(tmp_path)
    preview = plan_news_normalization(db, paths)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO news SELECT 5,'THIRD',title,description,url,publisher,source,"
        "published_at,article_hash,5.0,sentiment_source,sentiment_scale "
        "FROM news WHERE id=1"
    )
    conn.commit()
    conn.close()
    changed = plan_news_normalization(db, paths)

    with pytest.raises(MigrationPlanDriftError):
        require_expected_counts(
            changed,
            {"legacy_rejected": preview.counts["legacy_rejected"]},
        )


def test_legacy_loader_opens_sqlite_read_only(tmp_path):
    db = tmp_path / "market.db"
    _legacy_db(db)
    before = db.read_bytes()
    rows = list(iter_legacy_news(db, batch_size=2))
    assert len(rows) == 4
    assert rows[0]["id"] == 1
    assert db.read_bytes() == before
    assert not Path(f"{db}-wal").exists()
    assert not Path(f"{db}-shm").exists()


def test_parquet_loader_streams_batches_and_optional_columns(tmp_path):
    path = tmp_path / "ibkr" / "2026" / "2026-06.parquet"
    _parquet(path)
    batches = list(iter_parquet_news([path], batch_size=2))
    assert [len(batch) for batch in batches] == [2, 1]
    assert batches[0][0].provider_article_id == "DJ-N$1"
    assert batches[0][0].related_tickers == ("AAPL", "MSFT")
    assert batches[1][0].related_tickers == ()


def test_parquet_loader_exposes_stable_row_group_locators(tmp_path):
    path = tmp_path / "ibkr" / "2026" / "2026-06.parquet"
    _parquet(path)
    table = pq.read_table(path)
    pq.write_table(table, path, row_group_size=2)

    evidence = [item for batch in iter_parquet_news([path]) for item in batch]

    assert [(item.row_group, item.row_index) for item in evidence] == [
        (0, 0),
        (0, 1),
        (1, 0),
    ]


def test_inventory_aggregates_body_by_provider_article_not_ticker_row(tmp_path):
    db = tmp_path / "market.db"
    _legacy_db(db)
    path = tmp_path / "raw" / "ibkr" / "2026" / "2026-06.parquet"
    _parquet(path)
    report = inventory_inputs(db, [path])
    ibkr = report.sources["ibkr"]
    assert ibkr.legacy_rows == 3
    assert ibkr.parquet_rows == 3
    assert ibkr.distinct_provider_ids == 2
    assert ibkr.provider_articles_with_body == 1
    assert ibkr.provider_articles_without_body == 1
    assert ibkr.sqlite_rows_matched_to_parquet == 2
    assert ibkr.sqlite_rows_with_parquet_body == 2
    assert ibkr.sqlite_match_rate == 0.666667
    assert ibkr.body_match_rate == 0.666667
    polygon = report.sources["polygon"]
    assert polygon.legacy_rows == 1
    assert polygon.parquet_rows == 0


def test_inventory_records_input_file_metadata_without_body_content(tmp_path):
    db = tmp_path / "market.db"
    _legacy_db(db)
    path = tmp_path / "raw" / "ibkr" / "2026" / "2026-06.parquet"
    _parquet(path)
    report = inventory_inputs(db, [path])
    file_row = report.parquet_files[0]
    assert file_row.path == str(path)
    assert file_row.rows == 3
    assert file_row.size_bytes == path.stat().st_size
    assert "full body" not in repr(report)


def test_preview_reports_provider_matches_fallback_blast_and_collapse(tmp_path):
    db = tmp_path / "market.db"
    _legacy_db(db)
    path = tmp_path / "raw" / "ibkr" / "2026" / "2026-06.parquet"
    _parquet(path)
    preview = plan_news_normalization(db, [path])
    ibkr = preview.sources["ibkr"]
    assert ibkr.legacy_rows == 3
    assert ibkr.planned_articles == 3
    assert ibkr.provider_id_matched == 1
    assert ibkr.fallback_only == 1
    assert ibkr.body_fetched == 1
    assert ibkr.body_missing == 2
    assert preview.sources["polygon"].fallback_only == 1
    assert preview.cross_ticker_rows_collapsed == 1
    assert preview.planned_ticker_links == 5
    assert preview.planned_titles == 4
    assert preview.blocking_conflicts == ()
    assert preview.weak_ambiguities == ()
    assert preview.would_apply is True
    assert len(preview.fingerprint) == 64
    assert "full body" not in repr(preview)


def test_preview_fingerprint_is_deterministic_and_body_sensitive(tmp_path):
    db = tmp_path / "market.db"
    _legacy_db(db)
    path = tmp_path / "raw" / "ibkr" / "2026" / "2026-06.parquet"
    _parquet(path)
    first = plan_news_normalization(db, [path])
    second = plan_news_normalization(db, list(reversed([path])))
    assert first.fingerprint == second.fingerprint

    table = pq.read_table(path)
    rows = table.to_pylist()
    rows[0]["content"] = "different body"
    pq.write_table(pa.Table.from_pylist(rows), path)
    changed = plan_news_normalization(db, [path])
    assert changed.fingerprint != first.fingerprint


def test_preview_blocks_provider_id_reuse_across_publication_dates(tmp_path):
    db = tmp_path / "market.db"
    _legacy_db(db)
    path = tmp_path / "raw" / "ibkr" / "2026" / "2026-06.parquet"
    _parquet(path)
    table = pq.read_table(path)
    rows = table.to_pylist()
    reused = dict(rows[0])
    reused["ticker"] = "META"
    reused["title"] = "Unrelated"
    reused["published_at"] = "2026-06-28T10:00:00Z"
    rows.append(reused)
    pq.write_table(pa.Table.from_pylist(rows), path)
    preview = plan_news_normalization(db, [path])
    assert preview.would_apply is False
    assert preview.blocking_conflicts[0].kind == "provider_id_reuse"


def test_preview_compares_provider_reuse_dates_in_utc(tmp_path):
    db = tmp_path / "market.db"
    _legacy_db(db)
    path = tmp_path / "raw" / "ibkr" / "2026" / "2026-06.parquet"
    path.parent.mkdir(parents=True)
    base = {
        "article_id": "same-instant",
        "ticker": "AAPL",
        "title": "Same instant",
        "source_api": "ibkr",
        "description": "",
        "content": "same body",
        "url": "",
        "publisher": "DJ-N",
        "related_tickers": '["AAPL"]',
    }
    pq.write_table(
        pa.Table.from_pylist(
            [
                {**base, "published_at": "2026-06-27T23:30:00-02:00"},
                {**base, "published_at": "2026-06-28T01:30:00Z"},
            ]
        ),
        path,
    )

    preview = plan_news_normalization(db, [path])

    assert all(
        conflict.kind != "provider_id_reuse"
        for conflict in preview.blocking_conflicts
    )


def test_preview_uses_stable_url_to_disambiguate_same_legacy_mention_hash(tmp_path):
    db = tmp_path / "market.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE news ("
        "id INTEGER PRIMARY KEY,ticker TEXT,title TEXT,description TEXT,url TEXT,"
        "publisher TEXT,source TEXT,published_at TEXT,article_hash TEXT,"
        "sentiment_score REAL,sentiment_source TEXT,sentiment_scale TEXT)"
    )
    published_at = "2026-06-27T10:00:00Z"
    mention_hash = canonical_article_hash("AAPL", "Shared wire title", published_at)
    conn.execute(
        "INSERT INTO news VALUES (1,'AAPL','Shared wire title','',?,"
        "'Wire','ibkr',?,?,NULL,NULL,NULL)",
        ("https://example.test/story/a?utm_source=feed", published_at, mention_hash),
    )
    conn.commit()
    conn.close()

    path = tmp_path / "raw" / "ibkr" / "2026" / "2026-06.parquet"
    path.parent.mkdir(parents=True)
    rows = []
    for provider_id, url in (
        ("wire-a", "https://example.test/story/a"),
        ("wire-b", "https://example.test/story/b"),
    ):
        rows.append(
            {
                "article_id": provider_id,
                "ticker": "AAPL",
                "title": "Shared wire title",
                "published_at": published_at,
                "source_api": "ibkr",
                "description": "",
                "content": "",
                "url": url,
                "publisher": "Wire",
                "related_tickers": '["AAPL"]',
            }
        )
    pq.write_table(pa.Table.from_pylist(rows), path)

    preview = plan_news_normalization(db, [path])

    assert preview.blocking_conflicts == ()
    assert preview.sources["ibkr"].provider_id_matched == 1
    assert preview.sources["ibkr"].fallback_only == 0


def test_preview_keeps_unresolved_fallback_match_as_weak_ambiguity(tmp_path):
    db = tmp_path / "market.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE news ("
        "id INTEGER PRIMARY KEY,ticker TEXT,title TEXT,description TEXT,url TEXT,"
        "publisher TEXT,source TEXT,published_at TEXT,article_hash TEXT,"
        "sentiment_score REAL,sentiment_source TEXT,sentiment_scale TEXT)"
    )
    published_at = "2026-06-27T10:00:00Z"
    mention_hash = canonical_article_hash("AAPL", "Shared wire title", published_at)
    conn.execute(
        "INSERT INTO news VALUES (1,'AAPL','Shared wire title','','',"
        "'Wire','ibkr',?,?,NULL,NULL,NULL)",
        (published_at, mention_hash),
    )
    conn.commit()
    conn.close()

    path = tmp_path / "raw" / "ibkr" / "2026" / "2026-06.parquet"
    path.parent.mkdir(parents=True)
    rows = [
        {
            "article_id": provider_id,
            "ticker": "AAPL",
            "title": "Shared wire title",
            "published_at": published_at,
            "source_api": "ibkr",
            "description": "",
            "content": "",
            "url": "",
            "publisher": "Wire",
            "related_tickers": '["AAPL"]',
        }
        for provider_id in ("wire-a", "wire-b")
    ]
    pq.write_table(pa.Table.from_pylist(rows), path)

    preview = plan_news_normalization(db, [path])

    assert preview.blocking_conflicts == ()
    assert [item.kind for item in preview.weak_ambiguities] == [
        "legacy_weak_identity_ambiguity"
    ]
    assert preview.sources["ibkr"].fallback_only == 0
    assert preview.sources["ibkr"].provider_id_matched == 0
    assert preview.sources["ibkr"].planned_articles == 2
    assert preview.rejection_evidence.rejected_rows == 1
    assert preview.would_apply is True


def test_preview_canonicalizes_parquet_tickers_before_identity_and_relations(tmp_path):
    db = tmp_path / "market.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE news ("
        "id INTEGER PRIMARY KEY,ticker TEXT,title TEXT,description TEXT,url TEXT,"
        "publisher TEXT,source TEXT,published_at TEXT,article_hash TEXT,"
        "sentiment_score REAL,sentiment_source TEXT,sentiment_scale TEXT)"
    )
    conn.execute(
        "CREATE TABLE ticker_aliases (alias TEXT PRIMARY KEY, canonical TEXT NOT NULL)"
    )
    conn.execute("INSERT INTO ticker_aliases VALUES ('LC','HAPN')")
    published_at = "2026-06-27T10:00:00Z"
    conn.execute(
        "INSERT INTO news VALUES (1,'HAPN','Renamed story','','',"
        "'Legacy Wire','ibkr',?,?,NULL,NULL,NULL)",
        (published_at, canonical_article_hash("HAPN", "Renamed story", published_at)),
    )
    conn.commit()
    conn.close()

    path = tmp_path / "raw" / "ibkr" / "2026" / "2026-06.parquet"
    path.parent.mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "article_id": "DJ-N$rename",
                    "ticker": "LC",
                    "title": "Renamed story",
                    "published_at": published_at,
                    "source_api": "ibkr",
                    "description": "",
                    "content": "body",
                    "url": "",
                    "publisher": "Parquet Wire",
                    "related_tickers": '["LC", "HAPN"]',
                }
            ]
        ),
        path,
    )

    preview = plan_news_normalization(db, [path])
    inventory = inventory_inputs(db, [path])

    assert preview.sources["ibkr"].provider_id_matched == 1
    assert preview.sources["ibkr"].fallback_only == 0
    assert preview.planned_ticker_links == 1
    assert inventory.sources["ibkr"].sqlite_rows_matched_to_parquet == 1


def test_preview_to_dict_contains_only_aggregate_and_digest_data(tmp_path):
    db = tmp_path / "market.db"
    _legacy_db(db)
    path = tmp_path / "raw" / "ibkr" / "2026" / "2026-06.parquet"
    _parquet(path)
    payload = plan_news_normalization(db, [path]).to_dict()
    rendered = json.dumps(payload, sort_keys=True)
    assert payload["would_apply"] is True
    assert "fingerprint" in payload
    assert "full body" not in rendered


def test_preview_cli_is_read_only_and_emits_json(tmp_path):
    db = tmp_path / "market.db"
    _legacy_db(db)
    root = tmp_path / "raw"
    path = root / "ibkr" / "2026" / "2026-06.parquet"
    _parquet(path)
    before_db = db.read_bytes()
    before_parquet = path.read_bytes()
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/migration/preview_news_normalization.py",
            "--market-db",
            str(db),
            "--parquet-root",
            str(root),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["would_apply"] is True
    assert len(payload["fingerprint"]) == 64
    assert db.read_bytes() == before_db
    assert path.read_bytes() == before_parquet
    assert not Path(f"{db}-wal").exists()
