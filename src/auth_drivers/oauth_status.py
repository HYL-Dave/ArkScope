"""Local OAuth lifecycle truth and bounded non-secret observations."""

from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Iterator

from pydantic import BaseModel


MAX_REFRESH_DETAIL_LENGTH = 240
_REFRESH_BUFFER = timedelta(minutes=5)


class OAuthLifecycleState(str, Enum):
    READY = "ready"
    REFRESH_REQUIRED = "refresh_required"
    REFRESH_FAILED_RETRYABLE = "refresh_failed_retryable"
    REAUTH_REQUIRED = "reauth_required"
    UNVERIFIABLE = "unverifiable"


class OAuthRefreshStatus(BaseModel):
    credential_id: str
    provider: str
    auth_mode: str
    last_refresh_attempt_at: str | None = None
    last_refresh_success_at: str | None = None
    last_refresh_error_at: str | None = None
    last_refresh_error_code: str | None = None
    last_refresh_error_detail: str | None = None
    updated_at: str


class OAuthLifecycleProjection(BaseModel):
    lifecycle_state: OAuthLifecycleState
    expires_at: str | None = None
    lifecycle_error_code: str | None = None
    last_refresh_attempt_at: str | None = None
    last_refresh_success_at: str | None = None
    last_refresh_error_at: str | None = None
    last_refresh_error_detail: str | None = None

    @property
    def available(self) -> bool:
        return self.lifecycle_state == OAuthLifecycleState.READY


_SCHEMA = """
CREATE TABLE IF NOT EXISTS oauth_refresh_status (
    credential_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    auth_mode TEXT NOT NULL,
    last_refresh_attempt_at TEXT,
    last_refresh_success_at TEXT,
    last_refresh_error_at TEXT,
    last_refresh_error_code TEXT,
    last_refresh_error_detail TEXT,
    updated_at TEXT NOT NULL
);
"""

_ERROR_CODES = frozenset(
    {
        "invalid_grant",
        "missing_refresh_token",
        "missing_token",
        "oauth_lock_busy",
        "protocol_incompatible",
        "token_store_unavailable",
        "transport_error",
    }
)
_RETRYABLE_CODES = frozenset({"oauth_lock_busy", "transport_error"})
_TERMINAL_CODES = frozenset({"invalid_grant", "missing_refresh_token", "missing_token"})
_UNVERIFIABLE_CODES = frozenset({"protocol_incompatible", "token_store_unavailable"})

_KEYED_SECRET_RE = re.compile(
    r"(?i)\b(access[_ -]?token|refresh[_ -]?token|id[_ -]?token|authorization|"
    r"account[_ -]?id|raw[_ -]?account[_ -]?id|email)\b\s*[:=]\s*[^\s,;]+"
)
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[^\s,;]+")
_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_OPAQUE_RE = re.compile(r"\b[A-Za-z0-9_-]{32,}\b")
def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    if re.search(r"[+-]\d{4}$", normalized):
        normalized = normalized[:-5] + normalized[-5:-2] + ":" + normalized[-2:]
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("OAuth timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def _timestamp(value: str | datetime | None = None) -> str:
    parsed = _utc_now() if value is None else (_parse_datetime(value) if isinstance(value, str) else value)
    if parsed.tzinfo is None:
        raise ValueError("OAuth timestamps must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


def _sanitize_detail(detail: str | None) -> str | None:
    if detail is None:
        return None
    text = " ".join(str(detail).split())
    text = _KEYED_SECRET_RE.sub(lambda match: f"{match.group(1)}=<redacted>", text)
    text = _BEARER_RE.sub("Bearer <redacted>", text)
    text = _EMAIL_RE.sub("<redacted-email>", text)
    text = _OPAQUE_RE.sub("<redacted>", text)
    return text[:MAX_REFRESH_DETAIL_LENGTH] or None


class OAuthObservationStore:
    """Latest-only OAuth observations in the local profile-state database.

    Construction and reads are no-create. The first explicit write creates the
    parent/database/schema, then replaces one row per credential.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    @contextmanager
    def _write_connection(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), timeout=5.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA busy_timeout = 5000")
            conn.executescript(_SCHEMA)
            yield conn
        finally:
            conn.close()

    @contextmanager
    def _read_connection(self) -> Iterator[sqlite3.Connection | None]:
        if not self.db_path.is_file():
            yield None
            return
        conn = sqlite3.connect(f"{self.db_path.resolve().as_uri()}?mode=ro", uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA query_only = ON")
            yield conn
        finally:
            conn.close()

    @staticmethod
    def _has_table(conn: sqlite3.Connection, table: str) -> bool:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
        ).fetchone() is not None

    def read_refresh_status(self, credential_id: str) -> OAuthRefreshStatus | None:
        with self._read_connection() as conn:
            if conn is None or not self._has_table(conn, "oauth_refresh_status"):
                return None
            row = conn.execute(
                "SELECT credential_id, provider, auth_mode, last_refresh_attempt_at, "
                "last_refresh_success_at, last_refresh_error_at, last_refresh_error_code, "
                "last_refresh_error_detail, updated_at FROM oauth_refresh_status "
                "WHERE credential_id = ?",
                (credential_id,),
            ).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["last_refresh_error_detail"] = _sanitize_detail(data["last_refresh_error_detail"])
        return OAuthRefreshStatus(**data)

    def record_refresh_attempt(
        self,
        *,
        credential_id: str,
        provider: str,
        auth_mode: str,
        observed_at: str | datetime | None = None,
    ) -> None:
        timestamp = _timestamp(observed_at)
        with self._write_connection() as conn:
            conn.execute(
                "INSERT INTO oauth_refresh_status "
                "(credential_id, provider, auth_mode, last_refresh_attempt_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(credential_id) DO UPDATE SET "
                "provider=excluded.provider, auth_mode=excluded.auth_mode, "
                "last_refresh_attempt_at=excluded.last_refresh_attempt_at, updated_at=excluded.updated_at",
                (credential_id, provider, auth_mode, timestamp, timestamp),
            )
            conn.commit()

    def record_refresh_success(
        self,
        *,
        credential_id: str,
        provider: str,
        auth_mode: str,
        observed_at: str | datetime | None = None,
    ) -> None:
        timestamp = _timestamp(observed_at)
        with self._write_connection() as conn:
            conn.execute(
                "INSERT INTO oauth_refresh_status "
                "(credential_id, provider, auth_mode, last_refresh_success_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(credential_id) DO UPDATE SET "
                "provider=excluded.provider, auth_mode=excluded.auth_mode, "
                "last_refresh_success_at=excluded.last_refresh_success_at, "
                "last_refresh_error_at=NULL, last_refresh_error_code=NULL, "
                "last_refresh_error_detail=NULL, updated_at=excluded.updated_at",
                (credential_id, provider, auth_mode, timestamp, timestamp),
            )
            conn.commit()

    def record_refresh_error(
        self,
        *,
        credential_id: str,
        provider: str,
        auth_mode: str,
        error_code: str,
        detail: str | None = None,
        observed_at: str | datetime | None = None,
    ) -> None:
        if error_code not in _ERROR_CODES:
            raise ValueError(f"unsupported OAuth refresh error code: {error_code}")
        timestamp = _timestamp(observed_at)
        safe_detail = _sanitize_detail(detail)
        with self._write_connection() as conn:
            conn.execute(
                "INSERT INTO oauth_refresh_status "
                "(credential_id, provider, auth_mode, last_refresh_error_at, "
                "last_refresh_error_code, last_refresh_error_detail, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(credential_id) DO UPDATE SET "
                "provider=excluded.provider, auth_mode=excluded.auth_mode, "
                "last_refresh_error_at=excluded.last_refresh_error_at, "
                "last_refresh_error_code=excluded.last_refresh_error_code, "
                "last_refresh_error_detail=excluded.last_refresh_error_detail, "
                "updated_at=excluded.updated_at",
                (credential_id, provider, auth_mode, timestamp, error_code, safe_detail, timestamp),
            )
            conn.commit()

def _projection(
    state: OAuthLifecycleState,
    *,
    expires_at: str | None,
    error_code: str | None = None,
    status: OAuthRefreshStatus | None = None,
) -> OAuthLifecycleProjection:
    return OAuthLifecycleProjection(
        lifecycle_state=state,
        expires_at=expires_at,
        lifecycle_error_code=error_code,
        last_refresh_attempt_at=status.last_refresh_attempt_at if status else None,
        last_refresh_success_at=status.last_refresh_success_at if status else None,
        last_refresh_error_at=status.last_refresh_error_at if status else None,
        last_refresh_error_detail=status.last_refresh_error_detail if status else None,
    )


def _latest_error_code(status: OAuthRefreshStatus | None) -> str | None:
    if status is None or not status.last_refresh_error_at or not status.last_refresh_error_code:
        return None
    if status.last_refresh_success_at:
        if _parse_datetime(status.last_refresh_success_at) >= _parse_datetime(status.last_refresh_error_at):
            return None
    return status.last_refresh_error_code


def project_oauth_lifecycle(
    *,
    provider: str,
    auth_mode: str,
    credential_id: str,
    db_expires_at: str | None,
    token_store=None,
    observation_store: OAuthObservationStore | None = None,
    now: datetime | None = None,
) -> OAuthLifecycleProjection:
    """Project local token and latest-witness evidence into one closed state."""
    owned_expiry = db_expires_at if auth_mode == "claude_code_oauth" else None
    status: OAuthRefreshStatus | None = None
    if observation_store is not None:
        try:
            status = observation_store.read_refresh_status(credential_id)
        except Exception:  # noqa: BLE001 - local status cannot be trusted
            return _projection(
                OAuthLifecycleState.UNVERIFIABLE,
                expires_at=owned_expiry,
                error_code="protocol_incompatible",
            )

    try:
        if token_store is None:
            raise RuntimeError("OAuth token store was not supplied")
        record = token_store.load(
            provider=provider,
            auth_mode=auth_mode,
            credential_id=credential_id,
        )
    except Exception:  # noqa: BLE001 - never expose token-store diagnostics
        return _projection(
            OAuthLifecycleState.UNVERIFIABLE,
            expires_at=owned_expiry,
            error_code="token_store_unavailable",
            status=status,
        )

    if record is None or not getattr(record, "access_token", None):
        return _projection(
            OAuthLifecycleState.REAUTH_REQUIRED,
            expires_at=owned_expiry,
            error_code="missing_token",
            status=status,
        )

    expires_at = getattr(record, "expires_at", None) if auth_mode == "chatgpt_oauth" else db_expires_at
    current = now or _utc_now()
    if current.tzinfo is None:
        raise ValueError("OAuth lifecycle projection requires a timezone-aware now")

    due = False
    if expires_at:
        try:
            due = _parse_datetime(expires_at) <= current.astimezone(timezone.utc) + _REFRESH_BUFFER
        except (TypeError, ValueError):
            return _projection(
                OAuthLifecycleState.UNVERIFIABLE,
                expires_at=expires_at,
                error_code="protocol_incompatible",
                status=status,
            )

    try:
        latest_error = _latest_error_code(status)
    except ValueError:
        return _projection(
            OAuthLifecycleState.UNVERIFIABLE,
            expires_at=expires_at,
            error_code="protocol_incompatible",
            status=status,
        )
    if latest_error in _RETRYABLE_CODES:
        return _projection(
            OAuthLifecycleState.REFRESH_FAILED_RETRYABLE,
            expires_at=expires_at,
            error_code=latest_error,
            status=status,
        )
    if latest_error in _TERMINAL_CODES:
        return _projection(
            OAuthLifecycleState.REAUTH_REQUIRED,
            expires_at=expires_at,
            error_code=latest_error,
            status=status,
        )
    if latest_error in _UNVERIFIABLE_CODES or latest_error is not None:
        return _projection(
            OAuthLifecycleState.UNVERIFIABLE,
            expires_at=expires_at,
            error_code=(
                latest_error if latest_error in _UNVERIFIABLE_CODES else "protocol_incompatible"
            ),
            status=status,
        )

    if not due:
        return _projection(
            OAuthLifecycleState.READY,
            expires_at=expires_at,
            status=status,
        )

    if getattr(record, "refresh_token", None):
        return _projection(
            OAuthLifecycleState.REFRESH_REQUIRED,
            expires_at=expires_at,
            status=status,
        )
    return _projection(
        OAuthLifecycleState.REAUTH_REQUIRED,
        expires_at=expires_at,
        error_code="missing_refresh_token",
        status=status,
    )
