"""Account for every finished check, including RED and fixture failures."""

from collections import Counter
import json
from pathlib import Path
import xml.etree.ElementTree as ET

WORK = Path(__file__).resolve().parent
NONZERO = {
    "route-red": "route inventory drift reproduced",
    "child-red": "model I/O heartbeat regression reproduced; route controls pass",
    "cancellation-red": "response cleanup ownership regression reproduced",
    "authority-covering": "new integrity fixture compared sqlite3.Row to tuple",
    "close-entry-red": "first cancellation during response close reproduced",
    "error-entry-red": "pre-stream error response cleanup regression reproduced",
    "backend-full": "complete suite found missed async mock in lifetime fixture",
    "lifetime-collateral-red": "isolated lifetime fixture collateral reproduced",
}
rows = []
for path in sorted(WORK.glob("*/command.json")):
    record = json.loads(path.read_text())
    name = path.parent.name
    assert record["name"] == name
    assert bool(record["exit_code"]) == (name in NONZERO), name
    row = {
        "run": name, "exit_code": record["exit_code"], "seconds": record["seconds"],
        "classification": NONZERO.get(name, "passed check"),
    }
    junit = path.with_name("results.xml")
    if junit.exists():
        counts = Counter()
        for case in ET.parse(junit).findall(".//testcase"):
            state = next((kind for kind in ("failure", "error", "skipped")
                          if case.find(kind) is not None), "passed")
            counts[state] += 1
        row["junit"] = dict(counts)
    rows.append(row)
unfinished = sorted(path.parent.name for path in WORK.glob("*/output.log")
                    if not path.with_name("command.json").exists())
assert not unfinished
assert NONZERO.keys() <= {row["run"] for row in rows}
before = json.loads((WORK / "source-before.json").read_text())
after = json.loads((WORK / "accepted-source-after.json").read_text())
frontend = lambda snapshot: [row for row in snapshot["source_files"]
                             if row["path"].startswith("apps/arkscope-web/")]
assert frontend(before) == frontend(after)
result = {
    "runs": rows, "run_count": len(rows), "nonzero_count": len(NONZERO),
    "unfinished": unfinished, "overlapping_checks_are_not_summed": True,
    "frontend_source_unchanged": {
        "from": before["immutable_source_anchor"],
        "to": after["immutable_source_anchor"], "paths": len(frontend(after)),
    },
}
with (WORK / "checks-summary.json").open("x") as output:
    json.dump(result, output, indent=2, sort_keys=True)
    output.write("\n")
print(json.dumps(result, indent=2))
