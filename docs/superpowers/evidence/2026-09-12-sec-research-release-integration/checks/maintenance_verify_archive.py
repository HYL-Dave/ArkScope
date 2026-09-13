"""Verify committed archive membership, hashes and decompressed source digests."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess

ROOT = Path(__file__).resolve().parents[3]


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def verify(commit, archive):
    assert not archive.is_absolute() and ".." not in archive.parts
    prefix = archive.as_posix().rstrip("/") + "/"
    anchor = git("rev-parse", "--verify", commit + "^{commit}").decode().strip()
    manifest = json.loads(git("show", anchor + ":" + prefix + "manifest.json"))
    names = git("ls-tree", "-r", "--name-only", "-z", anchor, "--", prefix).decode().split("\0")
    actual = {name[len(prefix):] for name in names if name}
    declared = {row["path"] for row in manifest["files"]}
    assert len(declared) == len(manifest["files"])
    assert actual == declared | {"manifest.json"}, (actual - declared, declared - actual)
    stored_bytes = 0
    for row in manifest["files"]:
        relative = PurePosixPath(row["path"])
        assert not relative.is_absolute() and ".." not in relative.parts
        raw = git("show", anchor + ":" + prefix + row["path"])
        assert len(raw) == row["bytes"]
        assert hashlib.sha256(raw).hexdigest() == row["sha256"]
        content = gzip.decompress(raw) if row["path"] == row["source"] + ".gz" else raw
        assert hashlib.sha256(content).hexdigest() == row["source_sha256"]
        stored_bytes += len(raw)
    print(json.dumps({"commit": anchor, "files": len(declared), "stored_bytes": stored_bytes,
                      "exact_membership": True, "stored_and_source_hashes": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("commit")
    parser.add_argument("archive", type=PurePosixPath)
    args = parser.parse_args()
    verify(args.commit, args.archive)
