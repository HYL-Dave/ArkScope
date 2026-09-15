"""Summarize archived offline test results, preserving case identity checks."""

import gzip
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree


checks = Path(__file__).resolve().with_name("checks")
reports, identities = {}, {}
for path in sorted(checks.glob("*.xml.gz")):
    root = ElementTree.fromstring(gzip.decompress(path.read_bytes()))
    cases = root.findall(".//testcase")
    ids = sorted((case.get("classname", ""), case.get("name", "")) for case in cases)
    identities[path.name] = set(ids)
    reports[path.name] = {
        "tests": len(cases),
        **{key: sum(case.find(tag) is not None for case in cases)
           for key, tag in [("failed", "failure"), ("errors", "error"), ("skipped", "skipped")]},
        "case_ids_sha256": hashlib.sha256(json.dumps(ids).encode()).hexdigest(),
    }
frontend = json.loads(gzip.decompress((checks / "frontend-full.json.gz").read_bytes()))
result = {
    "backend": reports,
    "frontend": {key: frontend[key] for key in
                 ("success", "numTotalTests", "numPassedTests", "numFailedTests", "numPendingTests")},
    "frontend_files": len(frontend["testResults"]),
    "final_document_case_ids_equal": identities["guard-final-current.xml.gz"]
        == identities["guard-final-candidate.xml.gz"],
    "candidate_coverage_is_aggregated_not_one_final_run": True,
    "candidate_aggregate_matches_final_current": identities["backend-current-complete.xml.gz"]
        == identities["backend-candidate.xml.gz"] | identities["guard-final-candidate.xml.gz"],
}
assert result["final_document_case_ids_equal"]
assert result["candidate_aggregate_matches_final_current"]
assert result["frontend"]["success"]
for name in ("backend-current-complete.xml.gz", "backend-candidate.xml.gz",
             "guard-final-current.xml.gz", "guard-final-candidate.xml.gz"):
    assert all(reports[name][key] == 0 for key in ("failed", "errors", "skipped"))
rendered = json.dumps(result, indent=2) + "\n"
(checks / "summary.json").write_text(rendered)
print(rendered, end="")
