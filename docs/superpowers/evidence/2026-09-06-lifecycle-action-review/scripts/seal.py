"""Publish a measured action-review packet only after complete offline admission."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from verify import MUTATIONS

PACKET = Path(__file__).resolve().parent.parent
ROOT = PACKET.parents[3]
PRIOR = PACKET.parent / "2026-09-06-lifecycle-population-reconciliation"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report(path):
    root = ET.parse(path).getroot()
    nodes = [row.get("classname", "") + "::" + row.get("name", "") for row in root.iter("testcase")]
    counts = {key: sum(int(suite.get(key, "0")) for suite in root.iter("testsuite"))
              for key in ("tests", "failures", "errors", "skipped")}
    failed = [row.get("classname", "") + "::" + row.get("name", "") for row in root.iter("testcase")
              if row.find("failure") is not None or row.find("error") is not None]
    assert counts["tests"] == len(nodes) == len(set(nodes))
    return {"file": path.name, "sha256": digest(path), "counts": counts, "failed_nodes": failed}, sorted(nodes)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--frontend", type=Path, required=True)
    parser.add_argument("--interrupted-results", type=Path, action="append", required=True)
    args = parser.parse_args()
    results = json.loads((args.results / "report.json").read_text())
    assert results["complete"] and len(results["mutations"]) == 23
    assert [(item["name"], item["owner"]) for item in results["mutations"]] == [
        (item["name"], item["owner"]) for item in MUTATIONS]
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert head == results["head"]
    for name, value in results["code_sha256"].items():
        assert digest(ROOT / name) == value, name
        assert digest(args.results.parent / "source" / name) == value, name
    changed = set()
    for command in (["git", "diff", "--name-only", "-z"], ["git", "ls-files", "--others", "--exclude-standard", "-z"]):
        changed.update(name for name in subprocess.check_output(command, cwd=ROOT, text=True).split("\0")
                       if name and not name.startswith("docs/"))
    assert changed <= set(results["code_sha256"])
    payloads, measured = {}, {}
    for name in ("baseline", "restored", "integration", "backend"):
        item = results[name]
        measured[name], nodes = report(args.results / (name + ".xml"))
        assert item["exit_code"] == 0 and measured[name]["counts"] == item["counts"]
        assert item["counts"]["failures"] == item["counts"]["errors"] == 0
        payloads[name + "-nodes.json"] = {"count": len(nodes), "nodes": nodes}
    assert payloads["baseline-nodes.json"] == payloads["restored-nodes.json"]
    frontend = json.loads(args.frontend.read_text())
    frontend_nodes = sorted(
        Path(suite["name"]).relative_to(ROOT / "apps/arkscope-web").as_posix() + "::" + test["fullName"]
        for suite in frontend["testResults"] for test in suite["assertionResults"])
    assert frontend["success"] and frontend["numFailedTests"] == frontend["numPendingTests"] == 0
    assert frontend["numTotalTests"] == len(frontend_nodes)
    assert all(test["status"] == "passed" for suite in frontend["testResults"] for test in suite["assertionResults"])
    previous_ui = PACKET.parent / "2026-09-06-price-window-and-repair-ui"
    assert frontend_nodes == json.loads((previous_ui / "frontend-nodes.json").read_text())["nodes"]
    payloads["frontend-nodes.json"] = {"count": len(frontend_nodes), "nodes": frontend_nodes}
    measured["frontend"] = {"file": args.frontend.name, "sha256": digest(args.frontend),
                            "counts": {"tests": len(frontend_nodes), "failures": 0, "errors": 0, "skipped": 0}}
    for item in results["mutations"]:
        measured_mutation, _ = report(args.results / (item["name"] + ".xml"))
        assert item["exit_code"] == 1 and item["killed_by_owner"] and not item["counts"]["errors"]
        assert item["counts"] == measured_mutation["counts"] and item["failed_nodes"] == measured_mutation["failed_nodes"]
        assert item["counts"]["tests"] == results["baseline"]["counts"]["tests"]
        assert any(item["owner"] in node for node in item["failed_nodes"])
        assert all(value == results["code_sha256"][name] for name, value in item["restored_sha256"].items())
    node_changes = {}
    for name in ("integration", "backend"):
        old = set(json.loads((PRIOR / (name + "-nodes.json")).read_text())["nodes"])
        new = set(payloads[name + "-nodes.json"]["nodes"])
        added, removed = sorted(new - old), sorted(old - new)
        assert not removed and len(added) == 86
        assert all(node.startswith(("tests.test_security_lifecycle_review::", "tests.test_security_lifecycle_review_routes::")) for node in added)
        node_changes[name] = {"added_count": len(added), "removed_count": len(removed), "added": added, "removed": removed}
    old_packets = {}
    for previous in (PRIOR, PACKET.parent / "2026-09-06-price-window-and-repair-ui"):
        manifest = json.loads((previous / "files.sha256.json").read_text())["files"]
        assert all(digest(previous / name) == value for name, value in manifest.items())
        old_packets[previous.name] = {"seal_sha256": digest(previous / "files.sha256.json"), "files_verified": len(manifest)}
    schema_files = ("src/security_lifecycle_schema.py", "src/ticker_identity_schema.py", "src/sa_tracking_memberships.py")
    prior_source_manifest = json.loads((PRIOR / "source-manifest.json").read_text())
    previous_sources = prior_source_manifest["files"]
    schema_checks = {}
    for name in schema_files:
        if name in previous_sources:
            expected, basis = previous_sources[name], "prior_source_manifest"
        else:
            blob = subprocess.check_output(["git", "show", prior_source_manifest["base_commit"] + ":" + name], cwd=ROOT)
            expected, basis = hashlib.sha256(blob).hexdigest(), "prior_base_commit"
        assert digest(ROOT / name) == digest(args.results.parent / "source" / name) == expected
        schema_checks[name] = {"sha256": expected, "basis": basis}
    red = []
    for name in ("initial-red", "boundaries-red-v2", "recovery-red-v2", "projection-red", "full-focus", "proposals-red", "legacy-projection-red", "legacy-status-red", "reapproval-red"):
        value, _ = report(Path("/tmp/arkscope-lifecycle-review-" + name + ".xml"))
        assert value["counts"]["failures"] > 0 and not value["counts"]["errors"]
        red.append(value)
    fixture_corrections = [report(Path("/tmp/arkscope-lifecycle-review-" + name + ".xml"))[0]
                           for name in ("boundaries-red", "recovery-red")]
    assert len(args.interrupted_results) == 4
    for index, previous in enumerate(args.interrupted_results, start=1):
        interrupted = json.loads((previous / "report.json").read_text())
        assert interrupted["complete"] is False and interrupted["baseline"]["exit_code"] == 0
        assert len(interrupted["mutations"]) == (4, 16, 4, 15)[index - 1]
        for name, value in interrupted["code_sha256"].items():
            assert digest(previous.parent / "source" / name) == value
        payloads[f"interrupted-campaign-{index}.json"] = interrupted
    payloads["verification.json"] = {"measured": measured, "red": red, "fixture_correction_reports_not_admission": fixture_corrections,
        "mutation_count": len(results["mutations"]), "node_changes": {name: {key: row[key] for key in ("added_count", "removed_count")} for name, row in node_changes.items()},
        "changed_product_test_files_verified": len(changed), "frozen_source_files_verified": len(results["code_sha256"]),
        "prior_packets": old_packets, "schema_files_unchanged": schema_checks, "temporary_stores": "separate_tmpfs_filesystem",
        "provider_calls": 0, "production_reads": False, "production_writes": False, "migration": False,
        "app_restart": False, "commit": False, "merge": False, "push": False,
        "complete_slice": "provider_backed_action_review_backend", "task_6_complete": False,
        "remaining": ["validated_web_finding_and_confirmation", "compact_ui_and_research_projection", "bounded_web_adapter", "release_cutover"]}
    payloads["node-changes.json"] = node_changes
    payloads["focus-files.json"] = {"files": results["focus_files"]}
    payloads["integration-files.json"] = {"files": results["integration_files"]}
    payloads["mutation-results.json"] = {"baseline": results["baseline"], "mutations": results["mutations"], "restored": results["restored"]}
    sources = set(results["code_sha256"])
    sources.update(schema_files)
    sources.update({"docs/design/PROJECT_PRIORITY_MAP.md", "docs/superpowers/plans/2026-09-05-lifecycle-tracking-first-implementation.md",
                    "docs/superpowers/specs/2026-09-05-lifecycle-tracking-status-and-web-supplement-design.md",
                    "docs/superpowers/plans/2026-09-05-lifecycle-terminal-membership-completion.md"})
    sources.update(str(path.relative_to(ROOT)) for path in (PACKET / "scripts").glob("*.py"))
    payloads["source-manifest.json"] = {"base_commit": head, "files": {name: digest(ROOT / name) for name in sorted(sources)}}
    env = {key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR"}}
    for name, script in (("typecheck", "typecheck"), ("build", "build"), ("i18n", "check:i18n-literals")):
        command = ["npm", "run", script]
        check = subprocess.run(command, cwd=ROOT / "apps/arkscope-web", env=env, capture_output=True, text=True, timeout=180)
        assert check.returncode == 0, check.stdout + check.stderr
        payloads[name + ".json"] = {"command": command, "exit_code": check.returncode, "output": check.stdout + check.stderr}
    subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=True)
    assert not (PACKET / "files.sha256.json").exists()
    assert not any((PACKET / name).exists() for name in payloads)
    for name, value in payloads.items():
        with (PACKET / name).open("x") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
    files = {str(path.relative_to(PACKET)): digest(path) for path in sorted(PACKET.rglob("*"))
             if path.is_file() and "__pycache__" not in path.parts and path.name != "files.sha256.json"}
    with (PACKET / "files.sha256.json").open("x") as stream:
        json.dump({"algorithm": "sha256", "file_count": len(files), "files": files}, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"measured": {name: value["counts"] for name, value in measured.items()}, "files": len(files),
                      "seal_sha256": digest(PACKET / "files.sha256.json")}), flush=True)


if __name__ == "__main__":
    main()
