"""Guarded preview/apply orchestration for the one-time S3.0a news identity repair."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from src.market_data_admin import resolve_market_db_path
from src.market_data_direct import backup_market_db, market_write_lock
from src.news_identity import (
    apply_news_identity_plan,
    plan_news_identity_repair,
    validate_news_identity,
)


def preview_news_identity_repair(db_path: str | None = None) -> dict[str, object]:
    """Classify the existing DB through a read-only connection without materializing it."""
    path = Path(db_path or resolve_market_db_path())
    if not path.exists():
        return {
            "exists": False,
            "path": str(path),
            "fingerprint": None,
            "scanned": 0,
            "updates": 0,
            "collisions": 0,
        }
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        plan = plan_news_identity_repair(conn)
        return {
            "exists": True,
            "path": str(path),
            "fingerprint": plan.fingerprint,
            "scanned": plan.scanned,
            "updates": len(plan.updates),
            "collisions": len(plan.collisions),
        }
    finally:
        conn.close()


def _require_clean(validation: dict[str, int]) -> None:
    failures = {
        key: validation[key]
        for key in (
            "hash_mismatches",
            "duplicate_hash_groups",
            "semantic_duplicate_groups",
            "fts_missing",
            "fts_orphans",
        )
        if validation[key] != 0
    }
    if validation["news_rows"] != validation["fts_rows"]:
        failures["news_fts_count_delta"] = validation["news_rows"] - validation["fts_rows"]
    if failures:
        detail = ", ".join(f"{key}={value}" for key, value in failures.items())
        raise RuntimeError(f"news identity post-validation failed: {detail}")


def _default_backup_path(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return path.with_name(f"{path.name}.bak-pre-news-identity-{stamp}")


def apply_news_identity_repair(
    *,
    expected_fingerprint: str,
    db_path: str | None = None,
    backup_path: str | None = None,
) -> dict[str, object]:
    """Apply one reviewed repair plan under the market writer lock and one transaction."""
    path = Path(db_path or resolve_market_db_path())
    if not path.exists():
        raise FileNotFoundError(path)

    with market_write_lock():
        conn = sqlite3.connect(path, timeout=10.0)
        try:
            conn.execute("PRAGMA busy_timeout = 10000")
            plan = plan_news_identity_repair(conn)
            if plan.fingerprint != expected_fingerprint:
                raise ValueError(
                    "news identity preview fingerprint changed; run and review preview again")

            if not plan.updates and not plan.collisions:
                validation = validate_news_identity(conn)
                _require_clean(validation)
                return {
                    "path": str(path),
                    "fingerprint": plan.fingerprint,
                    "backup_path": None,
                    "changes": {"updated": 0, "deleted": 0, "merged_fields": 0},
                    "validation": validation,
                }

            destination = Path(backup_path) if backup_path else _default_backup_path(path)
            backup_market_db(str(path), str(destination), overwrite=False)

            conn.execute("BEGIN IMMEDIATE")
            locked_plan = plan_news_identity_repair(conn)
            if locked_plan.fingerprint != plan.fingerprint:
                raise RuntimeError("news identity plan changed after transaction start")
            changes = apply_news_identity_plan(conn, locked_plan)
            validation = validate_news_identity(conn)
            _require_clean(validation)
            conn.commit()
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()

        verify = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            after_plan = plan_news_identity_repair(verify)
            after_validation = validate_news_identity(verify)
            _require_clean(after_validation)
            if after_plan.updates or after_plan.collisions:
                raise RuntimeError("news identity repair committed but post-check is not idempotent")
        finally:
            verify.close()

        return {
            "path": str(path),
            "fingerprint": plan.fingerprint,
            "backup_path": str(destination),
            "changes": changes,
            "validation": after_validation,
        }
