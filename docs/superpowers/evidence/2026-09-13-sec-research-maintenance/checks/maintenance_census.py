"""Source-only census receipts for the continuation, using the unchanged scanner."""

import argparse
import json
from pathlib import Path
import subprocess
import time

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
PYTHON = "/home/hyl/.virtualenvs/llm_app/bin/python"
NODE = "/home/hyl/.nvm/versions/node/v22.14.0/bin"


def run(name, revision, baseline):
    target = WORK / name
    target.mkdir(exist_ok=False)
    (target / "home").mkdir()
    env = {"PATH": NODE + ":/usr/bin:/bin", "HOME": str(target / "home"),
           "PYTHONDONTWRITEBYTECODE": "1", "CI": "1", "TZ": "Asia/Taipei"}
    cmd = [PYTHON, "-B", str(WORK / "run_census.py"), "--root", str(ROOT),
           "--output", str(target / "census.json.gz"),
           "--untracked-root", "/mnt/md0/PycharmProjects/ArkScope"]
    if revision:
        cmd.extend(["--revision", revision])
    if baseline:
        cmd.extend(["--compare", str(WORK / baseline / "census.json.gz")])
    start = time.monotonic()
    with (target / "output.log").open("x") as handle:
        result = subprocess.run(cmd, cwd=ROOT, env=env, stdout=handle, stderr=subprocess.STDOUT)
    record = {"name": name, "command": cmd, "cwd": str(ROOT), "environment": env,
              "exit_code": result.returncode, "seconds": round(time.monotonic() - start, 3)}
    with (target / "command.json").open("x") as handle:
        json.dump(record, handle, indent=2)
        handle.write("\n")
    print(json.dumps(record))
    print((target / "output.log").read_text())
    return result.returncode


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    options = parser.add_mutually_exclusive_group(required=True)
    options.add_argument("--revision")
    options.add_argument("--baseline")
    args = parser.parse_args()
    raise SystemExit(run(args.name, args.revision, args.baseline))
