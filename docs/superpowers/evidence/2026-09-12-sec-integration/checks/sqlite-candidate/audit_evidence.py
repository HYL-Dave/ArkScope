"""Read back command receipts and assert the standalone-candidate conclusions."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LOGS = ROOT / "logs"
KNOWN_ATTEMPT_FAILURES = {"private-stage": 2, "candidate-upsert": 1, "candidate-identity": 1}


def lines(label):
    return [json.loads(line) for line in (LOGS / f"{label}.stdout").read_text().splitlines()]


def document(label):
    return json.loads((LOGS / f"{label}.stdout").read_text())


steps = []
for path in sorted(LOGS.glob("*.json")):
    record = json.loads(path.read_text())
    assert record["label"] == path.stem
    for stream in ("stdout", "stderr"):
        actual = hashlib.sha256(path.with_suffix("." + stream).read_bytes()).hexdigest()
        assert actual == record[stream + "_sha256"], f"changed receipt: {path.stem} {stream}"
    assert not record["timed_out"], f"timed-out step: {path.stem}"
    assert record["exit_code"] == KNOWN_ATTEMPT_FAILURES.get(path.stem, record["expected_exit"])
    steps.append(record)

baseline = document("baseline-upsert")
candidate = document("candidate-upsert-verified")
assert baseline["classification"] == "defect_reproduced" and baseline["exit_code"] == 1
assert [case["classification"] for case in baseline["cases"]] == ["defect_signature"] * 3 + ["pass"] * 2
assert candidate["classification"] == "all_pass" and candidate["exit_code"] == 0
assert all(case["classification"] == "pass" and case["indexed_count"] == 2
           and case["table_count"] == 2 and case["integrity_check"] == ["ok"] for case in candidate["cases"])
assert all(case["sqlite_version"] == "3.53.4" for case in candidate["cases"])
assert document("archive-verify")["result"] == "pass"
assert document("source-verify")["result"] == "pass"
assert document("source-final-verify")["result"] == "pass"
summaries = {}
for label in ("baseline-synthetic", "candidate-synthetic", "candidate-synthetic-repeat"):
    rows = lines(label)
    cases = [row for row in rows if "test" in row]
    summary = rows[-1]["summary"]
    assert len(cases) == 8 and all(case["result"] == "pass" for case in cases)
    assert summary["passed"] == 8 and summary["failed"] == 0
    assert summary["application_admitted"] is False
    summaries[label] = summary
old_identity = lines("baseline-synthetic")[0]["identity"]
final_identity = lines("baseline-final-identity")[0]["identity"]
new_identity = lines("candidate-synthetic")[0]["identity"]
assert old_identity == final_identity
assert old_identity["sqlite_extension_sha256"] == new_identity["sqlite_extension_sha256"]
assert old_identity["python_version"] == new_identity["python_version"]
assert new_identity["sqlite_source_id"] == document("source-verify")["sqlite3.h"]["source_id"]
assert (LOGS / "repro-blob-final.stdout").read_text().strip() == "cd2a0e50f7c23a9a89e750b8b4780415f7259a64"
assert (LOGS / "scope-process-check.stdout").read_bytes() == b""

fingerprints = {}
paths = [ROOT / name for name in (
    "sqlite-autoconf-3530400.tar.gz", "sqlite-autoconf-3530400/sqlite3.c",
    "prefix/lib/libsqlite3.so.3.53.4", "prefix/bin/sqlite3", "run_step.py",
    "verify_source.py", "synthetic_probe.py", "audit_evidence.py")]
for path in paths:
    data = path.read_bytes()
    fingerprints[str(path.relative_to(ROOT))] = {
        "sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}
print(json.dumps({"result": "pass", "receipt_count": len(steps),
                  "known_corrected_attempt_failures": KNOWN_ATTEMPT_FAILURES,
                  "synthetic_summaries": summaries,
                  "baseline_identity_unchanged": True,
                  "compile_options_removed": sorted(set(old_identity["compile_options"]) - set(new_identity["compile_options"])),
                  "compile_options_added": sorted(set(new_identity["compile_options"]) - set(old_identity["compile_options"])),
                  "fingerprints": fingerprints,
                  "steps": sorted(steps, key=lambda row: row["started_utc"])}, indent=2))
