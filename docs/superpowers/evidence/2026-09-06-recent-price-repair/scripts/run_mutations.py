"""Independent mutations in a source-only copy, never in an operator worktree."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


HERE = Path(__file__).resolve().parent
PACKET = HERE.parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def test_run(python, source, output, temp_root, name, files):
    xml = output / f"{name}.xml"
    env = {key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR"}}
    env.update(PYTHONPATH=str(source), PYTHONDONTWRITEBYTECODE="1", ARKSCOPE_DISABLE_SCHEDULER="1")
    started = time.monotonic()
    result = subprocess.run([python, "-m", "pytest", "-q", *files, f"--junitxml={xml}", f"--basetemp={temp_root / name}"],
                            cwd=source, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=600)
    (output / f"{name}.log").write_text(result.stdout)
    suites = ET.parse(xml).getroot().findall("testsuite")
    failures = [f'{case.attrib["classname"]}::{case.attrib["name"]}' for suite in suites for case in suite.findall("testcase")
                if case.find("failure") is not None or case.find("error") is not None]
    counts = {key: sum(int(s.attrib.get(key, 0)) for s in suites) for key in ("tests", "failures", "errors", "skipped")}
    return {"name": name, "exit_code": result.returncode, "counts": counts, "failed_nodes": failures,
            "duration_seconds": round(time.monotonic() - started, 3)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--staging", required=True, type=Path)
    parser.add_argument("--temp-root", required=True, type=Path)
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args()
    os.umask(0o077)
    repo, staging, temp_root = args.repo.resolve(), args.staging.resolve(), args.temp_root.resolve()
    if staging == repo or repo in staging.parents or staging.exists() or temp_root.exists() or repo in temp_root.parents or temp_root == repo:
        raise RuntimeError("mutation_stage_must_be_new_and_outside_repository")
    staging.mkdir(mode=0o700)
    source, output = staging / "source", staging / "results"
    source.mkdir()
    output.mkdir()
    temp_root.mkdir(mode=0o700)
    subprocess.run(["rsync", "-a", "--exclude=/.git", "--exclude=/data/", "--exclude=node_modules", "--exclude=.env",
                    "--exclude=.pytest_cache", "--exclude=__pycache__", "--exclude=*.pyc", str(repo) + "/", str(source)], check=True)
    if (repo / "node_modules").exists():
        (source / "node_modules").symlink_to(repo / "node_modules", target_is_directory=True)
    files = json.loads((PACKET / "price-focus-files.json").read_text())["files"]
    mutations = json.loads((PACKET / "mutations.json").read_text())
    baseline = test_run(args.python, source, output, temp_root, "baseline", files)
    report = {"focus": files, "baseline": baseline, "mutations": [],
              "temporary_data_on_distinct_filesystem": temp_root.stat().st_dev != source.stat().st_dev}
    print(json.dumps({"event": "baseline", **baseline}), flush=True)
    if baseline["exit_code"]:
        write_json(output / "report.json", report)
        raise RuntimeError("mutation_baseline_failed")
    for mutation in mutations:
        originals = {edit["path"]: (source / edit["path"]).read_bytes() for edit in mutation["edits"]}
        try:
            for edit in mutation["edits"]:
                target = source / edit["path"]
                value = target.read_text()
                if value.count(edit["before"]) != 1:
                    raise RuntimeError("mutation_anchor_is_not_unique")
                target.write_text(value.replace(edit["before"], edit["after"], 1))
            result = test_run(args.python, source, output, temp_root, mutation["name"], files)
        finally:
            for name, data in originals.items():
                (source / name).write_bytes(data)
        result["killed_by_owner"] = result["exit_code"] == 1 and any(mutation["owner"] in node for node in result["failed_nodes"])
        result["restored_files"] = {name: digest((source / name).read_bytes()) for name in originals}
        if any(result["restored_files"][name] != digest(data) for name, data in originals.items()):
            raise RuntimeError("mutation_restore_failed")
        report["mutations"].append(result)
        print(json.dumps({"event": "mutation", **result}), flush=True)
        if not result["killed_by_owner"]:
            write_json(output / "report.json", report)
            raise RuntimeError("mutation_owner_not_failed")
    report["restored"] = test_run(args.python, source, output, temp_root, "restored", files)
    write_json(output / "report.json", report)
    print(json.dumps({"event": "restored", **report["restored"]}), flush=True)
    if report["restored"]["exit_code"]:
        raise RuntimeError("mutation_restored_focus_failed")


if __name__ == "__main__":
    main()
