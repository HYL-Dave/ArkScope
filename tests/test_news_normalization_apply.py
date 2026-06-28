from dataclasses import replace
from pathlib import Path
import sqlite3

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from src.news_identity import canonical_article_hash
from src.news_normalized.migration import build_resolved_plan
from src.news_normalized.migration_apply import (
    MigrationValidationError,
    read_body_evidence_batch,
    validate_applied_plan,
    write_resolved_plan,
)
from src.news_normalized.schema import begin_news_normalized_schema_transaction


NOW = "2026-06-29T12:00:00Z"


def _legacy_db(path: Path):
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE news ("
        "id INTEGER PRIMARY KEY,ticker TEXT,title TEXT,description TEXT,url TEXT,"
        "publisher TEXT,source TEXT,published_at TEXT,article_hash TEXT,"
        "sentiment_score REAL,sentiment_source TEXT,sentiment_scale TEXT)"
    )
    published = "2026-06-27T10:00:00Z"
    rows = (
        (1, "AAPL", "Polygon shared", "https://example.test/shared", "polygon"),
        (2, "MSFT", "IBKR ambiguous", "", "ibkr"),
    )
    for row_id, ticker, title, url, source in rows:
        conn.execute(
            "INSERT INTO news VALUES (?,?,?,?,?,?,?,?,?,NULL,NULL,NULL)",
            (
                row_id,
                ticker,
                title,
                "",
                url,
                "Wire",
                source,
                published,
                canonical_article_hash(ticker, title, published),
            ),
        )
    conn.commit()
    conn.close()


def _parquet_inputs(root: Path):
    published = "2026-06-27T10:00:00Z"
    polygon = root / "polygon" / "2026" / "input.parquet"
    polygon.parent.mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "article_id": provider_id,
                    "ticker": "AAPL",
                    "title": "Polygon shared",
                    "published_at": published,
                    "source_api": "polygon",
                    "content": body,
                    "description": "",
                    "url": "https://example.test/shared",
                    "publisher": "Wire",
                    "related_tickers": '["AAPL"]',
                    "content_fetched_at": fetched_at,
                }
                for provider_id, body, fetched_at in (
                    ("polygon-a", "short body", "2026-06-27T10:01:00Z"),
                    (
                        "polygon-b",
                        "longer canonical body text",
                        "2026-06-27T10:02:00Z",
                    ),
                )
            ]
        ),
        polygon,
        row_group_size=2,
    )
    ibkr = root / "ibkr" / "2026" / "input.parquet"
    ibkr.parent.mkdir(parents=True)
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "article_id": provider_id,
                    "ticker": "MSFT",
                    "title": "IBKR ambiguous",
                    "published_at": published,
                    "source_api": "ibkr",
                    "content": "",
                    "description": "",
                    "url": "",
                    "publisher": "Wire",
                    "related_tickers": '["MSFT"]',
                }
                for provider_id in ("ibkr-a", "ibkr-b")
            ]
        ),
        ibkr,
    )
    return [polygon, ibkr]


@pytest.fixture
def temp_inputs(tmp_path):
    db = tmp_path / "market.db"
    _legacy_db(db)
    paths = _parquet_inputs(tmp_path / "raw")
    plan = build_resolved_plan(db, paths)
    assert plan.preview.would_apply
    return db, paths, plan


def _apply(temp_inputs):
    db, _paths, plan = temp_inputs
    conn = sqlite3.connect(db, isolation_level=None)
    conn.row_factory = sqlite3.Row
    begin_news_normalized_schema_transaction(conn)
    result = write_resolved_plan(conn, plan, "backup.db", NOW)
    validate_applied_plan(conn, plan)
    conn.commit()
    return conn, result


def test_apply_accounts_for_every_legacy_row(temp_inputs):
    conn, result = _apply(temp_inputs)
    mapped = conn.execute("SELECT COUNT(*) FROM news_legacy_migration_map").fetchone()[0]
    legacy = conn.execute("SELECT COUNT(*) FROM news").fetchone()[0]
    assert mapped == legacy == 2
    assert result.resolved_fingerprint == temp_inputs[2].preview.resolved_fingerprint
    conn.close()


def test_apply_keeps_cold_body_out_of_fts(temp_inputs):
    conn, _result = _apply(temp_inputs)
    cold = conn.execute("SELECT raw_body FROM news_article_body_variants").fetchone()[0]
    active = conn.execute(
        "SELECT body_text FROM news_article_bodies WHERE body_status='fetched'"
    ).fetchone()[0]
    fts = " ".join(row[0] for row in conn.execute("SELECT body_text FROM news_search_documents"))
    assert cold == "short body"
    assert active == "longer canonical body text"
    assert cold not in fts
    assert active in fts
    conn.close()


def test_apply_polygon_aliases_have_no_url_key(temp_inputs):
    conn, _result = _apply(temp_inputs)
    provider_keys = conn.execute(
        "SELECT COUNT(*) FROM news_article_keys WHERE source='polygon' "
        "AND key_kind='provider_id'"
    ).fetchone()[0]
    url_keys = conn.execute(
        "SELECT COUNT(*) FROM news_article_keys WHERE source='polygon' "
        "AND key_kind='url'"
    ).fetchone()[0]
    assert provider_keys == 2
    assert url_keys == 0
    conn.close()


def test_body_reader_batches_same_parquet_row_group(temp_inputs, monkeypatch):
    refs = [
        ref
        for article in temp_inputs[2].articles
        for ref in ((article.active_body,) + article.cold_bodies)
        if ref is not None
    ]
    calls = []
    original = pq.ParquetFile.read_row_group

    def recording(self, row_group, *args, **kwargs):
        calls.append((self.reader.metadata.num_rows, row_group))
        return original(self, row_group, *args, **kwargs)

    monkeypatch.setattr(pq.ParquetFile, "read_row_group", recording)
    bodies = read_body_evidence_batch(refs)

    assert set(bodies.values()) == {"short body", "longer canonical body text"}
    assert len(calls) == 1


def test_apply_rolls_back_when_outer_validation_raises(temp_inputs):
    db, _paths, plan = temp_inputs
    conn = sqlite3.connect(db, isolation_level=None)
    begin_news_normalized_schema_transaction(conn)
    with pytest.raises(MigrationValidationError):
        write_resolved_plan(conn, plan, "backup.db", NOW)
        raise MigrationValidationError("injected")
    conn.rollback()
    assert conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name='news_articles'"
    ).fetchone()[0] == 0
    conn.close()


def test_body_locator_digest_mismatch_aborts(temp_inputs):
    db, _paths, plan = temp_inputs
    article_index = next(
        index for index, article in enumerate(plan.articles) if article.active_body
    )
    article = plan.articles[article_index]
    bad_article = replace(
        article,
        active_body=replace(article.active_body, body_sha256="0" * 64),
    )
    bad_plan = replace(
        plan,
        articles=plan.articles[:article_index]
        + (bad_article,)
        + plan.articles[article_index + 1 :],
    )
    conn = sqlite3.connect(db, isolation_level=None)
    begin_news_normalized_schema_transaction(conn)
    with pytest.raises(MigrationValidationError, match="digest changed"):
        write_resolved_plan(conn, bad_plan, "backup.db", NOW)
    conn.rollback()
    conn.close()


def test_second_apply_of_same_fingerprint_is_zero_change(temp_inputs):
    conn, first = _apply(temp_inputs)
    before = conn.total_changes
    second = write_resolved_plan(conn, temp_inputs[2], "backup.db", NOW)
    assert second.already_applied is True
    assert second.run_id == first.run_id
    assert conn.total_changes == before
    conn.close()
