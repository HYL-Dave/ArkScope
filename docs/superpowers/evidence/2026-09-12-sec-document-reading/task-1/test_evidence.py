"""Verify retained Task1 logs against the exact restored source set."""

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


PLAN = Path(__file__).resolve().parents[1]
ROOT = PLAN.parents[2]


def test_task1_source_restoration_and_raw_evidence(request):
    hashes = {}
    for line in (PLAN / "task-1/source-before-inverses.sha256").read_text().splitlines():
        expected, path = line.split("  ", 1)
        actual = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        assert actual == expected, path
        hashes[path] = actual
    request.node.user_properties.append(("restored_source_sha256", json.dumps(hashes, sort_keys=True)))
    expected_runs = {
        "task1-red-core-01": (1, 88, 87),
        "task1-green-core-01": (0, 88, 0),
        "task1-red-encoding-01": (1, 6, 6),
        "task1-green-core-02": (1, 98, 4),
        "task1-green-core-03": (0, 98, 0),
        "task1-probe-01": (0, 10, 0),
        "task1-inverse-unsafe-name-01": (1, 16, 13),
        "task1-inverse-nesting-01": (1, 5, 2),
        "task1-inverse-duplicate-item-01": (1, 1, 1),
        "task1-regression-01": (0, 1130, 0),
    }
    for name, (exit_code, tests, failures) in expected_runs.items():
        record = json.loads((PLAN / name / "command.json").read_text())
        suite = ET.parse(PLAN / name / "results.xml").getroot().find("testsuite")
        assert record["exit_code"] == exit_code, name
        assert int(suite.attrib["tests"]) == tests, name
        assert int(suite.attrib["failures"]) == failures, name
        assert int(suite.attrib["errors"]) == int(suite.attrib["skipped"]) == 0, name
    red = ET.parse(PLAN / "task1-red-core-01/results.xml").getroot()
    failing_names = {case.attrib["name"].split("[")[0] for case in red.iter("testcase")
                     if case.find("failure") is not None}
    assert {
        "test_directory_rejects_escape_and_cross_accession",
        "test_directory_keeps_actual_document_ids_and_unknown_size",
        "test_accession_filer_prefix_need_not_equal_issuer",
        "test_sec_text_keeps_visible_ixbrl_and_hides_ix_hidden",
        "test_sec_parser_limits_fail_without_truncation",
        "test_ambiguous_toc_heading_does_not_fabricate_section",
        "test_section_offsets_are_exact_utf8",
        "test_default_public_reader_extraction_unchanged",
    } <= failing_names
