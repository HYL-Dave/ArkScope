"""Read archived task evidence only; no product imports or test execution."""

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


PLAN = Path(__file__).resolve().parent
ROOT = PLAN.parents[2]
TASK = PLAN / "task-2"
summary = json.loads((TASK / "summary.json").read_text())
for name, expected in sorted(summary["runs"].items()):
    run = TASK / name
    suites = ET.parse(run / "results.xml").getroot().findall("testsuite")
    counts = {key: sum(int(s.attrib[key]) for s in suites)
              for key in ("tests", "failures", "errors", "skipped")}
    assert counts == {key: expected[key] for key in counts}, name
    command = json.loads((run / "command.json").read_text())
    assert command["exit_code"] == (1 if counts["failures"] else 0), name
    assert command["environment"]["TZ"] == "Asia/Taipei", name
    output = (run / "output.log").read_text()
    assert "warnings summary" not in output.lower(), name
    assert "PytestWarning" not in output, name
    print(name, json.dumps(counts, sort_keys=True))
    if name == "red":
        failures = [f.text for s in suites for f in s.findall("testcase/failure")]
        assert len(failures) == 59
        assert all("stored fact queries missing" in text for text in failures)
    if name == "green-final-http":
        cases = [c for s in suites for c in s.findall("testcase")]
        print("facts owners", sum(c.attrib["classname"] == "tests.test_sec_research_fact_queries" for c in cases))
        print("catalog owners", sum(c.attrib["classname"] == "tests.test_sec_research_queries" for c in cases))
        print("route fact owners", [c.attrib["name"] for c in cases
              if c.attrib["classname"] == "tests.test_sec_research_routes" and "fact" in c.attrib["name"]])

current = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
           for name in summary["hashes"]}
assert current == summary["hashes"]
print("product hashes match archived summary", json.dumps(current, sort_keys=True))
for mutant in ("float", "as-of-end", "ids-latest"):
    hashes = json.loads((TASK / ("inverse-final-" + mutant) / "hashes.json").read_text())
    assert hashes["before"] == hashes["after"] == current
    print("inverse hashes match", mutant)
assert hashlib.sha256((TASK / "mutants/test_sec_research_fact_queries.py").read_bytes()).hexdigest() == current["tests/test_sec_research_fact_queries.py"]
print("scratch inverse owners match current test file")
