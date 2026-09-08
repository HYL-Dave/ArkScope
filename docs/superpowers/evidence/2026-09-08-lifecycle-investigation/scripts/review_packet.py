"""Create-only review evidence; no production DB, credential or provider access."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

from PIL import Image, ImageStat

from mutations import BACKEND, FRONTEND

ROOT = Path(__file__).resolve().parents[5]
PACKET = Path(__file__).resolve().parent.parent
PRIOR = PACKET.with_name("2026-09-07-lifecycle-independent-task")
PRIOR_SEAL = "2806a7cab50e1bd021e84b254944f13ca2030fb8eeb99d9bb6769ac0e8dbd16d"
STATUS_DOCS = {"docs/design/PROJECT_PRIORITY_MAP.md", "docs/superpowers/plans/2026-09-08-lifecycle-investigation-completion.md"}
EVIDENCE_PRODUCERS = {str(Path(__file__).resolve().relative_to(ROOT))}
SUPERSEDED_FRONTEND_NODES = {
    "src/Universe.test.tsx::Universe localization forwards the exact Models Settings target from lifecycle translation recovery":
        "src/Universe.test.tsx::Universe localization forwards the exact Models Settings target from independent investigation setup",
    "src/Universe.test.tsx::Universe localization opens an exact lifecycle case navigation target and preserves it across locale switch":
        "src/Universe.test.tsx::Universe localization opens an exact investigation ticker and preserves it across locale switch without a legacy case",
}
DEFINITION_SETUP_NODES = {
    "tests.test_lifecycle_investigation_routes::" + name for name in (
        "test_target_routes_read_and_adopt_without_dispatch_or_legacy_queue",
        "test_investigation_activity_reports_current_reverse_readiness_without_legacy_cases[none]",
        "test_investigation_activity_reports_current_reverse_readiness_without_legacy_cases[unrelated]",
        "test_investigation_activity_reports_current_reverse_readiness_without_legacy_cases[affected]",
        "test_runtime_routes_roundtrip_unknown_fields_reject_and_reset",
        "test_unknown_failures_are_closed_and_contain_no_private_data",
        "test_saved_provider_observations_are_dated_readonly_and_refresh_is_target_scoped",
        "test_pending_confirmed_actions_remain_visible_without_the_legacy_queue",
        "test_provider_preparation_api_is_bound_to_the_selected_snapshot_without_dispatch",
    )
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def new_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=True, sort_keys=True)
        stream.write("\n")


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as incoming, target.open("xb") as outgoing:
        shutil.copyfileobj(incoming, outgoing)


def xml(path):
    root = ET.parse(path).getroot()
    cases = list(root.iter("testcase"))
    def name(item):
        return item.get("classname", "") + "::" + item.get("name", "").replace(" > ", " ")
    nodes = sorted(name(item) for item in cases)
    assert len(nodes) == len(set(nodes)), path
    failed = [name(item) for item in cases if item.find("failure") is not None]
    errors = [name(item) for item in cases if item.find("error") is not None]
    skipped = sum(item.find("skipped") is not None for item in cases)
    return {"tests": len(cases), "passed": len(cases) - len(failed) - len(errors) - skipped,
        "skipped": skipped, "failed": failed, "errors": errors, "nodes": nodes}


def green(report):
    assert report["tests"] and not report["failed"] and not report["errors"], report


def source_path(name):
    path = Path(name)
    assert not path.is_absolute() and ".." not in path.parts
    return ROOT / path


def verify_prior():
    assert sha(PRIOR / "files.sha256.json") == PRIOR_SEAL
    manifest = read(PRIOR / "files.sha256.json")
    for name, digest in manifest["files"].items():
        assert sha(PRIOR / name) == digest, name
    return {"path": str(PRIOR.relative_to(ROOT)), "seal_sha256": sha(PRIOR / "files.sha256.json"), "files": len(manifest["files"])}


def mutation_setup_errors(name, path, report):
    if name != "valid_security_definition_ignored":
        assert not report["errors"], (name, report["errors"])
        return []
    # This mutation also breaks the shared fixture's real successful finding.
    # Require its exact nine assertion sites, not arbitrary setup/transport errors.
    assert set(report["errors"]) == DEFINITION_SETUP_NODES
    assert sum("test_only_security_qualified_definitions_bind_event_aliases" in node
        for node in report["failed"]) == 8
    for case in ET.parse(path).getroot().iter("testcase"):
        error = case.find("error")
        if error is None:
            continue
        detail = error.text or ""
        assert error.get("message", "").startswith('failed on setup with "AssertionError:')
        assert '>       assert result["status"] == "succeeded", result' in detail
        assert "E       assert 'incomplete' == 'succeeded'" in detail
        assert "'stop_reason': 'investigation_no_progress'" in detail
        assert re.search(r"tests/test_lifecycle_investigation_review\.py:\d+: AssertionError\s*$", detail)
    return sorted(report["errors"])


def collect_mutations(folder, out):
    results = read(folder / "results.json")
    expected = [(row["name"], row["owner"]) for row in [*BACKEND, *FRONTEND]]
    assert [(row["name"], row["owner"]) for row in results if "owner_failed" in row] == expected
    assert read(folder / "source-integrity.json")["changed"] == []
    scopes = {}
    expected_setup_errors = {}
    for layer in ("backend", "frontend"):
        baseline = xml(folder / f"{layer}-baseline.xml")
        restored = xml(folder / f"{layer}-restored.xml")
        green(baseline)
        green(restored)
        assert baseline["nodes"] == restored["nodes"]
        scopes[layer] = baseline["nodes"]
    for row in results:
        path = folder / (row["name"] + ".xml")
        measured = xml(path)
        assert measured["nodes"] == scopes[row["layer"]]
        assert sha(path) == row["report_sha256"]
        if "owner_failed" in row:
            assert row["returncode"] == 1 and row["owner_failed"]
            setup_errors = mutation_setup_errors(row["name"], path, measured)
            if setup_errors:
                expected_setup_errors[row["name"]] = setup_errors
            assert any(row["owner"] in name for name in measured["failed"]), row["name"]
        else:
            green(measured)
        copy(path, out / "mutations" / path.name)
    for name in ("results.json", "focused-nodes.json", "source-manifest.json", "source-integrity.json"):
        copy(folder / name, out / "mutations" / name)
    sources = read(folder / "source-manifest.json")
    workspaces = {"source", *(row["workspace"] for row in results if "workspace" in row)}
    for workspace in workspaces:
        assert Path(workspace).name == workspace
        for name, digest in sources.items():
            assert sha(folder / workspace / name) == digest, (workspace, name)
    documentation_changes = {}
    for name, digest in sources.items():
        current = sha(source_path(name))
        if name in STATUS_DOCS | EVIDENCE_PRODUCERS and current != digest:
            documentation_changes[name] = {"tested": digest, "reported": current}
        else:
            assert current == digest, name
    return {"named_mutants": len(expected), "backend_focus": len(scopes["backend"]), "frontend_focus": len(scopes["frontend"]),
        "expected_mutation_setup_errors": expected_setup_errors,
        "verified_restored_workspaces": len(workspaces),
        "post_test_documentation_changes": documentation_changes}, sources


def collect_regressions(entries, out):
    results = []
    for name, path in entries.items():
        assert name.replace("-", "").isalnum()
        report = xml(path)
        assert report["tests"] and not report["errors"]
        if name == "disproved-row-probe":
            green(report)
        else:
            assert report["failed"], name
        copy(path, out / "regressions" / (name + ".xml"))
        results.append({"name": name, "disproved_hypothesis": name == "disproved-row-probe",
            **{key: value for key, value in report.items() if key != "nodes"}})
    return results


def collect_checkpoints(entries, out):
    checkpoints = []
    for name, folder in entries.items():
        assert name.replace("-", "").isalnum()
        results = read(folder / "results.json")
        for row in results:
            path = folder / (row["name"] + ".xml")
            report = xml(path)
            assert sha(path) == row["report_sha256"] and report["tests"] == row["tests"]
            copy(path, out / "historical-mutations" / name / path.name)
        for filename in ("results.json", "focused-nodes.json", "source-manifest.json", "source-integrity.json"):
            path = folder / filename
            if path.exists():
                copy(path, out / "historical-mutations" / name / filename)
        checkpoints.append({"name": name, "final_acceptance": False,
            "recorded_mutants": sum("owner_failed" in row for row in results),
            "surviving_mutants": [row["name"] for row in results if row.get("owner_failed") is False],
            "failed_baselines": [row["name"] for row in results if "owner_failed" not in row and row["returncode"] != 0]})
    return checkpoints


def collect_historical_tests(entries, out):
    reports = []
    for name, path in entries.items():
        assert name.replace("-", "").isalnum()
        report = xml(path)
        assert report["tests"]
        copy(path, out / "historical-tests" / (name + ".xml"))
        reports.append({"name": name, "final_acceptance": False,
            "report_sha256": sha(path), **{key: value for key, value in report.items() if key != "nodes"}})
    return reports


def collect_build(path, mutation_folder, out):
    result = read(path)
    log = path.with_suffix(".log")
    assert result["command"] == ["npm", "run", "build"] and result["returncode"] == 0
    assert result["log_sha256"] == sha(log)
    assert result["source_manifest_sha256"] == sha(mutation_folder / "source-manifest.json")
    assert "tsc --noEmit && vite build" in log.read_text()
    copy(path, out / "build.json")
    copy(log, out / "build.log")
    return result


def collect_producer_check(folder, mutation_folder, out):
    from check_mutation_setup_errors import NEGATIVE_CASES
    result = read(folder / "verification.json")
    assert set(result["checks"]) == {"expected_nine_setup_assertions", *(name + "_rejected" for name in NEGATIVE_CASES)}
    assert all(value is True for value in result["checks"].values())
    assert result["producer_sha256"] == sha(Path(__file__))
    assert result["checker_sha256"] == sha(Path(__file__).with_name("check_mutation_setup_errors.py"))
    assert result["original_report_sha256"] == sha(mutation_folder / "valid_security_definition_ignored.xml")
    assert set(result["files"]) == {name + ".xml" for name in NEGATIVE_CASES}
    for name, digest in result["files"].items():
        assert sha(folder / name) == digest
        copy(folder / name, out / "producer-check" / name)
    copy(folder / "verification.json", out / "producer-check" / "verification.json")
    return {"checks": result["checks"], "producer_sha256": result["producer_sha256"]}


def collect_browser(folder, out):
    reports = read(folder / "report.json")
    assert {(row["locale"], row["width"]) for row in reports} == {(locale, width) for locale in ("en", "zh-Hant") for width in (1440, 390, 320)}
    shots = 0
    for row in reports:
        assert row["provider_calls"] == 0 and row["synthetic_model_submissions"] == 3
        for entry in row["screens"]:
            assert not any(entry["geometry"].values())
            path = folder / entry["file"]
            with Image.open(path) as image:
                assert max(ImageStat.Stat(image).var) > 5
            copy(path, out / "browser" / path.name)
            shots += 1
    assert shots == 96
    copy(folder / "report.json", out / "browser" / "report.json")
    return {"scenarios": len(reports), "screenshots": shots, "provider_calls": 0}


def collect_live(entries, out):
    successes = {"local-ta", "web-ta", "active-smci"}
    report = []
    for name, folder in entries.items():
        assert name.replace("-", "").isalnum()
        result, observed = read(folder / "result.json"), read(folder / "observations.json")
        assert observed["production_writes"] is False and observed["profile_actions"] is False and observed["fallback"] is False
        assert all(row["api_key_source"] == "none" and row["mcp_server_count"] == 0
            and set(row["tools"]) <= {"StructuredOutput", "WebSearch"} for row in observed["init"])
        assert all(row["model"] == result["execution"]["model"] for row in observed["init"])
        if name in successes:
            assert result["status"] == "succeeded" and not result["block_reasons"] and result["failure_code"] is None
            assert result["stats"]["model_submissions"] == observed["sdk_submissions"]
            assert result["execution"]["auth_mode"] == "claude_code_oauth"
            assert len(observed["init"]) == observed["sdk_submissions"]
            assert {model for row in observed["results"] for model in (row["model_usage"] or {})} == {result["execution"]["model"]}
            for path, digest in read(folder / "execution-source-manifest.json").items():
                assert sha(source_path(path)) == digest, path
            if name == "active-smci":
                assert result["ticker"] == "SMCI" and result["action"] is None and result["finding"]["event_kind"] == "active_listing"
            else:
                assert result["ticker"] == "TA" and result["action"] == "terminal_delisting" and result["finding"]["event_kind"] == "listing_ended"
            if name == "local-ta":
                assert observed["local_fixture"] is not None and result["stats"]["local_queries"] > 0
                assert any(row["corpus"] != "web" for row in result["passages"])
            if name == "web-ta":
                assert result["stats"]["web_actions"] > 0 and result["stats"]["http_requests"] > 0
                assert any(row["corpus"] == "web" for row in result["passages"])
        for filename in ("result.json", "observations.json", "steps.json", "sources.json", "calls.json", "execution-source-manifest.json"):
            path = folder / filename
            if path.exists():
                copy(path, out / "live" / name / filename)
            else:
                assert name not in successes and filename == "execution-source-manifest.json"
        report.append({"name": name, "status": result["status"], "action": result["action"], "stop_reason": result["stop_reason"],
            "failure_code": result["failure_code"], "sdk_submissions": observed["sdk_submissions"], "stats": result["stats"],
            "model": result["execution"]["model"], "final_acceptance": name in successes,
            "source_manifest_present": (folder / "execution-source-manifest.json").is_file()})
    assert successes <= entries.keys(), "All three live acceptance cases are required"
    return report


def secret_scan(files):
    spec = importlib.util.spec_from_file_location("source_packet_scan", PACKET.with_name("2026-09-07-lifecycle-web-sonnet-canary") / "scan_packet.py")
    scanner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scanner)
    result = scanner.scan_files(files)
    for row in result["findings"]:
        fixture = scanner.SYNTHETIC_TEST_FIXTURES.get(row["sha256"])
        path = files[row["file"]]
        if fixture and fixture[0] == row["kind"] and path.suffix in {".xml", ".json"}:
            if any(b"test_redact_scrubs_token_shapes" in line and any(hashlib.sha256(match.group()).hexdigest() == row["sha256"]
                for match in scanner.PATTERNS[row["kind"]].finditer(line)) for line in path.read_bytes().splitlines()):
                row.update(synthetic_named_test_fixture=True, fixture_constant=fixture[1])
    result["unexpected"] = sum(not row["synthetic_named_test_fixture"] for row in result["findings"])
    assert result["unexpected"] == 0, result
    return result


def main(args):
    out = args.output.resolve()
    assert out.is_relative_to(PACKET) and not out.exists(), "New evidence subdirectory required"
    out.mkdir()
    back, front = xml(args.backend), xml(args.frontend)
    green(back)
    green(front)
    prior = verify_prior()
    mutants, sources = collect_mutations(args.mutations, out)
    browser = collect_browser(args.browser, out)
    def entries(values):
        pairs = [(name, Path(path)) for name, path in (entry.split("=", 1) for entry in values)]
        assert len(dict(pairs)) == len(pairs), "Duplicate evidence labels"
        return dict(pairs)
    live = collect_live(entries(args.live), out)
    regressions = collect_regressions(entries(args.regression), out)
    checkpoints = collect_checkpoints(entries(args.checkpoint), out)
    historical_tests = collect_historical_tests(entries(args.historical_test), out)
    build = collect_build(args.build, args.mutations, out)
    producer_check = collect_producer_check(args.producer_check, args.mutations, out)
    copy(args.backend, out / "backend.xml")
    copy(args.frontend, out / "frontend.xml")
    code = {name: sha(source_path(name)) for name in sources if (name.startswith(("src/", "tests/", "data_sources/", "apps/", "resources/"))
        or name in {"requirements.txt", "pyproject.toml", "pytest.ini"}) and not name.startswith("apps/arkscope-web/dist/")}
    before = read(PRIOR / "source-manifest.json")["files"]
    changed = sorted(name for name, digest in code.items() if before.get(name) != digest)
    documents = {**{name: sha(source_path(name)) for name in STATUS_DOCS},
        **{str(path.relative_to(ROOT)): sha(path) for path in (PACKET / "scripts").glob("*") if path.is_file()},
        str((PACKET / "claude_canary.py").relative_to(ROOT)): sha(PACKET / "claude_canary.py")}
    if (PACKET / "README.md").is_file():
        documents[str((PACKET / "README.md").relative_to(ROOT))] = sha(PACKET / "README.md")
    for name in [*changed, *documents]:
        copy(source_path(name), out / "source" / name)
    old_back = xml(PRIOR / "backend-suite-r2.xml")["nodes"]
    old_front = []
    for suite in read(PRIOR / "frontend-suite-r7.json")["testResults"]:
        parts = Path(suite["name"]).parts
        path = Path(*parts[parts.index("apps") + 2:]).as_posix()
        old_front.extend(path + "::" + test["fullName"] for test in suite["assertionResults"])
    ledger = {kind: {"before": len(old), "after": len(new), "added": sorted(set(new) - set(old)), "removed": sorted(set(old) - set(new))}
        for kind, old, new in (("backend", old_back, back["nodes"]), ("frontend", old_front, front["nodes"]))}
    assert not ledger["backend"]["removed"], ledger
    assert set(ledger["frontend"]["removed"]) == SUPERSEDED_FRONTEND_NODES.keys(), ledger
    assert set(SUPERSEDED_FRONTEND_NODES.values()) <= set(ledger["frontend"]["added"]), ledger
    ledger["frontend"]["intentional_replacements"] = SUPERSEDED_FRONTEND_NODES
    new_json(out / "node-changes.json", ledger)
    new_json(out / "source-manifest.json", {"head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "files": {**code, **documents}, "changed_since_prior": changed, "deleted_files": read(PRIOR / "source-manifest.json")["deleted_files"]})
    for name in ("backend", "frontend"):
        value = back if name == "backend" else front
        new_json(out / (name + "-nodes.json"), {"nodes": value["nodes"]})
    report = {"kind": "lifecycle_investigation_completion", "prior": prior,
        "backend": {k: v for k, v in back.items() if k != "nodes"}, "frontend": {k: v for k, v in front.items() if k != "nodes"},
        "mutations": mutants, "browser": browser, "build": build, "live": live,
        "red_regressions": regressions, "historical_mutations": checkpoints, "historical_tests": historical_tests,
        "producer_check": producer_check,
        "total_sdk_submissions": sum(row["sdk_submissions"] for row in live),
        "production_mutations": False, "merged": False, "pushed": False, "production_app_restarted": False}
    new_json(out / "verification.json", report)
    files = {str(path.relative_to(out)): path for path in out.rglob("*") if path.is_file()}
    new_json(out / "secret-shape-scan.json", secret_scan(files))
    new_json(out / "files.sha256.json", {"files": {str(path.relative_to(out)): sha(path) for path in sorted(out.rglob("*")) if path.is_file()}})
    print(json.dumps({**{key: report[key] for key in ("backend", "frontend", "mutations", "browser", "total_sdk_submissions")},
        "seal_sha256": sha(out / "files.sha256.json")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("output", "backend", "frontend", "mutations", "browser", "build", "producer-check"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--live", action="append", required=True, help="review-label=/tmp/authorized-calibration-directory")
    parser.add_argument("--regression", action="append", default=[], help="review-label=/tmp/red-or-disproved-probe.xml")
    parser.add_argument("--checkpoint", action="append", default=[], help="review-label=/tmp/interrupted-mutation-directory")
    parser.add_argument("--historical-test", action="append", default=[], help="review-label=/tmp/non-final-test-report.xml")
    main(parser.parse_args())
