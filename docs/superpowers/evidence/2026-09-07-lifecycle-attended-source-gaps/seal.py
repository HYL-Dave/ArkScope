"""Create-only source-bound admission for the approved attended-gap contract."""

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from PIL import Image, ImageStat
import verify as configuration


PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[3]
PRIOR = PACKET.parent / "2026-09-07-lifecycle-source-priority-capacity"
RUNTIME = PACKET.parent / "2026-09-07-lifecycle-web-runtime"
CANARY = PACKET.parent / "2026-09-07-lifecycle-web-sonnet-canary"
sys.modules["verify"] = configuration.verifier
sealer = configuration.verifier.module("gap_sealer", RUNTIME / "scripts/seal.py")
sys.modules["verify"] = configuration
sealer.ROOT = ROOT
sealer.MUTATIONS = configuration.verifier.MUTATIONS
scanner = configuration.verifier.module("gap_scanner", CANARY / "scan_packet.py")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write_new(name, value):
    path = PACKET / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def replacements(node):
    stem, bracket, parameters = node.partition("[")
    if "::test_unread_candidate_is_visible_incompleteness_not_absence" in stem:
        return "approved_unread_supplement_contract_change", [node.replace(
            "test_unread_candidate_is_visible_incompleteness_not_absence",
            "test_unread_supplement_does_not_block_an_otherwise_supported_attended_finding")]
    if "::test_incomplete_web_finding_is_readable_but_has_no_action" in stem:
        assert bracket
        return "preserved_material_blockers_with_and_without_read_gaps", [stem + "[" + str(count) + "-" + parameters for count in (0, 1)]
    if "::test_research_and_current_detail_share_readonly_web_findings_for_every_auth" in stem:
        assert bracket
        return "preserved_shared_projection_with_and_without_read_gaps", [stem + "[" + str(flag) + "-" + parameters for flag in (False, True)]
    if "::test_source_read_failure_remains_visible_and_never_retries" in stem:
        assert not bracket
        return "expanded_pipeline_owner_to_all_four_auth_combinations", [stem + "[" + auth + "]" for auth in (
            "openai-api_key", "openai-chatgpt_oauth", "anthropic-api_key", "anthropic-claude_code_oauth")]
    raise AssertionError("unexplained_removed_node:" + node)


def node_changes(old, current):
    old, current = set(old), set(current)
    mapped = {}
    for node in sorted(old - current):
        reason, targets = replacements(node)
        assert set(targets) <= current, (node, targets)
        mapped[node] = {"reason": reason, "current_owners": targets}
    return {"before": len(old), "after": len(current), "net_added_count": len(current) - len(old),
            "added": sorted(current - old), "replaced": mapped, "unexplained_removed": []}


def historical_frontend(path):
    result = read(path)
    items = [(suite["name"] + "::" + test["fullName"], test["status"])
             for suite in result["testResults"] for test in suite["assertionResults"]]
    assert len(items) == result["numTotalTests"]
    assert sum(status == "failed" for _, status in items) == result["numFailedTests"]
    return {"reported_success": result["success"], "tests": len(items),
            "failures": result["numFailedTests"], "pending": result["numPendingTests"],
            "duplicate_node_count": len(items) - len({name for name, _ in items}),
            "classification": "historical_only_never_final_admission"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("backend", "frontend", "browser", "iterations"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--historical-campaign", type=Path, action="append", default=[])
    args = parser.parse_args()
    assert not (PACKET / "files.sha256.json").exists()
    back, back_measured, back_nodes = sealer.validate_campaign(args.backend, "backend")
    front, front_measured, front_nodes = sealer.validate_campaign(args.frontend, "frontend")
    variants = {"gap_extra_internal_fields_accepted": "internal field", "gap_raw_error_reason_accepted": "raw error",
                "gap_unsafe_url_accepted": "javascript URL"}
    for item in front["mutations"]:
        if item["name"] in variants:
            expected = "Lifecycle Web DTOs rejects malformed gap metadata rather than hiding it: " + repr(variants[item["name"]])
            assert expected in item["failed_nodes"]
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert head == back["head"] == front["head"]
    assert back["source_sha256"] == front["source_sha256"] and back["deleted_files"] == front["deleted_files"]
    changed = set()
    for command in (["git", "diff", "--name-only", "-z"], ["git", "ls-files", "--others", "--exclude-standard", "-z"]):
        changed.update(name for name in subprocess.check_output(command, cwd=ROOT, text=True).split("\0")
                       if name and not name.startswith("docs/"))
    assert changed <= back["source_sha256"].keys() | set(back["deleted_files"])
    prior_packets = {}
    for previous in (PRIOR, CANARY, RUNTIME, PACKET.parent / "2026-09-07-lifecycle-source-context"):
        files = read(previous / "files.sha256.json")["files"]
        assert all(sha(previous / name) == expected for name, expected in files.items())
        prior_packets[previous.name] = {"seal_sha256": sha(previous / "files.sha256.json"), "files_verified": len(files)}
    old = {name: value for name, value in read(PRIOR / "source-manifest.json")["files"].items() if not name.startswith("docs/")}
    assert old.keys() <= back["source_sha256"].keys()
    schemas = {name: old[name] for name in ("src/security_lifecycle_schema.py", "src/lifecycle_web_schema.py",
                                           "src/ticker_identity_schema.py", "src/sa_tracking_memberships.py")}
    assert all(sha(ROOT / name) == expected for name, expected in schemas.items())
    payloads = {name + "-nodes.json": value for name, value in back_nodes.items()}
    payloads["frontend-nodes.json"] = front_nodes["restored"]
    changes = {kind: node_changes(read(PRIOR / (kind + "-nodes.json"))["nodes"], payloads[kind + "-nodes.json"]["nodes"])
               for kind in ("baseline", "restored", "integration", "backend", "frontend")}
    browser = read(args.browser / "results.json")
    assert browser["provider_calls"] == 0 and not browser["production_app_started"]
    assert len(browser["cases"]) == 24
    assert {(row["locale"], row["width"], row["scenario"]) for row in browser["cases"]} == {
        (locale, width, scenario) for locale in ("en", "zh-Hant") for width in (1440, 390, 320)
        for scenario in ("removal", "rename", "blocked", "legacy")}
    assert all(sha(ROOT / name) == expected for name, expected in browser["source_sha256"].items())
    assert all(back["source_sha256"][name] == expected for name, expected in browser["source_sha256"].items()
               if not name.startswith("docs/"))
    screenshots = []
    for row in browser["cases"]:
        assert not row["page_errors"] and row["provider_calls"] == 0
        assert row["fixture_confirmations"] == (0 if row["scenario"] == "blocked" else 1)
        for phase, metrics in row["geometry"].items():
            assert not any(metrics.values())
            path = args.browser / f'{row["locale"]}-{row["width"]}-{row["scenario"]}-{phase}.png'
            with Image.open(path) as picture:
                variance = max(ImageStat.Stat(picture).var)
            assert variance > 5 and variance == row["pixel_variance"][phase]
            screenshots.append(path)
    assert len(screenshots) == len(set(screenshots)) == 42
    assert set(screenshots) == set(args.browser.glob("*.png"))
    iterations, copies = {}, {}
    for path in sorted(args.iterations.iterdir()):
        if not path.is_file() or path.suffix not in {".json", ".xml", ".log"}:
            continue
        if path.suffix == ".xml":
            iterations[path.name], _ = sealer.parsers.backend_report(path)
        elif path.suffix == ".json":
            iterations[path.name] = historical_frontend(path)
        copies["historical-iterations/" + path.name] = path
    historical = {}
    for directory in args.historical_campaign:
        report = read(directory / "report.json")
        assert all(sha(directory.parent / "source" / name) == expected for name, expected in report["source_sha256"].items())
        historical[directory.parent.name] = {"scope": "before_nested_fixture_repair_not_final_admission", "report": report}
        for path in directory.iterdir():
            if path.is_file() and path.suffix in {".json", ".xml", ".log"}:
                copies[f"historical-campaigns/{directory.parent.name}/{path.name}"] = path
    payloads.update({
        "node-changes.json": changes, "browser-results.json": browser,
        "historical-campaigns.json": historical,
        "focus-files.json": {"files": back["focus_files"]}, "integration-files.json": {"files": back["integration_files"]},
        "incremental-results.json": {"scope": "historical_red_green_and_preliminary_suites_not_final_admission", "files": iterations},
        "source-changes.json": {"prior_manifest_sha256": sha(PRIOR / "source-manifest.json"),
            "changed": {name: {"before": value, "after": back["source_sha256"][name]} for name, value in old.items()
                        if value != back["source_sha256"][name]},
            "added": {name: value for name, value in back["source_sha256"].items() if name not in old}},
        "verification.json": {"backend": back_measured, "frontend": front_measured,
            "mutations": {"backend": len(back["mutations"]), "frontend": len(front["mutations"])},
            "browser_scenarios": 24, "browser_screenshots": 42, "prior_packets": prior_packets,
            "unchanged_schemas": schemas, "product_decision": "attended_confirmation_with_disclosed_unread_supplements",
            "provider_calls": 0, "production_reads": False, "production_writes": False,
            "migration": False, "app_restart": False, "commit": False, "merge": False, "push": False,
            "capacity_measurement_rerun": False, "whole_workflow_complete": False,
            "remaining": ["maximum_source_attended_write_concurrency_measurement", "model_usage_calibration",
                          "authorized_fresh_live_canary", "authorized_journal_installation_and_population_cutover", "merge_and_handtest"]},
    })
    env = {key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR"}}
    for name in ("typecheck", "build", "check:i18n-literals"):
        command = ["npm", "run", name]
        result = subprocess.run(command, cwd=ROOT / "apps/arkscope-web", env=env, capture_output=True, text=True, timeout=180)
        assert result.returncode == 0, result.stdout + result.stderr
        payloads[name.replace(":", "-") + ".json"] = {"command": command, "exit_code": result.returncode, "output": result.stdout + result.stderr}
    subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=True)
    docs = ["docs/design/PROJECT_PRIORITY_MAP.md", "docs/superpowers/plans/2026-09-06-lifecycle-web-auth-adapters.md",
            "docs/superpowers/specs/2026-09-05-lifecycle-tracking-status-and-web-supplement-design.md"]
    docs.extend(str(path.relative_to(ROOT)) for path in PACKET.glob("*.py"))
    payloads["source-manifest.json"] = {"base_commit": head, "files": {
        **back["source_sha256"], **{name: sha(ROOT / name) for name in docs}}, "deleted_files": back["deleted_files"]}
    fixture_names = {value[1] for value in scanner.SYNTHETIC_TEST_FIXTURES.values()}
    literals = {target.id: ast.literal_eval(node.value) for node in ast.parse((ROOT / "tests/test_probe_harness.py").read_text()).body
                if isinstance(node, ast.Assign) for target in node.targets if isinstance(target, ast.Name) and target.id in fixture_names}
    assert {hashlib.sha256(value.encode()).hexdigest(): key for key, value in literals.items()} == {
        key: value[1] for key, value in scanner.SYNTHETIC_TEST_FIXTURES.items()}
    for kind, directory in (("backend-results", args.backend), ("frontend-results", args.frontend)):
        for path in directory.iterdir():
            if path.is_file() and path.suffix in {".json", ".xml", ".log"}:
                copies[f"{kind}/{path.name}"] = path
    assert scanner.scan_files(copies)["unexpected"] == 0
    assert not any((PACKET / name).exists() for name in payloads.keys() | copies.keys())
    for name, value in payloads.items():
        write_new(name, value)
    for name, path in copies.items():
        target = PACKET / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with path.open("rb") as source, target.open("xb") as destination:
            shutil.copyfileobj(source, destination)
    (PACKET / "screenshots").mkdir()
    for path in screenshots:
        shutil.copy2(path, PACKET / "screenshots" / path.name)
    scan = scanner.scan_files({str(path.relative_to(PACKET)): path for path in PACKET.rglob("*")
                               if path.is_file() and "__pycache__" not in path.parts})
    assert scan["unexpected"] == 0
    write_new("secret-shape-scan.json", scan)
    assert all(sha(ROOT / name) == expected for name, expected in back["source_sha256"].items())
    write_new("files.sha256.json", {"files": {str(path.relative_to(PACKET)): sha(path) for path in sorted(PACKET.rglob("*"))
                                              if path.is_file() and "__pycache__" not in path.parts}})
    print(json.dumps({"seal_sha256": sha(PACKET / "files.sha256.json"), "source_files": len(back["source_sha256"]),
                      "verification": payloads["verification.json"]}), flush=True)


if __name__ == "__main__":
    main()
