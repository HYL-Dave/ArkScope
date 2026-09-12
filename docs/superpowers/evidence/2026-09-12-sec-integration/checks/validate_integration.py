"""Reconcile actual JUnit nodes and frozen sources without application imports."""

import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
BASE = ROOT / "docs/superpowers/evidence/2026-09-12-research-output-boundary/backend-full-04/results.xml.gz"
parser = argparse.ArgumentParser()
parser.add_argument("run")
parser.add_argument("before")
parser.add_argument("after")
parser.add_argument("output")
args = parser.parse_args()
CURRENT = WORK / args.run / "results.xml"
RETAINED_OWNERS = (
    "test_native_key_echo_is_redacted_before_logs_scratchpad_and_public_errors",
    "test_openai_retry_key_echo_is_private_without_changing_retry_policy",
    "test_enabled_sdk_tracing_excludes_sensitive_data_preserves_metadata",
    "test_api_fixed_dispatch_pins_complete_selection",
    "test_failed_generation_redacts_selected_key_after_activation",
    "test_card_oauth_auth_failure_survives_sdk_to_http_without_retry_or_storage",
    "test_original_oauth_id_can_refresh_normally_without_reselection",
)


def identity(node):
    return node.get("classname"), node.get("name")


def counts(nodes):
    result = Counter({"passed": 0, "failed": 0, "errors": 0, "skipped": 0})
    for node in nodes:
        state = ("failed" if node.find("failure") is not None else
                 "errors" if node.find("error") is not None else
                 "skipped" if node.find("skipped") is not None else "passed")
        result[state] += 1
    return dict(result)


def collected_identity(line):
    # Parameter IDs can contain :: (IPv6 and URLs); split only the test prefix.
    prefix, bracket, parameters = line.partition("[")
    parts = prefix.split("::")
    assert parts[0].endswith(".py") and len(parts) >= 2
    module = parts[0][:-3].replace("/", ".")
    return ".".join([module, *parts[1:-1]]), parts[-1] + bracket + parameters


previous = ET.fromstring(gzip.decompress(BASE.read_bytes())).findall(".//testcase")
current = ET.parse(CURRENT).findall(".//testcase")
previous_ids, current_ids = Counter(map(identity, previous)), Counter(map(identity, current))
collection = WORK / "backend-final-collection/output.log"
collected = Counter(collected_identity(line) for line in collection.read_text().splitlines()
                    if line.startswith("tests/") and ".py::" in line)
before = json.loads((WORK / args.before).read_text())
after = json.loads((WORK / args.after).read_text())
fields = ("immutable_source_anchor", "source_files", "source_collection_sha256",
          "runner_sha256", "python", "sqlite", "packages")
drift = [key for key in fields if before[key] != after[key]]
command = json.loads((WORK / args.run / "command.json").read_text())
collect_command = json.loads((WORK / "backend-final-collection/command.json").read_text())
totals = counts(current)
retained = {name: counts([node for node in current
                         if node.get("name", "").split("[", 1)[0] == name])
            for name in RETAINED_OWNERS}
skipped_before = Counter(identity(node) for node in previous if node.find("skipped") is not None)
skipped_after = Counter(identity(node) for node in current if node.find("skipped") is not None)
new_modules = ("test_sec_research_native_dispatch", "test_sec_research_tool_adapters",
               "test_sec_research_tool_results", "test_sec_research_output_integration",
               "test_sec_transport_cancellation")
new_suites = {name: counts([node for node in current
                           if name in node.get("classname", "").split(".")])
              for name in new_modules}
checks = {
    "complete_commands_succeeded": command["exit_code"] == collect_command["exit_code"] == 0,
    "explicit_tests_directory": "tests" in command["command"],
    "no_backend_failures_or_errors": totals["failed"] == totals["errors"] == 0,
    "collected_equals_executed": collected == current_ids,
    "no_duplicate_nodes": all(value == 1 for value in current_ids.values()),
    "unchanged_skip_ids": skipped_before == skipped_after,
    "immutable_source_anchor_matches": before["source_matches_anchor"] and after["source_matches_anchor"],
    "no_source_runtime_or_runner_drift": not drift,
    "retained_safety_owners_ran": all(row["passed"] > 0 and not any(row[k] for k in
        ("failed", "errors", "skipped")) for row in retained.values()),
    "new_regression_suites_ran": all(row["passed"] > 0 and not any(row[k] for k in
        ("failed", "errors", "skipped")) for row in new_suites.values()),
}
record = {
    "checks": checks, "backend": totals, "collected": sum(collected.values()),
    "executed": len(current), "baseline": counts(previous),
    "added": sorted((current_ids - previous_ids).elements()),
    "removed": sorted((previous_ids - current_ids).elements()),
    "source_drift": drift, "source_anchor": after["immutable_source_anchor"],
    "source_files": len(after["source_files"]),
    "source_collection_sha256": after["source_collection_sha256"],
    "sqlite": after["sqlite"], "seconds": command["seconds"],
    "retained_safety_owners": retained, "new_suites": new_suites,
    "skipped": sorted(skipped_after),
    "junit_sha256": hashlib.sha256(CURRENT.read_bytes()).hexdigest(),
    "baseline_junit_gzip_sha256": hashlib.sha256(BASE.read_bytes()).hexdigest(),
    "source_snapshot_before": args.before, "source_snapshot_after": args.after,
    "limit": "Read source snapshot filenames for observation timing; this is not full SEC release acceptance.",
}
with (WORK / args.output).open("x") as output:
    json.dump(record, output, indent=2, sort_keys=True)
    output.write("\n")
print(json.dumps({"checks": checks, "backend": totals, "collected": record["collected"],
                  "added": len(record["added"]), "removed": len(record["removed"]),
                  "seconds": record["seconds"]}, indent=2))
raise SystemExit(0 if all(checks.values()) else 1)
