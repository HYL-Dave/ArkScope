"""Mechanical reverse mutations in a disposable source/test copy, never the worktree."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
FOCUS = sorted({
    "tests/test_agents.py", "tests/test_model_routing.py", "tests/test_model_effective.py",
    "tests/test_model_capabilities.py", "tests/test_model_route_store.py", "tests/test_model_task_test.py",
    "tests/test_chatgpt_oauth_driver.py", "tests/test_claude_code_sdk_driver.py",
    "tests/test_subscription_structured_output.py", "tests/test_codex_web_runtime.py",
    *[str(path.relative_to(ROOT)) for pattern in (
        "test_lifecycle_investigation_*.py", "test_lifecycle_web_*.py", "test_security_lifecycle_web_*.py",
    ) for path in (ROOT / "tests").glob(pattern)],
})
MUTATIONS = [
    ("borrow_research_route", "src/api/routes/lifecycle_web.py",
     'route_loader=lambda: task_route("lifecycle_investigation")',
     'route_loader=lambda: task_route("ai_research")',
     "test_web_preflight_factory_uses_dedicated_profile_route"),
    ("route_read_failure_falls_back", "src/agents/config.py",
     '        if task == "lifecycle_investigation":\n            raise ModelRouteUnavailable() from None\n', "",
     "test_investigation_route_read_error_is_not_a_billing_fallback"),
    ("unknown_model_eligible", "src/model_effective.py",
     'return task != "lifecycle_investigation", "model_not_in_registry"',
     'return True, "model_not_in_registry"',
     "test_unknown_discovered_models_stay_visible_but_not_executable_for_investigation"),
    ("ignore_result_schema", "src/model_task_canary.py",
     '        validate_output(reply.output, schema)\n', "",
     "test_investigation_schema_check_does_not_accept_malformed_success"),
    ("ignore_terminal_witness", "src/model_task_canary.py",
     '                or control.terminal_statuses != {call.call_id: "completed"}\n', "",
     "test_investigation_schema_check_requires_completed_tool_free_witness[missing_terminal]"),
    ("ignore_unexpected_search", "src/model_task_canary.py",
     '                or any(control.observed_web_actions.values())):', '                ):',
     "test_investigation_schema_check_requires_completed_tool_free_witness[unexpected_search]"),
    ("use_generic_test_transport", "src/model_task_canary.py",
     '    if task == "lifecycle_investigation":\n        return await _run_lifecycle_canary(',
     '    if False:\n        return await _run_lifecycle_canary(',
     "test_investigation_schema_check_uses_same_adapter_once_on_all_four_channels"),
    ("custom_model_save_bypass", "src/model_routing.py",
     '        if capability is None:\n            return {"code": "model_not_in_registry", "field": "model"}\n',
     '        if capability is None:\n            return None\n',
     "test_investigation_save_rejects_unsupported_models_before_writing[gpt-unknown-custom-model_not_in_registry]"),
    ("share_generic_task_authority", "src/security_lifecycle_web_contract.py",
     'model_execution_admission_detail(model, task="lifecycle_investigation", auth_mode=auth_mode)',
     'model_execution_admission_detail(model, task="ai_research", auth_mode=auth_mode)',
     "test_runtime_selection_checks_new_task_not_borrowed_research"),
]


def run_suite(root, output, name):
    xml_path = output / f"{name}.xml"
    result = subprocess.run([sys.executable, "-m", "pytest", *FOCUS, "-q", "--tb=short", f"--junitxml={xml_path}"],
        cwd=root, env={**os.environ, "PYTHONPATH": str(root), "PYTHONDONTWRITEBYTECODE": "1",
                       "ARKSCOPE_DISABLE_SCHEDULER": "1"}, capture_output=True, text=True, timeout=600)
    (output / f"{name}.log").write_text(result.stdout + result.stderr)
    document = ET.parse(xml_path).getroot()
    cases = list(document.iter("testcase"))
    failures = [row.attrib["name"] for row in cases if row.find("failure") is not None]
    errors = [row.attrib.get("name") for row in cases if row.find("error") is not None]
    return {"exit_code": result.returncode, "nodes": len(cases), "failed": failures, "errors": errors}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
              for directory in ("src", "tests") for path in (ROOT / directory).rglob("*.py")}
    (output / "sources.json").write_text(json.dumps(hashes, sort_keys=True, indent=2) + "\n")
    (output / "focus.json").write_text(json.dumps(FOCUS, indent=2) + "\n")
    results = []
    with tempfile.TemporaryDirectory(prefix="arkscope-independent-task-mutation-") as directory:
        copy = Path(directory)
        for source in ROOT.iterdir():
            if source.name in {".git", ".pytest_cache", "__pycache__"}:
                continue
            if source.name in {"src", "tests"}:
                shutil.copytree(source, copy / source.name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            else:
                (copy / source.name).symlink_to(source)
        baseline = run_suite(copy, output, "baseline")
        assert baseline["exit_code"] == 0, baseline
        print(json.dumps({"baseline": baseline["nodes"]}), flush=True)
        for name, filename, old, new, owner in MUTATIONS:
            path = copy / filename
            original = path.read_text()
            assert original.count(old) == 1, (name, "mutation anchor")
            try:
                path.write_text(original.replace(old, new, 1))
                result = run_suite(copy, output, name)
            finally:
                path.write_text(original)
            owned = any(value.startswith(owner) for value in result["failed"])
            results.append({"name": name, "owner": owner, "owned": owned, **result})
            (output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
            print(json.dumps({"mutation": name, "owned": owned, "failures": len(result["failed"])}), flush=True)
            assert owned and result["exit_code"] == 1 and not result["errors"], result
        restored = run_suite(copy, output, "restored")
        assert restored["exit_code"] == 0
    assert all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest for name, digest in hashes.items())
    print(json.dumps({"owned_mutations": len(results), "restored_nodes": restored["nodes"], "worktree_unchanged": True}))


if __name__ == "__main__":
    main()
