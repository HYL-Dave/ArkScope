"""Round2 evidence and restored snapshot; earlier snapshots remain historical."""

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


PLAN = Path(__file__).resolve().parents[1]
ROOT = PLAN.parents[2]


def test_fix_r2_source_restoration_and_raw_evidence(request):
    hashes = {}
    for line in (PLAN / "task-1/fix-r2-before-inverses.sha256").read_text().splitlines():
        expected, path = line.split("  ", 1)
        actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        assert actual == expected, path
        hashes[path] = actual
    request.node.user_properties.append(("restored_source_sha256", json.dumps(hashes, sort_keys=True)))
    expected_runs = {
        "task1-fix-r2-red-01": (1, 44, 17),
        "task1-fix-r2-red-review-probes-01": (1, 2, 2),
        "task1-fix-r2-green-core-01": (0, 174, 0),
        "task1-fix-r2-probe-01": (0, 19, 0),
        "task1-fix-r2-inverse-declaration-case-01": (1, 9, 9),
        "task1-fix-r2-inverse-start-qname-01": (1, 4, 4),
        "task1-fix-r2-inverse-end-qname-01": (1, 4, 4),
        "task1-fix-r2-inverse-empty-qname-01": (1, 2, 2),
        "task1-fix-r2-inverse-token-work-01": (1, 2, 2),
        "task1-fix-r2-regression-01": (0, 1201, 0),
    }
    for name, (exit_code, tests, failures) in expected_runs.items():
        record = json.loads((PLAN / name / "command.json").read_text())
        suite = ET.parse(PLAN / name / "results.xml").getroot().find("testsuite")
        assert record["exit_code"] == exit_code, name
        assert int(suite.attrib["tests"]) == tests, name
        assert int(suite.attrib["failures"]) == failures, name
        assert int(suite.attrib["errors"]) == int(suite.attrib["skipped"]) == 0, name
    red = ET.parse(PLAN / "task1-fix-r2-red-01/results.xml").getroot()
    failing_names = {case.attrib["name"].split("[")[0] for case in red.iter("testcase")
                     if case.find("failure") is not None}
    assert {
        "test_xhtml_case_distinct_nested_prefix_does_not_rebind_inline_namespace",
        "test_xhtml_case_distinct_namespace_declarations_are_not_conflicting",
        "test_xhtml_case_distinct_nested_qnames_restore_each_scope",
        "test_xhtml_mismatched_case_close_does_not_restore_namespace_early",
        "test_xhtml_source_attribute_token_work_consumes_parser_budget",
        "test_xhtml_source_attribute_token_work_is_cancellable",
    } <= failing_names
