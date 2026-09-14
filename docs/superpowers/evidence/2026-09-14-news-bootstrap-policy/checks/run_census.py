"""Run the source census without opening tracked historical SDD scratch."""

import argparse
import hashlib
from pathlib import Path, PurePosixPath
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from tests import repository_inventory as inventory

_classify_path = inventory.classify_path


def classify_path(path):
    if PurePosixPath(path).parts[:1] == (".superpowers",):
        return "excluded_plan_workspace"
    return _classify_path(path)


inventory.classify_path = classify_path


def use_revision(revision, *, current_scanner=False):
    original_names = inventory.git_names
    tree = subprocess.run(
        ["git", "ls-tree", "-r", "-z", revision], cwd=ROOT, capture_output=True, check=True,
    )
    entries = {}
    for item in tree.stdout.split(b"\0"):
        if item:
            header, path = item.split(b"\t", 1)
            mode, kind, digest = header.decode("ascii").split()
            entries[path.decode("utf-8")] = (mode, kind, digest)

    def names(root, *arguments):
        return original_names(root, *arguments) if arguments else sorted(entries)

    def read_sources(root, paths):
        files, manifest = {}, []
        for path in sorted(paths):
            kind = classify_path(path)
            row = {"path": path, "kind": kind, "status": kind}
            manifest.append(row)
            if kind.startswith("excluded") or kind == "documentation":
                continue
            mode, object_kind, digest = entries[path]
            if mode == "120000":
                row["status"] = "symlink_not_read"
                continue
            if object_kind != "blob":
                raise RuntimeError("unexpected non-blob source")
            raw = subprocess.run(
                ["git", "cat-file", "blob", digest], cwd=ROOT, capture_output=True, check=True,
            ).stdout
            row.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            try:
                files[path] = raw.decode("utf-8")
                row["status"] = "read"
            except UnicodeDecodeError:
                row["status"] = "decode_failed"
        return files, manifest

    # The scanner itself stays identical at both checkpoints.
    for path in ("tests/repository_inventory.py", "tests/repository_sql_inventory.py",
                 "apps/arkscope-web/scripts/maintenance/frontend-inventory.mjs"):
        expected = subprocess.run(
            ["git", "cat-file", "blob", entries[path][2]], cwd=ROOT,
            capture_output=True, check=True,
        ).stdout
        if not current_scanner and (ROOT / path).read_bytes() != expected:
            raise RuntimeError("scanner differs from requested baseline")
    inventory.git_names = names
    inventory.read_sources = read_sources

if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--revision")
    parser.add_argument("--current-scanner-on-revision", action="store_true")
    options, rest = parser.parse_known_args()
    if options.revision:
        use_revision(options.revision, current_scanner=options.current_scanner_on_revision)
    raise SystemExit(inventory.main(rest))
