"""Create-only archive of the source canary and its one analysis diagnostic."""

import hashlib
import json
from pathlib import Path
import shutil
import sys

import claude_canary

PACKET = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKET.parent / "2026-09-07-lifecycle-web-sonnet-canary"))
from scan_packet import scan_files


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    live = Path("/tmp/lifecycle-usage-live-r1")
    diagnostic = Path("/tmp/lifecycle-usage-analysis-diagnostic-r1")
    target = PACKET / "failed-live-r1"
    claude_canary.CHECKPOINT_SEAL = "37747682f666575d7df400f8db53ed54e21d5842bef60fe7caaf2848de7f7e96"
    admitted = claude_canary.source_identity()
    metrics = json.loads((live / "metrics.json").read_text())
    result = json.loads((live / "result.json").read_text())
    plan = json.loads((live / "authorized-plan.json").read_text())
    probe = json.loads((diagnostic / "metrics.json").read_text())
    assert claude_canary.digest(plan) == "e1f1cec9f7063e5eef46c8636b991b8a82a294d6694862fade88f0f7f9fd5f54"
    assert plan["offline_source"] == admitted
    assert metrics["sdk_query_submissions"] == metrics["journal_model_submissions"] == 2
    assert metrics["source_http_requests"] == 4
    assert [entry["status"] for entry in metrics["source_reads"]] == ["captured", "captured", "failed", "captured"]
    assert metrics["human_assessments_created"] == metrics["human_adoptions_created"] == 0
    assert result["status"] == "failed" and result["failure_code"] == "model_result_incomplete"
    assert result["usage_report"]["coverage"] == "partial" and result["usage_report"]["recorded_submissions"] == 1
    assert metrics["local_children_reaped"] == [True, True]
    assert probe["sdk_submissions"] == 1 and probe["source_http_requests"] == probe["search_submissions"] == 0
    assert probe["local_children_reaped"] == [True]
    assert probe["selected_metadata_unchanged"] and probe["original_capture_unchanged"]
    assert probe["harness_sha256"] == sha(PACKET / "diagnose_analysis.py")
    assert all(sha(live / name) == expected for name, expected in probe["capture_files_sha256"].items())
    attempts = [attempt for event in probe["events"] for attempt in event.get("structured_output_attempts", [])]
    assert len(attempts) == 2 and all(not item["schema_valid"] for item in attempts)
    assert all("$FUNCTION_NAME" in str(item["schema_errors"]) and "$PARAMETER_NAME" in str(item["schema_errors"]) for item in attempts)
    sessions = [entry["events"] for entry in metrics["sessions"]] + [probe["events"]]
    for events in sessions:
        init = [event for event in events if event["kind"] == "init"]
        assert len(init) == 1 and init[0]["api_key_source"] == "none"
        assert init[0]["session_matches_request"] and init[0]["mcp_server_count"] == 0
        assert init[0]["model"] == "claude-sonnet-5"
    files = {"live-" + name: live / name for name in ("authorized-plan.json", "metrics.json", "result.json", "search-output.json")}
    files.update({"diagnostic-" + name: diagnostic / name for name in ("prepared.json", "metrics.json")})
    files.update({name: PACKET / name for name in ("claude_canary.py", "diagnose_analysis.py", "test_analysis_diagnostic.py", "live-authorization.md")})
    assert scan_files(files)["unexpected"] == 0
    target.mkdir()
    for name, path in files.items():
        with path.open("rb") as incoming, (target / name).open("xb") as outgoing:
            shutil.copyfileobj(incoming, outgoing)
    claude_canary.write_new_json(target / "verification.json", {
        "complete_investigation_live_verified": False, "source_reader_captured_pages": 3,
        "source_unavailable_pages": 1, "sdk_submissions": 3, "source_http_requests": 4,
        "source_http_budget_remaining": 4, "subscription_api_key_source_values": ["none", "none", "none"],
        "main_and_helper_model": "claude-sonnet-5", "original_source_checkpoint": admitted,
        "first_analysis_cause": "unobserved_tool_result_details; max_turns_owned_terminal",
        "diagnostic_cause": "two_literal_function_parameter_wrapper_outputs_fail_required_field_schema",
        "native_terminal": "error_max_turns", "rate_limit_failure_observed": False,
        "upstream_similar_report": "https://github.com/anthropics/claude-code/issues/87234",
        "upstream_report_is_not_vendor_confirmation": True,
        "profile_writes": False, "migration": False, "adoptions": 0,
        "app_restart": False, "commit": False, "merge": False, "push": False,
        "raw_temporary_journal_sha256": sha(live / "profile.sqlite"),
        "raw_temporary_journal_archived": False,
        "diagnostic_rehearsal": {"passed": 14, "initial_import_order_fixture_failures_corrected": 3},
    })
    scan = scan_files({str(path.relative_to(target)): path for path in target.iterdir()})
    assert scan["unexpected"] == 0
    claude_canary.write_new_json(target / "secret-shape-scan.json", scan)
    claude_canary.write_new_json(target / "files.sha256.json", {"files": {
        path.name: sha(path) for path in sorted(target.iterdir())}})
    print(json.dumps({"failed_live_seal_sha256": sha(target / "files.sha256.json"), "sdk_submissions": 3, "source_http_requests": 4}))


if __name__ == "__main__":
    main()
