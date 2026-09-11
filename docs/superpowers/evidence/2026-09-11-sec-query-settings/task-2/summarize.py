"""Archive Task 2 verification metadata without importing application code."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[3]
OWNED = ["src/sec_research/queries.py", "src/sec_research/fact_queries.py",
         "tests/test_sec_research_fact_queries.py"]

summary = {"runs": {}, "hashes": {}, "git": {}}
for path in sorted(WORK.glob("*/results.xml")):
    suites = ET.parse(path).getroot().findall("testsuite")
    cases = [case for suite in suites for case in suite.findall("testcase")]
    summary["runs"][path.parent.name] = {
        key: sum(int(suite.attrib[key]) for suite in suites)
        for key in ("tests", "failures", "errors", "skipped")
    } | {"owners": dict(Counter(case.attrib["classname"] for case in cases))}
for name in OWNED:
    summary["hashes"][name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
for label, args in {
    "head": ["rev-parse", "HEAD"],
    "commit": ["show", "--format=fuller", "--stat", "HEAD"],
    "status": ["status", "--short", "--", *OWNED],
    "staged": ["diff", "--cached", "--name-only", "--", *OWNED],
    "diff_check": ["diff", "--check", "--", *OWNED],
    "new_fact_check": ["diff", "--no-index", "--check", "/dev/null", OWNED[1]],
    "new_test_check": ["diff", "--no-index", "--check", "/dev/null", OWNED[2]],
}.items():
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    summary["git"][label] = {"command": ["git", *args], "exit_code": result.returncode,
                              "stdout": result.stdout, "stderr": result.stderr}
for label in ("inverse-final-float", "inverse-final-as-of-end", "inverse-final-ids-latest"):
    evidence = json.loads((WORK / label / "hashes.json").read_text())
    assert evidence["before"] == evidence["after"] == summary["hashes"]
    assert summary["runs"][label]["failures"] == 1
    assert summary["runs"][label]["errors"] == 0
summary["inverse_final_hashes_match"] = True
(WORK / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
