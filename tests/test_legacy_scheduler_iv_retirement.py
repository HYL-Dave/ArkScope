from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import stat
from pathlib import Path

import pandas as pd
import pytest

from scripts.migration import retire_legacy_scheduler_iv as migration


TARGET_SOURCES = ("price_backfill", "local_incremental", "iv_history")
NOW = "2026-07-26T00:00:00+00:00"


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _make_profile_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE scheduler_state (
                source TEXT PRIMARY KEY,
                last_attempt TEXT,
                last_status TEXT,
                last_error TEXT,
                continuation TEXT,
                last_result TEXT,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE profile_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE job_runs (
                id INTEGER PRIMARY KEY,
                job_name TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
                trigger_source TEXT NOT NULL DEFAULT 'api',
                payload TEXT NOT NULL DEFAULT '{}',
                result TEXT,
                message TEXT,
                error TEXT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                duration_ms INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE unrelated_profile (id INTEGER PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO unrelated_profile VALUES (1, 'keep-profile');
            """
        )
        for index, source in enumerate((*TARGET_SOURCES, "polygon_news"), start=1):
            conn.execute(
                "INSERT INTO scheduler_state VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    source,
                    f"2026-07-{index:02d}T00:00:00+00:00",
                    "succeeded",
                    None,
                    None,
                    json.dumps({"source": source, "planned": index}),
                    NOW,
                ),
            )
        settings = [
            ("schedule.price_backfill.enabled", "false"),
            ("schedule.local_incremental.interval_minutes", "60"),
            ("schedule.iv_history.enabled", "false"),
            ("schedule.iv_history_extra.enabled", "keep"),
            ("ui_locale", "zh-Hant"),
        ]
        conn.executemany(
            "INSERT INTO profile_settings VALUES (?, ?, ?)",
            [(key, value, NOW) for key, value in settings],
        )
        jobs = [
            (1, "collect.price_backfill", "failed"),
            (2, "collect.local_incremental", "succeeded"),
            (3, "collect.iv_history", "succeeded"),
            (4, "collect.polygon_news", "succeeded"),
        ]
        conn.executemany(
            "INSERT INTO job_runs "
            "(id, job_name, status, payload, result, started_at, created_at, updated_at) "
            "VALUES (?, ?, ?, '{}', ?, ?, ?, ?)",
            [
                (row_id, name, status, json.dumps({"row": row_id}), NOW, NOW, NOW)
                for row_id, name, status in jobs
            ],
        )


def _iv_rows() -> list[tuple[object, ...]]:
    return [
        (1, "AMD", "2026-01-30", 0.41, 0.31, 0.10, 145.0, 21),
        (2, "NVDA", "2026-02-06", 0.42, 0.30, 0.12, 180.0, 22),
        (3, "PLTR", "2026-02-13", 0.43, 0.29, 0.14, 120.0, 23),
        (4, "PYPL", "2026-03-06", 0.44, 0.28, 0.16, 80.0, 24),
    ]


def _make_market_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            PRAGMA foreign_keys=ON;
            CREATE TABLE iv_history (
                id INTEGER PRIMARY KEY, ticker TEXT NOT NULL, date TEXT NOT NULL,
                atm_iv REAL, hv_30d REAL, vrp REAL, spot_price REAL, num_quotes INTEGER
            );
            CREATE INDEX idx_iv_ticker_date ON iv_history(ticker, date);
            CREATE TABLE market_sync_meta (
                domain TEXT PRIMARY KEY,
                last_success TEXT,
                last_error TEXT,
                rows_added INTEGER DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE prices (
                ticker TEXT NOT NULL, datetime TEXT NOT NULL, interval TEXT NOT NULL,
                close REAL, PRIMARY KEY (ticker, datetime, interval)
            );
            CREATE TABLE unrelated_market (id INTEGER PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO prices VALUES ('AAPL', '2026-07-25T19:45:00+0000', '15min', 215.5);
            INSERT INTO unrelated_market VALUES (1, 'keep-market');
            """
        )
        conn.executemany("INSERT INTO iv_history VALUES (?, ?, ?, ?, ?, ?, ?, ?)", _iv_rows())
        conn.executemany(
            "INSERT INTO market_sync_meta VALUES (?, ?, ?, ?, ?)",
            [
                ("iv", "2026-07-03T00:00:00+00:00", None, 0, NOW),
                ("prices", "2026-07-25T20:00:00+00:00", None, 10, NOW),
            ],
        )


def _make_parquets(path: Path) -> None:
    path.mkdir(parents=True)
    columns = ["date", "ticker", "atm_iv", "hv_30d", "vrp", "spot_price", "num_quotes"]
    for row in _iv_rows():
        _, ticker, date, atm_iv, hv_30d, vrp, spot_price, num_quotes = row
        pd.DataFrame(
            [[date, ticker, atm_iv, hv_30d, vrp, spot_price, num_quotes]],
            columns=columns,
        ).to_parquet(path / f"{ticker}.parquet", index=False)


def _make_fixture(root: Path) -> migration.RetirementPaths:
    root.mkdir(parents=True)
    profile_db = root / "profile_state.db"
    market_db = root / "market_data.db"
    iv_dir = root / "iv_history"
    _make_profile_db(profile_db)
    _make_market_db(market_db)
    _make_parquets(iv_dir)
    return migration.RetirementPaths(
        profile_db=profile_db,
        market_db=market_db,
        iv_parquet_dir=iv_dir,
        backup_root=root / "backups",
    )


@pytest.fixture()
def paths(tmp_path: Path) -> migration.RetirementPaths:
    return _make_fixture(tmp_path / "fixture")


def _placeholder_preview() -> migration.PreviewReport:
    return migration.PreviewReport(
        preview_sha256="preview-not-implemented",
        pre_retirement_commit=migration.PRE_RETIREMENT_COMMIT,
        profile_targets={},
        market_targets={},
        parquet_targets=(),
        preserved_job_runs_sha256="",
        non_target_digests={},
    )


def _preview_or_placeholder(paths: migration.RetirementPaths) -> migration.PreviewReport:
    try:
        return migration.preview_retirement(paths)
    except NotImplementedError as exc:
        if str(exc) != "preview":
            raise
        return _placeholder_preview()


def _apply(paths: migration.RetirementPaths) -> dict[str, object]:
    preview = _preview_or_placeholder(paths)
    return dict(
        migration.apply_retirement(
            paths,
            expected_preview_sha256=preview.preview_sha256,
            expected_pre_retirement_commit=preview.pre_retirement_commit,
        )
    )


def _apply_or_placeholder_archive(paths: migration.RetirementPaths) -> Path:
    try:
        return Path(str(_apply(paths)["archive_dir"]))
    except NotImplementedError as exc:
        if str(exc) != "apply":
            raise
        with sqlite3.connect(paths.profile_db) as profile:
            profile.execute(
                "DELETE FROM scheduler_state WHERE source IN (?, ?, ?)",
                TARGET_SOURCES,
            )
            profile.execute(
                "DELETE FROM profile_settings WHERE "
                "key LIKE 'schedule.price_backfill.%' OR "
                "key LIKE 'schedule.local_incremental.%' OR "
                "key LIKE 'schedule.iv_history.%'"
            )
        with sqlite3.connect(paths.market_db) as market:
            market.execute("DELETE FROM market_sync_meta WHERE domain='iv'")
            market.execute("DROP TABLE iv_history")
        for item in paths.iv_parquet_dir.glob("*.parquet"):
            item.unlink()
        return paths.backup_root / "archive-not-implemented"


def _rows(path: Path, table: str, order_by: str) -> list[list[object]]:
    with sqlite3.connect(path) as conn:
        return [list(row) for row in conn.execute(f'SELECT * FROM "{table}" ORDER BY {order_by}')]


def _target_snapshot(paths: migration.RetirementPaths) -> dict[str, object]:
    with sqlite3.connect(paths.profile_db) as profile:
        scheduler = [list(row) for row in profile.execute(
            "SELECT * FROM scheduler_state WHERE source IN (?, ?, ?) ORDER BY source",
            TARGET_SOURCES,
        )]
        settings = [list(row) for row in profile.execute(
            "SELECT * FROM profile_settings WHERE "
            "key LIKE 'schedule.price_backfill.%' OR "
            "key LIKE 'schedule.local_incremental.%' OR "
            "key LIKE 'schedule.iv_history.%' ORDER BY key"
        )]
    with sqlite3.connect(paths.market_db) as market:
        table = market.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='iv_history'"
        ).fetchone()
        index = market.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_iv_ticker_date'"
        ).fetchone()
        iv_rows = [list(row) for row in market.execute("SELECT * FROM iv_history ORDER BY id")]
        sync = [list(row) for row in market.execute(
            "SELECT * FROM market_sync_meta WHERE domain='iv'"
        )]
    files = {
        item.name: _sha256(item.read_bytes())
        for item in sorted(paths.iv_parquet_dir.glob("*.parquet"))
    }
    return {
        "scheduler": scheduler,
        "settings": settings,
        "table_sql": table[0] if table else None,
        "index_sql": index[0] if index else None,
        "iv_rows": iv_rows,
        "sync": sync,
        "files": files,
    }


def _non_target_snapshot(paths: migration.RetirementPaths) -> dict[str, object]:
    with sqlite3.connect(paths.profile_db) as profile:
        profile_rows = {
            "scheduler": [list(row) for row in profile.execute(
                "SELECT * FROM scheduler_state WHERE source='polygon_news'"
            )],
            "settings": [list(row) for row in profile.execute(
                "SELECT * FROM profile_settings WHERE key IN "
                "('schedule.iv_history_extra.enabled', 'ui_locale') ORDER BY key"
            )],
            "jobs": [list(row) for row in profile.execute("SELECT * FROM job_runs ORDER BY id")],
            "unrelated": [list(row) for row in profile.execute("SELECT * FROM unrelated_profile")],
        }
    with sqlite3.connect(paths.market_db) as market:
        market_rows = {
            "prices": [list(row) for row in market.execute("SELECT * FROM prices")],
            "sync": [list(row) for row in market.execute(
                "SELECT * FROM market_sync_meta WHERE domain!='iv' ORDER BY domain"
            )],
            "unrelated": [list(row) for row in market.execute("SELECT * FROM unrelated_market")],
        }
    return {"profile": profile_rows, "market": market_rows}


def _assert_code(code: str, call) -> None:
    with pytest.raises(migration.MigrationError) as exc:
        call()
    assert exc.value.code == code


def test_preview_classifies_exact_targets_and_value_multisets(paths):
    report = migration.preview_retirement(paths)
    assert report.pre_retirement_commit == migration.PRE_RETIREMENT_COMMIT
    assert report.profile_targets["scheduler_state_count"] == 3
    assert report.profile_targets["profile_settings_count"] == 3
    assert report.profile_targets["job_runs_count"] == 3
    assert report.market_targets["row_count"] == 4
    assert report.market_targets["ticker_count"] == 4
    assert report.market_targets["id_bounds"] == [1, 4]
    assert report.market_targets["date_bounds"] == ["2026-01-30", "2026-03-06"]
    assert report.market_targets["sqlite_parquet_value_multiset_match"] is True
    assert [item["name"] for item in report.parquet_targets] == [
        "AMD.parquet", "NVDA.parquet", "PLTR.parquet", "PYPL.parquet",
    ]
    assert len(report.preview_sha256) == 64


def test_preview_is_read_only_and_deterministic(paths):
    source_paths = [paths.profile_db, paths.market_db, *sorted(paths.iv_parquet_dir.glob("*.parquet"))]
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in source_paths}
    first = migration.preview_retirement(paths)
    second = migration.preview_retirement(paths)
    assert first == second
    assert not paths.backup_root.exists()
    assert {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in source_paths} == before


def test_preview_rejects_schema_or_index_drift(tmp_path):
    schema_paths = _make_fixture(tmp_path / "schema")
    with sqlite3.connect(schema_paths.market_db) as conn:
        conn.execute("ALTER TABLE iv_history ADD COLUMN unexpected TEXT")
    _assert_code("iv_schema_mismatch", lambda: migration.preview_retirement(schema_paths))

    index_paths = _make_fixture(tmp_path / "index")
    with sqlite3.connect(index_paths.market_db) as conn:
        conn.execute("DROP INDEX idx_iv_ticker_date")
        conn.execute("CREATE INDEX idx_iv_ticker_date ON iv_history(date, ticker)")
    _assert_code("iv_index_mismatch", lambda: migration.preview_retirement(index_paths))


def test_preview_rejects_unknown_view_trigger_or_reference(paths):
    with sqlite3.connect(paths.market_db) as conn:
        conn.execute("CREATE VIEW legacy_iv_view AS SELECT ticker FROM iv_history")
    _assert_code("iv_schema_dependency", lambda: migration.preview_retirement(paths))


def test_preview_rejects_sqlite_parquet_value_mismatch(paths):
    frame = pd.read_parquet(paths.iv_parquet_dir / "AMD.parquet")
    frame.loc[0, "atm_iv"] = 9.99
    frame.to_parquet(paths.iv_parquet_dir / "AMD.parquet", index=False)
    _assert_code("iv_value_mismatch", lambda: migration.preview_retirement(paths))


def test_preview_rejects_source_drift_between_classification_and_archive(paths):
    report = _preview_or_placeholder(paths)
    with sqlite3.connect(paths.profile_db) as conn:
        conn.execute(
            "INSERT INTO profile_settings VALUES ('unrelated.drift', '1', ?)",
            (NOW,),
        )
    _assert_code("source_drift", lambda: migration.create_archive(paths, report))


def test_archive_writes_mode_restricted_restore_complete_artifacts(paths):
    archive = migration.create_archive(paths, _preview_or_placeholder(paths))
    assert stat.S_IMODE(archive.stat().st_mode) == 0o700
    expected = {
        "manifest.json", "legacy_iv.sqlite3", "profile_state.json",
        "market_sync_state.json", "RESTORE.txt", "parquet",
    }
    assert {item.name for item in archive.iterdir()} == expected
    assert {item.name for item in (archive / "parquet").iterdir()} == {
        "AMD.parquet", "NVDA.parquet", "PLTR.parquet", "PYPL.parquet",
    }
    for item in archive.rglob("*"):
        if item.is_file():
            assert stat.S_IMODE(item.stat().st_mode) == 0o600
    manifest = migration.verify_archive(archive)
    assert manifest["phase"] == "archived"


def test_archive_verification_rejects_tamper_before_apply(paths):
    preview = _preview_or_placeholder(paths)
    archive = migration.create_archive(paths, preview)
    (archive / "profile_state.json").write_text("tampered", encoding="utf-8")
    _assert_code(
        "archive_tampered",
        lambda: migration.apply_retirement(
            paths,
            expected_preview_sha256=preview.preview_sha256,
            expected_pre_retirement_commit=preview.pre_retirement_commit,
        ),
    )


def test_apply_removes_only_target_operational_state_and_iv_payload(paths):
    result = _apply(paths)
    assert result["phase"] == "complete"
    with sqlite3.connect(paths.profile_db) as profile:
        assert profile.execute(
            "SELECT COUNT(*) FROM scheduler_state WHERE source IN (?, ?, ?)", TARGET_SOURCES
        ).fetchone()[0] == 0
        assert profile.execute(
            "SELECT COUNT(*) FROM profile_settings WHERE "
            "key LIKE 'schedule.price_backfill.%' OR "
            "key LIKE 'schedule.local_incremental.%' OR "
            "key LIKE 'schedule.iv_history.%'"
        ).fetchone()[0] == 0
    with sqlite3.connect(paths.market_db) as market:
        assert market.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name IN ('iv_history','idx_iv_ticker_date')"
        ).fetchone()[0] == 0
        assert market.execute(
            "SELECT COUNT(*) FROM market_sync_meta WHERE domain='iv'"
        ).fetchone()[0] == 0
    assert list(paths.iv_parquet_dir.glob("*.parquet")) == []


def test_apply_preserves_job_runs_and_non_target_logical_digests(paths):
    before = _non_target_snapshot(paths)
    result = _apply(paths)
    assert _non_target_snapshot(paths) == before
    manifest = migration.verify_archive(Path(str(result["archive_dir"])))
    assert manifest["preserved_job_runs_sha256"] == _preview_or_placeholder(
        _make_fixture(paths.profile_db.parent / "comparison")
    ).preserved_job_runs_sha256


def test_apply_resumes_after_profile_owner_checkpoint(paths, monkeypatch):
    original = migration._after_phase_checkpoint
    raised = False

    def interrupt(phase: str) -> None:
        nonlocal raised
        if phase == "profile_applied" and not raised:
            raised = True
            raise RuntimeError("interrupt after profile")
        original(phase)

    monkeypatch.setattr(migration, "_after_phase_checkpoint", interrupt)
    with pytest.raises(RuntimeError, match="interrupt after profile"):
        _apply(paths)
    monkeypatch.setattr(migration, "_after_phase_checkpoint", original)
    result = _apply(paths)
    assert result["phase"] == "complete"
    assert result["resumed_from"] == "profile_applied"


def test_apply_resumes_after_market_owner_checkpoint(paths, monkeypatch):
    original = migration._after_phase_checkpoint
    raised = False

    def interrupt(phase: str) -> None:
        nonlocal raised
        if phase == "market_applied" and not raised:
            raised = True
            raise RuntimeError("interrupt after market")
        original(phase)

    monkeypatch.setattr(migration, "_after_phase_checkpoint", interrupt)
    with pytest.raises(RuntimeError, match="interrupt after market"):
        _apply(paths)
    monkeypatch.setattr(migration, "_after_phase_checkpoint", original)
    result = _apply(paths)
    assert result["phase"] == "complete"
    assert result["resumed_from"] == "market_applied"


def test_second_apply_is_byte_and_row_idempotent(paths):
    first = _apply(paths)
    archive = Path(str(first["archive_dir"]))
    before = {
        "profile": paths.profile_db.read_bytes(),
        "market": paths.market_db.read_bytes(),
        "manifest": (archive / "manifest.json").read_bytes(),
        "non_target": _non_target_snapshot(paths),
    }
    second = _apply(paths)
    assert second["already_applied"] is True
    assert Path(str(second["archive_dir"])) == archive
    assert paths.profile_db.read_bytes() == before["profile"]
    assert paths.market_db.read_bytes() == before["market"]
    assert (archive / "manifest.json").read_bytes() == before["manifest"]
    assert _non_target_snapshot(paths) == before["non_target"]


def test_restore_round_trip_recovers_exact_archived_targets(paths, monkeypatch):
    before = _target_snapshot(paths)
    archive = _apply_or_placeholder_archive(paths)
    monkeypatch.setattr(migration, "_git_head", lambda _root: migration.PRE_RETIREMENT_COMMIT)
    result = migration.restore_retirement(
        archive,
        paths,
        repo_root=paths.profile_db.parent,
        expected_current_commit=migration.PRE_RETIREMENT_COMMIT,
    )
    assert result["restored"] is True
    assert _target_snapshot(paths) == before


def test_restore_refuses_nonempty_or_differently_shaped_targets(paths, monkeypatch):
    archive = _apply_or_placeholder_archive(paths)
    with sqlite3.connect(paths.market_db) as conn:
        conn.execute("CREATE TABLE iv_history (id INTEGER PRIMARY KEY, wrong TEXT)")
        conn.execute("INSERT INTO iv_history VALUES (1, 'occupied')")
    monkeypatch.setattr(migration, "_git_head", lambda _root: migration.PRE_RETIREMENT_COMMIT)
    _assert_code(
        "restore_target_conflict",
        lambda: migration.restore_retirement(
            archive,
            paths,
            repo_root=paths.profile_db.parent,
            expected_current_commit=migration.PRE_RETIREMENT_COMMIT,
        ),
    )


def test_cli_requires_reviewed_preview_and_exact_pre_retirement_commit(paths):
    preview = _preview_or_placeholder(paths)
    common = [
        "apply",
        "--profile-db", str(paths.profile_db),
        "--market-db", str(paths.market_db),
        "--iv-parquet-dir", str(paths.iv_parquet_dir),
        "--backup-root", str(paths.backup_root),
        "--output", str(paths.profile_db.parent / "apply.json"),
    ]
    _assert_code(
        "preview_sha256_mismatch",
        lambda: migration.main(common + [
            "--expected-preview-sha256", "0" * 64,
            "--expected-pre-retirement-commit", preview.pre_retirement_commit,
        ]),
    )
    _assert_code(
        "pre_retirement_commit_mismatch",
        lambda: migration.main(common + [
            "--expected-preview-sha256", preview.preview_sha256,
            "--expected-pre-retirement-commit", "f" * 40,
        ]),
    )
