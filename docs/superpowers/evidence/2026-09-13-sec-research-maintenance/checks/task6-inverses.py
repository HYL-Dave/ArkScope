"""Task6 temporary inverse mutations, existing isolated runner, exact restoration."""

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
MAINTENANCE = "src/sec_research/maintenance.py"
SCHEMA = "src/sec_research/schema_admin.py"
REFERENCES = "src/sec_research/references.py"
TESTS = ["tests/test_sec_research_maintenance.py", "tests/test_sec_research_schema_admin.py",
         "tests/test_sec_research_cli.py"]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def replace(source, old, new):
    assert source.count(old) == 1, (old, source.count(old))
    return source.replace(old, new)


def patch(path, before, after):
    lines = list(difflib.unified_diff(before.splitlines(True), after.splitlines(True)))[2:]
    diff = "".join("@@\n" if line.startswith("@@") else line for line in lines)
    result = subprocess.run(["apply_patch"], cwd=ROOT, text=True,
        input="*** Begin Patch\n*** Update File: " + path + "\n" + diff + "*** End Patch\n", check=True)
    assert result.returncode == 0


def mutation(case, originals):
    source = {key: value.decode() for key, value in originals.items()}
    if case == "skip-recheck":
        source[MAINTENANCE] = replace(source[MAINTENANCE],
            '_require(current == preview, "sec_research_preview_stale")',
            '_require(True, "sec_research_preview_stale")')
        tests = [TESTS[0] + "::test_new_reference_invalidates_cleanup_preview"]
    elif case == "event-only":
        source[REFERENCES] = replace(source[REFERENCES],
            "SELECT data_json FROM research_run_events ORDER BY run_id, seq",
            "SELECT data_json FROM research_run_events WHERE 0 ORDER BY run_id, seq")
        tests = [TESTS[0] + "::test_new_reference_invalidates_cleanup_preview",
                 TESTS[1] + "::test_schema_reset_refuses_research_references"]
    elif case == "charge":
        source[MAINTENANCE] = replace(source[MAINTENANCE],
            '            for item in current["candidates"]:\n                absent =',
            '            with _write_transaction(paths) as conn:\n'
            '                conn.execute("DELETE FROM sec_research_orphans")\n'
            '            for item in current["candidates"]:\n                absent =')
        tests = [TESTS[0] + "::test_registered_orphan_unlink_failure_remains_charged",
                 TESTS[0] + "::test_failed_directory_durability_charge_survives_ordinary_recovery"]
    elif case == "backup":
        source[SCHEMA] = replace(source[SCHEMA],
            'backup = raw_backup(paths, backup_path, observed_sha256=current["state_sha256"], recheck=recheck)',
            'backup = {"format": "arkscope-sec-research-raw-backup", "version": 1, "database": {}, '
            '"observed_sha256": current["state_sha256"], "captures": []}')
        tests = [TESTS[1] + "::test_schema_reset_requires_backup_and_exclusive_lease"]
    elif case == "unknown-prefix":
        source[MAINTENANCE] = replace(source[MAINTENANCE], "    if unknown:\n", "    if False:\n")
        start = source[SCHEMA].index("def _drop_owned(")
        end = source[SCHEMA].index("\n\ndef apply_schema_reset(", start)
        source[SCHEMA] = source[SCHEMA][:start] + '''def _drop_owned(conn, owned):
    for kind in ("trigger", "index", "table"):
        for name, (actual_kind, _, _) in reversed(tuple(owned.items())):
            if actual_kind == kind:
                conn.execute(f"DROP {kind.upper()} {_quote(name)}")
''' + source[SCHEMA][end:]
        tests = [TESTS[1] + "::test_unknown_owned_objects_are_not_prefix_drop_targets"]
    elif case == "lease":
        source[MAINTENANCE] = replace(source[MAINTENANCE],
            "with research_operation(paths.capture_root, exclusive=True):",
            "with research_operation(paths.capture_root, exclusive=False):")
        tests = [TESTS[0] + "::test_cleanup_requires_fresh_exclusive_lease"]
    elif case == "profile-outputs":
        source[MAINTENANCE] = replace(source[MAINTENANCE],
            "for database in (paths.market_db_path, profile_path)",
            "for database in (paths.market_db_path,)")
        tests = [TESTS[0] + "::test_cleanup_receipt_rejects_profile_sqlite_namespace",
                 TESTS[1] + "::test_schema_outputs_reject_profile_sqlite_namespace",
                 TESTS[2] + "::test_cli_outputs_reject_profile_sqlite_namespace"]
    elif case == "failure-audit-lease":
        for key in (MAINTENANCE, SCHEMA):
            source[key] = replace(source[key], "    lifetime = ExitStack()\n",
                "    lifetime = ExitStack()\n    released = lifetime.enter_context(ExitStack())\n")
            source[key] = replace(source[key],
                "lifetime.enter_context(research_operation(paths.capture_root, exclusive=True))",
                "released.enter_context(research_operation(paths.capture_root, exclusive=True))")
            source[key] = replace(source[key], "        return _finish_failure(result, audit, exc)\n",
                "        released.close()\n        return _finish_failure(result, audit, exc)\n")
        tests = [TESTS[0] + "::test_cleanup_failure_audit_keeps_original_exclusive_lease",
                 TESTS[1] + "::test_schema_failure_audit_keeps_original_exclusive_lease",
                 TESTS[0] + "::test_admin_admission_failure_has_no_lease_or_audit"]
    else:
        raise ValueError(case)
    return {key: value for key, value in source.items() if value.encode() != originals[key]}, tests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("case", choices=("skip-recheck", "event-only", "charge", "backup", "unknown-prefix", "lease",
                                        "profile-outputs", "failure-audit-lease"))
    parser.add_argument("run")
    args = parser.parse_args()
    assert args.run.startswith("task6-") and not (WORK / args.run).exists()
    artifacts = WORK / (args.run + "-source")
    originals = {key: (ROOT / key).read_bytes() for key in (MAINTENANCE, SCHEMA, REFERENCES)}
    mutated, tests = mutation(args.case, originals)
    artifacts.mkdir(exist_ok=False)
    for key in mutated:
        with (artifacts / (Path(key).name + ".original")).open("xb") as handle:
            handle.write(originals[key])
        with (artifacts / (Path(key).name + ".mutated")).open("xb") as handle:
            handle.write(mutated[key].encode())
    original_hashes = {key: digest(value) for key, value in originals.items() if key in mutated}
    test_hashes = {key: digest((ROOT / key).read_bytes()) for key in TESTS}
    applied = []
    command = [PYTHON, "-B", str(WORK / "run_checks.py"), args.run, "backend", "-q", *tests]
    returncode = None
    try:
        for key, value in mutated.items():
            patch(key, originals[key].decode(), value)
            applied.append(key)
        returncode = subprocess.run(command, cwd=ROOT).returncode
    finally:
        for key in reversed(applied):
            patch(key, mutated[key], originals[key].decode())
        assert all((ROOT / key).read_bytes() == raw for key, raw in originals.items())
        assert test_hashes == {key: digest((ROOT / key).read_bytes()) for key in TESTS}
    xml = ET.parse(WORK / args.run / "results.xml")
    failures = [node for node in xml.iter("testcase") if node.find("failure") is not None]
    errors = [node for node in xml.iter("testcase") if node.find("error") is not None]
    record = {"run": args.run, "case": args.case, "command": command, "exit_code": returncode,
        "restored": original_hashes, "mutated": {k: digest(v.encode()) for k, v in mutated.items()},
        "tests": test_hashes,
        "failed_testcases": [node.attrib["classname"] + "::" + node.attrib["name"] for node in failures],
        "error_testcases": [node.attrib["classname"] + "::" + node.attrib["name"] for node in errors],
        "mutation_script": "task6-inverses.py", "source_bytes": artifacts.name}
    with (artifacts / "receipt.json").open("x") as handle:
        json.dump(record, handle, indent=2)
        handle.write("\n")
    print(json.dumps(record), flush=True)
    assert returncode == 1 and failures and not errors
    assert all(node.find("failure").attrib.get("message", "").startswith(("assert ", "AssertionError"))
               for node in failures)


if __name__ == "__main__":
    main()
