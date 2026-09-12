"""Inventory completed plan receipts without visiting their fixture directories."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

WORK = Path(__file__).resolve().parent
rows, unfinished = [], []
for folder in sorted(WORK.iterdir()):
    if not folder.is_dir() or folder.is_symlink() or folder.name == "sqlite-candidate":
        continue
    receipt = folder / "command.json"
    if not receipt.exists():
        if (folder / "output.log").exists():
            unfinished.append(folder.name)
        continue
    command = json.loads(receipt.read_text())
    record = {"run": folder.name, "exit_code": command["exit_code"],
              "seconds": command["seconds"],
              "command_sha256": hashlib.sha256(receipt.read_bytes()).hexdigest()}
    junit = folder / "results.xml"
    if junit.exists():
        nodes = ET.parse(junit).findall(".//testcase")
        counts = Counter({"passed": 0, "failed": 0, "errors": 0, "skipped": 0})
        failures = []
        for node in nodes:
            state = ("failed" if node.find("failure") is not None else
                     "errors" if node.find("error") is not None else
                     "skipped" if node.find("skipped") is not None else "passed")
            counts[state] += 1
            if state in {"failed", "errors"}:
                failures.append({"class": node.get("classname"), "name": node.get("name"), "state": state})
        record.update(cases=len(nodes), outcomes=dict(counts), failures=failures,
                      junit_sha256=hashlib.sha256(junit.read_bytes()).hexdigest())
    rows.append(record)
if unfinished:
    raise SystemExit("Unfinished run receipts: " + ", ".join(unfinished))
record = {"runs": rows, "unfinished": unfinished,
          "note": "Separate RED, inverse, intermediate failure, focused and full runs are not an additive passing-test total. Read phase reports for nonzero dispositions."}
with (WORK / "run-accounting.json").open("x") as output:
    json.dump(record, output, indent=2, sort_keys=True)
    output.write("\n")
print(json.dumps({"completed_runs": len(rows), "nonzero_runs": sum(row["exit_code"] != 0 for row in rows), "unfinished": unfinished}))
