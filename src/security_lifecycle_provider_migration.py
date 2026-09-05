"""Explicit, backed-up V3-to-V4 provider evidence and membership installation."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3

from src.sa_tracking_memberships import SaTrackingMembershipStore, read_sa_tracking_observations, tracking_identity_context
from src.security_lifecycle_schema import (
    LifecycleSchemaMismatch, PROFILE_INDEX_SQL, PROFILE_TABLE_SQL, PROFILE_TRIGGER_SQL,
    V3_PROFILE_TABLE_SQL, verify_profile_connection, verify_v3_profile_connection,
)
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
    try:
        verify_profile_connection(conn)
        version = "v4"
    except LifecycleSchemaMismatch:
        verify_v3_profile_connection(conn)
        version = "v3"
    if conn.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise ValueError("provider_upgrade_integrity")
    automation = parse_security_lifecycle_automation_config(_automation_settings(conn))
    return {"schema_version": version, "approval_sha256": _digest(conn),
            "membership_installed": SaTrackingMembershipStore.installed(conn),
            "automation": {"valid": automation.valid,
                           "enabled": automation.config.enabled if automation.config else None,
                           "apply_profile_transitions": automation.config.apply_profile_transitions if automation.config else None}}


def preflight_provider_upgrade(path: str | Path) -> dict:
    with sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=ro", uri=True) as conn:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")
        return _preflight(conn)


def upgrade_provider_authority(path: str | Path, *, backup_path: str | Path, approval_sha256: str,
                               bootstrap_observations=None, at: str | None = None) -> dict:
    source = Path(path).resolve()
    backup = Path(backup_path).resolve()
    if source == backup:
        raise ValueError("provider_upgrade_backup_path")
    with sqlite3.connect(f"{source.as_uri()}?mode=rw", uri=True, timeout=10) as conn:
        before = _preflight(conn)
        if before["approval_sha256"] != approval_sha256:
            raise ValueError("provider_upgrade_preview_changed")
        if before["automation"] != {"valid": True, "enabled": False, "apply_profile_transitions": False}:
            raise ValueError("provider_upgrade_automation_disable_required")
        if before["schema_version"] == "v4" and before["membership_installed"]:
            return {"changed": False, **before}
        backup.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        with sqlite3.connect(backup) as destination:
            conn.backup(destination)
        if preflight_provider_upgrade(backup)["approval_sha256"] != approval_sha256:
            raise ValueError("provider_upgrade_backup_changed")
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("BEGIN IMMEDIATE")
        try:
            if _preflight(conn)["approval_sha256"] != approval_sha256:
                raise ValueError("provider_upgrade_preview_changed")
            if before["schema_version"] == "v3":
                cursor = conn.execute("SELECT rowid,* FROM security_lifecycle_evidence ORDER BY rowid")
                columns = [item[0] for item in cursor.description]
                rows = cursor.fetchall()
                conn.execute("DROP TABLE security_lifecycle_evidence")
                conn.execute(PROFILE_TABLE_SQL["security_lifecycle_evidence"])
                projection = ",".join('"' + column + '"' for column in columns)
                placeholders = ",".join("?" for _ in columns)
                conn.executemany(f"INSERT INTO security_lifecycle_evidence ({projection}) VALUES ({placeholders})", rows)
                for table in PROFILE_TABLE_SQL.keys() - V3_PROFILE_TABLE_SQL.keys():
                    conn.execute(PROFILE_TABLE_SQL[table])
                for statement in PROFILE_TRIGGER_SQL.values():
                    conn.execute(statement)
                indexes = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
                for name, statement in PROFILE_INDEX_SQL.items():
                    if name not in indexes:
                        conn.execute(statement)
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
    return {"changed": True, **preflight_provider_upgrade(source),
            "backup_sha256": hashlib.sha256(backup.read_bytes()).hexdigest()}


def _cutover_preview(profile_path, observations):
    profile = preflight_provider_upgrade(profile_path)
    observation_digest = hashlib.sha256(json.dumps(observations, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    payload = {"profile": profile, "observations_sha256": observation_digest,
               "lineage_count": len(observations), "current_count": sum(row["portfolio_status"] == "current" for row in observations),
               "former_count": sum(row["portfolio_status"] == "closed" for row in observations),
               "current_observed_count": sum(row.get("current_observed", row["portfolio_status"] == "current") for row in observations),
               "dual_source_count": sum(row["portfolio_status"] == "closed" and row.get("current_observed", False) for row in observations)}
    return {**payload, "cutover_sha256": hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}


def preview_provider_cutover(profile_path, sa_path):
    return _cutover_preview(profile_path, read_sa_tracking_observations(sa_path))


def apply_provider_cutover(profile_path, sa_path, *, backup_path, cutover_sha256, at, app_stopped):
    if app_stopped is not True:
        raise ValueError("provider_cutover_app_stop_required")
    observations = read_sa_tracking_observations(sa_path)
    preview = _cutover_preview(profile_path, observations)
    if preview["cutover_sha256"] != cutover_sha256:
        raise ValueError("provider_cutover_preview_changed")
    result = upgrade_provider_authority(profile_path, backup_path=backup_path,
        approval_sha256=preview["profile"]["approval_sha256"], bootstrap_observations=observations, at=at)
    return {**result, "bootstrap": preview, "actor": "attended_user", "at": at,
            "memberships": SaTrackingMembershipStore(profile_path).list_memberships()}
