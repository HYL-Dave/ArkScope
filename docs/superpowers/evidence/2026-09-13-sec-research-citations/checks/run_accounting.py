"""Inventory all actual check receipts, retaining failures without aggregating scopes."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

WORK = Path(__file__).resolve().parent
EXCEPTIONS = {
    "inverse-recovery-500-01": "launcher annotation setup failure; rerun02 proves inverse",
    "citations-browser-01": "preview listener blocked by test-only DNS guard; corrected preview-only wrapper",
    "final-review-cancel-green": "controller nonexistent test path; exit4 and zero tests; corrected02",
    "task2-red-01": "mixed missing behavior and incorrect Anthropic fixture patch target; corrected02",
    "task2-green-01": "incorrect fixture isinstance against generic RunHooks alias; corrected hook owners",
    "task2-regression-01": "two old exact start-event assertions missing newly required call_id",
    "task2-edge-red-01": "mixed ChatGPT error-evidence gap and misplaced fixture assertion; corrected02",
    "task2-edge-red-02": "error-evidence RED plus deliberate exact-ID dedup inverse; see task2 report",
    "task4-green-01": "test Response reuse and post-unpin focus fixture assumptions; see task4 report",
    "task4-green-02": "test Response reuse and post-unpin focus fixture assumptions; see task4 report",
    "task4-full-01": "localized interpolation and locale inventory collateral; corrected final03",
    "task4-final-full-01": "localized interpolation and locale inventory collateral; corrected final03",
    "task4-final-typecheck-02": "reserved i18next ordinal boolean option; renamed to position",
    "task4-final-build-02": "reserved i18next ordinal boolean option; renamed to position",
}

rows = []
unclassified = []
for path in sorted(WORK.glob("*/command.json")):
    command = json.loads(path.read_text())
    name, code = command["name"], command["exit_code"]
    if code == 0:
        classification = "completed_check; scope from exact command, not additive coverage"
    elif name in EXCEPTIONS:
        classification = EXCEPTIONS[name]
    elif "census" in name and code == 2:
        classification = "review_required; use separate classified census report"
    elif "-red" in name or name.startswith("inverse-"):
        classification = "retained RED/inverse; exact intended owner evidence in task/inverse reports"
    else:
        classification = "UNCLASSIFIED"
        unclassified.append(name)
    counts = None
    xml = path.parent / "results.xml"
    failures = []
    if xml.exists():
        counts = Counter()
        for node in ET.parse(xml).findall(".//testcase"):
            state = next((tag for tag in ("failure", "error", "skipped") if node.find(tag) is not None), "passed")
            counts[state] += 1
            if state in {"failure", "error"}:
                failures.append([node.get("classname"), node.get("name"), state])
    rows.append({"run": name, "exit_code": code, "seconds": command["seconds"],
                 "classification": classification, "junit_counts": counts,
                 "failed_nodes": failures, "command_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
result = {"runs": rows, "unclassified_failures": unclassified,
          "counting_policy": "Only backend-final-full owns the complete backend total; overlapping selections are not added."}
with (WORK / "run-accounting.json").open("x") as target:
    json.dump(result, target, indent=2, sort_keys=True)
    target.write("\n")
print(json.dumps({"runs": len(rows), "nonzero": sum(row["exit_code"] != 0 for row in rows),
                  "unclassified_failures": unclassified}))
raise SystemExit(bool(unclassified))
