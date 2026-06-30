import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from scripts.migration import news_n8a_cutover as cutover_cli
from src.market_data_admin import (
    _NEWS_SCHEMA,
    _ensure_news_fts_triggers,
    _ensure_news_hash_unique,
)
from src.news_identity import canonical_article_hash
from src.news_normalized import cutover
from src.news_normalized.schema import ensure_news_normalized_schema


PUBLISHED = "2026-06-27T10:00:00+0000"


def _file_identity(path: Path) -> dict:
    stat = path.stat()
    return {
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "wal_exists": path.with_name(path.name + "-wal").exists(),
        "shm_exists": path.with_name(path.name + "-shm").exists(),
    }


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _create_legacy_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_NEWS_SCHEMA)
    _ensure_news_hash_unique(conn)
    _ensure_news_fts_triggers(conn)


def _insert_legacy(
    conn: sqlite3.Connection,
    *,
    row_id: int,
    ticker: str = "AAPL",
    title: str = "Apple raises outlook",
    source: str = "polygon",
    published_at: str = PUBLISHED,
    url: str = "https://example.test/apple",
) -> None:
    conn.execute(
        "INSERT INTO news "
        "(id,ticker,title,description,url,publisher,source,published_at,article_hash) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (
            row_id,
            ticker,
            title,
            "reviewed body",
            url,
            "Example Wire",
            source,
            published_at,
            canonical_article_hash(ticker, title, published_at),
        ),
    )


def _insert_normalized_article(
    conn: sqlite3.Connection,
    *,
    article_id: int,
    source: str,
    title: str,
    published_at: str,
    ticker: str,
) -> None:
    conn.execute(
        "INSERT INTO news_articles "
        "(id,source,provider_article_id,canonical_title,publisher,url,published_at,"
        "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            article_id,
            source,
            f"{source}-{article_id}",
            title,
            "Example Wire",
            f"https://example.test/{article_id}",
            published_at,
            "2026-06-27T10:01:00Z",
            "2026-06-27T10:01:00Z",
        ),
    )
    conn.execute(
        "INSERT INTO news_article_tickers "
        "(article_id,ticker,relation_kind,first_seen_at,last_seen_at) "
        "VALUES (?,?,?,?,?)",
        (
            article_id,
            ticker,
            "primary",
            "2026-06-27T10:01:00Z",
            "2026-06-27T10:01:00Z",
        ),
    )


def _insert_migration_run(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO news_normalization_runs "
        "(id,policy_version,input_fingerprint,resolved_fingerprint,"
        "rejection_evidence_fingerprint,counts_json,backup_path,applied_at) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (
            1,
            "test",
            "input",
            "resolved",
            "rejection",
            "{}",
            "backup.db",
            "2026-06-27T10:02:00Z",
        ),
    )


def _create_matched_db(path: Path) -> Path:
    conn = _connect(path)
    _create_legacy_schema(conn)
    ensure_news_normalized_schema(conn)
    _insert_migration_run(conn)

    rows = (
        (10, 101, "AAPL", "Apple raises outlook", "polygon", PUBLISHED),
        (11, 102, "MSFT", "Microsoft opens region", "finnhub", "2026-06-28T11:00:00+0000"),
    )
    for legacy_id, article_id, ticker, title, source, published_at in rows:
        _insert_legacy(
            conn,
            row_id=legacy_id,
            ticker=ticker,
            title=title,
            source=source,
            published_at=published_at,
            url=f"https://example.test/{legacy_id}",
        )
        _insert_normalized_article(
            conn,
            article_id=article_id,
            source=source,
            title=title,
            published_at=published_at,
            ticker=ticker,
        )
        conn.execute(
            "INSERT INTO news_legacy_migration_map "
            "(legacy_news_id,article_id,resolution_kind,migration_run_id,"
            "migration_fingerprint) VALUES (?,?,?,?,?)",
            (legacy_id, article_id, "mapped", 1, "resolved"),
        )
    conn.commit()
    conn.close()
    return path


def _create_legacy_only_db(path: Path) -> Path:
    conn = _connect(path)
    _create_legacy_schema(conn)
    _insert_legacy(conn, row_id=99, title="Unmapped story")
    conn.commit()
    conn.close()
    return path


def _create_normalized_only_db(path: Path) -> Path:
    _create_matched_db(path)
    conn = _connect(path)
    _insert_normalized_article(
        conn,
        article_id=103,
        source="ibkr",
        title="IBKR normalized-only archive",
        published_at="2026-06-29T12:00:00+0000",
        ticker="NVDA",
    )
    conn.commit()
    conn.close()
    return path


def _table_exists(path: Path, table: str) -> bool:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return bool(
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
        )
    finally:
        conn.close()


def _audit_row_count(path: Path) -> int:
    if not _table_exists(path, "news_pg_exit_runs"):
        return 0
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return int(conn.execute("SELECT COUNT(*) FROM news_pg_exit_runs").fetchone()[0])
    finally:
        conn.close()


def _canonical_json(data: dict) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def test_read_only_preview_preserves_file_identity_and_does_not_create_schema(tmp_path):
    db_path = _create_legacy_only_db(tmp_path / "market.db")
    before = _file_identity(db_path)

    report = cutover.preview_news_pg_exit(db_path)

    assert report.unmapped_legacy_rows == 1
    assert len(report.fingerprint) == 64
    assert _file_identity(db_path) == before
    assert not _table_exists(db_path, "news_pg_exit_runs")
    assert not _table_exists(db_path, "news_articles")


def test_preview_report_and_fingerprint_are_deterministic(tmp_path):
    db_path = _create_matched_db(tmp_path / "market.db")

    first = cutover.preview_news_pg_exit(db_path).to_json_dict()
    second = cutover.preview_news_pg_exit(db_path).to_json_dict()

    assert _canonical_json(first) == _canonical_json(second)
    assert "generated_at" not in first
    assert first["unmapped_legacy_rows"] == 0
    assert first["legacy_max_id"] == 11
    assert first["legacy_row_count"] == 2
    assert first["normalized_row_count"] == 2
    assert first["normalized_only_count"] == 0
    assert first["per_source"] == {
        "legacy": {
            "finnhub": {
                "count": 1,
                "latest_published_at": "2026-06-28T11:00:00+0000",
            },
            "polygon": {"count": 1, "latest_published_at": PUBLISHED},
        },
        "normalized": {
            "finnhub": {
                "count": 1,
                "latest_published_at": "2026-06-28T11:00:00+0000",
            },
            "polygon": {"count": 1, "latest_published_at": PUBLISHED},
        },
    }

    payload = dict(first)
    fingerprint = payload.pop("fingerprint")
    assert fingerprint == hashlib.sha256(_canonical_json(payload).encode()).hexdigest()


def test_unmapped_legacy_rows_are_reported_and_block_begin_before_writes(
    tmp_path, monkeypatch
):
    db_path = _create_legacy_only_db(tmp_path / "market.db")
    expected = cutover.preview_news_pg_exit(db_path)
    backup_calls = []
    monkeypatch.setattr(
        cutover,
        "backup_market_db",
        lambda *args, **kwargs: backup_calls.append((args, kwargs)) or str(args[1]),
    )

    with pytest.raises(cutover.CutoverBlocked, match="unmapped legacy rows: 1"):
        cutover.begin_news_pg_exit(
            db_path,
            expected_report=expected,
            backup_path=tmp_path / "backup.db",
        )

    assert expected.unmapped_rows == [
        {
            "legacy_news_id": 99,
            "ticker": "AAPL",
            "title": "Unmapped story",
            "source": "polygon",
            "published_at": PUBLISHED,
            "article_hash": canonical_article_hash(
                "AAPL", "Unmapped story", PUBLISHED
            ),
            "url": "https://example.test/apple",
        }
    ]
    assert backup_calls == []
    assert not (tmp_path / "backup.db").exists()
    assert not _table_exists(db_path, "news_pg_exit_runs")


def test_begin_requires_exact_report_match_before_backup(tmp_path, monkeypatch):
    db_path = _create_matched_db(tmp_path / "market.db")
    expected = cutover.preview_news_pg_exit(db_path).to_json_dict()
    expected["legacy_row_count"] = 999
    backup_calls = []
    monkeypatch.setattr(
        cutover,
        "backup_market_db",
        lambda *args, **kwargs: backup_calls.append((args, kwargs)) or str(args[1]),
    )

    with pytest.raises(cutover.CutoverBlocked, match="expected report changed"):
        cutover.begin_news_pg_exit(
            db_path,
            expected_report=expected,
            backup_path=tmp_path / "backup.db",
        )

    assert backup_calls == []
    assert _audit_row_count(db_path) == 0


def test_begin_writes_testing_audit_row_after_zero_delta_and_reserved_backup(tmp_path):
    db_path = _create_matched_db(tmp_path / "market.db")
    expected = cutover.preview_news_pg_exit(db_path)
    backup_path = tmp_path / "backup.db"

    result = cutover.begin_news_pg_exit(
        db_path,
        expected_report=expected,
        backup_path=backup_path,
    )

    assert result.run_id == 1
    assert Path(result.backup_path) == backup_path
    assert backup_path.is_file()

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT preflight_fingerprint,legacy_max_id,legacy_row_count,"
            "normalized_row_count,normalized_only_count,backup_path,status,"
            "validation_json FROM news_pg_exit_runs"
        ).fetchone()
    finally:
        conn.close()

    assert dict(row) == {
        "preflight_fingerprint": expected.fingerprint,
        "legacy_max_id": 11,
        "legacy_row_count": 2,
        "normalized_row_count": 2,
        "normalized_only_count": 0,
        "backup_path": str(backup_path),
        "status": "testing",
        "validation_json": None,
    }


def test_begin_allows_normalized_only_rows_and_audits_the_count(tmp_path):
    db_path = _create_normalized_only_db(tmp_path / "market.db")
    expected = cutover.preview_news_pg_exit(db_path)
    backup_path = tmp_path / "backup.db"

    assert expected.unmapped_legacy_rows == 0
    assert expected.normalized_only_count == 1

    result = cutover.begin_news_pg_exit(
        db_path,
        expected_report=expected,
        backup_path=backup_path,
    )

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "SELECT normalized_only_count,status FROM news_pg_exit_runs WHERE id=?",
            (result.run_id,),
        ).fetchone()
    finally:
        conn.close()

    assert row == (1, "testing")
    assert backup_path.is_file()


def test_finalize_and_rollback_update_existing_testing_runs(tmp_path):
    first_db = _create_matched_db(tmp_path / "finalize.db")
    first = cutover.begin_news_pg_exit(
        first_db,
        expected_report=cutover.preview_news_pg_exit(first_db),
        backup_path=tmp_path / "finalize-backup.db",
    )
    validation_path = tmp_path / "validation.json"
    validation_path.write_text('{"projection_parity":"passed"}', encoding="utf-8")

    cutover.finalize_news_pg_exit(
        first_db, run_id=first.run_id, validation_json_path=validation_path
    )

    conn = sqlite3.connect(first_db)
    try:
        row = conn.execute(
            "SELECT status,validation_json,completed_at FROM news_pg_exit_runs WHERE id=?",
            (first.run_id,),
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "completed"
    assert row[1] == '{"projection_parity":"passed"}'
    assert row[2] is not None

    second_db = _create_matched_db(tmp_path / "rollback.db")
    second = cutover.begin_news_pg_exit(
        second_db,
        expected_report=cutover.preview_news_pg_exit(second_db),
        backup_path=tmp_path / "rollback-backup.db",
    )
    cutover.rollback_news_pg_exit(second_db, run_id=second.run_id)
    conn = sqlite3.connect(second_db)
    try:
        assert (
            conn.execute(
                "SELECT status FROM news_pg_exit_runs WHERE id=?",
                (second.run_id,),
            ).fetchone()[0]
            == "rolled_back"
        )
    finally:
        conn.close()


def test_cli_preview_output_and_begin_requires_confirmation(tmp_path):
    db_path = _create_matched_db(tmp_path / "market.db")
    output = tmp_path / "report.json"

    assert (
        cutover_cli.main(
            ["preview", "--db", str(db_path), "--output", str(output)]
        )
        == 0
    )

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data == cutover.preview_news_pg_exit(db_path).to_json_dict()

    parser = cutover_cli.build_parser()
    begin_args = [
        "begin",
        "--db",
        str(db_path),
        "--expected-report",
        str(output),
        "--backup",
        str(tmp_path / "backup.db"),
    ]
    with pytest.raises(SystemExit):
        parser.parse_args(begin_args)

    parsed = parser.parse_args(begin_args + ["--confirm-scheduler-paused"])
    assert parsed.confirm_scheduler_paused is True

    with pytest.raises(SystemExit):
        parser.parse_args(begin_args + ["--confirm-scheduler-paused", "--force"])
