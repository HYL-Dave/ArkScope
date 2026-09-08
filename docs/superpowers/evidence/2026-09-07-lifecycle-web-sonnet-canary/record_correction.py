"""Seal the renewed failed canary and its distinct offline source correction."""

import argparse
import ast
import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import ssl
import sys

from verify_correction import verifier
from scan_packet import SYNTHETIC_TEST_FIXTURES, scan_files


PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[3]
PRIOR = PACKET.parent / "2026-09-07-lifecycle-web-oauth-canary"
RUNTIME = PACKET.parent / "2026-09-07-lifecycle-web-runtime"
sys.path.insert(0, str(PRIOR))
from read_inventory import digest as value_digest, write_new_json

sys.path.insert(0, str(RUNTIME / "scripts"))
spec = importlib.util.spec_from_file_location("source_correction_sealer", RUNTIME / "scripts/seal.py")
sealer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sealer)
sealer.MUTATIONS = verifier.MUTATIONS


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--previous-source", type=Path, required=True)
    parser.add_argument("--live", type=Path, required=True)
    args = parser.parse_args()
    report, measured, nodes = sealer.validate_campaign(args.campaign, "backend")
    history = report["backend_recheck"]
    assert history["same_product_and_tests"] and not history["assertion_or_product_timeout_changes"]
    assert history["runner_timeout_seconds"] == 1200 and history["provider_calls"] == 0
    assert history["prior_timeout_receipt_sha256"] == sha(args.campaign / "backend-timeout.json")
    assert history["prior_report_sha256"] == sha(args.campaign / "report-before-backend-recheck.json")
    previous_report = json.loads((args.campaign / "report-before-backend-recheck.json").read_text())
    assert not previous_report["complete"] and "backend" not in previous_report
    assert previous_report["source_sha256"] == report["source_sha256"]
    assert all(previous_report[key] == report[key] for key in ("baseline", "mutations", "restored", "integration"))
    old_seal = json.loads((PRIOR / "files.sha256.json").read_text())
    assert sha(PRIOR / "files.sha256.json") == "f26fe21ed1e7d908b17c0dc48ca4de6f67751ec1afa5a9f8c7b30d701ca5109e"
    assert all(sha(PRIOR / name) == expected for name, expected in old_seal["files"].items())
    old_source = json.loads((PRIOR / "source-manifest.json").read_text())
    old_code = {name: value for name, value in old_source["files"].items() if not name.startswith("docs/")}
    added = {"tests/test_lifecycle_public_sources_wire.py"}
    assert old_code.keys() | added == report["source_sha256"].keys()
    changed = sorted(name for name in old_code if old_code[name] != report["source_sha256"][name])
    assert changed == ["src/lifecycle_public_sources.py", "tests/test_lifecycle_public_sources.py"]
    assert old_source["deleted_files"] == report["deleted_files"]
    patches = []
    for name in sorted(set(changed) | added):
        before = []
        if name in old_code:
            assert sha(args.previous_source / name) == old_code[name]
            before = (args.previous_source / name).read_text().splitlines(keepends=True)
        patches.extend(difflib.unified_diff(before, (ROOT / name).read_text().splitlines(keepends=True),
            fromfile="before/" + name if before else "/dev/null", tofile="after/" + name))
    ledger = {}
    for kind in ("baseline", "restored", "integration", "backend"):
        _, previous_nodes = sealer.parsers.backend_report(PRIOR / "correction-results" / (kind + ".xml"))
        old, new = set(previous_nodes), set(nodes[kind]["nodes"])
        assert not old - new and len(new - old) == 12
        ledger[kind] = {"before": len(old), "after": len(new), "added": sorted(new - old), "removed": []}

    live_files = {"live-metrics.json": "metrics.json", "live-result.json": "result.json",
                  "live-search-output.json": "search-output.json", "executed-plan.json": "authorized-plan.json"}
    fixture_names = {value[1] for value in SYNTHETIC_TEST_FIXTURES.values()}
    literals = {target.id: ast.literal_eval(node.value) for node in ast.parse((ROOT / "tests/test_probe_harness.py").read_text()).body
                if isinstance(node, ast.Assign) for target in node.targets if isinstance(target, ast.Name) and target.id in fixture_names}
    assert {hashlib.sha256(value.encode()).hexdigest(): key for key, value in literals.items()} == {
        key: value[1] for key, value in SYNTHETIC_TEST_FIXTURES.items()}
    inputs_to_scan = {name: args.live / source for name, source in live_files.items()}
    inputs_to_scan.update({"correction-results/" + path.name: path for path in args.campaign.iterdir()
                          if path.is_file() and path.suffix in {".xml", ".log", ".json"}})
    assert scan_files(inputs_to_scan)["unexpected"] == 0
    data = {name: json.loads((args.live / source).read_text()) for name, source in live_files.items()}
    plan = json.loads((PACKET / "live-plan.json").read_text())
    assert data["executed-plan.json"] == plan
    assert value_digest(plan) == "99a48750675362e0a32332bd0b575ea0fa8c8f6786954ba0adc424c8b74376d5"
    assert plan["harness_sha256"] == sha(PACKET / "claude_canary.py")
    assert plan["offline_source"]["manifest_sha256"] == sha(PRIOR / "source-manifest.json")
    metrics, result = data["live-metrics.json"], data["live-result.json"]
    assert metrics["sdk_query_submissions"] == metrics["journal_model_submissions"] == 1
    assert metrics["token_loads"] == 1 and metrics["token_backend"] == "keyring"
    assert metrics["selected_metadata_unchanged"] and metrics["local_children_reaped"] == [True]
    assert metrics["human_assessments_created"] == metrics["human_adoptions_created"] == 0
    assert metrics["source_http_requests"] == 4
    assert metrics["stages"] == ["searching", "reading_sources"]
    assert metrics["journal_calls"] == {"search-1": {"terminal": "completed"}}
    assert result["status"] == metrics["result_status"] == "failed"
    assert result["failure_code"] == metrics["failure_code"] == "source_read_incomplete"
    assert result["finding"] is None and result["model_submissions"] == 1
    assert result["source_requests"] is None and result["usage"] == {"input_tokens": None, "output_tokens": None}
    assert not (args.live / "analysis-output.json").exists()
    assert len(metrics["sessions"]) == 1
    session = metrics["sessions"][0]
    assert session["model"] == "claude-sonnet-5" and session["fallback_model"] is None
    assert session["helper_model_overrides"] == {"current": "claude-sonnet-5", "legacy": "claude-sonnet-5"}
    assert session["api_key_env_empty"] and session["api_token_env_empty"]
    assert session["tools"] == session["allowed_tools"] == ["WebSearch"]
    assert session["strict_mcp_config"] and session["setting_sources"] == []
    assert session["permission_mode"] == "dontAsk" and session["max_turns"] == 6
    assert session["auto_compact_disabled"] == "1" and session["cli_max_retries"] == "0"
    init = [item for item in session["events"] if item["kind"] == "init"]
    terminals = [item for item in session["events"] if item["kind"] == "result"]
    assert len(init) == len(terminals) == 1
    assert init[0]["api_key_source"] == "none" and init[0]["session_matches_request"]
    assert init[0]["model"] == "claude-sonnet-5" and init[0]["mcp_server_count"] == 0
    assert set(init[0]["tools"]) == {"WebSearch", "StructuredOutput"}
    assistants = [item for item in session["events"] if item["kind"] == "assistant"]
    assert assistants and all(item["model"] == "claude-sonnet-5" for item in assistants)
    assert sum(item["tool_names"].count("WebSearch") for item in assistants) == 2
    terminal = terminals[0]
    assert terminal["session_matches_request"] and terminal["terminal_reason"] == "completed"
    assert terminal["num_turns"] == 4 and not terminal["is_error"] and terminal["has_structured_output"]
    assert terminal["permission_denial_count"] == 0 and terminal["model_usage_models"] == ["claude-sonnet-5"]
    usage = terminal["model_usage"]
    assert usage["shape"] == "object" and len(usage["models"]) == 1
    assert usage["models"][0] == {
        "model": "claude-sonnet-5", "shape": "object", "invalid_fields": [],
        "input_tokens": 29706, "output_tokens": 3228, "cache_creation_input_tokens": 3976,
        "cache_read_input_tokens": 3354, "web_search_requests": 2,
    }
    assert metrics["phase_replies"] == [{"phase": "search", "usage": {"input_tokens": 4, "output_tokens": 1036}}]
    assert [item["code"] for item in metrics["source_reads"]] == [
        "source_body_incomplete", "source_body_incomplete", "source_body_incomplete", "source_unavailable"]
    for index, item in enumerate(metrics["source_reads"]):
        assert item["status"] == "failed" and item["requests_before"] == index and item["requests_after"] == index + 1
        assert item["url"] == data["live-search-output.json"]["sources"][index]

    preparation = {}
    for name, expected in {
        "harness-red": (13, 13), "harness-green": (13, 0), "pre-live-focus": (129, 0),
        "source-wire-red": (12, 8), "source-wire-green": (81, 0), "source-tls-green": (24, 0),
        "post-correction-old-plan-rejection": (29, 1), "packet-green": (30, 0),
    }.items():
        value, _ = sealer.parsers.backend_report(PACKET / (name + ".xml"))
        counts = value["counts"]
        assert (counts["tests"], counts["failures"]) == expected and counts["errors"] == counts["skipped"] == 0
        preparation[name] = value

    docs = ["docs/design/PROJECT_PRIORITY_MAP.md",
        "docs/superpowers/plans/2026-09-05-lifecycle-tracking-first-implementation.md",
        "docs/superpowers/plans/2026-09-06-lifecycle-web-auth-adapters.md"]
    outputs = {
        **{name + "-nodes.json": value for name, value in nodes.items()},
        "node-changes.json": ledger,
        "source-manifest.json": {"base_commit": report["head"], "files": {
            **report["source_sha256"], **{name: sha(ROOT / name) for name in docs}}, "deleted_files": report["deleted_files"]},
        "source-changes.json": {"prior_manifest_sha256": sha(PRIOR / "source-manifest.json"),
            "changed": {name: {"before": old_code[name], "after": report["source_sha256"][name]} for name in changed},
            "added": {name: report["source_sha256"][name] for name in added}, "updated_unsealed_docs": docs},
        "verification.json": {
            "offline_source_correction_complete": True, "source_correction_live_verified": False,
            "sonnet_search_model_auth_session_live_verified": True, "complete_investigation_live_verified": False,
            "live_model_submissions": 1, "live_source_http_requests": 4, "analysis_submissions": 0,
            "human_adoptions": 0, "correction_provider_calls": 0,
            "measured": measured, "mutations": len(report["mutations"]), "preparation": preparation,
            "backend_recheck": history,
            "mutations_scope": "five_independent_mutants_against_whole_affected_focus",
            "source_files_verified": len(report["source_sha256"]), "frontend_bytes_unchanged": True,
            "source_correction_code_files": changed + sorted(added),
            "tls_probe": {"network": "local_socketpair_only", "openssl": ssl.OPENSSL_VERSION,
                          "certificate": "ephemeral_test_only_not_archived", "peer_verification": True},
            "prior_seal_sha256": sha(PRIOR / "files.sha256.json"), "prior_files_verified": len(old_seal["files"]),
            "production_writes": False, "production_migration": False, "app_restart": False,
            "commit": False, "merge": False, "push": False,
            "remaining": ["corrected_source_and_complete_claude_live_gate", "other_channel_live_gates",
                          "multi_turn_usage_and_partial_failure_diagnostics", "authorized_web_journal_installation",
                          "complete_population_cutover", "merge_and_handtest"],
        },
    }
    assert not (PACKET / "files.sha256.json").exists() and not (PACKET / "correction-results").exists()
    assert not (PACKET / "product-correction.patch").exists()
    assert not any((PACKET / name).exists() for name in outputs.keys() | live_files.keys())
    for name, source in live_files.items():
        with (args.live / source).open("rb") as incoming, (PACKET / name).open("xb") as outgoing:
            shutil.copyfileobj(incoming, outgoing)
    for name, value in outputs.items():
        write_new_json(PACKET / name, value)
    with (PACKET / "product-correction.patch").open("x") as stream:
        stream.writelines(patches)
    (PACKET / "correction-results").mkdir()
    for path in sorted(args.campaign.iterdir()):
        if path.is_file() and path.suffix in {".xml", ".log", ".json"}:
            with path.open("rb") as incoming, (PACKET / "correction-results" / path.name).open("xb") as outgoing:
                shutil.copyfileobj(incoming, outgoing)
    scan = scan_files({str(path.relative_to(PACKET)): path for path in PACKET.rglob("*")
                       if path.is_file() and "__pycache__" not in path.parts})
    assert scan["unexpected"] == 0
    write_new_json(PACKET / "secret-shape-scan.json", scan)
    files = {str(path.relative_to(PACKET)): sha(path) for path in sorted(PACKET.rglob("*"))
             if path.is_file() and "__pycache__" not in path.parts and path.name != "files.sha256.json"}
    write_new_json(PACKET / "files.sha256.json", {"algorithm": "sha256", "file_count": len(files), "files": files})
    print(json.dumps({"backend": measured["backend"]["counts"], "mutants": len(report["mutations"]),
        "files": len(files), "seal_sha256": sha(PACKET / "files.sha256.json"), "complete_live_passed": False}))


if __name__ == "__main__":
    main()
