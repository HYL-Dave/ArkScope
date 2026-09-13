"""Operator-only current-schema reset/uninstall with external durable audit."""

from contextlib import ExitStack
import sqlite3

from . import schema
from .capture_lock import CaptureDirectory, research_operation
from .operations import OperationReceipt, raw_backup
from .store import Store
from .maintenance import (_preview, _observe, _profile_admission, _profile_snapshot,
    _file_identity, _output_path, validate_preview, _require, _receipt, _recheck,
    _finish_failure, _quote, _write_transaction, _write_point)


def preview_schema_reset(paths, *, mode, profile_connection) -> dict:
    return _preview(paths, profile_connection, operation="schema", mode=mode)


def _drop_owned(conn, owned):
    # The inventory is evidence, never the authority for new DROP targets.
    for kind in ("trigger", "index", "table"):
        for name in reversed(schema._DDL):
            for actual, (actual_kind, owner, _) in owned.items():
                if actual.lower() == name and actual_kind == kind:
                    _require((kind, owner.lower()) == schema._DDL[name][:2])
                    conn.execute(f"DROP {kind.upper()} {_quote(actual)}")


def apply_schema_reset(paths, preview, *, approval_sha256, backup_path,
                       receipt_path, profile_connection) -> dict:
    result, audit = _receipt(preview), None
    lifetime = ExitStack()
    try:
        validate_preview(preview, operation="schema", approval_sha256=approval_sha256)
        backup_only = preview["apply_effect"] == "raw_backup_only"
        _require(preview["status"] == "ready" or backup_only)
        profile_path, _ = _profile_admission(profile_connection)
        receipt_path = _output_path(paths, receipt_path, profile_path=profile_path)
        backup_path = _output_path(paths, backup_path, profile_path=profile_path)
        _require(receipt_path != backup_path and not receipt_path.is_relative_to(backup_path),
                 "sec_research_admin_path_invalid")
        _file_identity(paths.market_db_path)
        lifetime.enter_context(research_operation(paths.capture_root, exclusive=True))
        directory = CaptureDirectory(paths.capture_root)
        lifetime.callback(directory.close)

        def recheck():
            with Store(paths).connect(readonly=True) as conn, _profile_snapshot(profile_connection) as (profile, identity):
                conn.execute("BEGIN")
                current = _observe(paths, conn, directory, profile, identity, "schema", preview["mode"])
                _recheck(preview, current)
                return current

        current = recheck()
        result.update(retained_bytes=current["retained_bytes"],
                      selected=[item["name"] for item in current["owned_objects"]],
                      apply_effect=current["apply_effect"], references=current["references"],
                      reference_status=current["reference_status"])
        result["remaining"] = list(result["selected"])
        audit = OperationReceipt(receipt_path)
        lifetime.callback(audit.close)
        prepared = dict(result, phase="prepared")
        audit.write(prepared)
        result = prepared
        backup = raw_backup(paths, backup_path, observed_sha256=current["state_sha256"], recheck=recheck)
        result.update(phase="backed_up", backup={"path": str(backup_path),
            "format": backup["format"], "version": backup["version"],
            "database": backup["database"], "observed_sha256": backup["observed_sha256"],
            "capture_files": len(backup["captures"])})
        if backup_only:
            result.update(code="sec_research_unknown_owned_objects", recovery="inspect_raw_backup",
                          blocked=list(result["remaining"]))
        audit.write(result)
        if backup_only:
            return result
        current = recheck()
        # Only after proving namespace durability may absent-file charges
        # disappear with the old accounting tables. No writer lock for fsync.
        directory.sync()
        with _write_transaction(paths) as conn:
            _write_point(conn, current)
            _drop_owned(conn, schema._owned(conn))
            _require(not schema._owned(conn))
            if preview["mode"] == "reset":
                for _, _, ddl in schema._DDL.values():
                    conn.execute(ddl)
                conn.executemany("INSERT INTO sec_research_orphans VALUES(?,?)",
                                 [(item["key"], item["size_bytes"]) for item in backup["captures"]])
                schema.verify(conn)
                for table in schema._TABLES:
                    _require(conn.execute(f"PRAGMA foreign_key_check({_quote(table)})").fetchone() is None,
                             "sec_research_references_invalid")
        result.update(phase="schema_committed", removed=list(result["selected"]), remaining=[],
                      accounting="orphans_charged" if preview["mode"] == "reset" else "schema_absent")
        audit.write(result)
        completed = dict(result, status="ok", phase="complete", recovery="none")
        audit.write(completed)
        return completed
    except (ValueError, OSError, sqlite3.Error, TypeError, KeyError, KeyboardInterrupt) as exc:
        return _finish_failure(result, audit, exc)
    finally:
        lifetime.close()
