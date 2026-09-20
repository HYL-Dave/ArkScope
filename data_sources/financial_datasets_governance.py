"""Installation/key-scoped admission for metered Financial Datasets requests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import math
import os
from pathlib import Path
import sqlite3
import time
from typing import Mapping


class FinancialDatasetsFailure(RuntimeError):
    """Closed public failure; never includes credentials, URLs or response text."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class FinancialDatasetsPolicy:
    daily_request_limit: int
    requests_per_minute: int

    def __post_init__(self):
        if any(type(value) is not int or not 0 < value < 2**63 for value in (
            self.daily_request_limit, self.requests_per_minute,
        )):
            raise FinancialDatasetsFailure("financial_datasets_policy_invalid")

    @classmethod
    def from_config(cls, config: Mapping | None):
        if config is None:
            raise FinancialDatasetsFailure("financial_datasets_policy_unconfigured")
        if not isinstance(config, Mapping) or type(config.get("enabled")) is not bool:
            raise FinancialDatasetsFailure("financial_datasets_policy_invalid")
        if not config["enabled"]:
            raise FinancialDatasetsFailure("financial_datasets_paid_requests_disabled")
        if any(config.get(key) is None for key in ("daily_request_limit", "requests_per_minute")):
            raise FinancialDatasetsFailure("financial_datasets_policy_unconfigured")
        return cls(config["daily_request_limit"], config["requests_per_minute"])


_SCHEMA = ("""
CREATE TABLE fd_request_accounts (
    key_hash TEXT PRIMARY KEY,
    day TEXT NOT NULL,
    attempts INTEGER NOT NULL CHECK (attempts >= 0),
    last_seen REAL NOT NULL,
    blocked_until REAL NOT NULL
)
""", """
CREATE TABLE fd_request_starts (
    key_hash TEXT NOT NULL,
    started_at REAL NOT NULL
)
""", """
CREATE INDEX fd_request_starts_key_time ON fd_request_starts(key_hash, started_at)
""")
_COLUMNS = {
    "fd_request_accounts": ("key_hash", "day", "attempts", "last_seen", "blocked_until"),
    "fd_request_starts": ("key_hash", "started_at"),
}


class FinancialDatasetsGovernor:
    """Reserve before dispatch; uncertain/failed requests are not refunded.

    One UTC-day attempt budget and a rolling minute per key in this installation.
    This is not a dollar/credit balance or coordination across separate hosts.
    Rate denial is immediate: tools must not silently retry or wait for minutes.
    """

    def __init__(self, path: Path | None = None, *, clock=time.time):
        root = Path(os.environ.get("ARKSCOPE_LOCK_DIR") or Path(__file__).resolve().parents[1] / "data" / "locks")
        self.path = Path(path) if path is not None else root / "financial_datasets_requests.db"
        self.clock = clock

    @staticmethod
    def _key(api_key):
        if not isinstance(api_key, str) or not api_key:
            raise FinancialDatasetsFailure("financial_datasets_credential_missing")
        return hashlib.sha256(api_key.encode()).hexdigest()

    def _now(self):
        now = float(self.clock())
        if not math.isfinite(now) or now < 0:
            raise FinancialDatasetsFailure("financial_datasets_governor_unavailable")
        return now

    def _connect(self):
        """Begin a transaction; initialize a new ledger, never repair a partial one."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        try:
            conn.execute("BEGIN IMMEDIATE")
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'",
            )}
            if not tables and version == 0:
                for statement in _SCHEMA:
                    conn.execute(statement)
                conn.execute("PRAGMA user_version=1")
            else:
                if version != 1 or tables != set(_COLUMNS):
                    raise FinancialDatasetsFailure("financial_datasets_governor_unavailable")
                for table, columns in _COLUMNS.items():
                    actual = tuple(row[1] for row in conn.execute("PRAGMA table_info(" + table + ")"))
                    if actual != columns:
                        raise FinancialDatasetsFailure("financial_datasets_governor_unavailable")
        except Exception:
            conn.close()
            raise
        return conn

    def reserve(self, api_key: str, policy: FinancialDatasetsPolicy) -> None:
        key = self._key(api_key)
        conn = None
        try:
            conn = self._connect()
            now = self._now()
            day = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
            row = conn.execute(
                "SELECT day, attempts, last_seen, blocked_until FROM fd_request_accounts WHERE key_hash=?", (key,),
            ).fetchone()
            used, blocked_until = 0, 0
            if row:
                if now < row[2]:
                    raise FinancialDatasetsFailure("financial_datasets_clock_regressed")
                used = row[1] if row[0] == day else 0
                blocked_until = row[3]
            if used >= policy.daily_request_limit:
                raise FinancialDatasetsFailure("financial_datasets_budget_exhausted")
            if blocked_until > now:
                raise FinancialDatasetsFailure("financial_datasets_rate_limited")
            starts = conn.execute(
                "SELECT count(*) FROM fd_request_starts WHERE key_hash=? AND started_at>?",
                (key, now - 60),
            ).fetchone()[0]
            if starts >= policy.requests_per_minute:
                raise FinancialDatasetsFailure("financial_datasets_rate_limited")
            if row:
                conn.execute("UPDATE fd_request_accounts SET day=?, attempts=?, last_seen=? WHERE key_hash=?",
                             (day, used + 1, now, key))
            else:
                conn.execute("INSERT INTO fd_request_accounts VALUES (?, ?, ?, ?, ?)", (key, day, 1, now, 0))
            conn.execute("DELETE FROM fd_request_starts WHERE key_hash=? AND started_at<=?", (key, now - 60))
            conn.execute("INSERT INTO fd_request_starts VALUES (?, ?)", (key, now))
            conn.execute("COMMIT")
        except (sqlite3.Error, OSError, OverflowError, ValueError) as exc:
            raise FinancialDatasetsFailure("financial_datasets_governor_unavailable") from exc
        finally:
            if conn is not None:
                conn.close()

    def defer(self, api_key: str, seconds: float) -> None:
        """Honor a provider Retry-After without scheduling another request."""
        key = self._key(api_key)
        if not math.isfinite(seconds) or seconds < 0:
            return
        conn = None
        try:
            conn = self._connect()
            now = self._now()
            until = now + seconds
            if not math.isfinite(until):
                raise FinancialDatasetsFailure("financial_datasets_governor_unavailable")
            conn.execute("UPDATE fd_request_accounts SET blocked_until=max(blocked_until, ?) WHERE key_hash=?",
                         (until, key))
            conn.execute("COMMIT")
        except (sqlite3.Error, OSError, OverflowError, ValueError) as exc:
            raise FinancialDatasetsFailure("financial_datasets_governor_unavailable") from exc
        finally:
            if conn is not None:
                conn.close()
