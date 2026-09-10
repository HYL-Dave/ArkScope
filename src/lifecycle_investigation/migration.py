"""Explicit backed-up journal cutover, with unchanged existing profile contents."""

from contextlib import closing
import hashlib
from pathlib import Path
import sqlite3

from src.lifecycle_investigation.schema import installed, schema_digest, verify_journal, _install_on_connection
from src.lifecycle_journal_codec import digest_json
from src.lifecycle_web_migration import _backup
from src.security_lifecycle_listing_migration import _encode_cell, _quote_identifier as q, _sha_file
from src.security_lifecycle_provider_snapshot import instant
from src.security_lifecycle_schema import verify_profile_connection, assert_lifecycle_writes_available


def _snapshot(conn, names=None):
    schema = [tuple(row) for row in conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name")
        if names is None or row[2] in names]
    rows = hashlib.sha256()
    for kind, name, _, _ in schema:
        if kind != "table":
            continue
        rows.update(_encode_cell(name))
        primary = sorted((row[5], row[1]) for row in conn.execute(f"PRAGMA table_info({q(name)})") if row[5])
        order = ",".join(q(column) for _, column in primary) or "rowid"
        for row in conn.execute(f"SELECT * FROM {q(name)} ORDER BY {order}"):
            rows.update(b"row:")
            for cell in row:
                value = _encode_cell(cell)
                rows.update(str(len(value)).encode() + b":" + value)
    return {"schema_sha256": digest_json(schema), "rows_sha256": rows.hexdigest()}


def _preview(conn):
    verify_profile_connection(conn)
    if conn.execute("PRAGMA integrity_check").fetchall() != [("ok",)] or conn.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("investigation_install_integrity")
    present = installed(conn)
    if present:
        verify_journal(conn)
    value = {"version": 2, "installed": present, "target_schema_sha256": schema_digest(), **_snapshot(conn)}
    return {**value, "approval_sha256": digest_json(value)}


def preview_installation(path):
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        return _preview(conn)


def apply_installation(path, *, backup_path, approval_sha256, at, app_stopped):
    if app_stopped is not True:
        raise ValueError("investigation_install_app_stop_required")
    instant(at)
    path, backup = Path(path).resolve(), Path(backup_path).resolve()
    if path == backup:
        raise ValueError("investigation_install_backup_path")
    with closing(sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=10)) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        before = _preview(conn)
        if before["approval_sha256"] != approval_sha256:
            raise ValueError("investigation_install_changed")
        assert_lifecycle_writes_available(conn)
        if before["installed"]:
            return {"changed": False, **before}
        _backup(conn, backup)
        if preview_installation(backup) != before:
            raise ValueError("investigation_install_backup_changed")
        conn.execute("BEGIN IMMEDIATE")
        try:
            if _preview(conn) != before:
                raise ValueError("investigation_install_changed")
            names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            old = _snapshot(conn, names)
            _install_on_connection(conn, at=at)
            if _snapshot(conn, names) != old:
                raise ValueError("investigation_install_existing_data_changed")
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    return {"changed": True, "approval_sha256": approval_sha256, "target_schema_sha256": schema_digest(),
        "backup_sha256": _sha_file(backup), "installed_at": at}
