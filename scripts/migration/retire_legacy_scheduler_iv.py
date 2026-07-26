#!/usr/bin/env python3
"""Audited retirement of legacy scheduler identities and the old IV store."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import sqlite3
import stat
import subprocess
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd


PRE_RETIREMENT_COMMIT = "7bb7cc29f70ca899a5b598f2322ce181daa17ebe"
TARGET_SOURCES = ("price_backfill", "local_incremental", "iv_history")
TARGET_JOB_NAMES = tuple(f"collect.{source}" for source in TARGET_SOURCES)
PHASES = ("archived", "profile_applied", "market_applied", "files_applied", "complete")
IV_COLUMNS = (
    ("id", "INTEGER", 0, 1),
    ("ticker", "TEXT", 1, 0),
    ("date", "TEXT", 1, 0),
    ("atm_iv", "REAL", 0, 0),
    ("hv_30d", "REAL", 0, 0),
    ("vrp", "REAL", 0, 0),
    ("spot_price", "REAL", 0, 0),
    ("num_quotes", "INTEGER", 0, 0),
)
PARQUET_COLUMNS = ("date", "ticker", "atm_iv", "hv_30d", "vrp", "spot_price", "num_quotes")


@dataclass(frozen=True)
class RetirementPaths:
    profile_db: Path
    market_db: Path
    iv_parquet_dir: Path
    backup_root: Path


@dataclass(frozen=True)
class PreviewReport:
    preview_sha256: str
    pre_retirement_commit: str
    profile_targets: Mapping[str, object]
    market_targets: Mapping[str, object]
    parquet_targets: tuple[Mapping[str, object], ...]
    preserved_job_runs_sha256: str
    non_target_digests: Mapping[str, str]


class MigrationError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize(value: object) -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"__bytes__": bytes(value).hex()}
    if isinstance(value, (date, datetime, pd.Timestamp)):
        return value.isoformat()
    if hasattr(value, "item"):
        return _normalize(value.item())
    if isinstance(value, float):
        if math.isnan(value):
            return None
        if math.isinf(value):
            return {"__float__": "inf" if value > 0 else "-inf"}
        return value
    return str(value)


def _normalize_row(row: Iterable[object]) -> list[object]:
    return [_normalize(value) for value in row]


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _connect_read_only(path: Path) -> sqlite3.Connection:
    resolved = path.resolve()
    if not resolved.is_file():
        raise MigrationError("source_missing")
    connection = sqlite3.connect(f"{resolved.as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _database_health(connection: sqlite3.Connection) -> Mapping[str, object]:
    integrity = [row[0] for row in connection.execute("PRAGMA integrity_check")]
    foreign_keys = [list(row) for row in connection.execute("PRAGMA foreign_key_check")]
    if integrity != ["ok"]:
        raise MigrationError("integrity_check_failed")
    if foreign_keys:
        raise MigrationError("foreign_key_check_failed")
    return {"integrity_check": "ok", "foreign_key_violations": 0}


def _dict_rows(
    connection: sqlite3.Connection,
    sql: str,
    parameters: Sequence[object] = (),
) -> list[dict[str, object]]:
    return [
        {key: _normalize(row[key]) for key in row.keys()}
        for row in connection.execute(sql, parameters)
    ]


def _is_target_setting(key: object) -> bool:
    if not isinstance(key, str):
        return False
    return any(key.startswith(f"schedule.{source}.") for source in TARGET_SOURCES)


def _schema_entries(
    connection: sqlite3.Connection,
    *,
    exclude_market_target: bool,
) -> list[list[object]]:
    entries: list[list[object]] = []
    for row in connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
    ):
        if exclude_market_target and row[1] in {"iv_history", "idx_iv_ticker_date"}:
            continue
        entries.append(_normalize_row(row))
    return entries


def _ordered_table_cursor(
    connection: sqlite3.Connection,
    table: str,
) -> tuple[list[str], sqlite3.Cursor]:
    columns = [row[1] for row in connection.execute(f"PRAGMA table_info({_quote(table)})")]
    if not columns:
        return [], connection.execute("SELECT 1 WHERE 0")
    try:
        cursor = connection.execute(f"SELECT * FROM {_quote(table)} ORDER BY rowid")
    except sqlite3.OperationalError:
        order = ", ".join(_quote(column) for column in columns)
        cursor = connection.execute(f"SELECT * FROM {_quote(table)} ORDER BY {order}")
    return columns, cursor


def _update_framed_digest(digest: Any, value: object) -> None:
    payload = _canonical_bytes(value)
    digest.update(len(payload).to_bytes(8, byteorder="big"))
    digest.update(payload)


def _logical_database_digest(path: Path, *, domain: str, exclude_targets: bool) -> str:
    digest = hashlib.sha256()
    _update_framed_digest(
        digest,
        {"version": 2, "domain": domain, "exclude_targets": exclude_targets},
    )
    with _connect_read_only(path) as connection:
        _update_framed_digest(
            digest,
            {
                "schema": _schema_entries(
                    connection,
                    exclude_market_target=exclude_targets and domain == "market",
                )
            },
        )
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        for table in tables:
            if exclude_targets and domain == "market" and table == "iv_history":
                continue
            columns, cursor = _ordered_table_cursor(connection, table)
            _update_framed_digest(digest, {"table": table, "columns": columns})
            for raw_row in cursor:
                row = _normalize_row(raw_row)
                if exclude_targets and domain == "profile":
                    if table == "scheduler_state" and "source" in columns:
                        if row[columns.index("source")] in TARGET_SOURCES:
                            continue
                    elif table == "profile_settings" and "key" in columns:
                        if _is_target_setting(row[columns.index("key")]):
                            continue
                elif exclude_targets and domain == "market" and table == "market_sync_meta":
                    if row[columns.index("domain")] == "iv":
                        continue
                _update_framed_digest(digest, row)
            _update_framed_digest(digest, {"table_end": table})
    return digest.hexdigest()


def _database_fingerprint(path: Path, *, domain: str) -> Mapping[str, object]:
    stat_result = path.stat()
    return {
        "size": stat_result.st_size,
        "mtime_ns": stat_result.st_mtime_ns,
        "logical_sha256": _logical_database_digest(path, domain=domain, exclude_targets=False),
    }


def _parquet_rows(frame: pd.DataFrame) -> list[list[object]]:
    if tuple(frame.columns) != PARQUET_COLUMNS:
        raise MigrationError("iv_parquet_schema_mismatch")
    rows = [
        [_normalize(value) for value in row]
        for row in frame.loc[:, list(PARQUET_COLUMNS)].itertuples(index=False, name=None)
    ]
    rows.sort(key=_canonical_bytes)
    return rows


def _parquet_report(path: Path) -> Mapping[str, object]:
    if path.is_symlink() or not path.is_file():
        raise MigrationError("iv_parquet_path_invalid")
    frame = pd.read_parquet(path)
    rows = _parquet_rows(frame)
    return {
        "name": path.name,
        "row_count": len(rows),
        "columns": list(frame.columns),
        "dtypes": [str(frame[column].dtype) for column in frame.columns],
        "rows": rows,
        "rows_sha256": _sha256_bytes(_canonical_bytes(rows)),
        "sha256": _file_sha256(path),
        "size": path.stat().st_size,
        "mtime_ns": path.stat().st_mtime_ns,
        "mode": stat.S_IMODE(path.stat().st_mode),
    }


def _parquet_reports(directory: Path) -> tuple[Mapping[str, object], ...]:
    if not directory.is_dir():
        raise MigrationError("iv_parquet_directory_missing")
    reports = [
        _parquet_report(path)
        for path in sorted(directory.glob("*.parquet"), key=lambda item: item.name)
    ]
    if not reports:
        raise MigrationError("iv_parquet_files_missing")
    return tuple(reports)


def _profile_targets(path: Path) -> Mapping[str, object]:
    placeholders = ",".join("?" for _ in TARGET_SOURCES)
    with _connect_read_only(path) as connection:
        health = _database_health(connection)
        scheduler = _dict_rows(
            connection,
            f"SELECT * FROM scheduler_state WHERE source IN ({placeholders}) ORDER BY source",
            TARGET_SOURCES,
        )
        all_settings = _dict_rows(connection, "SELECT * FROM profile_settings ORDER BY key")
        settings = [row for row in all_settings if _is_target_setting(row.get("key"))]
        jobs = _dict_rows(
            connection,
            f"SELECT * FROM job_runs WHERE job_name IN ({placeholders}) ORDER BY id",
            TARGET_JOB_NAMES,
        )
    if any(row.get("last_status") == "running" for row in scheduler):
        raise MigrationError("active_legacy_source")
    if any(row.get("status") == "running" for row in jobs):
        raise MigrationError("active_legacy_job")
    status_counts = {
        status: sum(1 for row in jobs if row.get("status") == status)
        for status in sorted({str(row["status"]) for row in jobs})
    }
    return {
        "scheduler_state_count": len(scheduler),
        "scheduler_state": scheduler,
        "profile_settings_count": len(settings),
        "profile_settings": settings,
        "job_runs_count": len(jobs),
        "job_run_status_counts": status_counts,
        "job_runs_sha256": _sha256_bytes(_canonical_bytes(jobs)),
        "health": health,
        "source_fingerprint": _database_fingerprint(path, domain="profile"),
    }


def _validate_iv_schema(connection: sqlite3.Connection) -> tuple[str, str]:
    table = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='iv_history'"
    ).fetchone()
    if table is None:
        raise MigrationError("iv_schema_missing")
    columns = tuple(
        (row[1], str(row[2]).upper(), int(row[3]), int(row[5]))
        for row in connection.execute("PRAGMA table_info(iv_history)")
    )
    if columns != IV_COLUMNS:
        raise MigrationError("iv_schema_mismatch")

    indexes = connection.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='iv_history' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    if len(indexes) != 1 or indexes[0][0] != "idx_iv_ticker_date":
        raise MigrationError("iv_index_mismatch")
    index_columns = tuple(row[2] for row in connection.execute("PRAGMA index_info(idx_iv_ticker_date)"))
    if index_columns != ("ticker", "date"):
        raise MigrationError("iv_index_mismatch")

    for row in connection.execute(
        "SELECT type, name, sql FROM sqlite_master WHERE type IN ('view','trigger') ORDER BY type,name"
    ):
        if row[2] and "iv_history" in row[2].lower():
            raise MigrationError("iv_schema_dependency")
    for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ):
        for foreign_key in connection.execute(f"PRAGMA foreign_key_list({_quote(row[0])})"):
            if foreign_key[2] == "iv_history":
                raise MigrationError("iv_schema_dependency")
    return str(table[0]), str(indexes[0][1])


def _market_targets(path: Path) -> Mapping[str, object]:
    with _connect_read_only(path) as connection:
        health = _database_health(connection)
        table_sql, index_sql = _validate_iv_schema(connection)
        rows = _dict_rows(connection, "SELECT * FROM iv_history ORDER BY id")
        sync = _dict_rows(
            connection,
            "SELECT * FROM market_sync_meta WHERE domain='iv' ORDER BY domain",
        )
    ids = [int(row["id"]) for row in rows]
    dates = [str(row["date"]) for row in rows]
    tickers = sorted({str(row["ticker"]) for row in rows})
    return {
        "table_sql": table_sql,
        "index_sql": index_sql,
        "row_count": len(rows),
        "ticker_count": len(tickers),
        "tickers": tickers,
        "id_bounds": [min(ids), max(ids)] if ids else [None, None],
        "date_bounds": [min(dates), max(dates)] if dates else [None, None],
        "rows": rows,
        "rows_sha256": _sha256_bytes(_canonical_bytes(rows)),
        "market_sync_meta": sync,
        "health": health,
        "source_fingerprint": _database_fingerprint(path, domain="market"),
    }


def _sqlite_value_rows(market_targets: Mapping[str, object]) -> list[list[object]]:
    rows = []
    for row in market_targets["rows"]:
        assert isinstance(row, Mapping)
        rows.append([row[column] for column in PARQUET_COLUMNS])
    rows.sort(key=_canonical_bytes)
    return rows


def _preview_payload(report: PreviewReport) -> Mapping[str, object]:
    return {
        "pre_retirement_commit": report.pre_retirement_commit,
        "profile_targets": report.profile_targets,
        "market_targets": report.market_targets,
        "parquet_targets": list(report.parquet_targets),
        "preserved_job_runs_sha256": report.preserved_job_runs_sha256,
        "non_target_digests": report.non_target_digests,
    }


def _report_from_mapping(value: Mapping[str, object]) -> PreviewReport:
    return PreviewReport(
        preview_sha256=str(value["preview_sha256"]),
        pre_retirement_commit=str(value["pre_retirement_commit"]),
        profile_targets=value["profile_targets"],
        market_targets=value["market_targets"],
        parquet_targets=tuple(value["parquet_targets"]),
        preserved_job_runs_sha256=str(value["preserved_job_runs_sha256"]),
        non_target_digests=value["non_target_digests"],
    )


def preview_retirement(
    paths: RetirementPaths,
    *,
    pre_retirement_commit: str = PRE_RETIREMENT_COMMIT,
) -> PreviewReport:
    profile = _profile_targets(paths.profile_db)
    market = dict(_market_targets(paths.market_db))
    parquets = _parquet_reports(paths.iv_parquet_dir)
    parquet_rows = [row for report in parquets for row in report["rows"]]
    parquet_rows.sort(key=_canonical_bytes)
    sqlite_rows = _sqlite_value_rows(market)
    matches = sqlite_rows == parquet_rows
    market["sqlite_parquet_value_multiset_match"] = matches
    if not matches:
        raise MigrationError("iv_value_mismatch")
    report = PreviewReport(
        preview_sha256="",
        pre_retirement_commit=pre_retirement_commit,
        profile_targets=profile,
        market_targets=market,
        parquet_targets=parquets,
        preserved_job_runs_sha256=str(profile["job_runs_sha256"]),
        non_target_digests={
            "profile": _logical_database_digest(
                paths.profile_db, domain="profile", exclude_targets=True
            ),
            "market": _logical_database_digest(
                paths.market_db, domain="market", exclude_targets=True
            ),
        },
    )
    digest = _sha256_bytes(_canonical_bytes(_preview_payload(report)))
    return PreviewReport(
        preview_sha256=digest,
        pre_retirement_commit=report.pre_retirement_commit,
        profile_targets=report.profile_targets,
        market_targets=report.market_targets,
        parquet_targets=report.parquet_targets,
        preserved_job_runs_sha256=report.preserved_job_runs_sha256,
        non_target_digests=report.non_target_digests,
    )


def _write_bytes_atomic(path: Path, payload: bytes, mode: int = 0o600) -> None:
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def _write_json_atomic(path: Path, value: object) -> None:
    _write_bytes_atomic(path, _canonical_bytes(value) + b"\n")


def _archive_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _create_mini_database(path: Path, preview: PreviewReport) -> None:
    target = preview.market_targets
    columns = [column[0] for column in IV_COLUMNS]
    placeholders = ",".join("?" for _ in columns)
    with sqlite3.connect(path) as connection:
        connection.execute(str(target["table_sql"]))
        rows = target["rows"]
        connection.executemany(
            f"INSERT INTO iv_history ({','.join(map(_quote, columns))}) VALUES ({placeholders})",
            [[row[column] for column in columns] for row in rows],
        )
        connection.execute(str(target["index_sql"]))
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise MigrationError("archive_database_invalid")
    os.chmod(path, 0o600)


def _artifact_hashes(root: Path, relative_paths: Iterable[str]) -> Mapping[str, str]:
    return {name: _file_sha256(root / name) for name in sorted(relative_paths)}


def create_archive(paths: RetirementPaths, preview: PreviewReport) -> Path:
    try:
        current = preview_retirement(
            paths,
            pre_retirement_commit=preview.pre_retirement_commit,
        )
    except (MigrationError, OSError, sqlite3.Error, ValueError) as exc:
        raise MigrationError("source_drift") from exc
    if current != preview:
        raise MigrationError("source_drift")

    paths.backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(paths.backup_root, 0o700)
    final = paths.backup_root / f"legacy_scheduler_iv_retirement_{_archive_timestamp()}"
    temporary = final.with_name(f".{final.name}.tmp-{os.getpid()}")
    temporary.mkdir(mode=0o700)
    try:
        parquet_archive = temporary / "parquet"
        parquet_archive.mkdir(mode=0o700)
        _create_mini_database(temporary / "legacy_iv.sqlite3", preview)
        _write_json_atomic(
            temporary / "profile_state.json",
            {
                "scheduler_state": preview.profile_targets["scheduler_state"],
                "profile_settings": preview.profile_targets["profile_settings"],
            },
        )
        _write_json_atomic(
            temporary / "market_sync_state.json",
            {"market_sync_meta": preview.market_targets["market_sync_meta"]},
        )
        for report in preview.parquet_targets:
            source = paths.iv_parquet_dir / str(report["name"])
            destination = parquet_archive / source.name
            shutil.copyfile(source, destination)
            os.chmod(destination, 0o600)
        _write_bytes_atomic(
            temporary / "RESTORE.txt",
            (
                "Stop all ArkScope processes, check out commit "
                f"{preview.pre_retirement_commit}, then run this tool's restore mode.\n"
            ).encode("utf-8"),
        )
        relative_artifacts = [
            "legacy_iv.sqlite3",
            "profile_state.json",
            "market_sync_state.json",
            "RESTORE.txt",
            *[f"parquet/{report['name']}" for report in preview.parquet_targets],
        ]
        manifest = {
            "version": 1,
            "phase": "archived",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "preview_sha256": preview.preview_sha256,
            "pre_retirement_commit": preview.pre_retirement_commit,
            "preview": asdict(preview),
            "source_paths": {
                "profile_db": str(paths.profile_db.resolve()),
                "market_db": str(paths.market_db.resolve()),
                "iv_parquet_dir": str(paths.iv_parquet_dir.resolve()),
            },
            "artifacts": _artifact_hashes(temporary, relative_artifacts),
            "preserved_job_runs_sha256": preview.preserved_job_runs_sha256,
            "non_target_digests": dict(preview.non_target_digests),
            "post_apply_digests": {},
        }
        _write_json_atomic(temporary / "manifest.json", manifest)
        os.replace(temporary, final)
        parent_fd = os.open(paths.backup_root, os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    verify_archive(final)
    return final


def _safe_artifact_path(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise MigrationError("archive_tampered") from exc
    return candidate


def verify_archive(archive_dir: Path) -> Mapping[str, object]:
    archive_dir = archive_dir.resolve()
    manifest_path = archive_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise MigrationError("archive_tampered") from exc
    if stat.S_IMODE(archive_dir.stat().st_mode) != 0o700:
        raise MigrationError("archive_mode_invalid")
    if manifest_path.is_symlink() or stat.S_IMODE(manifest_path.stat().st_mode) != 0o600:
        raise MigrationError("archive_mode_invalid")
    if manifest.get("phase") not in PHASES:
        raise MigrationError("archive_tampered")
    report = _report_from_mapping(manifest["preview"])
    if report.preview_sha256 != manifest.get("preview_sha256"):
        raise MigrationError("archive_tampered")
    if _sha256_bytes(_canonical_bytes(_preview_payload(report))) != report.preview_sha256:
        raise MigrationError("archive_tampered")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise MigrationError("archive_tampered")
    required_artifacts = {
        "legacy_iv.sqlite3",
        "profile_state.json",
        "market_sync_state.json",
        "RESTORE.txt",
        *[f"parquet/{item['name']}" for item in report.parquet_targets],
    }
    if set(artifacts) != required_artifacts:
        raise MigrationError("archive_tampered")
    expected_entries = required_artifacts | {"manifest.json", "parquet"}
    actual_entries = {
        str(path.relative_to(archive_dir))
        for path in archive_dir.rglob("*")
    }
    if actual_entries != expected_entries:
        raise MigrationError("archive_tampered")
    parquet_dir = archive_dir / "parquet"
    if parquet_dir.is_symlink() or stat.S_IMODE(parquet_dir.stat().st_mode) != 0o700:
        raise MigrationError("archive_mode_invalid")
    for relative, expected in artifacts.items():
        path = _safe_artifact_path(archive_dir, str(relative))
        if not path.is_file() or path.is_symlink():
            raise MigrationError("archive_tampered")
        if stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise MigrationError("archive_mode_invalid")
        if _file_sha256(path) != expected:
            raise MigrationError("archive_tampered")
    with _connect_read_only(archive_dir / "legacy_iv.sqlite3") as connection:
        _database_health(connection)
        _validate_iv_schema(connection)
    return manifest


def _find_archive(root: Path, preview_sha256: str) -> Path | None:
    if not root.is_dir():
        return None
    matches: list[Path] = []
    for path in sorted(root.glob("legacy_scheduler_iv_retirement_*")):
        manifest_path = path / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if manifest.get("preview_sha256") == preview_sha256:
            matches.append(path)
    if len(matches) > 1:
        raise MigrationError("ambiguous_archive")
    return matches[0] if matches else None


def _load_report(manifest: Mapping[str, object]) -> PreviewReport:
    return _report_from_mapping(manifest["preview"])


def _write_manifest_phase(
    archive_dir: Path,
    manifest: Mapping[str, object],
    phase: str,
    *,
    post_apply_digests: Mapping[str, str] | None = None,
) -> Mapping[str, object]:
    updated = dict(manifest)
    updated["phase"] = phase
    updated["updated_at"] = datetime.now(timezone.utc).isoformat()
    if post_apply_digests is not None:
        updated["post_apply_digests"] = dict(post_apply_digests)
    _write_json_atomic(archive_dir / "manifest.json", updated)
    return updated


def _after_phase_checkpoint(phase: str) -> None:
    del phase


def _target_profile_rows(path: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    placeholders = ",".join("?" for _ in TARGET_SOURCES)
    with _connect_read_only(path) as connection:
        scheduler = _dict_rows(
            connection,
            f"SELECT * FROM scheduler_state WHERE source IN ({placeholders}) ORDER BY source",
            TARGET_SOURCES,
        )
        settings = [
            row
            for row in _dict_rows(connection, "SELECT * FROM profile_settings ORDER BY key")
            if _is_target_setting(row.get("key"))
        ]
    return scheduler, settings


def _target_market_state(path: Path) -> tuple[bool, list[dict[str, object]]]:
    with _connect_read_only(path) as connection:
        table_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='iv_history'"
        ).fetchone() is not None
        sync = _dict_rows(
            connection,
            "SELECT * FROM market_sync_meta WHERE domain='iv' ORDER BY domain",
        )
    return table_exists, sync


def _target_jobs_digest(path: Path) -> str:
    placeholders = ",".join("?" for _ in TARGET_JOB_NAMES)
    with _connect_read_only(path) as connection:
        rows = _dict_rows(
            connection,
            f"SELECT * FROM job_runs WHERE job_name IN ({placeholders}) ORDER BY id",
            TARGET_JOB_NAMES,
        )
    return _sha256_bytes(_canonical_bytes(rows))


def _verify_preserved(paths: RetirementPaths, report: PreviewReport) -> Mapping[str, str]:
    digests = {
        "profile": _logical_database_digest(
            paths.profile_db, domain="profile", exclude_targets=True
        ),
        "market": _logical_database_digest(
            paths.market_db, domain="market", exclude_targets=True
        ),
        "job_runs": _target_jobs_digest(paths.profile_db),
    }
    if digests["profile"] != report.non_target_digests["profile"]:
        raise MigrationError("profile_non_target_drift")
    if digests["market"] != report.non_target_digests["market"]:
        raise MigrationError("market_non_target_drift")
    if digests["job_runs"] != report.preserved_job_runs_sha256:
        raise MigrationError("job_runs_drift")
    return digests


def _assert_profile_original(paths: RetirementPaths, report: PreviewReport) -> None:
    if _database_fingerprint(paths.profile_db, domain="profile") != report.profile_targets["source_fingerprint"]:
        raise MigrationError("source_drift")
    scheduler, settings = _target_profile_rows(paths.profile_db)
    if scheduler != report.profile_targets["scheduler_state"]:
        raise MigrationError("source_drift")
    if settings != report.profile_targets["profile_settings"]:
        raise MigrationError("source_drift")


def _assert_market_original(paths: RetirementPaths, report: PreviewReport) -> None:
    if _database_fingerprint(paths.market_db, domain="market") != report.market_targets["source_fingerprint"]:
        raise MigrationError("source_drift")
    current = _market_targets(paths.market_db)
    for key in ("table_sql", "index_sql", "rows", "market_sync_meta"):
        if current[key] != report.market_targets[key]:
            raise MigrationError("source_drift")


def _assert_files_original(paths: RetirementPaths, report: PreviewReport) -> None:
    if _parquet_reports(paths.iv_parquet_dir) != report.parquet_targets:
        raise MigrationError("source_drift")


def _apply_profile(paths: RetirementPaths, report: PreviewReport) -> None:
    _assert_profile_original(paths, report)
    settings = [str(row["key"]) for row in report.profile_targets["profile_settings"]]
    with sqlite3.connect(paths.profile_db) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "DELETE FROM scheduler_state WHERE source IN (?, ?, ?)",
            TARGET_SOURCES,
        )
        if settings:
            placeholders = ",".join("?" for _ in settings)
            connection.execute(
                f"DELETE FROM profile_settings WHERE key IN ({placeholders})",
                settings,
            )
        connection.commit()
    if any(_target_profile_rows(paths.profile_db)):
        raise MigrationError("profile_apply_failed")


def _profile_owner_state(paths: RetirementPaths, report: PreviewReport) -> str:
    scheduler, settings = _target_profile_rows(paths.profile_db)
    if (
        scheduler == report.profile_targets["scheduler_state"]
        and settings == report.profile_targets["profile_settings"]
    ):
        return "original"
    if not scheduler and not settings:
        return "applied"
    raise MigrationError("profile_checkpoint_mismatch")


def _apply_market(paths: RetirementPaths, report: PreviewReport) -> None:
    _assert_market_original(paths, report)
    with sqlite3.connect(paths.market_db) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM market_sync_meta WHERE domain='iv'")
        connection.execute("DROP TABLE iv_history")
        connection.commit()
    table_exists, sync = _target_market_state(paths.market_db)
    if table_exists or sync:
        raise MigrationError("market_apply_failed")


def _market_owner_state(paths: RetirementPaths, report: PreviewReport) -> str:
    table_exists, sync = _target_market_state(paths.market_db)
    if not table_exists and not sync:
        return "applied"
    if table_exists and sync == report.market_targets["market_sync_meta"]:
        return "original"
    raise MigrationError("market_checkpoint_mismatch")


def _apply_files(paths: RetirementPaths, report: PreviewReport) -> None:
    if not paths.iv_parquet_dir.is_dir():
        raise MigrationError("iv_parquet_directory_missing")
    expected = {str(item["name"]): item for item in report.parquet_targets}
    current_paths = sorted(paths.iv_parquet_dir.glob("*.parquet"), key=lambda item: item.name)
    if any(path.name not in expected for path in current_paths):
        raise MigrationError("source_drift")
    for path in current_paths:
        if _parquet_report(path) != expected[path.name]:
            raise MigrationError("source_drift")
    for path in current_paths:
        path.unlink()
    directory_fd = os.open(paths.iv_parquet_dir, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    if list(paths.iv_parquet_dir.glob("*.parquet")):
        raise MigrationError("files_apply_failed")


def _verify_applied(paths: RetirementPaths, report: PreviewReport) -> Mapping[str, str]:
    scheduler, settings = _target_profile_rows(paths.profile_db)
    table_exists, sync = _target_market_state(paths.market_db)
    files = list(paths.iv_parquet_dir.glob("*.parquet")) if paths.iv_parquet_dir.exists() else []
    if scheduler or settings or table_exists or sync or files:
        raise MigrationError("apply_incomplete")
    with _connect_read_only(paths.profile_db) as connection:
        _database_health(connection)
    with _connect_read_only(paths.market_db) as connection:
        _database_health(connection)
    return _verify_preserved(paths, report)


def apply_retirement(
    paths: RetirementPaths,
    *,
    expected_preview_sha256: str,
    expected_pre_retirement_commit: str,
) -> Mapping[str, object]:
    if expected_pre_retirement_commit != PRE_RETIREMENT_COMMIT:
        raise MigrationError("pre_retirement_commit_mismatch")

    archive_dir = _find_archive(paths.backup_root, expected_preview_sha256)
    if archive_dir is None:
        preview = preview_retirement(
            paths,
            pre_retirement_commit=expected_pre_retirement_commit,
        )
        if preview.preview_sha256 != expected_preview_sha256:
            raise MigrationError("preview_sha256_mismatch")
        archive_dir = create_archive(paths, preview)
    manifest = verify_archive(archive_dir)
    report = _load_report(manifest)
    if report.preview_sha256 != expected_preview_sha256:
        raise MigrationError("preview_sha256_mismatch")
    if report.pre_retirement_commit != expected_pre_retirement_commit:
        raise MigrationError("pre_retirement_commit_mismatch")

    initial_phase = str(manifest["phase"])
    if initial_phase == "complete":
        _verify_applied(paths, report)
        return {
            "phase": "complete",
            "archive_dir": str(archive_dir),
            "already_applied": True,
            "resumed_from": "complete",
        }

    phase_index = PHASES.index(initial_phase)
    if phase_index < PHASES.index("profile_applied"):
        if _profile_owner_state(paths, report) == "original":
            _apply_profile(paths, report)
        _verify_preserved(paths, report)
        manifest = _write_manifest_phase(archive_dir, manifest, "profile_applied")
        _after_phase_checkpoint("profile_applied")
        phase_index = PHASES.index("profile_applied")
    else:
        scheduler, settings = _target_profile_rows(paths.profile_db)
        if scheduler or settings:
            raise MigrationError("profile_checkpoint_mismatch")

    if phase_index < PHASES.index("market_applied"):
        if _market_owner_state(paths, report) == "original":
            _apply_market(paths, report)
        _verify_preserved(paths, report)
        manifest = _write_manifest_phase(archive_dir, manifest, "market_applied")
        _after_phase_checkpoint("market_applied")
        phase_index = PHASES.index("market_applied")
    else:
        table_exists, sync = _target_market_state(paths.market_db)
        if table_exists or sync:
            raise MigrationError("market_checkpoint_mismatch")

    if phase_index < PHASES.index("files_applied"):
        _apply_files(paths, report)
        _verify_preserved(paths, report)
        manifest = _write_manifest_phase(archive_dir, manifest, "files_applied")
        _after_phase_checkpoint("files_applied")

    post_digests = _verify_applied(paths, report)
    manifest = _write_manifest_phase(
        archive_dir,
        manifest,
        "complete",
        post_apply_digests=post_digests,
    )
    _after_phase_checkpoint("complete")
    return {
        "phase": str(manifest["phase"]),
        "archive_dir": str(archive_dir),
        "already_applied": False,
        "resumed_from": initial_phase if initial_phase != "archived" else None,
    }


def _git_head(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _insert_dict_rows(connection: sqlite3.Connection, table: str, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        return
    columns = list(rows[0])
    placeholders = ",".join("?" for _ in columns)
    connection.executemany(
        f"INSERT INTO {_quote(table)} ({','.join(map(_quote, columns))}) VALUES ({placeholders})",
        [[row[column] for column in columns] for row in rows],
    )


def _assert_restore_targets_empty(paths: RetirementPaths) -> None:
    scheduler, settings = _target_profile_rows(paths.profile_db)
    table_exists, sync = _target_market_state(paths.market_db)
    files = list(paths.iv_parquet_dir.glob("*.parquet")) if paths.iv_parquet_dir.exists() else []
    if scheduler or settings or table_exists or sync or files:
        raise MigrationError("restore_target_conflict")


def restore_retirement(
    archive_dir: Path,
    paths: RetirementPaths,
    *,
    repo_root: Path,
    expected_current_commit: str,
) -> Mapping[str, object]:
    manifest = verify_archive(archive_dir)
    report = _load_report(manifest)
    if manifest["phase"] != "complete":
        raise MigrationError("archive_not_complete")
    if expected_current_commit != report.pre_retirement_commit:
        raise MigrationError("restore_commit_mismatch")
    try:
        actual_commit = _git_head(repo_root)
    except (OSError, subprocess.SubprocessError) as exc:
        raise MigrationError("restore_commit_unavailable") from exc
    if actual_commit != expected_current_commit:
        raise MigrationError("restore_commit_mismatch")

    _assert_restore_targets_empty(paths)
    _verify_preserved(paths, report)

    profile_state = json.loads((archive_dir / "profile_state.json").read_text(encoding="utf-8"))
    market_state = json.loads((archive_dir / "market_sync_state.json").read_text(encoding="utf-8"))
    with sqlite3.connect(paths.profile_db) as connection:
        connection.execute("BEGIN IMMEDIATE")
        _insert_dict_rows(connection, "scheduler_state", profile_state["scheduler_state"])
        _insert_dict_rows(connection, "profile_settings", profile_state["profile_settings"])
        connection.commit()

    with _connect_read_only(archive_dir / "legacy_iv.sqlite3") as archived:
        table_sql, index_sql = _validate_iv_schema(archived)
        rows = _dict_rows(archived, "SELECT * FROM iv_history ORDER BY id")
    with sqlite3.connect(paths.market_db) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(table_sql)
        _insert_dict_rows(connection, "iv_history", rows)
        connection.execute(index_sql)
        _insert_dict_rows(connection, "market_sync_meta", market_state["market_sync_meta"])
        connection.commit()

    paths.iv_parquet_dir.mkdir(parents=True, exist_ok=True)
    archived_reports = {str(item["name"]): item for item in report.parquet_targets}
    for name, item in archived_reports.items():
        destination = paths.iv_parquet_dir / name
        shutil.copyfile(archive_dir / "parquet" / name, destination)
        os.chmod(destination, int(item["mode"]))
        os.utime(destination, ns=(int(item["mtime_ns"]), int(item["mtime_ns"])))

    scheduler, settings = _target_profile_rows(paths.profile_db)
    current_market = _market_targets(paths.market_db)
    current_parquets = _parquet_reports(paths.iv_parquet_dir)
    if scheduler != report.profile_targets["scheduler_state"]:
        raise MigrationError("restore_verification_failed")
    if settings != report.profile_targets["profile_settings"]:
        raise MigrationError("restore_verification_failed")
    for key in ("table_sql", "index_sql", "rows", "market_sync_meta"):
        if current_market[key] != report.market_targets[key]:
            raise MigrationError("restore_verification_failed")
    if current_parquets != report.parquet_targets:
        raise MigrationError("restore_verification_failed")
    _verify_preserved(paths, report)
    return {"restored": True, "archive_dir": str(archive_dir), "phase": "restored"}


def _paths_from_args(args: argparse.Namespace) -> RetirementPaths:
    return RetirementPaths(
        profile_db=Path(args.profile_db),
        market_db=Path(args.market_db),
        iv_parquet_dir=Path(args.iv_parquet_dir),
        backup_root=Path(getattr(args, "backup_root", ".")),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode", required=True)
    for mode in ("preview", "apply"):
        command = subparsers.add_parser(mode)
        command.add_argument("--profile-db", required=True)
        command.add_argument("--market-db", required=True)
        command.add_argument("--iv-parquet-dir", required=True)
        command.add_argument("--backup-root", required=True)
        command.add_argument("--output", required=True)
        if mode == "apply":
            command.add_argument("--expected-preview-sha256", required=True)
            command.add_argument("--expected-pre-retirement-commit", required=True)
    restore = subparsers.add_parser("restore")
    restore.add_argument("--archive-dir", required=True)
    restore.add_argument("--profile-db", required=True)
    restore.add_argument("--market-db", required=True)
    restore.add_argument("--iv-parquet-dir", required=True)
    restore.add_argument("--repo-root", required=True)
    restore.add_argument("--expected-current-commit", required=True)
    restore.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.mode == "preview":
        result: object = asdict(preview_retirement(_paths_from_args(args)))
    elif args.mode == "apply":
        result = apply_retirement(
            _paths_from_args(args),
            expected_preview_sha256=args.expected_preview_sha256,
            expected_pre_retirement_commit=args.expected_pre_retirement_commit,
        )
    else:
        result = restore_retirement(
            Path(args.archive_dir),
            RetirementPaths(
                profile_db=Path(args.profile_db),
                market_db=Path(args.market_db),
                iv_parquet_dir=Path(args.iv_parquet_dir),
                backup_root=Path(args.archive_dir).parent,
            ),
            repo_root=Path(args.repo_root),
            expected_current_commit=args.expected_current_commit,
        )
    _write_json_atomic(Path(args.output), result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
