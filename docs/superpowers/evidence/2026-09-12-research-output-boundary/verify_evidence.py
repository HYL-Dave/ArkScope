"""Validate this plan's sealed evidence hashes and excluded artifact classes."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path


def verify(root):
    root = root.resolve()
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest["format"] != 1:
        raise ValueError("unsupported evidence manifest")
    declared = {"manifest.json"}
    decoded_bytes = 0
    for row in manifest["files"]:
        path = root / row["path"]
        if (path.is_symlink() or not path.resolve().is_relative_to(root)
                or row["path"] in declared):
            raise ValueError("invalid evidence path")
        declared.add(row["path"])
        stored = path.read_bytes()
        if len(stored) != row["bytes"] or hashlib.sha256(stored).hexdigest() != row["sha256"]:
            raise ValueError("stored evidence identity mismatch")
        raw = gzip.decompress(stored) if path.name != Path(row["source"]).name else stored
        if hashlib.sha256(raw).hexdigest() != row["source_sha256"]:
            raise ValueError("source evidence identity mismatch")
        decoded_bytes += len(raw)
        if path.suffix in {".db", ".sqlite", ".sqlite3"} or path.name == ".env":
            raise ValueError("application state must not be sealed")
    actual = {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()}
    if actual != declared:
        raise ValueError("unlisted or missing evidence file")
    result = {"format": 1, "files_verified": len(declared) - 1,
              "all_hashes_match": True, "unlisted_files": 0,
              "source_bytes": decoded_bytes,
              "manifest_sha256": hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest()}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    verify(args.root)
