"""Freeze a blind code/test patch, without implementation reports or claims."""

import argparse
import hashlib
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]


def main(base, head, output):
    for revision in (base, head):
        subprocess.run(["git", "rev-parse", "--verify", revision], cwd=ROOT,
                       check=True, capture_output=True)
    patch = subprocess.run(
        ["git", "diff", "-U10", base, head, "--", "src", "data_sources", "tests"],
        cwd=ROOT, check=True, capture_output=True,
    ).stdout
    raw = f"# Candidate {base}..{head}\n\n".encode() + patch
    with output.open("xb") as target:
        target.write(raw)
    print(f"{len(raw)} bytes; sha256 {hashlib.sha256(raw).hexdigest()}; {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("base")
    parser.add_argument("head")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    main(args.base, args.head, args.output)
