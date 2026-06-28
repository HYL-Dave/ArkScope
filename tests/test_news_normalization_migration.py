import json
import sqlite3
from pathlib import Path
import subprocess
import sys

import pyarrow as pa
import pyarrow.parquet as pq

from src.news_identity import canonical_article_hash
from src.news_normalized.migration import (
    inventory_inputs,
    iter_legacy_news,
    iter_parquet_news,
    plan_news_normalization,
)


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
    assert preview.sources["ibkr"].fallback_only == 1
    assert preview.sources["ibkr"].provider_id_matched == 0


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
