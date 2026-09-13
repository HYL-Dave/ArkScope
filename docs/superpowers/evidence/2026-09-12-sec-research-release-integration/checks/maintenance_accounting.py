"""Account only this continuation's receipts without summing overlapping tests."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

WORK = Path(__file__).resolve().parent
KNOWN_FAILURES = {
    "task5-operation-green-01": "validation order/read fsync regression; product corrected, receipt retained",
    "task5-bundle-green-03": "UTF-8 fixture selected no query result; corrected fixture, receipt retained",
    "task6-red-01": "41 missing-owner assertions plus active-run archive fixture failure; fixture fixed before RED02",
    "task6-cleanup-green-01": "dedicated SQLite authorizer restoration denied subsequent SQL; corrected callback, not fingerprint overbinding",
    "task6-cleanup-diagnose-01": "retained diagnostic expanded the closed inspection failure",
    "task6-cleanup-diagnose-02": "retained diagnostic exposed underlying SQLite authorizer DatabaseError",
    "task6-final-frontend": "missed Task5 locale inventory collateral: research224/total2974 must include12 admitted new leaves; full RED retained",
    "task8-workflow-integration-01": "fixture incorrectly expected an index without structural headings to be ok; actual partial/section_index_unavailable is correct, not product RED",
    "task8-workflow-integration-02": "fixture incorrectly applied the index section gap to whole-text pages; exact mode-specific status expectations corrected, not product RED",
}


def account(output, prefix, dispositions=()):
    rows, unclassified, unfinished = [], [], []
    reviewed = {}
    for path in dispositions:
        document = json.loads(path.read_text())
        if "records" in document:
            assert "receipts" not in document
            records = document["records"]
        else:
            records = [{**row, "command_sha256": row["command_json"]["sha256"]}
                       for row in document["receipts"]]
        for row in records:
            if row["name"] in reviewed:
                raise ValueError("duplicate reviewed receipt")
            reviewed[row["name"]] = row
    for directory in sorted(WORK.iterdir()):
        if not directory.is_dir() or not directory.name.startswith(prefix):
            continue
        receipt = directory / "command.json"
        if not receipt.exists():
            if (directory / "output.log").exists():
                unfinished.append(directory.name)
            continue
        command = json.loads(receipt.read_text())
        name, code = command["name"], command["exit_code"]
        assert name == directory.name
        review = reviewed.get(name)
        if review:
            assert review["exit_code"] == code
            assert review["command_sha256"] == hashlib.sha256(receipt.read_bytes()).hexdigest()
            assert review["disposition"] and review["explanation"]
        if code == 0:
            classification = "completed check; scope from exact command"
        elif review:
            classification = review["disposition"] + ": " + review["explanation"]
        elif name in KNOWN_FAILURES:
            classification = KNOWN_FAILURES[name]
        elif "census" in name and code == 2:
            classification = "review_required; see separate census adjudication"
        elif "-red" in name or "-inverse-" in name:
            classification = "retained RED/inverse; intended assertion must be read in the task report"
        else:
            classification = "UNCLASSIFIED"
            unclassified.append(name)
        xml = directory / "results.xml"
        counts, failures = None, []
        if xml.exists():
            counts = Counter()
            for node in ET.parse(xml).findall(".//testcase"):
                state = next((tag for tag in ("failure", "error", "skipped")
                              if node.find(tag) is not None), "passed")
                counts[state] += 1
                if state in {"failure", "error"}:
                    failures.append([node.get("classname"), node.get("name"), state])
        rows.append({"run": name, "exit_code": code, "seconds": command.get("seconds"),
                     "classification": classification, "junit_counts": counts,
                     "failed_nodes": failures,
                     "command_sha256": hashlib.sha256(receipt.read_bytes()).hexdigest()})
    result = {"runs": rows, "unclassified_failures": unclassified, "unfinished": unfinished,
              "counting_policy": "Only the named final full backend run owns its total. Focused runs are not added.",
              "process_limit": "Receipt accounting does not establish absence of unrelated external processes."}
    with (WORK / output).open("x") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({"runs": len(rows), "nonzero": sum(r["exit_code"] != 0 for r in rows),
                      "unclassified_failures": unclassified, "unfinished": unfinished}))
    return int(bool(unclassified or unfinished))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--task5-only", action="store_true")
    parser.add_argument("--prefix", action="append")
    parser.add_argument("--dispositions", type=Path, action="append", default=[])
    args = parser.parse_args()
    prefix = tuple(args.prefix) if args.prefix else (("task5-",) if args.task5_only else ("task5-", "task6-"))
    raise SystemExit(account(args.output, prefix, args.dispositions))
