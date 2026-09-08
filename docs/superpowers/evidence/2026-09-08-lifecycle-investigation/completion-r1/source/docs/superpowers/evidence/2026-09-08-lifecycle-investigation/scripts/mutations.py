"""Run named negative mutations against frozen full focused sets in a disposable copy."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent.parent
SEALED_FIXTURES = (
    "docs/superpowers/evidence/2026-09-04-lifecycle-provider-authority-shadow-census/",
    "docs/superpowers/evidence/2026-08-25-trusted-lifecycle-automation-real-source-canary/",
)


def mutation(name, path, old, new, owner):
    return {"name": name, "path": path, "old": old, "new": new, "owner": owner}


BACKEND = [
    mutation("entity_definition_borrows_security_identity", "src/lifecycle_investigation/findings.py",
        "for term in _defined_security_terms(part, finding.security_class, finding.venue)}",
        "for term in re.findall(r'[\"\\u201c]([A-Za-z][A-Za-z ]{2,70})[\"\\u201d]', part)}",
        "test_only_security_qualified_definitions_bind_event_aliases"),
    mutation("valid_security_definition_ignored", "src/lifecycle_investigation/findings.py",
        "for term in _defined_security_terms(part, finding.security_class, finding.venue)}",
        "for term in ()}",
        "test_only_security_qualified_definitions_bind_event_aliases"),
    mutation("nominal_value_normalization_erases_named_share_class", "src/lifecycle_investigation/findings.py",
        'name = _PAR_VALUE_SUFFIX.sub("", name.strip())',
        'name = re.sub(r"^Class [A-Za-z0-9]+\\s+", "", _PAR_VALUE_SUFFIX.sub("", name.strip()), flags=re.I)',
        "test_par_value_normalization_never_discards_security_class"),
    mutation("par_value_mistaken_for_share_class", "src/lifecycle_investigation/findings.py",
        'name = _PAR_VALUE_SUFFIX.sub("", name.strip())', 'name = name.strip()',
        "test_par_value_does_not_change_common_stock_event_identity"),
    mutation("rejected_candidate_lost_between_corrections", "src/lifecycle_investigation/agent.py",
        '"candidate": step.finding.model_dump()', '"candidate": None',
        "test_grounding_feedback_preserves_candidate_for_targeted_correction"),
    mutation("fragment_count_starves_short_notice", "src/lifecycle_investigation/sources.py",
        'complete = limit is None and offset == 0 and len(source["text"]) <= 12 * 2000', 'complete = False',
        "test_small_fragmented_notice_initial_context_preserves_complete_document"),
    mutation("read_query_accepted_but_ignored", "src/lifecycle_investigation/agent.py",
        'last_feedback = await read_url(step.url, query=step.query)', 'last_feedback = await read_url(step.url)',
        "test_search_candidates_survive_rejected_action_and_read_query_is_consumed"),
    mutation("search_date_hints_accepted_but_ignored", "src/lifecycle_investigation/agent.py",
        '"publication_window_hint": {"since": step.since, "until": step.until}',
        '"publication_window_hint": {"since": None, "until": None}',
        "test_search_candidates_survive_rejected_action_and_read_query_is_consumed"),
    mutation("observed_search_candidates_disappear_after_error", "src/lifecycle_investigation/agent.py",
        '"web_candidates": list(web_candidates.values())', '"web_candidates": []',
        "test_search_candidates_survive_rejected_action_and_read_query_is_consumed"),
    mutation("adopted_finding_offered_as_new_action", "src/lifecycle_investigation/controller.py",
        ' and not row["adopted"]', "",
        "test_target_routes_read_and_adopt_without_dispatch_or_legacy_queue"),
    mutation("current_reverse_readiness_not_projected", "src/ticker_identity_service.py",
        'item["reverse_readiness"] = readiness_by_transition[transition_id]', "pass",
        "test_investigation_activity_reports_current_reverse_readiness_without_legacy_cases[none]"),
    mutation("provider_preview_attempts_auto_approval", "src/lifecycle_investigation/provider_review.py",
        "transition_mutation_allowed=lambda: False", "transition_mutation_allowed=lambda: True",
        "test_structured_provider_review_needs_no_llm_or_new_provider_read_and_keeps_confirmation_separate[2025-01-15]"),
    mutation("success_without_owned_conclusion", "src/lifecycle_investigation/store.py",
        "self._require_success(conn, run_id, payload)", "pass",
        "test_success_requires_a_completed_owned_conclusion"),
    mutation("unknown_remote_reported_cancelled", "src/lifecycle_investigation/store.py",
        "if pending:\n                status, failure_code", "if False:\n                status, failure_code",
        "test_unknown_remote_is_not_reported_cancelled_or_successful"),
    mutation("skip_post_credential_stop_and_permission", "src/lifecycle_investigation/controller.py",
        '            self.before_dispatch()\n            if worker.control.stop_state != "running":\n                raise WebModelError("stop_requested")\n', "",
        "test_pre_dispatch_rereads_stop_identity_and_permission_after_credential_load"),
    mutation("malformed_runtime_becomes_default", "src/lifecycle_investigation/runtime.py",
        "            install_runtime(conn)  # Existing tables are verified; a read never creates one.\n", "",
        "test_runtime_existing_malformed_empty_table_is_not_a_default"),
    mutation("changed_candidate_read_as_original", "src/lifecycle_investigation/news.py",
        "if row is None or _metadata(row, kind) != admitted:", "if row is None:",
        "test_archived_or_reidentified_candidate_cannot_be_used_as_the_original_source"),
    mutation("unsupplied_citations_admitted", "src/lifecycle_investigation/findings.py",
        "elif citation.passage_id not in supplied:", "elif False:",
        "test_unsupplied_or_changed_passage_never_authorizes_action"),
    mutation("debt_borrows_stock_definition", "src/lifecycle_investigation/findings.py",
        'target_citations = [(item, claims) for item, claims in citations if item["source_id"] in identities and\n        (_security_class(item["text"], finding.security_class) or\n         any(_contains(item["text"], term) for term in definitions.get(item["source_id"], ())))]',
        'target_citations = [(item, claims) for item, claims in citations if item["source_id"] in identities]',
        "test_real_ta_notice_requires_its_stock_definition_and_wrapped_event_date[different_security]"),
    mutation("unrelated_sentence_borrows_date", "src/lifecycle_investigation/findings.py",
        '''and not re.search(r'[.!?]["\\u201d)]*$', event_item["text"].strip())):''', "and True):",
        "test_real_ta_notice_requires_its_stock_definition_and_wrapped_event_date[unrelated_date]"),
    mutation("positive_active_evidence_not_vetoed", "src/lifecycle_web_review.py",
        'blockers.add("web_active_listing_conflict")', "pass",
        "test_fresh_active_provider_evidence_is_not_waived_by_source_gap_acknowledgement"),
    mutation("external_market_dependency_deleted", "src/lifecycle_investigation/disposal.py",
        'def market_dependency(conn, observation):\n    owned =', 'def market_dependency(conn, observation):\n    return False\n    owned =',
        "test_market_dependencies_are_retained_before_profile_disposal"),
    mutation("market_deleted_before_profile_receipt", "src/lifecycle_investigation/disposal.py",
        'if _receipt(profile, approval_sha256, "profile") is None:', "if False:",
        "test_disposal_market_stage_requires_profile_receipt_and_receipts_cannot_be_forged"),
    mutation("calibration_source_hash_not_verified", "docs/superpowers/evidence/2026-09-08-lifecycle-investigation/claude_canary.py",
        'if source["text_sha256"] != original["text_sha256"]:', "if False:",
        "test_live_calibration_rejects_changed_local_fixture_before_creating_corpus"),
]

FRONTEND = [
    mutation("removed_target_offers_provider_removal", "apps/arkscope-web/src/lifecycle/InvestigationView.tsx",
        ' || preflight?.reason === "target_not_tracked"', "",
        "keeps a removed target readable without offering another provider removal"),
    mutation("reverse_does_not_refresh_tracked_targets", "apps/arkscope-web/src/lifecycle/InvestigationView.tsx",
        'await read(); if (r.status !== "reversed") throw new Error("review_changed"); onChanged();',
        'await read(); if (r.status !== "reversed") throw new Error("review_changed");',
        "confirms reversal separately and refreshes the tracked targets without launching an investigation"),
    mutation("refused_reverse_keeps_stale_action", "apps/arkscope-web/src/lifecycle/InvestigationView.tsx",
        'await read(); if (r.status !== "reversed") throw new Error("review_changed"); onChanged();',
        'if (r.status !== "reversed") throw new Error("review_changed"); await read(); onChanged();',
        "refreshes a reversal refused after a concurrent edit instead of leaving the stale action enabled"),
    mutation("oauth_output_limit_claimed_effective", "apps/arkscope-web/src/settings/InvestigationRuntimeSection.tsx",
        '(key === "api_output_tokens" && !!authMode && authMode !== "api_key")', "false",
        "loads only on expansion and reflects the real OAuth output control"),
    mutation("malformed_arrays_become_empty", "apps/arkscope-web/src/lifecycle/investigationContract.ts",
        "if (!Array.isArray(value)) return invalid(); return value.map(parse);",
        "if (!Array.isArray(value)) return []; return value.map(parse);",
        "requires array passages"),
    mutation("source_gap_checkbox_not_required", "apps/arkscope-web/src/lifecycle/InvestigationView.tsx",
        "disabled={busy || dirty || !packet.ready || (!!packet.source_gaps?.length && !acknowledged)}",
        "disabled={busy || dirty || !packet.ready}",
        "requires explicit source-gap acknowledgement before confirmation"),
    mutation("stale_date_preview_confirmable", "apps/arkscope-web/src/lifecycle/InvestigationView.tsx",
        "disabled={busy || dirty || !packet.ready || (!!packet.source_gaps?.length && !acknowledged)}",
        "disabled={busy || !packet.ready || (!!packet.source_gaps?.length && !acknowledged)}",
        "requires a refreshed preview after changing the execution date"),
]


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_source(destination):
    tracked = subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=ROOT).decode().split("\0")
    paths = []
    for value in sorted(set(tracked)):
        path = Path(value)
        if not value or not (ROOT / path).is_file():
            continue
        if (path.parts[0] == "data" or any(part in {"node_modules", ".git", ".claude", ".codex", ".idea", ".venv", "__pycache__"} for part in path.parts)
                or any(part.startswith(".env") for part in path.parts) or path.suffix in {".db", ".sqlite", ".sqlite3"}):
            continue
        if value.startswith("docs/superpowers/evidence/") and not value.startswith(SEALED_FIXTURES) and (path.suffix != ".py" or "source" in path.parts):
            continue
        if path.parts[0] not in {"src", "tests", "data_sources", "config", "docs", "apps", "scripts", "extensions", "skills", "assets", "resources"} and len(path.parts) != 1:
            continue
        if (ROOT / path).is_symlink():
            continue
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / path, target)
        paths.append(value)
    modules = ROOT / "apps/arkscope-web/node_modules"
    (destination / "apps/arkscope-web/node_modules").symlink_to(modules.resolve(), target_is_directory=True)
    root_modules = ROOT / "node_modules"
    if root_modules.exists():
        (destination / "node_modules").symlink_to(root_modules.resolve(), target_is_directory=True)
    return {value: sha(ROOT / value) for value in paths}


def xml_report(path):
    root = ET.parse(path).getroot()
    cases = list(root.iter("testcase"))
    failed = [f'{item.attrib.get("classname", "")}::{item.attrib["name"]}' for item in cases
        if item.find("failure") is not None or item.find("error") is not None]
    return {"tests": len(cases), "skipped": sum(item.find("skipped") is not None for item in cases), "failed": failed}


def main(work, layer, backend_workers=1):
    if work.exists() or not work.resolve().is_relative_to(Path("/tmp")):
        raise ValueError("new_temporary_workspace_required")
    work.mkdir(mode=0o700)
    tree = work / "source"
    tree.mkdir()
    manifest = copy_source(tree)
    write_json(work / "source-manifest.json", manifest)
    env = dict(os.environ, TMPDIR="/dev/shm", PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(tree), CI="1")
    for key in list(env):
        if key.startswith("ARKSCOPE_") and key not in {"ARKSCOPE_DISABLE_SCHEDULER"}:
            del env[key]
    backend_files = sorted({path.relative_to(tree).as_posix() for pattern in (
        "tests/test_lifecycle*.py", "tests/test_security_lifecycle*.py", "tests/test_ticker_identity*.py",
        "tests/test_model_routing.py", "tests/test_model_effective.py", "tests/test_claude_code_sdk_driver.py",
        "tests/test_codex_web_runtime.py", "tests/test_chatgpt_oauth_driver.py") for path in tree.glob(pattern)})
    collection = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", *backend_files], cwd=tree, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    collected = collection.stdout
    (work / "collection.log").write_text(collected)
    if collection.returncode:
        raise ValueError("collection_failed_no_mutation_claim")
    nodes = sorted(line.strip() for line in collected.splitlines() if line.startswith("tests/") and "::" in line)
    if not nodes:
        raise ValueError("empty_focused_set")
    write_json(work / "focused-nodes.json", {"files": backend_files, "nodes": nodes,
        "sha256": hashlib.sha256(("\n".join(nodes) + "\n").encode()).hexdigest()})
    results = []

    def run(name, selected, source=tree):
        xml = work / f"{name}.xml"
        log = work / f"{name}.log"
        if selected == "backend":
            command = [sys.executable, "-m", "pytest", "-q", *backend_files, f"--junitxml={xml}"]
            cwd = source
        else:
            command = ["npm", "test", "--", "--silent", "--maxWorkers=1", "--reporter=junit", f"--outputFile={xml}"]
            cwd = source / "apps/arkscope-web"
        with log.open("w") as output:
            process = subprocess.run(command, cwd=cwd, env={**env, "PYTHONPATH": str(source)}, stdout=output, stderr=subprocess.STDOUT, timeout=1200)
        report = xml_report(xml)
        report.update(name=name, layer=selected, returncode=process.returncode, report_sha256=sha(xml), command=command)
        return report

    worker_sources = []

    def isolated_mutant(value, selected, source):
        path = source / value["path"]
        original = path.read_text()
        if original.count(value["old"]) != 1:
            raise ValueError("mutation_anchor_not_unique:" + value["name"])
        path.write_text(original.replace(value["old"], value["new"]))
        try:
            report = run(value["name"], selected, source)
        finally:
            path.write_text(original)
        report.update(owner=value["owner"], path=value["path"], old=value["old"], new=value["new"],
            owner_failed=any(value["owner"] in failed for failed in report["failed"]), workspace=source.name)
        return report

    def record(report):
        results.append(report)
        write_json(work / "results.json", results)
        print(json.dumps({key: report[key] for key in ("name", "tests", "returncode", "owner_failed")}), flush=True)

    for selected, mutants in (("backend", BACKEND), ("frontend", FRONTEND)):
        if layer not in {"both", selected}:
            continue
        baseline = run(f"{selected}-baseline", selected)
        results.append(baseline)
        write_json(work / "results.json", results)
        print(json.dumps(baseline), flush=True)
        if baseline["returncode"] or baseline["failed"]:
            raise ValueError("baseline_failed_no_mutation_claim")
        if selected == "backend" and backend_workers > 1:
            # Each mutation owns a separate frozen tree; no two tests observe a
            # shared edited module. Only execution order is parallelized.
            with ThreadPoolExecutor(max_workers=backend_workers) as pool:
                pending = []
                for index, value in enumerate(mutants):
                    source = work / f"backend-{index:02d}"
                    source.mkdir()
                    if copy_source(source) != manifest:
                        raise ValueError("source_changed_before_parallel_mutation")
                    worker_sources.append(source)
                    pending.append(pool.submit(isolated_mutant, value, selected, source))
                for future in pending:
                    record(future.result())
        else:
            for value in mutants:
                record(isolated_mutant(value, selected, tree))
        restored = run(f"{selected}-restored", selected)
        results.append(restored)
        write_json(work / "results.json", results)
        if restored["returncode"] or restored["failed"]:
            raise ValueError("restored_baseline_failed")
    changed = [value for value, digest in manifest.items() if sha(ROOT / value) != digest or sha(tree / value) != digest]
    changed.extend(f"{source.name}:{value}" for source in worker_sources for value, digest in manifest.items() if sha(source / value) != digest)
    write_json(work / "source-integrity.json", {"changed": changed, "original_worktree_modified_by_harness": False,
        "backend_workers": backend_workers, "independent_mutant_workspaces": len(worker_sources)})
    if changed or any(row.get("owner_failed") is False for row in results):
        raise ValueError("mutation_unowned_or_source_changed")
    print(json.dumps({"mutants": sum("owner_failed" in row for row in results), "all_named_owners_failed": True}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--layer", choices=("backend", "frontend", "both"), default="both")
    parser.add_argument("--backend-workers", type=int, choices=range(1, 9), default=1)
    args = parser.parse_args()
    main(args.work, args.layer, args.backend_workers)
