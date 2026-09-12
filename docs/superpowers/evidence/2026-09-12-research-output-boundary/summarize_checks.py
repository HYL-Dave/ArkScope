"""Summarize only runner metadata/JUnit, never fixture databases or token files."""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def summarize(work):
    records = []
    for record_path in sorted(work.glob("*/command.json")):
        command = json.loads(record_path.read_text())
        root = record_path.parent
        row = {"run": root.name, "exit_code": command["exit_code"],
               "seconds": command["seconds"], "command": command["command"]}
        files = [record_path, root / "output.log"]
        junit = root / "results.xml"
        if junit.exists():
            files.append(junit)
            tree = ET.parse(junit)
            nodes = tree.findall(".//testcase")
            counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
            failures = []
            for node in nodes:
                kind = "passed"
                for tag, state in (("failure", "failed"), ("error", "error"), ("skipped", "skipped")):
                    if node.find(tag) is not None:
                        kind = state
                        break
                counts[kind] += 1
                if kind in ("failed", "error"):
                    failures.append({"class": node.get("classname"), "name": node.get("name"), "kind": kind})
            row.update(counts=counts, failure_nodes=failures)
        else:
            row["junit"] = "not_produced"
        row["sha256"] = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
        records.append(row)
    return {"runs": records, "count_note": "Runs may overlap; counts must not be summed into a test-suite claim."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = summarize(Path(__file__).resolve().parent)
    with args.output.open("x") as output:
        json.dump(result, output, indent=2)
        output.write("\n")
    print(json.dumps({"runs": len(result["runs"]), "output": str(args.output)}))
