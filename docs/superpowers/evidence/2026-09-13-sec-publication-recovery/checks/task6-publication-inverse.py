"""Omit publication alias recovery, retain evidence, restore exact source bytes."""

import argparse
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
PYTHON = "/home/hyl/.virtualenvs/llm_app/bin/python"
CAPTURES = "src/sec_research/captures.py"
PRODUCT = (CAPTURES, "src/sec_research/capture_lock.py")
TESTS = ("tests/test_sec_research_captures.py", "tests/test_sec_research_capture_lock.py",
         "tests/test_sec_research_maintenance.py", str(WORK / "task6-publication-probe.py"))
RUNNERS = ("run_checks.py", "offline_pytest.py")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def hashes(paths):
    return {str(path): digest((ROOT / path).read_bytes()) for path in paths}


def patch(before, after):
    lines = list(difflib.unified_diff(before.decode().splitlines(True), after.decode().splitlines(True)))[2:]
    diff = "".join("@@\n" if line.startswith("@@") else line for line in lines)
    subprocess.run(["apply_patch"], cwd=ROOT, text=True, check=True,
        input="*** Begin Patch\n*** Update File: " + CAPTURES + "\n" + diff + "*** End Patch\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run")
    args = parser.parse_args()
    assert args.run.startswith("task6-publication-") and Path(args.run).name == args.run
    assert not (WORK / args.run).exists()
    originals = {path: (ROOT / path).read_bytes() for path in PRODUCT}
    needle = b"        directory.recover_published_stages(files)\n"
    assert originals[CAPTURES].count(needle) == 1
    mutant = originals[CAPTURES].replace(needle, b"")
    selected = [TESTS[2] + "::test_publication_recovery_reaches_explicit_cleanup_with_unrelated_orphan", TESTS[3]]
    command = [PYTHON, "-B", str(WORK / "run_checks.py"), args.run, "backend", "-q", *selected]
    record = {"run": args.run, "case": "omit-publication-alias-recovery", "command": command,
              "source_mutation_applied": False, "runner_invoked": False,
              "original_sha256": hashes(PRODUCT), "test_sha256": hashes(TESTS),
              "runner_sha256": hashes([WORK / name for name in RUNNERS])}
    artifacts = WORK / (args.run + "-source")
    artifacts.mkdir(exist_ok=False)
    try:
        for suffix, raw in (("original", originals[CAPTURES]), ("mutated", mutant)):
            with (artifacts / ("captures.py." + suffix)).open("xb") as handle:
                handle.write(raw)
        patch(originals[CAPTURES], mutant)
        assert (ROOT / CAPTURES).read_bytes() == mutant
        record["source_mutation_applied"] = True
        record["mutated_sha256"] = hashes(PRODUCT)
        record["runner_invoked"] = True
        record["exit_code"] = subprocess.run(command, cwd=ROOT).returncode
    except BaseException as exc:
        record["error"] = repr(exc)
        raise
    finally:
        try:
            current = (ROOT / CAPTURES).read_bytes()
            if current != originals[CAPTURES]:
                assert current == mutant, "unexpected source change; do not overwrite"
                patch(mutant, originals[CAPTURES])
            record["restored_sha256"] = hashes(PRODUCT)
            record["restored_test_sha256"] = hashes(TESTS)
            record["restored_runner_sha256"] = hashes([WORK / name for name in RUNNERS])
            record["source_restored_exact"] = all((ROOT / key).read_bytes() == raw for key, raw in originals.items())
            record["tests_unchanged"] = record["test_sha256"] == record["restored_test_sha256"]
            record["runners_unchanged"] = record["runner_sha256"] == record["restored_runner_sha256"]
            xml_path = WORK / args.run / "results.xml"
            if xml_path.exists():
                cases = list(ET.parse(xml_path).iter("testcase"))
                record["failures"] = [{"name": case.get("name"), "message": case.find("failure").get("message")}
                    for case in cases if case.find("failure") is not None]
                record["errors"] = [case.get("name") for case in cases if case.find("error") is not None]
                record["passed"] = sum(not any(case.find(tag) is not None for tag in ("failure", "error", "skipped"))
                    for case in cases)
            record["status"] = "completed" if record.get("exit_code") is not None else "aborted_setup_or_invocation"
        finally:
            with (artifacts / "receipt.json").open("x") as handle:
                json.dump(record, handle, indent=2)
                handle.write("\n")
    assert record["source_restored_exact"] and record["tests_unchanged"] and record["runners_unchanged"]
    assert record["exit_code"] == 1 and record["passed"] == 2 and not record["errors"]
    failures = {failure["name"]: failure["message"] for failure in record["failures"]}
    assert set(failures) == {
        "test_publication_recovery_reaches_explicit_cleanup_with_unrelated_orphan[before_register]",
        "test_interrupted_publication_can_reach_cleanup[before_register]"}
    assert "2 == 1" in failures["test_publication_recovery_reaches_explicit_cleanup_with_unrelated_orphan[before_register]"]
    assert "capture_path_unsafe" in failures["test_interrupted_publication_can_reach_cleanup[before_register]"]
    print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
