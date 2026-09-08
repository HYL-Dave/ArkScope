"""Create-only usage evidence; all counts, owners and source hashes re-derived."""

import argparse
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
PRIOR = PACKET.parent / "2026-09-07-lifecycle-attended-write-concurrency"
CANARY = PACKET.parent / "2026-09-07-lifecycle-web-usage-canary"
sys.modules["verify"] = configuration.verifier
sealer = configuration.verifier.module("usage_result_sealer", PACKET.parent / "2026-09-07-lifecycle-web-runtime/scripts/seal.py")
sys.modules["verify"] = configuration
sealer.ROOT = ROOT
sealer.MUTATIONS = configuration.verifier.MUTATIONS
previous = configuration.verifier.module("usage_capacity_sealer", PRIOR / "seal.py")
scanner = configuration.verifier.module("usage_secret_scanner", PACKET.parent / "2026-09-07-lifecycle-web-sonnet-canary/scan_packet.py")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write_new(name, value):
    target = PACKET / name
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def browser_result(directory, source):
    value = read(directory / "results.json")
    assert value["provider_calls"] == 0 and not value["production_app_started"]
    assert all(sha(ROOT / name) == expected for name, expected in value["source_sha256"].items())
    assert all(source[name] == expected for name, expected in value["source_sha256"].items() if not name.startswith("docs/"))
    scenarios = [(name, "anthropic", "claude_code_oauth") for name in
                 ("complete", "source_failed", "partial", "unknown", "legacy", "large_counters")]
    scenarios += [("complete", "openai", "api_key"), ("complete", "openai", "chatgpt_oauth"), ("complete", "anthropic", "api_key")]
    names = {f"{locale}-{width}-{scenario}-{provider}-{auth}" for locale in ("en", "zh-Hant")
             for width in (1440, 390, 320) for scenario, provider, auth in scenarios}
    observed, pictures = set(), {}
    for row in value["cases"]:
        name = "-".join(str(row[key]) for key in ("locale", "width", "scenario", "provider", "auth_mode"))
        assert name not in observed
        observed.add(name)
        assert row["provider_calls"] == row["fixture_writes"] == 0 and not row["page_errors"]
        assert set(row["geometry"]) == set(row["pixel_variance"]) == {"collapsed", "expanded"}
        for state, geometry in row["geometry"].items():
            assert not any(geometry.values())
            path = directory / f"{name}-{state}.png"
            with Image.open(path) as picture:
                variance = max(ImageStat.Stat(picture).var)
            assert variance == row["pixel_variance"][state] and variance > 5
            pictures["browser/" + path.name] = path
    assert observed == names and len(names) == len(value["cases"]) == 54
    assert set(pictures.values()) == set(directory.glob("*.png")) and len(pictures) == 108
    return {"cases": 54, "screenshots": 108, "nonblank_and_geometry_verified": True}, pictures


def harness_result(directory):
    value = read(directory / "report.json")
    assert value["complete"] and value["provider_calls"] == 0
    assert not value["production_reads"] and not value["production_writes"]
    assert all(sha(ROOT / name) == expected for name, expected in value["source_sha256"].items())
    module = configuration.verifier.module("usage_canary_admission", CANARY / "verify_harness.py")
    assert [item["name"] for item in value["mutations"]] == [item[0] for item in module.MUTATIONS]
    for name in ("baseline", "restored"):
        result, nodes = sealer.parsers.backend_report(directory / (name + ".xml"))
        assert result["counts"] == {"tests": 9, "failures": 0, "errors": 0, "skipped": 0}
        assert value[name]["exit_code"] == 0 and not value[name]["failed_nodes"]
        assert len(nodes) == len(value[name]["nodes"]) == 9
    assert value["baseline"] == value["restored"]
    for item, (_, owner, _, _) in zip(value["mutations"], module.MUTATIONS):
        result, nodes = sealer.parsers.backend_report(directory / (item["name"] + ".xml"))
        assert result["counts"]["tests"] == len(nodes) == 9 and result["counts"]["errors"] == 0
        assert item["exit_code"] == 1 and result["counts"]["failures"] > 0
        assert item["nodes"] == value["baseline"]["nodes"] and item["owner"] == owner
        assert any(owner in node for node in result["failed_nodes"])
    return {"rehearsal_passed": 9, "mutations": 3, "live_executed": False, "production_reads": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", required=True, type=Path)
    parser.add_argument("--frontend", required=True, type=Path)
    parser.add_argument("--browser", required=True, type=Path)
    parser.add_argument("--harness", required=True, type=Path)
    parser.add_argument("--measurement", required=True, type=Path, action="append")
    parser.add_argument("--historical-campaign", type=Path, action="append", default=[])
    parser.add_argument("--incremental", type=Path, action="append", default=[])
    parser.add_argument("--frontend-incremental", type=Path, action="append", default=[])
    args = parser.parse_args()
    assert not (PACKET / "files.sha256.json").exists()
    back, back_measured, back_nodes = sealer.validate_campaign(args.backend, "backend")
    front, front_measured, front_nodes = sealer.validate_campaign(args.frontend, "frontend")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert head == back["head"] == front["head"]
    assert back["source_sha256"] == front["source_sha256"] and back["deleted_files"] == front["deleted_files"]
    source = back["source_sha256"]
    prior_packets = {}
    for name in (PRIOR.name, "2026-09-07-lifecycle-attended-source-gaps", "2026-09-07-lifecycle-source-priority-capacity",
                 "2026-09-07-lifecycle-source-context", "2026-09-07-lifecycle-web-runtime", "2026-09-07-lifecycle-web-sonnet-canary"):
        path = PACKET.parent / name
        manifest = read(path / "files.sha256.json")["files"]
        assert all(sha(path / filename) == expected for filename, expected in manifest.items())
        prior_packets[name] = {"seal_sha256": sha(path / "files.sha256.json"), "files_verified": len(manifest)}
    old = {name: expected for name, expected in read(PRIOR / "source-manifest.json")["files"].items() if not name.startswith("docs/")}
    assert old.keys() <= source.keys()
    changes = {name: {"before": expected, "after": source[name]} for name, expected in old.items() if source[name] != expected}
    assert set(changes) == {
        "src/auth_drivers/lifecycle_web_claude.py", "src/auth_drivers/lifecycle_web_models.py", "src/lifecycle_web_controller.py",
        "src/lifecycle_web_store.py", "src/lifecycle_web_projection.py", "tests/test_lifecycle_web_frontend_contract.py",
        "apps/arkscope-web/src/lifecycle/LifecycleWebPanel.tsx", "apps/arkscope-web/src/lifecycle/LifecycleWebPanel.test.tsx",
        "apps/arkscope-web/src/lifecycle/webContract.ts", "apps/arkscope-web/src/lifecycle/webFixtures.ts",
        "apps/arkscope-web/src/lifecycle/webPresentation.test.ts", "apps/arkscope-web/src/styles.css",
        "apps/arkscope-web/src/i18n/resources.test.ts", "apps/arkscope-web/src/i18n/resources/en/explore.ts",
        "apps/arkscope-web/src/i18n/resources/zh-Hant/explore.ts"}
    assert set(source) - set(old) == {"src/auth_drivers/lifecycle_web_usage.py", "tests/test_lifecycle_web_usage.py",
        "tests/test_lifecycle_web_usage_journal.py", "apps/arkscope-web/src/lifecycle/webUsageContract.test.ts"}
    schemas = {name: old[name] for name in ("src/security_lifecycle_schema.py", "src/lifecycle_web_schema.py",
        "src/ticker_identity_schema.py", "src/sa_tracking_memberships.py")}
    protected = {name: old[name] for name in ("src/auth_drivers/claude_code_sdk_driver.py",
        "src/auth_drivers/codex_translation_adapter.py", "src/auth_drivers/codex_app_server_runtime.py",
        "src/auth_drivers/lifecycle_web_dispatch.py", "src/model_capabilities.py", "src/card_synthesis.py")}
    assert all(source[name] == expected for name, expected in {**schemas, **protected}.items())
    payloads = {name + "-nodes.json": value for name, value in back_nodes.items()}
    payloads["frontend-nodes.json"] = front_nodes["restored"]
    nodes_changed = {}
    for name in ("baseline", "restored", "integration", "backend", "frontend"):
        before = set(read(PRIOR / (name + "-nodes.json"))["nodes"])
        after = set(payloads[name + "-nodes.json"]["nodes"])
        assert not before - after
        nodes_changed[name] = {"before": len(before), "after": len(after), "removed": [], "added": sorted(after - before)}
    browser, copies = browser_result(args.browser, source)
    copies["browser/results.json"] = args.browser / "results.json"
    harness = harness_result(args.harness)
    measurements = {}
    for directory in args.measurement:
        measurements[directory.name] = previous.measured(directory, source, final=True)
        for path in directory.iterdir():
            if path.is_file() and path.suffix in {".json", ".py", ".log"}:
                copies["measurements/" + directory.name + "/" + path.name] = path
    assert len(measurements) == 2
    assert {(value["action"], value["decoded_source_bytes"]) for value in measurements.values()} == {
        (action, 128 * 1024**2) for action in ("terminal_delisting", "symbol_continuation")}
    historical = {}
    for directory in args.historical_campaign:
        report = read(directory / "report.json")
        assert report["complete"] is False
        assert report["baseline"]["counts"]["failures"] == (2 if report["kind"] == "frontend" else 0)
        assert all(sha(directory.parent / "source" / name) == expected for name, expected in report["source_sha256"].items())
        historical[directory.parent.name] = {"scope": "incomplete_not_final_admission", "reason": "i18n_inventory_updated",
                                            "report": report}
        for path in directory.iterdir():
            if path.is_file() and path.suffix in {".json", ".xml", ".log"}:
                copies["historical-campaigns/" + directory.parent.name + "/" + path.name] = path
        copies["historical-campaigns/" + directory.parent.name + "/verify.py"] = directory.parent / "source" / PACKET.relative_to(ROOT) / "verify.py"
    assert len(historical) == 2
    iterations = {}
    for path in args.incremental:
        value, _ = sealer.parsers.backend_report(path)
        iterations[path.name] = value
        copies["historical-iterations/" + path.name] = path
    for path in args.frontend_incremental:
        value, _ = sealer.parsers.frontend_report(path, ROOT)
        iterations[path.name] = value
        copies["historical-iterations/" + path.name] = path
    for name, directory in (("backend-results", args.backend), ("frontend-results", args.frontend), ("harness-results", args.harness)):
        for path in directory.iterdir():
            if path.is_file() and path.suffix in {".json", ".xml", ".log"}:
                copies[name + "/" + path.name] = path
    assert scanner.scan_files(copies)["unexpected"] == 0
    env = {key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR"}}
    for name in ("typecheck", "build", "check:i18n-literals"):
        command = ["npm", "run", name]
        result = subprocess.run(command, cwd=ROOT / "apps/arkscope-web", env=env, capture_output=True, text=True, timeout=180)
        assert result.returncode == 0, result.stdout + result.stderr
        payloads[name.replace(":", "-") + ".json"] = {"command": command, "exit_code": 0, "output": result.stdout + result.stderr}
    subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=True)
    docs = ["docs/design/PROJECT_PRIORITY_MAP.md", "docs/superpowers/plans/2026-09-07-lifecycle-web-usage-calibration.md",
            "docs/superpowers/plans/2026-09-06-lifecycle-web-auth-adapters.md"]
    docs += [str(path.relative_to(ROOT)) for path in PACKET.glob("*.py")]
    docs += [str(path.relative_to(ROOT)) for path in CANARY.iterdir() if path.is_file() and path.suffix in {".py", ".md"}]
    payloads.update({
        "source-manifest.json": {"base_commit": head, "files": {**source, **{name: sha(ROOT / name) for name in docs}}, "deleted_files": back["deleted_files"]},
        "source-changes.json": {"changed": changes, "added": {name: expected for name, expected in source.items() if name not in old}},
        "node-changes.json": nodes_changed, "measurements.json": measurements,
        "historical-campaigns.json": historical,
        "incremental-results.json": {"scope": "historical_red_green_not_final_source_admission", "files": iterations},
        "focus-files.json": {"files": back["focus_files"]}, "integration-files.json": {"files": back["integration_files"]},
        "verification.json": {"backend": back_measured, "frontend": front_measured,
            "mutations": {"backend": len(back["mutations"]), "frontend": len(front["mutations"])},
            "prior_packets": prior_packets, "unchanged_schemas": schemas, "unchanged_other_execution_paths": protected,
            "browser": browser, "canary_harness": harness,
            "provider_calls": 0, "production_reads": False, "production_writes": False, "migration": False,
            "app_restart": False, "commit": False, "merge": False, "push": False,
            "whole_workflow_complete": False, "usage_is_billing_authority": False, "crash_durable_phase_usage": False,
            "remaining": ["explicit_canary_envelope_confirmation", "authorized_fresh_live_canary", "remaining_live_channel_gates",
                          "authorized_journal_installation_and_population_cutover", "merge_restart_and_handtest"]},
    })
    assert not any((PACKET / name).exists() for name in payloads.keys() | copies.keys())
    for name, value in payloads.items():
        write_new(name, value)
    for name, source_path in copies.items():
        target = PACKET / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with source_path.open("rb") as incoming, target.open("xb") as outgoing:
            shutil.copyfileobj(incoming, outgoing)
    scan = scanner.scan_files({str(path.relative_to(PACKET)): path for path in PACKET.rglob("*")
                               if path.is_file() and "__pycache__" not in path.parts})
    assert scan["unexpected"] == 0
    write_new("secret-shape-scan.json", scan)
    assert all(sha(ROOT / name) == expected for name, expected in source.items())
    write_new("files.sha256.json", {"files": {str(path.relative_to(PACKET)): sha(path) for path in sorted(PACKET.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts}})
    print(json.dumps({"seal_sha256": sha(PACKET / "files.sha256.json"), "verification": payloads["verification.json"],
                      "measurements": measurements}), flush=True)


if __name__ == "__main__":
    main()
