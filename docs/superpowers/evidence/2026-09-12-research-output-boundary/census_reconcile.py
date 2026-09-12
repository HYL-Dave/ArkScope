"""Verify the archived source baseline and reconcile this slice's census."""

from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
BASE = "18d46062c30da87b30666b1ba0f290872a28fa7f"
BASELINE = WORK / "census-base-02/census.json.gz"


def read(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def baseline_check(previous):
    checked = 0
    mismatches = []
    for row in previous["source_manifest"]:
        path = row["path"]
        if row["status"] != "read" or path.startswith(".superpowers/"):
            continue
        process = subprocess.run(
            ["git", "show", f"{BASE}:{path}"], cwd=ROOT, capture_output=True, check=True,
        )
        actual = hashlib.sha256(process.stdout).hexdigest()
        checked += 1
        if actual != row["sha256"]:
            mismatches.append({"path": path, "archived": row["sha256"], "base": actual})
    return {"base": BASE, "source_files_checked": checked, "mismatches": mismatches,
            "plan_workspace_contents_read": False}


def main(name=None):
    previous = read(BASELINE)
    result = {"baseline_identity": baseline_check(previous)}
    output = WORK / "census-baseline-check.json"
    if name:
        current = read(WORK / name / "census.json.gz")
        comparison = current["comparison"]
        new_ids = set(comparison["new_candidates"])
        result.update(
            status=current["status"], coverage=current["coverage"],
            candidate_count=len(current["candidates"]),
            uncertainty_count=len(current["uncertainties"]),
            comparison_counts={key: len(value) if isinstance(value, list) else value
                               for key, value in comparison.items()},
            new_candidates=[item for item in current["candidates"] if item["id"] in new_ids],
            new_uncertainty_kinds=dict(Counter(item.split(":")[0]
                                              for item in comparison["new_uncertainties"])),
            coverage_reductions=comparison["coverage_reductions"],
        )
        output = WORK / name / "reconciliation.json"
    with output.open("x") as target:
        json.dump(result, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main(*sys.argv[1:])
