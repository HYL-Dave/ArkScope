"""Stdlib-only verifier, also copied into each immutable runtime package."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import stat
import sys


class RuntimeAdmissionError(RuntimeError):
    """Fixed public failure code; never includes config or environment contents."""


def _require(condition, code="sqlite_runtime_manifest_invalid"):
    if not condition:
        raise RuntimeAdmissionError(code)


def sha256(path: Path) -> str:
    with path.open("rb") as source:
        digest = hashlib.sha256()
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
        return digest.hexdigest()


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _keys(value, names):
    _require(isinstance(value, dict) and set(value) == set(names))


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result)
        result[key] = value
    return result


def _regular(path, *, maximum=32 * 1024 * 1024):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as source:
        info = os.fstat(source.fileno())
        _require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                 and info.st_uid == os.getuid() and not info.st_mode & 0o022
                 and info.st_size <= maximum, "sqlite_runtime_path_unsafe")
        body = source.read(maximum + 1)
        _require(len(body) == info.st_size, "sqlite_runtime_artifact_changed")
        return body


def selector_text(python: str, digest: str, files: dict[str, str]) -> str:
    return ("#!/bin/sh\nset -eu\n"
            'SELF=$(readlink -f -- "$0")\n'
            'ROOT=$(dirname -- "$SELF")\n'
            'fail() { echo sqlite_runtime_artifact_changed >&2; exit 78; }\n'
            'check() {\n'
            '  [ -f "$ROOT/$1" ] && [ ! -L "$ROOT/$1" ] || fail\n'
            '  SIZE=$(/usr/bin/stat -c%s -- "$ROOT/$1" 2>/dev/null) || fail\n'
            '  [ "$SIZE" -le 524288 ] || fail\n'
            '  SUM=$(/usr/bin/timeout -k 1 5 /usr/bin/sha256sum -- "$ROOT/$1" 2>/dev/null) || fail\n'
            '  [ "${SUM%% *}" = "$2" ] || fail\n'
            '}\n'
            f'check manifest.json {shlex.quote(digest)}\n'
            f'check contract.py {shlex.quote(files["contract.py"])}\n'
            f'check launch.py {shlex.quote(files["launch.py"])}\n'
            f'exec {shlex.quote(python)} -I -S -B "$ROOT/launch.py" '
            f'{shlex.quote(digest)} "$@"\n')


def _validate_manifest(data):
    _keys(data, ("format", "platform", "engine", "python", "source", "files"))
    _require(type(data["format"]) is int and data["format"] == 1)
    _require(data["platform"] == "linux-" + platform.machine() and sys.platform == "linux",
             "sqlite_runtime_platform_unsupported")
    engine = data["engine"]
    _keys(engine, ("version", "source_id", "compile_options"))
    _require(isinstance(engine["version"], str)
             and re.fullmatch(r"3\.[0-9]{1,3}\.[0-9]{1,3}", engine["version"]) is not None)
    _require(isinstance(engine["source_id"], str) and re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} [0-9a-f]{64}",
        engine["source_id"]) is not None)
    options = engine["compile_options"]
    _require(isinstance(options, list) and options and len(options) <= 256
             and all(isinstance(x, str) and re.fullmatch(r"[A-Z0-9_]+(?:=[A-Za-z0-9_,.+-]+)?", x)
                     for x in options))
    _require(options == sorted(set(options)))
    interpreter = data["python"]
    _keys(interpreter, ("path", "sha256", "extension_path", "extension_sha256"))
    for key in ("path", "extension_path"):
        value = interpreter[key]
        _require(isinstance(value, str) and Path(value).is_absolute()
                 and not any(ord(c) < 32 or ord(c) == 127 for c in value))
    _require(_digest(interpreter["sha256"]) and _digest(interpreter["extension_sha256"]))
    _keys(data["source"], ("archive_sha3", "amalgamation_sha3"))
    _require(all(_digest(x) for x in data["source"].values()))
    library = "lib/libsqlite3.so." + engine["version"]
    _keys(data["files"], ("contract.py", "launch.py", library))
    _require(all(_digest(x) for x in data["files"].values()))


def verify_package(root: Path, expected_sha256: str) -> dict:
    """Validate fixed inventory and bytes without importing SQLite or opening a DB."""
    try:
        _require(_digest(expected_sha256))
        _require(root.is_absolute() and root.resolve(strict=True) == root
                 and not any(ord(c) < 32 or ord(c) == 127 or c == ":" for c in str(root)),
                 "sqlite_runtime_path_unsafe")
        for directory in (root, root / "lib"):
            info = directory.lstat()
            _require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
                     and not info.st_mode & 0o022, "sqlite_runtime_path_unsafe")
        body = _regular(root / "manifest.json", maximum=512 * 1024)
        _require(hashlib.sha256(body).hexdigest() == expected_sha256,
                 "sqlite_runtime_manifest_changed")
        data = json.loads(body, object_pairs_hook=_pairs)
        _validate_manifest(data)
        version = data["engine"]["version"]
        _require({x.name for x in root.iterdir()} ==
                 {"manifest.json", "python", "contract.py", "launch.py", "lib"},
                 "sqlite_runtime_inventory_changed")
        _require({x.name for x in (root / "lib").iterdir()} ==
                 {"libsqlite3.so." + version, "libsqlite3.so.0"},
                 "sqlite_runtime_inventory_changed")
        link = root / "lib/libsqlite3.so.0"
        _require(link.is_symlink() and os.readlink(link) == "libsqlite3.so." + version,
                 "sqlite_runtime_path_unsafe")
        for name, digest in data["files"].items():
            _require(hashlib.sha256(_regular(root / name)).hexdigest() == digest,
                     "sqlite_runtime_artifact_changed")
        _require(_regular(root / "python") == selector_text(data["python"]["path"], expected_sha256, data["files"]).encode(),
                 "sqlite_runtime_artifact_changed")
        _require(os.access(root / "python", os.X_OK), "sqlite_runtime_path_unsafe")
        for name, digest_key in (("path", "sha256"), ("extension_path", "extension_sha256")):
            target = Path(data["python"][name]).resolve(strict=True)
            info = target.stat()
            _require(stat.S_ISREG(info.st_mode) and info.st_uid in {0, os.getuid()}
                     and not info.st_mode & 0o022, "sqlite_runtime_interpreter_changed")
            _require(sha256(target) == data["python"][digest_key], "sqlite_runtime_interpreter_changed")
        return data
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        raise RuntimeAdmissionError("sqlite_runtime_manifest_invalid") from None


def loaded_library() -> Path:
    """Resolve the function actually bound through Python's SQLite extension."""
    import _sqlite3

    class DlInfo(ctypes.Structure):
        _fields_ = [("filename", ctypes.c_char_p), ("base", ctypes.c_void_p),
                    ("symbol", ctypes.c_char_p), ("address", ctypes.c_void_p)]

    extension = ctypes.CDLL(_sqlite3.__file__)
    address = ctypes.cast(extension.sqlite3_libversion, ctypes.c_void_p).value
    dladdr = ctypes.CDLL(None).dladdr
    dladdr.argtypes = (ctypes.c_void_p, ctypes.POINTER(DlInfo))
    dladdr.restype = ctypes.c_int
    info = DlInfo()
    _require(dladdr(address, ctypes.byref(info)) and info.filename,
             "sqlite_runtime_engine_mismatch")
    path = Path(os.fsdecode(info.filename)).resolve(strict=True)
    target = path.stat()
    with open("/proc/self/maps", encoding="utf-8") as mappings:
        for line in mappings:
            fields = line.split(None, 5)
            lower, upper = (int(x, 16) for x in fields[0].split("-"))
            if lower <= address < upper:
                major, minor = (int(x, 16) for x in fields[3].split(":"))
                _require((target.st_dev, target.st_ino) == (os.makedev(major, minor), int(fields[4])),
                         "sqlite_runtime_engine_mismatch")
                return path
    raise RuntimeAdmissionError("sqlite_runtime_engine_mismatch")


def engine_identity() -> dict:
    import sqlite3
    connection = sqlite3.connect(":memory:")
    try:
        version, source = connection.execute("SELECT sqlite_version(), sqlite_source_id()").fetchone()
        options = sorted(row[0] for row in connection.execute("PRAGMA compile_options"))
    finally:
        connection.close()
    return {"version": version, "source_id": source, "compile_options": options}


def verify_runtime(root: Path, expected_sha256: str) -> dict:
    _require(not any(os.environ.get(name) for name in ("LD_PRELOAD", "LD_AUDIT")),
             "sqlite_runtime_loader_conflict")
    data = verify_package(root, expected_sha256)
    try:
        import _sqlite3
        import sqlite3

        _require(sys.executable == data["python"]["path"]
                 and str(Path(_sqlite3.__file__).resolve()) == data["python"]["extension_path"]
                 and engine_identity() == data["engine"], "sqlite_runtime_engine_mismatch")
        library = root / ("lib/libsqlite3.so." + data["engine"]["version"])
        _require(loaded_library() == library, "sqlite_runtime_engine_mismatch")
        options = set(data["engine"]["compile_options"])
        _require({"ENABLE_FTS5", "THREADSAFE=1", "MAX_VARIABLE_NUMBER=250000"} <= options,
                 "sqlite_runtime_features_missing")
        connection = sqlite3.connect(":memory:")
        try:
            _require(connection.execute("SELECT json_extract('{\"x\": 7}', '$.x')").fetchone() == (7,),
                     "sqlite_runtime_features_missing")
            connection.execute("CREATE VIRTUAL TABLE probe USING fts5(value, tokenize='porter unicode61')")
            connection.execute("SELECT ?250000", (None,) * 250000).fetchone()
            connection.execute("CREATE TABLE grammar_probe(value)")
            connection.execute("INSERT INTO grammar_probe VALUES (1), (2)")
            connection.execute("UPDATE grammar_probe SET value=3 ORDER BY value LIMIT 1")
            connection.execute("DELETE FROM grammar_probe ORDER BY value LIMIT 1")
            _require(connection.execute("SELECT value FROM grammar_probe").fetchall() == [(3,)],
                     "sqlite_runtime_features_missing")
        finally:
            connection.close()
        return {"status": "verified", "manifest_sha256": expected_sha256,
                "version": data["engine"]["version"], "source_id": data["engine"]["source_id"],
                "library": str(library)}
    except (OSError, ValueError, AttributeError, sqlite3.Error):
        raise RuntimeAdmissionError("sqlite_runtime_engine_mismatch") from None


def require_selected_runtime() -> dict | None:
    names = ("ARKSCOPE_SQLITE_PACKAGE", "ARKSCOPE_SQLITE_MANIFEST_SHA256")
    if all(name not in os.environ for name in names):
        return None
    root, digest = (os.environ.get(name, "") for name in names)
    _require(root and Path(root).is_absolute() and _digest(digest), "sqlite_runtime_selection_invalid")
    return verify_runtime(Path(root), digest)


if __name__ == "__main__":
    try:
        _require(len(sys.argv) == 4 and sys.argv[1] == "--probe", "sqlite_runtime_selection_invalid")
        print(json.dumps(verify_runtime(Path(sys.argv[2]), sys.argv[3]), sort_keys=True))
    except RuntimeAdmissionError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(78)
