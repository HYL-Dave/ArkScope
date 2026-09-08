"""Capture tests only through the existing no-egress verification wrapper."""

import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[4]


def main():
    label, *args = sys.argv[1:]
    if not label.replace("-", "").isalnum():
        raise ValueError("invalid_log_label")
    target = Path(__file__).with_name(label + ".txt")
    env = {key: value for key, value in os.environ.items()
           if key in {"HOME", "PATH", "LANG", "LC_ALL", "TMPDIR"}}
    wrapper = ROOT / "docs/superpowers/evidence/2026-09-08-automation-modes-gpt6/offline_check.py"
    with target.open("x", encoding="utf-8") as output:
        result = subprocess.run([sys.executable, str(wrapper), "pytest", *args],
                                cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT)
    print(target.read_text(encoding="utf-8")[-5000:], flush=True)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
