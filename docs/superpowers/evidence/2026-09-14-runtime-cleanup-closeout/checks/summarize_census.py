"""Attribute scanner changes separately from this batch's source removals."""
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tests.repository_inventory import compare_reports


def read(path):
    return json.loads(gzip.decompress(path.read_bytes()))


def ids(report):
    return {row["id"] for row in report["candidates"]}


def leaves(report):
    return {(row["file"], row["key"]): row for row in report["frontend"]["i18n"]["keys"]}


def candidate_id(row):
    return f'i18n:{row["file"]}:{row["locale"]}:{row["namespace"]}:{row["key"]}'


original = read(ROOT / "docs/superpowers/evidence/2026-09-10-pre-release-cleanup-audit/mechanical-census.json.gz")
accepted = read(ROOT / "docs/superpowers/evidence/2026-09-14-anthropic-child-async/checks/accepted-census/census.json.gz")
baseline = read(WORK / "census-current-scanner-base/census.json.gz")
current = read(WORK / "census-current/census.json.gz")
old_leaves, current_leaves = leaves(original), leaves(current)
original_ids = ids(original)
reviewed = [row for row in leaves(accepted).values()
            if (row["file"], row["key"]) in old_leaves
            and row["status"] == "unresolved" and candidate_id(row) not in original_ids]
assert len(reviewed) == 100
dispositions = [{"id": candidate_id(row), "locale": row["locale"], "key": row["key"],
                 "disposition": "retained_shared_consumer" if (row["file"], row["key"]) in current_leaves else "removed"}
                for row in reviewed]
assert sum(row["disposition"] == "removed" for row in dispositions) == 82
assert sum(row["disposition"] == "retained_shared_consumer" for row in dispositions) == 18
translation = next(row for row in current["sql"]["tables"]
                   if row["table"] == "security_lifecycle_evidence_translations")
assert any(row["path"] == "src/security_lifecycle_investigation.py" for row in translation["reads"])
assert translation["columns_without_observed_read"] == []
assert translation["deletion_authorized"] is False
result = {
    "baseline_source": "a065a0c30a4f75995215cabc0e39dd2579c17c3d",
    "scanner_delta_same_source": compare_reports(accepted, baseline),
    "scanner_removed_candidates": sorted(ids(accepted) - ids(baseline)),
    "cleanup_delta_same_scanner": compare_reports(baseline, current),
    "cleanup_removed_candidates": sorted(ids(baseline) - ids(current)),
    "original_i18n_queue": dispositions,
    "retained_translation_reader": translation,
    "global_cleanup_complete": False,
}
with (WORK / "census-attribution.json").open("x") as stream:
    json.dump(result, stream, indent=2, sort_keys=True)
    stream.write("\n")
for key in ("scanner_delta_same_source", "scanner_removed_candidates", "cleanup_delta_same_scanner"):
    print(key, json.dumps(result[key]))
print("cleanup_removed_candidate_count", len(result["cleanup_removed_candidates"]))
print("original_i18n_queue", "100 = 82 removed + 18 retained")
print("retained_translation_reader", len(translation["read_columns"]), "columns; gaps", translation["columns_without_observed_read"])
