"""Record and reconcile exact local test/source evidence; no App imports."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
BASE = "95ad149ea4bda2569030f1dfc95f93bf3c279738"


def save(path, value):
    with path.open("x", encoding="utf-8") as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write("\n")


def source_identity():
    paths = subprocess.check_output(
        ["git", "ls-files", "-z", "--", "src", "tests", "data_sources"], cwd=ROOT,
    ).decode().rstrip("\0").split("\0")
    source = {}
    for relative in paths:
        path = ROOT / relative
        source[relative] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    patch = subprocess.check_output(["git", "diff", BASE, "--", "src", "tests", "data_sources"], cwd=ROOT)
    return {"paths": source, "patch_sha256": hashlib.sha256(patch).hexdigest()}


def nodes(path):
    values = [line for line in path.read_text().splitlines() if line.startswith("tests/") and "::" in line]
    assert len(set(values)) == len(values), "duplicate collected nodes"
    return set(values)


def reconcile(xml):
    old = nodes(WORK / "baseline-nodes.txt")
    new = nodes(WORK / "final-nodes.txt")
    paths = {node.split("::", 1)[0] for node in new}
    modules = {path[:-3].replace("/", "."): path for path in paths}
    results = {}
    for case in ET.parse(xml).iter("testcase"):
        classname = case.get("classname", "")
        matched = [module for module in modules if classname == module or classname.startswith(module + ".")]
        assert matched, ("unmapped executed node", classname, case.get("name"))
        module = max(matched, key=len)
        classes = classname[len(module):].lstrip(".").replace(".", "::")
        prefix = modules[module] + ("::" + classes if classes else "")
        node = prefix + "::" + case.get("name")
        assert node not in results, ("duplicate executed node", node)
        status = next((kind for kind in ("error", "failure", "skipped") if case.find(kind) is not None), "passed")
        results[node] = status
    assert set(results) == new, {"missing": sorted(new - results.keys()), "extra": sorted(results.keys() - new)}
    before = json.loads((WORK / "source-before.json").read_text())
    after = source_identity()
    assert before == after, "source/test bytes changed during final verification"
    counts = Counter(results.values())
    assert not counts["failure"] and not counts["error"], counts
    skipped = sorted(node for node, status in results.items() if status == "skipped")
    previous = json.loads((ROOT / "docs/superpowers/evidence/2026-09-10-pre-release-cleanup-audit/current-journal-cleanup/verification-summary.json").read_text())
    assert skipped == previous["skipped"], "skip identities changed"
    summary = {
        "base": BASE,
        "source_paths_verified": len(after["paths"]),
        "source_patch_sha256": after["patch_sha256"],
        "baseline_collected": len(old), "final_collected": len(new),
        "executed": len(results), "counts": dict(counts),
        "removed": sorted(old - new), "added": sorted(new - old),
        "skipped": skipped, "skip_identities_unchanged": True,
        "production_access": False,
    }
    save(WORK / "verification-summary.json", summary)
    print(json.dumps({key: len(value) if isinstance(value, list) else value for key, value in summary.items()}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("freeze", "reconcile"))
    args = parser.parse_args()
    if args.mode == "freeze":
        current = source_identity()
        save(WORK / "source-before.json", current)
        print(json.dumps({"source_paths": len(current["paths"]), "patch_sha256": current["patch_sha256"]}))
    else:
        reconcile(WORK / "backend-full.xml")
