"""Create-only Linux measurement with an isolated environment and sampled RSS."""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--decoded-mib", type=int, default=128)
    parser.add_argument("--action", choices=("terminal_delisting", "symbol_continuation"), default="terminal_delisting")
    args = parser.parse_args()
    repo, output = args.repo.resolve(), args.output.resolve()
    spec = importlib.util.spec_from_file_location("prior_supervisor", Path(__file__).parents[1] /
        "2026-09-07-lifecycle-source-priority-capacity/run_capacity.py")
    previous = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(previous)
    output.mkdir()
    manifest = previous.inputs(repo)
    (output / "source-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    runner = Path(__file__).with_name("measure_attended.py")
    for script in (runner, Path(__file__)):
        (output / script.name).write_bytes(script.read_bytes())
    command = [sys.executable, str(runner), "--repo", str(repo), "--decoded-mib", str(args.decoded_mib),
               "--action", args.action, "--output", str(output / "measurement.json")]
    started, peak, failure = time.monotonic(), 0, None
    with tempfile.TemporaryDirectory(prefix="attended-supervisor-") as temporary, (output / "worker.log").open("x") as log:
        env = {"PATH": "/usr/bin:/bin", "HOME": temporary, "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
               "ARKSCOPE_DISABLE_SCHEDULER": "1", "ARKSCOPE_PROFILE_DB": temporary + "/profile.db",
               "ARKSCOPE_SA_DB": temporary + "/sa.db", "TMPDIR": temporary}
        process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while process.poll() is None:
                try:
                    resident = int(Path(f"/proc/{process.pid}/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE")
                    peak = max(peak, resident)
                except (FileNotFoundError, IndexError):
                    pass
                if peak > 4 * 1024**3 or time.monotonic() - started > 900:
                    failure = "measured_rss_exceeded" if peak > 4 * 1024**3 else "measurement_timeout"
                    break
                time.sleep(0.025)
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                code = process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                code = process.wait()
    report = {"exit_code": code, "sampled_peak_rss_bytes": peak, "rss_guard_bytes": 4 * 1024**3,
        "failure": failure, "source_unchanged": manifest == previous.inputs(repo),
        "runner_sha256": hashlib.sha256(runner.read_bytes()).hexdigest(),
        "elapsed_seconds": round(time.monotonic() - started, 3)}
    (output / "supervisor.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report), flush=True)
    if code or failure or not report["source_unchanged"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
