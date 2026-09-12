"""Explain new uncertainty IDs with source identity, without waiving the census."""

import argparse
import ast
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
BASE = "18d46062c30da87b30666b1ba0f290872a28fa7f"


def source(revision, path):
    return subprocess.run(["git", "show", f"{revision}:{path}"], cwd=ROOT,
                          capture_output=True, check=True).stdout.decode("utf-8")


def main(name, revision):
    report = json.loads(gzip.decompress((WORK / name / "census.json.gz").read_bytes()))
    ids = set(report["comparison"]["new_uncertainties"])
    rows = []
    for uncertainty in report["uncertainties"]:
        if uncertainty["id"] not in ids:
            continue
        row = {**uncertainty, "classification": "requires_review"}
        path, line = row["path"], row["line"]
        tree = ast.parse(source(revision, path))
        if row["axis"] == "sql":
            literals = [node for node in ast.walk(tree)
                        if isinstance(node, ast.Constant) and type(node.value) is str
                        and node.lineno <= line <= node.end_lineno]
            if len(literals) == 1:
                value = literals[0].value
                matches = [node.lineno for node in ast.walk(ast.parse(source(BASE, path)))
                           if isinstance(node, ast.Constant) and node.value == value]
                row.update(literal_sha256=hashlib.sha256(value.encode()).hexdigest(),
                           matching_base_lines=matches)
                if matches:
                    row["classification"] = "unchanged_literal_relocated"
        elif row["kind"] == "dynamic_import" and path.startswith("tests/"):
            calls = [ast.unparse(node) for node in ast.walk(tree)
                     if isinstance(node, ast.Call) and node.lineno == line
                     and "import" in ast.unparse(node.func)]
            if calls:
                row.update(classification="test_only_dynamic_import", expressions=calls)
        rows.append(row)
    result = {"base": BASE, "revision": revision, "uncertainties": rows,
              "review_required_preserved": report["comparison"]["review_required"],
              "note": "Source explanation only; no candidate deletion or scanner waiver."}
    output = WORK / f"{name}-classification.json"
    with output.open("x") as target:
        json.dump(result, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("revision")
    args = parser.parse_args()
    main(args.name, args.revision)
