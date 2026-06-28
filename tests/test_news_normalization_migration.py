import sqlite3
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from src.news_identity import canonical_article_hash
from src.news_normalized.migration import (
    inventory_inputs,
    iter_legacy_news,
    iter_parquet_news,
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
