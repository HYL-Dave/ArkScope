"""Offline admission in a source-only copy; no live stores or provider tools."""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

PACKET = Path(__file__).resolve().parent.parent
PRIOR = PACKET.parent / "2026-09-06-price-window-and-repair-ui"
BASE = PACKET.parent / "2026-09-06-recent-price-repair/scripts/run_mutations.py"
spec = importlib.util.spec_from_file_location("offline_test_runner", BASE)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
MODULE = "src/security_lifecycle_population.py"
OWNER = "test_population_manifest_accounts_for_all_three_input_populations"


def mutation(name, before, after, owner=OWNER, *, path=MODULE):
    return {"name": name, "owner": owner, "path": path, "before": before, "after": after}


MUTATIONS = [
    mutation("omit_market", 'read_market_observations(str(market), limit=None)', '[]'),
    mutation("omit_profile", '"profile_tables": _rows(profile_conn, PROFILE_TABLE_SQL),',
             '"profile_tables": {**_rows(profile_conn, PROFILE_TABLE_SQL), "security_lifecycle_cases": []},'),
    mutation("omit_provider_history", 'for row in tables[_PREFIX + "provider_checks"]]', 'for row in []]'),
    mutation("counts_instead_of_keys", '    return {\n        "matched": sorted(case_id_for(*key) for key in observed & persisted),',
             '    if len(observed) == len(persisted):\n        persisted = observed\n    return {\n        "matched": sorted(case_id_for(*key) for key in observed & persisted),',
             "test_equal_population_counts_do_not_prove_equal_case_keys"),
    mutation("drop_recovered_active", 'projected = [latest[ticker]["observation"] for ticker in sorted(tracked)]',
             'projected = [latest[ticker]["observation"] for ticker in sorted(tracked) if latest[ticker]["state"] != "active"]'),
    mutation("ignore_concurrent_commit", 'if versions != after or identities != tuple(_identity(path) for path in paths):',
             'if identities != tuple(_identity(path) for path in paths):',
             "test_population_capture_rejects_cross_store_changes_without_blocking_writers"),
    mutation("ignore_file_replacement", 'if versions != after or identities != tuple(_identity(path) for path in paths):',
             'if versions != after:', "test_population_capture_rejects_replaced_database_file"),
    mutation("ignore_capture_digest", 'if snapshot["sha256"] != _digest(unsigned):', 'if False:',
             "test_manifest_builder_rejects_changed_snapshot_and_replays_without_stores"),
    mutation("join_by_issuer_and_ticker", 'else ("listing", *key), []).append(case_id)',
             'else ("listing", key[0], key[-1]), []).append(case_id)',
             "test_consolidation_rejects_issuer_only_or_unproven_listing_identity"),
    mutation("ignore_observation_binding", 'and row["observation_fingerprint_sha256"] == observation_fingerprint(observation)]',
             ']', "test_consolidation_rejects_issuer_only_or_unproven_listing_identity[wrong_observation]"),
    mutation("ignore_filing_time", 'if not filing_date <= as_of <= filing_date + timedelta(days=3):', 'if False:',
             "test_consolidation_rejects_issuer_only_or_unproven_listing_identity[old_filing]"),
    mutation("stale_is_healthy", 'ticker=case["ticker"], evidence=provider["evidence"], today=today,',
             'ticker=case["ticker"], evidence=provider["evidence"], today=instant(provider["at"]).date(),',
             "test_always_active_snapshot_must_not_claim_current_health_after_expiry"),
    mutation("retirement_hides_pending_continuation", 'if review["continuation_state"] == "not_observed":', 'if True:',
             "test_actual_removal_receipt_does_not_erase_unresolved_continuation"),
    mutation("receipt_follows_ticker_not_identity", 'transition["review_id"] = target["review_id"]',
             'transition["review_id"] = by_case[case_id]["review_id"]',
             "test_old_retirement_receipt_does_not_describe_reused_ticker_as_removed"),
    mutation("ignore_receipt_digest", 'if (not isinstance(preview, dict) or preview.get("preview_sha256") != row["approved_preview_sha256"]\n                or profile_snapshot_sha256(preview) != row["approved_preview_sha256"]',
             'if (not isinstance(preview, dict)', "test_receipt_digest_corruption_never_becomes_a_historical_success"),
    mutation("drop_pending_regulator_question", 'def _regulator_question(case, tables, *, today):\n',
             'def _regulator_question(case, tables, *, today):\n    return None\n',
             "test_bound_active_listing_does_not_erase_future_regulator_event"),
    mutation("drop_source_missing_question", 'result["reason"] = "source_missing"',
             'result.update(bucket="history", reason="previously_reviewed")',
             "test_old_accepted_assessment_never_screens_out_a_source_missing_question"),
    mutation("ignore_ticker_reuse", 'if key is not None and current_key is not None and key != current_key:', 'if False:',
             "test_reused_provider_ticker_retains_distinct_historical_identity"),
    mutation("ignore_provider_source_key", 'if row is None or _case_id(row["observation"]) != case["case_id"]:', 'if row is None:',
             "test_provider_source_missing_is_not_recovered_by_a_different_source_ref"),
    mutation("forget_applied_listing_when_snapshot_expires", '_retain_applied_listing(review, latest, today=today)', 'None',
             "test_actual_removal_receipt_does_not_erase_unresolved_continuation"),
    mutation("unescaped_market_store_path", 'f"{path.resolve().as_uri()}?mode=ro"', 'f"file:{path.resolve()}?mode=ro"',
             "test_population_capture_uses_literal_store_paths", path="src/security_lifecycle.py"),
    mutation("unescaped_profile_store_path", 'f"{path.resolve().as_uri()}?mode=ro"', 'f"file:{path.resolve()}?mode=ro"',
             "test_population_capture_uses_literal_store_paths", path="src/security_lifecycle_investigation.py"),
]

FOCUS = [
    "test_security_lifecycle_population", "test_security_lifecycle", "test_security_lifecycle_investigation",
    "test_security_lifecycle_tools", "test_security_lifecycle_routes", "test_security_lifecycle_disposition",
    "test_security_lifecycle_provider_store", "test_security_lifecycle_provider_snapshot", "test_security_lifecycle_provider_authority",
    "test_security_lifecycle_listing_evidence", "test_security_lifecycle_sec_admission", "test_security_lifecycle_schema",
    "test_security_lifecycle_fact_kernel", "test_security_lifecycle_terminal_workflow", "test_security_lifecycle_tracking_policy",
    "test_ticker_identity_transition", "test_ticker_identity_schema", "test_ticker_identity_routes", "test_sa_tracking_memberships",
    "test_active_universe", "test_lifecycle_tracking_and_price_repair_routes",
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def resume_report(output, source, code_hashes, focus, integration):
    raw = (output / "report.json").read_bytes()
    report = json.loads(raw)
    if report.get("complete") or report.get("harness_resume"):
        raise RuntimeError("campaign_not_resumable")
    if report["focus_files"] != focus or report["integration_files"] != integration:
        raise RuntimeError("campaign_scope_changed")
    if any(code_hashes.get(name) != value for name, value in report["code_sha256"].items()):
        raise RuntimeError("campaign_source_changed")
    if any(digest(source / name) != value for name, value in code_hashes.items()):
        raise RuntimeError("campaign_copy_changed")
    added = set(code_hashes) - set(report["code_sha256"])
    if added != {"src/security_lifecycle.py", "src/security_lifecycle_investigation.py"}:
        raise RuntimeError("unexpected_hash_ledger_repair")
    completed = report["mutations"]
    if len(completed) != 21 or report["baseline"]["exit_code"] != 0:
        raise RuntimeError("campaign_checkpoint_changed")
    for item in [report["baseline"], *completed]:
        root = ET.parse(output / (item["name"] + ".xml")).getroot()
        counts = {key: sum(int(suite.get(key, "0")) for suite in root.iter("testsuite"))
                  for key in ("tests", "failures", "errors", "skipped")}
        failed = [row.get("classname", "") + "::" + row.get("name", "") for row in root.iter("testcase")
                  if row.find("failure") is not None or row.find("error") is not None]
        if counts != item["counts"] or failed != item["failed_nodes"]:
            raise RuntimeError("campaign_xml_changed")
    for item, spec in zip(completed, MUTATIONS):
        if (any(item[key] != spec[key] for key in ("name", "path", "owner"))
                or item["exit_code"] != 1 or not item["killed_by_owner"] or item["counts"]["errors"]
                or item["counts"]["tests"] != report["baseline"]["counts"]["tests"]
                or not any(item["owner"] in node for node in item["failed_nodes"])
                or item["restored_sha256"] != code_hashes[item["path"]]):
            raise RuntimeError("campaign_mutation_changed")
    with (output / "report.before-harness-repair.json").open("xb") as stream:
        stream.write(raw)
    report["harness_resume"] = {
        "reason": "nested_reader_hashes_omitted_from_ledger",
        "original_report_sha256": hashlib.sha256(raw).hexdigest(),
        "completed_mutations": len(completed), "product_source_changed": False,
        "current_and_original_copy_verified": True,
        "newly_recorded_hashes": {name: code_hashes[name] for name in sorted(added)},
    }
    report["code_sha256"] = code_hashes
    save(output / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser()
    for name in ("repo", "staging", "temp-root"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    repo, staging, temporary = args.repo.resolve(), args.staging.resolve(), args.temp_root.resolve()
    if any(path == repo or repo in path.parents or (path.exists() and not args.resume) for path in (staging, temporary)):
        raise RuntimeError("new_external_staging_paths_required")
    os.umask(0o077)
    source, output = staging / "source", staging / "results"
    if args.resume:
        if not all(path.is_dir() for path in (source, output, temporary)):
            raise RuntimeError("campaign_checkpoint_missing")
    else:
        source.mkdir(parents=True)
        output.mkdir()
        temporary.mkdir()
    names = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=repo).decode().split("\0")
    for name in (() if args.resume else sorted(set(names) - {""})):
        path = Path(name)
        if path.parts[0] == "data" or path.name in {".env", ".mcp.json", "CLAUDE.md"} or ".claude" in path.parts or not (repo / path).is_file():
            continue
        target = source / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo / path, target)
    if not args.resume and (repo / "node_modules").exists():
        (source / "node_modules").symlink_to(repo / "node_modules", target_is_directory=True)
    focus = sorted("tests/" + name + ".py" for name in FOCUS)
    integration = sorted(set(json.loads((PRIOR / "integration-files.json").read_text())["files"]) | {"tests/test_security_lifecycle_population.py"})
    input_files = set(json.loads((PRIOR / "source-manifest.json").read_text())["files"]) | {MODULE, "tests/test_security_lifecycle_population.py", "src/tools/security_lifecycle_tools.py"}
    input_files.update(item["path"] for item in MUTATIONS)
    code_hashes = {name: digest(repo / name) for name in sorted(input_files) if not name.startswith("docs/")}
    changed = set(subprocess.check_output(["git", "diff", "--name-only", "-z"], cwd=repo).decode().split("\0"))
    changed.update(subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=repo).decode().split("\0"))
    if any(name and not name.startswith("docs/") and name not in code_hashes for name in changed):
        raise RuntimeError("changed_source_missing_from_hash_ledger")
    report = {"focus_files": focus, "integration_files": integration, "code_sha256": code_hashes, "mutations": []}
    def run(name, files, root=source):
        result = runner.test_run(sys.executable, root, output, temporary, name, files)
        save(output / "report.json", report)
        print(json.dumps({"event": name, **result}), flush=True)
        return result
    if args.resume:
        report = resume_report(output, source, code_hashes, focus, integration)
        print(json.dumps({"event": "harness_resume", **report["harness_resume"]}), flush=True)
    else:
        if any(digest(source / name) != value for name, value in code_hashes.items()):
            raise RuntimeError("campaign_copy_changed")
        report["baseline"] = run("baseline", focus)
    save(output / "report.json", report)
    if report["baseline"]["exit_code"]:
        raise RuntimeError("focus_baseline_failed")
    for item in MUTATIONS[len(report["mutations"]):]:
        target = source / item["path"]
        original = target.read_text()
        if original.count(item["before"]) != 1:
            raise RuntimeError("mutation_anchor_not_unique:" + item["name"])
        try:
            target.write_text(original.replace(item["before"], item["after"], 1))
            result = run(item["name"], focus)
        finally:
            target.write_text(original)
        result["owner"] = item["owner"]
        result["path"] = item["path"]
        result["killed_by_owner"] = (result["exit_code"] == 1 and result["counts"]["errors"] == 0
            and result["counts"]["tests"] == report["baseline"]["counts"]["tests"]
            and any(item["owner"] in node for node in result["failed_nodes"]))
        result["restored_sha256"] = digest(target)
        report["mutations"].append(result)
        save(output / "report.json", report)
        if not result["killed_by_owner"] or result["restored_sha256"] != code_hashes[item["path"]]:
            raise RuntimeError("mutation_owner_survived_or_restore_failed:" + item["name"])
    for name, files, root in (("restored", focus, source), ("integration", integration, source), ("backend", ["tests"], repo)):
        report[name] = run(name, files, root)
        save(output / "report.json", report)
        if report[name]["exit_code"]:
            raise RuntimeError(name + "_failed")
    if any(digest(repo / name) != expected for name, expected in code_hashes.items()):
        raise RuntimeError("source_changed_during_verification")
    report["complete"] = True
    save(output / "report.json", report)


if __name__ == "__main__":
    main()
