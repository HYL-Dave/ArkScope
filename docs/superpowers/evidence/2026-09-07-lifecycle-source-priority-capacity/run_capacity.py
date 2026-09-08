"""Linux-only offline benchmark supervisor; never a product RSS guarantee."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def inputs(repo):
    names = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=repo, text=True).splitlines()
    return {name: hashlib.sha256((repo / name).read_bytes()).hexdigest() for name in sorted(set(names))
            if not name.startswith("docs/") and (repo / name).is_file()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--decoded-mib", type=int, default=128)
    parser.add_argument("--source-timeout", type=float, default=180)
    parser.add_argument("--runtime", action="store_true")
    parser.add_argument("--dense", action="store_true")
    parser.add_argument("--polling", action="store_true")
    parser.add_argument("--sql-trace", action="store_true")
    parser.add_argument("--hold-commit-seconds", type=float, default=0)
    args = parser.parse_args()
    repo, output = args.repo.resolve(), args.output.resolve()
    output.mkdir()
    source = inputs(repo)
    (output / "source-manifest.json").write_text(json.dumps(source, sort_keys=True, indent=2) + "\n")
    if args.polling and not args.runtime:
        parser.error("progress polling requires the runtime benchmark")
    if args.sql_trace and not args.polling:
        parser.error("SQL timing requires the progress workload")
    if args.hold_commit_seconds and (not args.sql_trace or not 0 < args.hold_commit_seconds <= 30):
        parser.error("a synthetic commit hold requires SQL timing and at most 30 seconds")
    runner = Path(__file__).with_name("measure_sql.py" if args.sql_trace else "measure_polling.py" if args.polling else
                                    "measure_runtime.py" if args.runtime else "measure_capacity.py")
    command = [sys.executable, str(runner), "--repo", str(repo), "--decoded-mib", str(args.decoded_mib),
               "--source-timeout", str(args.source_timeout), "--output", str(output / "measurement.json")]
    if args.dense:
        if not args.runtime:
            parser.error("dense context requires the runtime benchmark")
        command.append("--dense")
    if args.hold_commit_seconds:
        command.extend(["--hold-commit-seconds", str(args.hold_commit_seconds)])
    peak, stopped, failure = 0, False, None
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="capacity-supervisor-") as temporary, (output / "worker.log").open("x") as log:
        env = {"PATH": "/usr/bin:/bin", "HOME": temporary, "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
               "ARKSCOPE_DISABLE_SCHEDULER": "1", "ARKSCOPE_PROFILE_DB": temporary + "/profile.db",
               "ARKSCOPE_SA_DB": temporary + "/sa.db", "TMPDIR": temporary}
        process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while process.poll() is None:
                try:
                    pages = int(Path(f"/proc/{process.pid}/statm").read_text().split()[1])
                    peak = max(peak, pages * os.sysconf("SC_PAGE_SIZE"))
                except (FileNotFoundError, IndexError):
                    pass
                if peak > 4 * 1024**3 or time.monotonic() - started > 600:
                    failure = "measured_rss_exceeded" if peak > 4 * 1024**3 else "measurement_timeout"
                    stopped = True
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
    unchanged = inputs(repo) == source
    report = {"exit_code": code, "sampled_peak_rss_bytes": peak, "rss_guard_bytes": 4 * 1024**3,
              "terminated_by_supervisor": stopped, "failure": failure,
              "source_unchanged": unchanged, "benchmark_sha256": hashlib.sha256(runner.read_bytes()).hexdigest(),
              "elapsed_seconds": round(time.monotonic() - started, 3)}
    (output / "supervisor.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps(report), flush=True)
    if code != 0 or stopped or not unchanged:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
