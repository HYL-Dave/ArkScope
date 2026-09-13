"""Explicit offline SEC bundles: a whole market backup and SEC captures only."""

from contextlib import contextmanager
import ctypes
from dataclasses import asdict
import errno
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import sqlite3
import stat
import struct

from src.market_data_direct import backup_market_db
from . import schema
from .capture_lock import CaptureDirectory, _supported, research_operation
from .captures import CaptureStore, MAX_OBJECT_BYTES, METADATA_SPACE_MARGIN
from .citations import _json, validate_citation
from .document_store import DocumentStore, _attempt, _identity
from .documents import parse_document_directory, parse_filing_id
from .issuers import parse_ticker_map
from .paths import SecResearchPaths
from .references import _ReferenceReader, iter_research_sec_citations
from .store import Store


FORMAT = "arkscope-sec-research"
VERSION = 1
MANIFEST = "manifest.json"
CHUNK_BYTES = 1024 * 1024
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
_SQLITE_HEADER = struct.Struct(">16sHBB")
_renameat2 = getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None)
if _renameat2 is not None:
    _renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    _renameat2.restype = ctypes.c_int
_COUNTS = {
    "objects": "sec_research_objects", "snapshots": "sec_research_snapshots",
    "receipts": "sec_research_receipts", "issuer_maps": "sec_research_issuer_maps",
    "filing_observations": "sec_research_filings", "fact_observations": "sec_research_facts",
    "documents": "sec_research_documents", "document_directories": "sec_research_document_directories",
    "document_sources": "sec_research_document_sources", "document_attempts": "sec_research_document_attempts",
}


def _scope():
    return {"database": "whole-market-database", "captures": "sec-research-only",
            "excluded": ["independent-profile-store", "independent-sa-store", "other-capture-roots"]}


def _require(condition, code="sec_research_bundle_invalid"):
    if not condition:
        raise ValueError(code)


def _basename(value):
    _require(isinstance(value, str) and bool(value) and len(value.encode("utf-8")) <= 200
             and value not in {".", "..", MANIFEST, ".incomplete", ".manifest.pending"}
             and not any(c in '<>:"/\\|?*' or ord(c) < 32 or ord(c) == 127 for c in value)
             and not value.endswith((".", " ")) and not PureWindowsPath(value).is_reserved(),
             "sec_research_bundle_path_invalid")
    return value


def _path(value):
    path = Path(value).absolute()
    _require(".." not in path.parts and "\x00" not in str(path), "sec_research_bundle_path_invalid")
    _basename(path.name)
    return path


def _directory(path):
    _require(_supported(), "capture_platform_unsupported")
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def _current(path, fd):
    check = _directory(path)
    try:
        a, b = os.fstat(fd), os.fstat(check)
        _require((a.st_dev, a.st_ino) == (b.st_dev, b.st_ino), "sec_research_bundle_path_invalid")
    finally:
        os.close(check)


@contextmanager
def _file(path, *, create=False):
    parent = _directory(path.parent)
    fd = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL if create else os.O_RDONLY
        fd = os.open(path.name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=parent)
        _require(stat.S_ISREG(os.fstat(fd).st_mode), "sec_research_bundle_path_invalid")
        with os.fdopen(fd, "wb" if create else "rb", closefd=False) as handle:
            yield handle
            if create:
                handle.flush()
                os.fsync(fd)
        if create:
            os.fsync(parent)
    finally:
        if fd is not None:
            os.close(fd)
        os.close(parent)


@contextmanager
def _errors():
    try:
        yield
    except FileExistsError:
        raise ValueError("sec_research_bundle_destination_exists") from None
    except OSError as exc:
        code = ("storage_space_insufficient" if exc.errno == errno.ENOSPC else
                "sec_research_bundle_path_invalid" if exc.errno in {errno.ELOOP, errno.ENOTDIR, errno.ENOENT} else
                "sec_research_bundle_write_failed")
        raise ValueError(code) from None
    except sqlite3.Error:
        raise ValueError("sec_research_bundle_database_invalid") from None
    except (KeyError, TypeError, UnicodeError, RecursionError, OverflowError):
        raise ValueError("sec_research_bundle_invalid") from None


def _new_destination(path):
    parent = _directory(path.parent)
    try:
        try:
            os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return
        raise ValueError("sec_research_bundle_destination_exists")
    finally:
        os.close(parent)


@contextmanager
def _owned_destination(path):
    parent = _directory(path.parent)
    fd = None
    try:
        # mkdir, not exists()+rename, arbitrates competing destinations.
        os.mkdir(path.name, 0o700, dir_fd=parent)
        fd = os.open(path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        marker = os.open(".incomplete", os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
                         0o600, dir_fd=fd)
        os.close(marker)
        os.fsync(fd)
        os.fsync(parent)
        _current(path, fd)
        yield fd
    finally:
        if fd is not None:
            os.close(fd)
        os.close(parent)


def _digest(path):
    digest = hashlib.sha256()
    size = 0
    with _file(path) as handle:
        while chunk := handle.read(CHUNK_BYTES):
            size += len(chunk)
            digest.update(chunk)
    return {"sha256": digest.hexdigest(), "size_bytes": size}


def _copy_member(source, destination, expected):
    digest, size = hashlib.sha256(), 0
    with _file(source) as src, _file(destination, create=True) as dst:
        _require(os.fstat(src.fileno()).st_size == expected["size_bytes"], "sec_research_bundle_integrity_failed")
        while chunk := src.read(CHUNK_BYTES):
            size += len(chunk)
            _require(size <= expected["size_bytes"], "sec_research_bundle_integrity_failed")
            dst.write(chunk)
            digest.update(chunk)
        _require(size == expected["size_bytes"] and digest.hexdigest() == expected["sha256"],
                 "sec_research_bundle_integrity_failed")


def _inventory(store):
    with store.connect(readonly=True) as conn:
        schema.verify(conn)
        result = [dict(row) for row in conn.execute(
            "SELECT object_key AS key,sha256,size_bytes FROM sec_research_objects ORDER BY object_key")]
    for item in result:
        _object_shape(item)
    return result


def _hash_shape(item):
    _require(type(item["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) is not None
             and type(item["size_bytes"]) is int and item["size_bytes"] >= 0)


def _object_shape(item):
    _require(type(item) is dict and set(item) == {"key", "sha256", "size_bytes"})
    _hash_shape(item)
    _require(item["key"] == "objects/" + item["sha256"] and item["size_bytes"] <= MAX_OBJECT_BYTES)


def _fingerprint():
    return hashlib.sha256(json.dumps(schema._DDL, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _verify_database(store):
    """Verify every registered graph, not only current/latest or SQL FK edges."""
    captures = CaptureStore(store, budget=None)
    reader = _ReferenceReader(store, captures, retain_closure=True)
    with store.connect(readonly=True) as conn:
        _require([row[0] for row in conn.execute("PRAGMA integrity_check")] == ["ok"])
        _require(conn.execute("PRAGMA foreign_key_check").fetchone() is None)
        counts = {key: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for key, table in _COUNTS.items()}
        for row in conn.execute("SELECT cik,snapshot_id FROM sec_research_snapshots ORDER BY snapshot_id"):
            reader._snapshot(row["cik"], row["snapshot_id"])
        for row in conn.execute("SELECT * FROM sec_research_receipts ORDER BY receipt_id"):
            for key in ("completed", "pending", "gaps", "source_snapshots"):
                _json(row[key])
            receipt = store.receipt(row["cik"], row["receipt_id"])
            for locator, binding in receipt["source_snapshots"].items():
                store.bound_snapshot(row["cik"], locator, binding)
        for row in conn.execute("SELECT * FROM sec_research_issuer_maps ORDER BY observation_id"):
            symbols, gaps = _json(row["symbols"]), _json(row["gaps"])
            _require(type(symbols) is dict and type(gaps) is list)
            if row["status"] == "ok":
                parsed = parse_ticker_map(captures.read(row["object_sha256"]))
                _require({key: list(values) for key, values in parsed.items()} == symbols)
        for row in conn.execute("SELECT * FROM sec_research_document_directories ORDER BY directory_id"):
            metadata = _json(row["metadata"])
            _require(_identity("secdir_", metadata) == row["directory_id"])
            _require(all(metadata[key] == row[key] for key in row.keys() if key not in {"directory_id", "metadata"}))
            parsed = parse_document_directory(captures.read(row["object_sha256"]), filing_id=row["filing_id"])
            _require(metadata["entries"] == [asdict(entry) for entry in parsed.entries] and metadata["source_url"] == parsed.url)
        for row in conn.execute("SELECT * FROM sec_research_documents ORDER BY capture_id"):
            metadata = _json(row["metadata"])
            # A citation-sized probe invokes the verifier for the whole capture
            # and all catalog/receipt sources, including large UTF-8 documents.
            first_character = captures.read(metadata["text_sha256"]).decode("utf-8")[:1]
            ref = {"kind": "document", "capture_id": row["capture_id"],
                   "accession": parse_filing_id(row["filing_id"])[1],
                   **{key: metadata[key] for key in ("filing_id", "document_id", "source_url",
                       "original_sha256", "text_sha256", "extraction_version")},
                   "start_byte": 0, "end_byte": len(first_character.encode("utf-8")),
                   "match_start_byte": None, "match_end_byte": None}
            reader.read(validate_citation(ref))
        for row in conn.execute("SELECT provenance FROM sec_research_document_sources"):
            _json(row["provenance"])
        for row in conn.execute("SELECT * FROM sec_research_document_attempts"):
            _json(row["details"])
            attempt = _attempt(row)
            if attempt["capture_id"] is not None:
                capture = DocumentStore(store).capture(attempt["capture_id"])
                _require(capture["filing_id"] == attempt["filing_id"]
                         and capture["document_id"] == attempt["resolved_document_id"])
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        counts["research_citations"] = 0
        if tables & {"research_messages", "research_run_events"}:
            for ref in iter_research_sec_citations(conn):
                reader.read(ref)
                counts["research_citations"] += 1
    return counts


def _space(destination, database_bytes, object_bytes, free_bytes):
    available = (free_bytes or (lambda path: shutil.disk_usage(path).free))(destination)
    # Full DB and captures plus another full staging allocation, outside quota.
    required = 2 * (database_bytes + object_bytes) + METADATA_SPACE_MARGIN
    _require(type(available) is int and available >= required, "storage_space_insufficient")


def _members(path):
    members = set()

    def walk(fd, prefix):
        for name in os.listdir(fd):
            key = prefix + name
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            _require(stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode), "sec_research_bundle_path_invalid")
            members.add(key)
            if stat.S_ISDIR(info.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    walk(child, key + "/")
                finally:
                    os.close(child)

    fd = _directory(path)
    try:
        walk(fd, "")
    finally:
        os.close(fd)
    return members


def _expected(manifest):
    name = manifest["database"]["name"]
    root = name + ".sec-research"
    return {name, root, root + "/objects", root + "/staging", MANIFEST,
            *(root + "/" + item["key"] for item in manifest["objects"])}


def _manifest_shape(value):
    _require(type(value) is dict and set(value) == {"format", "version", "scope", "database", "schema_sha256",
                                                  "objects", "normalization", "references"})
    _require(value["format"] == FORMAT and type(value["version"]) is int and value["version"] == VERSION)
    _require(value["scope"] == _scope() and value["schema_sha256"] == _fingerprint())
    db = value["database"]
    _require(type(db) is dict and set(db) == {"name", "sha256", "size_bytes"})
    _basename(db["name"])
    _hash_shape(db)
    _require(type(value["objects"]) is list)
    for item in value["objects"]:
        _object_shape(item)
    keys = [item["key"] for item in value["objects"]]
    _require(keys == sorted(set(keys)))
    norm = value["normalization"]
    _require(type(norm) is dict and set(norm) == {"policy", "database_bytes", "reservations_cleared", "orphans_cleared"})
    _require(norm["policy"] == "clear-transient-accounting-v1" and norm["database_bytes"] == "normalized-backup-not-source")
    _require(all(type(norm[key]) is int and norm[key] >= 0 for key in ("reservations_cleared", "orphans_cleared")))
    counts = value["references"]
    _require(type(counts) is dict and set(counts) == {*_COUNTS, "research_citations"}
             and all(type(v) is int and v >= 0 for v in counts.values()))


def _verify_bundle(path, manifest, *, incomplete=False):
    _manifest_shape(manifest)
    expected = _expected(manifest)
    if incomplete:
        expected = expected - {MANIFEST} | {".incomplete"}
    _require(_members(path) == expected, "sec_research_bundle_members_invalid")
    db = manifest["database"]
    # SQLite's fixed header must advertise rollback mode before any connection
    # can create WAL/SHM files in a supposedly normalized, read-only bundle.
    with _file(path / db["name"]) as handle:
        header = handle.read(_SQLITE_HEADER.size)
    _require(len(header) == _SQLITE_HEADER.size)
    magic, _, write_version, read_version = _SQLITE_HEADER.unpack(header)
    _require(magic == b"SQLite format 3\x00" and write_version == read_version == 1,
             "sec_research_bundle_database_invalid")
    _require(_digest(path / db["name"]) == {k: db[k] for k in ("sha256", "size_bytes")},
             "sec_research_bundle_integrity_failed")
    store = Store(SecResearchPaths.from_market_db(path / db["name"]))
    for item in manifest["objects"]:
        _require(_digest(store.paths.capture_root / item["key"]) == {k: item[k] for k in ("sha256", "size_bytes")},
                 "sec_research_bundle_integrity_failed")
    _require(_inventory(store) == manifest["objects"], "sec_research_bundle_inventory_invalid")
    with store.connect(readonly=True) as conn:
        _require(conn.execute("SELECT COUNT(*) FROM sec_research_reservations").fetchone()[0] == 0
                 and conn.execute("SELECT COUNT(*) FROM sec_research_orphans").fetchone()[0] == 0)
        _require(conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete")
    _require(_verify_database(store) == manifest["references"], "sec_research_bundle_references_invalid")


def _rename_new(fd, source, destination):
    _require(_renameat2 is not None, "sec_research_bundle_publication_unsupported")
    if _renameat2(fd, os.fsencode(source), fd, os.fsencode(destination), 1) != 0:
        error = ctypes.get_errno()
        _require(error not in {errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP},
                 "sec_research_bundle_publication_unsupported")
        raise OSError(error, "bundle publication failed")


def _publish(path, fd, manifest):
    raw = json.dumps(manifest, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    _require(len(raw) <= MAX_MANIFEST_BYTES, "sec_research_bundle_manifest_too_large")
    with _file(path / ".manifest.pending", create=True) as handle:
        handle.write(raw)
    _current(path, fd)
    linked = False
    try:
        os.unlink(".incomplete", dir_fd=fd)
        os.fsync(fd)
        _rename_new(fd, ".manifest.pending", MANIFEST)
        linked = True
        os.fsync(fd)
    except BaseException:
        if linked:
            os.unlink(MANIFEST, dir_fd=fd)
        try:
            marker = os.open(".incomplete", os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600, dir_fd=fd)
            os.close(marker)
        except OSError:
            pass
        raise


def export_bundle(paths, destination: Path, *, free_bytes=None) -> dict:
    """Create a new verified bundle. Never normalize or enumerate the live DB after backup."""
    with _errors():
        destination = _path(destination)
        _require(_renameat2 is not None, "sec_research_bundle_publication_unsupported")
        _new_destination(destination)
        source = _path(paths.market_db_path)
        with _file(source):
            pass
        with research_operation(paths.capture_root):
            live = Store(paths)
            with live.connect(readonly=True) as conn:
                schema.verify(conn)
                size = conn.execute("PRAGMA page_count").fetchone()[0] * conn.execute("PRAGMA page_size").fetchone()[0]
                objects_size = conn.execute("SELECT COALESCE(SUM(size_bytes),0) FROM sec_research_objects").fetchone()[0]
            _space(destination.parent, size, objects_size, free_bytes)
            with _owned_destination(destination) as fd:
                staged = Store(SecResearchPaths.from_market_db(destination / "market_data.db"))
                _require(backup_market_db(str(source), str(staged.paths.market_db_path), overwrite=False) is not None)
                _current(destination, fd)
                inventory = _inventory(staged)
                with staged.connect() as conn:
                    normalization = {"policy": "clear-transient-accounting-v1", "database_bytes": "normalized-backup-not-source",
                        "reservations_cleared": conn.execute("SELECT COUNT(*) FROM sec_research_reservations").fetchone()[0],
                        "orphans_cleared": conn.execute("SELECT COUNT(*) FROM sec_research_orphans").fetchone()[0]}
                    conn.execute("PRAGMA journal_mode=DELETE")
                    conn.execute("BEGIN IMMEDIATE")
                    conn.execute("DELETE FROM sec_research_reservations")
                    conn.execute("DELETE FROM sec_research_orphans")
                    conn.commit()
                _space(destination, staged.paths.market_db_path.stat().st_size,
                       sum(item["size_bytes"] for item in inventory), free_bytes)
                CaptureDirectory(staged.paths.capture_root, create=True).close()
                for item in inventory:
                    _copy_member(paths.capture_root / item["key"], staged.paths.capture_root / item["key"], item)
                manifest = {"format": FORMAT, "version": VERSION, "scope": _scope(),
                    "database": {"name": "market_data.db", **_digest(staged.paths.market_db_path)},
                    "schema_sha256": _fingerprint(), "objects": inventory, "normalization": normalization,
                    "references": _verify_database(staged)}
                _verify_bundle(destination, manifest, incomplete=True)
                with _file(staged.paths.market_db_path) as handle:
                    os.fsync(handle.fileno())
                _publish(destination, fd, manifest)
                return manifest


def restore_bundle(bundle: Path, destination: Path, *, database_name="market_data.db", free_bytes=None) -> dict:
    """Restore into a new enclosing directory, rebinding capture paths to the DB name."""
    with _errors():
        bundle, destination = _path(bundle), _path(destination)
        _basename(database_name)
        _require(_renameat2 is not None, "sec_research_bundle_publication_unsupported")
        _new_destination(destination)
        with _file(bundle / MANIFEST) as handle:
            _require(os.fstat(handle.fileno()).st_size <= MAX_MANIFEST_BYTES, "sec_research_bundle_manifest_too_large")
            manifest = _json(handle.read(MAX_MANIFEST_BYTES + 1).decode("utf-8"))
        _manifest_shape(manifest)
        source = Store(SecResearchPaths.from_market_db(bundle / manifest["database"]["name"]))
        with research_operation(source.paths.capture_root):
            _verify_bundle(bundle, manifest)
            _space(destination.parent, manifest["database"]["size_bytes"],
                   sum(item["size_bytes"] for item in manifest["objects"]), free_bytes)
            with _owned_destination(destination) as fd:
                restored = Store(SecResearchPaths.from_market_db(destination / database_name))
                _copy_member(source.paths.market_db_path, restored.paths.market_db_path, manifest["database"])
                CaptureDirectory(restored.paths.capture_root, create=True).close()
                for item in manifest["objects"]:
                    _copy_member(source.paths.capture_root / item["key"], restored.paths.capture_root / item["key"], item)
                result = {**manifest, "database": {**manifest["database"], "name": database_name}}
                _verify_bundle(destination, result, incomplete=True)
                _current(destination, fd)
                _publish(destination, fd, result)
                return result
