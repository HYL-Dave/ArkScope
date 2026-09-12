"""Check final JUnit/source identities, without reading application state."""

import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

WORK = Path(__file__).resolve().parent
NEW_SUITES = (
    "test_output_boundary", "test_tool_output_policy", "test_tool_output_channels",
    "test_research_output_events", "test_research_output_lifetimes",
    "test_model_catalog_output_boundary", "test_research_output_compaction",
)
RETAINED_OWNERS = (
    "test_native_key_echo_is_redacted_before_logs_scratchpad_and_public_errors",
    "test_openai_retry_key_echo_is_private_without_changing_retry_policy",
    "test_enabled_sdk_tracing_excludes_sensitive_data_preserves_metadata",
    "test_api_fixed_dispatch_pins_complete_selection",
    "test_failed_generation_redacts_selected_key_after_activation",
    "test_card_oauth_auth_failure_survives_sdk_to_http_without_retry_or_storage",
    "test_original_oauth_id_can_refresh_normally_without_reselection",
)


def counts(nodes):
    result = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    for node in nodes:
        if node.find("failure") is not None:
            result["failed"] += 1
        elif node.find("error") is not None:
            result["errors"] += 1
        elif node.find("skipped") is not None:
            result["skipped"] += 1
        else:
            result["passed"] += 1
    return result


def main(run, before_name, after, output):
    before = json.loads((WORK / before_name).read_text())
    final = json.loads((WORK / after).read_text())
    identity_fields = ("source_files", "source_collection_sha256", "runner_sha256",
                       "python", "sqlite", "packages")
    drift = [key for key in identity_fields if before[key] != final[key]]
    command = json.loads((WORK / run / "command.json").read_text())
    junit = WORK / run / "results.xml"
    nodes = ET.parse(junit).findall(".//testcase")
    total = counts(nodes)
    suites = {name: counts([node for node in nodes
                           if name in node.get("classname", "").split(".")])
              for name in NEW_SUITES}
    retained = {name: counts([node for node in nodes
                             if node.get("name", "").split("[", 1)[0] == name])
                for name in RETAINED_OWNERS}
    skipped = [{"class": node.get("classname"), "name": node.get("name"),
                "reason": node.find("skipped").get("message")}
               for node in nodes if node.find("skipped") is not None]
    checks = {
        "source_and_runtime_unchanged": not drift,
        "command_exit_zero": command["exit_code"] == 0,
        "explicit_tests_directory": "tests" in command["command"],
        "no_backend_failure_or_error": total["failed"] == total["errors"] == 0,
        "all_new_suites_executed_without_skip": all(
            value["passed"] > 0 and value["failed"] == value["errors"] == value["skipped"] == 0
            for value in suites.values()
        ),
        "retained_safety_owners_executed_without_skip": all(
            value["passed"] > 0 and value["failed"] == value["errors"] == value["skipped"] == 0
            for value in retained.values()
        ),
    }
    result = {"checks": checks, "source_drift": drift, "backend": total,
              "new_suite_counts": suites, "retained_owner_counts": retained, "skipped": skipped,
              "junit_sha256": hashlib.sha256(junit.read_bytes()).hexdigest(),
              "source_collection_sha256": final["source_collection_sha256"],
              "head": final["head"], "test_command": command["command"],
              "seconds": command["seconds"],
              "note": "Complete backend totals include the new suites; do not add them twice."}
    with output.open("x") as target:
        json.dump(result, target, indent=2, sort_keys=True)
        target.write("\n")
    print(json.dumps(result, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run")
    parser.add_argument("before")
    parser.add_argument("after")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    raise SystemExit(main(args.run, args.before, args.after, args.output))
