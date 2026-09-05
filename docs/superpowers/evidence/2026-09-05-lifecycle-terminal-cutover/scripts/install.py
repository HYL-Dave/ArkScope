"""User-authorized V4 installation; no provider access or terminal disposition."""

from collections import Counter
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import sqlite3
import sys

ROOT = Path("/mnt/md0/PycharmProjects/ArkScope")
PROFILE = ROOT / "data/profile_state.db"
SA = ROOT / "data/sa_capture.db"
TARGETS = ("ARCH", "LTHM", "TA")
APP_PIDS = (3926831, 3926850, 3926892, 3926956)


def require(ok, code):
    if not ok:
        raise ValueError(code)


def audit(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "subprocess.Popen", "os.system"}:
        raise RuntimeError("cutover_network_or_subprocess_forbidden")
    if event == "open" and isinstance(args[0], (str, bytes)):
        path = Path(os.fsdecode(args[0]))
        if path.name.startswith(".env") or path.name == "auth.json":
            raise RuntimeError("cutover_ambient_credential_file_forbidden")


sys.addaudithook(audit)

from src.active_universe import build_active_universe_snapshot
from src.sa_tracking_memberships import SaTrackingMembershipStore, read_sa_tracking_observations
from src.security_lifecycle_provider_migration import (
    apply_provider_cutover, preflight_provider_upgrade, preview_provider_cutover,
)
from src.security_lifecycle_schema import verify_profile_connection


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode()


def digest(value):
    return hashlib.sha256(json_bytes(value)).hexdigest()


def write(directory, name, value):
    fd = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(json_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())


def stopped():
    for pid in APP_PIDS:
        require(not Path(f"/proc/{pid}").exists(), "cutover_app_process_still_present")
    for port in (8430, 39769):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                raise ValueError("cutover_app_port_in_use") from None


def readonly(path):
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")
    return conn


def backup(source, target):
    fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    conn = readonly(source)
    destination = sqlite3.connect(target)
    try:
        conn.backup(destination)
        require(destination.execute("PRAGMA integrity_check").fetchall() == [("ok",)], "cutover_backup_integrity")
    finally:
        destination.close()
        conn.close()


def universe(profile, sa):
    value = build_active_universe_snapshot(profile_db=profile, sa_db=sa)
    require(all(item.available for item in value.source_status.values()), "cutover_universe_source_unavailable")
    return {"tickers": list(value.tickers), "sources": {k: list(v) for k, v in value.sources_by_ticker.items()}}


def row_inventory(path):
    conn = readonly(path)
    try:
        names = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND ("
            "name LIKE 'security_lifecycle_%' OR name LIKE 'ticker_identity_%' OR "
            "name IN ('ticker_meta','watchlists','watchlist_memberships','universe_source_memberships','portfolio_positions','portfolio_accounts')) ORDER BY name"
        )]
        values = {}
        for name in names:
            quoted = '"' + name.replace('"', '""') + '"'
            rows = conn.execute(f"SELECT rowid,* FROM {quoted} ORDER BY rowid").fetchall()
            values[name] = {"count": len(rows), "sha256": digest(rows)}
        return values
    finally:
        conn.close()


def check_targets(profile, scope):
    conn = readonly(profile)
    try:
        for ticker in TARGETS:
            require(scope["sources"].get(ticker) == ["sa_alpha_picks_former"], "cutover_target_source_changed")
            require(conn.execute(
                "SELECT count(*) FROM portfolio_positions p JOIN portfolio_accounts a ON a.id=p.account_id "
                "WHERE UPPER(TRIM(p.symbol))=? AND p.closed_at IS NULL AND a.archived_at IS NULL", (ticker,)
            ).fetchone()[0] == 0, "cutover_target_open_position")
        require(conn.execute("SELECT count(*) FROM ticker_identity_transitions").fetchone()[0] == 0, "cutover_transition_scope_changed")
    finally:
        conn.close()


def membership_summary(profile):
    conn = readonly(profile)
    try:
        verify_profile_connection(conn)
        require(SaTrackingMembershipStore.installed(conn), "cutover_membership_absent")
        require(conn.execute("PRAGMA integrity_check").fetchall() == [("ok",)], "cutover_integrity")
        require(not conn.execute("PRAGMA foreign_key_check").fetchall(), "cutover_foreign_keys")
        return {
            "memberships": conn.execute("SELECT count(*) FROM sa_tracking_memberships").fetchone()[0],
            "bindings": conn.execute("SELECT count(*) FROM sa_tracking_bindings").fetchone()[0],
            "events": conn.execute("SELECT count(*) FROM sa_tracking_events").fetchone()[0],
            "removed_memberships": conn.execute("SELECT count(*) FROM sa_tracking_memberships WHERE removed_at IS NOT NULL").fetchone()[0],
            "actors": dict(conn.execute("SELECT actor,count(*) FROM sa_tracking_events GROUP BY actor")),
            "statuses": dict(conn.execute("SELECT portfolio_status,count(*) FROM sa_tracking_memberships GROUP BY portfolio_status")),
            "current_tracking_count": conn.execute("SELECT count(*) FROM sa_tracking_memberships WHERE current_tracking=1").fetchone()[0],
            "dual_source_count": conn.execute("SELECT count(*) FROM sa_tracking_memberships WHERE portfolio_status='closed' AND current_tracking=1").fetchone()[0],
            "integrity": "ok", "foreign_key_violations": 0,
        }
    finally:
        conn.close()


def unchanged(before, after):
    require(all(after.get(name) == value for name, value in before.items()), "cutover_existing_rows_changed")


def prepare(directory):
    stopped()
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    before = preview_provider_cutover(PROFILE, SA)
    require(before["profile"]["schema_version"] == "v3", "cutover_expected_v3")
    require(before["profile"]["automation"] == {"valid": True, "enabled": False, "apply_profile_transitions": False}, "cutover_automation_not_disabled")
    require((before["lineage_count"], before["current_count"], before["former_count"]) == (105, 46, 59), "cutover_sa_scope_changed")
    scope = universe(PROFILE, SA)
    require(len(scope["tickers"]) == 186, "cutover_universe_changed")
    check_targets(PROFILE, scope)
    inventory = row_inventory(PROFILE)
    at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    write(directory, "preview.json", before)
    write(directory, "private-universe-before.json", scope)
    write(directory, "old-row-inventory.json", inventory)
    backup(PROFILE, directory / "profile.rehearsal.db")
    backup(SA, directory / "sa-capture.before.db")
    rehearsal_preview = preview_provider_cutover(directory / "profile.rehearsal.db", directory / "sa-capture.before.db")
    require(rehearsal_preview == before, "cutover_rehearsal_input_changed")
    result = apply_provider_cutover(
        directory / "profile.rehearsal.db", directory / "sa-capture.before.db",
        backup_path=directory / "profile.rehearsal-v3.backup.db", cutover_sha256=before["cutover_sha256"], at=at, app_stopped=True,
    )
    unchanged(inventory, row_inventory(directory / "profile.rehearsal.db"))
    require(universe(directory / "profile.rehearsal.db", directory / "sa-capture.before.db") == scope, "cutover_rehearsal_universe_changed")
    summary = membership_summary(directory / "profile.rehearsal.db")
    require(summary["memberships"] == summary["bindings"] == 105 and summary["removed_memberships"] == 0, "cutover_rehearsal_membership_count")
    require(preview_provider_cutover(PROFILE, SA) == before, "cutover_live_preview_changed")
    write(directory, "private-rehearsal-receipt.json", result)
    public = {"at": at, "cutover_sha256": before["cutover_sha256"], "rehearsal": summary,
              "existing_domain_tables_preserved": len(inventory), "universe_preserved": 186,
              "provider_requests": 0, "production_migration_performed": False}
    write(directory, "prepare-summary.json", public)
    print(json.dumps(public, sort_keys=True))


def apply(directory, approved):
    stopped()
    before = json.loads((directory / "preview.json").read_text())
    require(approved == before["cutover_sha256"], "cutover_approval_mismatch")
    require(preview_provider_cutover(PROFILE, SA) == before, "cutover_preview_changed")
    scope = json.loads((directory / "private-universe-before.json").read_text())
    check_targets(PROFILE, scope)
    at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    write(directory, "production-install-started.json", {"at": at, "cutover_sha256": approved})
    result = apply_provider_cutover(PROFILE, SA, backup_path=directory / "profile-state.v3.backup.db",
                                    cutover_sha256=approved, at=at, app_stopped=True)
    write(directory, "private-production-install-receipt.json", result)
    inventory = json.loads((directory / "old-row-inventory.json").read_text())
    unchanged(inventory, row_inventory(PROFILE))
    require(universe(PROFILE, SA) == scope, "cutover_production_universe_changed")
    check_targets(PROFILE, scope)
    summary = membership_summary(PROFILE)
    require(summary["memberships"] == summary["bindings"] == 105 and summary["removed_memberships"] == 0, "cutover_production_membership_count")
    require(summary["current_tracking_count"] == before["current_observed_count"] and summary["dual_source_count"] == before["dual_source_count"],
            "cutover_production_dual_source_count")
    require(read_sa_tracking_observations(SA) == read_sa_tracking_observations(directory / "sa-capture.before.db"), "cutover_sa_changed")
    current = preview_provider_cutover(PROFILE, SA)
    again = apply_provider_cutover(PROFILE, SA, backup_path=directory / "unused-idempotence.db",
                                  cutover_sha256=current["cutover_sha256"], at=at, app_stopped=True)
    require(again["changed"] is False and not (directory / "unused-idempotence.db").exists(), "cutover_idempotence")
    require(preview_provider_cutover(PROFILE, SA) == current, "cutover_idempotence_changed_state")
    public = {"at": at, "schema_version": result["schema_version"], "changed": result["changed"],
              "membership": summary, "automation": result["automation"], "universe_preserved": 186,
              "existing_domain_tables_preserved": len(inventory), "backup_sha256": result["backup_sha256"],
              "cutover_sha256": approved, "idempotence_verified": True,
              "terminal_dispositions_applied": 0, "provider_requests": 0, "price_writes": 0,
              "post_profile_sha256": result["approval_sha256"]}
    write(directory, "install-summary.json", public)
    print(json.dumps(public, sort_keys=True))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("prepare", "apply"))
    parser.add_argument("--directory", required=True, type=Path)
    parser.add_argument("--approved-cutover")
    args = parser.parse_args()
    lock = sqlite3.connect(f"{SA.as_uri()}?mode=rw", uri=True, timeout=2)
    try:
        lock.execute("BEGIN IMMEDIATE")
        if args.phase == "prepare":
            prepare(args.directory)
        else:
            apply(args.directory, args.approved_cutover)
    finally:
        lock.rollback()
        lock.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        code = str(exc) if isinstance(exc, ValueError) and str(exc).startswith("cutover_") else type(exc).__name__
        print(json.dumps({"status": "stopped", "code": code}))
        raise SystemExit(1) from None
