"""Seal only measured current-review results from one final product/test snapshot."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

from PIL import Image, ImageStat

from verify import MUTATIONS


PACKET = Path(__file__).resolve().parent.parent
ROOT = PACKET.parents[3]
PRIOR = PACKET.parent / "2026-09-06-lifecycle-action-review"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def backend_report(path):
    root = ET.parse(path).getroot()
    nodes = [row.get("classname", "") + "::" + row.get("name", "") for row in root.iter("testcase")]
    counts = {key: sum(int(suite.get(key, "0")) for suite in root.iter("testsuite"))
              for key in ("tests", "failures", "errors", "skipped")}
    failed = [row.get("classname", "") + "::" + row.get("name", "") for row in root.iter("testcase")
              if row.find("failure") is not None or row.find("error") is not None]
    assert counts["tests"] == len(nodes) == len(set(nodes))
    return {"file": path.name, "sha256": digest(path), "counts": counts, "failed_nodes": failed}, sorted(nodes)


def frontend_report(path, source):
    result = json.loads(path.read_text())
    nodes = sorted(Path(suite["name"]).relative_to(source / "apps/arkscope-web").as_posix() + "::" + test["fullName"]
                   for suite in result["testResults"] for test in suite["assertionResults"])
    counts = {"tests": result["numTotalTests"], "failures": result["numFailedTests"], "skipped": result["numPendingTests"],
              "errors": sum(not suite["assertionResults"] and suite["status"] == "failed" for suite in result["testResults"])}
    failed = [test["fullName"] for suite in result["testResults"] for test in suite["assertionResults"] if test["status"] == "failed"]
    assert counts["tests"] == len(nodes) == len(set(nodes))
    return {"file": path.name, "sha256": digest(path), "counts": counts, "failed_nodes": failed}, nodes


def validate_campaign(directory, kind):
    result = json.loads((directory / "report.json").read_text())
    assert result["complete"] and result["kind"] == kind
    assert [(item["name"], item["owner"]) for item in result["mutations"]] == [(item["name"], item["owner"]) for item in MUTATIONS[kind]]
    source = directory.parent / "source"
    parse = (lambda path: backend_report(path)) if kind == "backend" else (lambda path: frontend_report(path, source))
    suffix = ".xml" if kind == "backend" else ".json"
    measured, manifests = {}, {}
    for name in ("baseline", "restored", "integration", "backend") if kind == "backend" else ("baseline", "restored"):
        item = result[name]
        measured[name], nodes = parse(directory / (name + suffix))
        assert item["exit_code"] == 0 and item["counts"] == measured[name]["counts"]
        assert item["counts"]["failures"] == item["counts"]["errors"] == 0
        assert not measured[name]["failed_nodes"]
        manifests[name] = {"count": len(nodes), "nodes": nodes}
    assert manifests["baseline"] == manifests["restored"]
    for item in result["mutations"]:
        value, nodes = parse(directory / (item["name"] + suffix))
        assert item["exit_code"] == 1 and item["killed_by_owner"] and not item["counts"]["errors"]
        assert item["counts"] == value["counts"] and item["failed_nodes"] == value["failed_nodes"]
        assert nodes == manifests["baseline"]["nodes"]
        assert any(item["owner"] in node for node in item["failed_nodes"])
        assert all(value == result["code_sha256"][name] for name, value in item["restored_sha256"].items())
    for name, value in result["code_sha256"].items():
        assert digest(ROOT / name) == digest(source / name) == value, name
    assert all(not (ROOT / name).exists() and not (source / name).exists() for name in result["deleted_files"])
    return result, measured, manifests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--frontend", type=Path, required=True)
    parser.add_argument("--browser", type=Path, required=True)
    parser.add_argument("--interrupted", type=Path, action="append", default=[])
    args = parser.parse_args()
    backend, backend_measured, backend_nodes = validate_campaign(args.backend, "backend")
    frontend, frontend_measured, frontend_nodes = validate_campaign(args.frontend, "frontend")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert head == backend["head"] == frontend["head"]
    assert backend["code_sha256"] == frontend["code_sha256"]
    assert backend["deleted_files"] == frontend["deleted_files"]
    changed = set()
    for command in (["git", "diff", "--name-only", "-z"], ["git", "ls-files", "--others", "--exclude-standard", "-z"]):
        changed.update(name for name in subprocess.check_output(command, cwd=ROOT, text=True).split("\0")
                       if name and not name.startswith("docs/"))
    assert changed <= set(backend["code_sha256"]) | set(backend["deleted_files"])

    browser = json.loads((args.browser / "results.json").read_text())
    assert browser["complete"] and browser["provider_calls"] == 0 and not browser["production_app_started"]
    assert browser["head"] == head
    assert {"apps/arkscope-web/src/lifecycle/CurrentLifecycleView.tsx", "apps/arkscope-web/src/api.ts",
            "tests/fixtures/lifecycle_current_v1.json"} <= browser["source_sha256"].keys()
    for name, value in browser["source_sha256"].items():
        assert digest(ROOT / name) == value, name
        if not name.startswith("docs/"):
            assert digest(args.backend.parent / "source" / name) == value, name
            assert digest(args.frontend.parent / "source" / name) == value, name
    assert frontend["frontend_scope"] == "all_frontend_tests" and frontend["frontend_max_workers"] == 4
    expected_scenarios = {f"{locale}-{width}-{scenario}" for locale in ("en", "zh-Hant") for width in (1440, 390, 320)
                          for scenario in ("success", "response_lost", "scheduled", "changed", "malformed", "history")}
    assert len(browser["scenarios"]) == len(expected_scenarios)
    assert {row["name"] for row in browser["scenarios"]} == expected_scenarios
    screenshots = []
    for scenario in browser["scenarios"]:
        assert not scenario["unexpected_requests"] and not scenario["page_errors"]
        assert scenario["mocked_posts"] == int(scenario["name"].endswith(("-success", "-response_lost")))
        assert scenario["audit_reads"] == int(not scenario["name"].endswith("-malformed"))
        for phase, metrics in scenario["geometry"].items():
            assert not any(metrics.values())
            path = args.browser / f'{scenario["name"]}-{phase}.png'
            assert path.is_file()
            with Image.open(path) as picture:
                variance = max(ImageStat.Stat(picture).var)
            assert variance > 5 and variance == scenario["pixel_variance"][phase]
            screenshots.append(path)
    assert len(screenshots) == len(set(screenshots)) == 120

    payloads = {name + "-nodes.json": value for name, value in backend_nodes.items()}
    payloads["frontend-nodes.json"] = frontend_nodes["restored"]
    payloads["backend-log.json"] = {"sha256": digest(args.backend / "backend.log"),
                                    "output": (args.backend / "backend.log").read_text()}
    changes = {}
    for name in ("integration", "backend", "frontend"):
        old = set(json.loads((PRIOR / (name + "-nodes.json")).read_text())["nodes"])
        new = set(payloads[name + "-nodes.json"]["nodes"])
        added, removed = sorted(new - old), sorted(old - new)
        if name != "frontend":
            assert not removed
        if name == "backend":
            assert all(node.startswith(("tests.test_security_lifecycle_current::", "tests.test_security_lifecycle_current_routes::")) for node in added)
        changes[name] = {"added_count": len(added), "removed_count": len(removed), "added": added, "removed": removed}
    ledger = json.loads((PACKET / "test-retirement.json").read_text())
    assert set(changes["frontend"]["removed"]) == set(ledger["prior_nodes"])
    assert len(ledger["entries"]) == ledger["prior_node_count"] == len(ledger["prior_nodes"])
    assert {"src/lifecycle/LifecycleView.test.tsx::Lifecycle workflow " + entry["old_test"] for entry in ledger["entries"]} == set(ledger["prior_nodes"])
    for entry in ledger["entries"]:
        replacement = entry["replacement"]
        if replacement is None:
            assert entry["disposition"] == "retired_product_contract" and entry["rationale"]
        elif replacement.startswith("browser:"):
            assert browser["complete"]
        elif replacement.startswith("apps/arkscope-web/"):
            pattern = re.escape(replacement.removeprefix("apps/arkscope-web/")).replace("%s", ".+")
            assert any(re.fullmatch(pattern, node) for node in payloads["frontend-nodes.json"]["nodes"]), replacement
        else:
            file, owner = replacement.split("::")
            expected = file.removesuffix(".py").replace("/", ".") + "::" + owner
            assert expected in payloads["backend-nodes.json"]["nodes"], replacement

    previous_packets = {}
    for previous in (PRIOR, PACKET.parent / "2026-09-06-lifecycle-population-reconciliation", PACKET.parent / "2026-09-06-price-window-and-repair-ui"):
        manifest = json.loads((previous / "files.sha256.json").read_text())["files"]
        assert all(digest(previous / name) == value for name, value in manifest.items())
        previous_packets[previous.name] = {"seal_sha256": digest(previous / "files.sha256.json"), "files_verified": len(manifest)}
    schema_files = ("src/security_lifecycle_schema.py", "src/ticker_identity_schema.py", "src/sa_tracking_memberships.py")
    previous_sources = json.loads((PRIOR / "source-manifest.json").read_text())["files"]
    schema_checks = {}
    for name in schema_files:
        expected = previous_sources[name]
        assert digest(ROOT / name) == expected
        schema_checks[name] = expected
    for index, directory in enumerate(args.interrupted, 1):
        report = json.loads((directory / "report.json").read_text())
        assert report["complete"] is False
        for name, value in report["code_sha256"].items():
            assert digest(directory.parent / "source" / name) == value
        payloads[f"interrupted-campaign-{index}.json"] = report

    env = {key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR"}}
    for name, script in (("typecheck", "typecheck"), ("build", "build"), ("i18n", "check:i18n-literals")):
        command = ["npm", "run", script]
        result = subprocess.run(command, cwd=ROOT / "apps/arkscope-web", env=env, capture_output=True, text=True, timeout=180)
        assert result.returncode == 0, result.stdout + result.stderr
        payloads[name + ".json"] = {"command": command, "exit_code": result.returncode, "output": result.stdout + result.stderr}
    subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=True)
    assert all(digest(ROOT / name) == value for name, value in backend["code_sha256"].items())

    payloads["verification.json"] = {
        "backend": backend_measured, "frontend": frontend_measured,
        "mutations": {"backend": len(backend["mutations"]), "frontend": len(frontend["mutations"])},
        "node_changes": {name: {key: row[key] for key in ("added_count", "removed_count")} for name, row in changes.items()},
        "browser_scenarios": len(browser["scenarios"]), "browser_screenshots": len(screenshots),
        "browser_source_files_verified": len(browser["source_sha256"]),
        "frontend_max_workers": frontend["frontend_max_workers"],
        "changed_product_test_files_verified": len(changed), "frozen_source_files_verified": len(backend["code_sha256"]),
        "prior_packets": previous_packets, "schema_files_unchanged": schema_checks,
        "provider_calls": 0, "production_reads": False, "production_writes": False, "migration": False,
        "app_restart": False, "commit": False, "merge": False, "push": False,
        "complete_slice": "current_review_ui_api_research", "whole_workflow_complete": False,
        "remaining": ["validated_web_finding_and_confirmation", "bounded_web_adapter", "release_cutover"],
    }
    payloads["node-changes.json"] = changes
    payloads["focus-files.json"] = {"files": backend["focus_files"]}
    payloads["integration-files.json"] = {"files": backend["integration_files"]}
    payloads["mutation-results.json"] = {kind: {key: value[key] for key in ("baseline", "mutations", "restored")}
                                          for kind, value in (("backend", backend), ("frontend", frontend))}
    payloads["browser-results.json"] = browser
    sources = set(backend["code_sha256"]) | set(schema_files)
    sources.update({"docs/design/PROJECT_PRIORITY_MAP.md", "docs/design/ARKSCOPE_TOOL_CATALOG.md",
                    "docs/superpowers/plans/2026-09-05-lifecycle-tracking-first-implementation.md",
                    "docs/superpowers/specs/2026-09-05-lifecycle-tracking-status-and-web-supplement-design.md",
                    "docs/superpowers/plans/2026-09-05-lifecycle-terminal-membership-completion.md"})
    sources.update(str(path.relative_to(ROOT)) for path in (PACKET / "scripts").iterdir() if path.is_file())
    payloads["source-manifest.json"] = {"base_commit": head, "files": {name: digest(ROOT / name) for name in sorted(sources)},
                                        "deleted_files": backend["deleted_files"]}
    assert not (PACKET / "files.sha256.json").exists()
    assert not any((PACKET / name).exists() for name in payloads)
    assert not (PACKET / "screenshots").exists()
    for name, value in payloads.items():
        with (PACKET / name).open("x") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
    (PACKET / "screenshots").mkdir()
    for path in screenshots:
        shutil.copy2(path, PACKET / "screenshots" / path.name)
    files = {str(path.relative_to(PACKET)): digest(path) for path in sorted(PACKET.rglob("*"))
             if path.is_file() and "__pycache__" not in path.parts and path.name != "files.sha256.json"}
    with (PACKET / "files.sha256.json").open("x") as stream:
        json.dump({"algorithm": "sha256", "file_count": len(files), "files": files}, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"backend": backend_measured["backend"]["counts"], "frontend": frontend_measured["restored"]["counts"],
                      "browser_scenarios": len(browser["scenarios"]), "files": len(files),
                      "seal_sha256": digest(PACKET / "files.sha256.json")}), flush=True)


if __name__ == "__main__":
    main()
