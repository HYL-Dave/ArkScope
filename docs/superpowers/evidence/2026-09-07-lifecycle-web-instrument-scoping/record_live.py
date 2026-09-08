"""Read-only live receipt verification; never dispatch or adopt a finding."""

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.with_name("2026-09-07-lifecycle-web-usage-canary")))
import claude_canary as original
from record_json_admission import scan_files


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def without_quotations(value):
    if isinstance(value, list):
        return [without_quotations(item) for item in value]
    if isinstance(value, dict):
        result = {key: without_quotations(item) for key, item in value.items() if key != "quote"}
        if "quote" in value:
            quote = value["quote"]
            assert isinstance(quote, str)
            result.update(quote_sha256=hashlib.sha256(quote.encode()).hexdigest(), quote_utf8_bytes=len(quote.encode()))
        return result
    return value


def frontend_readback(value):
    script = """
const fs = require('node:fs'), ts = require('typescript');
const code = ts.transpileModule(fs.readFileSync(process.argv[1], 'utf8'), {
  compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS}
}).outputText;
const exports = {};
new Function('exports', code)(exports);
process.stdout.write(JSON.stringify(exports.parseWebRun(JSON.parse(fs.readFileSync(0, 'utf8')))));
"""
    result = subprocess.run(["node", "-e", script, str(ROOT / "apps/arkscope-web/src/lifecycle/webContract.ts")],
        cwd=ROOT, input=json.dumps(value), capture_output=True, text=True, timeout=20, check=True)
    assert json.loads(result.stdout) == value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--seal", required=True)
    args = parser.parse_args()
    admitted = original.require_sources(ROOT, HERE / "admission", args.seal)
    work = args.work.resolve()
    assert any(work.is_relative_to(base) for base in (Path("/tmp"), Path("/dev/shm")))
    names = ("authorized-plan.json", "metrics.json", "result.json", "search-output.json", "analysis-output.json", "profile.sqlite")
    before = {name: sha(work / name) for name in names}
    metrics = json.loads((work / "metrics.json").read_text())
    result = json.loads((work / "result.json").read_text())
    plan = json.loads((work / "authorized-plan.json").read_text())
    search = json.loads((work / "search-output.json").read_text())
    analysis = json.loads((work / "analysis-output.json").read_text())
    assert plan["offline_source"] == admitted
    assert plan["public_input"]["ticker"] == "TA" and plan["public_input"]["security_class"] == "common stock"
    assert plan["execution"] == {"provider": "anthropic", "auth_mode": "claude_code_oauth", "model": "claude-sonnet-5"}
    assert plan["options"]["max_search_uses"] == 12 and plan["options"]["max_sources"] == 8
    assert plan["options"]["max_source_requests"] == 24 and plan["options"]["model_timeout_seconds"] == 600
    assert metrics["sdk_query_submissions"] == metrics["journal_model_submissions"] == 2
    assert metrics["token_loads"] == 1 and metrics["selected_metadata_unchanged"]
    assert metrics["local_children_reaped"] == [True, True]
    assert metrics["human_assessments_created"] == metrics["human_adoptions_created"] == 0
    assert metrics["result_status"] == result["status"] == "succeeded"
    assert metrics["failure_code"] is None and result["failure_code"] is None
    assert metrics["journal_calls"] == {"search-1": {"terminal": "completed"}, "analysis-1": {"terminal": "completed"}}
    assert metrics["stages"] == ["searching", "reading_sources", "analyzing", "completed"]
    assert 1 <= metrics["source_http_requests"] <= 24
    assert len(metrics["sessions"]) == 2
    phase_observations = []
    for phase, session, max_turns in zip(("search", "analysis"), metrics["sessions"], (14, 2), strict=True):
        assert session["max_turns"] == max_turns and session["fallback_model"] is None
        assert session["helper_model_overrides"] == {"current": "claude-sonnet-5", "legacy": "claude-sonnet-5"}
        assert session["api_key_env_empty"] and session["api_token_env_empty"]
        assert session["strict_mcp_config"] is True and session["setting_sources"] == []
        assert session["cli_max_retries"] == "0"
        init = [event for event in session["events"] if event["kind"] == "init"]
        end = [event for event in session["events"] if event["kind"] == "result"]
        assert len(init) == len(end) == 1
        assert init[0]["api_key_source"] == "none" and init[0]["model"] == "claude-sonnet-5"
        assert init[0]["session_matches_request"] and init[0]["mcp_server_count"] == 0
        allowed = {"WebSearch", "StructuredOutput"} if phase == "search" else set()
        assert set(init[0]["tools"]) == allowed
        observed_tools = [tool for event in session["events"] if event["kind"] == "assistant" for tool in event["tool_names"]]
        assert set(observed_tools) <= allowed
        assert all(event["model"] == "claude-sonnet-5" and not event["error_present"]
                   for event in session["events"] if event["kind"] == "assistant")
        terminal = end[0]
        assert terminal["subtype"] == "success" and terminal["terminal_reason"] == "completed"
        assert terminal["session_matches_request"] and not terminal["is_error"]
        assert terminal["permission_denial_count"] == 0 and 1 <= terminal["num_turns"] <= max_turns + 1
        assert terminal["model_usage_models"] == ["claude-sonnet-5"]
        assert terminal["has_structured_output"] is (phase == "search")
        phase_observations.append({"phase": phase, "literal_api_key_source": init[0]["api_key_source"],
            "init_tools": init[0]["tools"], "observed_tools": observed_tools,
            "reported_turns": terminal["num_turns"], "reported_model_usage": terminal["model_usage"]})
    assert 1 <= phase_observations[0]["observed_tools"].count("WebSearch") <= 12
    from src.lifecycle_web_store import LifecycleWebStore
    from src.lifecycle_web_projection import project_web_run
    path = work / "profile.sqlite"
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as conn:
        conn.execute("PRAGMA query_only=ON")
        row = LifecycleWebStore.read_on_connection(conn, result["run_id"])
        assert project_web_run(row, at=metrics["finished_at"]) == result
        assert row["finding"].finding.model_dump() == analysis
        assert conn.execute("SELECT COUNT(*) FROM security_lifecycle_assessments").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM lifecycle_web_acceptances").fetchone()[0] == 0
    frontend_readback(result)
    assert result["usage_report"]["coverage"] == "complete" and result["usage_report"]["recorded_submissions"] == 2
    assert result["usage_report"]["totals"] == result["usage"]
    observations = [item for page in metrics["source_reads"] for item in page["observations"]]
    assert len(observations) == metrics["source_http_requests"]
    assert [item["request_index"] for item in observations] == list(range(1, len(observations) + 1))
    assert result["source_reads"] == observations
    assert {name: sha(work / name) for name in names} == before
    target = HERE / "live-r1"
    target.mkdir()
    for name, value in (("authorized-plan.json", plan), ("metrics.json", metrics), ("result-projection.json", result),
                        ("search-output.json", search), ("analysis-projection.json", analysis)):
        original.write_new_json(target / name, without_quotations(value))
    verification = {"source_checkpoint": admitted, "harness_sha256": sha(HERE / "canary.py"),
        "receipt_verifier_sha256": sha(Path(__file__)), "raw_files_sha256": before,
        "fresh_end_to_end_live_investigation_verified": True, "action": row["finding"].action,
        "finding_block_reasons": list(row["finding"].block_reasons), "phases": phase_observations,
        "sdk_query_submissions": 2, "source_http_attempts": len(observations),
        "source_http_budget_remaining": 24 - len(observations), "captured_sources": len(row["pages"]),
        "source_gaps": result["source_gaps"], "reopened_result_identical": True,
        "actual_frontend_parser_roundtrip": True, "raw_capture_unchanged": True,
        "human_assessments_or_adoptions": 0, "production_writes": False,
        "quotations_published_as_hashes": True, "observed_model": "claude-sonnet-5",
        "observed_api_key_source": "none", "no_automatic_retry_or_billing_fallback": True,
        "other_channels_live_verified": False, "app_restart_commit_merge_push": False,
        "limitations": ["One public stock case does not verify every event or instrument",
                        "SDK submissions and observed WebSearch uses are not exact hidden provider HTTP counts"]}
    original.write_new_json(target / "verification.json", verification)
    scan = scan_files({str(path.relative_to(target)): path for path in target.rglob("*") if path.is_file()})
    assert scan["unexpected"] == 0
    original.write_new_json(target / "secret-shape-scan.json", scan)
    original.write_new_json(target / "files.sha256.json", {"files": {path.name: sha(path) for path in sorted(target.iterdir())}})
    print(json.dumps({"seal_sha256": sha(target / "files.sha256.json"),
        "protocol": "complete_with_reopened_and_frontend_readback", "action": row["finding"].action,
        "block_reasons": list(row["finding"].block_reasons), "sdk_submissions": 2,
        "source_http_attempts": len(observations), "captured_sources": len(row["pages"])}))


if __name__ == "__main__":
    main()
