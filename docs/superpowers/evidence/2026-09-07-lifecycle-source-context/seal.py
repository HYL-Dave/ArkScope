"""Create-only, source-bound offline admission; no production/provider access."""

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
PRIOR = PACKET.parent / "2026-09-07-lifecycle-web-sonnet-canary"
RUNTIME = PACKET.parent / "2026-09-07-lifecycle-web-runtime"
sys.modules["verify"] = configuration.verifier
sealer = configuration.verifier.module("source_context_sealer", RUNTIME / "scripts/seal.py")
sys.modules["verify"] = configuration
sealer.ROOT = ROOT
sealer.MUTATIONS = configuration.verifier.MUTATIONS
scanner = configuration.verifier.module("source_context_scanner", PRIOR / "scan_packet.py")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(name, value):
    with (PACKET / name).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--frontend", type=Path, required=True)
    parser.add_argument("--browser", type=Path, required=True)
    parser.add_argument("--interrupted", type=Path, action="append", default=[])
    args = parser.parse_args()
    assert not (PACKET / "files.sha256.json").exists()
    back, back_measured, back_nodes = sealer.validate_campaign(args.backend, "backend")
    front, front_measured, front_nodes = sealer.validate_campaign(args.frontend, "frontend")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert head == back["head"] == front["head"]
    assert back["source_sha256"] == front["source_sha256"] and back["deleted_files"] == front["deleted_files"]
    prior_packets = {}
    for previous in (PRIOR, RUNTIME):
        manifest = json.loads((previous / "files.sha256.json").read_text())["files"]
        assert all(sha(previous / name) == expected for name, expected in manifest.items())
        prior_packets[previous.name] = {"seal_sha256": sha(previous / "files.sha256.json"), "files_verified": len(manifest)}
    old = json.loads((PRIOR / "source-manifest.json").read_text())["files"]
    old_code = {name: value for name, value in old.items() if not name.startswith("docs/")}
    assert old_code.keys() <= back["source_sha256"].keys()
    schemas = {name: old_code[name] for name in (
        "src/security_lifecycle_schema.py", "src/lifecycle_web_schema.py",
        "src/ticker_identity_schema.py", "src/sa_tracking_memberships.py",
    )}
    assert all(sha(ROOT / name) == expected for name, expected in schemas.items())
    payloads = {name + "-nodes.json": value for name, value in back_nodes.items()}
    payloads["frontend-nodes.json"] = front_nodes["restored"]
    renamed_before = "tests.test_lifecycle_public_sources::test_invalid_source_response_is_not_usable_evidence[headers1-compressed-source_encoding_unsupported]"
    renamed_after = renamed_before.replace("source_encoding_unsupported", "source_compression_invalid")
    changes = {}
    for kind in ("baseline", "restored", "integration", "backend", "frontend"):
        previous = RUNTIME if kind == "frontend" else PRIOR
        old_nodes = set(json.loads((previous / (kind + "-nodes.json")).read_text())["nodes"])
        new_nodes = set(payloads[kind + "-nodes.json"]["nodes"])
        removed, added = old_nodes - new_nodes, new_nodes - old_nodes
        assert removed == (set() if kind == "frontend" else {renamed_before}), sorted(removed)
        if kind != "frontend":
            assert renamed_after in added
        changes[kind] = {"before": len(old_nodes), "after": len(new_nodes),
                         "added": sorted(added), "removed": sorted(removed),
                         "net_added_count": len(added) - len(removed),
                         "renamed_parameters": [] if kind == "frontend" else [{
                             "before": renamed_before, "after": renamed_after,
                             "reason": "gzip is supported; malformed compressed bytes remain rejected as compression_invalid",
                         }]}
    browser = json.loads((args.browser / "results.json").read_text())
    assert browser["provider_calls"] == 0 and not browser["production_app_started"]
    assert len(browser["cases"]) == 12
    assert {(row["locale"], row["width"], row["scenario"]) for row in browser["cases"]} == {
        (locale, width, scenario) for locale in ("en", "zh-Hant") for width in (1440, 390, 320)
        for scenario in ("selected", "read_failure")}
    assert all(sha(ROOT / name) == expected for name, expected in browser["source_sha256"].items())
    assert all(back["source_sha256"][name] == expected for name, expected in browser["source_sha256"].items()
               if not name.startswith("docs/"))
    screenshots = []
    for row in browser["cases"]:
        assert not row["page_errors"] and row["provider_calls"] == row["writes"] == 0
        for phase, metrics in row["geometry"].items():
            assert not any(metrics.values())
            path = args.browser / f'{row["locale"]}-{row["width"]}-{row["scenario"]}-{phase}.png'
            with Image.open(path) as picture:
                assert max(ImageStat.Stat(picture).var) > 5
            screenshots.append(path)
    assert len(screenshots) == len(set(screenshots)) == 24
    assert set(screenshots) == set(args.browser.glob("*.png"))
    interrupted = {}
    for index, path in enumerate(args.interrupted):
        report = json.loads((path / "report.json").read_text())
        assert report["complete"] is False
        assert all(sha(path.parent / "source" / name) == expected for name, expected in report["source_sha256"].items())
        interrupted[f"attempt-{index}"] = report
    capacity = json.loads((PACKET / "capacity-32mib-final.json").read_text())
    assert capacity["provider_calls"] == capacity["network_calls"] == 0 and not capacity["production_data_access"]
    assert capacity["concurrent_workers"] == 2 and capacity["retained_sources_per_worker"] == 4
    assert all(row["requests"] == 4 and row["retained_text_bytes"] > row["model_text_bytes"] > 0
               and len(row["observations"]) == 4 and all(item["result_code"] == "complete" for item in row["observations"])
               for row in capacity["runs"])
    payloads.update({
        "node-changes.json": changes, "browser-results.json": browser,
        "interrupted-campaigns.json": interrupted,
        "source-changes.json": {"prior_manifest_sha256": sha(PRIOR / "source-manifest.json"),
            "changed": {name: {"before": value, "after": back["source_sha256"][name]} for name, value in old_code.items()
                        if value != back["source_sha256"][name]},
            "added": {name: value for name, value in back["source_sha256"].items() if name not in old_code}},
        "verification.json": {"backend": back_measured, "frontend": front_measured,
            "mutations": {"backend": len(back["mutations"]), "frontend": len(front["mutations"])},
            "browser_scenarios": 12, "browser_screenshots": 24, "prior_packets": prior_packets,
            "unchanged_schemas": schemas, "capacity_peak_rss_bytes": capacity["peak_rss_bytes"],
            "provider_calls": 0, "production_reads": False, "production_writes": False,
            "migration": False, "app_restart": False, "merge": False, "push": False,
            "whole_workflow_complete": False,
            "remaining": ["authorized_fresh_live_canary", "model_usage_calibration", "sec_document_resolver",
                          "authorized_journal_installation_and_population_cutover", "merge_and_handtest"]},
    })
    env = {key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR"}}
    for name in ("typecheck", "build", "check:i18n-literals"):
        command = ["npm", "run", name]
        result = subprocess.run(command, cwd=ROOT / "apps/arkscope-web", env=env, capture_output=True, text=True, timeout=180)
        assert result.returncode == 0, result.stdout + result.stderr
        payloads[name.replace(":", "-") + ".json"] = {"command": command, "exit_code": result.returncode,
                                                         "output": result.stdout + result.stderr}
    subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=True)
    docs = ["docs/design/PROJECT_PRIORITY_MAP.md", "docs/superpowers/plans/2026-09-06-lifecycle-web-auth-adapters.md"]
    docs.extend(str(path.relative_to(ROOT)) for path in PACKET.glob("*.py"))
    payloads["source-manifest.json"] = {"base_commit": head, "files": {
        **back["source_sha256"], **{name: sha(ROOT / name) for name in docs}}, "deleted_files": back["deleted_files"]}
    fixture_names = {value[1] for value in scanner.SYNTHETIC_TEST_FIXTURES.values()}
    literals = {target.id: ast.literal_eval(node.value) for node in ast.parse((ROOT / "tests/test_probe_harness.py").read_text()).body
                if isinstance(node, ast.Assign) for target in node.targets if isinstance(target, ast.Name) and target.id in fixture_names}
    assert {hashlib.sha256(value.encode()).hexdigest(): key for key, value in literals.items()} == {
        key: value[1] for key, value in scanner.SYNTHETIC_TEST_FIXTURES.items()}
    inputs = {f"{kind}-results/{path.name}": path for kind, directory in (("backend", args.backend), ("frontend", args.frontend))
              for path in directory.iterdir() if path.is_file() and path.suffix in {".json", ".xml", ".log"}}
    assert scanner.scan_files(inputs)["unexpected"] == 0
    assert not any((PACKET / name).exists() for name in payloads)
    for name, value in payloads.items():
        write_new(name, value)
    for kind, directory in (("backend", args.backend), ("frontend", args.frontend)):
        target = PACKET / (kind + "-results")
        target.mkdir()
        for path in directory.iterdir():
            if path.is_file() and path.suffix in {".json", ".xml", ".log"}:
                shutil.copy2(path, target / path.name)
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
