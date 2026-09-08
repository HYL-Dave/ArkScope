"""Check measured routing-foundation evidence, then optionally publish a create-only seal."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

from PIL import Image, ImageStat

from verify_mutations import MUTATIONS as BACKEND_MUTATIONS
from verify_frontend_mutations import MUTATIONS as FRONTEND_MUTATIONS

HERE = Path(__file__).resolve().parent
PACKET = HERE.parent
ROOT = HERE.parents[4]
PRIOR = PACKET.with_name("2026-09-07-lifecycle-web-instrument-scoping")
PRIOR_SHA = "6129d26288cba6089c2040c35a5b9c273da8de4b239c941683d19e8f3c90e257"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_packet(directory, expected=None):
    manifest = directory / "files.sha256.json"
    if expected is not None:
        assert sha(manifest) == expected
    files = json.loads(manifest.read_text())["files"]
    assert all(sha(directory / name) == digest for name, digest in files.items())
    return {"sha256": sha(manifest), "files_verified": len(files)}


def backend(path):
    root = ET.parse(path).getroot()
    cases = list(root.iter("testcase"))
    nodes = sorted(row.get("classname", "") + "::" + row.get("name", "") for row in cases)
    counts = {key: sum(int(suite.get(key, "0")) for suite in root.iter("testsuite"))
              for key in ("tests", "failures", "errors", "skipped")}
    failures = [row.get("name", "") for row in cases if row.find("failure") is not None]
    assert counts["tests"] == len(nodes) == len(set(nodes))
    return {"counts": counts, "failed": failures, "nodes": nodes}


def frontend(path):
    data = json.loads(path.read_text())
    nodes, failures = [], []
    for suite in data["testResults"]:
        parts = Path(suite["name"]).parts
        index = parts.index("apps")
        assert parts[index + 1] == "arkscope-web"
        filename = Path(*parts[index + 2:]).as_posix()
        for case in suite["assertionResults"]:
            nodes.append(filename + "::" + case["fullName"])
            if case["status"] == "failed":
                failures.append(case["fullName"])
    assert len(nodes) == len(set(nodes)) == data["numTotalTests"]
    return {"counts": {"tests": len(nodes), "failures": data["numFailedTests"],
                       "skipped": data["numPendingTests"], "errors": data.get("numRuntimeErrorTestSuites", 0)},
            "failed": failures, "nodes": sorted(nodes)}


def green(report):
    assert report["counts"]["failures"] == report["counts"]["errors"] == 0
    assert not report["failed"]


def mutations(directory, expected, parse, suffix):
    results = json.loads((directory / "results.json").read_text())
    assert [(row["name"], row["owner"]) for row in results] == [(row[0], row[-1]) for row in expected]
    baseline = parse(directory / ("baseline" + suffix))
    restored = parse(directory / ("restored" + suffix))
    green(baseline)
    green(restored)
    assert baseline["nodes"] == restored["nodes"]
    for row in results:
        report = parse(directory / (row["name"] + suffix))
        assert row["exit_code"] == 1 and row["owned"] and report["counts"]["errors"] == 0
        assert report["nodes"] == baseline["nodes"]
        assert report["failed"] == row["failed"]
        assert any(row["owner"] in name for name in report["failed"])
    source = json.loads((directory / "sources.json").read_text())
    assert all(sha(ROOT / name) == digest for name, digest in source.items())
    return {"owned": len(results), "focus_nodes": len(baseline["nodes"]),
            "restored": True, "worktree_unchanged": True}, source


def new_json(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def secret_scan(files):
    path = PACKET.with_name("2026-09-07-lifecycle-web-sonnet-canary") / "scan_packet.py"
    spec = importlib.util.spec_from_file_location("reviewed_packet_scanner", path)
    scanner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scanner)
    result = scanner.scan_files(files)
    # These campaign filenames differ from the old scanner's backend.xml name.
    # Admit only the exact existing synthetic token and its named redaction test.
    for finding in result["findings"]:
        fixture = scanner.SYNTHETIC_TEST_FIXTURES.get(finding["sha256"])
        source = files[finding["file"]]
        if not fixture or fixture[0] != finding["kind"] or source.suffix not in {".xml", ".json"}:
            continue
        lines = source.read_bytes().splitlines()
        if any(b"test_redact_scrubs_token_shapes" in line and any(
            hashlib.sha256(match.group()).hexdigest() == finding["sha256"]
            for match in scanner.PATTERNS[finding["kind"]].finditer(line)) for line in lines):
            finding["synthetic_named_test_fixture"] = True
            finding["fixture_constant"] = fixture[1]
    result["unexpected"] = sum(not row["synthetic_named_test_fixture"] for row in result["findings"])
    assert result["unexpected"] == 0, result
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seal", action="store_true")
    args = parser.parse_args()
    prior = checked_packet(PRIOR, PRIOR_SHA)
    previous_frontend = PACKET.with_name("2026-09-07-lifecycle-web-usage")
    checked_packet(previous_frontend)
    back = backend(PACKET / "backend-suite-r2.xml")
    front = frontend(PACKET / "frontend-suite-r7.json")
    green(back)
    green(front)
    back_mutants, back_sources = mutations(PACKET / "mutations-r1", BACKEND_MUTATIONS, backend, ".xml")
    front_mutants, front_sources = mutations(PACKET / "frontend-mutations-r3", FRONTEND_MUTATIONS, frontend, ".json")
    prior_sources = json.loads((PRIOR / "admission/source-manifest.json").read_text())
    old_code = {name: value for name, value in prior_sources["files"].items() if not name.startswith("docs/")}
    code = {name: sha(ROOT / name) for name in old_code}
    code.update(back_sources)
    code.update(front_sources)
    added = sorted(code.keys() - old_code.keys())
    changed = sorted(name for name in old_code if code[name] != old_code[name])
    assert added == ["tests/test_lifecycle_investigation_routing.py", "tests/test_lifecycle_investigation_task_test.py"]
    assert len(changed) == 25
    assert all(not (ROOT / name).exists() for name in prior_sources["deleted_files"])
    schemas = ("src/security_lifecycle_schema.py", "src/ticker_identity_schema.py",
               "src/lifecycle_web_schema.py", "src/sa_tracking_memberships.py")
    assert all(code[name] == old_code[name] for name in schemas)
    status_docs = {name: sha(ROOT / name) for name in (
        "docs/design/PROJECT_PRIORITY_MAP.md",
        "docs/superpowers/plans/2026-09-05-lifecycle-tracking-first-implementation.md",
        "docs/superpowers/plans/2026-09-07-lifecycle-web-bounded-followup.md",
    )}

    ledger = {}
    for kind, current, previous, expected in (
        ("backend", back, PRIOR / "admission/backend-nodes.json", 50),
        ("frontend", front, previous_frontend / "frontend-nodes.json", 6),
    ):
        before = set(json.loads(previous.read_text())["nodes"])
        after = set(current["nodes"])
        assert not before - after and len(after - before) == expected
        ledger[kind] = {"before": len(before), "after": len(after), "added": sorted(after - before), "removed": []}

    browser = json.loads((PACKET / "browser-r5/results.json").read_text())
    assert browser["actual_provider_calls"] == 0 and not browser["production_app_started"]
    assert len(browser["scenarios"]) == 12
    assert {(row["locale"], row["width"], row["auth"]) for row in browser["scenarios"]} == {
        (locale, width, auth) for locale in ("en", "zh-Hant") for width in (1440, 390, 320) for auth in ("api_key", "oauth")}
    for row in browser["scenarios"]:
        assert all(not any(metrics.values()) for metrics in row["metrics"])
        assert len(row["synthetic_model_calls"]) == 2
    shots = list((PACKET / "browser-r5").glob("*.png"))
    assert len(shots) == 24
    for path in shots:
        with Image.open(path) as picture:
            assert max(ImageStat.Stat(picture).var) > 5
    report = {"kind": "independent_lifecycle_routing_foundation_offline_only", "prior": prior,
        "backend": back["counts"], "frontend": front["counts"],
        "backend_mutations": back_mutants, "frontend_mutations": front_mutants,
        "browser": {"scenarios": 12, "screenshots": 24, "actual_provider_calls": 0},
        "changed": changed, "added": added, "schemas_unchanged": list(schemas),
        "status_documents_sha256": status_docs,
        "full_agent_verified": False, "independent_target_launch_delivered": False,
        "local_news_delivered": False, "legacy_retirement_delivered": False,
        "production_read_write_provider_restart_merge_push": False,
        "test_environment": {"backend_final_tmpdir": "/dev/shm", "frontend_final_tmpdir": "/dev/shm",
                             "frontend_max_workers": 4, "assertions_and_timeouts_not_relaxed": True}}
    files = {str(path.relative_to(PACKET)): path for path in PACKET.rglob("*")
             if path.is_file() and "__pycache__" not in path.parts}
    files.update({"source/" + name: ROOT / name for name in changed + added})
    scan = secret_scan(files)
    if args.seal:
        new_json(PACKET / "secret-shape-scan.json", scan)
        new_json(PACKET / "verification.json", report)
        new_json(PACKET / "node-changes.json", ledger)
        new_json(PACKET / "source-manifest.json", {"head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "files": {**code, **status_docs},
            "deleted_files": prior_sources["deleted_files"]})
        for name in [*changed, *added, *status_docs]:
            destination = PACKET / "source" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            with (ROOT / name).open("rb") as incoming, destination.open("xb") as outgoing:
                shutil.copyfileobj(incoming, outgoing)
        new_json(PACKET / "files.sha256.json", {"files": {str(path.relative_to(PACKET)): sha(path)
            for path in sorted(PACKET.rglob("*")) if path.is_file() and "__pycache__" not in path.parts}})
        report["seal_sha256"] = sha(PACKET / "files.sha256.json")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
