"""Record one bounded command without inheriting user configuration or secrets."""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parent


def scratch_path(value):
    path = Path(value).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("path outside authorized scratch directory")
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--expect", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--cwd", default=str(ROOT))
    parser.add_argument("--library-path")
    parser.add_argument("--stdin")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", args.label):
        parser.error("invalid log label")
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("missing command")
    for name in ("logs", "home", "tmp"):
        (ROOT / name).mkdir(mode=0o700, exist_ok=True)
    prefix = ROOT / "logs" / args.label
    if prefix.with_suffix(".json").exists():
        parser.error("log label already used; choose a new label")
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": str(ROOT / "home"),
        "TMPDIR": str(ROOT / "tmp"),
        "LC_ALL": "C",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if args.library_path:
        env["LD_LIBRARY_PATH"] = str(scratch_path(args.library_path))
    stdin = scratch_path(args.stdin).read_bytes() if args.stdin else b""
    cwd = scratch_path(args.cwd)
    record = {
        "label": args.label,
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "argv": command,
        "cwd": str(cwd),
        "environment": env,
        "shell_command": shlex.join(["env", "-i"] + [f"{k}={v}" for k, v in env.items()] + command),
        "stdin_path": args.stdin,
        "stdin_sha256": hashlib.sha256(stdin).hexdigest(),
        "expected_exit": args.expect,
        "timeout_seconds": args.timeout,
    }
    started = time.monotonic()
    timed_out = False
    proc = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=True)
    try:
        stdout, stderr = proc.communicate(stdin, timeout=args.timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(proc.pid, signal.SIGKILL)
        stdout, stderr = proc.communicate()
    finally:
        # Kill any descendant that unexpectedly outlived its command.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()
    prefix.with_suffix(".stdout").write_bytes(stdout)
    prefix.with_suffix(".stderr").write_bytes(stderr)
    record.update(exit_code=proc.returncode, timed_out=timed_out,
                  elapsed_seconds=round(time.monotonic() - started, 6),
                  stdout_sha256=hashlib.sha256(stdout).hexdigest(),
                  stderr_sha256=hashlib.sha256(stderr).hexdigest())
    prefix.with_suffix(".json").write_text(json.dumps(record, indent=2) + "\n", encoding="ascii")
    print(json.dumps(record, indent=2), flush=True)
    print("STDOUT:\n" + stdout.decode("utf-8", errors="replace")[-14000:], flush=True)
    if stderr:
        print("STDERR:\n" + stderr.decode("utf-8", errors="replace")[-6000:], flush=True)
    return 0 if proc.returncode == args.expect and not timed_out else 1


if __name__ == "__main__":
    sys.exit(main())
