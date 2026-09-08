"""Create-only concurrency evidence, with source-bound regressions and controls."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import verify as configuration


PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[3]
PRIOR = PACKET.parent / "2026-09-07-lifecycle-attended-source-gaps"
CAPACITY = PACKET.parent / "2026-09-07-lifecycle-source-priority-capacity"
RUNTIME = PACKET.parent / "2026-09-07-lifecycle-web-runtime"
CANARY = PACKET.parent / "2026-09-07-lifecycle-web-sonnet-canary"
sys.modules["verify"] = configuration.verifier
sealer = configuration.verifier.module("attended_sealer", RUNTIME / "scripts/seal.py")
sys.modules["verify"] = configuration
sealer.ROOT = ROOT
sealer.MUTATIONS = configuration.verifier.MUTATIONS
scanner = configuration.verifier.module("attended_scanner", CANARY / "scan_packet.py")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write_new(name, value):
    target = PACKET / name
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")


def measured(directory, source, *, final):
    supervisor = read(directory / "supervisor.json")
    report = read(directory / "measurement.json")
    manifest = read(directory / "source-manifest.json")
    assert supervisor["source_unchanged"] and supervisor["failure"] is None
    assert sha(directory / "measure_attended.py") == supervisor["runner_sha256"]
    assert report["provider_calls"] == report["network_calls"] == 0
    assert report["production_data_access"] is False
    assert report["real_controller_heartbeat_and_governed_writer"]
    assert report["shared_temporary_profile"]
    assert supervisor["sampled_peak_rss_bytes"] < supervisor["rss_guard_bytes"] == 4 * 1024**3
    assert report["peak_rss_bytes"] < supervisor["rss_guard_bytes"]
    assert report["options"]["max_decoded_source_bytes"] == report["document_decoded_bytes"]
    assert {key: report["options"][key] for key in ("max_source_bytes", "max_sources", "max_source_requests",
            "max_redirects", "source_timeout_seconds", "model_timeout_seconds")} == {
        "max_source_bytes": 32 * 1024**2, "max_sources": 4, "max_source_requests": 8,
        "max_redirects": 2, "source_timeout_seconds": 180, "model_timeout_seconds": 180}
    if final:
        assert supervisor["exit_code"] == 0 and report["passed"]
        assert manifest == source
        assert report["source_counts"] == [4, 4]
        assert report["statuses"] == [["succeeded", None], ["succeeded", None]]
        assert report["receipt"]["status"] == "applied" and report["receipt"]["current_effects_match"] is True
        assert report["acceptances"] == 1 and report["second_receipt"]["source_requests"] == 4
        assert report["active_tickers"] == (["LIVE"] if report["action"] == "terminal_delisting" else ["LIVE", "NEW"])
        assert not any(item["error"] for item in report["sql"] + report["heartbeats"] + report["polls"])
        assert {(item["job"], item["phase"]) for item in report["model_phases"]} == {
            (job, phase) for job in ("first", "second") for phase in ("search", "analysis")}
        assert len(report["model_phases"]) == 4
        assert report["confirmation_elapsed_seconds"] < 180
    writes = [item["elapsed_seconds"] for item in report["sql"]
              if item["thread"] == "attended-confirmation" and item["operation"].startswith("write_transaction_")]
    if final:
        assert len(writes) == 2 and max(writes) < 10
    return {"scope": "final_source_admission" if final else "historical_not_current_source_admission",
        "action": report["action"], "decoded_source_bytes": report["document_decoded_bytes"],
        "supervisor": supervisor, "passed": report["passed"], "statuses": report["statuses"],
        "child_ru_maxrss_bytes": report["peak_rss_bytes"],
        "source_counts": report["source_counts"], "active_tickers": report["active_tickers"],
        "confirmation_elapsed_seconds": report["confirmation_elapsed_seconds"],
        "human_write_transactions_seconds": writes,
        "max_heartbeat_seconds": max(item["elapsed_seconds"] for item in report["heartbeats"]),
        "max_poll_seconds": max((item["elapsed_seconds"] for item in report["polls"]), default=None)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--frontend", type=Path, required=True)
    parser.add_argument("--measurement", type=Path, action="append", required=True)
    parser.add_argument("--historical-measurement", type=Path, action="append", default=[])
    parser.add_argument("--historical-campaign", nargs=2, action="append", default=[], metavar=("DIRECTORY", "REASON"))
    parser.add_argument("--incremental", type=Path, action="append", default=[])
    args = parser.parse_args()
    assert not (PACKET / "files.sha256.json").exists()
    back, back_measured, back_nodes = sealer.validate_campaign(args.backend, "backend")
    front, front_measured, front_nodes = sealer.validate_campaign(args.frontend, "frontend")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert head == back["head"] == front["head"]
    assert back["source_sha256"] == front["source_sha256"] and back["deleted_files"] == front["deleted_files"]
    source = back["source_sha256"]
    prior_packets = {}
    for previous in (PRIOR, CAPACITY, RUNTIME, CANARY, PACKET.parent / "2026-09-07-lifecycle-source-context"):
        manifest = read(previous / "files.sha256.json")["files"]
        assert all(sha(previous / name) == expected for name, expected in manifest.items())
        prior_packets[previous.name] = {"files_verified": len(manifest), "seal_sha256": sha(previous / "files.sha256.json")}
    old = {name: expected for name, expected in read(PRIOR / "source-manifest.json")["files"].items() if not name.startswith("docs/")}
    assert old.keys() <= source.keys()
    allowed_changes = {"src/lifecycle_web_store.py", "src/lifecycle_web_review.py",
                       "src/security_lifecycle_review.py", "src/ticker_identity_transition.py"}
    changes = {name: {"before": expected, "after": source[name]} for name, expected in old.items() if source[name] != expected}
    assert set(changes) == allowed_changes
    assert set(source) - set(old) == {"tests/test_lifecycle_web_attended_concurrency.py"}
    schemas = {name: old[name] for name in ("src/security_lifecycle_schema.py", "src/lifecycle_web_schema.py",
                                           "src/ticker_identity_schema.py", "src/sa_tracking_memberships.py")}
    assert all(source[name] == expected for name, expected in schemas.items())
    ui = {name: expected for name, expected in old.items() if name.startswith("apps/arkscope-web/")}
    assert all(source[name] == expected for name, expected in ui.items())
    payloads = {kind + "-nodes.json": value for kind, value in back_nodes.items()}
    payloads["frontend-nodes.json"] = front_nodes["restored"]
    node_changes = {}
    for kind in ("baseline", "restored", "integration", "backend", "frontend"):
        previous = set(read(PRIOR / (kind + "-nodes.json"))["nodes"])
        current = set(payloads[kind + "-nodes.json"]["nodes"])
        assert not previous - current
        node_changes[kind] = {"before": len(previous), "after": len(current), "removed": [], "added": sorted(current - previous)}
    copies, measurements, historical = {}, {}, {}
    for final, directories in ((True, args.measurement), (False, args.historical_measurement)):
        for directory in directories:
            name = directory.name
            target = measurements if final else historical
            assert name not in target
            target[name] = measured(directory, source, final=final)
            for path in directory.iterdir():
                if path.is_file() and path.suffix in {".json", ".log", ".py"}:
                    copies[("measurements/" if final else "historical-measurements/") + name + "/" + path.name] = path
    assert len(measurements) == 4
    assert {(value["action"], value["decoded_source_bytes"]) for value in measurements.values()} == {
        (action, size * 1024**2) for action in ("terminal_delisting", "symbol_continuation") for size in (1, 128)}
    red = [value for value in historical.values() if not value["passed"]]
    assert len(red) == 1 and red[0]["supervisor"]["exit_code"] == 1
    assert red[0]["source_counts"] == [4, 0]
    assert sum(red[0]["human_write_transactions_seconds"]) > 60
    iterations = {}
    for path in args.incremental:
        value, _ = sealer.parsers.backend_report(path)
        iterations[path.name] = value
        copies["historical-iterations/" + path.name] = path
    campaigns = {}
    for directory_name, reason in args.historical_campaign:
        assert reason in {"verifier_owner_correction", "storage_wait_rerun_on_tmpfs"}
        directory = Path(directory_name)
        report = read(directory / "report.json")
        assert report["complete"] is False
        assert all(sha(directory.parent / "source" / name) == expected for name, expected in report["source_sha256"].items())
        campaigns[directory.parent.name] = {"scope": "interrupted_not_final_admission", "reason": reason, "report": report}
        for path in directory.iterdir():
            if path.is_file() and path.suffix in {".json", ".xml", ".log"}:
                copies["historical-campaigns/" + directory.parent.name + "/" + path.name] = path
        wrapper = directory.parent / "source" / PACKET.relative_to(ROOT) / "verify.py"
        copies["historical-campaigns/" + directory.parent.name + "/verify.py"] = wrapper
    for kind, directory in (("backend-results", args.backend), ("frontend-results", args.frontend)):
        for path in directory.iterdir():
            if path.is_file() and path.suffix in {".json", ".xml", ".log"}:
                copies[kind + "/" + path.name] = path
    assert scanner.scan_files(copies)["unexpected"] == 0
    env = {key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR"}}
    for name in ("typecheck", "build", "check:i18n-literals"):
        command = ["npm", "run", name]
        result = subprocess.run(command, cwd=ROOT / "apps/arkscope-web", env=env, capture_output=True, text=True, timeout=180)
        assert result.returncode == 0, result.stdout + result.stderr
        payloads[name.replace(":", "-") + ".json"] = {"command": command, "exit_code": result.returncode, "output": result.stdout + result.stderr}
    subprocess.run(["git", "diff", "--check"], cwd=ROOT, check=True)
    docs = ["docs/design/PROJECT_PRIORITY_MAP.md", "docs/superpowers/plans/2026-09-06-lifecycle-web-auth-adapters.md",
            "docs/superpowers/plans/2026-09-07-lifecycle-attended-write-concurrency.md",
            "docs/superpowers/specs/2026-09-05-lifecycle-tracking-status-and-web-supplement-design.md"]
    docs.extend(str(path.relative_to(ROOT)) for path in PACKET.glob("*.py"))
    payloads.update({
        "source-manifest.json": {"base_commit": head, "files": {**source, **{name: sha(ROOT / name) for name in docs}}, "deleted_files": back["deleted_files"]},
        "source-changes.json": {"changed": changes, "added": {name: expected for name, expected in source.items() if name not in old}},
        "node-changes.json": node_changes, "measurements.json": measurements,
        "historical-measurements.json": historical,
        "incremental-results.json": {"scope": "historical_red_green_not_final_admission", "files": iterations},
        "historical-campaigns.json": campaigns,
        "focus-files.json": {"files": back["focus_files"]}, "integration-files.json": {"files": back["integration_files"]},
        "verification.json": {"backend": back_measured, "frontend": front_measured,
            "mutations": {"backend": len(back["mutations"]), "frontend": len(front["mutations"])},
            "prior_packets": prior_packets, "unchanged_schemas": schemas,
            "browser": {"rerun": False, "reason": "no_frontend_source_or_DTO_changes",
                "unchanged_ui_files": len(ui), "prior_packet": PRIOR.name,
                "prior_scenarios": 24, "prior_screenshots": 42},
            "provider_calls": 0, "production_reads": False, "production_writes": False, "migration": False,
            "app_restart": False, "commit": False, "merge": False, "push": False,
            "whole_workflow_complete": False,
            "remaining": ["model_usage_calibration", "authorized_fresh_live_canary",
                          "authorized_journal_installation_and_population_cutover", "merge_and_handtest"]},
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
