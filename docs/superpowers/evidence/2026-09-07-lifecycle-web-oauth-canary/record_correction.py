"""Seal the failed canary and its distinct, provider-free correction evidence."""

import argparse
import difflib
import hashlib
import importlib.util
import json
import mmap
from pathlib import Path
import re
import shutil
import sys

from read_inventory import digest as value_digest, write_new_json
from verify_correction import verifier


PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[3]
PRIOR = PACKET.parent / "2026-09-07-lifecycle-web-runtime"
sys.path.insert(0, str(PRIOR / "scripts"))
spec = importlib.util.spec_from_file_location("historical_runtime_sealer", PRIOR / "scripts/seal.py")
sealer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sealer)
sealer.MUTATIONS = verifier.MUTATIONS


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspected_cli():
    package = Path(importlib.util.find_spec("claude_agent_sdk").origin).parent
    binary = package / "_bundled/claude"
    patterns = {
        "helper_selector": b'L("tengu_plum_vx3",!1)?Nm():n.options.mainLoopModel',
        "legacy_override": b"function Nm(){let e=a.ANTHROPIC_SMALL_FAST_MODEL;",
        "current_override": b"function B5(){let e=a.ANTHROPIC_DEFAULT_HAIKU_MODEL;",
        "web_source": b'querySource:"web_search_tool"',
    }
    with binary.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as body:
        digest = hashlib.sha256(body).hexdigest()
        assert digest == "704f1334ac65d3e89e1c6c1d7663293ad786a6166afdb71b5075337df630f976"
        features = {key: {"offset": body.find(value), "matches": body[:].count(value)} for key, value in patterns.items()}
        assert all(item["offset"] >= 0 and item["matches"] == 1 for item in features.values())
        anchor = features["helper_selector"]["offset"]
        hosted_limits = [int(match.group(1)) for match in re.finditer(rb"max_uses:(\d+)", body[anchor - 1600:anchor + 1600])]
        assert hosted_limits == [8]
        return {"scope": "static_read_after_failed_canary_not_corrected_live_behavior",
            "binary_sha256": digest, "size_bytes": len(body), "features": features,
            "nearby_native_tool_max_uses": hosted_limits, "provider_calls": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--previous-source", type=Path, required=True)
    args = parser.parse_args()
    report, measured, nodes = sealer.validate_campaign(args.campaign, "backend")
    prior_manifest = json.loads((PRIOR / "files.sha256.json").read_text())
    assert sha(PRIOR / "files.sha256.json") == "4d464e372600c7253508a1f9f9f0b48579bfa414c2d8338eec82d4ae82760aaa"
    assert all(sha(PRIOR / name) == expected for name, expected in prior_manifest["files"].items())
    old_source = json.loads((PRIOR / "source-manifest.json").read_text())
    old_code = {name: value for name, value in old_source["files"].items() if not name.startswith("docs/")}
    assert old_code.keys() == report["source_sha256"].keys()
    changed = sorted(name for name in old_code if old_code[name] != report["source_sha256"][name])
    assert changed == ["src/auth_drivers/lifecycle_web_claude.py", "tests/test_lifecycle_web_claude.py"]
    patches = []
    for name in changed:
        before = args.previous_source / name
        assert sha(before) == old_code[name]
        patches.extend(difflib.unified_diff(before.read_text().splitlines(keepends=True),
            (ROOT / name).read_text().splitlines(keepends=True), fromfile="before/" + name, tofile="after/" + name))
    assert old_source["deleted_files"] == report["deleted_files"]
    ledger = {}
    for kind in ("baseline", "restored", "integration", "backend"):
        old = set(json.loads((PRIOR / (kind + "-nodes.json")).read_text())["nodes"])
        new = set(nodes[kind]["nodes"])
        assert not old - new and len(new - old) == 9
        ledger[kind] = {"before": len(old), "after": len(new), "added": sorted(new - old), "removed": []}
    before = json.loads((PACKET / "production-inventory-before.json").read_text())
    after = json.loads((PACKET / "production-inventory-after.json").read_text())
    differences = [key for key in sorted(before.keys() | after.keys()) if before.get(key) != after.get(key)]
    assert differences == ["observed_at"]
    plan = json.loads((PACKET / "live-plan-r2.json").read_text())
    assert value_digest(plan) == "a864a9cbb3392d270bc3602dd5dea999ca5446fb047b1f5e224ff0ce89833a0d"
    assert plan["harness_sha256"] == sha(PACKET / "claude_canary.py")
    assert plan["offline_source"]["manifest_sha256"] == sha(PRIOR / "source-manifest.json")
    metrics = json.loads((PACKET / "live-metrics.json").read_text())
    result = json.loads((PACKET / "live-result.json").read_text())
    assert metrics["sdk_query_submissions"] == metrics["journal_model_submissions"] == 1
    assert metrics["token_loads"] == 1 and len(metrics["sessions"]) == 1
    assert metrics["source_http_requests"] == metrics["human_assessments_created"] == metrics["human_adoptions_created"] == 0
    assert result["status"] == metrics["result_status"] == "remote_outcome_unknown"
    assert result["failure_code"] == metrics["failure_code"] == "execution_identity_changed"
    assert result["finding"] is None and not metrics["phase_replies"]
    session = metrics["sessions"][0]
    assert session["fallback_model"] is None and session["api_key_env_empty"] and session["api_token_env_empty"]
    assert session["events"][0]["api_key_source"] == "none"
    assert all(event["model"] == "claude-sonnet-5" for event in session["events"] if event["kind"] in {"init", "assistant"})
    terminal = [event for event in session["events"] if event["kind"] == "result"]
    assert len(terminal) == 1 and terminal[0]["terminal_reason"] == "completed"
    assert set(terminal[0]["model_usage_models"]) == {"claude-sonnet-5", "claude-haiku-4-5-20251001"}

    docs = ["docs/design/PROJECT_PRIORITY_MAP.md",
        "docs/superpowers/plans/2026-09-05-lifecycle-tracking-first-implementation.md",
        "docs/superpowers/plans/2026-09-06-lifecycle-web-auth-adapters.md"]
    outputs = {
        "cli-helper-inspection.json": inspected_cli(),
        "verification.json": {
            "offline_correction_complete": True, "corrected_live_verified": False,
            "measured": measured, "mutations": len(report["mutations"]),
            "mutations_scope": "five_incremental_mutations_against_whole_affected_focus",
            "prior_backend_mutants_not_rerun": 23, "prior_frontend_mutants_not_rerun": 11,
            "source_files_verified": len(report["source_sha256"]), "changed_code_files": changed,
            "frontend_bytes_unchanged": True, "correction_provider_calls": 0,
            "production_writes": False, "production_migration": False, "app_restart": False,
            "commit": False, "merge": False, "push": False,
            "prior_seal_sha256": sha(PRIOR / "files.sha256.json"), "prior_files_verified": len(prior_manifest["files"]),
            "remaining": ["corrected_claude_live_canary", "other_channel_live_gates", "authorized_web_journal_installation",
                          "complete_population_cutover", "merge_and_handtest"],
        },
        "inventory-comparison.json": {"differences": differences, "observed_before": before["observed_at"],
            "observed_after": after["observed_at"], "scope": "authorized_metadata_only_not_full_database_byte_equality",
            "correspondence": after["correspondence"]},
        "node-changes.json": ledger,
        "source-manifest.json": {"base_commit": report["head"], "files": {
            **report["source_sha256"], **{name: sha(ROOT / name) for name in docs}}, "deleted_files": report["deleted_files"]},
        "source-changes.json": {"prior_manifest_sha256": sha(PRIOR / "source-manifest.json"),
            "code": {name: {"before": old_code[name], "after": report["source_sha256"][name]} for name in changed},
            "updated_unsealed_docs": docs},
    }
    assert not (PACKET / "files.sha256.json").exists()
    assert not (PACKET / "correction-results").exists()
    assert not (PACKET / "product-correction.patch").exists()
    assert not any((PACKET / name).exists() for name in outputs)
    for name, value in outputs.items():
        write_new_json(PACKET / name, value)
    with (PACKET / "product-correction.patch").open("x") as stream:
        stream.writelines(patches)
    (PACKET / "correction-results").mkdir()
    for path in sorted(args.campaign.iterdir()):
        if path.is_file() and path.suffix in {".xml", ".log", ".json"}:
            with path.open("rb") as source, (PACKET / "correction-results" / path.name).open("xb") as target:
                shutil.copyfileobj(source, target)
    files = {str(path.relative_to(PACKET)): sha(path) for path in sorted(PACKET.rglob("*"))
             if path.is_file() and "__pycache__" not in path.parts and path.name != "files.sha256.json"}
    write_new_json(PACKET / "files.sha256.json", {"algorithm": "sha256", "file_count": len(files), "files": files})
    print(json.dumps({"backend": measured["backend"]["counts"], "mutants": len(report["mutations"]),
        "files": len(files), "seal_sha256": sha(PACKET / "files.sha256.json"), "live_canary_passed": False}))


if __name__ == "__main__":
    main()
