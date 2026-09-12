"""Seal only this plan's reports, commands and test results, never fixture data."""

import argparse
import gzip
import hashlib
import json
from pathlib import Path

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
TOP_SUFFIXES = {".md", ".py", ".cjs", ".mjs", ".diff", ".json", ".sha256"}
RUN_FILES = {"command.json", "output.log", "results.xml", "census.json.gz", "reconciliation.json", "reconciliation-detailed.json", "task2-inverse.json"}


def seal(output):
    output = output.resolve()
    if not output.is_relative_to(ROOT / "docs/superpowers/evidence"):
        raise ValueError("output must be under this worktree's evidence directory")
    unfinished = [path.name for path in WORK.iterdir() if path.is_dir()
                  and (path / "output.log").exists()
                  and not (path / "command.json").exists()]
    if unfinished:
        raise ValueError("unfinished run receipts: " + ", ".join(sorted(unfinished)))
    output.mkdir(exist_ok=False)
    records = []
    for path in sorted(WORK.iterdir()):
        if path.is_symlink():
            raise ValueError("symlink in plan artifact selection")
        if path.is_file() and path.suffix in TOP_SUFFIXES:
            selected = [path]
        elif path.is_dir() and (path / "command.json").is_file():
            selected = [path / name for name in sorted(RUN_FILES) if (path / name).is_file()]
            if path.name in {"task1-browser-before", "task1-browser-after"}:
                browser = path / "browser"
                selected += [browser / "results.json", *sorted(browser.glob("*.png"))]
        elif path.is_dir() and path.name == "task1-fixture":
            selected = [path / "index.html", path / "fixture.tsx"]
        else:
            continue
        for source in selected:
            if source.is_symlink() or not source.resolve().is_relative_to(WORK):
                raise ValueError("artifact escapes plan workspace")
            relative = source.relative_to(WORK)
            destination = output / relative
            if (source.suffix in {".xml", ".log", ".diff", ".stdout", ".stderr"}
                    or source.name.startswith("test_") and source.suffix == ".py"):
                destination = destination.with_suffix(destination.suffix + ".gz")
            destination.parent.mkdir(parents=True, exist_ok=True)
            raw = source.read_bytes()
            stored = gzip.compress(raw, mtime=0) if destination.name != source.name else raw
            with destination.open("xb") as target:
                target.write(stored)
            records.append({"path": str(destination.relative_to(output)), "source": str(relative),
                            "source_sha256": hashlib.sha256(raw).hexdigest(),
                            "sha256": hashlib.sha256(stored).hexdigest(), "bytes": len(stored)})
    manifest = {"format": 1, "files": records,
                "excluded": ["fixture databases", "token fixtures", "home/XDG trees", "other plan workspaces"],
                "credential_examples": "synthetic fixtures only; no provider or production credential read"}
    with (output / "manifest.json").open("x") as target:
        json.dump(manifest, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({"output": str(output), "files": len(records),
                      "stored_bytes": sum(row["bytes"] for row in records)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    seal(args.output)
