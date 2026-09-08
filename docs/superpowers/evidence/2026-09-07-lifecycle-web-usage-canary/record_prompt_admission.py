"""Seal one-file prompt amendment before another authorized analysis replay."""

import difflib
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

from verify_prompt import verifier
from claude_canary import write_new_json


PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[3]
PRIOR = PACKET.parent / "2026-09-07-lifecycle-web-usage"
RUNTIME = PACKET.parent / "2026-09-07-lifecycle-web-runtime/scripts"
sys.path.insert(0, str(RUNTIME))
spec = importlib.util.spec_from_file_location("prompt_admission_sealer", RUNTIME / "seal.py")
sealer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sealer)
sealer.MUTATIONS = verifier.MUTATIONS
sys.path.insert(0, str(PACKET.parent / "2026-09-07-lifecycle-web-sonnet-canary"))
from scan_packet import scan_files


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    campaign = Path("/dev/shm/lifecycle-schema-prompt-campaign-r2/results")
    report, measured, nodes = sealer.validate_campaign(campaign, "backend")
    seal = "37747682f666575d7df400f8db53ed54e21d5842bef60fe7caaf2848de7f7e96"
    assert sha(PRIOR / "files.sha256.json") == seal
    prior_seal = json.loads((PRIOR / "files.sha256.json").read_text())
    assert all(sha(PRIOR / name) == value for name, value in prior_seal["files"].items())
    prior_source = json.loads((PRIOR / "source-manifest.json").read_text())
    prior_code = {name: value for name, value in prior_source["files"].items() if not name.startswith("docs/")}
    changed = sorted(name for name in prior_code if prior_code[name] != report["source_sha256"][name])
    assert changed == ["src/auth_drivers/lifecycle_web_claude.py"]
    added = sorted(report["source_sha256"].keys() - prior_code.keys())
    assert added == ["tests/test_lifecycle_web_claude_output_contract.py"]
    assert report["deleted_files"] == prior_source["deleted_files"]
    old = Path("/tmp/lifecycle-structured-output-before") / changed[0]
    assert sha(old) == prior_code[changed[0]]
    red, _ = sealer.parsers.backend_report(PACKET / "prompt-red.xml")
    green, _ = sealer.parsers.backend_report(PACKET / "prompt-green.xml")
    harness, _ = sealer.parsers.backend_report(PACKET / "replay-amendment-final-green.xml")
    assert red["counts"] == {"tests": 4, "failures": 1, "errors": 0, "skipped": 0}
    assert green["counts"] == {"tests": 117, "failures": 0, "errors": 0, "skipped": 0}
    assert harness["counts"] == {"tests": 7, "failures": 0, "errors": 0, "skipped": 0}
    ledger = {}
    for kind in ("baseline", "restored", "integration", "backend"):
        previous = set(json.loads((PRIOR / (kind + "-nodes.json")).read_text())["nodes"])
        current = set(nodes[kind]["nodes"])
        assert not previous - current and len(current - previous) == 4
        ledger[kind] = {"before": len(previous), "after": len(current), "removed": [], "added": sorted(current - previous)}
    docs = {name: value for name, value in prior_source["files"].items() if name.startswith("docs/")}
    assert all(sha(ROOT / name) == value for name, value in docs.items())
    for name in ("diagnose_analysis.py", "test_analysis_diagnostic.py", "verify_prompt.py", "record_prompt_admission.py", "renewed_full_canary.py", "replay-amendment-final-green.xml"):
        path = PACKET / name
        docs[str(path.relative_to(ROOT))] = sha(path)
    target = PACKET / "prompt-admission"
    target.mkdir()
    (target / "results").mkdir()
    for path in campaign.iterdir():
        if path.is_file() and path.suffix in {".xml", ".json", ".log"}:
            with path.open("rb") as incoming, (target / "results" / path.name).open("xb") as outgoing:
                shutil.copyfileobj(incoming, outgoing)
    for kind, value in nodes.items():
        write_new_json(target / (kind + "-nodes.json"), value)
    write_new_json(target / "node-changes.json", ledger)
    write_new_json(target / "source-manifest.json", {"base_commit": report["head"],
        "files": {**report["source_sha256"], **docs}, "deleted_files": report["deleted_files"]})
    write_new_json(target / "verification.json", {"kind": "offline_prompt_amendment_not_live_confirmation",
        "original_capture_files": json.loads((PACKET / "failed-live-r1/diagnostic-metrics.json").read_text())["capture_files_sha256"],
        "prior_source": {"seal_sha256": seal, "manifest_sha256": sha(PRIOR / "source-manifest.json"),
                         "matched_files": len(prior_source["files"])},
        "changed": changed, "added": added, "measured": measured, "owned_mutations": 4,
        "model_submissions": 0, "source_http_requests": 0, "turn_limits_unchanged": True,
        "tool_surface_unchanged": True, "schema_and_validation_unchanged": True,
        "api_and_other_auth_adapters_unchanged": True, "frontend_unchanged": True, "migration": False,
        "interrupted_test_attempt": "prompt-campaign-r1-interrupted.json; same product, RAM-backed rerun; no timeout/expectation change",
        "renewed_full_canary_budget": {"sdk_submissions": 2, "source_http_requests": 4, "cumulative_http_limit": 8},
        "live_replay": "Same R1 public captures, one fresh analysis-only Sonnet subscription request; no search or HTTP; original failure retained."})
    patch = difflib.unified_diff(old.read_text().splitlines(keepends=True), (ROOT / changed[0]).read_text().splitlines(keepends=True),
                                fromfile="before/" + changed[0], tofile="after/" + changed[0])
    with (target / "product-correction.patch").open("x") as stream:
        stream.writelines(patch)
    scan = scan_files({str(path.relative_to(target)): path for path in target.rglob("*") if path.is_file()})
    assert scan["unexpected"] == 0
    write_new_json(target / "secret-shape-scan.json", scan)
    write_new_json(target / "files.sha256.json", {"files": {str(path.relative_to(target)): sha(path)
        for path in sorted(target.rglob("*")) if path.is_file()}})
    print(json.dumps({"prompt_admission_seal_sha256": sha(target / "files.sha256.json"),
                      "measured": {name: value["counts"] for name, value in measured.items()}}))


if __name__ == "__main__":
    main()
