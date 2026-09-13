"""Bind final UI checks to the unchanged accepted backend and reviewed census."""

import json
from pathlib import Path
import re

WORK = Path(__file__).resolve().parent


def read(name):
    return json.loads((WORK / name).read_text())


backend = read("closure-validation.json")
before, after = read("source-after-full.json"), read("source-final-ui.json")
left = {row["path"]: row["sha256"] for row in before["source_files"]}
right = {row["path"]: row["sha256"] for row in after["source_files"]}
changed = sorted(path for path in left.keys() | right.keys() if left.get(path) != right.get(path))
runs = ["frontend-census-cleanup-final", "frontend-census-cleanup-typecheck",
        "frontend-census-cleanup-build", "frontend-census-cleanup-i18n", "citations-browser-cleanup-final"]
commands = {name: read(name + "/command.json") for name in runs}
log = re.sub(r"\x1b\[[0-9;]*m", "", (WORK / runs[0] / "output.log").read_text())
workflows = read("citations-browser-cleanup-final/browser/results.json")["workflows"]
census = read("census-reconciliation.json")
inverse = read("citation-inverse-validation.json")
checks = {
    "complete_backend_accepted": all(backend["checks"].values()),
    "only_final_source_change_is_dead_css_deletion": changed == ["apps/arkscope-web/src/styles.css"],
    "same_runtime_sdk_and_guards": all(before[key] == after[key] for key in
        ("runner_sha256", "python", "sqlite", "packages", "sdk_hook_sources")),
    "final_frontend_commands_pass": all(row["exit_code"] == 0 for row in commands.values()),
    "full_frontend_1824_in_126_files": bool(re.search(r"Test Files\s+126 passed", log)
                                             and re.search(r"Tests\s+1824 passed", log)),
    "four_final_browser_workflows": {(row["locale"], row["width"]) for row in workflows}
        == {("en", 1280), ("en", 390), ("zh-Hant", 1280), ("zh-Hant", 390)} and len(workflows) == 4,
    "browser_integrity_geometry_and_retry": all(
        row["geometry"]["scrollWidth"] <= row["width"] and not row["geometry"]["clippedButtons"]
        and not row["page_errors"] and len(row["pinned_text"].encode()) == 176
        and row["exact_fact_value"] == "123456789012345678945"
        and all(row[key] for key in ("newer_capture_distinct", "reopened_after_relocation",
                                    "persisted_message_reloaded", "missing_object_retry", "focus_restored"))
        for row in workflows),
    "five_inverse_receipts_accepted": inverse["all_checks_passed"] and inverse["restored_passed"] == 16,
    "no_new_candidates_or_coverage_dependency_untracked_drift": not any(census["comparison"][key] for key in
        ("new_candidates", "coverage_reductions", "dependency_metadata_changed", "new_untracked_paths")),
    "uncertainties_accounted": len(census["comparison"]["new_uncertainties"]) == 151
        and census["position_only_count"] == 145 and len(census["new_or_changed"]) == 6,
}
result = {"checks": checks, "source_change_after_backend": changed,
          "backend_source_anchor": before["immutable_source_anchor"],
          "final_source_anchor": after["immutable_source_anchor"],
          "backend": backend["backend"], "frontend_passed": 1824,
          "browser_workflows": len(workflows), "final_commands": commands,
          "all_checks_passed": all(checks.values())}
with (WORK / "final-validation.json").open("x") as target:
    json.dump(result, target, indent=2, sort_keys=True)
    target.write("\n")
print(json.dumps({"checks": checks, "all_checks_passed": result["all_checks_passed"]}, indent=2))
raise SystemExit(not result["all_checks_passed"])
