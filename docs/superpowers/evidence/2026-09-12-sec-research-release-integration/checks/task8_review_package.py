"""Create a bounded review view, excluding only already archived evidence bytes."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]


def git(*args):
    return subprocess.run(["git", "--no-pager", *args], cwd=ROOT, check=True,
                          capture_output=True).stdout


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("base")
    parser.add_argument("head")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    base = git("rev-parse", args.base + "^{commit}").decode().strip()
    head = git("rev-parse", args.head + "^{commit}").decode().strip()
    revision = base + ".." + head
    paths = (".", ":(exclude)docs/superpowers/evidence", ":(exclude).superpowers")
    all_names = set(git("diff", "--name-only", revision).decode().splitlines())
    names = git("diff", "--name-only", revision, "--", *paths).decode().splitlines()
    excluded = sorted(all_names - set(names))
    assert all(name.startswith(("docs/superpowers/evidence/", ".superpowers/")) for name in excluded)
    header = {"base": base, "head": head, "included_files": names,
              "excluded_evidence_files": len(excluded),
              "scope": "All product, test, dependency, current documentation and skill changes; archived evidence bytes remain in the complete package."}
    result = b"# Current-source whole-change review\n\n" + json.dumps(header, indent=2).encode()
    result += b"\n\n## Commits\n" + git("log", "--oneline", revision)
    result += b"\n## Stat\n" + git("diff", "--stat", revision, "--", *paths)
    result += b"\n## Diff\n" + git("diff", "--no-ext-diff", "-U10", revision, "--", *paths)
    with args.output.open("xb") as handle:
        handle.write(result)
    print(json.dumps({"path": str(args.output), "bytes": len(result),
                      "sha256": hashlib.sha256(result).hexdigest(),
                      "included_files": len(names), "excluded_evidence_files": len(excluded)}))
