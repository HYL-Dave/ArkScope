"""Explain census identity changes without suppressing raw review requirements."""

import argparse
import ast
from collections import Counter, defaultdict
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]


def read_run(name):
    return json.loads(gzip.decompress((WORK / name / "census.json.gz").read_bytes()))


@lru_cache(maxsize=None)
def source_tree(revision, path):
    if not path.startswith("src/") or not path.endswith(".py") or ".." in Path(path).parts:
        return None
    result = subprocess.run(["git", "show", revision + ":" + path], cwd=ROOT,
                            capture_output=True, check=True, text=True)
    return ast.parse(result.stdout)


def source_nodes(revision, row):
    tree = source_tree(revision, row.get("path", row.get("file", "")))
    if tree is None:
        return None
    nodes = [ast.dump(node, include_attributes=False) for node in ast.walk(tree)
             if isinstance(node, (ast.Call, ast.Constant, ast.JoinedStr))
             and getattr(node, "lineno", None) == row.get("line")]
    return hashlib.sha256(json.dumps(sorted(nodes)).encode()).hexdigest() if nodes else None


def metadata(row):
    return {key: value for key, value in row.items() if key not in {"id", "line", "column"}}


def groups(rows, revision):
    grouped = defaultdict(list)
    for row in rows:
        key = json.dumps(metadata(row), sort_keys=True), source_nodes(revision, row)
        grouped[key].append(row)
    return grouped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default="census-maintenance-final")
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    base, final = read_run("census-maintenance-base"), read_run(args.run)
    old = {row["id"]: row for row in base["uncertainties"]}
    new = {row["id"]: row for row in final["uncertainties"]}
    removed = [old[key] for key in old.keys() - new.keys()]
    added = [new[key] for key in new.keys() - old.keys()]
    before, after = groups(removed, "ef5f7b48"), groups(added, args.revision)
    matches, matched_old, matched_new = [], set(), set()
    for key in sorted(before.keys() & after.keys(), key=repr):
        for first, last in zip(sorted(before[key], key=lambda row: row["id"]),
                               sorted(after[key], key=lambda row: row["id"])):
            matched_old.add(first["id"])
            matched_new.add(last["id"])
            matches.append({"old": first, "new": last,
                            "proof": "metadata_and_python_nodes" if key[1] else "metadata_only",
                            "source_nodes_sha256": key[1]})
    previous_candidates = {row["id"]: row for row in base["candidates"]}
    current_candidates = {row["id"]: row for row in final["candidates"]}
    previous_counts = Counter(row["id"] for row in base["candidates"])
    current_counts = Counter(row["id"] for row in final["candidates"])
    record = {
        "base_revision": "ef5f7b48", "final_revision": args.revision,
        "base_source_digest": base["source_digest"], "final_source_digest": final["source_digest"],
        "base_totals": {"candidates": len(base["candidates"]), "uncertainties": len(old),
                        "coverage": base["coverage"]},
        "final_totals": {"candidates": len(final["candidates"]), "uncertainties": len(new),
                         "coverage": final["coverage"]},
        "raw_comparison": final["comparison"],
        "removed_candidates_by_id": [previous_candidates[key] for key in
                               sorted(previous_candidates.keys() - current_candidates.keys())],
        "new_candidates": [current_candidates[key] for key in
                           sorted(current_candidates.keys() - previous_candidates.keys())],
        "matched_uncertainties": matches,
        "unmatched_removed_uncertainties": sorted([row for row in removed if row["id"] not in matched_old],
                                                  key=lambda row: row["id"]),
        "unmatched_new_uncertainties": sorted([row for row in added if row["id"] not in matched_new],
                                              key=lambda row: row["id"]),
        "proof_counts": dict(Counter(row["proof"] for row in matches)),
        "candidate_occurrences_removed": dict(sorted((previous_counts - current_counts).items())),
        "candidate_occurrences_added": dict(sorted((current_counts - previous_counts).items())),
        "candidate_id_multiplicity_note": "Repeated CSS selectors in different media contexts can share an ID; use occurrence counts, not unique-ID counts, for raw candidate total reconciliation.",
        "limit": "Metadata/location matches do not prove all code semantics or resolve scanner uncertainty. Raw review_required stays authoritative; unmatched rows require explicit review, never deletion by count.",
    }
    destination = WORK / args.run / "reconciliation-detailed.json"
    with destination.open("x") as target:
        json.dump(record, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps({"new_candidates": len(record["new_candidates"]),
                      "removed_candidate_ids": len(record["removed_candidates_by_id"]),
                      "removed_candidate_occurrences": sum(record["candidate_occurrences_removed"].values()),
                      "proof_counts": record["proof_counts"],
                      "unmatched_new_uncertainties": len(record["unmatched_new_uncertainties"]),
                      "unmatched_removed_uncertainties": len(record["unmatched_removed_uncertainties"]),
                      "output": str(destination)}, sort_keys=True))


if __name__ == "__main__":
    main()
