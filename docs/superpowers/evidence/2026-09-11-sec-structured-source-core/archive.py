"""Create-only archival of this batch's generated verification artifacts."""

import gzip
import hashlib
import json
from pathlib import Path
import shutil


WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
DEST = ROOT / "docs/superpowers/evidence/2026-09-11-sec-structured-source-core"
COMPRESSED = (
    "baseline-nodes.txt", "final-nodes.txt", "backend-full.xml",
    "backend-full.log", "source-before.json", "census.json.gz", "census-final.json.gz",
)
PLAIN = (
    "verification-summary.json", "census.log", "census-final.log", "progress.md",
    "offline_pytest.py", "verification.py", "archive.py",
    "task-1-report.md", "task12-review.md", "task-3-report.md",
    "task-3-mutations.log", "task-3-followup.log", "task-4-report.md",
    "parsers-final-review.md", "test_parsers_final_diagnostics.py",
    "task2-ast.json", "sqlite-repeat.json", "sqlite-diagnostics.log",
)
PAIRS = [(name, name + ("" if name.endswith(".gz") else ".gz")) for name in COMPRESSED]
PAIRS += [(name, name) for name in PLAIN]
for name in (
    "task2-red", "task2-green", "task2-inverse", "task2-restored",
    "task4-red", "task4-owner-red", "task4-green", "task4-float-inverse",
    "task4-overwrite-inverse", "task4-restored", "parsers-combined", "precommit-parsers",
):
    PAIRS += [(name + suffix, name + suffix) for suffix in (".xml", ".log")]
PAIRS += [
    ("parsers-final-review-20260911T0405/focused.xml", "review-focused.xml"),
    ("parsers-final-synthetic-20260911T0401/diagnostics.xml", "review-diagnostics.xml"),
]


if __name__ == "__main__":
    assert (WORK / "verification-summary.json").is_file(), "full verification required"
    manifest = {}
    for original, archived in PAIRS:
        src = WORK / original
        dst = DEST / archived
        assert src.is_file(), original
        assert not dst.exists(), f"create-only archive already exists: {archived}"
    for original, archived in PAIRS:
        src = WORK / original
        dst = DEST / archived
        compress = archived.endswith(".gz") and not original.endswith(".gz")
        with src.open("rb") as stream, dst.open("xb") as output:
            if compress:
                with gzip.GzipFile(filename="", fileobj=output, mode="wb", mtime=0) as packed:
                    shutil.copyfileobj(stream, packed)
            else:
                shutil.copyfileobj(stream, output)
        content = dst.read_bytes()
        restored = gzip.decompress(content) if compress else content
        assert restored == src.read_bytes(), f"archive readback mismatch: {archived}"
        manifest[archived] = {
            "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content),
            "original_sha256": hashlib.sha256(restored).hexdigest(),
        }
    for name in ("sqlite_upsert_repro.py", "sqlite-upsert-result.json", "review-followups.md"):
        content = (DEST / name).read_bytes()
        manifest[name] = {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
    with (DEST / "artifact-manifest.json").open("x", encoding="utf-8") as output:
        json.dump(manifest, output, indent=2, sort_keys=True)
        output.write("\n")
    print(json.dumps({"artifacts": len(manifest), "readback_verified": True}))
