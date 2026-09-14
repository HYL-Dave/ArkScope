"""The package manifest is closed data, never a filesystem command language."""

import hashlib
import json
import os
from pathlib import Path
import sys

import pytest


def contract():
    from src.sqlite_runtime import contract as module
    return module


def _sha(body):
    return hashlib.sha256(body).hexdigest()


@pytest.fixture
def package(tmp_path):
    root = tmp_path / "generation"
    root.mkdir(mode=0o700)
    (root / "lib").mkdir(mode=0o700)
    files = {
        "contract.py": b"contract", "launch.py": b"launch",
        "lib/libsqlite3.so.3.53.4": b"library",
    }
    for name, body in files.items():
        (root / name).write_bytes(body)
        (root / name).chmod(0o600)
    (root / "lib/libsqlite3.so.0").symlink_to("libsqlite3.so.3.53.4")
    import _sqlite3
    data = {
        "format": 1, "platform": "linux-x86_64",
        "engine": {"version": "3.53.4", "source_id": "2026-07-24 19:02:57 " + "a" * 64,
                   "compile_options": ["ENABLE_FTS5", "MAX_VARIABLE_NUMBER=250000", "THREADSAFE=1"]},
        "python": {"path": sys.executable, "sha256": _sha(Path(sys.executable).read_bytes()),
                   "extension_path": _sqlite3.__file__,
                   "extension_sha256": _sha(Path(_sqlite3.__file__).read_bytes())},
        "source": {"archive_sha3": "b" * 64, "amalgamation_sha3": "c" * 64},
        "files": {name: _sha(body) for name, body in files.items()},
    }
    return root, data


def seal(root, data):
    body = json.dumps(data, sort_keys=True).encode()
    digest = _sha(body)
    (root / "manifest.json").write_bytes(body)
    (root / "manifest.json").chmod(0o600)
    (root / "python").write_text(contract().selector_text(data["python"]["path"], digest, data["files"]))
    (root / "python").chmod(0o700)
    return digest


def test_exact_package_inventory_is_accepted(package):
    root, data = package
    digest = seal(root, data)
    assert contract().verify_package(root, digest) == data


@pytest.mark.parametrize("kind", ["extra_field", "wrong_format", "boolean_format", "bad_version",
                                 "bad_source", "bad_sha", "relative_python", "extra_python_field",
                                 "duplicate_options", "unsorted_options", "traversal", "absolute_payload"])
def test_manifest_rejects_invalid_shapes(package, kind):
    root, data = package
    if kind == "extra_field":
        data["extra"] = True
    elif kind == "wrong_format":
        data["format"] = 2
    elif kind == "boolean_format":
        data["format"] = True
    elif kind == "bad_version":
        data["engine"]["version"] = "../../other"
    elif kind == "bad_source":
        data["engine"]["source_id"] = "latest"
    elif kind == "bad_sha":
        data["files"]["launch.py"] = "A" * 64
    elif kind == "relative_python":
        data["python"]["path"] = "python"
    elif kind == "extra_python_field":
        data["python"]["fallback"] = "/usr/bin/python"
    elif kind == "duplicate_options":
        data["engine"]["compile_options"] *= 2
    elif kind == "unsorted_options":
        data["engine"]["compile_options"].reverse()
    else:
        data["files"]["../escape" if kind == "traversal" else "/tmp/escape"] = "a" * 64
    digest = seal(root, data)
    with pytest.raises(contract().RuntimeAdmissionError, match="sqlite_runtime_manifest_invalid"):
        contract().verify_package(root, digest)


@pytest.mark.parametrize("kind", ["extra_library", "extra_root", "changed_library", "bad_soname",
                                 "hardlink", "file_symlink", "root_symlink", "writable_dir",
                                 "writable_file", "changed_launcher", "bad_digest", "duplicate_json"])
def test_actual_filesystem_is_revalidated(package, tmp_path, kind):
    root, data = package
    digest = seal(root, data)
    if kind == "extra_library":
        (root / "lib/libc.so.6").write_bytes(b"not SQLite")
    elif kind == "extra_root":
        (root / "unowned").write_bytes(b"keep me")
    elif kind == "changed_library":
        (root / "lib/libsqlite3.so.3.53.4").write_bytes(b"changed")
    elif kind == "bad_soname":
        (root / "lib/libsqlite3.so.0").unlink()
        (root / "lib/libsqlite3.so.0").symlink_to("../../outside")
    elif kind == "hardlink":
        os.link(root / "launch.py", tmp_path / "outside")
    elif kind == "file_symlink":
        (root / "launch.py").rename(tmp_path / "outside")
        (root / "launch.py").symlink_to(tmp_path / "outside")
    elif kind == "root_symlink":
        (tmp_path / "alias").symlink_to(root)
        root = tmp_path / "alias"
    elif kind == "writable_dir":
        (root / "lib").chmod(0o777)
    elif kind == "writable_file":
        (root / "launch.py").chmod(0o666)
    elif kind == "changed_launcher":
        (root / "python").write_text("#!/bin/sh\nexit 0\n")
    elif kind == "bad_digest":
        digest = "f" * 64
    else:
        body = (root / "manifest.json").read_bytes()
        body = b'{"format": 1, ' + body[1:]
        (root / "manifest.json").write_bytes(body)
        digest = _sha(body)
    with pytest.raises(contract().RuntimeAdmissionError):
        contract().verify_package(root, digest)


def test_no_selection_is_explicitly_unmanaged(monkeypatch):
    monkeypatch.delenv("ARKSCOPE_SQLITE_PACKAGE", raising=False)
    monkeypatch.delenv("ARKSCOPE_SQLITE_MANIFEST_SHA256", raising=False)
    assert contract().require_selected_runtime() is None


@pytest.mark.parametrize("values", [{"ARKSCOPE_SQLITE_PACKAGE": "/missing"},
                                    {"ARKSCOPE_SQLITE_MANIFEST_SHA256": "a" * 64},
                                    {"ARKSCOPE_SQLITE_PACKAGE": "", "ARKSCOPE_SQLITE_MANIFEST_SHA256": ""}])
def test_partial_or_empty_selection_is_not_unmanaged(monkeypatch, values):
    for name in ("ARKSCOPE_SQLITE_PACKAGE", "ARKSCOPE_SQLITE_MANIFEST_SHA256"):
        monkeypatch.delenv(name, raising=False)
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(contract().RuntimeAdmissionError, match="sqlite_runtime_selection_invalid"):
        contract().require_selected_runtime()


def test_loaded_engine_is_not_inferred_from_manifest(package):
    root, data = package
    digest = seal(root, data)
    with pytest.raises(contract().RuntimeAdmissionError, match="sqlite_runtime_engine_mismatch"):
        contract().verify_runtime(root, digest)
