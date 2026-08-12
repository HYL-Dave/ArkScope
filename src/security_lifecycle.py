"""Evidence-first security lifecycle and corporate-action storage.

These tables record provider observations. They deliberately do not mutate the
active universe: a missing quote, an SEC Item 3.01 filing, or a Form 25 notice is
review material rather than an instruction to hide a ticker.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
import sqlite3
from pathlib import Path
from typing import Optional


EVENT_TYPES = frozenset(
    {
        "merger_agreement",
        "merger_proxy",
        "acquisition_completed",
        "listing_status_review",
        "listing_removal_notice",
    }
)
LIFECYCLE_STATES = frozenset(
    {
        "review_required",
        "pending_delisting",
        "inactive_confirmed",
        "renamed_or_transferred",
    }
)
ACTION_TYPES = frozenset({"acquisition", "merger"})
RELATIONSHIP_STATUSES = frozenset({"candidate", "confirmed", "rejected"})

_TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,19}$")
_CIK_RE = re.compile(r"^\d{10}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS security_lifecycle_observations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker              TEXT NOT NULL,
    cik                 TEXT,
    issuer_name         TEXT NOT NULL,
    event_type          TEXT NOT NULL CHECK (event_type IN (
                            'merger_agreement', 'merger_proxy',
                            'acquisition_completed', 'listing_status_review',
                            'listing_removal_notice')),
    lifecycle_state     TEXT NOT NULL CHECK (lifecycle_state IN (
                            'review_required', 'pending_delisting',
                            'inactive_confirmed', 'renamed_or_transferred')),
    filing_date         TEXT NOT NULL,
    effective_date      TEXT,
    source              TEXT NOT NULL,
    source_ref          TEXT NOT NULL,
    filing_form         TEXT NOT NULL,
    filing_items_json   TEXT NOT NULL,
    evidence_url        TEXT NOT NULL,
    description         TEXT NOT NULL,
    first_observed_at   TEXT NOT NULL,
    last_observed_at    TEXT NOT NULL,
    UNIQUE(source, source_ref, ticker, event_type)
);
CREATE INDEX IF NOT EXISTS idx_security_lifecycle_ticker_date
    ON security_lifecycle_observations(ticker, filing_date DESC);
CREATE INDEX IF NOT EXISTS idx_security_lifecycle_state_date
    ON security_lifecycle_observations(lifecycle_state, filing_date DESC);

CREATE TABLE IF NOT EXISTS corporate_action_relationships (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    action_type         TEXT NOT NULL CHECK (action_type IN ('acquisition', 'merger')),
    target_ticker       TEXT,
    target_cik          TEXT,
    target_name         TEXT NOT NULL,
    acquirer_ticker     TEXT,
    acquirer_cik        TEXT,
    acquirer_name       TEXT NOT NULL,
    status              TEXT NOT NULL CHECK (status IN (
                            'candidate', 'confirmed', 'rejected')),
    effective_date      TEXT,
    source              TEXT NOT NULL,
    source_ref          TEXT NOT NULL,
    evidence_url        TEXT NOT NULL,
    evidence_excerpt    TEXT NOT NULL,
    first_observed_at   TEXT NOT NULL,
    last_observed_at    TEXT NOT NULL,
    reviewed_at         TEXT,
    UNIQUE(source, source_ref, target_name, acquirer_name, action_type)
);
CREATE INDEX IF NOT EXISTS idx_corporate_action_target
    ON corporate_action_relationships(target_ticker, effective_date DESC);
CREATE INDEX IF NOT EXISTS idx_corporate_action_status
    ON corporate_action_relationships(status, effective_date DESC);
"""


@dataclass(frozen=True)
class LifecycleObservation:
    ticker: str
    cik: Optional[str]
    issuer_name: str
    event_type: str
    lifecycle_state: str
    filing_date: str
    effective_date: Optional[str]
    source: str
    source_ref: str
    filing_form: str
    filing_items: tuple[str, ...]
    evidence_url: str
    description: str
    observed_at: str


@dataclass(frozen=True)
class CorporateRelationship:
    action_type: str
    target_ticker: Optional[str]
    target_cik: Optional[str]
    target_name: str
    acquirer_ticker: Optional[str]
    acquirer_cik: Optional[str]
    acquirer_name: str
    status: str
    effective_date: Optional[str]
    source: str
    source_ref: str
    evidence_url: str
    evidence_excerpt: str
    observed_at: str


def _required_text(name: str, value: object, *, max_length: int) -> str:
    normalized = str(value or "").strip()
    if not normalized or len(normalized) > max_length:
        raise ValueError(name)
    return normalized


def _optional_ticker(name: str, value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip().upper()
    if not _TICKER_RE.fullmatch(normalized):
        raise ValueError(name)
    return normalized


def _optional_cik(name: str, value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip().zfill(10)
    if not _CIK_RE.fullmatch(normalized):
        raise ValueError(name)
    return normalized


def _optional_date(name: str, value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip()
    if not _DATE_RE.fullmatch(normalized):
        raise ValueError(name)
    return normalized


def _required_date(name: str, value: str) -> str:
    normalized = _optional_date(name, value)
    if normalized is None:
        raise ValueError(name)
    return normalized


def _observed_at(value: str) -> str:
    normalized = _required_text("observed_at", value, max_length=40)
    if not (normalized.endswith("Z") or normalized.endswith("+00:00")):
        raise ValueError("observed_at")
    return normalized


def _https_url(value: str) -> str:
    normalized = _required_text("evidence_url", value, max_length=1000)
    if not normalized.startswith("https://"):
        raise ValueError("evidence_url")
    return normalized


class SecurityLifecycleStore:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)

    def upsert_observation(self, value: LifecycleObservation) -> bool:
        ticker = _optional_ticker("ticker", value.ticker)
        if ticker is None:
            raise ValueError("ticker")
        if value.event_type not in EVENT_TYPES:
            raise ValueError("event_type")
        if value.lifecycle_state not in LIFECYCLE_STATES:
            raise ValueError("lifecycle_state")
        filing_items = tuple(
            sorted({_required_text("filing_item", item, max_length=20) for item in value.filing_items})
        )
        source = _required_text("source", value.source, max_length=64)
        source_ref = _required_text("source_ref", value.source_ref, max_length=160)
        existing = self.conn.execute(
            "SELECT id FROM security_lifecycle_observations "
            "WHERE source=? AND source_ref=? AND ticker=? AND event_type=?",
            (source, source_ref, ticker, value.event_type),
        ).fetchone()
        observed_at = _observed_at(value.observed_at)
        params = (
            ticker,
            _optional_cik("cik", value.cik),
            _required_text("issuer_name", value.issuer_name, max_length=240),
            value.event_type,
            value.lifecycle_state,
            _required_date("filing_date", value.filing_date),
            _optional_date("effective_date", value.effective_date),
            source,
            source_ref,
            _required_text("filing_form", value.filing_form, max_length=30),
            json.dumps(filing_items, separators=(",", ":")),
            _https_url(value.evidence_url),
            str(value.description or "").strip()[:1000],
            observed_at,
            observed_at,
        )
        with self.conn:
            self.conn.execute(
                "INSERT INTO security_lifecycle_observations "
                "(ticker,cik,issuer_name,event_type,lifecycle_state,filing_date,"
                "effective_date,source,source_ref,filing_form,filing_items_json,"
                "evidence_url,description,first_observed_at,last_observed_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(source,source_ref,ticker,event_type) DO UPDATE SET "
                "cik=excluded.cik, issuer_name=excluded.issuer_name, "
                "lifecycle_state=excluded.lifecycle_state, filing_date=excluded.filing_date, "
                "effective_date=excluded.effective_date, filing_form=excluded.filing_form, "
                "filing_items_json=excluded.filing_items_json, "
                "evidence_url=excluded.evidence_url, description=excluded.description, "
                "last_observed_at=excluded.last_observed_at",
                params,
            )
        return existing is None

    def upsert_relationship(self, value: CorporateRelationship) -> int:
        if value.action_type not in ACTION_TYPES:
            raise ValueError("action_type")
        if value.status not in RELATIONSHIP_STATUSES:
            raise ValueError("status")
        target_name = _required_text("target_name", value.target_name, max_length=240)
        acquirer_name = _required_text("acquirer_name", value.acquirer_name, max_length=240)
        source = _required_text("source", value.source, max_length=64)
        source_ref = _required_text("source_ref", value.source_ref, max_length=160)
        existing = self.conn.execute(
            "SELECT id FROM corporate_action_relationships "
            "WHERE source=? AND source_ref=? AND target_name=? AND acquirer_name=? "
            "AND action_type=?",
            (source, source_ref, target_name, acquirer_name, value.action_type),
        ).fetchone()
        observed_at = _observed_at(value.observed_at)
        params = (
            value.action_type,
            _optional_ticker("target_ticker", value.target_ticker),
            _optional_cik("target_cik", value.target_cik),
            target_name,
            _optional_ticker("acquirer_ticker", value.acquirer_ticker),
            _optional_cik("acquirer_cik", value.acquirer_cik),
            acquirer_name,
            value.status,
            _optional_date("effective_date", value.effective_date),
            source,
            source_ref,
            _https_url(value.evidence_url),
            _required_text("evidence_excerpt", value.evidence_excerpt, max_length=1000),
            observed_at,
            observed_at,
        )
        with self.conn:
            self.conn.execute(
                "INSERT INTO corporate_action_relationships "
                "(action_type,target_ticker,target_cik,target_name,acquirer_ticker,"
                "acquirer_cik,acquirer_name,status,effective_date,source,source_ref,"
                "evidence_url,evidence_excerpt,first_observed_at,last_observed_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(source,source_ref,target_name,acquirer_name,action_type) "
                "DO UPDATE SET target_ticker=excluded.target_ticker, "
                "target_cik=excluded.target_cik, acquirer_ticker=excluded.acquirer_ticker, "
                "acquirer_cik=excluded.acquirer_cik, effective_date=excluded.effective_date, "
                "evidence_url=excluded.evidence_url, "
                "evidence_excerpt=excluded.evidence_excerpt, "
                "last_observed_at=excluded.last_observed_at, "
                "status=CASE WHEN corporate_action_relationships.status='candidate' "
                "THEN excluded.status ELSE corporate_action_relationships.status END",
                params,
            )
        if existing is not None:
            return int(existing["id"])
        row = self.conn.execute("SELECT last_insert_rowid()").fetchone()
        return int(row[0])

    def review_relationship(self, relationship_id: int, *, status: str, reviewed_at: str) -> None:
        if status not in {"confirmed", "rejected"}:
            raise ValueError("status")
        with self.conn:
            cursor = self.conn.execute(
                "UPDATE corporate_action_relationships SET status=?, reviewed_at=? WHERE id=?",
                (status, _observed_at(reviewed_at), int(relationship_id)),
            )
        if cursor.rowcount != 1:
            raise KeyError("relationship_not_found")


def _empty_snapshot() -> dict:
    return {
        "events": [],
        "relationships": [],
        "summary": {
            "event_count": 0,
            "review_required": 0,
            "pending_delisting": 0,
            "relationship_candidates": 0,
        },
    }


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return bool(
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
    )


def read_security_lifecycle(db_path: str, *, limit: int = 200) -> dict:
    """Read the local projection without creating a DB, directory, or schema."""
    path = Path(db_path)
    if not path.is_file():
        return _empty_snapshot()
    try:
        conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return _empty_snapshot()
    conn.row_factory = sqlite3.Row
    try:
        if not _table_exists(conn, "security_lifecycle_observations"):
            return _empty_snapshot()
        bounded_limit = min(max(int(limit), 1), 1000)
        event_rows = conn.execute(
            "SELECT * FROM security_lifecycle_observations "
            "ORDER BY filing_date DESC, id DESC LIMIT ?",
            (bounded_limit,),
        ).fetchall()
        relation_rows = []
        if _table_exists(conn, "corporate_action_relationships"):
            relation_rows = conn.execute(
                "SELECT * FROM corporate_action_relationships "
                "ORDER BY COALESCE(effective_date, first_observed_at) DESC, id DESC LIMIT ?",
                (bounded_limit,),
            ).fetchall()
            relationship_candidates = int(
                conn.execute(
                    "SELECT COUNT(*) FROM corporate_action_relationships WHERE status='candidate'"
                ).fetchone()[0]
            )
        else:
            relationship_candidates = 0
        summary_row = conn.execute(
            "SELECT COUNT(*) AS event_count, "
            "SUM(CASE WHEN lifecycle_state='review_required' THEN 1 ELSE 0 END) "
            "AS review_required, "
            "SUM(CASE WHEN lifecycle_state='pending_delisting' THEN 1 ELSE 0 END) "
            "AS pending_delisting FROM security_lifecycle_observations"
        ).fetchone()
        events = []
        for row in event_rows:
            item = dict(row)
            item["filing_items"] = list(json.loads(item.pop("filing_items_json")))
            events.append(item)
        return {
            "events": events,
            "relationships": [dict(row) for row in relation_rows],
            "summary": {
                "event_count": int(summary_row["event_count"] or 0),
                "review_required": int(summary_row["review_required"] or 0),
                "pending_delisting": int(summary_row["pending_delisting"] or 0),
                "relationship_candidates": relationship_candidates,
            },
        }
    finally:
        conn.close()
