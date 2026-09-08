"""Verify unchanged product source and seal the measured, incomplete outcome."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.with_name("2026-09-07-lifecycle-web-usage-canary")))
from claude_canary import write_new_json
from record_json_admission import checked_packet, scan_files


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    seals = {
        "admission": "05a81e10133bbd66fe14b42fed636d4b2cd6f629cef4c379dda43000ce7d7781",
        "live-r1": "bcdb7581d9447177ad386e7c85d2b4eea73b6c1d59a472d590ff86504d7a5ab1",
        "failed-original-analysis-r1": "ff1ed46b26e044e60cf8d199d7e2014669a58a429b551c9a20c03af7c877ab4d",
        "public-original-followup": "a76271c27e134771184b0d739c1dbafaaf09f841b8a8ee86122eaf9f9984f2e4",
    }
    for name, expected in seals.items():
        checked_packet(HERE / name, expected)
    manifest = json.loads((HERE / "admission/source-manifest.json").read_text())
    changes = {name: sha(ROOT / name) for name, expected in manifest["files"].items() if sha(ROOT / name) != expected}
    assert set(changes) == {
        "docs/design/PROJECT_PRIORITY_MAP.md",
        "docs/superpowers/plans/2026-09-05-lifecycle-tracking-first-implementation.md",
        "docs/superpowers/plans/2026-09-06-lifecycle-web-auth-adapters.md",
        "docs/superpowers/plans/2026-09-07-lifecycle-web-instrument-scoping.md",
        "docs/superpowers/plans/2026-09-07-lifecycle-web-usage-calibration.md",
    }
    assert not any((ROOT / name).exists() for name in manifest["deleted_files"])
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    assert head == manifest["base_commit"]
    subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=True)
    report = json.loads((HERE / "admission/results/report.json").read_text())
    assert report["backend"]["counts"] == {"tests": 6943, "failures": 0, "errors": 0, "skipped": 12}
    suite = ET.parse(HERE / "closing-harness-green.xml").getroot()
    assert len(list(suite.iter("testcase"))) == 24
    assert not list(suite.iter("failure")) and not list(suite.iter("error")) and not list(suite.iter("skipped"))
    followup = json.loads((HERE / "public-original-followup/verification.json").read_text())
    assert followup["sdk_submissions_this_turn"] == 4 and followup["source_http_attempts_this_turn"] == 9
    assert followup["fresh_action_ready_live_runs"] == 0
    snapshots = HERE / "status-documents"
    snapshots.mkdir()
    new_plan = "docs/superpowers/plans/2026-09-07-lifecycle-web-bounded-followup.md"
    for name in [*changes, new_plan]:
        target = snapshots / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with (ROOT / name).open("rb") as incoming, target.open("xb") as outgoing:
            shutil.copyfileobj(incoming, outgoing)
    write_new_json(HERE / "closing-verification.json", {
        "base_commit": head, "admission_and_live_seals": seals,
        "post_live_changed_manifest_files": changes, "product_and_test_source_unchanged_after_admission": True,
        "additional_status_documents_sha256": {new_plan: sha(ROOT / new_plan)},
        "backend_passed": 6931, "backend_skipped": 12, "focused_passed": 2266,
        "integration_passed": 3085, "whole_focus_owned_mutants": 25, "current_harness_passed": 24,
        "sdk_submissions_this_turn": 4, "source_http_attempts_this_turn": 9,
        "no_action_ready_live_finding": True, "schema_followup_approved": False,
        "production_install_adoption_restart_commit_merge_push": False,
    })
    files = {str(path.relative_to(HERE)): path for path in HERE.rglob("*")
             if path.is_file() and "__pycache__" not in path.parts and ".pytest_cache" not in path.parts}
    scan = scan_files(files)
    assert scan["unexpected"] == 0
    write_new_json(HERE / "closing-secret-shape-scan.json", scan)
    files["closing-secret-shape-scan.json"] = HERE / "closing-secret-shape-scan.json"
    write_new_json(HERE / "files.sha256.json", {"files": {name: sha(path) for name, path in sorted(files.items())}})
    print(json.dumps({"closing_seal_sha256": sha(HERE / "files.sha256.json"),
        "product_source_unchanged_after_admission": True, "backend_passed": 6931,
        "sdk_calls": 4, "source_http": 9, "action_ready_live_findings": 0, "unexpected_secret_shapes": 0}))


if __name__ == "__main__":
    main()
