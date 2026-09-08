"""Seal corrected total-turn accounting before the renewed full live gate."""

import difflib
import hashlib
import json
from pathlib import Path
import shutil

from claude_canary import write_new_json
from record_prompt_admission import sealer, scan_files
from verify_turns import verifier


PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[3]
PRIOR = PACKET / "prompt-admission"
sealer.MUTATIONS = verifier.MUTATIONS


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    campaign = Path("/dev/shm/lifecycle-turns-campaign-r1/results")
    report, measured, nodes = sealer.validate_campaign(campaign, "backend")
    assert sha(PRIOR / "files.sha256.json") == "2cd4bcf60f5a9fcd4f60d91402a29bcca90e2a15c9d2bd76c1a67a61c4cb1752"
    prior_seal = json.loads((PRIOR / "files.sha256.json").read_text())
    assert all(sha(PRIOR / name) == value for name, value in prior_seal["files"].items())
    prior_source = json.loads((PRIOR / "source-manifest.json").read_text())
    code = {name: value for name, value in prior_source["files"].items() if not name.startswith("docs/")}
    changed = sorted(name for name in code if code[name] != report["source_sha256"][name])
    added = sorted(report["source_sha256"].keys() - code.keys())
    assert changed == ["src/auth_drivers/lifecycle_web_claude.py"]
    assert added == ["tests/test_lifecycle_web_claude_turns.py"] and prior_source["deleted_files"] == report["deleted_files"]
    old = Path("/dev/shm/lifecycle-schema-prompt-campaign-r2/source") / changed[0]
    assert sha(old) == code[changed[0]]
    ledger = {}
    for kind in ("baseline", "restored", "integration", "backend"):
        before = set(json.loads((PRIOR / (kind + "-nodes.json")).read_text())["nodes"])
        after = set(nodes[kind]["nodes"])
        assert not before - after and len(after - before) == 8
        ledger[kind] = {"before": len(before), "after": len(after), "added": sorted(after - before), "removed": []}
    checks = {}
    for name, count, failures in (("turns-red", 8, 2), ("turns-green", 125, 0), ("renewed-native-observer-green", 9, 0)):
        actual, _ = sealer.parsers.backend_report(PACKET / (name + ".xml"))
        assert actual["counts"] == {"tests": count, "failures": failures, "errors": 0, "skipped": 0}
        checks[name] = actual
    docs = {name: value for name, value in prior_source["files"].items() if name.startswith("docs/")}
    changed_docs = {str((PACKET / name).relative_to(ROOT)) for name in ("renewed_full_canary.py", "test_analysis_diagnostic.py")}
    assert {name for name, expected in docs.items() if sha(ROOT / name) != expected} == changed_docs
    for name in changed_docs:
        docs[name] = sha(ROOT / name)
    for name in ("verify_turns.py", "record_turns_admission.py", "renewed-native-observer-green.xml"):
        path = PACKET / name
        docs[str(path.relative_to(ROOT))] = sha(path)
    target = PACKET / "turns-admission"
    target.mkdir()
    (target / "results").mkdir()
    for path in campaign.iterdir():
        if path.is_file() and path.suffix in {".json", ".log", ".xml"}:
            with path.open("rb") as incoming, (target / "results" / path.name).open("xb") as outgoing:
                shutil.copyfileobj(incoming, outgoing)
    for kind, value in nodes.items():
        write_new_json(target / (kind + "-nodes.json"), value)
    previous_verification = json.loads((PRIOR / "verification.json").read_text())
    write_new_json(target / "source-manifest.json", {"base_commit": report["head"],
        "files": {**report["source_sha256"], **docs}, "deleted_files": report["deleted_files"]})
    write_new_json(target / "node-changes.json", ledger)
    write_new_json(target / "verification.json", {"kind": "offline_total_turn_count_correction",
        "prior_source": previous_verification["prior_source"],
        "original_capture_files": previous_verification["original_capture_files"],
        "previous_prompt_admission_seal": sha(PRIOR / "files.sha256.json"),
        "changed": changed, "added": added, "measured": measured, "preparation": checks, "owned_mutations": 7,
        "provider_calls": 0, "frontend_unchanged": True, "schema_and_output_validation_unchanged": True,
        "native_tool_round_trip_budgets_unchanged": True, "completed_total_turn_allowance": 1,
        "api_and_other_auth_adapters_unchanged": True, "migration": False,
        "full_live_gate": {"sdk_submissions": 2, "source_http_requests": 4, "campaign_http_limit": 8,
                           "no_retry": True, "no_fallback": True, "human_adoptions": 0}})
    with (target / "product-correction.patch").open("x") as stream:
        stream.writelines(difflib.unified_diff(old.read_text().splitlines(keepends=True), (ROOT / changed[0]).read_text().splitlines(keepends=True),
            fromfile="before/" + changed[0], tofile="after/" + changed[0]))
    scan = scan_files({str(path.relative_to(target)): path for path in target.rglob("*") if path.is_file()})
    assert scan["unexpected"] == 0
    write_new_json(target / "secret-shape-scan.json", scan)
    write_new_json(target / "files.sha256.json", {"files": {str(path.relative_to(target)): sha(path)
        for path in sorted(target.rglob("*")) if path.is_file()}})
    print(json.dumps({"turns_admission_seal_sha256": sha(target / "files.sha256.json"),
        "measured": {name: value["counts"] for name, value in measured.items()}}))


if __name__ == "__main__":
    main()
