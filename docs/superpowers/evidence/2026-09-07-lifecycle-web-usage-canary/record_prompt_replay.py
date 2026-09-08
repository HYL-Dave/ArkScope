"""Retain the native success rejected by the old host turn-count interpretation."""

import hashlib
import json
from pathlib import Path
import shutil
import sys

from claude_canary import ROOT, require_sources, write_new_json

PACKET = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKET.parent / "2026-09-07-lifecycle-web-sonnet-canary"))
from scan_packet import scan_files


def main():
    source = require_sources(ROOT, PACKET / "prompt-admission", "2cd4bcf60f5a9fcd4f60d91402a29bcca90e2a15c9d2bd76c1a67a61c4cb1752")
    live = Path("/tmp/lifecycle-usage-analysis-prompt-r2")
    metrics = json.loads((live / "metrics.json").read_text())
    assert metrics["source_checkpoint"] == source
    assert metrics["status"] == "failed" and metrics["failure_code"] == "model_result_incomplete"
    assert metrics["sdk_submissions"] == 1 and metrics["source_http_requests"] == 0
    assert metrics["terminal_statuses"] == {"analysis-1": "completed"}
    assert metrics["local_children_reaped"] == [True] and metrics["original_capture_unchanged"]
    attempts = [item for event in metrics["events"] for item in event.get("structured_output_attempts", [])]
    assert [item["schema_valid"] for item in attempts] == [False, True]
    result = next(event for event in metrics["events"] if event["kind"] == "result")
    assert result["subtype"] == "success" and result["terminal_reason"] == "completed"
    assert result["num_turns"] == 3 and result["has_structured_output"] and not result["is_error"]
    assert metrics["options"]["max_turns"] == 2 and metrics["options"]["prompt_schema_matches_output_format"]
    files = {name: live / name for name in ("metrics.json", "prepared.json")}
    files["diagnose_analysis.py"] = PACKET / "diagnose_analysis.py"
    assert hashlib.sha256(files["diagnose_analysis.py"].read_bytes()).hexdigest() == metrics["harness_sha256"]
    assert scan_files(files)["unexpected"] == 0
    target = PACKET / "host-rejected-replay-r2"
    target.mkdir()
    for name, path in files.items():
        with path.open("rb") as incoming, (target / name).open("xb") as outgoing:
            shutil.copyfileobj(incoming, outgoing)
    write_new_json(target / "verification.json", {"native_success": True, "host_acceptance": False,
        "source_schema_prompt_observed": True, "native_tool_round_trip_limit": 2, "reported_total_turns": 3,
        "sdk_submissions": 1, "source_http_requests": 0, "adoptions": 0,
        "cause": "Host compared tool-use round-trip limit with total turns including final completion.",
        "docs": "https://code.claude.com/docs/en/agent-sdk/agent-loop",
        "native_output_not_retained_by_this_old_diagnostic": True})
    write_new_json(target / "files.sha256.json", {"files": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(target.iterdir())}})
    print(json.dumps({"host_rejection_seal_sha256": hashlib.sha256((target / "files.sha256.json").read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
