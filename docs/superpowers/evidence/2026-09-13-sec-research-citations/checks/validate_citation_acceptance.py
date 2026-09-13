"""Check citation-specific acceptance receipts without importing the application."""

import ast
import hashlib
import json
from pathlib import Path
import textwrap
import xml.etree.ElementTree as ET

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
INVERSES = {
    "inverse-bound-hash-01": ["test_bound_hash_pointer_metadata_and_utf8_tampering_is_unavailable[fact-change0]"],
    "inverse-optional-fields-01": ["test_sec_tool_end_preserves_whole_citations_by_call_id"],
    "inverse-call-id-01": ["test_sec_tool_end_preserves_whole_citations_by_call_id"],
    "inverse-event-roots-01": ["test_profile_iterator_enumerates_message_and_event_only_roots"],
    "inverse-recovery-500-02": ["test_restart_and_no_task_cancel_rebuild_all_sec_tool_calls[restart]",
                                "test_restart_and_no_task_cancel_rebuild_all_sec_tool_calls[no-task-cancel]"],
}


def function_sha(module, qualname):
    path = ROOT / (module.replace(".", "/") + ".py")
    source = path.read_text()
    node = ast.parse(source)
    for part in qualname.split("."):
        matches = [child for child in node.body if isinstance(child, (ast.ClassDef, ast.FunctionDef))
                   and child.name == part]
        assert len(matches) == 1, (path, part)
        node = matches[0]
    assert not node.decorator_list
    body = textwrap.dedent("".join(source.splitlines(keepends=True)[node.lineno - 1:node.end_lineno]))
    return hashlib.sha256(body.encode()).hexdigest()


def main():
    inverses = {}
    for run, expected in INVERSES.items():
        folder = WORK / run
        command = json.loads((folder / "command.json").read_text())
        receipt = json.loads((folder / "citation-inverse.json").read_text())
        nodes = ET.parse(folder / "results.xml").findall(".//testcase")
        failures = sorted(node.get("name") for node in nodes if node.find("failure") is not None)
        assert failures == sorted(expected), (run, failures)
        assert not any(node.find("error") is not None or node.find("skipped") is not None for node in nodes)
        assert command["exit_code"] == receipt["exit_code"] == 1
        assert receipt["original_restored"] and receipt["tracked_source_edited"] is False
        assert receipt["source_sha256"] == function_sha(receipt["module"], receipt["qualname"])
        inverses[run] = {"failed_owners": failures, "current_function_sha256": receipt["source_sha256"],
                         "receipt_sha256": hashlib.sha256((folder / "citation-inverse.json").read_bytes()).hexdigest()}
    restored = WORK / "inverse-restored-green-01"
    restored_nodes = ET.parse(restored / "results.xml").findall(".//testcase")
    assert len(restored_nodes) == 16 and not any(
        node.find(tag) is not None for node in restored_nodes for tag in ("failure", "error", "skipped"))
    assert json.loads((restored / "command.json").read_text())["exit_code"] == 0
    result = {"inverses": inverses, "restored_passed": 16,
              "setup_failure_excluded": "inverse-recovery-500-01",
              "source_files_mutated_on_disk": False,
              "all_checks_passed": True}
    with (WORK / "citation-inverse-validation.json").open("x") as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
