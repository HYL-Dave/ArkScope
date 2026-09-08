"""Exercise report classification using a real, frozen mutation JUnit report."""

import argparse
import copy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import review_packet as packet

NEGATIVE_CASES = (
    "unexpected_node", "wrong_exception", "wrong_assertion", "wrong_fixture",
    "missing_setup_error", "missing_direct_owner", "different_mutation",
)


def run(source, output):
    assert output.resolve().is_relative_to(Path("/tmp")) and not output.exists()
    output.mkdir()
    original = ET.parse(source).getroot()
    name = "valid_security_definition_ignored"
    accepted = packet.mutation_setup_errors(name, source, packet.xml(source))
    checks = {"expected_nine_setup_assertions": len(accepted) == 9}
    files = {}
    for key in NEGATIVE_CASES:
        root = copy.deepcopy(original)
        cases = list(root.iter("testcase"))
        case = next(item for item in cases if item.find("error") is not None)
        error = case.find("error")
        selected = name
        if key == "unexpected_node":
            case.set("name", "test_unrelated_environment_error")
        elif key == "wrong_exception":
            error.set("message", "failed on setup with RuntimeError")
        elif key == "wrong_assertion":
            error.text = error.text.replace("E       assert 'incomplete' == 'succeeded'", "E       assert False")
        elif key == "wrong_fixture":
            error.text = error.text.replace("tests/test_lifecycle_investigation_review.py", "tests/unrelated.py")
        elif key == "missing_setup_error":
            case.remove(error)
        elif key == "missing_direct_owner":
            owner = next(item for item in cases if "test_only_security_qualified_definitions_bind_event_aliases"
                in item.get("name", "") and item.find("failure") is not None)
            owner.remove(owner.find("failure"))
        elif key == "different_mutation":
            selected = "different_mutation"
        target = output / (key + ".xml")
        ET.ElementTree(root).write(target, encoding="utf-8", xml_declaration=True)
        try:
            packet.mutation_setup_errors(selected, target, packet.xml(target))
        except AssertionError:
            checks[key + "_rejected"] = True
        else:
            checks[key + "_rejected"] = False
        files[target.name] = packet.sha(target)
    assert all(checks.values()), checks
    report = {"checks": checks, "files": files, "original_report_sha256": packet.sha(source),
        "producer_sha256": packet.sha(Path(packet.__file__)), "checker_sha256": packet.sha(Path(__file__))}
    packet.new_json(output / "verification.json", report)
    print(json.dumps({"output": str(output), "checks": checks}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    run(arguments.report, arguments.output)
