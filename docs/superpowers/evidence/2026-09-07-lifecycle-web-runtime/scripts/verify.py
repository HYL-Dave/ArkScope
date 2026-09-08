"""Source-bound offline admission; mutations run against the whole affected set."""

import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


PACKET = Path(__file__).resolve().parent.parent
PRIOR = PACKET.parent / "2026-09-06-lifecycle-current-review"


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


backend = module("runtime_backend", PACKET.parent / "2026-09-06-recent-price-repair/scripts/run_mutations.py")
frontend = module("runtime_frontend", PACKET.parent / "2026-09-06-price-window-and-repair-ui/scripts/run_mutations.py")
foundation = module("runtime_foundation", PACKET.parent / "2026-09-06-lifecycle-web-foundation/scripts/verify.py")
MODELS = "src/auth_drivers/lifecycle_web_models.py"
CODEX = "src/auth_drivers/lifecycle_web_codex.py"
CLAUDE = "src/auth_drivers/lifecycle_web_claude.py"
CONTROLLER = "src/lifecycle_web_controller.py"
REVIEW = "src/lifecycle_web_review.py"
API = "apps/arkscope-web/src/api.ts"
VIEW = "apps/arkscope-web/src/lifecycle/LifecycleWebPanel.tsx"
CONTRACT = "apps/arkscope-web/src/lifecycle/webContract.ts"


def mutation(name, owner, path, before, after):
    return {"name": name, "owner": owner, "path": path, "before": before, "after": after}


MUTATIONS = {
    "backend": tuple(item for item in foundation.MUTATIONS if item["name"] in {
        "unknown_auth_falls_back", "model_admission_ignored", "changed_billing_accepted", "mixed_private_dns_allowed",
    }) + (
        mutation("openai_ambient_headers", "test_real_api_sdk_serialization_keeps_selected_key_and_basic_search[openai]", MODELS,
                 "    client._custom_headers = {}\n    return client\n\n\ndef _anthropic_client",
                 "    return client\n\n\ndef _anthropic_client"),
        mutation("anthropic_ambient_headers", "test_real_api_sdk_serialization_keeps_selected_key_and_basic_search[anthropic]", MODELS,
                 "    client.auth_token = None\n    client._custom_headers = {}", "    client.auth_token = None"),
        mutation("claude_missing_auth_is_verified", "test_claude_web_rejects_changed_init_and_never_falls_back", CLAUDE,
                 "        require_subscription_auth_source(data)", "        pass"),
        mutation("claude_default_tool_surface", "test_claude_oauth_web_uses_exact_bundled_scope_and_subscription_witness", CLAUDE,
                 "tools=tools, allowed_tools=tools", "tools=None, allowed_tools=tools"),
        mutation("codex_missing_model_is_entitled", "test_codex_web_invalid_preflight_never_dispatches_a_model", CODEX,
                 'if any(row["model"] == model for row in rows):', "if True:"),
        mutation("codex_config_not_verified", "test_codex_web_invalid_preflight_never_dispatches_a_model", CODEX,
                 '        validate_web_codex_configuration(config.get("config"), purpose)', "        pass"),
        mutation("credential_change_not_checked", "test_changed_credential_generation_is_rejected_before_model_reservation", CONTROLLER,
                 'if row.get("credential_generation") is not None and row["credential_generation"] != credential.generation:', "if False:"),
        mutation("stop_during_refresh_ignored", "test_stop_during_oauth_refresh_prevents_late_model_dispatch", CONTROLLER,
                 '                raise WebModelError("selected_credential_changed")\n            if worker.control.stop_state != "running":',
                 '                raise WebModelError("selected_credential_changed")\n            if False:'),
        mutation("orphan_claims_running", "test_restart_read_reports_expired_lease_without_restarting_or_spending", "src/lifecycle_web_projection.py",
                 'if status in RUNNING and instant(row["lease_until"]) <= instant(at):', "if False:"),
        mutation("unknown_remote_work_succeeds", "test_completed_result_requires_all_owned_remote_terminals", "src/lifecycle_web_store.py",
                 'if calls != {"search-1": "completed", "analysis-1": "completed"}:', "if False:"),
        mutation("central_writer_without_confirmation", "test_central_writer_rejects_forged_web_authority_even_with_recomputed_preview_digest", REVIEW,
                 "if require_confirmation and not isinstance(confirmation, dict):", "if False:"),
        mutation("positive_otc_veto_lost", "test_current_active_otc_veto_is_not_lost_when_other_provider_requests_failed", REVIEW,
                 'row.get("listing_status") == "active" and instant(at)', 'False and instant(at)'),
        mutation("changed_review_is_accepted", "test_web_confirmation_rejects_changed_material_without_partial_human_adoption", REVIEW,
                 'if packet["packet_sha256"] != packet_sha256 or packet["action"] != action:', 'if packet["action"] != action:'),
        mutation("partial_human_adoption_commits", "test_web_adoption_cannot_survive_an_approval_failure_in_a_partial_transaction", REVIEW,
                 '                    at=at, _caller_transaction=True,\n                )', '                    at=at, _caller_transaction=False,\n                )'),
        mutation("backup_can_be_overwritten", "test_web_installation_rejects_changed_approval_and_never_overwrites_a_backup", "src/lifecycle_web_migration.py",
                 "os.O_WRONLY | os.O_CREAT | os.O_EXCL", "os.O_WRONLY | os.O_CREAT | os.O_TRUNC"),
        mutation("web_journal_disappears_from_retention", "test_population_retains_web_sources_and_human_adoption_without_exporting_pages_or_credentials", "src/security_lifecycle_population.py",
                 '"web_journal_inventory": read_web_inventory(profile_conn),', '"web_journal_inventory": None,'),
        mutation("sec_governor_not_used", "test_sec_sources_reuse_reviewed_identity_and_governor_on_every_redirect", "src/lifecycle_web_sec_sources.py",
                 "            governor.reserve_request_start(check=poll)", "            pass"),
        mutation("contradiction_is_actionable", "test_incomplete_web_finding_is_readable_but_has_no_action", "src/security_lifecycle_web_finding.py",
                 'if finding.contradictions or "contradiction" in support:', 'if "contradiction" in support:'),
        mutation("production_oauth_refresh_unwired", "test_production_web_worker_wires_scoped_refresh_only_when_an_expired_token_is_loaded", "src/api/routes/lifecycle_web.py",
                 'refresh_chatgpt=lambda **kwargs: refresh_if_needed(**kwargs, observation_store=get_oauth_observation_store()))', 'refresh_chatgpt=None)'),
    ),
    "frontend": (
        mutation("cast_web_read", "validates Web run shape at the actual read boundary and never dispatches on read", API,
                 'const result = parseWebRun(await getJSON<unknown>(`/security-lifecycle/web-runs/${encodeURIComponent(runId)}`));',
                 'const result = await getJSON<any>(`/security-lifecycle/web-runs/${encodeURIComponent(runId)}`);'),
        mutation("latest_journal_wrong_case", "binds Web reads and cancellation receipts to the exact requested run or case", API,
                 "if (result && result.case_id !== caseId) return invalidCurrentPayload();", "if (false) return invalidCurrentPayload();"),
        mutation("start_receipt_not_parsed", "validates an explicit Web start receipt without retrying malformed success", API,
                 'return parseWebStart(await sendJSON<unknown>(`/security-lifecycle/cases/${encodeURIComponent(caseId)}/web-runs`, "POST", body));',
                 'return await sendJSON<any>(`/security-lifecycle/cases/${encodeURIComponent(caseId)}/web-runs`, "POST", body);'),
        mutation("confirmation_date_not_bound", "checks the exact Web confirmation receipt and never turns a rejection into another execution", API,
                 '    { packet_sha256: packet.packet_sha256, action: packet.action, ...packet.options }));\n  if (result.case_id !== packet.case_id || result.packet_sha256 !== packet.packet_sha256 || result.action !== packet.action\n      || result.source_ticker !== packet.source_ticker || result.execute_on !== packet.execute_on) return invalidCurrentPayload();',
                 '    { packet_sha256: packet.packet_sha256, action: packet.action, ...packet.options }));\n  if (result.case_id !== packet.case_id || result.packet_sha256 !== packet.packet_sha256 || result.action !== packet.action\n      || result.source_ticker !== packet.source_ticker) return invalidCurrentPayload();'),
        mutation("dirty_web_packet_can_confirm", "invalidates Web confirmation immediately when its reviewed execution date changes", VIEW,
                 "disabled={busy || dirty || !packet.ready}", "disabled={busy || !packet.ready}"),
        mutation("other_case_journal_is_ours", "keeps validated Web findings in current detail but rejects malformed or cross-case journals",
                 "apps/arkscope-web/src/lifecycle/currentReviewContract.ts",
                 "web_runs.some((run) => !item.case_ids.includes(run.case_id) || run.ticker !== item.ticker)",
                 "web_runs.some((run) => run.ticker !== item.ticker)"),
        mutation("missing_status_vocabulary", "covers every Web state in both languages without inventing a state label", CONTRACT,
                 '"cancelling", "succeeded", "failed", "cancelled", "remote_outcome_unknown"] as const;',
                 '"cancelling", "succeeded", "failed", "cancelled"] as const;'),
        mutation("extra_status_vocabulary", "covers every Web state in both languages without inventing a state label", CONTRACT,
                 '"cancelling", "succeeded", "failed", "cancelled", "remote_outcome_unknown"] as const;',
                 '"cancelling", "succeeded", "failed", "cancelled", "remote_outcome_unknown", "imagined_status"] as const;'),
        mutation("cancel_ack_is_cancelled", "cancel acknowledgment stays pending, then an unknown outcome stays visible without retry", VIEW,
                 'try { const next = await cancelLifecycleWebRun(run.run_id); if (alive.current) setRun(next); }',
                 'try { const next = await cancelLifecycleWebRun(run.run_id); if (alive.current) setRun({ ...next, status: "cancelled" }); }'),
        mutation("stop_request_is_terminal_en", "cancel acknowledgment stays pending, then an unknown outcome stays visible without retry",
                 "apps/arkscope-web/src/i18n/resources/en/explore.ts",
                 '"stop_requested": "Stop was requested."', '"stop_requested": "Investigation was stopped."'),
        mutation("stop_request_is_terminal_zh", "cancel acknowledgment stays pending, then an unknown outcome stays visible without retry",
                 "apps/arkscope-web/src/i18n/resources/zh-Hant/explore.ts",
                 '"stop_requested": "\u5df2\u8981\u6c42\u505c\u6b62\u8abf\u67e5\u3002"',
                 '"stop_requested": "\u8abf\u67e5\u5df2\u505c\u6b62\u3002"'),
    ),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def recheck_frontend_restored(repo, stage, temporary):
    source, output = stage / "source", stage / "results"
    report = json.loads((output / "report.json").read_text())
    if (report["complete"] or report["kind"] != "frontend" or report["restored"]["exit_code"] != 1
            or report["restored"]["counts"]["errors"] or report["baseline"]["exit_code"] != 0
            or [item["edit"] for item in report["mutations"]] != list(MUTATIONS["frontend"])
            or not all(item["killed_by_owner"] for item in report["mutations"])):
        raise RuntimeError("restored_recheck_requires_completed_owned_mutations")

    def unchanged():
        if (subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip() != report["head"]
                or any(digest(repo / name) != value or digest(source / name) != value
                       for name, value in report["source_sha256"].items())
                or any((repo / name).exists() or (source / name).exists() for name in report["deleted_files"])):
            raise RuntimeError("restored_recheck_source_changed")

    unchanged()
    history = report.get("restored_attempts", [])
    name = f"restored-recheck-{len(history) + 1}"
    if any((output / (name + extension)).exists() for extension in (".json", ".log", "-typecheck.log")):
        raise RuntimeError("restored_recheck_output_exists")
    os.environ["TMPDIR"] = str(temporary)
    result = frontend.ui_run(source, output, name, ["--maxWorkers=4"])
    report["restored_attempts"] = [*history, report["restored"]]
    report["restored"] = result
    save(output / "report.json", report)
    print(json.dumps({"event": name, **result}), flush=True)
    if result["exit_code"] or result["counts"] != report["baseline"]["counts"]:
        raise RuntimeError("restored_recheck_failed")
    command = ["node", str(source / "node_modules/typescript/bin/tsc"), "-b"]
    check = subprocess.run(command, cwd=source / "apps/arkscope-web", capture_output=True, text=True, timeout=180)
    (output / (name + "-typecheck.log")).write_text(check.stdout + check.stderr)
    report["typecheck"] = {"exit_code": check.returncode}
    save(output / "report.json", report)
    if check.returncode:
        raise RuntimeError("typecheck_failed")
    unchanged()
    report["complete"] = True
    save(output / "report.json", report)


def run_backend(root, output, temporary, name, files):
    if files == ["tests"]:
        return backend.test_run(sys.executable, root, output, temporary, name, files)
    chunks = [files[index::4] for index in range(4)]
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(backend.test_run, sys.executable, root, output, temporary, f"{name}-shard-{index}", chunk)
                   for index, chunk in enumerate(chunks)]
        shards = [{**future.result(), "files": chunk} for future, chunk in zip(futures, chunks)]
    assert sorted(item for chunk in chunks for item in chunk) == sorted(files)
    combined = ET.Element("testsuites")
    for shard in shards:
        combined.extend(ET.parse(output / (shard["name"] + ".xml")).getroot().findall("testsuite"))
    ET.ElementTree(combined).write(output / (name + ".xml"), encoding="utf-8", xml_declaration=True)
    return {"name": name, "exit_code": max(shard["exit_code"] for shard in shards),
            "counts": {key: sum(shard["counts"][key] for shard in shards) for key in ("tests", "failures", "errors", "skipped")},
            "failed_nodes": [node for shard in shards for node in shard["failed_nodes"]],
            "duration_seconds": round(time.monotonic() - started, 3), "shards": shards}


def inputs(repo):
    extra = {str(path.relative_to(repo)) for pattern in ("test_lifecycle_web*.py", "test_security_lifecycle_web*.py", "test_codex_web*.py")
             for path in (repo / "tests").glob(pattern)}
    extra |= foundation.ADDED | {"tests/test_sec_transport.py", "tests/test_chatgpt_oauth_login.py"}
    focus = sorted(set(json.loads((PRIOR / "focus-files.json").read_text())["files"]) | extra)
    integration = sorted(set(json.loads((PRIOR / "integration-files.json").read_text())["files"]) | extra)
    owners = {node.name for name in focus for node in ast.walk(ast.parse((repo / name).read_text()))
              if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    ui = "\n".join(path.read_text() for path in (repo / "apps/arkscope-web/src/lifecycle").glob("*.test.*"))
    for kind, mutations in MUTATIONS.items():
        for item in mutations:
            if (item["owner"].split("[", 1)[0] not in owners if kind == "backend" else item["owner"] not in ui):
                raise RuntimeError("mutation_owner_missing:" + item["name"])
            if (repo / item["path"]).read_text().count(item["before"]) != 1:
                raise RuntimeError("mutation_anchor_not_unique:" + item["name"])
    print(json.dumps({"event": "anchors_checked", "mutations": {key: len(value) for key, value in MUTATIONS.items()}}), flush=True)
    return focus, integration


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--kind", choices=("backend", "frontend"), required=True)
    parser.add_argument("--staging", type=Path)
    parser.add_argument("--temp-root", type=Path)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--recheck-restored", action="store_true")
    args = parser.parse_args()
    repo = args.repo.resolve()
    focus, integration = inputs(repo)
    if args.check_only:
        return
    if args.staging is None or args.temp_root is None:
        parser.error("staging and temp-root are required")
    stage, temporary = args.staging.resolve(), args.temp_root.resolve()
    if args.recheck_restored:
        if (args.kind != "frontend" or not stage.is_dir() or not temporary.is_dir()
                or stage == repo or repo in stage.parents or temporary == repo or repo in temporary.parents):
            raise RuntimeError("restored_recheck_requires_existing_external_frontend_stage")
        recheck_frontend_restored(repo, stage, temporary)
        return
    if (stage == temporary or stage in temporary.parents or temporary in stage.parents
            or any(path.exists() or path == repo or repo in path.parents for path in (stage, temporary))):
        raise RuntimeError("new_external_staging_paths_required")
    os.umask(0o077)
    source, output = stage / "source", stage / "results"
    source.mkdir(parents=True)
    output.mkdir()
    temporary.mkdir(parents=True)
    os.environ["TMPDIR"] = str(temporary)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    names = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=repo).decode().split("\0")
    hashes, deleted = {}, []
    for name in sorted(set(names) - {""}):
        path = Path(name)
        if path.parts[0] == "data" or path.name in {".env", ".mcp.json", "CLAUDE.md"} or ".claude" in path.parts:
            continue
        if not (repo / path).is_file():
            deleted.append(name)
            continue
        target = source / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo / path, target)
        if not name.startswith("docs/"):
            hashes[name] = digest(target)
    (source / "node_modules").symlink_to(repo / "node_modules", target_is_directory=True)
    report = {"complete": False, "kind": args.kind, "head": head, "source_sha256": hashes, "deleted_files": deleted,
              "focus_files": focus, "integration_files": integration, "mutations": [], "provider_calls": 0,
              "frontend_scope": "all_frontend_tests", "backend_focus_shards": 4,
              "full_backend_scope": "single_process_worktree_with_existing_autouse_temp_database_isolation"}

    def run(name, files=None, root=source):
        result = (run_backend(root, output, temporary, name, files or focus) if args.kind == "backend"
                  else frontend.ui_run(root, output, name, ["--maxWorkers=4"]))
        print(json.dumps({"event": name, **{key: value for key, value in result.items() if key != "shards"}}), flush=True)
        return result

    report["baseline"] = run("baseline")
    save(output / "report.json", report)
    if report["baseline"]["exit_code"]:
        raise RuntimeError("baseline_failed")
    for item in MUTATIONS[args.kind]:
        target = source / item["path"]
        original = target.read_bytes()
        try:
            if original.decode().count(item["before"]) != 1:
                raise RuntimeError("mutation_anchor_changed")
            target.write_text(original.decode().replace(item["before"], item["after"], 1))
            result = run(item["name"])
        finally:
            target.write_bytes(original)
        result.update(owner=item["owner"], edit=item, restored_sha256=digest(target))
        result["killed_by_owner"] = (result["exit_code"] == 1 and result["counts"]["errors"] == 0
            and result["counts"]["tests"] == report["baseline"]["counts"]["tests"]
            and any(item["owner"] in node for node in result["failed_nodes"]))
        report["mutations"].append(result)
        save(output / "report.json", report)
        if not result["killed_by_owner"] or digest(target) != hashes[item["path"]]:
            raise RuntimeError("mutation_not_owned_or_not_restored:" + item["name"])
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
    else:
        command = ["node", str(source / "node_modules/typescript/bin/tsc"), "-b"]
        check = subprocess.run(command, cwd=source / "apps/arkscope-web", capture_output=True, text=True, timeout=180)
        (output / "typecheck.log").write_text(check.stdout + check.stderr)
        report["typecheck"] = {"exit_code": check.returncode}
        save(output / "report.json", report)
        if check.returncode:
            raise RuntimeError("typecheck_failed")
    if (head != subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
            or any(digest(repo / name) != value or digest(source / name) != value for name, value in hashes.items())
            or any((repo / name).exists() or (source / name).exists() for name in deleted)):
        raise RuntimeError("source_changed_during_admission")
    report["complete"] = True
    save(output / "report.json", report)


if __name__ == "__main__":
    main()
