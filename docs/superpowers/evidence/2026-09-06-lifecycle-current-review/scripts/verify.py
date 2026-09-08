"""Current-review admission in isolated source copies, with named mutation owners."""

import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


PACKET = Path(__file__).resolve().parent.parent
PRIOR = PACKET.parent / "2026-09-06-lifecycle-action-review"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


backend_runner = module("current_backend_runner", PACKET.parent / "2026-09-06-recent-price-repair/scripts/run_mutations.py")
ui_runner = module("current_ui_runner", PACKET.parent / "2026-09-06-price-window-and-repair-ui/scripts/run_mutations.py")
CURRENT = "src/security_lifecycle_current.py"
VIEW = "apps/arkscope-web/src/lifecycle/CurrentLifecycleView.tsx"
HOOK = "apps/arkscope-web/src/lifecycle/useLifecycleSourceCheck.ts"
AUDIT = "apps/arkscope-web/src/lifecycle/CurrentLifecycleAudit.tsx"
CONTRACT = "apps/arkscope-web/src/lifecycle/currentReviewContract.ts"
API = "apps/arkscope-web/src/api.ts"
ADDED_FOCUS = {"tests/test_security_lifecycle_current.py", "tests/test_security_lifecycle_current_routes.py",
               "tests/test_security_lifecycle_tools.py", "tests/test_tools.py", "tests/test_agents.py", "tests/test_api.py"}


def edit(path, before, after):
    return {"path": path, "before": before, "after": after}


def mutation(name, owner, *edits):
    return {"name": name, "owner": owner, "edits": edits}


MUTATIONS = {
    "backend": (
        mutation("unknown_sources_are_empty", "test_current_sources_unknown_is_not_an_empty_healthy_universe",
                 edit(CURRENT, "if value is None:\n        return None", "if value is None:\n        return {}")),
        mutation("trust_applied_without_effects", "test_current_projection_checks_actual_effects_not_just_applied_status",
                 edit(CURRENT, 'readiness["expected_state_sha256"] == readiness["observed_state_sha256"]', "True")),
        mutation("schedule_uses_utc", "test_current_review_scheduled_state_uses_new_york_not_utc",
                 edit(CURRENT, 'instant(snapshot["at"]).astimezone(ZoneInfo("America/New_York")).date().isoformat()',
                      'instant(snapshot["at"]).date().isoformat()')),
        mutation("mix_collection_snapshots", "test_source_loader_changes_invalidate_the_read_instead_of_mixing_collection_states",
                 edit(CURRENT, "sources != _sources(service.sources_by_ticker())", "False")),
        mutation("mix_database_snapshots", "test_new_source_observation_between_population_and_receipt_read_is_rejected",
                 edit(CURRENT, 'versions != [conn.execute("PRAGMA data_version").fetchone()[0] for conn in connections]', "False")),
        mutation("reused_ticker_shares_membership", "test_reused_ticker_current_tracking_is_not_assigned_to_historical_security",
                 edit(CURRENT, 'current_sources = [] if sources is None or review.get("historical") else sources.get(ticker, [])',
                      'current_sources = [] if sources is None else sources.get(ticker, [])')),
        mutation("drop_unresolved_reviews", "test_current_reviews_account_for_unpersisted_missing_and_recovered_cases",
                 edit(CURRENT, 'rows = [row for row in result["items"] if (case_id in row["case_ids"]',
                      'rows = [row for row in result["items"] if row["finding"] != "unresolved" and (case_id in row["case_ids"]')),
        mutation("unescaped_audit_path", "test_lazy_audit_uses_the_same_literal_database_as_current_review[%23literal]",
                 edit("src/tools/security_lifecycle_tools.py", 'f"{path.resolve().as_uri()}?mode=ro"', 'f"file:{path.resolve()}?mode=ro"')),
        mutation("trust_bad_confirmation", "test_bad_confirmation_receipt_never_becomes_displayed_success",
                 edit(CURRENT, "        confirmation_for(transition)", "        pass")),
        mutation("unreviewed_reason_is_public", "test_current_closed_vocabulary_is_enforced_before_api_or_research[reason]",
                 edit(CURRENT, 'if reason not in CURRENT_REVIEW_REASONS or action["state"] not in CURRENT_ACTION_STATES:',
                      'if action["state"] not in CURRENT_ACTION_STATES:')),
        mutation("unreviewed_state_is_public", "test_current_closed_vocabulary_is_enforced_before_api_or_research[state]",
                 edit(CURRENT, 'if reason not in CURRENT_REVIEW_REASONS or action["state"] not in CURRENT_ACTION_STATES:',
                      'if reason not in CURRENT_REVIEW_REASONS:')),
        mutation("ignore_exact_case_filter", "test_current_route_case_filter_is_not_silently_ignored",
                 edit("src/api/routes/security_lifecycle.py", "return service.list_current_reviews(at=_utc_now(), view=view, ticker=ticker, case_id=case_id, limit=limit, offset=offset)",
                      "return service.list_current_reviews(at=_utc_now(), view=view, ticker=ticker, case_id=None, limit=limit, offset=offset)")),
        mutation("offer_stale_assessment", "test_changed_observation_does_not_offer_an_old_assessment_as_current",
                 edit(CURRENT, 'if latest["observation_fingerprint_sha256"] != observation_fingerprint(case["observation"]):', "if False:")),
        mutation("active_coverage_never_expires", "test_always_active_coverage_expires_instead_of_staying_green",
                 edit(CURRENT, 'evidence=row["evidence"], today=instant(snapshot["at"]).date(), provider_codes=row["blockers"]',
                      'evidence=row["evidence"], today=instant(row["at"]).date(), provider_codes=row["blockers"]')),
    ),
    "frontend": (
        mutation("cast_current_list", "does not bypass current-list parsing at the real API boundary",
                 edit(API, 'return parseCurrentReviewList(await getJSON<unknown>(`/security-lifecycle/reviews${lifecycleQuery(filters)}`));',
                      'return await getJSON<CurrentLifecycleReviewList>(`/security-lifecycle/reviews${lifecycleQuery(filters)}`);')),
        mutation("hide_unresolved_rows", "keeps unresolved source-only rows visible instead of silently filtering them",
                 edit(VIEW, "<tbody>{page.items.map((row)", '<tbody>{page.items.filter((row) => row.finding !== "unresolved").map((row)')),
        mutation("approved_is_applied", "shows scheduled as distinct from a successful application",
                 edit(VIEW, "copy.states[actionable.state]", "copy.states.applied")),
        mutation("duplicate_confirmation", "sends only one confirmation even for two clicks in the same render",
                 edit(VIEW, "if ((!detail && !activityReverse) || commandLock.current || !command) return;",
                      "if ((!detail && !activityReverse) || !command) return;")),
        mutation("dirty_preview_can_confirm", "invalidates a ready packet immediately when its execution date changes",
                 edit(VIEW, "disabled={disabled || dirty || !packet.ready || error !== null}",
                      "disabled={disabled || !packet.ready || error !== null}")),
        mutation("late_queue_overwrites_current", "keeps only the newest queue response",
                 edit(VIEW, "if (mounted.current && token === listSequence.current) setPage(result);",
                      "if (mounted.current) setPage(result);")),
        mutation("late_detail_overwrites_selection", "keeps only the selected detail response",
                 edit(VIEW, "if (mounted.current && token === detailSequence.current && selected.current === id) setDetail(result.item);",
                      "if (mounted.current) setDetail(result.item);")),
        mutation("late_preview_overwrites_selection", "clears the old preview lock when switching cases and discards its late result",
                 edit(VIEW, "if (!mounted.current || token !== previewSequence.current || selected.current !== id) return;",
                      "if (!mounted.current) return;")),
        mutation("late_activity_overwrites_ack", "does not let a late activity read undo a newer acknowledgement",
                 edit(VIEW, "if (mounted.current && token === activitySequence.current) { setActivities(value.items);",
                      "if (mounted.current) { setActivities(value.items);")),
        mutation("duplicate_acknowledgement", "acknowledges activity at most once and preserves other visible case data",
                 edit(VIEW, "if (commandLock.current) return;", "if (false) return;")),
        mutation("other_case_is_our_completion", "does not use another case's running or completed job as the request receipt",
                 edit(HOOK, 'if (!active && value.telemetry_status === "valid" && newer && belongs)',
                      'if (!active && value.telemetry_status === "valid" && newer)')),
        mutation("stale_result_is_completion", "does not use a stale same-case result as completion of a new request",
                 edit(HOOK, 'if (!active && value.telemetry_status === "valid" && newer && belongs)',
                      'if (!active && value.telemetry_status === "valid" && belongs)')),
        mutation("duplicate_provider_dispatch", "prevents double dispatch before the first promise settles",
                 edit(HOOK, "if (pendingRef.current || dispatchLock.current) return;", "if (pendingRef.current) return;")),
        mutation("read_failure_stops_recovery", "keeps polling a pending request after a read failure without another POST",
                 edit(HOOK, "} catch { if (!cancelled && token === sequence.current) setReadFailed(true); }",
                      "} catch { keepPolling = false; if (!cancelled && token === sequence.current) setReadFailed(true); }")),
        mutation("translation_ignores_content_identity", "does not attach a translation for the wrong content digest",
                 edit(AUDIT, "|| result.locale !== locale || result.evidence_content_sha256 !== original.content_sha256)",
                      "|| result.locale !== locale)")),
        mutation("prefetch_historical_audit", "loads audit only on disclosure and keeps the primary view usable if it fails",
                 edit(AUDIT, "const [requested, setRequested] = useState(false);", "const [requested, setRequested] = useState(true);")),
        mutation("cast_activity_list", "rejects malformed tracking activity before opening its UI",
                 edit(API, 'return parseCurrentActivityList(await getJSON<unknown>(\n    `/security-lifecycle/transition-activity${query ? `?${query}` : ""}`,\n  ));',
                      'return await getJSON<TickerIdentityTransitionActivityResponse>(\n    `/security-lifecycle/transition-activity${query ? `?${query}` : ""}`,\n  );')),
        mutation("acknowledge_wrong_receipt", "binds activity acknowledgement to the requested receipt",
                 edit(API, "if (result.activity_id !== activityId || result.acknowledged_at === null)",
                      "if (result.acknowledged_at === null)")),
        mutation("missing_reason_translation", "has exactly the current review and action vocabulary in en",
                 edit("apps/arkscope-web/src/i18n/resources/en/explore.ts", 'provider_confirmation_missing: "Listing confirmation is missing.", ', "")),
        mutation("unpaired_extra_reason_translation", "has exactly the current review and action vocabulary in en",
                 edit(CONTRACT, '  "provider_confirmation_missing", "source_missing", "active_confirmed",',
                      '  "source_missing", "active_confirmed",')),
        mutation("false_applied_readback", "rejects false applied readbacks and preserves approved, scheduled and blocked states",
                 edit(CONTRACT, '(["applied", "already_applied"].includes(result.status) && (result.current_effects_match !== true || !result.applied_at))', "false")),
        mutation("missing_ack_time_is_success", "does not claim an unacknowledged receipt has been acknowledged",
                 edit(API, "if (result.activity_id !== activityId || result.acknowledged_at === null)",
                      "if (result.activity_id !== activityId)")),
    ),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def check_anchors(repo):
    owners = {node.name for name in ADDED_FOCUS for node in ast.walk(ast.parse((repo / name).read_text()))
              if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    ui_tests = "\n".join(path.read_text() for path in (repo / "apps/arkscope-web/src/lifecycle").glob("*.test.*"))
    for kind, items in MUTATIONS.items():
        for item in items:
            if kind == "backend" and item["owner"].split("[", 1)[0] not in owners:
                raise RuntimeError("mutation_owner_missing:" + item["name"])
            if kind == "frontend" and item["owner"] not in ui_tests and not any(
                    generic in ui_tests and generic.replace("%s", choice) == item["owner"]
                    for generic, choice in (("shows %s as distinct from a successful application", "scheduled"),
                                            ("has exactly the current review and action vocabulary in %s", "en"))):
                raise RuntimeError("mutation_owner_missing:" + item["name"])
            for change in item["edits"]:
                if (repo / change["path"]).read_text().count(change["before"]) != 1:
                    raise RuntimeError("mutation_anchor_not_unique:" + item["name"])
    print(json.dumps({"event": "anchors_checked", "mutations": {key: len(value) for key, value in MUTATIONS.items()}}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--kind", choices=("backend", "frontend"), required=True)
    parser.add_argument("--staging", type=Path)
    parser.add_argument("--temp-root", type=Path)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    check_anchors(repo)
    if args.check_only:
        return
    if args.staging is None or args.temp_root is None:
        parser.error("staging and temp-root are required")
    staging, temporary = args.staging.resolve(), args.temp_root.resolve()
    if (staging == temporary or staging in temporary.parents or temporary in staging.parents
            or any(path == repo or repo in path.parents or path.exists() for path in (staging, temporary))):
        raise RuntimeError("new_external_staging_paths_required")
    os.umask(0o077)
    source, output = staging / "source", staging / "results"
    source.mkdir(parents=True)
    output.mkdir()
    temporary.mkdir(parents=True)
    os.environ["TMPDIR"] = str(temporary)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    names = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=repo).decode().split("\0")
    for name in sorted(set(names) - {""}):
        path = Path(name)
        if (path.parts[0] == "data" or path.name in {".env", ".mcp.json", "CLAUDE.md"}
                or ".claude" in path.parts or not (repo / path).is_file()):
            continue
        target = source / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo / path, target)
    (source / "node_modules").symlink_to(repo / "node_modules", target_is_directory=True)
    focus = sorted(set(json.loads((PRIOR / "focus-files.json").read_text())["files"]) | ADDED_FOCUS)
    integration = sorted(set(json.loads((PRIOR / "integration-files.json").read_text())["files"]) | ADDED_FOCUS)
    changed = set(subprocess.check_output(["git", "diff", "--name-only", "-z"], cwd=repo).decode().split("\0"))
    changed.update(subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=repo).decode().split("\0"))
    inputs = set(json.loads((PRIOR / "source-manifest.json").read_text())["files"]) | changed | set(focus)
    hashes = {name: digest(repo / name) for name in sorted(inputs) if name and not name.startswith("docs/") and (repo / name).is_file()}
    deleted = sorted(name for name in changed if name and not name.startswith("docs/") and not (repo / name).exists())
    if any(digest(source / name) != value for name, value in hashes.items()):
        raise RuntimeError("source_copy_changed")
    report = {"complete": False, "head": head, "kind": args.kind, "code_sha256": hashes, "deleted_files": deleted,
              "focus_files": focus, "integration_files": integration, "mutations": [],
              "frontend_scope": "all_frontend_tests", "frontend_max_workers": 4,
              "temporary_data_on_distinct_filesystem": temporary.stat().st_dev != source.stat().st_dev}

    def run(name, files=None, root=source):
        result = (backend_runner.test_run(sys.executable, root, output, temporary, name, files or focus)
                  if args.kind == "backend" else ui_runner.ui_run(root, output, name, ["--maxWorkers=4"]))
        print(json.dumps({"event": name, **result}), flush=True)
        return result

    report["baseline"] = run("baseline")
    save(output / "report.json", report)
    if report["baseline"]["exit_code"]:
        raise RuntimeError("focus_baseline_failed")
    for item in MUTATIONS[args.kind]:
        originals = {change["path"]: (source / change["path"]).read_bytes() for change in item["edits"]}
        try:
            for change in item["edits"]:
                target = source / change["path"]
                value = target.read_text()
                if value.count(change["before"]) != 1:
                    raise RuntimeError("mutation_anchor_changed")
                target.write_text(value.replace(change["before"], change["after"], 1))
            result = run(item["name"])
        finally:
            for name, value in originals.items():
                (source / name).write_bytes(value)
        result["owner"] = item["owner"]
        result["edits"] = item["edits"]
        result["restored_sha256"] = {name: digest(source / name) for name in originals}
        result["killed_by_owner"] = (result["exit_code"] == 1 and result["counts"]["errors"] == 0
            and result["counts"]["tests"] == report["baseline"]["counts"]["tests"]
            and any(item["owner"] in name for name in result["failed_nodes"]))
        report["mutations"].append(result)
        save(output / "report.json", report)
        if not result["killed_by_owner"] or any(result["restored_sha256"][name] != hashes[name] for name in originals):
            raise RuntimeError("mutation_not_owned_or_restore_failed:" + item["name"])
    report["restored"] = run("restored")
    save(output / "report.json", report)
    if report["restored"]["exit_code"]:
        raise RuntimeError("restored_failed")
    if args.kind == "backend":
        for name, files, root in (("integration", integration, source), ("backend", ["tests"], repo)):
            report[name] = run(name, files, root)
            save(output / "report.json", report)
            if report[name]["exit_code"]:
                raise RuntimeError(name + "_failed")
    if (head != subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
            or any(digest(repo / name) != value or digest(source / name) != value for name, value in hashes.items())
            or any((repo / name).exists() or (source / name).exists() for name in deleted)):
        raise RuntimeError("source_changed_during_admission")
    report["complete"] = True
    save(output / "report.json", report)


if __name__ == "__main__":
    main()
