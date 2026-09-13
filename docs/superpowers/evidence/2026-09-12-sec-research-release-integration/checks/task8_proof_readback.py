"""Bind retained behavioral proofs to current source without rerunning tests."""

import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def source(name):
    path = ROOT / name
    assert path.resolve().is_relative_to(ROOT) and not path.is_symlink()
    return path.read_bytes()


def git_source(revision, name):
    return subprocess.run(["git", "show", revision + ":" + name], cwd=ROOT,
                          capture_output=True, check=True).stdout


def definitions(raw):
    return {node.name: ast.dump(node, include_attributes=False)
            for node in ast.parse(raw).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}


def delegated_fix_readback():
    inventory = json.loads((WORK / "task8-final-fix-receipt-inventory.json").read_text())
    proof = json.loads((WORK / "task8-final-fix-inverse-proof.json").read_text())
    verified = {}

    def check_artifact(record):
        path = ROOT / record["path"]
        assert path.is_relative_to(ROOT) and not path.is_symlink() and path.is_file()
        raw = path.read_bytes()
        assert sha(raw) == record["sha256"]
        verified[record["path"]] = sha(raw)
        return raw

    for record in inventory["final_source_and_tests"]:
        assert check_artifact(record) == git_source(inventory["commit"], record["path"])
    for record in inventory["runner_sources"]:
        check_artifact(record)
    for record in proof["artifacts"]:
        check_artifact(record)
    changed = subprocess.run(
        ["git", "diff", "--name-only", inventory["base"], inventory["commit"]],
        cwd=ROOT, capture_output=True, check=True).stdout.decode().splitlines()
    assert set(changed) == {row["path"] for row in inventory["final_source_and_tests"]}
    receipts = {}
    for row in inventory["receipts"]:
        command = json.loads(check_artifact(row["command_json"]))
        check_artifact(row["log"])
        nodes = ET.fromstring(check_artifact(row["junit"])).findall(".//testcase")
        actual = {"tests": len(nodes),
                  "failures": sum(node.find("failure") is not None for node in nodes),
                  "errors": sum(node.find("error") is not None for node in nodes),
                  "skipped": sum(node.find("skipped") is not None for node in nodes)}
        actual["passed"] = actual["tests"] - sum(actual[key] for key in ("failures", "errors", "skipped"))
        assert actual == row["result"]
        assert command["exit_code"] == row["exit_code"]
        assert command["command"] == row["command"]
        assert row["name"] not in receipts and row["disposition"] and row["explanation"]
        receipts[row["name"]] = row
    final_tests = {row["sha256"] for row in inventory["final_source_and_tests"]
                   if row["path"].startswith("tests/")}
    final = []
    for invocation in proof["invocations"]:
        if not invocation["final_source"]:
            continue
        original = check_artifact(invocation["original"])
        mutant = check_artifact(invocation["mutant"])
        assert original == source(invocation["target"]) and mutant != original
        for test in invocation["tests"]:
            assert sha(check_artifact(test)) in final_tests
        red = receipts[invocation["kill"]["receipt"]]
        green = receipts[invocation["restore"]["green_receipt"]]
        assert red["exit_code"] == 1 and red["result"]["failures"] > 0
        assert red["result"]["errors"] == 0
        assert green["exit_code"] == 0 and green["result"]["passed"] > 0
        assert not any(green["result"][key] for key in ("failures", "errors", "skipped"))
        assert invocation["restore"]["restored_sha256"] == sha(original)
        final.append({"boundary": invocation["boundary"], "red": red["name"],
                      "restored": green["name"], "source_sha256": sha(original)})
    assert len(final) == 3 and len(receipts) == inventory["receipt_count"] == 36
    return {"commit": inventory["commit"], "verified_files": verified,
            "receipt_count": len(receipts), "current_inverses": final,
            "covering": receipts["task8-final-fix-covering-03"]["result"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows = []
    documents = ("task7-final-inverses.json", "task7-fix1-inverses.json",
                 "task7-fix1-refreshed-inverses.json")
    retained = {"enable-by-default", "drop-partial", "reset-pins", "reset-draft"}
    for document in documents:
        for proof in json.loads((WORK / document).read_text()):
            if document == documents[0] and proof["name"] not in retained:
                continue
            files = []
            for file in proof["files"]:
                raw = source(file["file"])
                original = (WORK / file["original_artifact"]).read_bytes()
                mutant = (WORK / file["mutant_artifact"]).read_bytes()
                assert sha(raw) == sha(original) == file["before"] == file["restored"]
                assert sha(mutant) == file["mutant"] != sha(original)
                replay = original.decode()
                for replacement in file["replacements"]:
                    assert replay.count(replacement["original"]) == 1
                    replay = replay.replace(replacement["original"], replacement["mutant"])
                assert replay.encode() == mutant
                files.append({"file": file["file"], "sha256": sha(raw)})
            runs = []
            for phase, expected in (("red", 1), ("green", 0)):
                directory = WORK / proof[phase]
                command = json.loads((directory / "command.json").read_text())
                assert command["exit_code"] == expected
                xml = directory / "results.xml"
                counts = None
                if xml.exists():
                    nodes = ET.parse(xml).findall(".//testcase")
                    assert nodes and not any(node.find("error") is not None for node in nodes)
                    failures = sum(node.find("failure") is not None for node in nodes)
                    assert (failures > 0) == (phase == "red")
                    counts = {"nodes": len(nodes), "failures": failures}
                runs.append({"phase": phase, "run": proof[phase], "exit": expected,
                             "command_sha256": sha((directory / "command.json").read_bytes()),
                             "log_sha256": sha((directory / "output.log").read_bytes()),
                             "junit": counts})
            rows.append({"proof": proof["name"], "record": document, "files": files, "runs": runs})
    assert len(rows) == 13
    publication_path = WORK / "task6-publication-inverse-omit-alias-01-source/receipt.json"
    publication = json.loads(publication_path.read_text())
    for field in ("restored_sha256", "restored_test_sha256", "restored_runner_sha256"):
        assert all(sha(source(name)) == expected for name, expected in publication[field].items())
    assert publication["source_restored_exact"] and publication["tests_unchanged"] and publication["runners_unchanged"]
    unchanged = {}
    for name in ("src/sec_research/maintenance.py", "src/sec_research/schema_admin.py",
                 "src/sec_research/references.py"):
        assert source(name) == git_source("78157e62", name)
        unchanged[name] = sha(source(name))
    old_tests = definitions(git_source("78157e62", "tests/test_sec_research_maintenance.py"))
    current_tests = definitions(source("tests/test_sec_research_maintenance.py"))
    assert all(current_tests.get(name) == value for name, value in old_tests.items())
    old_ops = definitions(git_source("78157e62", "src/sec_research/operations.py"))
    current_ops = definitions(source("src/sec_research/operations.py"))
    changed_ops = sorted(name for name, value in old_ops.items() if current_ops.get(name) != value)
    assert changed_ops == ["_verify_database"]
    result = {
        "passed": True, "schedule_proofs": rows,
        "delegated_fix": delegated_fix_readback(),
        "publication_receipt_sha256": sha(publication_path.read_bytes()),
        "publication_current_source_test_runner_match": True,
        "unchanged_maintenance_sources_since_acceptance": unchanged,
        "existing_maintenance_definitions_preserved": len(old_tests),
        "changed_operation_definitions_since_acceptance": changed_ops,
        "operation_change_owner": "Task7 adds schedule batch validation/counts; terminal-coverage inverse and export/status/admin negative owners verify that new boundary. Earlier inventory/hash/path mechanisms are unchanged, not newly mutated here.",
        "limit": "Readback of retained proofs, not a fresh inverse run or actual-store validation. Earlier Task5/6 receipt stages remain historical checkpoints.",
    }
    with args.output.open("x") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({"passed": True, "schedule_proofs": len(rows),
                      "existing_maintenance_definitions_preserved": len(old_tests),
                      "changed_operation_definitions": changed_ops}))
