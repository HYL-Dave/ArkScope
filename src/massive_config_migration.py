"""Explicit migration from the legacy Polygon credential namespace to Massive."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from src.data_provider_config import (
    LEGACY_POLYGON_CONFIG_PROVIDER,
    MASSIVE_CONFIG_PROVIDER,
)

_FIELD = "api_key"
_FORMAT_VERSION = 1


class MassiveConfigMigrationError(RuntimeError):
    """Base class for explicit Massive configuration migration failures."""


class MassiveConfigMigrationConflict(MassiveConfigMigrationError):
    """Both namespaces hold different credentials; operator choice is required."""


class MassiveConfigMigrationApprovalMismatch(MassiveConfigMigrationError):
    """The profile rows changed after preflight."""


@dataclass(frozen=True)
class MassiveConfigMigrationPreflight:
    state: str
    eligible: bool
    approval_sha256: str
    legacy_value_sha256: str | None
    current_value_sha256: str | None
    legacy_updated_at: str | None
    current_updated_at: str | None


@dataclass(frozen=True)
class MassiveConfigMigrationResult:
    changed: bool
    before_state: str
    after_state: str
    approval_sha256: str


def _connect(path: Path, *, writable: bool) -> sqlite3.Connection:
    mode = "rw" if writable else "ro"
    return sqlite3.connect(
        f"{path.resolve().as_uri()}?mode={mode}", uri=True, timeout=10.0
    )


def _row(conn: sqlite3.Connection, provider: str) -> tuple[str, str] | None:
    try:
        value = conn.execute(
            "SELECT value, updated_at FROM data_provider_config "
            "WHERE provider = ? AND field = ?",
            (provider, _FIELD),
        ).fetchone()
    except sqlite3.OperationalError as exc:
        raise MassiveConfigMigrationError(
            "data_provider_config schema unavailable"
        ) from exc
    if value is None:
        return None
    return str(value[0]), str(value[1])


def _value_sha256(row: tuple[str, str] | None) -> str | None:
    if row is None:
        return None
    return hashlib.sha256(row[0].encode("utf-8")).hexdigest()


def _inspect(
    conn: sqlite3.Connection,
    *,
    path: Path,
) -> MassiveConfigMigrationPreflight:
    legacy = _row(conn, LEGACY_POLYGON_CONFIG_PROVIDER)
    current = _row(conn, MASSIVE_CONFIG_PROVIDER)
    if legacy is None and current is None:
        state = "absent"
    elif legacy is not None and current is None:
        state = "legacy_only"
    elif legacy is None and current is not None:
        state = "current_only"
    elif legacy is not None and current is not None and legacy[0] == current[0]:
        state = "duplicate_equal"
    else:
        state = "conflict"

    payload = {
        "format_version": _FORMAT_VERSION,
        "profile_path": str(path.resolve()),
        "state": state,
        "legacy": None
        if legacy is None
        else {"value_sha256": _value_sha256(legacy), "updated_at": legacy[1]},
        "current": None
        if current is None
        else {"value_sha256": _value_sha256(current), "updated_at": current[1]},
    }
    approval = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return MassiveConfigMigrationPreflight(
        state=state,
        eligible=state != "conflict",
        approval_sha256=approval,
        legacy_value_sha256=_value_sha256(legacy),
        current_value_sha256=_value_sha256(current),
        legacy_updated_at=None if legacy is None else legacy[1],
        current_updated_at=None if current is None else current[1],
    )


def preflight_massive_config_migration(
    *,
    profile_path: str | Path,
) -> MassiveConfigMigrationPreflight:
    """Inspect the two credential rows without creating or modifying the DB."""
    path = Path(profile_path)
    with _connect(path, writable=False) as conn:
        return _inspect(conn, path=path)


def migrate_massive_config_authority(
    *,
    profile_path: str | Path,
    approval_sha256: str,
) -> MassiveConfigMigrationResult:
    """Apply one approval-bound row migration under a single SQLite write lock."""
    path = Path(profile_path)
    conn = _connect(path, writable=True)
    try:
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.execute("BEGIN IMMEDIATE")
        before = _inspect(conn, path=path)
        if before.approval_sha256 != approval_sha256:
            raise MassiveConfigMigrationApprovalMismatch(
                "massive config migration approval no longer matches the profile rows"
            )
        if not before.eligible:
            raise MassiveConfigMigrationConflict(
                "polygon.api_key and massive.api_key differ; choose one explicitly"
            )

        changed = False
        if before.state == "legacy_only":
            cursor = conn.execute(
                "UPDATE data_provider_config SET provider = ? "
                "WHERE provider = ? AND field = ?",
                (MASSIVE_CONFIG_PROVIDER, LEGACY_POLYGON_CONFIG_PROVIDER, _FIELD),
            )
            changed = cursor.rowcount == 1
        elif before.state == "duplicate_equal":
            cursor = conn.execute(
                "DELETE FROM data_provider_config WHERE provider = ? AND field = ?",
                (LEGACY_POLYGON_CONFIG_PROVIDER, _FIELD),
            )
            changed = cursor.rowcount == 1

        after = _inspect(conn, path=path)
        expected_after = (
            "current_only"
            if before.state in {"legacy_only", "duplicate_equal", "current_only"}
            else "absent"
        )
        if after.state != expected_after:
            raise MassiveConfigMigrationError(
                "massive config migration postcondition failed"
            )
        conn.commit()
        return MassiveConfigMigrationResult(
            changed=changed,
            before_state=before.state,
            after_state=after.state,
            approval_sha256=before.approval_sha256,
        )
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
