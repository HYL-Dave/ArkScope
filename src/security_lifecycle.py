"""Provider-owned security-lifecycle observations.

The market store owns source facts and classifier kinds only. Investigation
state, assessments, and profile actions live in the profile-side lifecycle
store.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
import sqlite3
from typing import Optional

from src.security_lifecycle_schema import (
    OBSERVATION_KINDS,
    assert_lifecycle_writes_available,
    create_market_schema,
    verify_market_connection,
)


_TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,19}$")
_CIK_RE = re.compile(r"^\d{10}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True, order=True)
class ObservationKind:
    event_type: str
    effective_date: Optional[str] = None


@dataclass(frozen=True)
class LifecycleObservation:
    ticker: str
    cik: Optional[str]
    issuer_name: str
    filing_date: str
    source: str
    source_ref: str
    filing_form: str
    filing_items: tuple[str, ...]
    evidence_url: str
    description: str
    observed_at: str
    kinds: tuple[ObservationKind, ...]


def _required_text(name: str, value: object, *, max_length: int) -> str:
    normalized = str(value or "").strip()
    if not normalized or len(normalized) > max_length or "\0" in normalized:
        raise ValueError(name)
    return normalized


def _ticker(value: str) -> str:
    normalized = str(value or "").strip().upper()
    if not _TICKER_RE.fullmatch(normalized):
        raise ValueError("ticker")
    return normalized


def _optional_cik(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip().zfill(10)
    if not _CIK_RE.fullmatch(normalized):
        raise ValueError("cik")
    return normalized


def _date(name: str, value: Optional[str], *, optional: bool = False) -> Optional[str]:
    if value is None and optional:
        return None
    normalized = str(value or "").strip()
    if not _DATE_RE.fullmatch(normalized):
        raise ValueError(name)
    try:
        datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(name) from exc
    return normalized


def _timestamp(value: str) -> str:
    normalized = _required_text("observed_at", value, max_length=40)
    parseable = normalized[:-1] + "+00:00" if normalized.endswith("Z") else normalized
    try:
        parsed = datetime.fromisoformat(parseable)
    except ValueError as exc:
        raise ValueError("observed_at") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("observed_at")
    return normalized


def _https_url(value: str) -> str:
    normalized = _required_text("evidence_url", value, max_length=1000)
    if not normalized.startswith("https://"):
        raise ValueError("evidence_url")
    return normalized


def _validated_observation(value: LifecycleObservation) -> dict:
    kinds: dict[str, Optional[str]] = {}
    for kind in value.kinds:
        if kind.event_type not in OBSERVATION_KINDS:
            raise ValueError("event_type")
        effective_date = _date(
            "effective_date", kind.effective_date, optional=True
        )
        if kind.event_type in kinds:
            raise ValueError("duplicate_event_type")
        kinds[kind.event_type] = effective_date
    if not kinds:
        raise ValueError("kinds")
    filing_items = tuple(
        sorted(
            {
                _required_text("filing_item", item, max_length=20)
                for item in value.filing_items
            }
        )
    )
    return {
        "ticker": _ticker(value.ticker),
        "cik": _optional_cik(value.cik),
        "issuer_name": _required_text(
            "issuer_name", value.issuer_name, max_length=240
        ),
        "filing_date": _date("filing_date", value.filing_date),
        "source": _required_text("source", value.source, max_length=64),
        "source_ref": _required_text(
            "source_ref", value.source_ref, max_length=160
        ),
        "filing_form": _required_text(
            "filing_form", value.filing_form, max_length=30
        ),
        "filing_items_json": json.dumps(filing_items, separators=(",", ":")),
        "evidence_url": _https_url(value.evidence_url),
        "description": str(value.description or "").strip()[:1000],
        "observed_at": _timestamp(value.observed_at),
        "kinds": tuple(sorted(kinds.items())),
    }


def _component_tables(conn: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name LIKE 'security_lifecycle_%'"
        )
    }


class SecurityLifecycleStore:
    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        migration_conn: sqlite3.Connection | None = None,
    ):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        if not _component_tables(self.conn):
            create_market_schema(self.conn)
        else:
            verify_market_connection(self.conn)
        self._migration_conn = migration_conn

    def upsert_observation(self, value: LifecycleObservation) -> int:
        assert_lifecycle_writes_available(self._migration_conn)
        item = _validated_observation(value)
        existing = self.conn.execute(
            "SELECT id FROM security_lifecycle_observations "
            "WHERE source=? AND source_ref=? AND ticker=?",
            (item["source"], item["source_ref"], item["ticker"]),
        ).fetchone()
        with self.conn:
            self.conn.execute(
                "INSERT INTO security_lifecycle_observations "
                "(ticker,cik,issuer_name,filing_date,source,source_ref,filing_form,"
                "filing_items_json,evidence_url,description,first_observed_at,last_observed_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(source,source_ref,ticker) DO UPDATE SET "
                "cik=excluded.cik, issuer_name=excluded.issuer_name, "
                "filing_date=excluded.filing_date, filing_form=excluded.filing_form, "
                "filing_items_json=excluded.filing_items_json, "
                "evidence_url=excluded.evidence_url, description=excluded.description, "
                "last_observed_at=excluded.last_observed_at",
                (
                    item["ticker"],
                    item["cik"],
                    item["issuer_name"],
                    item["filing_date"],
                    item["source"],
                    item["source_ref"],
                    item["filing_form"],
                    item["filing_items_json"],
                    item["evidence_url"],
                    item["description"],
                    item["observed_at"],
                    item["observed_at"],
                ),
            )
            row = self.conn.execute(
                "SELECT id FROM security_lifecycle_observations "
                "WHERE source=? AND source_ref=? AND ticker=?",
                (item["source"], item["source_ref"], item["ticker"]),
            ).fetchone()
            observation_id = int(row["id"])
            self.conn.execute(
                "DELETE FROM security_lifecycle_observation_kinds "
                "WHERE observation_id=?",
                (observation_id,),
            )
            self.conn.executemany(
                "INSERT INTO security_lifecycle_observation_kinds "
                "(observation_id,event_type,effective_date) VALUES (?,?,?)",
                [
                    (observation_id, event_type, effective_date)
                    for event_type, effective_date in item["kinds"]
                ],
            )
        return observation_id if existing is None else int(existing["id"])

    def get_observation(self, source: str, source_ref: str, ticker: str) -> dict:
        row = self.conn.execute(
            "SELECT * FROM security_lifecycle_observations "
            "WHERE source=? AND source_ref=? AND ticker=?",
            (source, source_ref, ticker),
        ).fetchone()
        if row is None:
            raise KeyError("observation_not_found")
        return _row_to_observation(self.conn, row)

    def list_observations(self, *, limit: int = 1000) -> list[dict]:
        bounded = min(max(int(limit), 1), 1000)
        rows = self.conn.execute(
            "SELECT * FROM security_lifecycle_observations "
            "ORDER BY filing_date DESC, source, source_ref, ticker LIMIT ?",
            (bounded,),
        ).fetchall()
        return [_row_to_observation(self.conn, row) for row in rows]


def _row_to_observation(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    kinds = conn.execute(
        "SELECT event_type,effective_date "
        "FROM security_lifecycle_observation_kinds "
        "WHERE observation_id=? ORDER BY event_type",
        (int(row["id"]),),
    ).fetchall()
    item = dict(row)
    item["filing_items"] = list(json.loads(item.pop("filing_items_json")))
    item["kinds"] = [
        {"event_type": str(kind["event_type"]), "effective_date": kind["effective_date"]}
        for kind in kinds
    ]
    return item


def read_market_observations(db_path: str, *, limit: int = 1000) -> list[dict]:
    """Read observation facts without creating or repairing a database."""
    path = Path(db_path)
    if not path.is_file():
        return []
    conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        verify_market_connection(conn)
        store = object.__new__(SecurityLifecycleStore)
        store.conn = conn
        store._migration_conn = None
        return store.list_observations(limit=limit)
    finally:
        conn.close()


def read_security_lifecycle(db_path: str, *, limit: int = 200) -> dict:
    """Temporary read bridge until Task 3 replaces the old route surface."""
    observations = read_market_observations(db_path, limit=limit)
    return {
        "events": observations,
        "relationships": [],
        "summary": {"event_count": len(observations)},
    }
