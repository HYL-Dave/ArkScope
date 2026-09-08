"""Freeze the renewed full canary before changing its output transport."""

import hashlib
import json
from pathlib import Path
import shutil

import claude_canary as original
from record_prompt_admission import scan_files


PACKET = Path(__file__).resolve().parent
LIVE = Path("/tmp/lifecycle-renewed-full-r3")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    admitted = original.require_sources(original.ROOT, PACKET / "turns-admission",
        "3bd019ea5014e06a0249173e208ac5f7900ee9c063081c9e017b77afc1e438d4")
    metrics = json.loads((LIVE / "metrics.json").read_text())
    result = json.loads((LIVE / "result.json").read_text())
    plan = json.loads((LIVE / "authorized-plan.json").read_text())
    native = json.loads((LIVE / "native-diagnostics.json").read_text())
    assert original.digest(plan) == "34c60b957b81cb421a995a2850c4ab87e6bcc1ebf84f8bce0ad9fd6ddbe04110"
    assert plan["offline_source"] == admitted
    assert metrics["sdk_query_submissions"] == metrics["journal_model_submissions"] == 2
    assert metrics["source_http_requests"] == 4
    assert metrics["human_assessments_created"] == metrics["human_adoptions_created"] == 0
    assert metrics["local_children_reaped"] == [True, True] and metrics["selected_metadata_unchanged"]
    assert result["status"] == "failed" and result["failure_code"] == "model_result_incomplete"
    assert result["usage_report"]["coverage"] == "partial" and result["usage_report"]["recorded_submissions"] == 1
    assert [row["status"] for row in metrics["source_reads"]] == ["captured", "captured", "captured", "failed"]
    assert metrics["source_reads"][-1]["code"] == "source_request_budget_exhausted"
    for session in metrics["sessions"]:
        init = [row for row in session["events"] if row["kind"] == "init"]
        assert len(init) == 1 and init[0]["api_key_source"] == "none"
        assert init[0]["model"] == "claude-sonnet-5" and init[0]["session_matches_request"]
        assert init[0]["mcp_server_count"] == 0 and session["fallback_model"] is None
        assert set(session["helper_model_overrides"].values()) == {"claude-sonnet-5"}
    attempts = [attempt for event in native["events"] if event["phase"] == "analysis"
                for attempt in event.get("structured_output_attempts", [])]
    assert len(attempts) == 2 and all(not row["schema_valid"] for row in attempts)
    assert all("$PARAMETER_NAME" in str(row["schema_errors"]) for row in attempts)
    terminal = [row for row in native["events"] if row["phase"] == "analysis" and row["kind"] == "result"]
    assert len(terminal) == 1 and terminal[0]["terminal_reason"] == "max_turns"
    assert terminal[0]["subtype"] == "error_max_turns" and not terminal[0]["has_structured_output"]
    target = PACKET / "failed-renewed-r3"
    files = {name: LIVE / name for name in ("authorized-plan.json", "search-output.json", "metrics.json",
                                           "result.json", "native-diagnostics.json")}
    files.update({name: PACKET / name for name in ("renewed_full_canary.py", "diagnose_analysis.py",
        "test_analysis_diagnostic.py", "live-authorization.md", "record_renewed_failure.py")})
    assert scan_files(files)["unexpected"] == 0
    target.mkdir()
    for name, path in files.items():
        with path.open("rb") as incoming, (target / name).open("xb") as outgoing:
            shutil.copyfileobj(incoming, outgoing)
    original.write_new_json(target / "verification.json", {
        "offline_source": admitted, "current_full_investigation_live_verified": False,
        "cause": "schema_prompt_did_not_prevent_literal_parameter_wrapper_on_toolless_analysis",
        "native_completion_count_guard_caused_this_failure": False,
        "sdk_submissions_this_run": 2, "sdk_submissions_campaign_so_far": 6,
        "source_http_attempts_this_run": 4, "source_http_campaign_attempts": 8,
        "source_http_budget_remaining": 0, "source_pages_captured": 3,
        "source_candidate_not_dispatched_due_to_budget": 1,
        "rate_limit_failure_observed": False, "subscription_auth_values": ["none", "none"],
        "main_and_helper_model": "claude-sonnet-5", "profile_writes": False, "adoptions": 0,
        "capture_files_sha256": {name: sha(LIVE / name) for name in
            ("authorized-plan.json", "search-output.json", "result.json", "metrics.json", "profile.sqlite")},
        "raw_temporary_journal_archived": False, "migration": False, "restart": False,
        "commit": False, "merge": False, "push": False,
    })
    scan = scan_files({path.name: path for path in target.iterdir()})
    assert scan["unexpected"] == 0
    original.write_new_json(target / "secret-shape-scan.json", scan)
    original.write_new_json(target / "files.sha256.json", {"files": {path.name: sha(path) for path in sorted(target.iterdir())}})
    print(json.dumps({"failed_renewed_seal_sha256": sha(target / "files.sha256.json"),
                      "sdk_submissions": 6, "source_http_attempts": 8}))


if __name__ == "__main__":
    main()
