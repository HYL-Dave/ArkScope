"""Create-only source-bound offline capacity admission; no production/provider access."""

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
PRIOR = PACKET.parent / "2026-09-07-lifecycle-source-context"
RUNTIME = PACKET.parent / "2026-09-07-lifecycle-web-runtime"
CANARY = PACKET.parent / "2026-09-07-lifecycle-web-sonnet-canary"
sys.modules["verify"] = configuration.verifier
sealer = configuration.verifier.module("capacity_sealer", RUNTIME / "scripts/seal.py")
sys.modules["verify"] = configuration
sealer.ROOT = ROOT
sealer.MUTATIONS = configuration.verifier.MUTATIONS
scanner = configuration.verifier.module("capacity_scanner", CANARY / "scan_packet.py")


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


def validate_capacity(directory, sources, *, dense, runner="measure_polling.py"):
    supervision = read(directory / "supervisor.json")
    value = read(directory / "measurement.json")
    polling = read(directory / "polling.json")
    assert supervision["exit_code"] == 0 and supervision["source_unchanged"]
    assert supervision["failure"] is None and not supervision["terminated_by_supervisor"]
    assert supervision["benchmark_sha256"] == sha(PACKET / runner)
    assert read(directory / "source-manifest.json") == sources
    assert max(supervision["sampled_peak_rss_bytes"], value["peak_rss_bytes"]) < 4 * 1024**3
    assert value["provider_calls"] == value["network_calls"] == 0 and not value["production_data_access"]
    assert value["real_controller_and_heartbeat"] and value["shared_journal"]
    assert value["concurrent_workers"] == 2 and value["dense_context"] is dense
    assert value["statuses"] == [["succeeded", None], ["succeeded", None]]
    assert sorted(value["simulated_model_phases"]) == ["analysis", "analysis", "search", "search"]
    assert value["options"]["max_source_bytes"] == 32 * 1024**2
    assert value["options"]["max_decoded_source_bytes"] == 128 * 1024**2
    assert value["options"]["source_timeout_seconds"] == 180
    assert value["options"]["model_timeout_seconds"] == 180
    assert 127 * 1024**2 < value["document_decoded_bytes"] <= 128 * 1024**2
    assert len(value["source_reading"]) == 2
    for row in value["source_reading"]:
        assert row["sources"] == 4
        if dense:
            assert row["selected_sources"] == 0 and row["retained_text_bytes"] == row["model_text_bytes"]
        else:
            assert row["selected_sources"] == 4 and row["retained_text_bytes"] > row["model_text_bytes"] > 0
    assert polling["provider_calls"] == 0 and not polling["production_data_access"]
    assert polling["observations"] and all(row["error"] is None for row in polling["observations"])
    assert any(row["status"] == "reading_sources" for row in polling["observations"])
    assert all(row["elapsed_seconds"] < 180 for row in polling["observations"])
    terminals = [row for row in polling["observations"] if row["status"] == "succeeded"]
    assert len(terminals) == 2 and {row["case_id"] for row in terminals} == {"case-1", "case-2"}
    return {"measurement": value, "supervisor": supervision, "polling": polling}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("backend", "frontend", "browser", "sparse", "dense", "wire", "sql-control"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--historical-benchmark", type=Path, action="append", default=[])
    parser.add_argument("--historical-backend", type=Path, action="append", default=[])
    parser.add_argument("--incremental", type=Path, action="append", default=[])
    parser.add_argument("--frontend-incremental", type=Path, action="append", default=[])
    args = parser.parse_args()
    assert not (PACKET / "files.sha256.json").exists()
    back, back_measured, back_nodes = sealer.validate_campaign(args.backend, "backend")
    front, front_measured, front_nodes = sealer.validate_campaign(args.frontend, "frontend")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    assert head == back["head"] == front["head"]
    assert back["source_sha256"] == front["source_sha256"]
    assert back["deleted_files"] == front["deleted_files"]
    prior_packets = {}
    for previous in (PRIOR, CANARY, RUNTIME):
        manifest = read(previous / "files.sha256.json")["files"]
        assert all(sha(previous / name) == expected for name, expected in manifest.items())
        prior_packets[previous.name] = {"seal_sha256": sha(previous / "files.sha256.json"), "files_verified": len(manifest)}
    old = read(PRIOR / "source-manifest.json")["files"]
    old_code = {name: value for name, value in old.items() if not name.startswith("docs/")}
    assert old_code.keys() <= back["source_sha256"].keys()
    schemas = {name: old_code[name] for name in (
        "src/security_lifecycle_schema.py", "src/lifecycle_web_schema.py",
        "src/ticker_identity_schema.py", "src/sa_tracking_memberships.py",
    )}
    assert all(sha(ROOT / name) == expected for name, expected in schemas.items())
    payloads = {name + "-nodes.json": value for name, value in back_nodes.items()}
    payloads["frontend-nodes.json"] = front_nodes["restored"]
    changes = {}
    for kind in ("baseline", "restored", "integration", "backend", "frontend"):
        previous = set(read(PRIOR / (kind + "-nodes.json"))["nodes"])
        current = set(payloads[kind + "-nodes.json"]["nodes"])
        assert not previous - current, sorted(previous - current)
        changes[kind] = {"before": len(previous), "after": len(current), "added": sorted(current - previous),
                         "removed": [], "net_added_count": len(current - previous)}
    browser = read(args.browser / "results.json")
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
    capacities = {"sparse": validate_capacity(args.sparse, back["source_sha256"], dense=False),
                  "dense": validate_capacity(args.dense, back["source_sha256"], dense=True)}
    sql_control = validate_capacity(args.sql_control, back["source_sha256"], dense=False, runner="measure_sql.py")
    sql_timing = read(args.sql_control / "sql-timing.json")
    assert sql_timing["provider_calls"] == 0 and not sql_timing["production_data_access"]
    assert not sql_timing["parameters_recorded"] and sql_timing["synthetic_commit_holds_seconds"] == [29]
    assert sql_timing["source_inserts_observed"] == 8
    assert not any(row["error"] is not None for row in sql_timing["observations"])
    holds = [row for row in sql_timing["observations"] if row["operation"] == "synthetic_large_commit_hold"]
    assert len(holds) == 1 and holds[0]["elapsed_seconds"] >= 29
    assert any(row["operation"] != "synthetic_large_commit_hold" and row["elapsed_seconds"] > 5
               for row in sql_timing["observations"])
    wire = read(args.wire)
    assert wire["source_sha256"] == back["source_sha256"]
    assert wire["provider_calls"] == wire["network_calls"] == 0 and not wire["production_data_access"]
    assert wire["wire_limit_bytes"] == 32 * 1024**2
    assert wire["exact_limit_text_and_tail_preserved"] and wire["one_byte_over_rejected_without_returning_prefix"]
    assert [row["result_code"] for row in wire["observations"]] == ["complete", "source_body_too_large"]
    historical = {}
    copies = {}
    for directory in args.historical_benchmark:
        value = {path.name: read(path) for path in directory.glob("*.json") if path.name != "source-manifest.json"}
        historical[directory.name] = {"scope": "historical_experiment_not_final_admission", **value}
        for path in directory.iterdir():
            if path.is_file() and path.suffix in {".json", ".log"}:
                copies[f"historical-capacity/{directory.name}/{path.name}"] = path
    historical_backends = {}
    for directory in args.historical_backend:
        historical_report = read(directory / "report.json")
        assert all(sha(directory.parent / "source" / name) == expected
                   for name, expected in historical_report["source_sha256"].items())
        historical_backends[directory.parent.name] = {
            "scope": "historical_or_interrupted_before_final_capacity_contract_not_final_admission", "report": historical_report}
        for path in directory.iterdir():
            if path.is_file() and path.suffix in {".json", ".xml", ".log"}:
                copies[f"historical-backend-results/{directory.parent.name}/{path.name}"] = path
    incremental = {}
    for path in args.incremental:
        value, _ = sealer.parsers.backend_report(path)
        incremental[path.name] = value
        copies["incremental/" + path.name] = path
    incremental_frontend = {}
    for path in args.frontend_incremental:
        value, _ = sealer.parsers.frontend_report(path, ROOT)
        raw = read(path)
        incremental_frontend[path.name] = {
            **value, "reported_success": raw["success"],
            "classification": ("command_failure_no_tests" if value["counts"]["tests"] == 0
                               and not raw["success"] else "historical_test_execution"),
        }
        copies["incremental/" + path.name] = path
    payloads.update({
        "node-changes.json": changes, "browser-results.json": browser,
        "capacity-results.json": capacities, "wire-results.json": wire,
        "sql-control-results.json": {**sql_control, "sql_timing": sql_timing},
        "historical-capacity.json": historical,
        "historical-backend.json": historical_backends,
        "incremental-results.json": {"scope": "historical_red_green_not_final_admission", "files": incremental},
        "incremental-frontend-results.json": {"scope": "historical_red_green_not_final_admission", "files": incremental_frontend},
        "source-changes.json": {"prior_manifest_sha256": sha(PRIOR / "source-manifest.json"),
            "changed": {name: {"before": value, "after": back["source_sha256"][name]} for name, value in old_code.items()
                        if value != back["source_sha256"][name]},
            "added": {name: value for name, value in back["source_sha256"].items() if name not in old_code}},
        "verification.json": {"backend": back_measured, "frontend": front_measured,
            "mutations": {"backend": len(back["mutations"]), "frontend": len(front["mutations"])},
            "browser_scenarios": 12, "browser_screenshots": 24, "prior_packets": prior_packets,
            "unchanged_schemas": schemas, "capacity_includes_real_progress_reads": True,
            "local_receipt_timeout_seconds": 180, "general_request_timeout_seconds": 15,
            "journal_busy_timeout_seconds": 45, "lease_seconds": 60, "synthetic_commit_hold_seconds": 29,
            "shared_source_timeout_seconds": 180, "model_timeout_seconds": 180,
            "provider_calls": 0, "production_reads": False, "production_writes": False,
            "migration": False, "app_restart": False, "merge": False, "push": False,
            "whole_workflow_complete": False,
            "remaining": ["unread_supplementary_reference_product_decision", "authorized_fresh_live_canary",
                          "model_usage_calibration", "maximum_source_attended_write_concurrency_measurement",
                          "authorized_journal_installation_and_population_cutover",
                          "merge_and_handtest"]},
    })
    env = {key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR"}}
    for name in ("typecheck", "build", "check:i18n-literals"):
        command = ["npm", "run", name]
        result = subprocess.run(command, cwd=ROOT / "apps/arkscope-web", env=env, capture_output=True, text=True, timeout=180)
        assert result.returncode == 0, result.stdout + result.stderr
        payloads[name.replace(":", "-") + ".json"] = {"command": command, "exit_code": result.returncode,
                                                         "output": result.stdout + result.stderr}
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
    for kind, directory in (("backend-results", args.backend), ("frontend-results", args.frontend),
                            ("capacity-sparse", args.sparse), ("capacity-dense", args.dense),
                            ("capacity-sql-control", args.sql_control)):
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
