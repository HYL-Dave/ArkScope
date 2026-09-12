"""Record the exact tested product/test source and local runner/runtime identity."""

import argparse
import hashlib
from importlib import metadata
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def freeze(output):
    paths = git("ls-files", "-z", "src", "data_sources", "tests", "apps", "requirements.txt").decode().split("\0")
    sources = []
    for name in sorted(path for path in paths if path):
        path = ROOT / name
        if path.suffix not in {".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".css", ".json", ".txt"}:
            continue
        if path.is_symlink():
            raise ValueError("unexpected source symlink")
        sources.append({"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    versions = {}
    for name in ("openai", "openai-agents", "anthropic", "claude-agent-sdk", "pydantic", "httpx", "pytest"):
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    result = {
        "head": git("rev-parse", "HEAD").decode().strip(),
        "tree": git("rev-parse", "HEAD^{tree}").decode().strip(),
        "source_files": sources,
        "source_collection_sha256": hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest(),
        "runner_sha256": {name: hashlib.sha256((WORK / name).read_bytes()).hexdigest()
                          for name in ("offline_pytest.py", "offline_node.cjs", "run_checks.py")},
        "python": sys.version, "sqlite": sqlite3.sqlite_version, "packages": versions,
        "production_databases_opened": False,
    }
    with output.open("x") as target:
        json.dump(result, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({"head": result["head"], "files": len(sources),
                      "source_collection_sha256": result["source_collection_sha256"], "output": str(output)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    freeze(parser.parse_args().output)
