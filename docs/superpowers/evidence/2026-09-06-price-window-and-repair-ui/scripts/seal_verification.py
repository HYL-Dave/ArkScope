"""Seal existing offline test results; no application or provider execution."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

PACKET = Path(__file__).resolve().parent.parent
ROOT = PACKET.parents[3]
PRIOR = PACKET.parent / "2026-09-06-recent-price-repair-live"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def xml_result(path):
    root = ET.parse(path).getroot()
    cases = list(root.iter("testcase"))
    counts = {key: sum(int(row.get(key, "0")) for row in root.iter("testsuite"))
              for key in ("tests", "failures", "errors", "skipped")}
    nodes = sorted(row.get("classname", "") + "::" + row.get("name", "") for row in cases)
    failed = [row.get("classname", "") + "::" + row.get("name", "") for row in cases
              if row.find("failure") is not None or row.find("error") is not None]
    return {"report": path.name, "sha256": digest(path), "counts": counts, "failed_nodes": failed}, nodes


def ui_result(path):
    value = json.loads(path.read_text())
    tests = [test for suite in value["testResults"] for test in suite["assertionResults"]]
    nodes = sorted(Path(suite["name"]).relative_to(ROOT / "apps/arkscope-web").as_posix() + "::" + test["fullName"]
                   for suite in value["testResults"] for test in suite["assertionResults"])
    return {"report": path.name, "sha256": digest(path), "counts": {
        "tests": value["numTotalTests"], "failures": value["numFailedTests"], "skipped": value["numPendingTests"]},
        "failed_nodes": [test["fullName"] for test in tests if test["status"] == "failed"]}, nodes


def campaign(path, kind, count):
    value = json.loads(path.read_text())
    assert value["kind"] == kind and len(value["mutations"]) == count
    assert value["baseline"]["exit_code"] == value["restored"]["exit_code"] == 0
    assert value["baseline"]["counts"] == value["restored"]["counts"]
    for item in value["mutations"]:
        assert item["killed_by_owner"] and item["exit_code"] == 1 and not item["counts"]["errors"]
        assert item["counts"]["tests"] == value["baseline"]["counts"]["tests"]
        assert any(item["owner"] in node for node in item["failed_nodes"])
        assert all(digest(ROOT / name) == expected for name, expected in item["restored_sha256"].items())
    return value


def check(command, cwd):
    env = {key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR"}}
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=180)
    output = result.stdout + result.stderr
    record = {"command": command, "cwd": str(cwd.relative_to(ROOT)) or ".", "exit_code": result.returncode,
              "output_sha256": hashlib.sha256(output.encode()).hexdigest(), "output": output}
    if result.returncode != 0:
        write_json(PACKET / "check-failure.json", record)
        raise AssertionError(output)
    return record


def main():
    parser = argparse.ArgumentParser()
    for name in ("backend", "integration", "frontend", "backend-mutations", "frontend-mutations"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    backend, backend_nodes = xml_result(args.backend)
    integration, integration_nodes = xml_result(args.integration)
    frontend, frontend_nodes = ui_result(args.frontend)
    for result, nodes in ((backend, backend_nodes), (integration, integration_nodes), (frontend, frontend_nodes)):
        assert not result["failed_nodes"] and not result["counts"].get("errors") and not result["counts"]["failures"]
        assert len(nodes) == result["counts"]["tests"] and len(nodes) == len(set(nodes))
    mutations = {"backend": campaign(args.backend_mutations, "backend", 9),
                 "frontend": campaign(args.frontend_mutations, "frontend", 7)}
    browser = json.loads((PACKET / "browser/results.json").read_text())
    assert len(browser["scenarios"]) == 18
    assert len(list((PACKET / "browser").glob("*.png"))) == 30
    for item in browser["scenarios"]:
        assert not item["unexpected_requests"] and not item["page_errors"] and not any(item["geometry"].values())
    checks = [check(["npm", "run", name], ROOT / "apps/arkscope-web")
              for name in ("typecheck", "build", "check:i18n-literals")]
    checks.append(check(["git", "diff", "--check"], ROOT))
    prior_packets = {}
    # Earlier policy source fingerprints are historical, not packet seals.
    for name in ("2026-09-05-lifecycle-tracking-first-disposition",
                 "2026-09-05-lifecycle-tracking-first-readonly", "2026-09-06-lifecycle-target-scoped-disposition",
                 "2026-09-06-recent-price-repair", "2026-09-06-recent-price-repair-live"):
        directory = PACKET.parent / name
        seal = directory / "files.sha256.json"
        values = json.loads(seal.read_text())["files"]
        assert all(digest(directory / relative) == expected for relative, expected in values.items()), name
        prior_packets[name] = {"seal_sha256": digest(seal), "files_verified": len(values)}
    red = []
    for name in ("arkscope-price-window-red.xml", "arkscope-price-status-red.xml",
                 "arkscope-price-status-routes-red-clean.xml", "arkscope-price-window-backend-tests.xml",
                 "arkscope-price-id-read-red.xml"):
        value, _ = xml_result(Path("/tmp") / name)
        red.append(value)
    for name in ("arkscope-price-window-ui-red.json", "arkscope-price-status-ui-red.json", "arkscope-price-activity-red.json",
                 "arkscope-price-id-read-ui-red.json"):
        value, _ = ui_result(Path("/tmp") / name)
        red.append(value)
    write_json(PACKET / "mutation-results.json", mutations)
    for name, nodes in (("backend", backend_nodes), ("integration", integration_nodes), ("frontend", frontend_nodes)):
        write_json(PACKET / (name + "-nodes.json"), {"count": len(nodes), "nodes": nodes})
    base = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    write_json(PACKET / "verification.json", {"base_commit": base, "backend_command": "python -m pytest -q tests",
        "backend": backend, "integration": integration, "frontend": frontend, "checks": checks, "red": red,
        "mutation_count": 16, "browser_scenarios": 18, "browser_screenshots": 30,
        "provider_calls": 0, "production_reads": False, "production_writes": False,
        "migration": False, "app_restart": False, "commit": False, "merge": False, "push": False,
        "prior_packets": prior_packets})
    sources = set(json.loads((PRIOR / "source-manifest.json").read_text())["files"])
    sources.update(subprocess.check_output(["git", "diff", "--name-only"], cwd=ROOT, text=True).splitlines())
    untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT, text=True).splitlines()
    sources.update(name for name in untracked if name.startswith(("src/", "tests/", "apps/")))
    sources.update(str(path.relative_to(ROOT)) for path in (PACKET / "scripts").iterdir() if path.is_file())
    write_json(PACKET / "source-manifest.json", {"algorithm": "sha256", "base_commit": base,
        "source_file_count": len(sources), "files": {name: digest(ROOT / name) for name in sorted(sources)}})
    files = {str(path.relative_to(PACKET)): digest(path) for path in sorted(PACKET.rglob("*"))
             if path.is_file() and "__pycache__" not in path.parts and path.name != "files.sha256.json"}
    write_json(PACKET / "files.sha256.json", {"algorithm": "sha256", "file_count": len(files), "files": files})
    print(json.dumps({"backend": backend["counts"], "integration": integration["counts"], "frontend": frontend["counts"],
                      "source_files": len(sources), "packet_files": len(files), "seal_sha256": digest(PACKET / "files.sha256.json")}))


if __name__ == "__main__":
    main()
