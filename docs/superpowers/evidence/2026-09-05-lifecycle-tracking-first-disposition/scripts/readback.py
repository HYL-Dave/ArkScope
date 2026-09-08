"""Run with either admitted source tree; read only the three applied receipts."""

import argparse
from contextlib import closing
import hashlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import sqlite3
import sys


def require(value, code):
    if not value:
        raise ValueError(code)


def run(paths, *, plan_sha256):
    import src
    from src.active_universe import build_active_universe_snapshot
    from src.sa_tracking_memberships import SaTrackingMembershipStore, read_sa_tracking_observations
    from src.ticker_identity_transition import TickerIdentityTransitionStore
    from src.tools.security_lifecycle_tools import SecurityLifecycleReadService
    targets = ("ARCH", "LTHM", "TA")
    snapshot = build_active_universe_snapshot(profile_db=paths["profile"], sa_db=paths["sa"])
    require(all(item.available for item in snapshot.source_status.values()), "readback_source_unavailable")
    require(not set(targets).intersection(snapshot.tickers), "readback_target_still_tracked")
    reader = SecurityLifecycleReadService(market_db_path=str(paths["market"]), profile_db_path=str(paths["profile"]),
                                         source_loader=lambda: snapshot.sources_by_ticker)
    rows = []
    with closing(sqlite3.connect(paths["profile"].as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("PRAGMA query_only=ON")
        stored = conn.execute("SELECT source_ticker,transition_id,case_id,status,approval_authority FROM ticker_identity_transitions "
                              "WHERE source_ticker IN (?,?,?) ORDER BY source_ticker", targets).fetchall()
        require([row[0] for row in stored] == list(targets), "readback_receipts_incomplete")
        store = TickerIdentityTransitionStore(conn)
        for ticker, transition_id, case_id, status, authority in stored:
            require(status == "applied" and authority == "attended_user", "readback_status_not_applied")
            case = reader.get_case(case_id)
            require(case["ticker_transition"]["status"] == "applied", "readback_projection_disagrees")
            reverse = store.reverse_readiness(transition_id)
            require(reverse["reversible"] is True, "readback_reverse_not_ready")
            rows.append({"ticker": ticker, "status": status, "approval_authority": authority, "reverse_ready": True,
                         "projected_applied": True})
    source = Path(src.__file__).resolve().parent.parent
    names = ("src/ticker_identity_transition.py", "src/tools/security_lifecycle_tools.py", "src/security_lifecycle_provider_store.py")
    return {"status": "readonly_receipt_readback_passed", "code_root": str(source), "plan_sha256": plan_sha256,
            "source_hashes": {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in names},
            "universe_count": len(snapshot.tickers), "targets": rows, "provider_requests": 0, "production_writes": 0,
            "sa_sync_status": SaTrackingMembershipStore(paths["profile"]).synchronization_status(read_sa_tracking_observations(paths["sa"]))}


def main():
    parser = argparse.ArgumentParser()
    for role in ("profile", "market", "sa"):
        parser.add_argument("--" + role, type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = {role: getattr(args, role).resolve(strict=True) for role in ("profile", "market", "sa")}
    uris = {uri for path in paths.values() for uri in (path.as_uri() + "?mode=ro", f"file:{path}?mode=ro")}
    def audit(event, values):
        if event in {"socket.connect", "socket.getaddrinfo", "subprocess.Popen", "os.system", "os.posix_spawn"}:
            raise ValueError("readback_external_execution_forbidden")
        if event == "sqlite3.connect":
            require(os.fsdecode(values[0]) in uris, "readback_write_forbidden")
        if event == "open" and isinstance(values[0], (str, bytes)):
            name = Path(os.fsdecode(values[0])).name
            require(not name.startswith(".env") and name not in {"auth.json", "credentials.json"}, "readback_auth_forbidden")
    sys.addaudithook(audit)
    logging.disable(logging.CRITICAL)
    spec = importlib.util.spec_from_file_location("receipt_read_boundary", Path(__file__).with_name("disposition.py"))
    boundary = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(boundary)
    with boundary.connections(paths) as denials:
        result = run(paths, plan_sha256=args.plan_sha256)
        require(not denials, "readback_scope_denied")
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(result, stream, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"status": "stopped", "exception_type": type(exc).__name__}))
        raise SystemExit(2) from None
