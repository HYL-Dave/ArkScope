"""Attended, backed-up Web journal installation; never a profile bootstrap."""

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3

from src.lifecycle_web_schema import _install_on_connection, schema_digest, verify_web_journal
from src.security_lifecycle_listing_migration import _encode_cell, _quote_identifier, _sha_file
from src.security_lifecycle_provider_snapshot import instant
from src.security_lifecycle_schema import assert_lifecycle_writes_available, verify_profile_connection


def _snapshot(conn, *, exclude_web=False):
    schema = [tuple(row) for row in conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name")]
    if exclude_web:
        schema = [row for row in schema if not row[2].startswith("lifecycle_web_")]
    schema_sha = hashlib.sha256(json.dumps(schema, ensure_ascii=True, separators=(",", ":")).encode()).hexdigest()
    rows = hashlib.sha256()
    for kind, name, _, _ in schema:
        if kind != "table":
            continue
        rows.update(_encode_cell(name))
        for row in conn.execute(f"SELECT * FROM {_quote_identifier(name)} ORDER BY rowid"):
            rows.update(b"row:")
            for cell in row:
                value = _encode_cell(cell)
                rows.update(str(len(value)).encode() + b":" + value)
    return schema_sha, rows.hexdigest()


def _preview(conn):
    verify_profile_connection(conn)
    if conn.execute("PRAGMA integrity_check").fetchall() != [("ok",)] or conn.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("web_installation_integrity")
    installed = bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name LIKE 'lifecycle_web_%'").fetchone())
    if installed:
        verify_web_journal(conn)
    schema_sha, rows_sha = _snapshot(conn)
    value = {"version": 1, "installed": installed, "schema_sha256": schema_sha, "rows_sha256": rows_sha, "target_schema_sha256": schema_digest()}
    return {**value, "approval_sha256": hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}


def preview_web_installation(path):
    with sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True) as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        return _preview(conn)


def _backup(conn, path):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    with sqlite3.connect(path) as destination:
        conn.backup(destination)


def apply_web_installation(path, *, backup_path, approval_sha256, at, app_stopped):
    if app_stopped is not True:
        raise ValueError("web_installation_app_stop_required")
    instant(at)
    if not isinstance(approval_sha256, str) or not re.fullmatch("[0-9a-f]{64}", approval_sha256):
        raise ValueError("web_installation_approval_invalid")
    path, backup = Path(path).resolve(), Path(backup_path).resolve()
    if path == backup:
        raise ValueError("web_installation_backup_path")
    with sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=10) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        before = _preview(conn)
        if before["approval_sha256"] != approval_sha256:
            raise ValueError("web_installation_preview_changed")
        assert_lifecycle_writes_available(conn)
        if before["installed"]:
            return {"changed": False, **before}
        _backup(conn, backup)
        if preview_web_installation(backup)["approval_sha256"] != approval_sha256:
            raise ValueError("web_installation_backup_changed")
        conn.execute("BEGIN IMMEDIATE")
        try:
            if _preview(conn)["approval_sha256"] != approval_sha256:
                raise ValueError("web_installation_preview_changed")
            _install_on_connection(conn, at=at)
            if _snapshot(conn, exclude_web=True) != (before["schema_sha256"], before["rows_sha256"]):
                raise ValueError("web_installation_existing_data_changed")
            after = _preview(conn)
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    return {"changed": True, **after, "previous_approval_sha256": approval_sha256,
            "previous_rows_sha256": before["rows_sha256"], "backup_sha256": _sha_file(backup), "installed_at": at}
