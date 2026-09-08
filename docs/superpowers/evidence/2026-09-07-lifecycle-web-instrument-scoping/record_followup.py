"""Publish the bounded public-original diagnostic, without source quotations."""

import hashlib
import importlib.util
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.with_name("2026-09-07-lifecycle-web-usage-canary")))
import claude_canary as original
from record_json_admission import checked_packet, scan_files
SPEC = importlib.util.spec_from_file_location("instrument_result_projection", HERE / "record_live.py")
projection = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(projection)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    admitted = original.require_sources(ROOT, HERE / "admission", "05a81e10133bbd66fe14b42fed636d4b2cd6f629cef4c379dda43000ce7d7781")
    checked_packet(HERE / "live-r1", "bcdb7581d9447177ad386e7c85d2b4eea73b6c1d59a472d590ff86504d7a5ab1")
    checked_packet(HERE / "failed-original-analysis-r1", "ff1ed46b26e044e60cf8d199d7e2014669a58a429b551c9a20c03af7c877ab4d")
    target = HERE / "public-original-followup"
    source_reports, raw_files, outputs = [], {}, {}
    for name in ("original", "document"):
        work = Path(f"/tmp/lifecycle-instrument-{name}-r1")
        metrics = json.loads((work / "metrics.json").read_text())
        assert metrics["source_checkpoint"] == admitted and metrics["sdk_submissions"] == 0
        assert metrics["source_http_attempts"] == len(metrics["observations"]) == 2
        assert all(row["status"] == 200 and row["result_code"] == "complete" for row in metrics["observations"])
        raw_files[name] = {path.name: sha(path) for path in work.iterdir() if path.is_file()}
        source_reports.append(metrics)
        outputs[name + "-metrics.json"] = metrics
    assert source_reports[0]["source_http_campaign_used"] == 7
    assert source_reports[1]["source_http_campaign_used"] == 9
    failed = json.loads((HERE / "failed-original-analysis-r1/metrics.json").read_text())
    work = Path("/tmp/lifecycle-instrument-original-analysis-r2")
    metrics = json.loads((work / "metrics.json").read_text())
    output = json.loads((work / "analysis-output.json").read_text())
    for value in (failed, metrics):
        assert value["sdk_submissions"] == value["model_requests"] == value["token_loads"] == 1
        assert value["source_http_requests"] == value["search_submissions"] == 0
        assert value["source_checkpoint"] == admitted and value["local_children_reaped"] == [True]
        assert value["selected_metadata_unchanged"] and value["original_capture_unchanged"] and value["document_capture_unchanged"]
        init = [item for item in value["events"] if item["kind"] == "init"]
        ends = [item for item in value["events"] if item["kind"] == "result"]
        assert len(init) == len(ends) == 1
        assert init[0]["api_key_source"] == "none" and init[0]["model"] == "claude-sonnet-5"
        assert init[0]["tools"] == [] and init[0]["mcp_server_count"] == 0 and init[0]["session_matches_request"]
        assert ends[0]["model_usage_models"] == ["claude-sonnet-5"] and ends[0]["num_turns"] == 1
        assert ends[0]["session_matches_request"] and ends[0]["terminal_reason"] == "completed"
    assert metrics["status"] == "completed" and metrics["validated_finding"]["action"] is None
    assert metrics["native_final"]["host_schema_valid"] and metrics["native_final"]["schema_errors"] == []
    assert metrics["native_final"]["private_capture_sha256"] == sha(work / "native-final.json")
    assert metrics["prompt_sha256"] == failed["prompt_sha256"]
    assert metrics["harness_sha256"] == sha(HERE / "diagnose_original_analysis.py")
    raw_files["analysis-r2"] = {path.name: sha(path) for path in work.iterdir() if path.is_file()}
    outputs["analysis-metrics.json"] = metrics
    outputs["analysis-projection.json"] = output
    positive = json.loads((HERE / "source-binding-control.json").read_text())
    assert positive["actual_selected_context"] == {"action": "terminal_delisting", "block_reasons": []}
    target.mkdir()
    for name, value in outputs.items():
        original.write_new_json(target / name, projection.without_quotations(value))
    original.write_new_json(target / "verification.json", {
        "source_checkpoint": admitted, "raw_files_sha256": raw_files,
        "verifier_sha256": sha(Path(__file__)), "sdk_submissions_this_turn": 4,
        "source_http_attempts_this_turn": 9, "source_http_budget_remaining": 15,
        "fresh_full_live_runs": 1, "fresh_action_ready_live_runs": 0,
        "public_original_followed_by_host_diagnostic_not_product_agent": True,
        "primary_document_read_after_index_metadata": True,
        "whole_document_encoded_bytes": source_reports[1]["observations"][-1]["received_body_bytes"],
        "whole_document_decoded_bytes": source_reports[1]["observations"][-1]["decoded_body_bytes"],
        "capacity_limit_was_not_reached": True,
        "output_failure_r1_cause_unobserved": True,
        "same_input_analysis_r2_schema_valid_but_not_actionable": metrics["validated_finding"],
        "manual_positive_control_not_model_result": positive,
        "remaining_product_gaps": [
            "No search/follow-source pass after discovering publisher-provided partial text",
            "No bounded correction of citation, definition, date or contradictory-label output",
            "Journal call-id CHECK admits only search-1 and analysis-1; expansion requires an explicit schema decision",
        ],
        "all_model_calls_exact_sonnet_subscription": True, "automatic_retry_or_billing_fallback": False,
        "production_writes_install_restart_commit_merge_push": False,
    })
    scan = scan_files({path.name: path for path in target.iterdir()})
    assert scan["unexpected"] == 0
    original.write_new_json(target / "secret-shape-scan.json", scan)
    original.write_new_json(target / "files.sha256.json", {"files": {path.name: sha(path) for path in sorted(target.iterdir())}})
    print(json.dumps({"followup_seal_sha256": sha(target / "files.sha256.json"),
        "sdk_submissions_this_turn": 4, "source_http_attempts_this_turn": 9,
        "action_ready_live_findings": 0, "provider_calls_by_recorder": 0}))


if __name__ == "__main__":
    main()
