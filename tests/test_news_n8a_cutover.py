import hashlib
import json
import sqlite3
from contextlib import contextmanager
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
from src.news_normalized.routing import (
    NEWS_PG_EXIT_COMPLETED_KEY,
    USE_NORMALIZED_NEWS_WRITES_KEY,
)
from src.news_normalized.schema import ensure_news_normalized_schema
from src.profile_state import ProfileStateStore


PUBLISHED = "2026-06-27T10:00:00+0000"
VALIDATION_PASSED = {
    "polygon": "passed",
    "finnhub": "passed",
    "ibkr": "passed",
    "projection_parity": "passed",
    "pg_unreachable": "passed",
}


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


def _create_empty_legacy_db(path: Path) -> Path:
    conn = _connect(path)
    _create_legacy_schema(conn)
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


def _create_projection_only_legacy_db(path: Path) -> Path:
    _create_matched_db(path)
    conn = _connect(path)
    _insert_legacy(
        conn,
        row_id=12,
        ticker="NVDA",
        title="Projection-only legacy story",
        source="ibkr",
        published_at="2026-06-29T12:00:00+0000",
        url="https://example.test/projection-only",
    )
    _insert_normalized_article(
        conn,
        article_id=104,
        source="ibkr",
        title="Projection-only legacy story",
        published_at="2026-06-29T12:00:00+0000",
        ticker="NVDA",
    )
    conn.execute(
        "INSERT INTO news_legacy_projection_map "
        "(article_id,ticker,legacy_news_id,projected_at) VALUES (?,?,?,?)",
        (104, "NVDA", 12, "2026-06-29T12:01:00Z"),
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


def _write_validation_json(path: Path, data: dict | None = None) -> Path:
    path.write_text(
        json.dumps(VALIDATION_PASSED if data is None else data, sort_keys=True),
        encoding="utf-8",
    )
    return path


def _profile_setting(path: Path, key: str) -> str | None:
    return ProfileStateStore(path).get_setting(key)


def test_read_only_preview_preserves_file_identity_and_does_not_create_schema(tmp_path):
    db_path = _create_legacy_only_db(tmp_path / "market.db")
    before = _file_identity(db_path)

    report = cutover.preview_news_pg_exit(db_path)

    assert report.unmapped_legacy_rows == 1
    assert len(report.fingerprint) == 64
    assert _file_identity(db_path) == before
    assert not _table_exists(db_path, "news_pg_exit_runs")
    assert not _table_exists(db_path, "news_articles")


def test_preview_uses_safe_read_only_uri_for_relative_paths(tmp_path, monkeypatch):
    db_path = _create_matched_db(tmp_path / "market?cutover.db")
    before = _file_identity(db_path)
    monkeypatch.chdir(tmp_path)

    report = cutover.preview_news_pg_exit(Path("market?cutover.db"))

    assert report.legacy_row_count == 2
    assert report.unmapped_legacy_rows == 0
    assert _file_identity(db_path) == before
    assert not (tmp_path / "market").exists()


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
            profile_db=tmp_path / "profile_state.db",
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


def test_projection_map_does_not_mask_unmapped_legacy_rows(tmp_path):
    db_path = _create_projection_only_legacy_db(tmp_path / "market.db")

    report = cutover.preview_news_pg_exit(db_path)

    assert report.unmapped_legacy_rows == 1
    assert report.unmapped_rows == [
        {
            "legacy_news_id": 12,
            "ticker": "NVDA",
            "title": "Projection-only legacy story",
            "source": "ibkr",
            "published_at": "2026-06-29T12:00:00+0000",
            "article_hash": canonical_article_hash(
                "NVDA",
                "Projection-only legacy story",
                "2026-06-29T12:00:00+0000",
            ),
            "url": "https://example.test/projection-only",
        }
    ]


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
            profile_db=tmp_path / "profile_state.db",
        )

    assert backup_calls == []
    assert _audit_row_count(db_path) == 0


def test_begin_rechecks_expected_report_inside_lock_before_backup(tmp_path, monkeypatch):
    db_path = _create_matched_db(tmp_path / "market.db")
    expected = cutover.preview_news_pg_exit(db_path)
    backup_calls = []

    @contextmanager
    def drifting_lock(*args, **kwargs):
        conn = _connect(db_path)
        _insert_normalized_article(
            conn,
            article_id=105,
            source="ibkr",
            title="Drift between preview and lock",
            published_at="2026-06-30T12:00:00+0000",
            ticker="TSLA",
        )
        conn.commit()
        conn.close()
        yield

    monkeypatch.setattr(cutover, "market_write_lock", drifting_lock)
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
            profile_db=tmp_path / "profile_state.db",
        )

    assert backup_calls == []
    assert not (tmp_path / "backup.db").exists()
    assert _audit_row_count(db_path) == 0


def test_begin_writes_testing_audit_row_after_zero_delta_and_reserved_backup(
    tmp_path, monkeypatch
):
    db_path = _create_matched_db(tmp_path / "market.db")
    profile_db = tmp_path / "profile_state.db"
    expected = cutover.preview_news_pg_exit(db_path)
    backup_path = tmp_path / "backup.db"
    profile_writes = []

    class RecordingProfileStateStore:
        def __init__(self, path):
            self._store = ProfileStateStore(path)

        def set_setting(self, key, value):
            profile_writes.append(
                {
                    "key": key,
                    "value": value,
                    "audit_rows": _audit_row_count(db_path),
                    "backup_exists": backup_path.is_file(),
                }
            )
            self._store.set_setting(key, value)

    monkeypatch.setattr(
        cutover, "ProfileStateStore", RecordingProfileStateStore, raising=False
    )

    result = cutover.begin_news_pg_exit(
        db_path,
        expected_report=expected,
        backup_path=backup_path,
        profile_db=profile_db,
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
    assert profile_writes == [
        {
            "key": USE_NORMALIZED_NEWS_WRITES_KEY,
            "value": "true",
            "audit_rows": 1,
            "backup_exists": True,
        }
    ]
    assert _profile_setting(profile_db, USE_NORMALIZED_NEWS_WRITES_KEY) == "true"
    assert _profile_setting(profile_db, NEWS_PG_EXIT_COMPLETED_KEY) is None
    assert _profile_setting(profile_db, "use_local_market_strict") is None


def test_begin_does_not_write_profile_flag_when_report_gate_fails(tmp_path):
    db_path = _create_matched_db(tmp_path / "market.db")
    profile_db = tmp_path / "profile_state.db"
    expected = cutover.preview_news_pg_exit(db_path).to_json_dict()
    expected["legacy_row_count"] = 999

    with pytest.raises(cutover.CutoverBlocked, match="expected report changed"):
        cutover.begin_news_pg_exit(
            db_path,
            expected_report=expected,
            backup_path=tmp_path / "backup.db",
            profile_db=profile_db,
        )

    assert _audit_row_count(db_path) == 0
    assert _profile_setting(profile_db, USE_NORMALIZED_NEWS_WRITES_KEY) is None


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
        profile_db=tmp_path / "profile_state.db",
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


def test_begin_insert_failure_rolls_back_cutover_schema(tmp_path, monkeypatch):
    db_path = _create_empty_legacy_db(tmp_path / "market.db")
    expected = cutover.preview_news_pg_exit(db_path)
    monkeypatch.setattr(
        cutover,
        "backup_market_db",
        lambda *args, **kwargs: str(args[1]),
    )
    monkeypatch.setattr(cutover, "_utc_now", lambda: None)

    with pytest.raises(sqlite3.IntegrityError):
        cutover.begin_news_pg_exit(
            db_path,
            expected_report=expected,
            backup_path=tmp_path / "backup.db",
            profile_db=tmp_path / "profile_state.db",
        )

    assert not _table_exists(db_path, "news_pg_exit_runs")
    assert not _table_exists(db_path, "news_articles")


@pytest.mark.parametrize(
    "validation",
    [
        {
            "finnhub": "passed",
            "ibkr": "passed",
            "projection_parity": "passed",
            "pg_unreachable": "passed",
        },
        {**VALIDATION_PASSED, "polygon": True},
        {**VALIDATION_PASSED, "polygon": "PASS"},
    ],
)
def test_finalize_rejects_missing_or_non_passed_validation_gates(
    tmp_path, validation
):
    db_path = _create_matched_db(tmp_path / "market.db")
    profile_db = tmp_path / "profile_state.db"
    begin = cutover.begin_news_pg_exit(
        db_path,
        expected_report=cutover.preview_news_pg_exit(db_path),
        backup_path=tmp_path / "backup.db",
        profile_db=profile_db,
    )
    validation_path = _write_validation_json(tmp_path / "validation.json", validation)

    with pytest.raises(cutover.CutoverBlocked, match="validation gate"):
        cutover.finalize_news_pg_exit(
            db_path,
            run_id=begin.run_id,
            validation_json_path=validation_path,
            profile_db=profile_db,
        )

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT status,validation_json,completed_at FROM news_pg_exit_runs WHERE id=?",
            (begin.run_id,),
        ).fetchone()
    finally:
        conn.close()
    assert row == ("testing", None, None)
    assert _profile_setting(profile_db, NEWS_PG_EXIT_COMPLETED_KEY) is None


def test_finalize_with_all_validation_gates_sets_audit_and_profile_marker(tmp_path):
    db_path = _create_matched_db(tmp_path / "finalize.db")
    profile_db = tmp_path / "profile_state.db"
    begin = cutover.begin_news_pg_exit(
        db_path,
        expected_report=cutover.preview_news_pg_exit(db_path),
        backup_path=tmp_path / "finalize-backup.db",
        profile_db=profile_db,
    )
    validation_path = _write_validation_json(tmp_path / "validation.json")

    cutover.finalize_news_pg_exit(
        db_path,
        run_id=begin.run_id,
        validation_json_path=validation_path,
        profile_db=profile_db,
    )

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT status,validation_json,completed_at FROM news_pg_exit_runs WHERE id=?",
            (begin.run_id,),
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "completed"
    assert row[1] == _canonical_json(VALIDATION_PASSED)
    assert row[2] is not None
    assert _profile_setting(profile_db, NEWS_PG_EXIT_COMPLETED_KEY) == "true"


def test_finalize_is_repeatable_when_profile_marker_write_fails_after_audit(
    tmp_path, monkeypatch
):
    db_path = _create_matched_db(tmp_path / "market.db")
    profile_db = tmp_path / "profile_state.db"
    begin = cutover.begin_news_pg_exit(
        db_path,
        expected_report=cutover.preview_news_pg_exit(db_path),
        backup_path=tmp_path / "backup.db",
        profile_db=profile_db,
    )
    validation_path = _write_validation_json(tmp_path / "validation.json")

    class FailingProfileStateStore:
        def __init__(self, path):
            self._store = ProfileStateStore(path)

        def set_setting(self, key, value):
            if key == NEWS_PG_EXIT_COMPLETED_KEY:
                raise RuntimeError("profile marker write failed")
            self._store.set_setting(key, value)

    monkeypatch.setattr(cutover, "ProfileStateStore", FailingProfileStateStore)
    with pytest.raises(RuntimeError, match="profile marker write failed"):
        cutover.finalize_news_pg_exit(
            db_path,
            run_id=begin.run_id,
            validation_json_path=validation_path,
            profile_db=profile_db,
        )

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT status,validation_json FROM news_pg_exit_runs WHERE id=?",
            (begin.run_id,),
        ).fetchone()
    finally:
        conn.close()
    assert row == ("completed", _canonical_json(VALIDATION_PASSED))
    assert _profile_setting(profile_db, NEWS_PG_EXIT_COMPLETED_KEY) is None

    monkeypatch.setattr(cutover, "ProfileStateStore", ProfileStateStore)
    result = cutover.finalize_news_pg_exit(
        db_path,
        run_id=begin.run_id,
        validation_json_path=validation_path,
        profile_db=profile_db,
    )

    assert result.status == "completed"
    assert _profile_setting(profile_db, NEWS_PG_EXIT_COMPLETED_KEY) == "true"


def test_rollback_only_from_testing_and_never_sets_exit_marker(tmp_path):
    rollback_db = _create_matched_db(tmp_path / "rollback.db")
    rollback_profile_db = tmp_path / "rollback-profile.db"
    rollback_run = cutover.begin_news_pg_exit(
        rollback_db,
        expected_report=cutover.preview_news_pg_exit(rollback_db),
        backup_path=tmp_path / "rollback-backup.db",
        profile_db=rollback_profile_db,
    )
    cutover.rollback_news_pg_exit(
        rollback_db, run_id=rollback_run.run_id, profile_db=rollback_profile_db
    )
    conn = sqlite3.connect(rollback_db)
    try:
        assert (
            conn.execute(
                "SELECT status FROM news_pg_exit_runs WHERE id=?",
                (rollback_run.run_id,),
            ).fetchone()[0]
            == "rolled_back"
        )
    finally:
        conn.close()
    assert (
        _profile_setting(rollback_profile_db, USE_NORMALIZED_NEWS_WRITES_KEY)
        == "false"
    )
    assert _profile_setting(rollback_profile_db, NEWS_PG_EXIT_COMPLETED_KEY) is None

    completed_db = _create_matched_db(tmp_path / "completed.db")
    completed_profile_db = tmp_path / "completed-profile.db"
    completed_run = cutover.begin_news_pg_exit(
        completed_db,
        expected_report=cutover.preview_news_pg_exit(completed_db),
        backup_path=tmp_path / "completed-backup.db",
        profile_db=completed_profile_db,
    )
    cutover.finalize_news_pg_exit(
        completed_db,
        run_id=completed_run.run_id,
        validation_json_path=_write_validation_json(
            tmp_path / "completed-validation.json"
        ),
        profile_db=completed_profile_db,
    )
    with pytest.raises(cutover.CutoverBlocked, match="run is not in testing status"):
        cutover.rollback_news_pg_exit(
            completed_db, run_id=completed_run.run_id, profile_db=completed_profile_db
        )
    conn = sqlite3.connect(completed_db)
    try:
        assert (
            conn.execute(
                "SELECT status FROM news_pg_exit_runs WHERE id=?",
                (completed_run.run_id,),
            ).fetchone()[0]
            == "completed"
        )
    finally:
        conn.close()
    assert _profile_setting(completed_profile_db, NEWS_PG_EXIT_COMPLETED_KEY) == "true"
    assert (
        _profile_setting(completed_profile_db, USE_NORMALIZED_NEWS_WRITES_KEY)
        == "true"
    )


@pytest.mark.parametrize("action", ["finalize", "rollback"])
def test_finalize_and_rollback_do_not_create_missing_cutover_schema(
    tmp_path, action
):
    db_path = _create_empty_legacy_db(tmp_path / f"{action}.db")
    validation_path = tmp_path / "validation.json"
    _write_validation_json(validation_path)

    with pytest.raises(cutover.CutoverBlocked):
        if action == "finalize":
            cutover.finalize_news_pg_exit(
                db_path,
                run_id=1,
                validation_json_path=validation_path,
                profile_db=tmp_path / "profile.db",
            )
        else:
            cutover.rollback_news_pg_exit(
                db_path, run_id=1, profile_db=tmp_path / "profile.db"
            )

    assert not _table_exists(db_path, "news_pg_exit_runs")
    assert not _table_exists(db_path, "news_articles")


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


def test_cli_passes_profile_db_to_begin_finalize_and_rollback(tmp_path, monkeypatch):
    db_path = tmp_path / "market.db"
    profile_db = tmp_path / "profile.db"
    report_path = tmp_path / "report.json"
    report_path.write_text("{}", encoding="utf-8")
    validation_path = _write_validation_json(tmp_path / "validation.json")
    calls = []

    class Result:
        def __init__(self, status="testing"):
            self.status = status

        def to_json_dict(self):
            return {"run_id": 7, "status": self.status}

    def fake_begin(db_path_arg, *, expected_report, backup_path, profile_db):
        calls.append(("begin", db_path_arg, profile_db, expected_report, backup_path))
        return Result()

    def fake_finalize(db_path_arg, *, run_id, validation_json_path, profile_db):
        calls.append(("finalize", db_path_arg, profile_db, run_id, validation_json_path))
        return Result(status="completed")

    def fake_rollback(db_path_arg, *, run_id, profile_db):
        calls.append(("rollback", db_path_arg, profile_db, run_id))
        return Result(status="rolled_back")

    monkeypatch.setattr(cutover_cli, "begin_news_pg_exit", fake_begin)
    monkeypatch.setattr(cutover_cli, "finalize_news_pg_exit", fake_finalize)
    monkeypatch.setattr(cutover_cli, "rollback_news_pg_exit", fake_rollback)

    assert (
        cutover_cli.main(
            [
                "begin",
                "--db",
                str(db_path),
                "--profile-db",
                str(profile_db),
                "--expected-report",
                str(report_path),
                "--backup",
                str(tmp_path / "backup.db"),
                "--confirm-scheduler-paused",
            ]
        )
        == 0
    )
    assert (
        cutover_cli.main(
            [
                "finalize",
                "--db",
                str(db_path),
                "--profile-db",
                str(profile_db),
                "--run-id",
                "7",
                "--validation-json",
                str(validation_path),
            ]
        )
        == 0
    )
    assert (
        cutover_cli.main(
            [
                "rollback",
                "--db",
                str(db_path),
                "--profile-db",
                str(profile_db),
                "--run-id",
                "7",
            ]
        )
        == 0
    )

    assert [call[:3] for call in calls] == [
        ("begin", db_path, profile_db),
        ("finalize", db_path, profile_db),
        ("rollback", db_path, profile_db),
    ]
