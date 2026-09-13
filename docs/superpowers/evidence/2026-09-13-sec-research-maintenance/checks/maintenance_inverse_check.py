"""Reconcile retained inverse receipts and source restoration without pytest."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
parser = argparse.ArgumentParser()
parser.add_argument("output")
parser.add_argument("--source-anchor")
parser.add_argument("--pattern", default="task6-inverse-*-source")
parser.add_argument("--expected-cases", nargs="+", default=[
    "skip-recheck", "event-only", "charge", "backup", "unknown-prefix", "lease"])
args = parser.parse_args()


def source_sha(name):
    if args.source_anchor is None:
        return sha(ROOT / name)
    result = subprocess.run(["git", "show", f"{args.source_anchor}:{name}"],
                            cwd=ROOT, capture_output=True, check=True)
    return hashlib.sha256(result.stdout).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


records = []
for directory in sorted(WORK.glob(args.pattern)):
    receipt = json.loads((directory / "receipt.json").read_text())
    checks = {}
    for name, expected in receipt["restored"].items():
        checks[name + ":original"] = sha(directory / (Path(name).name + ".original")) == expected
        checks[name + ":restored_checkpoint"] = source_sha(name) == expected
        checks[name + ":mutated"] = sha(directory / (Path(name).name + ".mutated")) == receipt["mutated"][name]
        checks[name + ":distinct"] = expected != receipt["mutated"][name]
    for name, expected in receipt["tests"].items():
        checks[name + ":unchanged"] = source_sha(name) == expected
    aborted = receipt.get("status") == "aborted_before_runner"
    failures = []
    if aborted:
        checks["abort_no_runner_or_applied_mutation"] = (
            receipt["runner_invoked"] is False and receipt["source_mutation_applied"] is False
            and not (WORK / receipt["run"]).exists())
    else:
        run = WORK / receipt["run"]
        command = json.loads((run / "command.json").read_text())
        cases = ET.parse(run / "results.xml").findall(".//testcase")
        failures = [n.get("classname") + "::" + n.get("name") for n in cases if n.find("failure") is not None]
        errors = [n for n in cases if n.find("error") is not None]
        checks["runner_failed_behaviorally"] = command["exit_code"] == receipt["exit_code"] == 1 and bool(failures) and not errors
        checks["exact_failed_nodes"] = sorted(failures) == sorted(receipt["failed_testcases"])
        checks["no_reported_errors"] = not receipt["error_testcases"]
    records.append({"case": receipt["case"], "run": receipt["run"],
                    "classification": "aborted_before_runner" if aborted else "killed_inverse",
                    "checks": checks, "failed_nodes": failures,
                    "receipt_sha256": sha(directory / "receipt.json")})
accepted = [r for r in records if r["classification"] == "killed_inverse"]
expected_cases = set(args.expected_cases)
valid = len(accepted) == len(expected_cases) and {r["case"] for r in accepted} == expected_cases
valid = valid and all(all(r["checks"].values()) for r in records)
result = {"passed": valid, "records": records,
          "source_anchor": args.source_anchor or "working_tree_at_execution",
          "accepted_inverses": len(accepted), "retained_aborts": len(records) - len(accepted),
          "limit": "Receipt/source readback, not a fresh mutation run or actual-store validation."}
with (WORK / args.output).open("x") as output:
    json.dump(result, output, indent=2, sort_keys=True)
    output.write("\n")
print(json.dumps({key: result[key] for key in ("passed", "accepted_inverses", "retained_aborts")}))
raise SystemExit(0 if valid else 1)
