"""Packaged selector implementation; never imports application code."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def _contract(digest):
    manifest = (ROOT / "manifest.json").read_bytes()
    if hashlib.sha256(manifest).hexdigest() != digest:
        raise ValueError("manifest changed")
    source = (ROOT / "contract.py").read_bytes()
    if hashlib.sha256(source).hexdigest() != json.loads(manifest)["files"]["contract.py"]:
        raise ValueError("verifier changed")
    # Do not grant the directory import authority or load timestamp-based .pyc
    # caches. Only these freshly hashed source bytes execute; -I keeps stdlib
    # imports independent of cwd and unexpected adjacent files.
    namespace = {"__name__": "_arkscope_sqlite_contract", "__file__": str(ROOT / "contract.py")}
    exec(compile(source, str(ROOT / "contract.py"), "exec"), namespace)
    return namespace


def main():
    if len(sys.argv) < 2:
        raise ValueError("missing selection")
    digest = sys.argv[1]
    contract = _contract(digest)
    error_type = contract["RuntimeAdmissionError"]
    data = contract["verify_package"](ROOT, digest)
    if any(os.environ.get(name) for name in ("LD_PRELOAD", "LD_AUDIT")):
        raise error_type("sqlite_runtime_loader_conflict")
    env = dict(os.environ)
    env.update(LD_LIBRARY_PATH=str(ROOT / "lib"), ARKSCOPE_SQLITE_PACKAGE=str(ROOT),
               ARKSCOPE_SQLITE_MANIFEST_SHA256=digest)
    python = data["python"]["path"]
    probe = subprocess.run([python, "-I", "-S", "-B", str(ROOT / "contract.py"),
                            "--probe", str(ROOT), digest], env=env,
                           stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
    if probe.returncode:
        raise error_type("sqlite_runtime_probe_failed")
    os.execve(python, [python, *sys.argv[2:]], env)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError, TypeError, SyntaxError, subprocess.SubprocessError) as error:
        message = str(error) if type(error).__name__ == "RuntimeAdmissionError" else "sqlite_runtime_launch_failed"
        print(message, file=sys.stderr)
        raise SystemExit(78)
