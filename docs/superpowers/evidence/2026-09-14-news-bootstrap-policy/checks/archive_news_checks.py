"""Publish only selected offline news-target evidence, never fixture stores."""

import gzip
import hashlib
import json
from pathlib import Path

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
DEST = ROOT / "docs/superpowers/evidence/2026-09-14-news-bootstrap-policy/checks"
RUNS = (
    "news-bootstrap-red", "news-bootstrap-green", "news-bootstrap-controls",
    "news-collection", "news-backend-full",
)
FILES = (
    "news-source-before.json", "news-source-after.json", "news-validation.json",
    "news-review.md", "news-census.json.gz",
    "run_checks.py", "offline_pytest.py", "offline_node.cjs", "run_census.py",
    "maintenance_freeze.py", "maintenance_validate.py", "archive_news_checks.py",
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
    with destination.open("xb") as target:
        target.write(content)
    assert destination.read_bytes() == content
    manifest.append({
        "path": destination.relative_to(DEST).as_posix(),
        "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
    })


for name in FILES:
    publish(WORK / name, name)
for name in RUNS:
    for leaf in ("command.json", "output.log", "results.xml"):
        source = WORK / name / leaf
        if source.exists():
            publish(source, Path(name) / leaf, compress=leaf in {"output.log", "results.xml"})
with (DEST / "manifest.json").open("x") as target:
    json.dump({"format": 1, "files": manifest}, target, indent=2, sort_keys=True)
    target.write("\n")
print(json.dumps({
    "files": len(manifest), "bytes": sum(row["bytes"] for row in manifest),
    "destination": str(DEST), "readback": "exact",
}))
