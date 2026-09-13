"""Separate position-only uncertainty churn from new scanner obligations."""

import argparse
import ast
from collections import Counter
import difflib
import gzip
import json
from pathlib import Path
import subprocess

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
parser = argparse.ArgumentParser()
parser.add_argument("current")
parser.add_argument("output")
args = parser.parse_args()
base = json.loads(gzip.decompress((WORK / "task5-census-baseline/census.json.gz").read_bytes()))
current = json.loads(gzip.decompress((WORK / args.current / "census.json.gz").read_bytes()))


def stable(row):
    return json.dumps({key: value for key, value in row.items()
                       if key not in {"id", "line", "column"}}, sort_keys=True)


def source(revision, path):
    return subprocess.run(["git", "show", f"{revision}:{path}"], cwd=ROOT,
                          capture_output=True, check=True).stdout.decode()


def statement(text, line):
    nodes = [node for node in ast.walk(ast.parse(text))
             if isinstance(node, (ast.Constant, ast.JoinedStr, ast.Call))
             and getattr(node, "lineno", None) == line]
    sql_nodes = [node for node in nodes if isinstance(node, (ast.Constant, ast.JoinedStr))]
    if sql_nodes:
        return sorted(ast.dump(node, include_attributes=False) for node in sql_nodes)
    return sorted(ast.dump(node, include_attributes=False) for node in nodes)


previous = {row["id"]: row for row in base["uncertainties"]}
seen = Counter()
relocated, substantive = [], []
sql_sources = {}
for row in current["uncertainties"]:
    if row["id"] in previous:
        continue
    candidates = [old for old in previous.values() if stable(old) == stable(row)]
    match = None
    for old in candidates:
        if seen[old["id"]]:
            continue
        if row["axis"] == "sql":
            path = row["path"]
            if path not in sql_sources:
                try:
                    sql_sources[path] = source("7401e656", path), (ROOT / path).read_text()
                except subprocess.CalledProcessError:
                    sql_sources[path] = None
            texts = sql_sources[path]
            if texts is None:
                continue
            blocks = difflib.SequenceMatcher(a=texts[0].splitlines(), b=texts[1].splitlines(), autojunk=False).get_matching_blocks()
            mapped = any(block.a <= old["line"] - 1 < block.a + block.size
                         and row["line"] - 1 == block.b + old["line"] - 1 - block.a for block in blocks)
            if not mapped or not statement(texts[0], old["line"]) or statement(texts[0], old["line"]) != statement(texts[1], row["line"]):
                continue
        match = old
        break
    if match:
        seen[match["id"]] += 1
        relocated.append({"old": match, "new": row})
    else:
        substantive.append(row)

report = {
    "base_counts": {key: len(base[key]) for key in ("candidates", "uncertainties")},
    "current_counts": {key: len(current[key]) for key in ("candidates", "uncertainties")},
    "comparison": current["comparison"],
    "position_only_count": len(relocated),
    "position_only_by_axis": dict(Counter(row["new"]["axis"] for row in relocated)),
    "position_only": relocated, "new_or_changed": substantive,
    "method": "Identical non-position metadata; SQL additionally maps unchanged source lines and identical source AST fragments. This is not scanner completeness or deletion authority.",
}
with (WORK / args.output).open("x") as target:
    json.dump(report, target, indent=2, sort_keys=True)
    target.write("\n")
print(json.dumps({**{key: report[key] for key in ("base_counts", "current_counts", "position_only_count", "position_only_by_axis")},
                  "new_or_changed_count": len(substantive)}, indent=2))
