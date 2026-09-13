"""Seal this continuation's selected receipts, never stores or runtime binaries."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
PREFIXES = ("task5-", "task6-", "task5_", "task6_", "task-5-", "task-6-", "maintenance_")
RUN_FILES = {"command.json", "output.log", "results.xml", "census.json.gz"}
TOP_SUFFIXES = {".py", ".md", ".json", ".diff"}
INVERSE_SOURCES = {f"{name}.py.{suffix}"
                   for name in ("maintenance", "schema_admin", "references", "captures")
                   for suffix in ("original", "mutated")}


def seal(output, *, prefixes=PREFIXES, extras=()):
    output = output.resolve()
    if not output.is_relative_to(ROOT / "docs/superpowers/evidence"):
        raise ValueError("archive destination outside worktree evidence")
    selected = []
    for path in sorted(WORK.iterdir()):
        if not (path.name.startswith(prefixes) or path.name == "progress.md"):
            continue
        if path.is_symlink():
            raise ValueError("artifact symlink")
        if path.is_dir():
            if path.name.endswith("-source"):
                entries = list(path.iterdir())
                names = {entry.name for entry in entries}
                if "receipt.json" not in names or not names <= INVERSE_SOURCES | {"receipt.json"}:
                    raise ValueError("unfinished or unknown inverse source receipt: " + path.name)
                if not all(entry.is_file() and not entry.is_symlink() for entry in entries):
                    raise ValueError("unsafe inverse source receipt")
                selected.extend(sorted(entries))
                continue
            if (path / "output.log").exists() and not (path / "command.json").is_file():
                raise ValueError("unfinished receipt: " + path.name)
            if (path / "command.json").is_file():
                selected.extend(path / name for name in sorted(RUN_FILES) if (path / name).is_file())
        elif path.suffix in TOP_SUFFIXES:
            selected.append(path)
    selected.extend(WORK / name for name in ("run_checks.py", "offline_pytest.py", "offline_node.cjs"))
    for relative in extras:
        relative = Path(relative)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("extra artifact path outside owned workspace")
        path = WORK / relative
        if not path.is_file() or path.suffix not in TOP_SUFFIXES | {".png", ".log", ".mjs", ".cjs", ".txt", ".ts", ".tsx", ".html", ".body"}:
            raise ValueError("unknown extra artifact: " + str(relative))
        selected.append(path)
    selected = sorted(set(selected))
    output.mkdir(exist_ok=False)
    records = []
    for source in selected:
        if source.is_symlink() or not source.resolve().is_relative_to(WORK):
            raise ValueError("artifact outside owned workspace")
        relative = source.relative_to(WORK)
        destination = output / relative
        raw = source.read_bytes()
        stored = raw
        if (source.suffix in {".log", ".xml", ".diff", ".original", ".mutated"}
                or source.name.endswith("-brief.md")):
            destination = destination.with_suffix(destination.suffix + ".gz")
            stored = gzip.compress(raw, mtime=0)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as handle:
            handle.write(stored)
        records.append({"path": destination.relative_to(output).as_posix(),
                        "source": relative.as_posix(), "source_sha256": hashlib.sha256(raw).hexdigest(),
                        "sha256": hashlib.sha256(stored).hexdigest(), "bytes": len(stored)})
    manifest = {"format": 1, "files": records,
                "excluded": ["fixture databases", "HOME and credentials", "compiled binaries",
                             "prior continuation receipts", "other plan workspaces"],
                "production_access": False}
    with (output / "manifest.json").open("x") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({"files": len(records), "stored_bytes": sum(row["bytes"] for row in records)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--prefix", action="append")
    parser.add_argument("--extra", action="append", default=[])
    args = parser.parse_args()
    seal(args.output, prefixes=tuple(args.prefix) if args.prefix else PREFIXES, extras=args.extra)
