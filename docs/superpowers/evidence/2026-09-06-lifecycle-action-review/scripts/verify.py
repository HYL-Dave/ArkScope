"""Offline action-review admission; mutations never touch the working source."""

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
PRIOR = PACKET.parent / "2026-09-06-lifecycle-population-reconciliation"
RUNNER = PACKET.parent / "2026-09-06-recent-price-repair/scripts/run_mutations.py"
spec = importlib.util.spec_from_file_location("offline_test_runner", RUNNER)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

REVIEW = "src/security_lifecycle_review.py"
STORE = "src/ticker_identity_transition.py"
INVESTIGATION = "src/security_lifecycle_investigation.py"
SERVICE = "src/ticker_identity_service.py"
ROUTES = "src/api/routes/ticker_identity.py"
PROJECTION = "src/tools/security_lifecycle_tools.py"


def edit(before, after, path=REVIEW):
    return {"before": before, "after": after, "path": path}


def mutation(name, owner, *edits):
    return {"name": name, "owner": owner, "edits": edits}


MUTATIONS = (
    mutation("trust_stale_packet", "test_confirmation_rejects_changed_material_without_accepting_draft[finding]",
        edit('if packet["packet_sha256"] != packet_sha256 or packet["action"] != action:', 'if packet["action"] != action:')),
    mutation("ignore_newer_assessment", "test_newer_assessment_invalidates_review_even_without_new_evidence",
        edit('if latest["assessment_id"] != assessment_id:', 'if False:'),
        edit('"latest_assessment": {"assessment_id": latest["assessment_id"], "revision": latest["revision"]},',
             '"latest_assessment": {"assessment_id": assessment_id, "revision": assessment["revision"]},')),
    mutation("ignore_citation_bytes", "test_citation_material_is_bound_and_integrity_checked[content]",
        edit('digest = hashlib.sha256(row["excerpt"].encode("utf-8")).hexdigest()', 'digest = row["content_sha256"]')),
    mutation("ignore_citation_url", "test_citation_material_is_bound_and_integrity_checked[link]",
        edit('"adapter", "source_url", "title",', '"adapter", "title",')),
    mutation("ignore_proposal_dismissal", "test_dismissed_required_proposal_is_not_offered_as_confirmable",
        edit('blockers.extend(_proposal_vetoes(store, case=case, assessment=assessment, kind=kind))', 'None')),
    mutation("commit_acceptance_early", "test_confirmation_rolls_back_all_staging_before_approval_commit",
        edit('with nullcontext() if _caller_transaction else self.conn:\n            self.conn.execute(\n                "UPDATE security_lifecycle_assessments',
             'with self.conn:\n            self.conn.execute(\n                "UPDATE security_lifecycle_assessments', INVESTIGATION)),
    mutation("commit_proposals_early", "test_confirmation_rolls_back_all_staging_before_approval_commit",
        edit('with nullcontext() if _caller_transaction else self.conn:\n                    self.conn.execute(',
             'with self.conn:\n                    self.conn.execute(', INVESTIGATION)),
    mutation("commit_approval_early", "test_confirmation_rolls_back_all_staging_before_approval_commit",
        edit('            if not _caller_transaction:\n                self.conn.commit()\n        except Exception:\n            self.conn.rollback()\n            raise\n        return self.get(transition_id)\n\n    def approve(',
             '            self.conn.commit()\n        except Exception:\n            self.conn.rollback()\n            raise\n        return self.get(transition_id)\n\n    def approve(', STORE)),
    mutation("commit_effects_early", "test_application_crash_rolls_back_all_effects_but_preserves_the_confirmation",
        edit('self._step("activity_receipt")\n            if not _caller_transaction:\n                self.conn.commit()',
             'self._step("activity_receipt")\n            self.conn.commit()', STORE)),
    mutation("legacy_apply_bypasses_review", "test_legacy_store_apply_cannot_bypass_action_packet_revalidation",
        edit('if "review_confirmation" in transition["approved_preview"]:\n                if not _caller_transaction:',
             'if "review_confirmation" in transition["approved_preview"]:\n                if False:', STORE)),
    mutation("legacy_reapproval_discards_review", "test_legacy_reapproval_cannot_discard_an_action_confirmation[automation_policy-True]",
        edit('if ("review_confirmation" in self.get(transition_id)["approved_preview"]\n'
             '                        and "review_confirmation" not in preview):', 'if False:', STORE)),
    mutation("claim_success_without_readback", "test_lost_readback_reports_unavailable_not_unverified_success",
        edit('return _result(service, transition_id)\n\n\ndef confirm(',
             'return {"status": "applied", "transition_id": transition_id}\n\n\ndef confirm(')),
    mutation("ignore_confirmation_time", "test_confirmation_readback_rejects_tampered_action_binding[confirmed_at]",
        edit('_instant(value["confirmed_at"]) > _instant(transition["approved_at"])', 'False')),
    mutation("bool_is_review_version", "test_confirmation_readback_rejects_tampered_action_binding[packet_version]",
        edit('or type(packet.get("version")) is not int or packet["version"] != REVIEW_VERSION',
             'or packet.get("version") != REVIEW_VERSION')),
    mutation("drop_database_permission", "test_review_api_denial_is_not_partial_acceptance[require_db_write]",
        edit('require_db_write("security_lifecycle_confirm_review", detail)', 'None', ROUTES)),
    mutation("drop_profile_permission", "test_review_api_denial_is_not_partial_acceptance[require_profile_state_write]",
        edit('require_profile_state_write("security_lifecycle_confirm_review", detail)', 'None', ROUTES)),
    mutation("leak_internal_effect_rows", "test_review_projection_has_no_raw_membership_or_future_columns",
        edit('"effects": projected_effects,', '"effects": effects,')),
    mutation("leak_case_confirmation", "test_existing_case_readers_do_not_export_private_confirmation[case_api]",
        edit('projected["approved_preview"] = _project_transition_preview(projected["approved_preview"])',
             'projected["approved_preview"] = projected["approved_preview"]', PROJECTION)),
    mutation("leak_research_confirmation", "test_existing_case_readers_do_not_export_private_confirmation[research]",
        edit('item["ticker_transition"] = _project_transition(item.get("ticker_transition"))', 'None', PROJECTION)),
    mutation("leak_legacy_confirmation", "test_legacy_transition_commands_close_their_response[cancel]",
        edit('def _transition_record(value: dict) -> dict:\n    return {key: value[key] for key in (\n'
             '        "transition_id", "kind", "status", "source_ticker", "successor_ticker",\n'
             '        "execute_on", "approved_preview_sha256", "updated_at",\n    )}',
             'def _transition_record(value: dict) -> dict:\n    return value', ROUTES)),
    mutation("incomplete_attempt_is_completed", "test_legacy_retry_does_not_claim_an_incomplete_review_action_completed",
        edit('if value["status"] not in completed | {"blocked"}:', 'if False:', ROUTES)),
    mutation("break_due_runner_contract", "test_scheduled_review_preserves_due_runner_result_contract[True]",
        edit('return {**result, "transition": store.get(transition_id)}', 'return result', SERVICE)),
    mutation("unescaped_write_path", "test_confirmation_uses_the_selected_literal_database_filename",
        edit('f"{path.resolve().as_uri()}?mode={mode}"', 'f"file:{path.resolve()}?mode={mode}"', SERVICE)),
)

ADDED_FOCUS = {
    "tests/test_security_lifecycle_review.py", "tests/test_security_lifecycle_review_routes.py",
    "tests/test_ticker_identity_scheduler.py", "tests/test_security_lifecycle_automation_scheduler.py",
    "tests/test_security_lifecycle_automation_worker.py", "tests/test_security_lifecycle_decision_policy.py",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def check_anchors(repo):
    owners = {node.name for name in ADDED_FOCUS for node in ast.walk(ast.parse((repo / name).read_text()))
              if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    for item in MUTATIONS:
        if item["owner"].split("[", 1)[0] not in owners:
            raise RuntimeError("mutation_owner_missing:" + item["name"])
        for change in item["edits"]:
            if (repo / change["path"]).read_text().count(change["before"]) != 1:
                raise RuntimeError("mutation_anchor_not_unique:" + item["name"])
    print(json.dumps({"event": "anchors_checked", "mutations": len(MUTATIONS)}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
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
            or any(p == repo or repo in p.parents or p.exists() for p in (staging, temporary))):
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
    if (repo / "node_modules").exists():
        (source / "node_modules").symlink_to(repo / "node_modules", target_is_directory=True)
    focus = sorted(set(json.loads((PRIOR / "focus-files.json").read_text())["files"]) | ADDED_FOCUS)
    integration = sorted(set(json.loads((PRIOR / "integration-files.json").read_text())["files"]) | ADDED_FOCUS)
    changed = set(subprocess.check_output(["git", "diff", "--name-only", "-z"], cwd=repo).decode().split("\0"))
    changed.update(subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=repo).decode().split("\0"))
    inputs = set(json.loads((PRIOR / "source-manifest.json").read_text())["files"]) | changed | set(focus) | {REVIEW, STORE, INVESTIGATION, SERVICE, ROUTES}
    hashes = {name: digest(repo / name) for name in sorted(inputs) if name and not name.startswith("docs/") and (repo / name).is_file()}
    if any(digest(source / name) != value for name, value in hashes.items()):
        raise RuntimeError("source_copy_changed")
    report = {"complete": False, "head": head, "code_sha256": hashes, "focus_files": focus, "integration_files": integration, "mutations": []}

    def run(name, files, root=source):
        result = runner.test_run(sys.executable, root, output, temporary, name, files)
        print(json.dumps({"event": name, **result}), flush=True)
        return result

    report["baseline"] = run("baseline", focus)
    save(output / "report.json", report)
    if report["baseline"]["exit_code"]:
        raise RuntimeError("focus_baseline_failed")
    for item in MUTATIONS:
        originals = {change["path"]: (source / change["path"]).read_bytes() for change in item["edits"]}
        try:
            for change in item["edits"]:
                target = source / change["path"]
                value = target.read_text()
                if value.count(change["before"]) != 1:
                    raise RuntimeError("mutation_anchor_changed")
                target.write_text(value.replace(change["before"], change["after"], 1))
            result = run(item["name"], focus)
        finally:
            for name, value in originals.items():
                (source / name).write_bytes(value)
        result["owner"] = item["owner"]
        result["restored_sha256"] = {name: digest(source / name) for name in originals}
        result["killed_by_owner"] = (result["exit_code"] == 1 and result["counts"]["errors"] == 0
            and result["counts"]["tests"] == report["baseline"]["counts"]["tests"]
            and any(item["owner"] in name for name in result["failed_nodes"]))
        report["mutations"].append(result)
        save(output / "report.json", report)
        if not result["killed_by_owner"] or any(result["restored_sha256"][name] != hashes[name] for name in originals):
            raise RuntimeError("mutation_not_owned_or_restore_failed:" + item["name"])
    for name, files, root in (("restored", focus, source), ("integration", integration, source), ("backend", ["tests"], repo)):
        report[name] = run(name, files, root)
        save(output / "report.json", report)
        if report[name]["exit_code"]:
            raise RuntimeError(name + "_failed")
    if (head != subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
            or any(digest(repo / name) != value or digest(source / name) != value for name, value in hashes.items())):
        raise RuntimeError("source_changed_during_admission")
    report["complete"] = True
    save(output / "report.json", report)


if __name__ == "__main__":
    main()
