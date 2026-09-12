"""Verify only the explicitly authorized SQLite source artifact."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile


ROOT = Path(__file__).resolve().parent
ARCHIVE = ROOT / "sqlite-autoconf-3530400.tar.gz"
SOURCE = ROOT / "sqlite-autoconf-3530400"
ARCHIVE_SHA3 = "454e45f61c6bd75b7420e7190732dea03ce6639c63ada47bbc592f67fc340338"
AMALGAMATION_SHA3 = "67f423e9ebbbdc473cbc4772c872ee6b89f31fde4ed0279a5c25d5f65c043a16"
SOURCE_ID = "2026-07-24 19:02:57 bf7c7f30031888f4e796e429ab3978879485813aaca6f641c7b33e4e09459bcc"


def digest(path, algorithm):
    result = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("archive", "source"))
    args = parser.parse_args()
    report = {"phase": args.phase, "expected_source_id": SOURCE_ID}
    try:
        if args.phase == "archive":
            actual = digest(ARCHIVE, "sha3_256")
            report.update(archive=str(ARCHIVE), sha3_256=actual,
                          expected_sha3_256=ARCHIVE_SHA3,
                          sha256=digest(ARCHIVE, "sha256"), size_bytes=ARCHIVE.stat().st_size)
            assert actual == ARCHIVE_SHA3, "archive SHA3-256 mismatch; stop"
            with tarfile.open(ARCHIVE, "r:gz") as archive:
                members = archive.getmembers()
                for member in members:
                    path = PurePosixPath(member.name)
                    assert not path.is_absolute() and ".." not in path.parts, "unsafe archive path"
                    assert path.parts and path.parts[0] == SOURCE.name, "unexpected archive root"
                    assert member.isdir() or member.isfile(), "non-regular archive member; stop"
                report["archive_members"] = len(members)
        else:
            actual = digest(SOURCE / "sqlite3.c", "sha3_256")
            report.update(amalgamation=str(SOURCE / "sqlite3.c"), sha3_256=actual,
                          expected_sha3_256=AMALGAMATION_SHA3,
                          sha256=digest(SOURCE / "sqlite3.c", "sha256"))
            assert actual == AMALGAMATION_SHA3, "amalgamation SHA3-256 mismatch; stop"
            for name in ("sqlite3.h", "sqlite3.c"):
                source = (SOURCE / name).read_text(encoding="utf-8")
                version = re.search(r'^#define SQLITE_VERSION\s+"([^"]+)"', source, re.MULTILINE)
                identity = re.search(r'^#define SQLITE_SOURCE_ID\s+"([^"]+)"', source, re.MULTILINE)
                assert version and identity, f"missing identity in {name}"
                report[name] = {"version": version.group(1), "source_id": identity.group(1)}
                assert version.group(1) == "3.53.4", f"wrong version in {name}; stop"
                assert identity.group(1) == SOURCE_ID, f"wrong source ID in {name}; stop"
        report["result"] = "pass"
    except Exception as exc:
        report.update(result="stop", error_type=type(exc).__name__, error=str(exc))
    print(json.dumps(report, indent=2))
    return 0 if report["result"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
