"""Append-only broker observations for portfolio capture."""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from src.portfolio_capture_types import (
    AccountSnapshotObservation,
    BrokerCaptureResult,
    CaptureCommitResult,
    CaptureRun,
    CaptureRunNotReviewable,
    CaptureSettings,
    CaptureTerminalState,
    CaptureTrigger,
    CommissionObservation,
    ExecutionObservation,
    PositionObservation,
    commission_content_hash,
    correction_family,
    finite_or_none,
)
from src.portfolio_state import PortfolioStore, portfolio_account_hash

if TYPE_CHECKING:
    from src.portfolio_ibkr import BrokerSnapshot


_LEG_STATES = frozenset({"not_attempted", "complete", "partial", "failed"})
_TRIGGERS = frozenset({"startup", "scheduled", "manual"})
_TERMINAL_STATES = frozenset(
    {"succeeded", "partial", "failed", "blocked", "interrupted"}
)
_ACCOUNT_NUMERIC_FIELDS = tuple(
    field.name
    for field in fields(AccountSnapshotObservation)
    if field.name
    not in {"broker_account_id", "as_of_utc", "base_currency"}
)
_POSITION_NULLABLE_NUMERIC_FIELDS = (
    "avg_cost",
    "market_value",
    "unrealized_pnl",
    "realized_pnl",
    "market_value_base",
    "unrealized_pnl_base",
)
_EXECUTION_COMPARISON_COLUMNS = (
    "origin",
    "exec_id",
    "execution_time_utc",
    "broker_con_id",
    "symbol",
    "asset_class",
    "currency",
    "exchange",
    "side",
    "quantity",
    "price",
    "order_id",
    "perm_id",
    "client_id",
    "order_ref",
    "liquidation",
    "cumulative_quantity",
    "average_price",
    "correction_family",
)
_EASTERN = ZoneInfo("America/New_York")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS portfolio_capture_settings (
    id INTEGER PRIMARY KEY CHECK(id=1),
    enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
    interval_minutes INTEGER NOT NULL CHECK(interval_minutes BETWEEN 5 AND 1440),
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolio_capture_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trigger TEXT NOT NULL CHECK(trigger IN ('startup','scheduled','manual')),
    state TEXT NOT NULL CHECK(state IN ('running','succeeded','partial','failed','blocked','interrupted')),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    account_leg_state TEXT NOT NULL CHECK(account_leg_state IN ('not_attempted','complete','partial','failed')),
    execution_leg_state TEXT NOT NULL CHECK(execution_leg_state IN ('not_attempted','complete','partial','failed')),
    position_leg_state TEXT NOT NULL CHECK(position_leg_state IN ('not_attempted','complete','partial','failed')),
    discovered_account_count INTEGER NOT NULL DEFAULT 0 CHECK(discovered_account_count >= 0),
    new_account_count INTEGER NOT NULL DEFAULT 0 CHECK(new_account_count >= 0),
    archived_activity_count INTEGER NOT NULL DEFAULT 0 CHECK(archived_activity_count >= 0),
    inserted_execution_count INTEGER NOT NULL DEFAULT 0 CHECK(inserted_execution_count >= 0),
    inserted_commission_count INTEGER NOT NULL DEFAULT 0 CHECK(inserted_commission_count >= 0),
    unmatched_count INTEGER NOT NULL DEFAULT 0 CHECK(unmatched_count >= 0),
    data_conflict_count INTEGER NOT NULL DEFAULT 0 CHECK(data_conflict_count >= 0),
    error_code TEXT,
    error_detail TEXT,
    client_id_domain TEXT NOT NULL CHECK(client_id_domain='portfolio_capture'),
    effective_client_id INTEGER NOT NULL,
    coverage_notes_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS portfolio_capture_run_accounts (
    capture_run_id INTEGER NOT NULL REFERENCES portfolio_capture_runs(id) ON DELETE RESTRICT,
    portfolio_account_id INTEGER NOT NULL REFERENCES portfolio_accounts(id) ON DELETE RESTRICT,
    is_new INTEGER NOT NULL CHECK(is_new IN (0,1)),
    archived_at_capture TEXT,
    PRIMARY KEY (capture_run_id, portfolio_account_id)
);

CREATE TABLE IF NOT EXISTS portfolio_account_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    capture_run_id INTEGER NOT NULL REFERENCES portfolio_capture_runs(id) ON DELETE RESTRICT,
    portfolio_account_id INTEGER NOT NULL REFERENCES portfolio_accounts(id) ON DELETE RESTRICT,
    as_of_utc TEXT NOT NULL,
    base_currency TEXT,
    net_liquidation REAL,
    total_cash_value REAL,
    settled_cash REAL,
    gross_position_value REAL,
    buying_power REAL,
    available_funds REAL,
    initial_margin_requirement REAL,
    maintenance_margin_requirement REAL,
    daily_realized_pnl REAL,
    daily_unrealized_pnl REAL,
    source TEXT NOT NULL CHECK(source='ibkr_gateway'),
    as_of_kind TEXT NOT NULL CHECK(as_of_kind='capture_completed'),
    UNIQUE (capture_run_id, portfolio_account_id)
);

CREATE TABLE IF NOT EXISTS portfolio_broker_position_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    capture_run_id INTEGER NOT NULL REFERENCES portfolio_capture_runs(id) ON DELETE RESTRICT,
    portfolio_account_id INTEGER NOT NULL REFERENCES portfolio_accounts(id) ON DELETE RESTRICT,
    broker TEXT NOT NULL CHECK(broker='ibkr'),
    broker_con_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    quantity REAL NOT NULL,
    avg_cost REAL,
    market_value REAL,
    unrealized_pnl REAL,
    realized_pnl REAL,
    market_value_base REAL,
    unrealized_pnl_base REAL,
    currency TEXT NOT NULL,
    base_currency TEXT,
    exchange TEXT,
    local_symbol TEXT,
    multiplier TEXT,
    UNIQUE (capture_run_id, portfolio_account_id, broker_con_id)
);

CREATE TABLE IF NOT EXISTS portfolio_broker_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    broker TEXT NOT NULL CHECK(broker='ibkr'),
    origin TEXT NOT NULL CHECK(origin IN ('gateway','flex')),
    portfolio_account_id INTEGER NOT NULL REFERENCES portfolio_accounts(id) ON DELETE RESTRICT,
    first_observed_run_id INTEGER NOT NULL REFERENCES portfolio_capture_runs(id) ON DELETE RESTRICT,
    exec_id TEXT NOT NULL,
    first_observed_at_utc TEXT NOT NULL,
    execution_time_utc TEXT NOT NULL,
    broker_con_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    currency TEXT NOT NULL,
    exchange TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    order_id INTEGER,
    perm_id INTEGER,
    client_id INTEGER,
    order_ref TEXT,
    liquidation INTEGER,
    cumulative_quantity REAL,
    average_price REAL,
    correction_family TEXT NOT NULL,
    corrects_exec_id TEXT,
    UNIQUE (broker, portfolio_account_id, exec_id)
);

CREATE TABLE IF NOT EXISTS portfolio_broker_commission_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    broker TEXT NOT NULL CHECK(broker='ibkr'),
    portfolio_account_id INTEGER NOT NULL REFERENCES portfolio_accounts(id) ON DELETE RESTRICT,
    first_observed_run_id INTEGER NOT NULL REFERENCES portfolio_capture_runs(id) ON DELETE RESTRICT,
    exec_id TEXT NOT NULL,
    first_observed_at_utc TEXT NOT NULL,
    commission REAL,
    currency TEXT,
    realized_pnl REAL,
    yield_value REAL,
    yield_redemption_date INTEGER,
    content_hash TEXT NOT NULL,
    FOREIGN KEY (broker, portfolio_account_id, exec_id)
        REFERENCES portfolio_broker_executions(broker, portfolio_account_id, exec_id)
        ON DELETE RESTRICT,
    UNIQUE (broker, portfolio_account_id, exec_id, content_hash)
);

CREATE TABLE IF NOT EXISTS portfolio_unmatched_position_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_account_id INTEGER NOT NULL REFERENCES portfolio_accounts(id) ON DELETE RESTRICT,
    from_run_id INTEGER NOT NULL REFERENCES portfolio_capture_runs(id) ON DELETE RESTRICT,
    to_run_id INTEGER NOT NULL REFERENCES portfolio_capture_runs(id) ON DELETE RESTRICT,
    broker_con_id TEXT NOT NULL,
    from_as_of_utc TEXT NOT NULL,
    to_as_of_utc TEXT NOT NULL,
    before_quantity REAL NOT NULL,
    after_quantity REAL NOT NULL,
    expected_quantity REAL NOT NULL,
    residual_quantity REAL NOT NULL,
    execution_coverage TEXT NOT NULL CHECK(execution_coverage IN ('complete','incomplete','gap')),
    source TEXT NOT NULL CHECK(source='ibkr'),
    reason_code TEXT NOT NULL,
    symbol TEXT,
    asset_class TEXT,
    currency TEXT,
    UNIQUE (portfolio_account_id, broker_con_id, from_run_id, to_run_id)
);

CREATE INDEX IF NOT EXISTS idx_portfolio_capture_runs_recency
ON portfolio_capture_runs(started_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_portfolio_account_snapshots_recency
ON portfolio_account_snapshots(portfolio_account_id, as_of_utc DESC, capture_run_id DESC);
CREATE INDEX IF NOT EXISTS idx_portfolio_positions_account_run
ON portfolio_broker_position_observations(portfolio_account_id, capture_run_id, broker_con_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_executions_correction_projection
ON portfolio_broker_executions(portfolio_account_id, broker_con_id, correction_family, first_observed_run_id, id);
CREATE INDEX IF NOT EXISTS idx_portfolio_commissions_execution
ON portfolio_broker_commission_reports(broker, portfolio_account_id, exec_id, id);
CREATE INDEX IF NOT EXISTS idx_portfolio_unmatched_account_time
ON portfolio_unmatched_position_changes(portfolio_account_id, to_as_of_utc DESC, id DESC);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _required(value: Any, field: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field} is required")
    return normalized


def _currency(value: str | None) -> str | None:
    normalized = (value or "").strip().upper()
    return normalized or None


def _timestamp(value: str, field: str) -> str:
    normalized = _required(value, field)
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from None
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip() or None


def _integer_or_none(value: Any, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    try:
        normalized = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be an integer") from None
    if not math.isfinite(normalized) or not normalized.is_integer():
        raise ValueError(f"{field} must be an integer")
    return int(normalized)


class PortfolioObservationStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.portfolio = PortfolioStore(self.path)
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

    def get_stored_settings(self) -> CaptureSettings | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT enabled, interval_minutes, updated_at "
                "FROM portfolio_capture_settings WHERE id=1"
            ).fetchone()
        if row is None:
            return None
        return CaptureSettings(bool(row["enabled"]), row["interval_minutes"], row["updated_at"])

    def set_settings(self, *, enabled: bool, interval_minutes: int) -> CaptureSettings:
        if isinstance(interval_minutes, bool) or not isinstance(interval_minutes, int):
            raise ValueError("interval_minutes must be an integer from 5 to 1440")
        if not 5 <= interval_minutes <= 1440:
            raise ValueError("interval_minutes must be from 5 to 1440")
        updated_at = _now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO portfolio_capture_settings(id, enabled, interval_minutes, updated_at)
                VALUES (1, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    enabled=excluded.enabled,
                    interval_minutes=excluded.interval_minutes,
                    updated_at=excluded.updated_at
                """,
                (int(bool(enabled)), interval_minutes, updated_at),
            )
        return CaptureSettings(bool(enabled), interval_minutes, updated_at)

    def create_run(
        self, *, trigger: CaptureTrigger, effective_client_id: int
    ) -> CaptureRun:
        if trigger not in _TRIGGERS:
            raise ValueError(f"unsupported capture trigger: {trigger}")
        effective_client_id = _integer_or_none(
            effective_client_id, "effective_client_id"
        )
        if effective_client_id is None:
            raise ValueError("effective_client_id must be an integer")
        started_at = _now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO portfolio_capture_runs(
                    trigger, state, started_at,
                    account_leg_state, execution_leg_state, position_leg_state,
                    client_id_domain, effective_client_id
                ) VALUES (?, 'running', ?, 'not_attempted', 'not_attempted',
                          'not_attempted', 'portfolio_capture', ?)
                """,
                (trigger, started_at, effective_client_id),
            )
            row = conn.execute(
                "SELECT * FROM portfolio_capture_runs WHERE id=?",
                (cursor.lastrowid,),
            ).fetchone()
        return self._run_from_row(row)

    def record_blocked(
        self,
        *,
        trigger: CaptureTrigger,
        effective_client_id: int,
        error_code: str,
        error_detail: str | None = None,
    ) -> CaptureRun:
        run = self.create_run(trigger=trigger, effective_client_id=effective_client_id)
        return self.finish_run(
            run.id,
            state="blocked",
            error_code=error_code,
            error_detail=error_detail,
        )

    def commit_capture(
        self, run_id: int, result: BrokerCaptureResult
    ) -> CaptureCommitResult:
        normalized = self._validate_capture(result)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            run = conn.execute(
                "SELECT * FROM portfolio_capture_runs WHERE id=?", (run_id,)
            ).fetchone()
            if run is None:
                raise KeyError(f"capture run not found: {run_id}")
            if run["state"] != "running":
                raise ValueError(f"capture run is not running: {run_id}")

            account_ids: dict[str, int] = {}
            discovered_ids: list[int] = []
            new_ids: list[int] = []
            archived_ids: list[int] = []
            for account in normalized["accounts"]:
                raw_id = account["broker_account_id"]
                account_hash = portfolio_account_hash(raw_id)
                row = conn.execute(
                    """
                    SELECT * FROM portfolio_accounts
                    WHERE broker='ibkr' AND broker_account_id_hash=?
                    """,
                    (account_hash,),
                ).fetchone()
                is_new = row is None
                if row is None:
                    now = _now()
                    cursor = conn.execute(
                        """
                        INSERT INTO portfolio_accounts(
                            label, broker, broker_account_id, broker_account_id_hash,
                            sync_mode, base_currency, include_in_total,
                            created_at, updated_at
                        ) VALUES (?, 'ibkr', ?, ?, 'ibkr_review', ?, 1, ?, ?)
                        """,
                        (
                            f"IBKR · {account_hash[:8]}",
                            raw_id,
                            account_hash,
                            account["base_currency"],
                            now,
                            now,
                        ),
                    )
                    row = conn.execute(
                        "SELECT * FROM portfolio_accounts WHERE id=?",
                        (cursor.lastrowid,),
                    ).fetchone()
                local_id = int(row["id"])
                account_ids[raw_id] = local_id
                discovered_ids.append(local_id)
                inserted_mapping = conn.execute(
                    """
                    INSERT OR IGNORE INTO portfolio_capture_run_accounts(
                        capture_run_id, portfolio_account_id, is_new, archived_at_capture
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (run_id, local_id, int(is_new), row["archived_at"]),
                ).rowcount
                if inserted_mapping and is_new:
                    new_ids.append(local_id)
                if inserted_mapping and row["archived_at"] is not None:
                    archived_ids.append(local_id)

            for snapshot in normalized["snapshots"]:
                self._insert_snapshot(conn, run_id, account_ids, snapshot)
            for position in normalized["positions"]:
                self._insert_position(conn, run_id, account_ids, position)

            inserted_executions = 0
            conflicts = 0
            for observed in normalized["executions"]:
                inserted, conflict = self._insert_execution(
                    conn, run_id, normalized["finished_at_utc"], account_ids, observed
                )
                inserted_executions += inserted
                conflicts += conflict

            inserted_commissions = 0
            for report in normalized["commissions"]:
                inserted_commissions += self._insert_commission(
                    conn, run_id, normalized["finished_at_utc"], account_ids, report
                )

            conn.execute(
                """
                UPDATE portfolio_capture_runs SET
                    finished_at=COALESCE(finished_at, ?),
                    account_leg_state=?, execution_leg_state=?, position_leg_state=?,
                    discovered_account_count=?,
                    new_account_count=new_account_count+?,
                    archived_activity_count=archived_activity_count+?,
                    inserted_execution_count=inserted_execution_count+?,
                    inserted_commission_count=inserted_commission_count+?,
                    data_conflict_count=data_conflict_count+?
                WHERE id=?
                """,
                (
                    normalized["finished_at_utc"],
                    normalized["account_leg_state"],
                    normalized["execution_leg_state"],
                    normalized["position_leg_state"],
                    len(discovered_ids),
                    len(new_ids),
                    len(archived_ids),
                    inserted_executions,
                    inserted_commissions,
                    conflicts,
                    run_id,
                ),
            )
            unmatched = self._reconcile_positions(
                conn,
                run_id=run_id,
                current_as_of=normalized["finished_at_utc"],
                account_ids=tuple(discovered_ids),
                execution_leg_state=normalized["execution_leg_state"],
                position_leg_state=normalized["position_leg_state"],
            )
            conn.execute(
                "UPDATE portfolio_capture_runs "
                "SET unmatched_count=unmatched_count+? WHERE id=?",
                (unmatched, run_id),
            )

        return CaptureCommitResult(
            discovered_account_ids=tuple(discovered_ids),
            new_account_ids=tuple(new_ids),
            archived_activity_account_ids=tuple(archived_ids),
            inserted_execution_count=inserted_executions,
            inserted_commission_count=inserted_commissions,
            unmatched_count=unmatched,
            data_conflict_count=conflicts,
        )

    def finish_run(
        self,
        run_id: int,
        *,
        state: CaptureTerminalState,
        error_code: str | None = None,
        error_detail: str | None = None,
    ) -> CaptureRun:
        if state not in _TERMINAL_STATES:
            raise ValueError(f"unsupported terminal capture state: {state}")
        with self._connect() as conn:
            current = conn.execute(
                "SELECT * FROM portfolio_capture_runs WHERE id=?", (run_id,)
            ).fetchone()
            if current is None:
                raise KeyError(f"capture run not found: {run_id}")
            if current["state"] != "running":
                raise ValueError(f"capture run is already terminal: {run_id}")
            finished_at = current["finished_at"] or _now()
            redacted_detail = self._redact_account_ids(conn, error_detail)
            conn.execute(
                """
                UPDATE portfolio_capture_runs
                SET state=?, finished_at=?, error_code=?, error_detail=?
                WHERE id=?
                """,
                (state, finished_at, _optional_text(error_code), redacted_detail, run_id),
            )
            row = conn.execute(
                "SELECT * FROM portfolio_capture_runs WHERE id=?", (run_id,)
            ).fetchone()
        return self._run_from_row(row)

    def get_run(self, run_id: int) -> CaptureRun:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM portfolio_capture_runs WHERE id=?", (run_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"capture run not found: {run_id}")
        return self._run_from_row(row)

    def list_runs(self, *, limit: int = 20) -> list[CaptureRun]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit must be a positive integer")
        with self._connect() as conn:
            result = conn.execute(
                "SELECT * FROM portfolio_capture_runs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._run_from_row(row) for row in result]

    def last_successful_finished_at(self) -> datetime | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT finished_at FROM portfolio_capture_runs
                WHERE state='succeeded' AND finished_at IS NOT NULL
                ORDER BY finished_at DESC, id DESC LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        parsed = datetime.fromisoformat(row["finished_at"])
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def reconcile_interrupted(self) -> list[int]:
        finished_at = _now()
        with self._connect() as conn:
            stale = [
                int(row["id"])
                for row in conn.execute(
                    "SELECT id FROM portfolio_capture_runs "
                    "WHERE state='running' ORDER BY id"
                )
            ]
            if stale:
                placeholders = ",".join("?" for _ in stale)
                conn.execute(
                    f"""
                    UPDATE portfolio_capture_runs
                    SET state='interrupted', finished_at=COALESCE(finished_at, ?),
                        error_code='capture_interrupted',
                        error_detail='Capture process ended before completion.'
                    WHERE id IN ({placeholders})
                    """,
                    (finished_at, *stale),
                )
        return stale

    def position_snapshot_for_run(self, run_id: int) -> BrokerSnapshot:
        from src.portfolio_ibkr import (
            BrokerAccountSnapshot,
            BrokerPositionSnapshot,
            BrokerSnapshot,
        )

        with self._connect() as conn:
            run = conn.execute(
                "SELECT position_leg_state FROM portfolio_capture_runs WHERE id=?",
                (run_id,),
            ).fetchone()
            if run is None:
                raise KeyError(f"capture run not found: {run_id}")
            if run["position_leg_state"] != "complete":
                raise CaptureRunNotReviewable(
                    "capture run has no complete broker-position set"
                )
            account_rows = conn.execute(
                """
                SELECT a.* FROM portfolio_capture_run_accounts ra
                JOIN portfolio_accounts a ON a.id=ra.portfolio_account_id
                WHERE ra.capture_run_id=? ORDER BY a.id
                """,
                (run_id,),
            ).fetchall()
            position_rows = conn.execute(
                """
                SELECT p.*, a.broker_account_id
                FROM portfolio_broker_position_observations p
                JOIN portfolio_accounts a ON a.id=p.portfolio_account_id
                WHERE p.capture_run_id=?
                ORDER BY p.portfolio_account_id, p.id
                """,
                (run_id,),
            ).fetchall()
        return BrokerSnapshot(
            accounts=[
                BrokerAccountSnapshot(
                    account_id=row["broker_account_id"],
                    label=row["label"],
                    base_currency=row["base_currency"],
                )
                for row in account_rows
            ],
            positions=[
                BrokerPositionSnapshot(
                    account_id=row["broker_account_id"],
                    con_id=row["broker_con_id"],
                    symbol=row["symbol"],
                    asset_class=row["asset_class"],
                    quantity=row["quantity"],
                    currency=row["currency"],
                    avg_cost=row["avg_cost"],
                    market_value=row["market_value"],
                    unrealized_pnl=row["unrealized_pnl"],
                    market_value_base=row["market_value_base"],
                    unrealized_pnl_base=row["unrealized_pnl_base"],
                    metadata={
                        key: row[key]
                        for key in ("base_currency", "exchange", "local_symbol", "multiplier")
                        if row[key] is not None
                    },
                )
                for row in position_rows
            ],
        )

    def latest_reviewable_run_id(self) -> int | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT r.id FROM portfolio_capture_runs r
                WHERE r.position_leg_state='complete'
                  AND EXISTS (
                    SELECT 1 FROM portfolio_capture_run_accounts ra
                    JOIN portfolio_accounts a ON a.id=ra.portfolio_account_id
                    WHERE ra.capture_run_id=r.id
                      AND a.sync_mode='ibkr_review'
                      AND a.archived_at IS NULL
                  )
                ORDER BY r.id DESC LIMIT 1
                """
            ).fetchone()
        return None if row is None else int(row["id"])

    def _validate_capture(self, result: BrokerCaptureResult) -> dict[str, Any]:
        finished_at = _timestamp(result.finished_at_utc, "finished_at_utc")
        leg_states = (
            result.account_leg.state,
            result.execution_leg.state,
            result.position_leg.state,
        )
        if any(state not in _LEG_STATES for state in leg_states):
            raise ValueError("capture leg state is invalid")

        accounts: list[dict[str, Any]] = []
        account_ids: set[str] = set()
        for account in result.discovered_accounts:
            raw_id = _required(account.broker_account_id, "broker_account_id")
            if raw_id in account_ids:
                raise ValueError("discovered broker account ids must be unique")
            account_ids.add(raw_id)
            accounts.append(
                {
                    "broker_account_id": raw_id,
                    "base_currency": _currency(account.base_currency),
                }
            )

        snapshots = [self._normalize_snapshot(value, account_ids) for value in result.account_snapshots]
        positions = [self._normalize_position(value, account_ids) for value in result.positions]
        executions = [self._normalize_execution(value, account_ids) for value in result.executions]
        commissions = [self._normalize_commission(value, account_ids) for value in result.commissions]
        return {
            "finished_at_utc": finished_at,
            "account_leg_state": leg_states[0],
            "execution_leg_state": leg_states[1],
            "position_leg_state": leg_states[2],
            "accounts": accounts,
            "snapshots": snapshots,
            "positions": positions,
            "executions": executions,
            "commissions": commissions,
        }

    @staticmethod
    def _require_discovered(raw_id: str, account_ids: set[str]) -> str:
        normalized = _required(raw_id, "broker_account_id")
        if normalized not in account_ids:
            raise ValueError("observation account was not discovered in this capture")
        return normalized

    def _normalize_snapshot(
        self, value: AccountSnapshotObservation, account_ids: set[str]
    ) -> dict[str, Any]:
        normalized = {
            "broker_account_id": self._require_discovered(
                value.broker_account_id, account_ids
            ),
            "as_of_utc": _timestamp(value.as_of_utc, "as_of_utc"),
            "base_currency": _currency(value.base_currency),
        }
        normalized.update(
            {
                name: finite_or_none(getattr(value, name), name)
                for name in _ACCOUNT_NUMERIC_FIELDS
            }
        )
        return normalized

    def _normalize_position(
        self, value: PositionObservation, account_ids: set[str]
    ) -> dict[str, Any]:
        quantity = finite_or_none(value.quantity, "quantity")
        assert quantity is not None
        normalized = {
            "broker_account_id": self._require_discovered(
                value.broker_account_id, account_ids
            ),
            "broker_con_id": _required(value.broker_con_id, "broker_con_id"),
            "symbol": _required(value.symbol, "symbol").upper(),
            "asset_class": _required(value.asset_class, "asset_class").lower(),
            "quantity": quantity,
            "currency": _required(value.currency, "currency").upper(),
            "base_currency": _currency(value.base_currency),
            "exchange": _optional_text(value.exchange),
            "local_symbol": _optional_text(value.local_symbol),
            "multiplier": _optional_text(value.multiplier),
        }
        normalized.update(
            {
                name: finite_or_none(getattr(value, name), name)
                for name in _POSITION_NULLABLE_NUMERIC_FIELDS
            }
        )
        return normalized

    def _normalize_execution(
        self, value: ExecutionObservation, account_ids: set[str]
    ) -> dict[str, Any]:
        quantity = finite_or_none(value.quantity, "quantity")
        price = finite_or_none(value.price, "price")
        assert quantity is not None and price is not None
        origin = _required(value.origin, "origin").lower()
        if origin not in {"gateway", "flex"}:
            raise ValueError("origin must be gateway or flex")
        exec_id = _required(value.exec_id, "exec_id")
        return {
            "broker_account_id": self._require_discovered(
                value.broker_account_id, account_ids
            ),
            "origin": origin,
            "exec_id": exec_id,
            "execution_time_utc": _timestamp(
                value.execution_time_utc, "execution_time_utc"
            ),
            "broker_con_id": _required(value.broker_con_id, "broker_con_id"),
            "symbol": _required(value.symbol, "symbol").upper(),
            "asset_class": _required(value.asset_class, "asset_class").lower(),
            "currency": _required(value.currency, "currency").upper(),
            "exchange": _required(value.exchange, "exchange").upper(),
            "side": _required(value.side, "side").upper(),
            "quantity": quantity,
            "price": price,
            "order_id": _integer_or_none(value.order_id, "order_id"),
            "perm_id": _integer_or_none(value.perm_id, "perm_id"),
            "client_id": _integer_or_none(value.client_id, "client_id"),
            "order_ref": _optional_text(value.order_ref),
            "liquidation": _integer_or_none(value.liquidation, "liquidation"),
            "cumulative_quantity": finite_or_none(
                value.cumulative_quantity, "cumulative_quantity"
            ),
            "average_price": finite_or_none(value.average_price, "average_price"),
            "correction_family": correction_family(exec_id),
        }

    def _normalize_commission(
        self, value: CommissionObservation, account_ids: set[str]
    ) -> dict[str, Any]:
        report = CommissionObservation(
            broker_account_id=self._require_discovered(
                value.broker_account_id, account_ids
            ),
            exec_id=_required(value.exec_id, "exec_id"),
            commission=finite_or_none(value.commission, "commission"),
            currency=_currency(value.currency),
            realized_pnl=finite_or_none(value.realized_pnl, "realized_pnl"),
            yield_value=finite_or_none(value.yield_value, "yield_value"),
            yield_redemption_date=_integer_or_none(
                value.yield_redemption_date, "yield_redemption_date"
            ),
        )
        return {
            "broker_account_id": report.broker_account_id,
            "exec_id": report.exec_id,
            "commission": report.commission,
            "currency": report.currency,
            "realized_pnl": report.realized_pnl,
            "yield_value": report.yield_value,
            "yield_redemption_date": report.yield_redemption_date,
            "content_hash": commission_content_hash(report),
        }

    @staticmethod
    def _insert_snapshot(conn, run_id, account_ids, value) -> None:
        columns = (
            "net_liquidation", "total_cash_value", "settled_cash",
            "gross_position_value", "buying_power", "available_funds",
            "initial_margin_requirement", "maintenance_margin_requirement",
            "daily_realized_pnl", "daily_unrealized_pnl",
        )
        conn.execute(
            f"""
            INSERT OR IGNORE INTO portfolio_account_snapshots(
                capture_run_id, portfolio_account_id, as_of_utc, base_currency,
                {', '.join(columns)}, source, as_of_kind
            ) VALUES ({', '.join('?' for _ in range(4 + len(columns)))},
                      'ibkr_gateway', 'capture_completed')
            """,
            (
                run_id,
                account_ids[value["broker_account_id"]],
                value["as_of_utc"],
                value["base_currency"],
                *(value[column] for column in columns),
            ),
        )

    @staticmethod
    def _insert_position(conn, run_id, account_ids, value) -> None:
        columns = (
            "broker_con_id", "symbol", "asset_class", "quantity", "avg_cost",
            "market_value", "unrealized_pnl", "realized_pnl", "market_value_base",
            "unrealized_pnl_base", "currency", "base_currency", "exchange",
            "local_symbol", "multiplier",
        )
        conn.execute(
            f"""
            INSERT OR IGNORE INTO portfolio_broker_position_observations(
                capture_run_id, portfolio_account_id, broker, {', '.join(columns)}
            ) VALUES (?, ?, 'ibkr', {', '.join('?' for _ in columns)})
            """,
            (
                run_id,
                account_ids[value["broker_account_id"]],
                *(value[column] for column in columns),
            ),
        )

    def _insert_execution(self, conn, run_id, observed_at, account_ids, value):
        account_id = account_ids[value["broker_account_id"]]
        existing = conn.execute(
            """
            SELECT * FROM portfolio_broker_executions
            WHERE broker='ibkr' AND portfolio_account_id=? AND exec_id=?
            """,
            (account_id, value["exec_id"]),
        ).fetchone()
        if existing is not None:
            conflict = any(
                existing[column] != value[column]
                for column in _EXECUTION_COMPARISON_COLUMNS
            )
            return 0, int(conflict)

        prior = conn.execute(
            """
            SELECT exec_id FROM portfolio_broker_executions
            WHERE broker='ibkr' AND portfolio_account_id=?
              AND correction_family=?
            ORDER BY first_observed_run_id DESC, id DESC LIMIT 1
            """,
            (account_id, value["correction_family"]),
        ).fetchone()
        corrects_exec_id = None if prior is None else prior["exec_id"]
        columns = _EXECUTION_COMPARISON_COLUMNS
        conn.execute(
            f"""
            INSERT INTO portfolio_broker_executions(
                broker, portfolio_account_id, first_observed_run_id,
                first_observed_at_utc, {', '.join(columns)}, corrects_exec_id
            ) VALUES ('ibkr', ?, ?, ?, {', '.join('?' for _ in columns)}, ?)
            """,
            (
                account_id,
                run_id,
                observed_at,
                *(value[column] for column in columns),
                corrects_exec_id,
            ),
        )
        return 1, 0

    @staticmethod
    def _insert_commission(conn, run_id, observed_at, account_ids, value) -> int:
        return conn.execute(
            """
            INSERT OR IGNORE INTO portfolio_broker_commission_reports(
                broker, portfolio_account_id, first_observed_run_id,
                exec_id, first_observed_at_utc, commission, currency,
                realized_pnl, yield_value, yield_redemption_date, content_hash
            ) VALUES ('ibkr', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                account_ids[value["broker_account_id"]],
                run_id,
                value["exec_id"],
                observed_at,
                value["commission"],
                value["currency"],
                value["realized_pnl"],
                value["yield_value"],
                value["yield_redemption_date"],
                value["content_hash"],
            ),
        ).rowcount

    def _reconcile_positions(
        self,
        conn,
        *,
        run_id: int,
        current_as_of: str,
        account_ids: tuple[int, ...],
        execution_leg_state: str,
        position_leg_state: str,
    ) -> int:
        if position_leg_state != "complete":
            return 0
        inserted = 0
        for account_id in account_ids:
            previous = conn.execute(
                """
                SELECT r.id, r.finished_at
                FROM portfolio_capture_runs r
                JOIN portfolio_capture_run_accounts ra ON ra.capture_run_id=r.id
                WHERE ra.portfolio_account_id=? AND r.id < ?
                  AND r.position_leg_state='complete'
                ORDER BY r.id DESC LIMIT 1
                """,
                (account_id, run_id),
            ).fetchone()
            if previous is None:
                continue
            previous_run_id = int(previous["id"])
            previous_as_of = self._run_as_of(
                conn, previous_run_id, account_id, previous["finished_at"]
            )
            before = self._positions_for_run(conn, previous_run_id, account_id)
            after = self._positions_for_run(conn, run_id, account_id)
            for con_id in sorted(set(before) | set(after)):
                before_row = before.get(con_id)
                after_row = after.get(con_id)
                before_quantity = 0.0 if before_row is None else before_row["quantity"]
                after_quantity = 0.0 if after_row is None else after_row["quantity"]
                old_projection, old_unknown = self._execution_projection(
                    conn, account_id, con_id, previous_run_id
                )
                new_projection, new_unknown = self._execution_projection(
                    conn, account_id, con_id, run_id
                )
                expected = before_quantity + new_projection - old_projection
                residual = after_quantity - expected
                if abs(residual) <= 1e-9:
                    continue
                coverage = self._coverage(
                    previous_as_of,
                    current_as_of,
                    execution_leg_state,
                    bool(old_unknown or new_unknown),
                )
                reason = {
                    "complete": "unexplained_position_change",
                    "incomplete": "execution_coverage_incomplete",
                    "gap": "execution_coverage_gap",
                }[coverage]
                descriptive = after_row or before_row
                inserted += conn.execute(
                    """
                    INSERT OR IGNORE INTO portfolio_unmatched_position_changes(
                        portfolio_account_id, from_run_id, to_run_id, broker_con_id,
                        from_as_of_utc, to_as_of_utc, before_quantity, after_quantity,
                        expected_quantity, residual_quantity, execution_coverage,
                        source, reason_code, symbol, asset_class, currency
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ibkr', ?, ?, ?, ?)
                    """,
                    (
                        account_id,
                        previous_run_id,
                        run_id,
                        con_id,
                        previous_as_of,
                        current_as_of,
                        before_quantity,
                        after_quantity,
                        expected,
                        residual,
                        coverage,
                        reason,
                        descriptive["symbol"],
                        descriptive["asset_class"],
                        descriptive["currency"],
                    ),
                ).rowcount
        return inserted

    @staticmethod
    def _run_as_of(conn, run_id: int, account_id: int, fallback: str | None) -> str:
        row = conn.execute(
            """
            SELECT MAX(as_of_utc) AS as_of_utc
            FROM portfolio_account_snapshots
            WHERE capture_run_id=? AND portfolio_account_id=?
            """,
            (run_id, account_id),
        ).fetchone()
        as_of_utc = None if row is None else row["as_of_utc"]
        as_of_utc = as_of_utc or fallback
        if as_of_utc is None:
            raise ValueError("complete position capture requires an observation time")
        return as_of_utc

    @staticmethod
    def _positions_for_run(conn, run_id: int, account_id: int):
        return {
            row["broker_con_id"]: row
            for row in conn.execute(
                """
                SELECT * FROM portfolio_broker_position_observations
                WHERE capture_run_id=? AND portfolio_account_id=?
                """,
                (run_id, account_id),
            )
        }

    @staticmethod
    def _execution_projection(conn, account_id: int, con_id: str, run_id: int):
        effective: dict[str, sqlite3.Row] = {}
        for row in conn.execute(
            """
            SELECT * FROM portfolio_broker_executions
            WHERE portfolio_account_id=? AND first_observed_run_id <= ?
            ORDER BY first_observed_run_id, id
            """,
            (account_id, run_id),
        ):
            effective[row["correction_family"]] = row
        signed = 0.0
        unknown: set[str] = set()
        for family, row in effective.items():
            if row["broker_con_id"] != con_id:
                continue
            if row["side"] in {"BUY", "BOT"}:
                signed += row["quantity"]
            elif row["side"] in {"SELL", "SLD"}:
                signed -= row["quantity"]
            else:
                unknown.add(family)
        return signed, unknown

    @staticmethod
    def _coverage(
        from_as_of: str,
        to_as_of: str,
        execution_leg_state: str,
        has_unknown_side: bool,
    ) -> str:
        start = datetime.fromisoformat(from_as_of).astimezone(_EASTERN).date()
        end = datetime.fromisoformat(to_as_of).astimezone(_EASTERN).date()
        if start != end:
            return "gap"
        if execution_leg_state != "complete" or has_unknown_side:
            return "incomplete"
        return "complete"

    @staticmethod
    def _redact_account_ids(conn, detail: str | None) -> str | None:
        normalized = _optional_text(detail)
        if normalized is None:
            return None
        raw_ids = [
            row[0]
            for row in conn.execute(
                """
                SELECT broker_account_id FROM portfolio_accounts
                WHERE broker_account_id IS NOT NULL AND broker_account_id != ''
                """
            )
        ]
        for raw_id in sorted(raw_ids, key=len, reverse=True):
            normalized = normalized.replace(raw_id, "[redacted-account]")
        return normalized

    @staticmethod
    def _run_from_row(row: sqlite3.Row) -> CaptureRun:
        try:
            notes = json.loads(row["coverage_notes_json"] or "[]")
        except (TypeError, json.JSONDecodeError):
            notes = []
        if not isinstance(notes, list):
            notes = []
        return CaptureRun(
            id=int(row["id"]),
            trigger=row["trigger"],
            state=row["state"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            account_leg_state=row["account_leg_state"],
            execution_leg_state=row["execution_leg_state"],
            position_leg_state=row["position_leg_state"],
            discovered_account_count=int(row["discovered_account_count"]),
            new_account_count=int(row["new_account_count"]),
            archived_activity_count=int(row["archived_activity_count"]),
            inserted_execution_count=int(row["inserted_execution_count"]),
            inserted_commission_count=int(row["inserted_commission_count"]),
            unmatched_count=int(row["unmatched_count"]),
            data_conflict_count=int(row["data_conflict_count"]),
            error_code=row["error_code"],
            error_detail=row["error_detail"],
            effective_client_id=int(row["effective_client_id"]),
            coverage_notes=tuple(str(note) for note in notes),
        )
