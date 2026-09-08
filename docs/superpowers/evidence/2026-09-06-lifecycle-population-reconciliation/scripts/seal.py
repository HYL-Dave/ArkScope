"""Seal measured offline results only after all admission checks succeed."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

PACKET = Path(__file__).resolve().parent.parent
ROOT = PACKET.parents[3]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    (PACKET / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def report(path):
    root = ET.parse(path).getroot()
    nodes = [row.get("classname", "") + "::" + row.get("name", "") for row in root.iter("testcase")]
    counts = {key: sum(int(suite.get(key, "0")) for suite in root.iter("testsuite")) for key in ("tests", "failures", "errors", "skipped")}
    failed = [row.get("classname", "") + "::" + row.get("name", "") for row in root.iter("testcase")
              if row.find("failure") is not None or row.find("error") is not None]
    assert counts["tests"] == len(nodes) == len(set(nodes))
    return {"file": path.name, "sha256": digest(path), "counts": counts, "failed_nodes": failed}, sorted(nodes)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True, type=Path)
    args = parser.parse_args()
    results = json.loads((args.results / "report.json").read_text())
    assert results["complete"] and len(results["mutations"]) == 22
    for name, expected in results["code_sha256"].items():
        assert digest(ROOT / name) == expected, name
        assert digest(args.results.parent / "source" / name) == expected, name
    changed = set()
    for command in (["git", "diff", "--name-only", "-z"], ["git", "ls-files", "--others", "--exclude-standard", "-z"]):
        changed.update(name for name in subprocess.check_output(command, cwd=ROOT, text=True).split("\0")
                       if name and not name.startswith("docs/"))
    assert changed <= set(results["code_sha256"])
    for key in ("baseline", "restored", "integration", "backend"):
        item = results[key]
        assert item["exit_code"] == 0 and item["counts"]["errors"] == item["counts"]["failures"] == 0
    assert results["baseline"]["counts"] == results["restored"]["counts"]
    for item in results["mutations"]:
        assert item["killed_by_owner"] and item["exit_code"] == 1 and not item["counts"]["errors"]
        assert item["counts"]["tests"] == results["baseline"]["counts"]["tests"]
        assert any(item["owner"] in node for node in item["failed_nodes"])
        assert item["restored_sha256"] == results["code_sha256"][item["path"]]
    if results.get("harness_resume"):
        original = args.results / "report.before-harness-repair.json"
        assert digest(original) == results["harness_resume"]["original_report_sha256"]
        (PACKET / "interrupted-harness-report.json").write_bytes(original.read_bytes())
    measured = {}
    for name in ("baseline", "restored", "integration", "backend"):
        measured[name], nodes = report(args.results / (name + ".xml"))
        assert measured[name]["counts"] == results[name]["counts"]
        save(name + "-nodes.json", {"count": len(nodes), "nodes": nodes})
    red = []
    for name in ("red-v2", "boundaries-red", "dependencies-red-v2", "regulator-red", "reused-red", "shape-red", "provider-binding-red", "persistent-retirement-red", "literal-path-red-v2"):
        value, _ = report(Path("/tmp/arkscope-lifecycle-population-" + name + ".xml"))
        assert value["counts"]["failures"] > 0 and value["counts"]["errors"] == 0
        red.append(value)
    previous = PACKET.parent / "2026-09-06-price-window-and-repair-ui"
    prior = json.loads((previous / "files.sha256.json").read_text())["files"]
    assert all(digest(previous / name) == expected for name, expected in prior.items())
    node_changes = {}
    for name in ("integration", "backend"):
        old_nodes = set(json.loads((previous / (name + "-nodes.json")).read_text())["nodes"])
        new_nodes = set(json.loads((PACKET / (name + "-nodes.json")).read_text())["nodes"])
        added, removed = sorted(new_nodes - old_nodes), sorted(old_nodes - new_nodes)
        assert not removed
        assert len(added) == 63 and all(node.startswith("tests.test_security_lifecycle_population::") for node in added)
        node_changes[name] = {"added_count": len(added), "removed_count": len(removed), "added": added, "removed": removed}
    save("node-changes.json", node_changes)
    subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=True)
    save("focus-files.json", {"files": results["focus_files"]})
    save("integration-files.json", {"files": results["integration_files"]})
    save("mutation-results.json", {"baseline": results["baseline"], "mutations": results["mutations"], "restored": results["restored"],
        "harness_resume": results.get("harness_resume")})
    save("verification.json", {"measured": measured, "red": red, "mutation_count": 22,
        "node_changes": {name: {key: value[key] for key in ("added_count", "removed_count")} for name, value in node_changes.items()},
        "changed_product_test_files_verified": len(changed), "frozen_code_files_verified": len(results["code_sha256"]),
        "current_and_test_copy_verified_at_seal": True,
        "harness_resume": results.get("harness_resume"),
        "provider_calls": 0, "production_reads": False, "production_writes": False, "migration": False,
        "app_restart": False, "commit": False, "merge": False, "push": False,
        "prior_packet": {"seal_sha256": digest(previous / "files.sha256.json"), "files_verified": len(prior)},
        "full_backend_command": "python -m pytest -q tests"})
    sources = set(results["code_sha256"])
    sources.update({"docs/design/PROJECT_PRIORITY_MAP.md", "docs/superpowers/plans/2026-09-05-lifecycle-tracking-first-implementation.md",
        "docs/superpowers/plans/2026-09-05-lifecycle-terminal-membership-completion.md",
        "docs/superpowers/specs/2026-09-05-lifecycle-tracking-status-and-web-supplement-design.md"})
    sources.update(str(path.relative_to(ROOT)) for path in (PACKET / "scripts").glob("*.py"))
    save("source-manifest.json", {"base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "files": {name: digest(ROOT / name) for name in sorted(sources)}})
    files = {str(path.relative_to(PACKET)): digest(path) for path in sorted(PACKET.rglob("*"))
             if path.is_file() and "__pycache__" not in path.parts and path.name != "files.sha256.json"}
    save("files.sha256.json", {"algorithm": "sha256", "file_count": len(files), "files": files})
    print(json.dumps({"measured": {key: value["counts"] for key, value in measured.items()}, "packet_files": len(files),
                      "source_files": len(sources), "seal_sha256": digest(PACKET / "files.sha256.json")}))


if __name__ == "__main__":
    main()
