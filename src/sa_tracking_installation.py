"""Attended, backed-up tracking-membership installation on current V4 profiles."""

from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3

from src.sa_tracking_memberships import SaTrackingMembershipStore, read_sa_tracking_observations, tracking_identity_context
from src.security_lifecycle_schema import verify_profile_connection
from src.service.security_lifecycle_automation_config import (
    SECURITY_LIFECYCLE_AUTOMATION_SETTING_KEYS,
    parse_security_lifecycle_automation_config,
)


def _automation_settings(conn: sqlite3.Connection) -> dict:
    keys = SECURITY_LIFECYCLE_AUTOMATION_SETTING_KEYS
    placeholders = ",".join("?" for _ in keys)
    return dict(conn.execute(
        f"SELECT key,value FROM profile_settings WHERE key IN ({placeholders}) ORDER BY key",
        keys,
    ))


def _digest(conn: sqlite3.Connection) -> str:
    digest = hashlib.sha256()
    digest.update(json.dumps(_automation_settings(conn), sort_keys=True, separators=(",", ":")).encode())
    names = [row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND ("
        "name LIKE 'security_lifecycle_%' OR name LIKE 'ticker_identity_%' OR "
        "name LIKE 'sa_tracking_%' OR name IN ('ticker_meta','watchlists','watchlist_memberships','universe_source_memberships','portfolio_positions','portfolio_accounts')) ORDER BY name"
    )]
    for name in names:
        quoted = '"' + name.replace('"', '""') + '"'
        schema = conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (name,)).fetchone()[0]
        digest.update(schema.encode())
        for row in conn.execute(f"SELECT * FROM {quoted} ORDER BY rowid"):
            digest.update(json.dumps(tuple(row), separators=(",", ":"), ensure_ascii=True).encode())
            digest.update(b"\n")
    return digest.hexdigest()


def _preflight(conn: sqlite3.Connection) -> dict:
    verify_profile_connection(conn)
    if conn.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise ValueError("provider_upgrade_integrity")
    automation = parse_security_lifecycle_automation_config(_automation_settings(conn))
    return {"schema_version": "v4", "approval_sha256": _digest(conn),
            "membership_installed": SaTrackingMembershipStore.installed(conn),
            "automation": {"valid": automation.valid,
                           "enabled": automation.config.enabled if automation.config else None,
                           "apply_profile_transitions": automation.config.apply_profile_transitions if automation.config else None}}


def inspect_installation(path: str | Path) -> dict:
    """Inspect current schema, controls and membership state in one read snapshot."""
    with closing(sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=ro", uri=True)) as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        try:
            return _preflight(conn)
        finally:
            conn.rollback()


def _install_memberships(path: str | Path, *, backup_path: str | Path, approval_sha256: str,
                         bootstrap_observations=None, at: str | None = None) -> dict:
    source = Path(path).resolve()
    backup = Path(backup_path).resolve()
    if source == backup:
        raise ValueError("provider_upgrade_backup_path")
    with closing(sqlite3.connect(f"{source.as_uri()}?mode=rw", uri=True, timeout=10)) as conn:
        before = _preflight(conn)
        if before["approval_sha256"] != approval_sha256:
            raise ValueError("provider_upgrade_preview_changed")
        if before["automation"] != {"valid": True, "enabled": False, "apply_profile_transitions": False}:
            raise ValueError("provider_upgrade_automation_disable_required")
        if before["membership_installed"]:
            return {"changed": False, **before}
        backup.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        with closing(sqlite3.connect(backup)) as destination:
            conn.backup(destination)
        if inspect_installation(backup)["approval_sha256"] != approval_sha256:
            raise ValueError("provider_upgrade_backup_changed")
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN IMMEDIATE")
        try:
            if _preflight(conn)["approval_sha256"] != approval_sha256:
                raise ValueError("provider_upgrade_preview_changed")
            SaTrackingMembershipStore.install(conn)
            if bootstrap_observations is not None:
                links, relations = tracking_identity_context(conn)
                SaTrackingMembershipStore.reconcile_in_transaction(
                    conn, bootstrap_observations, at=at, bootstrap_actor="attended_user",
                    identity_links=links, related_securities=relations,
                )
            verify_profile_connection(conn)
            if conn.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ValueError("provider_upgrade_integrity")
            if conn.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("provider_upgrade_foreign_keys")
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.execute("PRAGMA foreign_keys=ON")
    return {"changed": True, **inspect_installation(source),
            "backup_sha256": hashlib.sha256(backup.read_bytes()).hexdigest()}


def _installation_preview(profile_path, observations):
    profile = inspect_installation(profile_path)
    observation_digest = hashlib.sha256(json.dumps(observations, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    payload = {"profile": profile, "observations_sha256": observation_digest,
               "lineage_count": len(observations), "current_count": sum(row["portfolio_status"] == "current" for row in observations),
               "former_count": sum(row["portfolio_status"] == "closed" for row in observations),
               "current_observed_count": sum(row.get("current_observed", row["portfolio_status"] == "current") for row in observations),
               "dual_source_count": sum(row["portfolio_status"] == "closed" and row.get("current_observed", False) for row in observations)}
    return {**payload, "cutover_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}


def preview_installation(profile_path, sa_path):
    """Bind a current profile and the exact SA observations for attended approval."""
    return _installation_preview(profile_path, read_sa_tracking_observations(sa_path))


def apply_installation(profile_path, sa_path, *, backup_path, cutover_sha256, at, app_stopped):
    """Install missing memberships with disabled automation and a stopped App."""
    if app_stopped is not True:
        raise ValueError("provider_cutover_app_stop_required")
    observations = read_sa_tracking_observations(sa_path)
    preview = _installation_preview(profile_path, observations)
    if preview["cutover_sha256"] != cutover_sha256:
        raise ValueError("provider_cutover_preview_changed")
    result = _install_memberships(profile_path, backup_path=backup_path,
        approval_sha256=preview["profile"]["approval_sha256"], bootstrap_observations=observations, at=at)
    return {**result, "bootstrap": preview, "actor": "attended_user", "at": at,
            "memberships": SaTrackingMembershipStore(profile_path).list_memberships()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "install-preview", "install"):
        item = commands.add_parser(name)
        item.add_argument("--profile", required=True, type=Path)
        if name != "inspect":
            item.add_argument("--sa", required=True, type=Path)
        if name == "install":
            item.add_argument("--backup", required=True, type=Path)
            item.add_argument("--cutover-sha256", required=True)
            item.add_argument("--app-stopped", action="store_true", required=True)
        else:
            item.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command == "install":
        value = apply_installation(args.profile, args.sa, backup_path=args.backup,
            cutover_sha256=args.cutover_sha256, at=datetime.now(timezone.utc).isoformat(),
            app_stopped=args.app_stopped)
    else:
        with args.output.open("x", encoding="utf-8") as output:
            value = inspect_installation(args.profile) if args.command == "inspect" else preview_installation(args.profile, args.sa)
            output.write(json.dumps(value, ensure_ascii=True, indent=2) + "\n")
    print(json.dumps(value, ensure_ascii=True, sort_keys=True))
    return value


if __name__ == "__main__":
    main()
