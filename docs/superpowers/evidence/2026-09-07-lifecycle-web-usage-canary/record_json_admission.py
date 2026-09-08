"""Seal the explicit final-JSON transport and its zero-HTTP replay authority."""

import asyncio
import difflib
import hashlib
import json
from pathlib import Path
import shutil

from claude_canary import write_new_json
from diagnose_analysis import capture_analysis, snapshot
from record_prompt_admission import sealer, scan_files
from verify_json_analysis import verifier


PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[3]
PRIOR = PACKET / "turns-admission"
sealer.MUTATIONS = verifier.MUTATIONS


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_packet(path, expected):
    assert sha(path / "files.sha256.json") == expected
    seal = json.loads((path / "files.sha256.json").read_text())
    assert all(sha(path / name) == value for name, value in seal["files"].items())


def main():
    from src.lifecycle_web_store import LifecycleWebStore

    campaign = Path("/dev/shm/lifecycle-json-analysis-campaign-r1/results")
    report, measured, nodes = sealer.validate_campaign(campaign, "backend")
    checked_packet(PRIOR, "3bd019ea5014e06a0249173e208ac5f7900ee9c063081c9e017b77afc1e438d4")
    checked_packet(PACKET / "failed-renewed-r3", "79711c3a3a147242f748b58cc765ab7cf5d3a0dca2335296f4100b02648c2422")
    prior_source = json.loads((PRIOR / "source-manifest.json").read_text())
    prior_verification = json.loads((PRIOR / "verification.json").read_text())
    renewed = json.loads((PACKET / "failed-renewed-r3/verification.json").read_text())
    code = {name: value for name, value in prior_source["files"].items() if not name.startswith("docs/")}
    changed = sorted(name for name in code if code[name] != report["source_sha256"][name])
    added = sorted(report["source_sha256"].keys() - code.keys())
    assert changed == ["src/auth_drivers/lifecycle_web_claude.py", "tests/test_lifecycle_web_claude.py",
                       "tests/test_lifecycle_web_claude_output_contract.py", "tests/test_lifecycle_web_claude_wire.py"]
    assert added == ["tests/test_lifecycle_web_claude_json_analysis.py"]
    assert prior_source["deleted_files"] == report["deleted_files"]
    for name in changed:
        assert sha(Path("/dev/shm/lifecycle-turns-campaign-r1/source") / name) == code[name]
    ledger = {}
    for kind in ("baseline", "restored", "integration", "backend"):
        before = set(json.loads((PRIOR / (kind + "-nodes.json")).read_text())["nodes"])
        after = set(nodes[kind]["nodes"])
        assert not before - after and len(after - before) == 29
        ledger[kind] = {"before": len(before), "after": len(after), "added": sorted(after - before), "removed": []}
    preparation = {}
    for name, count, failures in (("json-analysis-red", 28, 6), ("json-analysis-integration-first", 133, 1),
                                 ("json-analysis-green", 134, 0), ("json-analysis-harness-final", 16, 0)):
        result, _ = sealer.parsers.backend_report(PACKET / (name + ".xml"))
        assert result["counts"] == {"tests": count, "failures": failures, "errors": 0, "skipped": 0}
        preparation[name] = result
    docs = {name: value for name, value in prior_source["files"].items() if name.startswith("docs/")}
    changed_docs = {str((PACKET / name).relative_to(ROOT)) for name in ("diagnose_analysis.py", "test_analysis_diagnostic.py")}
    assert {name for name, expected in docs.items() if sha(ROOT / name) != expected} == changed_docs
    for name in changed_docs:
        docs[name] = sha(ROOT / name)
    for name in ("verify_json_analysis.py", "record_json_admission.py", "record_renewed_failure.py",
                 "claude-analysis-json-amendment.md", "json-analysis-harness-final.xml"):
        path = PACKET / name
        docs[str(path.relative_to(ROOT))] = sha(path)
    captures = []
    for label, directory, files, checkpoint in (
        ("R3", Path("/tmp/lifecycle-renewed-full-r3"), renewed["capture_files_sha256"], renewed["offline_source"]),
        ("R1", Path("/tmp/lifecycle-usage-live-r1"), prior_verification["original_capture_files"], prior_verification["prior_source"]),
    ):
        assert snapshot(directory) == files
        result = json.loads((directory / "result.json").read_text())
        metrics = json.loads((directory / "metrics.json").read_text())
        row = LifecycleWebStore(directory / "profile.sqlite").read(result["run_id"])
        call = asyncio.run(capture_analysis(row, json.loads((directory / "search-output.json").read_text()), metrics["source_reads"]))
        assert call.phase == "analysis" and call.selection.model == "claude-sonnet-5"
        assert snapshot(directory) == files
        captures.append({"label": label, "files": files, "source_checkpoint": checkpoint,
                         "prompt_sha256": hashlib.sha256(call.prompt.encode()).hexdigest(),
                         "schema_sha256": hashlib.sha256(json.dumps(call.output_schema, sort_keys=True, separators=(",", ":")).encode()).hexdigest()})
    target = PACKET / "json-analysis-admission"
    target.mkdir()
    (target / "results").mkdir()
    for path in campaign.iterdir():
        if path.is_file() and path.suffix in {".json", ".log", ".xml"}:
            with path.open("rb") as incoming, (target / "results" / path.name).open("xb") as outgoing:
                shutil.copyfileobj(incoming, outgoing)
    for kind, value in nodes.items():
        write_new_json(target / (kind + "-nodes.json"), value)
    write_new_json(target / "source-manifest.json", {"base_commit": report["head"],
        "files": {**report["source_sha256"], **docs}, "deleted_files": report["deleted_files"]})
    write_new_json(target / "node-changes.json", ledger)
    write_new_json(target / "verification.json", {"kind": "offline_explicit_final_json_analysis_transport",
        "previous_turns_admission_seal": sha(PRIOR / "files.sha256.json"), "changed": changed, "added": added,
        "measured": measured, "preparation": preparation, "owned_mutations": 15,
        "analysis_capture_receipts": captures, "source_http_attempts_remaining": 0,
        "provider_calls": 0, "frontend_unchanged": True, "schema_and_finding_validation_unchanged": True,
        "other_auth_adapters_unchanged": True, "search_transport_unchanged": True,
        "analysis_native_output_tool_removed": True, "analysis_json_strictly_validated_by_shared_parser": True,
        "native_tool_round_trip_budgets_unchanged": True, "migration": False,
        "analysis_replay_authority": {"max_submissions_each": 1, "source_http_attempts": 0,
            "selected_subscription_only": True, "no_retry": True, "no_fallback": True, "human_adoptions": 0},
        "replay_is_not_a_new_full_retrieval_canary": True})
    with (target / "correction.patch").open("x") as stream:
        for name in changed:
            old = Path("/dev/shm/lifecycle-turns-campaign-r1/source") / name
            stream.writelines(difflib.unified_diff(old.read_text().splitlines(keepends=True), (ROOT / name).read_text().splitlines(keepends=True),
                fromfile="before/" + name, tofile="after/" + name))
    scan = scan_files({str(path.relative_to(target)): path for path in target.rglob("*") if path.is_file()})
    assert scan["unexpected"] == 0
    write_new_json(target / "secret-shape-scan.json", scan)
    write_new_json(target / "files.sha256.json", {"files": {str(path.relative_to(target)): sha(path)
        for path in sorted(target.rglob("*")) if path.is_file()}})
    print(json.dumps({"json_analysis_admission_seal_sha256": sha(target / "files.sha256.json"),
        "measured": {name: value["counts"] for name, value in measured.items()},
        "replay_source_sets": [row["label"] for row in captures], "provider_calls": 0}))


if __name__ == "__main__":
    main()
