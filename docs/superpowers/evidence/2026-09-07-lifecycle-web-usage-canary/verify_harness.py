"""Run the entire nine-case canary rehearsal and mutations without providers."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[3]
RELATIVE = PACKET.relative_to(ROOT)
MUTATIONS = (
    ("usage_callback_dropped", "test_canary_real_controller_keeps_usage_hook_and_exact_budget_without_live_calls",
     "            journal_reply(call, result)\n", "            pass\n"),
    ("metadata_before_source_admission", "test_canary_source_admission_precedes_any_credential_metadata_read",
     "    admitted_source = source_identity()\n    runtime = require_reviewed_claude_agent_runtime()\n    metadata = selected_metadata(profile)",
     "    runtime = require_reviewed_claude_agent_runtime()\n    metadata = selected_metadata(profile)\n    admitted_source = source_identity()"),
    ("source_observation_field_drift", "test_canary_real_controller_keeps_usage_hook_and_exact_budget_without_live_calls",
     "item.request_index > started", "item.request_number > started"),
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(root, output, name):
    xml = output / (name + ".xml")
    command = [sys.executable, "-m", "pytest", "-q", str(root / RELATIVE / "test_usage_canary.py"),
               "--rootdir", str(ROOT), "--junitxml=" + str(xml)]
    env = {key: value for key, value in os.environ.items() if key in {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR"}}
    env["PYTHONPATH"] = str(ROOT)
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=90)
    with (output / (name + ".log")).open("x") as stream:
        stream.write(result.stdout + result.stderr)
    cases = ET.parse(xml).findall(".//testcase")
    nodes = sorted(item.attrib["name"] for item in cases)
    failures = sorted(item.attrib["name"] for item in cases if item.find("failure") is not None)
    assert len(nodes) == len(set(nodes)) == 9
    assert not any(item.find("error") is not None or item.find("skipped") is not None for item in cases)
    return {"exit_code": result.returncode, "nodes": nodes, "failed_nodes": failures}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    copies = [RELATIVE / name for name in ("claude_canary.py", "test_usage_canary.py")]
    copies += [RELATIVE.parent / "2026-09-07-lifecycle-web-sonnet-canary/test_sonnet_canary.py",
               RELATIVE.parent / "2026-09-07-lifecycle-web-oauth-canary/test_live_harness.py",
               RELATIVE.parent / "2026-09-07-lifecycle-web-oauth-canary/read_inventory.py"]
    sources = {str(path): sha(ROOT / path) for path in copies + [RELATIVE / "verify_harness.py"]}
    report = {"complete": False, "source_sha256": sources, "provider_calls": 0, "production_reads": False,
              "production_writes": False, "mutations": []}
    try:
        with tempfile.TemporaryDirectory(prefix="lifecycle-usage-canary-") as temporary:
            root = Path(temporary)
            for path in copies:
                (root / path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / path, root / path)
            harness = root / RELATIVE / "claude_canary.py"
            original = harness.read_text()
            baseline = report["baseline"] = run(root, args.output, "baseline")
            assert baseline["exit_code"] == 0 and not baseline["failed_nodes"]
            for name, owner, before, after in MUTATIONS:
                assert original.count(before) == 1
                harness.write_text(original.replace(before, after))
                try:
                    result = run(root, args.output, name)
                finally:
                    harness.write_text(original)
                    shutil.rmtree(harness.parent / "__pycache__", ignore_errors=True)
                assert result["exit_code"] == 1 and result["nodes"] == baseline["nodes"]
                assert any(owner in node for node in result["failed_nodes"])
                report["mutations"].append({"name": name, "owner": owner, **result})
            report["restored"] = run(root, args.output, "restored")
            assert report["restored"] == baseline
            assert sha(harness) == sources[str(RELATIVE / "claude_canary.py")]
            assert all(sha(ROOT / path) == expected for path, expected in sources.items())
            report["complete"] = True
    finally:
        with (args.output / "report.json").open("x") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
    print(json.dumps({"passed": len(baseline["nodes"]), "mutations": len(report["mutations"]), "provider_calls": 0}), flush=True)


if __name__ == "__main__":
    main()
