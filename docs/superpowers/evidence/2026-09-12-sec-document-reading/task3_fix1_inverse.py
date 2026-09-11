"""Reproduce Task3 inverses in memory and retain exact current-source evidence."""

import hashlib
import importlib
import json
import os
from pathlib import Path
import xml.etree.ElementTree as ET


WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
SOURCE = "src/api/routes/sec_research.py"
SCOPED = (SOURCE, "tests/test_sec_research_document_routes.py", "tests/test_api.py",
          "tests/test_security_lifecycle_routes.py")
CHANGES = {
    "validation-order": (
        "def _document_operands(filing_id, **params):\n",
        "def _document_operands(filing_id, **params):\n    SecResearchPaths.resolve()\n"),
    "get-budget": (
        "        captures = CaptureStore(store, budget=None)\n",
        "        get_capture_budget_bytes(get_profile_store())\n"
        "        captures = CaptureStore(store, budget=None)\n"),
    "profile-identity": (
        "        policy = SecSourcePolicy(user_agent=identity)\n",
        '        policy = SecSourcePolicy(user_agent="Wrong wrong@example.com")\n'),
    "permission": (
        '    require_db_write("sec_research_document_acquire",\n'
        '                     {"filing_id": filing_id, "document_id": request.document_id})\n', ""),
}


def hashes():
    return {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in SCOPED}


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def pytest_addoption(parser):
    parser.addoption("--task3-inverse", choices=tuple(CHANGES))


def pytest_configure(config):
    choice = config.getoption("--task3-inverse")
    if choice is None:
        return
    module = importlib.import_module("src.api.routes.sec_research")
    before = hashes()
    source = (ROOT / SOURCE).read_text()
    old, new = CHANGES[choice]
    assert source.count(old) == 1, "mutation target drifted"
    mutated = source.replace(old, new, 1)
    run = Path(os.environ["ARKSCOPE_OFFLINE_TEST_WORKSPACE"])
    (run / "mutation.py").write_text(mutated)
    snapshot = dict(module.__dict__)
    exec(compile(mutated, str(run / "mutation.py"), "exec"), module.__dict__)
    config._task3_inverse = module, snapshot, run, {
        "kind": "process_local_compiled_source", "choice": choice,
        "before": before,
        "mutated": {**before, SOURCE: hashlib.sha256(mutated.encode()).hexdigest()},
        "patch": {"path": SOURCE, "old": old, "new": new},
        "disk_source_modified": False,
    }


def pytest_sessionfinish(session):
    state = getattr(session.config, "_task3_inverse", None)
    if state is None:
        return
    module, snapshot, run, record = state
    module.__dict__.clear()
    module.__dict__.update(snapshot)
    record["restored"] = record["after"] = hashes()
    save(run / "hashes.json", record)
    assert record["restored"] == record["before"], "scoped files changed during inverse"


def results(name):
    cases = list(ET.parse(WORK / name / "results.xml").iter("testcase"))
    failed = sorted(case.get("classname") + "::" + case.get("name")
                    for case in cases if case.find("failure") is not None)
    errors = sum(case.find("error") is not None for case in cases)
    skipped = sum(case.find("skipped") is not None for case in cases)
    return {"failed_testcases": failed, "failures": len(failed), "errors": errors,
            "skipped": skipped, "passed": sum(not list(case) for case in cases)}


def summarize():
    evidence = []
    for choice in CHANGES:
        name = "task3-fix1-inverse-" + choice + "-01"
        record = json.loads((WORK / name / "hashes.json").read_text())
        command = json.loads((WORK / name / "command.json").read_text())
        counts = results(name)
        assert command["exit_code"] == 1 and counts["failures"] and not counts["errors"]
        assert not counts["skipped"]
        assert record["before"] == record["restored"] == hashes()
        assert record["mutated"][SOURCE] != record["restored"][SOURCE]
        assert hashlib.sha256((WORK / name / "mutation.py").read_bytes()).hexdigest() == record["mutated"][SOURCE]
        evidence.append({"run": name, "record": name + "/hashes.json",
            "mutation": name + "/mutation.py", "kind": record["kind"],
            "before": record["before"], "mutated": record["mutated"],
            "restored": record["restored"], **counts})
    save(WORK / "task3-fix1-current-inverse-evidence.json", evidence)
    archived = {choice: results("task3-inverse-" + choice + "-01") for choice in CHANGES}
    assert [archived[name]["errors"] for name in CHANGES] == [17, 1, 0, 1]
    green = {name: results(name) for name in ("task3-fix1-green-01", "task3-fix1-precommit-01")}
    for name, count in zip(green, (81, 234)):
        assert green[name]["passed"] == count
        assert not any(green[name][key] for key in ("errors", "failures", "skipped"))
    def nodes(name):
        return {case.get("classname") + "::" + case.get("name")
                for case in ET.parse(WORK / name / "results.xml").iter("testcase")}
    assert nodes("task3-fix1-precommit-01") == nodes("task3-precommit-01")
    save(WORK / "task3-fix1-evidence-summary.json", {
        "archived_red": archived, "current": evidence, "current_hashes": hashes(),
        "focused_green": green, "focused_node_ids_unchanged": True,
        "helper_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    })
    print(json.dumps({row["run"]: {key: row[key] for key in ("passed", "failures", "errors")}
                      for row in evidence}, indent=2))


if __name__ == "__main__":
    summarize()
