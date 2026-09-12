"""Enumerate redaction/scrubbing call sites in tracked product source only."""

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]


class Calls(ast.NodeVisitor):
    def __init__(self, path):
        self.path = path
        self.stack = []
        self.rows = []

    def visit_scope(self, node):
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    visit_FunctionDef = visit_scope
    visit_AsyncFunctionDef = visit_scope
    visit_ClassDef = visit_scope

    def visit_Call(self, node):
        target = ast.unparse(node.func)
        if "redact" in target.lower() or "scrub" in target.lower():
            self.rows.append({"path": self.path, "line": node.lineno,
                              "scope": ".".join(self.stack), "target": target,
                              "expression": ast.unparse(node)})
        self.generic_visit(node)


def main(output, revision):
    listing = subprocess.run(
        ["git", "ls-tree", "-r", "-z", revision, "--", "src", "data_sources"],
        cwd=ROOT, capture_output=True, check=True,
    ).stdout
    rows, sources = [], []
    for item in listing.split(b"\0"):
        if not item:
            continue
        header, name = item.split(b"\t", 1)
        mode, kind, digest = header.decode("ascii").split()
        path = name.decode("utf-8")
        if not path.endswith(".py"):
            continue
        if mode == "120000" or kind != "blob":
            raise ValueError("unexpected non-regular product source")
        source = subprocess.run(["git", "cat-file", "blob", digest], cwd=ROOT,
                                capture_output=True, check=True).stdout
        tree = ast.parse(source, filename=path)
        visitor = Calls(path)
        visitor.visit(tree)
        rows.extend(visitor.rows)
        sources.append({"path": path, "sha256": hashlib.sha256(source).hexdigest()})
    result = {"revision": revision, "source_files": sources, "calls": rows,
              "scope_counts": dict(Counter(row["path"] for row in rows)),
              "limitations": "AST syntactic call inventory, not a complete dynamic data-flow proof; all rows require classification."}
    with output.open("x") as target:
        json.dump(result, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({"revision": revision, "source_files": len(sources), "calls": len(rows), "output": str(output)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    main(args.output, args.revision)
