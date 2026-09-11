"""Fix-round evidence verification; original snapshot evidence is left unchanged."""

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


PLAN = Path(__file__).resolve().parents[1]
ROOT = PLAN.parents[2]


def test_fix_r1_source_restoration_and_raw_evidence(request):
    hashes = {}
    for line in (PLAN / "task-1/fix-r1-before-inverses.sha256").read_text().splitlines():
        expected, path = line.split("  ", 1)
        actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        assert actual == expected, path
        hashes[path] = actual
    request.node.user_properties.append(("restored_source_sha256", json.dumps(hashes, sort_keys=True)))
    expected_runs = {
        "task1-fix-r1-red-01": (1, 95, 39),
        "task1-fix-r1-red-scope-work-01": (1, 4, 4),
        "task1-fix-r1-after-i1-01": (1, 99, 3),
        "task1-fix-r1-green-core-01": (0, 152, 0),
        "task1-fix-r1-probe-01": (0, 12, 0),
        "task1-fix-r1-inverse-alias-01": (1, 4, 4),
        "task1-fix-r1-inverse-namespace-identity-01": (1, 18, 18),
        "task1-fix-r1-inverse-scope-restoration-01": (1, 10, 10),
        "task1-fix-r1-inverse-map-clone-01": (1, 2, 1),
        "task1-fix-r1-inverse-toc-transition-01": (1, 3, 3),
        "task1-fix-r1-regression-01": (0, 1181, 0),
    }
    for name, (exit_code, tests, failures) in expected_runs.items():
        record = json.loads((PLAN / name / "command.json").read_text())
        suite = ET.parse(PLAN / name / "results.xml").getroot().find("testsuite")
        assert record["exit_code"] == exit_code, name
        assert int(suite.attrib["tests"]) == tests, name
        assert int(suite.attrib["failures"]) == failures, name
        assert int(suite.attrib["errors"]) == int(suite.attrib["skipped"]) == 0, name
    red = ET.parse(PLAN / "task1-fix-r1-red-01/results.xml").getroot()
    failing_names = {case.attrib["name"].split("[")[0] for case in red.iter("testcase")
                     if case.find("failure") is not None}
    assert {
        "test_namespace_aliased_ixbrl_does_not_publish_hidden_facts",
        "test_namespace_rebinding_restores_enclosing_inline_binding",
        "test_namespace_rebinding_restores_enclosing_unrelated_binding",
        "test_unrelated_namespace_hidden_names_remain_visible",
        "test_duplicate_inside_toc_does_not_authorize_later_toc_only_item",
    } <= failing_names
