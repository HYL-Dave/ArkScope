"""Run the two-session SDK gate once, retaining only its closed projection."""

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))


def run(profile, output):
    from tests.live.sdk_driver_smoke import validate_evidence

    with output.open("x", encoding="utf-8") as report:
        command = [sys.executable, str(ROOT / "tests/live/sdk_driver_smoke.py"),
                   "--profile-db", str(profile), "--token-store", "keyring"]
        process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=240)
            evidence = json.loads(stdout if process.returncode == 0 else stderr)
            if not isinstance(evidence, dict):
                raise ValueError("gate_output_invalid")
            if process.returncode == 0:
                validate_evidence(evidence)
            else:
                evidence = {"overall_passed": False, "error": "admission_gate_failed",
                            "sessions_started": evidence.get("sessions_started"),
                            "session_budget": 2}
        except subprocess.TimeoutExpired:
            # Stop the SDK and its CLI children, not only the supervising Python.
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    os.killpg(process.pid, sig)
                except ProcessLookupError:
                    pass
                try:
                    process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    continue
            evidence = {"overall_passed": False, "error": "gate_timeout", "session_budget": 2,
                        "sessions_started": None}
        except (TypeError, ValueError):
            evidence = {"overall_passed": False, "error": "gate_output_invalid", "session_budget": 2,
                        "sessions_started": None}
        json.dump(evidence, report, indent=2)
        print(json.dumps(evidence), flush=True)
    return evidence.get("overall_passed") is True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if run(args.profile, args.output) else 1)
