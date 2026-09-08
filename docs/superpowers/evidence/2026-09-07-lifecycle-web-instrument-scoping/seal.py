"""Create-only current-source admission; no credentials or provider dispatch."""

import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PREVIOUS = HERE.with_name("2026-09-07-lifecycle-web-usage-canary")
spec = importlib.util.spec_from_file_location("instrument_verification_config", HERE / "verify.py")
configuration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(configuration)
sys.path.insert(0, str(PREVIOUS))
from record_json_admission import checked_packet, scan_files, sealer
from claude_canary import write_new_json

sealer.MUTATIONS = configuration.verifier.MUTATIONS


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    campaign = Path("/dev/shm/lifecycle-instrument-campaign-r1/results")
    report, measured, nodes = sealer.validate_campaign(campaign, "backend")
    prior = PREVIOUS / "json-analysis-admission"
    checked_packet(prior, "9c4f48ddc0f4bad452a93b610a610942336390f1ea761fca14bcf12e62e4ba60")
    checked_packet(PREVIOUS / "live-json-analysis", "c44fa6670430620747f3a5d85bcffc5220555b49afd0a068052e635a3dd5510b")
    closing = PREVIOUS / "closing-verification.json"
    assert sha(closing) == "70e94999e247e5b81063f4d8bef6b655798cea9340d4e00ddf5e8cfc340ea7b1"
    prior_source = json.loads((prior / "source-manifest.json").read_text())
    old_code = {name: value for name, value in prior_source["files"].items() if not name.startswith("docs/")}
    changed = sorted(name for name, value in old_code.items() if report["source_sha256"][name] != value)
    added = sorted(report["source_sha256"].keys() - old_code.keys())
    assert changed == ["src/lifecycle_web_preflight.py", "src/security_lifecycle_web_contract.py",
                       "src/security_lifecycle_web_finding.py", "src/security_lifecycle_web_pipeline.py"]
    assert added == ["tests/test_lifecycle_web_instrument_scope.py", "tests/test_lifecycle_web_investigation_budget.py"]
    assert report["deleted_files"] == prior_source["deleted_files"]
    ledger = {}
    for name, value in nodes.items():
        before = set(json.loads((prior / (name + "-nodes.json")).read_text())["nodes"])
        after = set(value["nodes"])
        assert not before - after and len(after - before) == 30
        ledger[name] = {"before": len(before), "after": len(after), "added": sorted(after - before), "removed": []}
    preparation = {}
    for name, count, failed in (("red", 30, 17), ("green-first", 177, 0), ("harness-green", 8, 0),
                               ("harness-final-green", 9, 0), ("harness-readback-green", 10, 0),
                               ("recording-green", 2, 0)):
        value, _ = sealer.parsers.backend_report(HERE / (name + ".xml"))
        assert value["counts"] == {"tests": count, "failures": failed, "errors": 0, "skipped": 0}
        preparation[name] = value
    docs = {name: value for name, value in prior_source["files"].items() if name.startswith("docs/")}
    prior_closeout = json.loads(closing.read_text())
    docs.update(prior_closeout["post_live_changed_manifest_files"])
    docs.update(prior_closeout["additional_status_documents_sha256"])
    assert all(sha(ROOT / name) == value for name, value in docs.items())
    for path in [*(HERE / name for name in ("verify.py", "seal.py", "canary.py", "test_canary.py", "record_live.py", "test_record_live.py")),
                 ROOT / "docs/superpowers/plans/2026-09-07-lifecycle-web-instrument-scoping.md",
                 HERE.with_name("2026-09-07-lifecycle-web-oauth-canary") / "read_inventory.py"]:
        docs[str(path.relative_to(ROOT))] = sha(path)
    target = HERE / "admission"
    target.mkdir()
    (target / "results").mkdir()
    for path in campaign.iterdir():
        if path.is_file() and path.suffix in {".json", ".xml", ".log"}:
            with path.open("rb") as incoming, (target / "results" / path.name).open("xb") as outgoing:
                shutil.copyfileobj(incoming, outgoing)
    for name, value in nodes.items():
        write_new_json(target / (name + "-nodes.json"), value)
    for name in changed + added:
        path = target / "source" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with (ROOT / name).open("rb") as incoming, path.open("xb") as outgoing:
            shutil.copyfileobj(incoming, outgoing)
    with (target / "correction.patch").open("x") as output:
        for name in changed:
            old = Path("/dev/shm/lifecycle-json-analysis-campaign-r1/source") / name
            assert sha(old) == old_code[name]
            output.writelines(difflib.unified_diff(old.read_text().splitlines(keepends=True),
                (ROOT / name).read_text().splitlines(keepends=True), fromfile="before/" + name, tofile="after/" + name))
    write_new_json(target / "source-manifest.json", {"base_commit": report["head"],
        "files": {**report["source_sha256"], **docs}, "deleted_files": report["deleted_files"]})
    write_new_json(target / "node-changes.json", ledger)
    write_new_json(target / "verification.json", {
        "kind": "instrument_scoped_attended_finding_and_bounded_claude_oauth_exploration",
        "prior_code_seal": sha(prior / "files.sha256.json"), "prior_closeout_sha256": sha(closing),
        "changed": changed, "added": added, "measured": measured, "preparation": preparation,
        "owned_mutations": len(report["mutations"]), "provider_calls": 0,
        "database_schemas_unchanged": True, "persisted_finding_fields_unchanged": True,
        "other_auth_execution_budgets_unchanged": True, "shared_finding_validation_changed": True,
        "shared_prompt_guidance_changed": True, "frontend_unchanged": True,
        "independent_search_analysis_calls": 2, "no_automatic_retry_or_fallback": True,
        "claude_oauth_envelope": {"max_search_uses": 12, "max_sources": 8, "max_source_requests": 24,
            "max_redirects_per_source": 2, "model_timeout_seconds": 600, "source_timeout_seconds": 180},
        "source_hashes_checked_before_live_authority": True,
        "known_limit": "Lexical citation bindings improve inspectability; neither claim labels nor exact quotes prove publisher truth or event semantics",
        "production_migration": False, "profile_actions": 0, "commit_merge_push_restart": False,
    })
    scan = scan_files({str(path.relative_to(target)): path for path in target.rglob("*") if path.is_file()})
    assert scan["unexpected"] == 0
    write_new_json(target / "secret-shape-scan.json", scan)
    write_new_json(target / "files.sha256.json", {"files": {str(path.relative_to(target)): sha(path)
        for path in sorted(target.rglob("*")) if path.is_file()}})
    print(json.dumps({"admission_seal_sha256": sha(target / "files.sha256.json"),
        "measured": {name: value["counts"] for name, value in measured.items()},
        "owned_mutations": len(report["mutations"]), "provider_calls": 0}))


if __name__ == "__main__":
    main()
