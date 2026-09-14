"""Offline, exclusive preparation of one reviewed Linux SQLite generation."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import subprocess
import sys
import tempfile
import stat
import zipfile

from .contract import RuntimeAdmissionError, selector_text, sha256, verify_package


VERSION = "3.53.4"
SOURCE_ID = "2026-07-24 19:02:57 bf7c7f30031888f4e796e429ab3978879485813aaca6f641c7b33e4e09459bcc"
ARCHIVE_SHA3 = "b834d474b9b393d85a9e3ee4cc11f1329e007e9376a424ee740796f5c4bda3a8"
ARCHIVE_ROOT = "sqlite-src-3530400"
DEFINES = (
    "SQLITE_THREADSAFE=1", "SQLITE_MAX_VARIABLE_NUMBER=250000", "SQLITE_SECURE_DELETE",
    "SQLITE_LIKE_DOESNT_MATCH_BLOBS", "SQLITE_USE_URI", "SQLITE_OMIT_LOOKASIDE",
    "SQLITE_DEFAULT_AUTOVACUUM=1", "SQLITE_DEFAULT_RECURSIVE_TRIGGERS=1",
    "SQLITE_MAX_FUNCTION_ARG=127", "SQLITE_MAX_MMAP_SIZE=0x7fff0000",
    "SQLITE_MAX_PAGE_COUNT=1073741823", "SQLITE_ENABLE_COLUMN_METADATA",
    "SQLITE_MAX_DEFAULT_PAGE_SIZE=32768", "SQLITE_MAX_SCHEMA_RETRY=25",
    "SQLITE_ENABLE_DBSTAT_VTAB", "SQLITE_ENABLE_FTS3", "SQLITE_ENABLE_FTS3_PARENTHESIS",
    "SQLITE_ENABLE_FTS3_TOKENIZER", "SQLITE_ENABLE_FTS4", "SQLITE_ENABLE_FTS5",
    "SQLITE_ENABLE_MATH_FUNCTIONS", "SQLITE_ENABLE_PREUPDATE_HOOK", "SQLITE_ENABLE_RTREE",
    "SQLITE_ENABLE_SESSION", "SQLITE_ENABLE_STMTVTAB", "SQLITE_ENABLE_UNLOCK_NOTIFY",
    "SQLITE_ENABLE_UPDATE_DELETE_LIMIT", "SQLITE_SOUNDEX", "HAVE_ISNAN",
)


def _source(archive):
    try:
        if archive.stat().st_size > 32 * 1024 * 1024:
            raise RuntimeAdmissionError("sqlite_runtime_source_mismatch")
        body = archive.read_bytes()
        if hashlib.sha3_256(body).hexdigest() != ARCHIVE_SHA3:
            raise RuntimeAdmissionError("sqlite_runtime_source_mismatch")
        with zipfile.ZipFile(io.BytesIO(body)) as source:
            members = source.infolist()
            seen = set()
            total = 0
            for member in members:
                path = PurePosixPath(member.filename)
                total += member.file_size
                mode = stat.S_IFMT(member.external_attr >> 16)
                if (path.is_absolute() or ".." in path.parts or not path.parts
                        or path.parts[0] != ARCHIVE_ROOT or member.filename in seen
                        or mode not in {0, stat.S_IFREG, stat.S_IFDIR}
                        or "\\" in member.filename
                        or total > 256 * 1024 * 1024 or len(members) > 10000):
                    raise RuntimeAdmissionError("sqlite_runtime_source_mismatch")
                seen.add(member.filename)
            result = {str(PurePosixPath(member.filename).relative_to(ARCHIVE_ROOT)): source.read(member)
                      for member in members if not member.is_dir()}
        return result
    except (OSError, zipfile.BadZipFile, KeyError, AttributeError) as error:
        raise RuntimeAdmissionError("sqlite_runtime_source_mismatch") from error


def _write(path, body, mode=0o444):
    with path.open("xb") as output:
        output.write(body)
    path.chmod(mode)


def build_package(archive: Path, destination: Path, python: Path) -> Path:
    """No network, installed selector access, database access or overwrite."""
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("sqlite_runtime_destination_exists")
    if sys.platform != "linux" or platform.machine() != "x86_64":
        raise RuntimeAdmissionError("sqlite_runtime_platform_unsupported")
    if (not destination.is_absolute() or destination.parent.resolve() != destination.parent
            or any(ord(c) < 32 or c == ":" for c in str(destination))
            or not python.is_absolute() or not os.access(python, os.X_OK)):
        raise RuntimeAdmissionError("sqlite_runtime_path_unsafe")
    sources = _source(archive)
    env = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "PYTHONDONTWRITEBYTECODE": "1"}
    with tempfile.TemporaryDirectory(prefix=".sqlite-build-", dir=destination.parent) as temporary:
        work = Path(temporary)
        env.update(HOME=str(work), TMPDIR=str(work))
        for name, body in sources.items():
            target = work / "source" / name
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            _write(target, body, mode=0o700)
        subprocess.run(["/bin/sh", str(work / "source/configure"), "--disable-tcl",
                        "--enable-update-limit", "--disable-rpath", "--disable-readline"],
                       cwd=work, env=env, check=True, timeout=120)
        subprocess.run(["/usr/bin/make", "-j2", "sqlite3.c"], cwd=work, env=env,
                       check=True, timeout=180)
        amalgamation_sha3 = hashlib.sha3_256((work / "sqlite3.c").read_bytes()).hexdigest()
        built = work / ("libsqlite3.so." + VERSION)
        command = ["/usr/bin/cc", "-O2", "-fPIC", "-shared", "-Wl,-soname,libsqlite3.so.0",
                   *("-D" + option for option in DEFINES), str(work / "sqlite3.c"),
                   "-o", str(built), "-lm", "-ldl", "-pthread"]
        subprocess.run(command, cwd=work, env=env, check=True, timeout=240)
        dynamic = subprocess.run(["/usr/bin/readelf", "-d", str(built)], env=env,
                                 capture_output=True, text=True, check=True, timeout=10).stdout
        if "(RPATH)" in dynamic or "(RUNPATH)" in dynamic or "[libsqlite3.so.0]" not in dynamic:
            raise RuntimeAdmissionError("sqlite_runtime_linkage_invalid")
        destination.mkdir(mode=0o700)
        (destination / "lib").mkdir(mode=0o700)
        library = destination / "lib" / built.name
        _write(library, built.read_bytes())
        (destination / "lib/libsqlite3.so.0").symlink_to(built.name)
        for name in ("contract.py", "launch.py"):
            _write(destination / name, Path(__file__).with_name(name).read_bytes())
        inspect = """
import _sqlite3, hashlib, json, pathlib, sqlite3, sys
c = sqlite3.connect(':memory:')
version, source_id = c.execute('SELECT sqlite_version(), sqlite_source_id()').fetchone()
options = sorted(row[0] for row in c.execute('PRAGMA compile_options'))
c.close()
extension = pathlib.Path(_sqlite3.__file__).resolve()
print(json.dumps({'engine': {'version':version, 'source_id':source_id, 'compile_options':options},
 'python': {'path':sys.executable, 'sha256':hashlib.sha256(pathlib.Path(sys.executable).read_bytes()).hexdigest(),
 'extension_path':str(extension), 'extension_sha256':hashlib.sha256(extension.read_bytes()).hexdigest()}}))
"""
        selected = dict(env, LD_LIBRARY_PATH=str(destination / "lib"))
        probe = subprocess.run([str(python), "-I", "-S", "-B", "-c", inspect], env=selected,
                               capture_output=True, check=True, timeout=30)
        identity = json.loads(probe.stdout)
        if (identity["engine"]["version"] != VERSION or identity["engine"]["source_id"] != SOURCE_ID
                or identity["python"]["path"] != str(python)):
            raise RuntimeAdmissionError("sqlite_runtime_engine_mismatch")
        data = {"format": 1, "platform": "linux-" + platform.machine(), **identity,
                "source": {"archive_sha3": ARCHIVE_SHA3, "amalgamation_sha3": amalgamation_sha3},
                "files": {name: sha256(destination / name) for name in
                          ("contract.py", "launch.py", "lib/" + built.name)}}
        body = json.dumps(data, sort_keys=True, indent=2).encode() + b"\n"
        digest = hashlib.sha256(body).hexdigest()
        _write(destination / "manifest.json", body)
        _write(destination / "python", selector_text(str(python), digest, data["files"]).encode(), mode=0o555)
        verify_package(destination, digest)
        subprocess.run([str(python), "-I", "-S", "-B", str(destination / "contract.py"),
                        "--probe", str(destination), digest], env=selected,
                       check=True, timeout=30, stdout=subprocess.DEVNULL)
        (destination / "lib").chmod(0o555)
        destination.chmod(0o555)
    return destination / "python"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare an exclusive offline SQLite runtime package")
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    args = parser.parse_args()
    try:
        selector = build_package(args.archive, args.destination, args.python)
        print(json.dumps({"status": "prepared_not_activated", "selector": str(selector)}))
    except (RuntimeAdmissionError, OSError, subprocess.SubprocessError) as error:
        message = str(error) if isinstance(error, RuntimeAdmissionError) else "sqlite_runtime_build_failed"
        print(message, file=sys.stderr)
        raise SystemExit(78)
