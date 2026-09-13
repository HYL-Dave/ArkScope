"""Explicit, digest-approved SEC orphan cleanup; previews never recover stores."""

from contextlib import contextmanager
import hashlib
import json
import os
import re
import sqlite3

from src.market_data_direct import market_write_lock
from . import schema
from .capture_lock import CaptureDirectory, research_operation
from .operations import _file, _path, _new_destination, _verify_database, _COUNTS, OperationReceipt
from .references import iter_research_sec_citations, sec_reference_closure, _ReferenceReader
from .captures import CaptureStore
from .store import Store


PREVIEW_FORMAT = "arkscope-sec-research-preview"
_PREVIEW_FIELDS = {"format", "version", "operation", "mode", "status", "code", "state_sha256",
                   "approval_sha256", "candidates", "references", "owned_objects", "schema_status",
                   "retained_bytes", "recovery", "apply_effect", "reference_status"}
_ROOT_TABLES = {"research_threads", "research_messages", "research_runs", "research_run_events"}
_ROOT_INDEXES = {"idx_research_threads_updated", "idx_research_messages_thread",
                 "idx_research_runs_thread", "idx_research_runs_status"}
_CODES = {"sec_research_preview_invalid", "sec_research_preview_stale", "sec_research_operation_busy",
          "sec_research_profile_invalid", "sec_research_profile_transaction_active", "sec_research_schema_mismatch",
          "sec_research_unknown_owned_objects", "sec_research_external_dependencies",
          "sec_research_reset_references_present", "sec_research_references_invalid", "capture_path_unsafe",
          "capture_platform_unsupported", "storage_space_insufficient", "sec_research_admin_path_invalid"}


def _require(condition, code="sec_research_preview_invalid"):
    if not condition:
        raise ValueError(code)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _code(exc):
    if isinstance(exc, KeyboardInterrupt):
        return "sec_research_admin_interrupted"
    if isinstance(exc, ValueError) and len(exc.args) == 1 and type(exc.args[0]) is str and exc.args[0] in _CODES:
        return exc.args[0]
    return "sec_research_admin_failed"


def _quote(name):
    return '"' + name.replace('"', '""') + '"'


def _file_identity(path):
    with _file(path) as handle:
        info = os.fstat(handle.fileno())
        _require(info.st_nlink == 1, "capture_path_unsafe")
        return [info.st_dev, info.st_ino]


def _profile_admission(conn):
    _require(isinstance(conn, sqlite3.Connection), "sec_research_profile_invalid")
    _require(not conn.in_transaction, "sec_research_profile_transaction_active")
    _require(conn.execute("PRAGMA query_only").fetchone()[0] == 1, "sec_research_profile_invalid")
    databases = list(conn.execute("PRAGMA database_list"))
    main = next((r[2] for r in databases if r[1] == "main"), None)
    _require(main, "sec_research_profile_invalid")
    path = _path(main)
    return path, _file_identity(path)


@contextmanager
def _profile_snapshot(conn):
    path, identity = _profile_admission(conn)
    # in_transaction cannot detect an unfinished autocommit SELECT cursor.
    # Own the connection as well as BEGIN, never inherit the caller's snapshot.
    fresh = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, isolation_level=None)
    try:
        fresh.execute("PRAGMA query_only=ON")
        fresh.execute("BEGIN")
        yield fresh, identity
    finally:
        fresh.close()


def _profile_roots(conn):
    objects = [tuple(row) for row in conn.execute("SELECT type,name,tbl_name,sql FROM sqlite_master")
               if row[3] is not None and (row[1].lower().startswith(("research_", "idx_research_"))
                                          or row[2].lower().startswith("research_"))]
    if not objects:
        return [], []
    _require({row[1] for row in objects if row[0] == "table"} == _ROOT_TABLES,
             "sec_research_profile_invalid")
    _require(all((kind == "table" and name in _ROOT_TABLES) or
                 (kind == "index" and name in _ROOT_INDEXES) for kind, name, _, _ in objects),
             "sec_research_profile_invalid")
    try:
        refs = list(iter_research_sec_citations(conn))
    except ValueError:
        raise ValueError("sec_research_references_invalid") from None
    return sorted(objects), refs


class _ObservedStore(Store):
    """Bind every existing graph reader to the same caller-owned market snapshot."""

    def __init__(self, paths, connection):
        super().__init__(paths)
        self.connection = connection

    @contextmanager
    def connect(self, readonly=False):
        _require(readonly)
        query_only = self.connection.execute("PRAGMA query_only").fetchone()[0]
        self.connection.execute("PRAGMA query_only=ON")
        try:
            yield self.connection
        finally:
            self.connection.execute(f"PRAGMA query_only={query_only}")


def _dependencies(conn, owned):
    """Use SQLite's FK metadata and compiler, including quoted/case-folded names."""
    targets = {name.lower() for name, (kind, _, _) in owned.items() if kind == "table"}
    objects = list(conn.execute("SELECT type,name,tbl_name FROM sqlite_master WHERE sql IS NOT NULL"))
    external = [(kind, name, owner) for kind, name, owner in objects
                if name not in owned and not name.lower().startswith("sqlite_")]
    for kind, name, _ in external:
        if kind == "table":
            if any(row[2].lower() in targets for row in conn.execute(f"PRAGMA foreign_key_list({_quote(name)})")):
                return True
    hit = False

    def authorizer(action, first, second, database, source):
        nonlocal hit
        if action in {sqlite3.SQLITE_READ, sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE}:
            hit = hit or (first or "").lower() in targets
        return sqlite3.SQLITE_OK

    for kind, name, owner in external:
        statements = []
        if kind == "view":
            statements = [f"EXPLAIN SELECT * FROM {_quote(name)}"]
        elif kind == "trigger":
            columns = [r[1] for r in conn.execute(f"PRAGMA table_xinfo({_quote(owner)})") if r[6] == 0]
            statements = [f"EXPLAIN DELETE FROM {_quote(owner)}",
                          f"EXPLAIN INSERT INTO {_quote(owner)} DEFAULT VALUES"]
            if columns:
                statements.append(f"EXPLAIN UPDATE {_quote(owner)} SET " +
                                  ",".join(f"{_quote(c)}={_quote(c)}" for c in columns))
        conn.set_authorizer(authorizer)
        try:
            for sql in statements:
                conn.execute(sql).fetchall()
        except sqlite3.Error:
            return True
        finally:
            conn.set_authorizer(lambda *_: sqlite3.SQLITE_OK)
    return hit


def _owned_data(conn, owned):
    result = {}
    for name, (kind, _, _) in sorted(owned.items()):
        if kind != "table":
            continue
        columns = list(conn.execute(f"PRAGMA table_xinfo({_quote(name)})"))
        primary = sorted((row for row in columns if row[5]), key=lambda row: row[5])
        order = ",".join(_quote(row[1]) for row in primary or columns)
        digest, count = hashlib.sha256(), 0
        for row in conn.execute(f"SELECT * FROM {_quote(name)} ORDER BY {order}"):
            digest.update(_hash([[type(v).__name__, v.hex() if isinstance(v, bytes) else v] for v in row]).encode())
            count += 1
        result[name] = {"count": count, "sha256": digest.hexdigest()}
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='sqlite_sequence'").fetchone():
        result["sqlite_sequence"] = sorted([tuple(row) for row in conn.execute("SELECT name,seq FROM sqlite_sequence")
                                             if row[0].lower() in {n.lower() for n in owned}])
    return result


def _base_preview(operation, mode):
    return dict(format=PREVIEW_FORMAT, version=1, operation=operation, mode=mode, status="blocked", code=None,
                state_sha256=None, approval_sha256=None, candidates=[], references={}, owned_objects=[],
                schema_status="unobserved", retained_bytes=0, recovery="inspect_and_preview_again",
                apply_effect="none", reference_status="unobserved")


def _seal(result):
    result["approval_sha256"] = _hash({k: v for k, v in result.items() if k != "approval_sha256"})
    return result


def _owned_inventory(owned):
    return [{"name": n, "type": k, "owner": o, "sql_sha256": _hash(sql)}
            for n, (k, o, sql) in sorted(owned.items())]


def _observe(paths, conn, directory, profile, profile_identity, operation, mode):
    result = _base_preview(operation, mode)
    store = _ObservedStore(paths, conn)
    owned = schema._owned(conn)
    files = directory.inventory()
    roots, refs = _profile_roots(profile)
    database_identity = _file_identity(paths.market_db_path)
    market_roots = []
    if database_identity != profile_identity:
        with store.connect(readonly=True) as observed:
            market_roots, market_refs = _profile_roots(observed)
        refs += market_refs
    result["schema_status"] = "canonical" if owned == schema._DDL else "mismatch" if owned else "absent"
    result["owned_objects"] = _owned_inventory(owned)
    result["references"] = {"research_citations": len(refs)}
    result["reference_status"] = "roots_observed_closure_unverified"
    result["retained_bytes"] = sum(item["size_bytes"] for item in files)
    unknown = any(n.lower() not in schema._DDL or
                  (kind, owner.lower()) != schema._DDL[n.lower()][:2] for n, (kind, owner, _) in owned.items())
    external = _dependencies(conn, owned)
    result["state_sha256"] = _hash({"database": database_identity,
        "root": [os.fstat(directory.root_fd).st_dev, os.fstat(directory.root_fd).st_ino],
        "children": {k: [os.fstat(fd).st_dev, os.fstat(fd).st_ino] for k, fd in directory.children.items()},
        "schema": owned, "data": _owned_data(conn, owned), "files": files,
        "profile": profile_identity, "roots": {"profile": roots, "market": market_roots},
        "citations": refs, "external": external})
    if unknown:
        result.update(code="sec_research_unknown_owned_objects", recovery="inspect_raw_backup",
                      apply_effect="raw_backup_only" if operation == "schema" else "none")
    elif external:
        result["code"] = "sec_research_external_dependencies"
    elif operation == "schema" and refs:
        result["code"] = "sec_research_reset_references_present"
    elif owned != schema._DDL and operation == "cleanup":
        result["code"] = "sec_research_schema_mismatch"
    else:
        if owned == schema._DDL:
            try:
                counts = _verify_database(store)
                closure = sec_reference_closure(store, citations=refs)
                reader = _ReferenceReader(store, CaptureStore(store, budget=None), retain_closure=True)
                for row in conn.execute("SELECT cik,receipt_id FROM sec_research_receipts"):
                    reader._receipt(row["cik"], row["receipt_id"])
            except (ValueError, KeyError, TypeError, sqlite3.Error):
                raise ValueError("sec_research_references_invalid") from None
            result["references"] = counts | {"research_citations": len(refs)}
            result["reference_status"] = "verified"
            referenced = set(closure["object_sha256s"])
            for name, (_, _, _) in owned.items():
                if name not in schema._TABLES:
                    continue
                for fk in conn.execute(f"PRAGMA foreign_key_list({_quote(name)})"):
                    if fk[2] == "sec_research_objects":
                        referenced.update(r[0] for r in conn.execute(
                            f"SELECT {_quote(fk[3])} FROM {_quote(name)} WHERE {_quote(fk[3])} IS NOT NULL"))
            registry = {row["object_key"]: dict(row) for row in conn.execute("SELECT * FROM sec_research_objects")}
            by_key = {item["key"]: item for item in files}
            for key, row in registry.items():
                _require(key in by_key and key == "objects/" + row["sha256"] and
                         row["sha256"] == by_key[key]["sha256"] and row["size_bytes"] == by_key[key]["size_bytes"],
                         "sec_research_references_invalid")
            if operation == "cleanup":
                result["candidates"] = [{**item, "kind": "registered" if item["key"] in registry else
                    "staging" if item["key"].startswith("staging/") else "unregistered"} for item in files
                    if item["key"] not in registry or registry[item["key"]]["sha256"] not in referenced]
                for key, size in conn.execute("SELECT object_key,size_bytes FROM sec_research_orphans ORDER BY object_key"):
                    _require(type(key) is str and
                             re.fullmatch(r"(?:objects/[0-9a-f]{64}|staging/[0-9a-f]{32})", key) is not None and
                             type(size) is int and size >= 0, "sec_research_references_invalid")
                    if key not in by_key:
                        result["candidates"].append({"key": key, "size_bytes": size, "kind": "absent_charge",
                                                     "sha256": None, "identity": None})
                result["candidates"].sort(key=lambda item: item["key"])
        result.update(status="ready", recovery="explicit_apply", apply_effect=mode or "cleanup")
    return _seal(result)


def _preview(paths, profile_connection, *, operation, mode=None):
    result = _base_preview(operation, mode)
    directory = None
    try:
        _require((operation == "cleanup" and mode is None) or (operation == "schema" and mode in {"reset", "uninstall"}))
        _profile_admission(profile_connection)
        _file_identity(paths.market_db_path)
        with research_operation(paths.capture_root), Store(paths).connect(readonly=True) as conn:
            conn.execute("BEGIN")
            directory = CaptureDirectory(paths.capture_root)
            with _profile_snapshot(profile_connection) as (profile, identity):
                return _observe(paths, conn, directory, profile, identity, operation, mode)
    except (ValueError, OSError, sqlite3.Error, TypeError, KeyError) as exc:
        result["code"] = _code(exc)
        return _seal(result)
    finally:
        if directory is not None:
            directory.close()


def preview_cleanup(paths, *, profile_connection) -> dict:
    return _preview(paths, profile_connection, operation="cleanup")


def validate_preview(preview, *, operation, approval_sha256):
    _require(type(preview) is dict and set(preview) == _PREVIEW_FIELDS)
    _require(preview["format"] == PREVIEW_FORMAT and type(preview["version"]) is int and preview["version"] == 1)
    _require(preview["operation"] == operation and
             ((operation == "cleanup" and preview["mode"] is None) or
              (operation == "schema" and preview["mode"] in {"reset", "uninstall"})))
    _require(preview["status"] in {"ready", "blocked"} and
             (preview["code"] is None or preview["code"] in _CODES | {"sec_research_admin_failed"}))
    _require(preview["schema_status"] in {"canonical", "mismatch", "absent", "unobserved"} and
             preview["recovery"] in {"inspect_and_preview_again", "explicit_apply", "inspect_raw_backup"})
    _require(preview["apply_effect"] in {"none", "cleanup", "reset", "uninstall", "raw_backup_only"} and
             preview["reference_status"] in {"unobserved", "roots_observed_closure_unverified", "verified"})
    if preview["apply_effect"] == "raw_backup_only":
        _require(operation == "schema" and preview["status"] == "blocked" and
                 preview["code"] == "sec_research_unknown_owned_objects" and
                 preview["schema_status"] == "mismatch" and preview["state_sha256"] is not None and
                 preview["recovery"] == "inspect_raw_backup" and
                 preview["reference_status"] == "roots_observed_closure_unverified")
    elif preview["status"] == "ready":
        _require(preview["code"] is None and preview["apply_effect"] == (preview["mode"] or "cleanup"))
    else:
        _require(preview["apply_effect"] == "none")
    _require(type(preview["retained_bytes"]) is int and preview["retained_bytes"] >= 0)
    _require(preview["state_sha256"] is None or
             (type(preview["state_sha256"]) is str and re.fullmatch("[0-9a-f]{64}", preview["state_sha256"]) is not None))
    counts = preview["references"]
    _require(type(counts) is dict and set(counts) <= {*_COUNTS, "research_citations"} and
             all(type(v) is int and v >= 0 for v in counts.values()))
    _require(type(preview["candidates"]) is list and type(preview["owned_objects"]) is list)
    for item in preview["candidates"]:
        _require(type(item) is dict and set(item) == {"key", "kind", "sha256", "size_bytes", "identity"})
        _require(type(item["key"]) is str and re.fullmatch(r"(?:objects/[0-9a-f]{64}|staging/[0-9a-f]{32})", item["key"]) is not None)
        _require(type(item["size_bytes"]) is int and item["size_bytes"] >= 0)
        if item["kind"] == "absent_charge":
            _require(item["identity"] is None and item["sha256"] is None)
            continue
        _require(item["kind"] in {"registered", "unregistered", "staging"} and
                 type(item["sha256"]) is str and re.fullmatch("[0-9a-f]{64}", item["sha256"]) is not None)
        _require(type(item["size_bytes"]) is int and item["size_bytes"] >= 0 and
                 type(item["identity"]) is list and len(item["identity"]) == 6 and
                 all(type(v) is int for v in item["identity"]) and
                 item["identity"][2:4] == [item["size_bytes"], 1])
    for item in preview["owned_objects"]:
        _require(type(item) is dict and set(item) == {"name", "type", "owner", "sql_sha256"} and
                 all(type(v) is str and v for v in item.values()))
        _require(item["type"] in {"table", "index", "trigger", "view"} and
                 re.fullmatch("[0-9a-f]{64}", item["sql_sha256"]) is not None)
    for field, key in (("candidates", "key"), ("owned_objects", "name")):
        keys = [item[key] for item in preview[field]]
        _require(keys == sorted(set(keys)))
    _require(type(approval_sha256) is str and re.fullmatch("[0-9a-f]{64}", approval_sha256) is not None)
    _require(approval_sha256 == preview["approval_sha256"] ==
             _hash({k: v for k, v in preview.items() if k != "approval_sha256"}))


def _output_path(paths, path):
    path = _path(path)
    _require(not path.is_relative_to(paths.capture_root) and path not in {
        paths.market_db_path, paths.market_db_path.with_name(paths.market_db_path.name + "-wal"),
        paths.market_db_path.with_name(paths.market_db_path.name + "-shm"),
        paths.market_db_path.with_name(paths.market_db_path.name + "-journal")}, "sec_research_admin_path_invalid")
    _new_destination(path)
    return path


def _receipt(preview):
    preview = preview if type(preview) is dict else {}
    operation = preview.get("operation") if preview.get("operation") in ("cleanup", "schema") else None
    mode = preview.get("mode") if preview.get("mode") in ("reset", "uninstall") else None
    approval = preview.get("approval_sha256")
    approval = approval if type(approval) is str and re.fullmatch("[0-9a-f]{64}", approval) else None
    return dict(format="arkscope-sec-research-receipt", version=1, operation=operation,
        mode=mode, approval_sha256=approval, status="blocked", code=None,
        phase="not_started", receipt_phase="not_started", selected=[], removed=[], remaining=[], blocked=[],
        resolved_charges=[], freed_bytes=0, retained_bytes=0, accounting="unchanged", backup=None,
        recovery="new_preview_and_approval", apply_effect="none", references={}, reference_status="unobserved")


def _finish_failure(result, audit, exc):
    result.update(status="blocked", code=_code(exc), blocked=list(result["remaining"]))
    if audit is not None:
        try:
            audit.write(result)
        except (OSError, ValueError):
            result["receipt_phase"] = audit.phase
    return result


def _recheck(preview, current):
    _require(current == preview, "sec_research_preview_stale")


def _delete_registered(conn, candidates):
    guard = "sec_research_objects_no_delete"
    conn.execute(f"DROP TRIGGER {guard}")
    for item in candidates:
        if item["kind"] == "registered":
            changed = conn.execute("DELETE FROM sec_research_objects WHERE object_key=? AND sha256=? AND size_bytes=?",
                                   (item["key"], item["sha256"], item["size_bytes"])).rowcount
            _require(changed == 1, "sec_research_preview_stale")
    conn.execute(schema._DDL[guard][2])
    schema.verify(conn)


@contextmanager
def _write_transaction(paths):
    with market_write_lock(), Store(paths).connect() as conn:
        conn.execute("PRAGMA synchronous=FULL")
        _require(conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1, "sec_research_references_invalid")
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise


def _write_point(conn, preview):
    # The exclusive SEC lease protects the expensive observation. Only metadata
    # and immediate FK enforcement belong at this short shared-market write point.
    owned = schema._owned(conn)
    _require(_owned_inventory(owned) == preview["owned_objects"], "sec_research_preview_stale")
    _require(not _dependencies(conn, owned), "sec_research_external_dependencies")


def apply_cleanup(paths, preview, *, approval_sha256, receipt_path, profile_connection) -> dict:
    result, audit, directory = _receipt(preview), None, None
    try:
        validate_preview(preview, operation="cleanup", approval_sha256=approval_sha256)
        _require(preview["status"] == "ready")
        receipt_path = _output_path(paths, receipt_path)
        _profile_admission(profile_connection)
        _file_identity(paths.market_db_path)
        with research_operation(paths.capture_root, exclusive=True):
            directory = CaptureDirectory(paths.capture_root)
            with Store(paths).connect(readonly=True) as conn, _profile_snapshot(profile_connection) as (profile, identity):
                conn.execute("BEGIN")
                current = _observe(paths, conn, directory, profile, identity, "cleanup", None)
                _recheck(preview, current)
            result.update(selected=[c["key"] for c in current["candidates"]],
                          remaining=[c["key"] for c in current["candidates"]],
                          retained_bytes=current["retained_bytes"], apply_effect=current["apply_effect"],
                          references=current["references"], reference_status=current["reference_status"])
            audit = OperationReceipt(receipt_path)
            prepared = dict(result, phase="prepared")
            audit.write(prepared)
            result = prepared
            with _write_transaction(paths) as conn:
                _write_point(conn, current)
                for item in current["candidates"]:
                    conn.execute("INSERT OR REPLACE INTO sec_research_orphans VALUES(?,?)",
                                 (item["key"], item["size_bytes"]))
                _delete_registered(conn, current["candidates"])
                conn.execute("DELETE FROM sec_research_reservations")
            result.update(phase="charged", accounting="orphans_charged")
            audit.write(result)
            for item in current["candidates"]:
                absent = item["kind"] == "absent_charge"
                if absent:
                    directory.confirm_absent(item["key"])
                else:
                    directory.remove_owned({k: v for k, v in item.items() if k != "kind"})
                    result["removed"].append(item["key"])
                    result["remaining"].remove(item["key"])
                    result["freed_bytes"] += item["size_bytes"]
                    result["retained_bytes"] -= item["size_bytes"]
                    result["phase"] = "files_removed"
                    audit.write(result)
                with _write_transaction(paths) as conn:
                    conn.execute("DELETE FROM sec_research_orphans WHERE object_key=?", (item["key"],))
                if absent:
                    result["resolved_charges"].append(item["key"])
                    result["remaining"].remove(item["key"])
                    result["phase"] = "charges_reconciled"
                    audit.write(result)
            result["accounting"] = "reconciled"
            completed = dict(result, status="ok", phase="complete", recovery="none")
            audit.write(completed)
            return completed
    except (ValueError, OSError, sqlite3.Error, TypeError, KeyError, KeyboardInterrupt) as exc:
        return _finish_failure(result, audit, exc)
    finally:
        if directory is not None:
            directory.close()
        if audit is not None:
            audit.close()
