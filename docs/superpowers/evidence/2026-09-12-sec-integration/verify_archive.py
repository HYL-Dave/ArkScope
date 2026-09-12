"""Verify the sealed archive in a Git revision, not merely on the local disk."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ARCHIVE = (HERE / "checks").relative_to(ROOT).as_posix()


def git(*arguments):
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, capture_output=True, check=True
    ).stdout


def verify(revision):
    revision = git("rev-parse", "--verify", revision + "^{commit}").decode().strip()
    manifest_path = ARCHIVE + "/manifest.json"
    body = git("show", revision + ":" + manifest_path)
    manifest = json.loads(body)
    expected = {manifest_path}
    for row in manifest["files"]:
        relative = PurePosixPath(row["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("invalid_manifest_path")
        path = ARCHIVE + "/" + relative.as_posix()
        if path in expected:
            raise ValueError("duplicate_manifest_path")
        expected.add(path)
    actual = set(git("ls-tree", "-r", "--name-only", "-z", revision, "--", ARCHIVE)
                 .decode().rstrip("\0").split("\0"))
    result = {
        "revision": revision,
        "manifest_sha256": hashlib.sha256(body).hexdigest(),
        "expected_files": len(expected),
        "committed_files": len(actual),
        "missing": sorted(expected - actual),
        "extra": sorted(actual - expected),
        "hash_mismatches": [],
    }
    if result["missing"] or result["extra"]:
        result["status"] = "archive_git_membership_mismatch"
        return result
    for row in manifest["files"]:
        stored = git("show", revision + ":" + ARCHIVE + "/" + row["path"])
        raw = (gzip.decompress(stored)
               if PurePosixPath(row["path"]).name != PurePosixPath(row["source"]).name
               else stored)
        if (len(stored) != row["bytes"]
                or hashlib.sha256(stored).hexdigest() != row["sha256"]
                or hashlib.sha256(raw).hexdigest() != row["source_sha256"]):
            result["hash_mismatches"].append(row["path"])
    result["status"] = "verified" if not result["hash_mismatches"] else "archive_hash_mismatch"
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("revision", nargs="?", default="HEAD")
    parser.add_argument("--receipt", type=Path)
    arguments = parser.parse_args()
    result = verify(arguments.revision)
    if arguments.receipt:
        with arguments.receipt.open("x") as target:
            json.dump(result, target, indent=2, sort_keys=True)
            target.write("\n")
    print(json.dumps({
        key: len(value) if isinstance(value, list) else value
        for key, value in result.items()
    }, sort_keys=True))
    raise SystemExit(0 if result["status"] == "verified" else 1)
