"""Resume only full-backend verification after the recorded 600-second timeout."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--temp-root", type=Path, required=True)
    args = parser.parse_args()
    repo, output, temporary = args.repo.resolve(), args.campaign.resolve(), args.temp_root.resolve()
    report_path = output / "report.json"
    report = json.loads(report_path.read_text())
    source = output.parent / "source"
    assert not report["complete"] and "backend" not in report and report["kind"] == "backend"
    assert all(report[name]["exit_code"] == 0 for name in ("baseline", "restored", "integration"))
    assert len(report["mutations"]) == 5 and all(item["killed_by_owner"] for item in report["mutations"])
    assert temporary.is_relative_to(Path("/dev/shm")) and not temporary.exists()

    def unchanged():
        assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip() == report["head"]
        assert all(sha(repo / name) == sha(source / name) == value for name, value in report["source_sha256"].items())
        assert all(not (repo / name).exists() and not (source / name).exists() for name in report["deleted_files"])

    unchanged()
    for name in ("backend.xml", "backend.log", "backend-timeout.json", "report-before-backend-recheck.json"):
        assert not (output / name).exists(), name
    os.umask(0o077)
    temporary.mkdir(mode=0o700)
    write_new(output / "report-before-backend-recheck.json", report)
    timeout = {
        "status": "runner_timeout", "runner_timeout_seconds": 600,
        "scope": "full_backend_same_source_no_provider_calls", "result": None,
        "xml_produced": False, "captured_stdout_retained": False,
        "observation": "subprocess.TimeoutExpired at 600 seconds; child PID 1461130 was no longer present",
        "previous_temporary_storage": "disk-backed /tmp; test process was observed waiting on journal I/O",
        "not_claimed": "No pass count is inferred for the incomplete original attempt.",
    }
    write_new(output / "backend-timeout.json", timeout)
    env = {key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "LANG", "LC_ALL"}}
    env.update(PYTHONPATH=str(repo), PYTHONDONTWRITEBYTECODE="1", ARKSCOPE_DISABLE_SCHEDULER="1", TMPDIR=str(temporary))
    command = [sys.executable, "-m", "pytest", "-q", "tests", f"--junitxml={output / 'backend.xml'}",
               f"--basetemp={temporary / 'backend'}"]
    started = time.monotonic()
    try:
        result = subprocess.run(command, cwd=repo, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, timeout=1200)
    except subprocess.TimeoutExpired as exc:
        data = exc.stdout or b""
        with (output / "backend.log").open("xb") as stream:
            stream.write(data.encode() if isinstance(data, str) else data)
        write_new(output / "backend-recheck-timeout.json", {"status": "runner_timeout", "runner_timeout_seconds": 1200})
        raise
    with (output / "backend.log").open("x") as stream:
        stream.write(result.stdout)
    suites = ET.parse(output / "backend.xml").getroot().findall("testsuite")
    counts = {key: sum(int(s.attrib.get(key, 0)) for s in suites) for key in ("tests", "failures", "errors", "skipped")}
    failures = [f'{case.attrib["classname"]}::{case.attrib["name"]}' for suite in suites for case in suite.findall("testcase")
                if case.find("failure") is not None or case.find("error") is not None]
    report["backend"] = {"name": "backend", "exit_code": result.returncode, "counts": counts,
                         "failed_nodes": failures, "duration_seconds": round(time.monotonic() - started, 3)}
    report["backend_recheck"] = {
        "reason": "prior_runner_timeout", "prior_timeout_receipt_sha256": sha(output / "backend-timeout.json"),
        "prior_report_sha256": sha(output / "report-before-backend-recheck.json"),
        "runner_timeout_seconds": 1200, "temporary_storage": "private /dev/shm directory",
        "same_product_and_tests": True, "assertion_or_product_timeout_changes": False,
        "provider_calls": 0, "command": command,
    }
    unchanged()
    report["complete"] = result.returncode == 0 and not counts["failures"] and not counts["errors"]
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"event": "backend_recheck", **report["backend"], "complete": report["complete"]}), flush=True)
    raise SystemExit(0 if report["complete"] else 1)


if __name__ == "__main__":
    main()
