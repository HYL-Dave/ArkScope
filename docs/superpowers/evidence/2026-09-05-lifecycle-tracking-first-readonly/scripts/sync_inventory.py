"""Explain a pending SA reconciliation without performing reconciliation."""

import argparse
from collections import Counter
from contextlib import ExitStack, closing
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import logging
from pathlib import Path
import sqlite3
import sys


SPEC = importlib.util.spec_from_file_location("tracking_inventory_boundary", Path(__file__).with_name("inventory.py"))
boundary = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(boundary)


def synchronization_details(conn, observations):
    from src.sa_tracking_memberships import _digest
    cursor = conn.execute("SELECT lineage_id,ticker,picked_date,observation_sha256,observed_at FROM sa_tracking_bindings ORDER BY lineage_id")
    names = [column[0] for column in cursor.description]
    bindings = {row[0]: dict(zip(names, row)) for row in cursor}
    counts, targets = Counter(), {}
    for observation in observations:
        binding = bindings.get(observation["lineage_id"])
        if binding is None:
            code = "unbound_lineage"
        elif (binding["ticker"], binding["picked_date"]) != (observation["ticker"], observation["picked_date"]):
            code = "anchor_changed"
        elif binding["observation_sha256"] == _digest(observation):
            code = "unchanged"
        elif binding["observation_sha256"] == _digest({**observation, "observed_at": binding["observed_at"]}):
            code = "timestamp_only"
        else:
            code = "content_changed"
        counts[code] += 1
        if observation["ticker"] in boundary.TARGETS:
            targets.setdefault(observation["ticker"], []).append(code)
    return {
        "observed_lineages": len(observations), "binding_count": len(bindings),
        "change_counts": dict(sorted(counts.items())), "target_changes": targets,
        "bindings_without_current_observation": len(set(bindings) - {row["lineage_id"] for row in observations}),
        "observations_sha256": boundary.digest(observations), "bindings_sha256": boundary.digest(bindings),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--sa", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = {role: getattr(args, role).resolve(strict=True) for role in ("profile", "sa")}
    boundary.require(args.output.is_dir() and args.output.stat().st_mode & 0o077 == 0, "inventory_private_output_required")
    sys.addaudithook(boundary.audit_for(paths))
    logging.disable(logging.CRITICAL)
    at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with boundary.guarded_connections(paths) as guard, ExitStack() as stack:
        connections = {role: stack.enter_context(closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True))) for role, path in paths.items()}
        identities, versions = boundary.file_identities(paths), boundary.data_versions(connections)
        from src.sa_tracking_memberships import read_sa_tracking_observations
        observations = read_sa_tracking_observations(paths["sa"])
        result = synchronization_details(connections["profile"], observations)
        boundary.require_stable(versions, boundary.data_versions(connections))
        boundary.require_stable(identities, boundary.file_identities(paths))
        boundary.require(not guard.denials, "inventory_read_scope_denied")
    result.update({"at": at, "status": "readonly_sync_diagnosis_complete", "production_writes": 0,
                   "provider_requests": 0, "stable_read_interval": True,
                   "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   "boundary_sha256": hashlib.sha256(Path(boundary.__file__).read_bytes()).hexdigest()})
    boundary.private_write(args.output, "sa-sync-summary.json", result)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
