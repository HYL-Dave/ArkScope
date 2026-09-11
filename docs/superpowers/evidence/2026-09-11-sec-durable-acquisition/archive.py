"""Create-only evidence publication from this plan's scratch, never fixture DBs."""
import gzip
import hashlib
import json
from pathlib import Path

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
DEST = ROOT / "docs/superpowers/evidence/2026-09-11-sec-durable-acquisition"


def sha(body):
    return hashlib.sha256(body).hexdigest()


def main():
    assert (WORK / "verification-summary.json").is_file()
    manifest = []
    accepted = {".py", ".md", ".xml", ".log", ".json", ".txt", ".gz"}
    files = sorted(path for path in WORK.iterdir() if path.is_file() and path.suffix in accepted)
    for relative in (
        "review1-tests/rereview/focused-service.xml",
        "review1-tests/rereview/canonical-index.xml",
        "review34-tests/rereview-routes.xml",
        "final-review-tests/integration.xml",
        "final-review-tests/probes.xml",
    ):
        path = WORK / relative
        if path.is_file():
            files.append(path)
    files.extend(sorted(path for path in (WORK / "collateral-review-tests").iterdir()
                        if path.is_file() and path.suffix in accepted))
    for path in files:
        relative = path.relative_to(WORK)
        body = path.read_bytes()
        compressed = path.suffix in {".xml", ".log", ".txt"} or path.name == "source-before.json"
        output = gzip.compress(body, mtime=0) if compressed else body
        target = DEST / (str(relative) + (".gz" if compressed else ""))
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(output)
        restored = gzip.decompress(target.read_bytes()) if compressed else target.read_bytes()
        assert restored == body
        manifest.append({"path": str(target.relative_to(DEST)), "sha256": sha(output),
                         "encoding": "gzip" if compressed else "identity",
                         "bytes": len(output), "original_sha256": sha(body), "original_bytes": len(body)})
    with (DEST / "artifact-manifest.json").open("x") as stream:
        json.dump({"format": 1, "artifacts": manifest}, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"archived": len(manifest), "readback_verified": True}))


if __name__ == "__main__":
    main()
