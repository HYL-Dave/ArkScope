"""Publish measured analysis receipts without republishing source quotations."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil

import claude_canary as original
from diagnose_analysis import snapshot
from record_json_admission import checked_packet, scan_files


PACKET = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def quotation_projection(value):
    result = deepcopy(value)
    for citation in result["citations"]:
        quote = citation.pop("quote")
        citation.update(quote_sha256=hashlib.sha256(quote.encode()).hexdigest(), quote_utf8_bytes=len(quote.encode()))
    return result


def main():
    admitted = original.require_sources(original.ROOT, PACKET / "json-analysis-admission",
        "9c4f48ddc0f4bad452a93b610a610942336390f1ea761fca14bcf12e62e4ba60")
    seals = {"failed-live-r1": "a7df8829579c6069ae4b5b2136f825864aead543b6a5caf1ee20b170c9d50093",
        "host-rejected-replay-r2": "3baa4ea61a1ca1ff918689a5b4e75166f42615a0438ff62eee6509ebd8cf23ac",
        "failed-renewed-r3": "79711c3a3a147242f748b58cc765ab7cf5d3a0dca2335296f4100b02648c2422"}
    for name, value in seals.items():
        checked_packet(PACKET / name, value)
    historical = {name: json.loads((PACKET / name / "verification.json").read_text()) for name in seals}
    sdk_before = historical["failed-live-r1"]["sdk_submissions"] + historical["host-rejected-replay-r2"]["sdk_submissions"] + historical["failed-renewed-r3"]["sdk_submissions_this_run"]
    source_before = historical["failed-live-r1"]["source_http_requests"] + historical["host-rejected-replay-r2"]["source_http_requests"] + historical["failed-renewed-r3"]["source_http_attempts_this_run"]
    assert sdk_before == 6 and source_before == 8
    readback_root = Path("/tmp/lifecycle-recorded-json-readback")
    readback = json.loads((readback_root / "verification.json").read_text())
    assert readback["source_checkpoint"] == admitted and readback["fresh_end_to_end_live_canary"] is False
    reports, files = [], {}
    for label, live, capture in (
        ("R3", Path("/tmp/lifecycle-final-json-analysis-r3"), Path("/tmp/lifecycle-renewed-full-r3")),
        ("R1", Path("/tmp/lifecycle-final-json-analysis-r1"), Path("/tmp/lifecycle-usage-live-r1")),
    ):
        metrics = json.loads((live / "metrics.json").read_text())
        output = json.loads((live / "analysis-output.json").read_text())
        assert metrics["source_checkpoint"] == admitted
        assert metrics["harness_sha256"] == sha(PACKET / "diagnose_analysis.py")
        assert metrics["status"] == "completed" and metrics["sdk_submissions"] == metrics["model_requests"] == 1
        assert metrics["source_http_requests"] == metrics["search_submissions"] == 0 and metrics["token_loads"] == 1
        assert metrics["terminal_statuses"] == {"analysis-1": "completed"}
        assert metrics["original_capture_unchanged"] and metrics["capture_files_sha256"] == snapshot(capture)
        assert metrics["selected_metadata_unchanged"] and metrics["local_children_reaped"] == [True]
        assert metrics["options"]["output_mode"] == "final_json" and metrics["options"]["native_output_format"] is None
        assert metrics["options"]["prompt_schema_matches_contract"] and metrics["options"]["tools"] == []
        init = [event for event in metrics["events"] if event["kind"] == "init"]
        terminal = [event for event in metrics["events"] if event["kind"] == "result"]
        assert len(init) == len(terminal) == 1 and init[0]["api_key_source"] == "none"
        assert init[0]["tools"] == [] and init[0]["mcp_server_count"] == 0
        assert init[0]["model"] == "claude-sonnet-5" and init[0]["session_matches_request"]
        end = terminal[0]
        assert end["subtype"] == "success" and end["terminal_reason"] == "completed" and end["num_turns"] == 1
        assert not end["is_error"] and end["final_json_schema_valid"] and end["native_output"] == output
        assert end["model_usage_models"] == ["claude-sonnet-5"] and end["permission_denial_count"] == 0
        assert metrics["usage_observation"]["values"]["web_search_requests"] == 0
        assert metrics["validated_finding"]["action"] is None
        offline = next(item for item in readback["results"] if item["label"] == label)
        assert offline["block_reasons"] == metrics["validated_finding"]["block_reasons"]
        assert offline["reopened_result_identical"] and offline["adoptions"] == 0
        projected_metrics = deepcopy(metrics)
        for event in projected_metrics["events"]:
            if "native_output" in event:
                event["native_output_projection"] = quotation_projection(event.pop("native_output"))
        files[label + "-metrics-projection.json"] = projected_metrics
        files[label + "-output-projection.json"] = quotation_projection(output)
        files[label + "-prepared.json"] = json.loads((live / "prepared.json").read_text())
        reports.append({"capture": label, "sdk_submissions": 1, "http_attempts": 0,
            "protocol": "completed", "action": None, "finding": metrics["validated_finding"],
            "usage": metrics["usage"], "literal_api_key_source": "none", "tool_names": [],
            "metadata_unchanged": True, "child_reaped": True,
            "raw_files_sha256": {name: sha(live / name) for name in ("prepared.json", "metrics.json", "analysis-output.json")}})
    assert "source_citation_mismatch" in reports[1]["finding"]["block_reasons"]
    assert "finding_incomplete" in reports[0]["finding"]["block_reasons"]
    target = PACKET / "live-json-analysis"
    target.mkdir()
    for name, value in files.items():
        original.write_new_json(target / name, value)
    for name in ("diagnose_analysis.py", "test_analysis_diagnostic.py", "verify_recorded_readback.py", "record_live_json.py"):
        with (PACKET / name).open("rb") as incoming, (target / name).open("xb") as outgoing:
            shutil.copyfileobj(incoming, outgoing)
    original.write_new_json(target / "offline-readback.json", readback)
    original.write_new_json(target / "verification.json", {"source_checkpoint": admitted,
        "historical_seals": seals, "analysis_checks": reports, "sdk_submissions_campaign": sdk_before + len(reports),
        "source_http_attempts_campaign": source_before, "source_http_budget_remaining": 0,
        "fresh_complete_live_investigation_verified": False, "action_ready_findings": 0,
        "finding_quality_gap": "R1 abbreviated quotations and imprecise date text correctly prevent adoption; R3 lacks common-stock listing proof",
        "native_structured_output_prompt_alone_was_insufficient": True,
        "quotations_published_as_hashes": True, "raw_observations_retained_in_private_temporary_directories": True,
        "no_automatic_retry_or_billing_fallback": True, "observed_rate_limit_failure": False,
        "profile_actions": 0, "production_migration": False, "app_restart": False,
        "commit": False, "merge": False, "push": False})
    scan = scan_files({path.name: path for path in target.iterdir()})
    assert scan["unexpected"] == 0
    original.write_new_json(target / "secret-shape-scan.json", scan)
    original.write_new_json(target / "files.sha256.json", {"files": {path.name: sha(path) for path in sorted(target.iterdir())}})
    print(json.dumps({"live_json_analysis_seal_sha256": sha(target / "files.sha256.json"),
        "analysis_protocol_passes": len(reports), "action_ready_findings": 0,
        "sdk_submissions_campaign": sdk_before + len(reports), "source_http_attempts_campaign": source_before,
        "fresh_complete_live_investigation_verified": False}))


if __name__ == "__main__":
    main()
