"""Reverse UI mutations against the complete frontend suite in a disposable copy."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
WEB = Path("apps/arkscope-web")
TARGET = WEB / "src/settings/ModelRoutingSection.tsx"
MUTATIONS = [
    ("offer_custom_models", '{task.supports_custom_models !== false && <button',
     '{true && <button', "has its own localized route and bounded test"),
    ("promote_retained_unknown", 'eligible: task.supports_custom_models !== false\n              &&',
     'eligible: true\n              &&', "does not promote an absent retained investigation model"),
    ("claim_full_test_success", 'result.task === "lifecycle_investigation"',
     'result.task === "ai_research"', "does not call a schema check a full investigation success"),
    ("show_other_model_rejection", 'const selectedReason = selectedModelStatus === "retired"',
     'const selectedReason = groups.flatMap((group) => group.entries).find((entry) => entry.disabledReason)?.disabledReason ?? (selectedModelStatus === "retired"',
     "renders one selector with four groups and disables ineligible entries with text reasons"),
]


def run_suite(root, output, name):
    report = output / f"{name}.json"
    result = subprocess.run(["npm", "test", "--", "--maxWorkers=4", "--reporter=json", f"--outputFile={report}"],
        cwd=root / WEB, capture_output=True, text=True, timeout=180)
    (output / f"{name}.log").write_text(result.stdout + result.stderr)
    data = json.loads(report.read_text())
    failures = [item["fullName"] for suite in data["testResults"] for item in suite["assertionResults"]
                if item["status"] == "failed"]
    return {"exit_code": result.returncode, "tests": data["numTotalTests"],
            "passed": data["numPassedTests"], "failed": failures,
            "runtime_errors": data.get("numRuntimeErrorTestSuites", 0)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    sources = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in (ROOT / WEB / "src").rglob("*") if path.is_file()}
    (output / "sources.json").write_text(json.dumps(sources, sort_keys=True, indent=2) + "\n")
    results = []
    with tempfile.TemporaryDirectory(prefix="arkscope-task-ui-mutation-") as directory:
        copy = Path(directory)
        for source in ROOT.iterdir():
            if source.name in {".git", ".pytest_cache", "__pycache__", "apps"}:
                continue
            (copy / source.name).symlink_to(source)
        (copy / "apps").mkdir()
        for source in (ROOT / "apps").iterdir():
            if source.name != "arkscope-web":
                (copy / "apps" / source.name).symlink_to(source)
        shutil.copytree(ROOT / WEB, copy / WEB, symlinks=True,
                        ignore=shutil.ignore_patterns("node_modules", "dist", ".vite"))
        baseline = run_suite(copy, output, "baseline")
        assert baseline["exit_code"] == 0, baseline
        target = copy / TARGET
        original = target.read_text()
        for name, old, new, owner in MUTATIONS:
            assert original.count(old) == 1, name
            mutated = original.replace(old, new, 1)
            if name == "show_other_model_rejection":
                end = ': selectedEntry ? optionReason(selectedEntry, providerReason) : null;'
                assert mutated.count(end) == 1
                mutated = mutated.replace(end, end[:-1] + ");", 1)
            try:
                target.write_text(mutated)
                result = run_suite(copy, output, name)
            finally:
                target.write_text(original)
            owned = any(owner in test for test in result["failed"])
            results.append({"name": name, "owner": owner, "owned": owned, **result})
            (output / "results.json").write_text(json.dumps(results, indent=2) + "\n")
            print(json.dumps({"name": name, "owned": owned}), flush=True)
            assert owned and result["exit_code"] == 1 and not result["runtime_errors"], result
        restored = run_suite(copy, output, "restored")
        assert restored["exit_code"] == 0, restored
    assert all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest for name, digest in sources.items())
    print(json.dumps({"owned_mutations": len(results), "restored_tests": restored["tests"], "worktree_unchanged": True}))


if __name__ == "__main__":
    main()
