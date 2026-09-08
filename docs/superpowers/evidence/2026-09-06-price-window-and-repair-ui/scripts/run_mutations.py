"""Independent source-copy campaigns; each mutant must fail its named owner."""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PACKET = HERE.parent
BASE_RUNNER = PACKET.parent / "2026-09-06-recent-price-repair/scripts/run_mutations.py"
spec = importlib.util.spec_from_file_location("price_mutation_base", BASE_RUNNER)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


def ui_run(source, output, name, files):
    report = output / (name + ".json")
    env = {key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR"}}
    result = subprocess.run(["node", str(source / "node_modules/vitest/vitest.mjs"), "run", *files,
                             "--reporter=json", "--outputFile=" + str(report)],
                            cwd=source / "apps/arkscope-web", env=env, capture_output=True, text=True, timeout=180)
    (output / (name + ".log")).write_text(result.stdout + result.stderr)
    value = json.loads(report.read_text())
    failed = [test["fullName"] for suite in value["testResults"] for test in suite["assertionResults"] if test["status"] == "failed"]
    return {"name": name, "exit_code": result.returncode, "counts": {"tests": value["numTotalTests"],
            "failures": value["numFailedTests"], "errors": sum(not suite["assertionResults"] and suite["status"] == "failed" for suite in value["testResults"]),
            "skipped": value["numPendingTests"]}, "failed_nodes": failed}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--staging", required=True, type=Path)
    parser.add_argument("--temp-root", required=True, type=Path)
    parser.add_argument("--kind", required=True, choices=("backend", "frontend"))
    args = parser.parse_args()
    os.umask(0o077)
    repo, staging, temp_root = args.repo.resolve(), args.staging.resolve(), args.temp_root.resolve()
    if any(path == repo or repo in path.parents or path.exists() for path in (staging, temp_root)):
        raise RuntimeError("campaign_requires_new_paths_outside_repository")
    source, output = staging / "source", staging / "results"
    source.mkdir(parents=True, mode=0o700)
    output.mkdir()
    temp_root.mkdir(mode=0o700)
    subprocess.run(["rsync", "-a", "--exclude=/.git", "--exclude=/data/", "--exclude=node_modules", "--exclude=.env", "--exclude=dist",
                    "--exclude=.pytest_cache", "--exclude=__pycache__", "--exclude=*.pyc", str(repo) + "/", str(source)], check=True)
    (source / "node_modules").symlink_to(repo / "node_modules", target_is_directory=True)
    manifest = "price-focus-files.json" if args.kind == "backend" else "ui-focus-files.json"
    files = json.loads((PACKET / manifest).read_text())["files"]
    mutations = json.loads((PACKET / "mutations.json").read_text())[args.kind]
    def run(name):
        return (base.test_run(sys.executable, source, output, temp_root, name, files)
                if args.kind == "backend" else ui_run(source, output, name, files))
    baseline = run("baseline")
    report = {"kind": args.kind, "files": files, "baseline": baseline, "mutations": []}
    print(json.dumps({"event": "baseline", **baseline}), flush=True)
    if baseline["exit_code"]:
        base.write_json(output / "report.json", report)
        raise RuntimeError("campaign_baseline_failed")
    for mutation in mutations:
        originals = {edit["path"]: (source / edit["path"]).read_bytes() for edit in mutation["edits"]}
        try:
            for edit in mutation["edits"]:
                target = source / edit["path"]
                text = target.read_text()
                if text.count(edit["before"]) != 1:
                    raise RuntimeError("mutation_anchor_is_not_unique")
                target.write_text(text.replace(edit["before"], edit["after"], 1))
            result = run(mutation["name"])
        finally:
            for name, data in originals.items():
                (source / name).write_bytes(data)
        result["owner"] = mutation["owner"]
        result["killed_by_owner"] = (result["exit_code"] == 1 and result["counts"]["errors"] == 0
                                      and result["counts"]["tests"] == baseline["counts"]["tests"]
                                      and any(mutation["owner"] in node for node in result["failed_nodes"]))
        result["restored_sha256"] = {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in originals}
        assert all(result["restored_sha256"][name] == hashlib.sha256(data).hexdigest() for name, data in originals.items())
        report["mutations"].append(result)
        print(json.dumps({"event": "mutation", **result}), flush=True)
        if not result["killed_by_owner"]:
            base.write_json(output / "report.json", report)
            raise RuntimeError("campaign_owner_survived")
    report["restored"] = run("restored")
    base.write_json(output / "report.json", report)
    print(json.dumps({"event": "restored", **report["restored"]}), flush=True)
    if report["restored"]["exit_code"]:
        raise RuntimeError("restored_focus_failed")


if __name__ == "__main__":
    main()
