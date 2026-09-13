"""Select release evidence explicitly; never recursively archive fixture stores."""

import argparse
import hashlib
import json
from pathlib import Path

from maintenance_seal import WORK, seal


def select_extras():
    extras = {
        "browser_check.py", "browser_fixture.py", "vite-preview.mjs",
        "browser-fixture/main.tsx", "browser-fixture/index.html",
        "maintenance_seal.py", "maintenance_accounting.py",
        "maintenance_freeze.py", "maintenance_validate.py",
        "maintenance_verify_archive.py", "maintenance_census.py",
        "maintenance_reconcile_census.py",
    }
    for name in ("task7-inverse-recipes.json", "task7-final-inverses.json",
                 "task7-fix1-inverses.json", "task7-fix1-refreshed-inverses.json"):
        for proof in json.loads((WORK / name).read_text()):
            for source in proof["files"]:
                extras.update(source[key] for key in ("original_artifact", "mutant_artifact"))
    fix_proof = json.loads((WORK / "task8-final-fix-inverse-proof.json").read_text())
    for artifact in fix_proof["artifacts"]:
        path = WORK.parents[2] / artifact["path"]
        assert path.is_relative_to(WORK) and path.suffix == ".py"
        assert not path.is_symlink() and path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
        extras.add(path.relative_to(WORK).as_posix())
    browser_proof = json.loads((WORK / "task7-fix1-browser-proof.json").read_text())
    for artifact in browser_proof["artifacts"] + browser_proof["helpers"]:
        path = WORK / artifact["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
        extras.add(artifact["path"])
    for body in browser_proof["bodies"]:
        if "file" not in body:
            continue
        path = Path(body["file"])
        assert path.is_relative_to(WORK) and path.suffix == ".body"
        raw = path.read_bytes()
        assert len(raw) == body["bytes"]
        assert hashlib.sha256(raw).hexdigest() == body["sha256"]
        extras.add(path.relative_to(WORK).as_posix())
    for extra in extras:
        path = Path(extra)
        assert not path.is_absolute() and ".." not in path.parts
        assert (WORK / path).is_file() and not (WORK / path).is_symlink()
    return sorted(extras)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--selection-only", action="store_true")
    args = parser.parse_args()
    extras = select_extras()
    if args.selection_only:
        print(json.dumps({"extras": extras}, indent=2))
    else:
        seal(args.output, prefixes=("task7-", "task8-", "task8_", "task-7-", "task-8-"), extras=extras)
