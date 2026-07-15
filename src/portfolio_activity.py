"""User-owned annotations over immutable portfolio activity facts."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, get_args

from src.portfolio_observations import PortfolioObservationStore
from src.portfolio_overview import safe_portfolio_account_label
from src.portfolio_state import PortfolioStore


ActivityKind = Literal[
    "order",
    "execution",
    "unmatched",
    "manual_adjustment",
    "coverage_gap",
    "history_start",
]
ActivitySource = Literal["broker", "manual", "system"]
ActivityState = Literal[
    "realized_gain",
    "realized_loss",
    "realized_flat",
    "outcome_unknown",
    "unmatched",
    "manual_adjustment",
    "coverage_gap",
    "history_start",
]
IntentLabel = Literal[
    "profit_take",
    "stop_loss",
    "rebalance",
    "thesis_broken",
    "cash_need",
    "other",
]
INTENT_LABELS = frozenset(get_args(IntentLabel))
ANNOTATABLE_KINDS = frozenset(
    {"order", "execution", "unmatched", "manual_adjustment"}
)


@dataclass(frozen=True)
class ActivityFilters:
    date_from_et: str | None = None
    date_to_et: str | None = None
    account_id: int | None = None
    symbol: str | None = None
    source: ActivitySource | None = None
    state: ActivityState | None = None
    recent: bool = False
    limit: int = 100
    cursor: str | None = None


@dataclass(frozen=True)
class ParsedActivityId:
    target_kind: Literal["order", "execution", "unmatched", "manual_adjustment"]
    account_id: int | None
    target_ref: str


@dataclass(frozen=True)
class ActivityAnnotation:
    intent_label: IntentLabel | None
    note: str
    updated_at_utc: str


_SCHEMA = """
CREATE TABLE IF NOT EXISTS portfolio_activity_annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_kind TEXT NOT NULL CHECK(target_kind IN (
        'order','execution','unmatched','manual_adjustment'
    )),
    portfolio_account_id INTEGER NOT NULL
        REFERENCES portfolio_accounts(id) ON DELETE RESTRICT,
    target_ref TEXT NOT NULL,
    intent_label TEXT CHECK(intent_label IS NULL OR intent_label IN (
        'profit_take','stop_loss','rebalance','thesis_broken','cash_need','other'
    )),
    note TEXT NOT NULL DEFAULT '',
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    CHECK(intent_label IS NOT NULL OR length(trim(note)) > 0),
    UNIQUE(target_kind, portfolio_account_id, target_ref)
);
CREATE INDEX IF NOT EXISTS idx_portfolio_activity_annotations_account
ON portfolio_activity_annotations(portfolio_account_id, updated_at_utc DESC, id DESC);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _positive_local_id(value: str) -> int:
    if not value or not value.isascii() or not value.isdigit():
        raise ValueError("activity id must use positive local integer identities")
    normalized = int(value)
    if normalized <= 0:
        raise ValueError("activity id must use positive local integer identities")
    return normalized


def _parse_annotatable_id(activity_id: str) -> ParsedActivityId:
    if not isinstance(activity_id, str):
        raise ValueError("activity id must be text")
    parts = activity_id.split(":")
    kind = parts[0] if parts else ""
    if kind in {"order", "execution"}:
        if len(parts) != 3:
            raise ValueError("invalid activity id")
        account_id = _positive_local_id(parts[1])
        target_ref = _positive_local_id(parts[2])
        return ParsedActivityId(kind, account_id, str(target_ref))
    if kind in {"unmatched", "manual"}:
        if len(parts) != 2:
            raise ValueError("invalid activity id")
        target_ref = _positive_local_id(parts[1])
        target_kind = "manual_adjustment" if kind == "manual" else "unmatched"
        return ParsedActivityId(target_kind, None, str(target_ref))
    raise ValueError("activity id is not annotatable")


def _normalized_intent_label(intent_label: str | None) -> IntentLabel | None:
    if intent_label is None:
        return None
    if not isinstance(intent_label, str):
        raise ValueError("intent_label must be supported")
    normalized = intent_label.strip()
    if normalized not in INTENT_LABELS:
        raise ValueError("intent_label must be supported")
    return normalized  # type: ignore[return-value]


def _normalized_note(note: str) -> str:
    if not isinstance(note, str):
        raise ValueError("note must be text")
    return note.strip()


class PortfolioActivityStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.portfolio = PortfolioStore(self.path)
        self.observations = PortfolioObservationStore(self.path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError:
            pass
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def list_activity(
        self, filters: ActivityFilters, *, now_utc: str | None = None
    ) -> list[object]:
        raise NotImplementedError("activity projection is implemented in Task 2")

    def put_annotation(
        self,
        activity_id: str,
        *,
        intent_label: str | None,
        note: str,
    ) -> ActivityAnnotation:
        parsed = _parse_annotatable_id(activity_id)
        normalized_intent = _normalized_intent_label(intent_label)
        normalized_note = _normalized_note(note)
        if normalized_intent is None and not normalized_note:
            raise ValueError("intent_label or note is required")

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            account_id = self._resolve_target_account(conn, parsed)
            now = _now()
            conn.execute(
                """
                INSERT INTO portfolio_activity_annotations(
                    target_kind, portfolio_account_id, target_ref, intent_label,
                    note, created_at_utc, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(target_kind, portfolio_account_id, target_ref) DO UPDATE SET
                    intent_label=excluded.intent_label,
                    note=excluded.note,
                    updated_at_utc=excluded.updated_at_utc
                """,
                (
                    parsed.target_kind,
                    account_id,
                    parsed.target_ref,
                    normalized_intent,
                    normalized_note,
                    now,
                    now,
                ),
            )
            row = conn.execute(
                """
                SELECT intent_label, note, updated_at_utc
                FROM portfolio_activity_annotations
                WHERE target_kind=? AND portfolio_account_id=? AND target_ref=?
                """,
                (parsed.target_kind, account_id, parsed.target_ref),
            ).fetchone()
        return ActivityAnnotation(
            intent_label=row["intent_label"],
            note=row["note"],
            updated_at_utc=row["updated_at_utc"],
        )

    def delete_annotation(self, activity_id: str) -> bool:
        parsed = _parse_annotatable_id(activity_id)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            account_id = self._resolve_target_account(conn, parsed)
            deleted = conn.execute(
                """
                DELETE FROM portfolio_activity_annotations
                WHERE target_kind=? AND portfolio_account_id=? AND target_ref=?
                """,
                (parsed.target_kind, account_id, parsed.target_ref),
            ).rowcount
        return bool(deleted)

    @staticmethod
    def _resolve_target_account(
        conn: sqlite3.Connection, parsed: ParsedActivityId
    ) -> int:
        if parsed.target_kind == "order":
            row = conn.execute(
                """
                WITH ranked AS (
                    SELECT portfolio_account_id, perm_id,
                           ROW_NUMBER() OVER (
                               PARTITION BY correction_family
                               ORDER BY first_observed_run_id DESC, id DESC
                           ) AS revision_rank
                    FROM portfolio_broker_executions
                    WHERE portfolio_account_id=?
                )
                SELECT portfolio_account_id FROM ranked
                WHERE revision_rank=1 AND perm_id=? AND perm_id > 0
                LIMIT 1
                """,
                (parsed.account_id, int(parsed.target_ref)),
            ).fetchone()
        elif parsed.target_kind == "execution":
            candidate = conn.execute(
                """
                SELECT id, portfolio_account_id, correction_family
                FROM portfolio_broker_executions
                WHERE id=? AND portfolio_account_id=?
                """,
                (int(parsed.target_ref), parsed.account_id),
            ).fetchone()
            if candidate is None:
                raise ValueError("activity target does not exist")
            root = conn.execute(
                """
                SELECT MIN(id) AS id
                FROM portfolio_broker_executions
                WHERE portfolio_account_id=? AND correction_family=?
                """,
                (candidate["portfolio_account_id"], candidate["correction_family"]),
            ).fetchone()
            effective = conn.execute(
                """
                SELECT perm_id FROM portfolio_broker_executions
                WHERE portfolio_account_id=? AND correction_family=?
                ORDER BY first_observed_run_id DESC, id DESC
                LIMIT 1
                """,
                (candidate["portfolio_account_id"], candidate["correction_family"]),
            ).fetchone()
            if root is None or root["id"] != candidate["id"]:
                raise ValueError("execution target must be the correction-family root")
            if effective is not None and (effective["perm_id"] or 0) > 0:
                raise ValueError("grouped execution must use an order target")
            row = candidate
        elif parsed.target_kind == "unmatched":
            row = conn.execute(
                """
                SELECT portfolio_account_id FROM portfolio_unmatched_position_changes
                WHERE id=?
                """,
                (int(parsed.target_ref),),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT account_id AS portfolio_account_id FROM portfolio_manual_adjustments
                WHERE id=?
                """,
                (int(parsed.target_ref),),
            ).fetchone()
        if row is None:
            raise ValueError("activity target does not exist")
        return int(row["portfolio_account_id"])
