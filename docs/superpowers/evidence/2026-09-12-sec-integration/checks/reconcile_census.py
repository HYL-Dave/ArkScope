"""Compare shifted census locations using source ASTs, not matching counts."""

import argparse
import ast
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
BASE = "41682675"
parser = argparse.ArgumentParser()
parser.add_argument("--run", default="census-integration-final")
parser.add_argument("--revision", default="885c2a2d")
args = parser.parse_args()
FINAL = args.revision


def read_run(name):
    return json.loads(gzip.decompress((WORK / name / "census.json.gz").read_bytes()))


def source_nodes(revision, path, line):
    assert path.startswith("src/") and path.endswith(".py") and ".." not in Path(path).parts
    source = subprocess.run(
        ["git", "--no-optional-locks", "show", f"{revision}:{path}"],
        cwd=ROOT, env={"PATH": "/usr/bin:/bin"}, check=True,
        capture_output=True, text=True,
    ).stdout
    nodes = [ast.dump(node, include_attributes=False) for node in ast.walk(ast.parse(source))
             if isinstance(node, (ast.Call, ast.Constant, ast.JoinedStr))
             and getattr(node, "lineno", None) == line]
    assert nodes, (revision, path, line)
    return hashlib.sha256(json.dumps(sorted(nodes)).encode()).hexdigest()


base, final = read_run("census-integration-base"), read_run(args.run)
old = {row["id"]: row for row in base["uncertainties"]}
new = {row["id"]: row for row in final["uncertainties"]}
removed = [old[key] for key in old.keys() - new.keys()]
added = [new[key] for key in new.keys() - old.keys()]


def signatures(rows, revision):
    result = defaultdict(list)
    for row in rows:
        assert row["axis"] == "sql"
        metadata = {k: v for k, v in row.items() if k not in {"id", "line"}}
        digest = source_nodes(revision, row["path"], row["line"])
        result[(json.dumps(metadata, sort_keys=True), digest)].append(row)
    return result


before, after = signatures(removed, BASE), signatures(added, FINAL)
assert {k: len(v) for k, v in before.items()} == {k: len(v) for k, v in after.items()}
matches = []
for (metadata, digest), rows in sorted(before.items()):
    later = after[(metadata, digest)]
    for first, last in zip(sorted(rows, key=lambda r: (r["line"], r["id"])),
                           sorted(later, key=lambda r: (r["line"], r["id"]))):
        matches.append({**json.loads(metadata), "old_id": first["id"],
                        "new_id": last["id"], "old_line": first["line"],
                        "new_line": last["line"], "source_nodes_sha256": digest})

record = {
    "base_revision": BASE, "final_revision": FINAL,
    "base_source_digest": base["source_digest"], "final_source_digest": final["source_digest"],
    "classification": "unchanged_ast_at_shifted_locations",
    "matches": matches,
    "by_path": dict(sorted(Counter(row["path"] for row in added).items())),
    "by_kind": dict(sorted(Counter(row["kind"] for row in added).items())),
    "new_candidates": final["comparison"]["new_candidates"],
    "coverage_reductions": final["comparison"]["coverage_reductions"],
    "review_required": final["comparison"]["review_required"],
    "limit": "Line movement does not resolve the underlying SQL scanner uncertainties or authorize data deletion.",
}
destination = WORK / args.run / "reconciliation.json"
with destination.open("x") as output:
    json.dump(record, output, indent=2, sort_keys=True)
    output.write("\n")
print(json.dumps({"matched": len(matches), "classification": record["classification"],
                  "output": str(destination)}))
