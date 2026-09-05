"""Local tracking intent, independent of mutable Alpha Picks capture rows."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from uuid import uuid4


TABLES = frozenset({"sa_tracking_memberships", "sa_tracking_bindings", "sa_tracking_events"})
_SCHEMA = (
    """CREATE TABLE sa_tracking_memberships (
        membership_id TEXT PRIMARY KEY,
        ticker TEXT NOT NULL,
        picked_date TEXT NOT NULL,
        portfolio_status TEXT NOT NULL CHECK (portfolio_status IN ('current', 'closed')),
        accepted_at TEXT,
        removed_at TEXT,
        reason TEXT NOT NULL CHECK (reason IN (
            'current_observed', 'bootstrap_accepted', 'capture_gap',
            'identity_ambiguous', 'related_security', 'user_removed',
            'user_restored', 'user_accepted', 'terminal_delisting')),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(ticker, picked_date),
        CHECK (removed_at IS NULL OR accepted_at IS NOT NULL)
    )""",
    """CREATE TABLE sa_tracking_bindings (
        lineage_id INTEGER PRIMARY KEY CHECK (lineage_id > 0),
        membership_id TEXT NOT NULL REFERENCES sa_tracking_memberships(membership_id),
        ticker TEXT NOT NULL,
        picked_date TEXT NOT NULL,
        observation_sha256 TEXT NOT NULL CHECK (length(observation_sha256) = 64),
        observed_at TEXT NOT NULL
    )""",
    """CREATE TABLE sa_tracking_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        membership_id TEXT NOT NULL REFERENCES sa_tracking_memberships(membership_id),
        action TEXT NOT NULL CHECK (action IN ('admitted', 'candidate', 'bound', 'former', 'remove', 'restore', 'accept')),
        actor TEXT NOT NULL,
        occurred_at TEXT NOT NULL,
        observation_sha256 TEXT NOT NULL CHECK (length(observation_sha256) = 64),
        receipt_json TEXT NOT NULL CHECK (json_valid(receipt_json))
    )""",
    """CREATE INDEX idx_sa_tracking_bindings_membership ON sa_tracking_bindings(membership_id)""",
    """CREATE TRIGGER sa_tracking_events_no_update BEFORE UPDATE ON sa_tracking_events
        BEGIN SELECT RAISE(ABORT, 'tracking_receipt_append_only'); END""",
    """CREATE TRIGGER sa_tracking_events_no_delete BEFORE DELETE ON sa_tracking_events
        BEGIN SELECT RAISE(ABORT, 'tracking_receipt_append_only'); END""",
)
_TICKER = re.compile(r"[A-Z][A-Z0-9]*(?:[ .-][A-Z0-9]+)*")
_SCHEMA_NAMES = ("sa_tracking_memberships", "sa_tracking_bindings", "sa_tracking_events",
                 "idx_sa_tracking_bindings_membership", "sa_tracking_events_no_update", "sa_tracking_events_no_delete")


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _instant(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("tracking_timestamp")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


def _observation(row: Mapping[str, object]) -> dict:
    try:
        lineage = row["lineage_id"]
        ticker = row["ticker"]
        picked = row["picked_date"]
        status = row["portfolio_status"]
        observed = row["observed_at"]
        if (
            type(lineage) is not int or lineage <= 0
            or not isinstance(ticker, str) or len(ticker) > 20
            or _TICKER.fullmatch(ticker) is None
            or not isinstance(picked, str) or date.fromisoformat(picked).isoformat() != picked
            or status not in {"current", "closed"} or not isinstance(observed, str)
        ):
            raise ValueError
        return {"lineage_id": lineage, "ticker": ticker, "picked_date": picked,
                "portfolio_status": status, "observed_at": _instant(observed)}
    except (KeyError, TypeError, ValueError):
        raise ValueError("tracking_observation") from None


def _identity(ticker: str, links: Mapping[str, str]) -> str:
    seen = set()
    while ticker in links:
        if ticker in seen:
            raise ValueError("tracking_identity_cycle")
        seen.add(ticker)
        ticker = links[ticker]
    return ticker


def read_sa_tracking_observations(path: str | Path) -> tuple[dict, ...]:
    with sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        rows = conn.execute(
            "SELECT lineage_id, symbol AS ticker, picked_date, portfolio_status, "
            "COALESCE(last_seen_snapshot, updated_at, fetched_at) AS observed_at "
            "FROM sa_alpha_picks WHERE is_stale=0 ORDER BY lineage_id, portfolio_status"
        ).fetchall()
    by_lineage: dict[int, dict] = {}
    for raw in rows:
        row = _observation(dict(raw))
        previous = by_lineage.get(row["lineage_id"])
        if previous and (previous["ticker"], previous["picked_date"]) != (row["ticker"], row["picked_date"]):
            raise ValueError("tracking_lineage_conflict")
        if previous is None or row["portfolio_status"] == "closed":
            by_lineage[row["lineage_id"]] = row
    return tuple(by_lineage.values())


class SaTrackingMembershipStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    @staticmethod
    def installed(conn: sqlite3.Connection) -> bool:
        present = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        owned = present & TABLES
        if owned and owned != TABLES:
            raise ValueError("tracking_schema_partial")
        if owned:
            for name, statement in zip(_SCHEMA_NAMES, _SCHEMA):
                actual = conn.execute("SELECT sql FROM sqlite_master WHERE name=?", (name,)).fetchone()
                if actual is None or " ".join(actual[0].split()).casefold() != " ".join(statement.split()).casefold():
                    raise ValueError("tracking_schema_mismatch")
        return owned == TABLES

    @staticmethod
    def install(conn: sqlite3.Connection) -> None:
        if SaTrackingMembershipStore.installed(conn):
            return
        for statement in _SCHEMA:
            conn.execute(statement)

    @contextmanager
    def _connection(self, *, write: bool = False):
        conn = sqlite3.connect(f"{self.path.resolve().as_uri()}?mode={'rw' if write else 'ro'}", uri=True, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            if not self.installed(conn):
                raise ValueError("tracking_schema_absent")
            conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield conn
            if write:
                conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _event(conn, member_id: str, action: str, actor: str, at: str, observation: object) -> None:
        cursor = conn.execute("SELECT * FROM sa_tracking_memberships WHERE membership_id=?", (member_id,))
        member = dict(zip((column[0] for column in cursor.description), cursor.fetchone()))
        conn.execute(
            "INSERT INTO sa_tracking_events(membership_id, action, actor, occurred_at, observation_sha256, receipt_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (member_id, action, actor, at, _digest(observation), _canonical({"observation": observation, "post_state": member})),
        )

    def reconcile(
        self, observations: Iterable[Mapping[str, object]], *, at: str,
        bootstrap_actor: str | None = None,
        identity_links: Mapping[str, str] | None = None,
        related_securities: Iterable[tuple[str, str]] = (),
    ) -> None:
        with self._connection(write=True) as conn:
            self.reconcile_in_transaction(conn, observations, at=at, bootstrap_actor=bootstrap_actor,
                                          identity_links=identity_links, related_securities=related_securities)

    @staticmethod
    def reconcile_in_transaction(conn, observations, *, at, bootstrap_actor=None, identity_links=None, related_securities=()):
        if not conn.in_transaction:
            raise ValueError("tracking_transaction_required")
        now = _instant(at)
        if bootstrap_actor not in {None, "attended_user"}:
            raise ValueError("tracking_bootstrap_actor")
        rows = tuple(_observation(row) for row in observations)
        if len({row["lineage_id"] for row in rows}) != len(rows):
            raise ValueError("tracking_lineage_conflict")
        links = identity_links or {}
        relations = set(related_securities)
        previous_factory = conn.row_factory
        conn.row_factory = sqlite3.Row
        try:
            for row in rows:
                binding = conn.execute("SELECT * FROM sa_tracking_bindings WHERE lineage_id=?", (row["lineage_id"],)).fetchone()
                if binding and (binding["ticker"], binding["picked_date"]) != (row["ticker"], row["picked_date"]):
                    raise ValueError("tracking_lineage_conflict")
                members = [dict(value) for value in conn.execute("SELECT * FROM sa_tracking_memberships WHERE picked_date=?", (row["picked_date"],))]
                matches = [value for value in members if _identity(value["ticker"], links) == _identity(row["ticker"], links)]
                exact = next((value for value in members if value["ticker"] == row["ticker"]), None)
                member_id = binding["membership_id"] if binding else (exact or (matches[0] if len(matches) == 1 else {})).get("membership_id")
                created = False
                if member_id is None:
                    ambiguous = len(matches) > 1
                    related = any((value["ticker"], row["ticker"]) in relations for value in members)
                    admitted = not ambiguous and not related and (bootstrap_actor is not None or row["portfolio_status"] == "current")
                    reason = ("identity_ambiguous" if ambiguous else "related_security" if related else
                              "bootstrap_accepted" if bootstrap_actor else "current_observed" if admitted else "capture_gap")
                    member_id = "sat_" + uuid4().hex
                    conn.execute(
                        "INSERT INTO sa_tracking_memberships VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?)",
                        (member_id, row["ticker"], row["picked_date"], row["portfolio_status"], now if admitted else None, reason, now, now),
                    )
                    SaTrackingMembershipStore._event(conn, member_id, "admitted" if admitted else "candidate", bootstrap_actor or "sa_observation", now, row)
                    created = True
                if binding is None:
                    conn.execute("INSERT INTO sa_tracking_bindings VALUES (?, ?, ?, ?, ?, ?)",
                                 (row["lineage_id"], member_id, row["ticker"], row["picked_date"], _digest(row), row["observed_at"]))
                    if not created:
                        SaTrackingMembershipStore._event(conn, member_id, "bound", "sa_observation", now, row)
                elif row["observed_at"] >= binding["observed_at"]:
                    conn.execute("UPDATE sa_tracking_bindings SET observation_sha256=?, observed_at=? WHERE lineage_id=?",
                                 (_digest(row), row["observed_at"], row["lineage_id"]))
                else:
                    continue
                member = conn.execute("SELECT * FROM sa_tracking_memberships WHERE membership_id=?", (member_id,)).fetchone()
                if row["portfolio_status"] == "closed" and member["portfolio_status"] != "closed":
                    conn.execute("UPDATE sa_tracking_memberships SET portfolio_status='closed', updated_at=? WHERE membership_id=?", (now, member_id))
                    SaTrackingMembershipStore._event(conn, member_id, "former", "sa_observation", now, row)
        finally:
            conn.row_factory = previous_factory

    @staticmethod
    def project(conn: sqlite3.Connection, *, identity_links: Mapping[str, str] | None = None) -> dict[str, set[str]]:
        links = identity_links or {}
        result: dict[str, set[str]] = {}
        for ticker, status in conn.execute("SELECT ticker, portfolio_status FROM sa_tracking_memberships WHERE accepted_at IS NOT NULL AND removed_at IS NULL"):
            source = "sa_alpha_picks_current" if status == "current" else "sa_alpha_picks_former"
            result.setdefault(source, set()).add(_identity(ticker, links))
        return result

    def active_sources(self, *, identity_links: Mapping[str, str] | None = None) -> dict[str, set[str]]:
        with self._connection() as conn:
            return self.project(conn, identity_links=identity_links)

    def synchronization_status(self, observations: Iterable[Mapping[str, object]]) -> str:
        rows = tuple(_observation(row) for row in observations)
        with self._connection() as conn:
            bindings = dict(conn.execute("SELECT lineage_id, observation_sha256 FROM sa_tracking_bindings"))
        if not rows and bindings:
            return "unavailable"
        return "pending" if any(bindings.get(row["lineage_id"]) != _digest(row) for row in rows) else "current"

    def list_memberships(self) -> list[dict]:
        with self._connection() as conn:
            from src.active_universe import _read_identity_links
            links = _read_identity_links(conn)
            return [
                {"membership_id": row["membership_id"], "ticker": _identity(row["ticker"], links),
                 "picked_date": row["picked_date"], "portfolio_status": row["portfolio_status"],
                 "state": "removed" if row["removed_at"] else "tracking" if row["accepted_at"] else "candidate",
                 "reason": row["reason"], "accepted_at": row["accepted_at"], "removed_at": row["removed_at"]}
                for row in conn.execute("SELECT * FROM sa_tracking_memberships ORDER BY ticker, picked_date")
            ]

    def _command(self, member_id: str, action: str, *, at: str) -> None:
        now = _instant(at)
        with self._connection(write=True) as conn:
            row = conn.execute("SELECT * FROM sa_tracking_memberships WHERE membership_id=?", (member_id,)).fetchone()
            if row is None:
                raise ValueError("tracking_membership_not_found")
            if action == "accept":
                if row["removed_at"]:
                    raise ValueError("membership_restore_required")
                if row["accepted_at"]:
                    return
                conn.execute("UPDATE sa_tracking_memberships SET accepted_at=?, reason='user_accepted', updated_at=? WHERE membership_id=?", (now, now, member_id))
            elif action == "remove":
                if row["removed_at"]:
                    return
                if not row["accepted_at"] or row["portfolio_status"] != "closed":
                    raise ValueError("former_membership_required")
                conn.execute("UPDATE sa_tracking_memberships SET removed_at=?, reason='user_removed', updated_at=? WHERE membership_id=?", (now, now, member_id))
            elif action == "restore":
                if not row["removed_at"]:
                    return
                if row["reason"] == "terminal_delisting":
                    raise ValueError("terminal_transition_reversal_required")
                conn.execute("UPDATE sa_tracking_memberships SET removed_at=NULL, reason='user_restored', updated_at=? WHERE membership_id=?", (now, member_id))
            else:
                raise ValueError("tracking_command")
            self._event(conn, member_id, action, "attended_user", now, {"command": action, "pre_state": dict(row)})

    def remove(self, member_id: str, *, at: str) -> None:
        self._command(member_id, "remove", at=at)

    def restore(self, member_id: str, *, at: str) -> None:
        self._command(member_id, "restore", at=at)

    def accept(self, member_id: str, *, at: str) -> None:
        self._command(member_id, "accept", at=at)


def terminal_tracking_memberships(conn: sqlite3.Connection, ticker: str) -> list[dict]:
    if not SaTrackingMembershipStore.installed(conn):
        return []
    links = {}
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ticker_identity_links'").fetchone():
        links = dict(conn.execute("SELECT source_ticker, successor_ticker FROM ticker_identity_links WHERE reversed_at IS NULL"))
    cursor = conn.execute("SELECT * FROM sa_tracking_memberships WHERE accepted_at IS NOT NULL AND removed_at IS NULL ORDER BY membership_id")
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row)) for row in cursor if _identity(row[names.index("ticker")], links) == ticker]


def tracking_identity_context(conn: sqlite3.Connection) -> tuple[dict[str, str], set[tuple[str, str]]]:
    from src.active_universe import _read_identity_links
    previous_factory = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        links = _read_identity_links(conn)
        relations: set[tuple[str, str]] = set()
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='security_lifecycle_assessments'").fetchone():
            relations = {
                (row[0], row[1]) for row in conn.execute(
                    "SELECT c.ticker, a.counterparty_ticker FROM security_lifecycle_assessments a "
                    "JOIN security_lifecycle_cases c ON c.case_id=a.case_id "
                    "JOIN security_lifecycle_assessment_outcomes o ON o.assessment_id=a.assessment_id "
                    "WHERE a.status='accepted' AND a.counterparty_ticker IS NOT NULL "
                    "AND o.outcome IN ('listing_ended', 'acquisition_cash', 'acquisition_stock', 'acquisition_mixed', 'acquisition_terms_unknown')"
                )
            }
        return links, relations
    finally:
        conn.row_factory = previous_factory


def reconcile_sa_tracking(*, profile_db: str | Path, sa_db: str | Path, at: str) -> bool:
    """Writer-side reconciliation. Read endpoints never admit observations."""
    profile_path = Path(profile_db)
    if not profile_path.is_file():
        return False
    with sqlite3.connect(f"{profile_path.resolve().as_uri()}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        if not SaTrackingMembershipStore.installed(conn):
            return False
    observations = read_sa_tracking_observations(sa_db)
    store = SaTrackingMembershipStore(profile_path)
    with store._connection(write=True) as conn:
        links, relations = tracking_identity_context(conn)
        store.reconcile_in_transaction(conn, observations, at=at, identity_links=links, related_securities=relations)
    return True
