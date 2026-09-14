"""Create-only publication of selected offline evidence, never fixture stores."""
import gzip
import hashlib
import json
from pathlib import Path

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
DEST = ROOT / "docs/superpowers/evidence/2026-09-14-runtime-cleanup-closeout/checks"
RUNS = (
    "c15-red", "c15-green", "i18n-red", "i18n-green", "i18n-green-final",
    "sql-red", "sql-green", "sql-green-scoped", "sql-shadow-red", "sql-green-final",
    "sql-review-red", "sql-review-green", "frontend-full", "frontend-typecheck",
    "frontend-build", "frontend-literals", "census-current-scanner-base", "census-current",
    "collection", "backend-full",
)
FILES = (
    "source-before.json", "source-after.json", "validation.json", "census-attribution.json",
    "sql-review.md", "c12-inventory.md", "c15-inventory.md",
    "run_checks.py", "offline_pytest.py", "offline_node.cjs", "run_census.py",
    "summarize_census.py", "maintenance_freeze.py", "maintenance_validate.py", "archive_checks.py",
)
manifest = []
DEST.mkdir(parents=True, exist_ok=False)


def publish(source, relative, *, compress=False):
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"unexpected evidence source: {source.name}")
    raw = source.read_bytes()
    content = gzip.compress(raw, mtime=0) if compress else raw
    destination = DEST / (str(relative) + (".gz" if compress else ""))
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as output:
        output.write(content)
    assert destination.read_bytes() == content
    manifest.append({"path": destination.relative_to(DEST).as_posix(), "bytes": len(content),
                     "sha256": hashlib.sha256(content).hexdigest(),
                     "source_sha256": hashlib.sha256(raw).hexdigest()})


for name in FILES:
    publish(WORK / name, name)
for name in RUNS:
    for leaf in ("command.json", "output.log", "results.xml", "census.json.gz"):
        source = WORK / name / leaf
        if source.exists():
            publish(source, Path(name) / leaf, compress=leaf in {"output.log", "results.xml"})
with (DEST / "manifest.json").open("x") as output:
    json.dump({"format": 1, "files": manifest}, output, indent=2, sort_keys=True)
    output.write("\n")
print(json.dumps({"files": len(manifest), "bytes": sum(row["bytes"] for row in manifest),
                  "destination": str(DEST), "readback": "exact"}))
