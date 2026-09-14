"""Seal this slice's explicit evidence list, never fixture stores or secrets."""

from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
import zipfile

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
DEST = ROOT / "docs/superpowers/evidence/2026-09-14-private-sqlite-runtime/checks"
RUNS = (
    "contract-red", "contract-green", "contract-green-02", "build-red",
    "launch-green", "startup-red", "startup-green", "startup-green-02",
    "grammar-red", "grammar-green", "runtime-focused", "bootstrap-red",
    "bootstrap-green", "review-red", "review-green", "fifo-red",
    "final-focused", "final-collect", "full-admitted",
)
STEPS = (
    "final-package-build", "final-package-build-02", "final-package-build-03",
    "final-upsert-02", "final-synthetic", "accepted-upsert", "accepted-synthetic",
    "system-after", "final-linkage", "system-extension-capability",
    "selected-extension-capability",
)
HELPERS = (
    "run_checks.py", "offline_pytest.py", "offline_node.cjs",
    "maintenance_freeze.py", "maintenance_validate.py", "run_step.py",
    "synthetic_probe.py", "seal_checks.py",
)


def digest(body):
    return hashlib.sha256(body).hexdigest()


def write(name, body):
    path = DEST / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as target:
        target.write(body)


def encode(data):
    return json.dumps(data, sort_keys=True, indent=2).encode() + b"\n"


def copy(name, *, compress=False):
    path = WORK / name
    assert path.is_file() and not path.is_symlink()
    body = path.read_bytes()
    if compress:
        write(name + ".gz", gzip.compress(body, mtime=0))
        assert gzip.decompress((DEST / (name + ".gz")).read_bytes()) == body
    else:
        write(name, body)


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


def outcomes(path):
    counts = Counter(passed=0, failed=0, errors=0, skipped=0)
    for node in ET.parse(path).findall(".//testcase"):
        counts["failed" if node.find("failure") is not None else
               "errors" if node.find("error") is not None else
               "skipped" if node.find("skipped") is not None else "passed"] += 1
    return dict(counts)


DEST.mkdir(parents=True, exist_ok=True)
summary = {}
for run in RUNS:
    command = json.loads((WORK / run / "command.json").read_text())
    copy(run + "/command.json")
    copy(run + "/output.log", compress=True)
    if (WORK / run / "results.xml").exists():
        copy(run + "/results.xml", compress=True)
        summary[run] = outcomes(WORK / run / "results.xml")
    else:
        summary[run] = {"junit_absent": True}
    summary[run].update(exit_code=command["exit_code"], seconds=command["seconds"])
    if (WORK / run / "runtime.json").exists():
        copy(run + "/runtime.json")
for step in STEPS:
    command = json.loads((WORK / "logs" / (step + ".json")).read_text())
    for stream in ("stdout", "stderr"):
        assert digest((WORK / "logs" / (step + "." + stream)).read_bytes()) == command[stream + "_sha256"]
    for suffix in ("json", "stdout", "stderr"):
        copy("logs/" + step + "." + suffix,
             compress=suffix == "stdout" and step.startswith("final-package-build"))
for name in (*HELPERS, "freeze-before.json", "freeze-after.json", "final-validation.json"):
    copy(name)
copy("package/manifest.json")
copy("package/python")
write("run-summary.json", encode(summary))

manifest_body = (WORK / "package/manifest.json").read_bytes()
manifest = json.loads(manifest_body)
system = json.loads((WORK / "logs/system-after.stdout").read_text())["identity"]
selected = json.loads((WORK / "full-admitted/runtime.json").read_text())
repro = "docs/superpowers/evidence/2026-09-11-sec-structured-source-core/sqlite_upsert_repro.py"
old_repro = git("show", "42b7ce93:" + repro)
assert old_repro == (ROOT / repro).read_bytes()
protected = {}
for path in ("src/tools/code_executor.py", "requirements.txt",
             "extensions/sa_alpha_picks/native_host_launcher.sh"):
    body = (ROOT / path).read_bytes()
    assert body == git("show", "42b7ce93:" + path)
    protected[path] = digest(body)
archive = WORK / "sqlite-src-3530400.zip"
archive_body = archive.read_bytes()
assert hashlib.sha3_256(archive_body).hexdigest() == manifest["source"]["archive_sha3"]
with zipfile.ZipFile(archive) as source:
    archive_members = len(source.infolist())
    decoded_bytes = sum(item.file_size for item in source.infolist())
for name, expected in manifest["files"].items():
    assert digest((WORK / "package" / name).read_bytes()) == expected
assert selected["engine"] == manifest["engine"]
assert selected["selection"]["manifest_sha256"] == digest(manifest_body)
assert digest(Path(manifest["python"]["path"]).read_bytes()) == manifest["python"]["sha256"]
assert digest(Path(manifest["python"]["extension_path"]).read_bytes()) == manifest["python"]["extension_sha256"]
write("artifact-validation.json", encode({
    "source_anchor": git("rev-parse", "292ef27f^{commit}").decode().strip(),
    "package_manifest_sha256": digest(manifest_body),
    "payload_sha256": manifest["files"],
    "source": dict(manifest["source"], archive_bytes=len(archive_body),
                   archive_members=archive_members, decoded_bytes=decoded_bytes),
    "actual_selected_engine": selected,
    "unmanaged_engine": system,
    "compile_options_added": sorted(set(manifest["engine"]["compile_options"]) - set(system["compile_options"])),
    "compile_options_no_longer_reported": sorted(set(system["compile_options"]) - set(manifest["engine"]["compile_options"])),
    "protected_source_sha256": protected,
    "reproducer": {"path": repro, "sha256": digest(old_repro),
                   "git_blob": git("rev-parse", "42b7ce93:" + repro).decode().strip(),
                   "unchanged": True},
    "installed_selectors_read": False, "production_databases_opened": False,
    "runtime_activated": False,
}))
artifacts = [{"path": str(path.relative_to(DEST)), "bytes": path.stat().st_size,
              "sha256": digest(path.read_bytes())}
             for path in sorted(DEST.rglob("*")) if path.is_file()]
assert all(not (DEST / item["path"]).is_symlink() for item in artifacts)
write("manifest.json", encode({"format": 1, "artifacts": artifacts,
    "source_workspace": str(WORK),
    "exclusions": ["fixture databases", "HOME/configuration", "source archives",
                   "compiled libraries", "superseded package directories", "unrelated scratch"]}))
for item in artifacts:
    body = (DEST / item["path"]).read_bytes()
    assert len(body) == item["bytes"] and digest(body) == item["sha256"]
print(json.dumps({"artifacts": len(artifacts), "bytes": sum(x["bytes"] for x in artifacts),
                  "runs": summary, "artifact_validation": "pass"}, indent=2))
