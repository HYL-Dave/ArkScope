"""Local portfolio/holdings state.

Holdings are profile state: local SQLite, never PG, and never broker-authoritative
without an explicit sync path.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_symbol(value: str) -> str:
    return (value or "").strip().upper()


def _float_or_error(value: Any, field_name: str, *, allow_none: bool) -> float | None:
    if value is None:
        if allow_none:
            return None
        raise ValueError(f"{field_name} must be a finite number")
    try:
        out = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a finite number") from None
    if not math.isfinite(out):
        raise ValueError(f"{field_name} must be a finite number")
    return out


def portfolio_account_hash(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


_account_hash = portfolio_account_hash


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


@dataclass(frozen=True)
class PortfolioAccount:
    id: int
    label: str
    broker: str
    broker_account_id: str | None = None
    broker_account_id_hash: str | None = None
    sync_mode: str = "manual"
    base_currency: str | None = None
    include_in_total: bool = True
    archived_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True)
class BrokerPosition:
    broker: str
    broker_account_id: str
    broker_con_id: str
    symbol: str
    asset_class: str
    quantity: float
    avg_cost: float | None = None
    currency: str = "USD"
    market_value: float | None = None
    unrealized_pnl: float | None = None
    market_value_base: float | None = None
    unrealized_pnl_base: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PortfolioPosition:
    id: int
    account_id: int
    broker: str
    broker_con_id: str | None
    symbol: str
    asset_class: str
    quantity: float
    avg_cost: float | None = None
    currency: str = "USD"
    market_value: float | None = None
    unrealized_pnl: float | None = None
    market_value_base: float | None = None
    unrealized_pnl_base: float | None = None
    source: str = "manual"
    sync_status: str = "local"
    last_sync_at: str | None = None
    closed_at: str | None = None
    notes: str = ""
    thesis: str = ""
    tags: list[str] = field(default_factory=list)
    strategy_bucket: str | None = None
    target_allocation: float | None = None


@dataclass(frozen=True)
class ManualAdjustmentChange:
    field: str
    before: Any
    after: Any


@dataclass(frozen=True)
class ManualAdjustment:
    id: int
    account_id: int
    position_id: int
    action: Literal["create", "update", "close"]
    note: str | None
    source: Literal["manual"]
    occurred_at_utc: str
    changes: tuple[ManualAdjustmentChange, ...]


@dataclass(frozen=True)
class CurrencyTotal:
    position_count: int
    market_value: float | None = None
    unrealized_pnl: float | None = None


@dataclass(frozen=True)
class PortfolioTotals:
    currency_basis: str
    per_currency: dict[str, CurrencyTotal]
    broker_base: dict[str, float] | None = None


@dataclass(frozen=True)
class PortfolioSnapshot:
    accounts: list[PortfolioAccount]
    positions: list[PortfolioPosition]
    totals: PortfolioTotals
    included_account_ids: list[int]


_SCHEMA = """
CREATE TABLE IF NOT EXISTS portfolio_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    broker TEXT NOT NULL,
    broker_account_id TEXT,
    broker_account_id_hash TEXT,
    sync_mode TEXT NOT NULL DEFAULT 'manual',
    base_currency TEXT,
    include_in_total INTEGER NOT NULL DEFAULT 1,
    archived_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_portfolio_accounts_broker_hash
ON portfolio_accounts(broker, broker_account_id_hash)
WHERE broker_account_id_hash IS NOT NULL;

CREATE TABLE IF NOT EXISTS portfolio_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES portfolio_accounts(id) ON DELETE CASCADE,
    broker TEXT NOT NULL DEFAULT 'manual',
    broker_con_id TEXT,
    symbol TEXT NOT NULL,
    asset_class TEXT NOT NULL DEFAULT 'stock',
    quantity REAL NOT NULL DEFAULT 0,
    avg_cost REAL,
    currency TEXT NOT NULL DEFAULT 'USD',
    market_value REAL,
    unrealized_pnl REAL,
    market_value_base REAL,
    unrealized_pnl_base REAL,
    broker_snapshot_json TEXT NOT NULL DEFAULT '{}',
    source TEXT NOT NULL DEFAULT 'manual',
    sync_status TEXT NOT NULL DEFAULT 'local',
    last_sync_at TEXT,
    closed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_portfolio_positions_broker_conid
ON portfolio_positions(account_id, broker, broker_con_id)
WHERE broker_con_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS portfolio_position_notes (
    position_id INTEGER PRIMARY KEY REFERENCES portfolio_positions(id) ON DELETE CASCADE,
    notes TEXT NOT NULL DEFAULT '',
    thesis TEXT NOT NULL DEFAULT '',
    tags_json TEXT NOT NULL DEFAULT '[]',
    strategy_bucket TEXT,
    target_allocation REAL,
    alert_preferences_json TEXT NOT NULL DEFAULT '{}',
    research_links_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolio_manual_adjustments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES portfolio_accounts(id) ON DELETE RESTRICT,
    position_id INTEGER NOT NULL REFERENCES portfolio_positions(id) ON DELETE RESTRICT,
    action TEXT NOT NULL CHECK(action IN ('create','update','close')),
    note TEXT,
    source TEXT NOT NULL CHECK(source='manual'),
    occurred_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS portfolio_manual_adjustment_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    adjustment_id INTEGER NOT NULL REFERENCES portfolio_manual_adjustments(id) ON DELETE RESTRICT,
    field TEXT NOT NULL,
    before_json TEXT,
    after_json TEXT,
    UNIQUE(adjustment_id, field)
);

"""

_UNSET = object()

# Row-update ownership sets: user-owned fields are editable on every position;
# manual-financial fields only when the row's broker is "manual" (broker-synced
# values are owned by the next IBKR snapshot).
_USER_OWNED_FIELDS = frozenset(
    {"notes", "thesis", "tags", "strategy_bucket", "target_allocation"}
)
_MANUAL_FINANCIAL_FIELDS = frozenset(
    {"symbol", "asset_class", "quantity", "avg_cost", "currency"}
)


class BrokerPositionManagedBySync(ValueError):
    """Manual-only mutation attempted on a broker-synced position."""


class PortfolioStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
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

    def ensure_manual_account(self) -> PortfolioAccount:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM portfolio_accounts WHERE broker='manual' AND archived_at IS NULL ORDER BY id LIMIT 1"
            ).fetchone()
            if row is None:
                now = _now()
                cur = conn.execute(
                    """
                    INSERT INTO portfolio_accounts
                    (label,broker,sync_mode,base_currency,include_in_total,created_at,updated_at)
                    VALUES ('Manual','manual','manual','USD',1,?,?)
                    """,
                    (now, now),
                )
                row = conn.execute(
                    "SELECT * FROM portfolio_accounts WHERE id=?",
                    (cur.lastrowid,),
                ).fetchone()
            return self._account_from_row(row)

    def list_accounts(self, *, include_archived: bool = False) -> list[PortfolioAccount]:
        self.ensure_manual_account()
        sql = "SELECT * FROM portfolio_accounts"
        if not include_archived:
            sql += " WHERE archived_at IS NULL"
        sql += " ORDER BY CASE WHEN broker='manual' THEN 0 ELSE 1 END, label, id"
        with self._connect() as conn:
            return [self._account_from_row(row) for row in conn.execute(sql)]

    def get_account(self, account_id: int) -> PortfolioAccount:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM portfolio_accounts WHERE id=?",
                (account_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"portfolio account not found: {account_id}")
        return self._account_from_row(row)

    def update_account(
        self,
        account_id: int,
        *,
        label: str | None = None,
        sync_mode: str | None = None,
        base_currency: str | None | object = _UNSET,
        include_in_total: bool | None = None,
        archived: bool | None = None,
    ) -> PortfolioAccount:
        current = self.get_account(account_id)
        next_sync_mode = current.sync_mode if sync_mode is None else _validate_sync_mode(sync_mode)
        if current.broker == "manual" and next_sync_mode != "manual":
            raise ValueError("manual portfolio accounts require manual sync_mode")
        next_label = current.label if label is None else label.strip()
        if not next_label:
            raise ValueError("portfolio account label is required")
        next_base_currency = (
            current.base_currency
            if base_currency is _UNSET
            else ((base_currency or "").strip().upper() or None)
        )
        next_include = current.include_in_total if include_in_total is None else bool(include_in_total)
        archived_at = current.archived_at
        if archived is True and archived_at is None:
            archived_at = _now()
        elif archived is False:
            archived_at = None

        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE portfolio_accounts
                SET label=?, sync_mode=?, base_currency=?, include_in_total=?,
                    archived_at=?, updated_at=?
                WHERE id=?
                """,
                (
                    next_label,
                    next_sync_mode,
                    next_base_currency,
                    int(next_include),
                    archived_at,
                    now,
                    account_id,
                ),
            )
        return self.get_account(account_id)

    def upsert_broker_account(
        self,
        broker: str,
        broker_account_id: str,
        label: str,
        sync_mode: str = "ibkr_review",
        base_currency: str | None = None,
    ) -> PortfolioAccount:
        broker = (broker or "").strip().lower()
        if not broker or broker == "manual":
            raise ValueError("broker account requires non-manual broker")
        broker_account_id = (broker_account_id or "").strip()
        if not broker_account_id:
            raise ValueError("broker_account_id is required")
        sync_mode = _validate_sync_mode(sync_mode)
        acct_hash = _account_hash(broker_account_id)
        now = _now()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM portfolio_accounts WHERE broker=? AND broker_account_id_hash=?",
                (broker, acct_hash),
            ).fetchone()
            if row is None:
                cur = conn.execute(
                    """
                    INSERT INTO portfolio_accounts
                    (label,broker,broker_account_id,broker_account_id_hash,sync_mode,base_currency,include_in_total,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,1,?,?)
                    """,
                    (label, broker, broker_account_id, acct_hash, sync_mode, base_currency, now, now),
                )
                row = conn.execute("SELECT * FROM portfolio_accounts WHERE id=?", (cur.lastrowid,)).fetchone()
            else:
                conn.execute(
                    """
                    UPDATE portfolio_accounts
                    SET label=?, broker_account_id=?, sync_mode=?, base_currency=?, archived_at=NULL, updated_at=?
                    WHERE id=?
                    """,
                    (label, broker_account_id, sync_mode, base_currency, now, row["id"]),
                )
                row = conn.execute("SELECT * FROM portfolio_accounts WHERE id=?", (row["id"],)).fetchone()
            return self._account_from_row(row)

    def upsert_manual_position(
        self,
        *,
        account_id: int,
        symbol: str,
        asset_class: str = "stock",
        quantity: float,
        avg_cost: float | None = None,
        currency: str = "USD",
        notes: str = "",
    ) -> PortfolioPosition:
        financial_sets = self._validated_manual_sets(
            {
                "symbol": symbol,
                "asset_class": asset_class,
                "quantity": quantity,
                "avg_cost": avg_cost,
                "currency": currency,
            }
        )
        now = _now()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO portfolio_positions
                (account_id,broker,symbol,asset_class,quantity,avg_cost,currency,source,sync_status,created_at,updated_at)
                VALUES (?,'manual',?,?,?,?,?,'manual','local',?,?)
                """,
                (
                    account_id,
                    financial_sets["symbol"],
                    financial_sets["asset_class"],
                    financial_sets["quantity"],
                    financial_sets["avg_cost"],
                    financial_sets["currency"],
                    now,
                    now,
                ),
            )
            position_id = int(cur.lastrowid)
            self._upsert_notes(conn, position_id=position_id, notes=notes, tags=None, now=now)
            self._record_manual_adjustment(
                conn,
                account_id=account_id,
                position_id=position_id,
                action="create",
                changes={field: (None, value) for field, value in financial_sets.items()},
                now=now,
            )
            return self._position_from_id(conn, position_id)

    def apply_broker_positions(
        self,
        *,
        account_id: int,
        positions: list[BrokerPosition],
        source: str,
    ) -> list[PortfolioPosition]:
        now = _now()
        out: list[PortfolioPosition] = []
        account = self.get_account(account_id)
        broker = account.broker
        incoming_con_ids: set[str] = set()
        with self._connect() as conn:
            for pos in positions:
                position_broker = (pos.broker or "").strip().lower()
                con_id = str(pos.broker_con_id or "").strip()
                symbol = _norm_symbol(pos.symbol)
                if not position_broker or not con_id or not symbol:
                    raise ValueError("broker positions require broker, conId, and symbol")
                if position_broker != broker:
                    raise ValueError("broker position does not match portfolio account")
                incoming_con_ids.add(con_id)
                existing = conn.execute(
                    """
                    SELECT id FROM portfolio_positions
                    WHERE account_id=? AND broker=? AND broker_con_id=?
                    """,
                    (account_id, position_broker, con_id),
                ).fetchone()
                payload = _json_dumps(pos.metadata or {})
                params = (
                    symbol,
                    pos.asset_class,
                    float(pos.quantity),
                    pos.avg_cost,
                    (pos.currency or "USD").upper(),
                    pos.market_value,
                    pos.unrealized_pnl,
                    pos.market_value_base,
                    pos.unrealized_pnl_base,
                    payload,
                    source,
                    "synced",
                    now,
                    now,
                )
                if existing is None:
                    cur = conn.execute(
                        """
                        INSERT INTO portfolio_positions
                        (account_id,broker,broker_con_id,symbol,asset_class,quantity,avg_cost,currency,
                         market_value,unrealized_pnl,market_value_base,unrealized_pnl_base,
                         broker_snapshot_json,source,sync_status,last_sync_at,created_at,updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            account_id,
                            position_broker,
                            con_id,
                            symbol,
                            pos.asset_class,
                            float(pos.quantity),
                            pos.avg_cost,
                            (pos.currency or "USD").upper(),
                            pos.market_value,
                            pos.unrealized_pnl,
                            pos.market_value_base,
                            pos.unrealized_pnl_base,
                            payload,
                            source,
                            "synced",
                            now,
                            now,
                            now,
                        ),
                    )
                    position_id = int(cur.lastrowid)
                    self._upsert_notes(conn, position_id=position_id, notes="", tags=None, now=now)
                else:
                    position_id = int(existing["id"])
                    conn.execute(
                        """
                        UPDATE portfolio_positions
                        SET symbol=?, asset_class=?, quantity=?, avg_cost=?, currency=?,
                            market_value=?, unrealized_pnl=?, market_value_base=?, unrealized_pnl_base=?,
                            broker_snapshot_json=?, source=?, sync_status=?, last_sync_at=?, updated_at=?,
                            closed_at=NULL
                        WHERE id=?
                        """,
                        (*params, position_id),
                    )
                out.append(self._position_from_id(conn, position_id))
            existing_rows = conn.execute(
                """
                SELECT id, broker_con_id
                FROM portfolio_positions
                WHERE account_id=? AND broker=? AND broker_con_id IS NOT NULL
                  AND closed_at IS NULL
                """,
                (account_id, broker),
            ).fetchall()
            for row in existing_rows:
                if str(row["broker_con_id"]) not in incoming_con_ids:
                    conn.execute(
                        """
                        UPDATE portfolio_positions
                        SET closed_at=?, sync_status='closed', last_sync_at=?, updated_at=?
                        WHERE id=?
                        """,
                        (now, now, now, row["id"]),
                    )
            return out

    def update_position_notes(
        self,
        position_id: int,
        *,
        notes: str | None = None,
        thesis: str | None = None,
        tags: list[str] | None = None,
        strategy_bucket: str | None = None,
        target_allocation: float | None = None,
    ) -> PortfolioPosition:
        """Compatibility wrapper: keeps the old ``None means unchanged`` contract."""
        fields: dict[str, Any] = {}
        if notes is not None:
            fields["notes"] = notes
        if thesis is not None:
            fields["thesis"] = thesis
        if tags is not None:
            fields["tags"] = tags
        if strategy_bucket is not None:
            fields["strategy_bucket"] = strategy_bucket
        if target_allocation is not None:
            fields["target_allocation"] = target_allocation
        return self.update_position(position_id, fields=fields)

    def update_position(
        self,
        position_id: int,
        *,
        fields: dict[str, Any],
    ) -> PortfolioPosition:
        """One transactional row update with key-presence semantics.

        A key absent from ``fields`` is unchanged. An explicit ``None`` clears the
        nullable fields (``avg_cost``, ``strategy_bucket``, ``target_allocation``);
        ``None`` for notes/thesis/tags means no change (empty string/list clears).
        Manual-financial keys on a broker-synced row raise before any write.
        """
        unknown = sorted(set(fields) - _USER_OWNED_FIELDS - _MANUAL_FINANCIAL_FIELDS)
        if unknown:
            raise ValueError(f"unknown position fields: {unknown}")
        now = _now()
        with self._connect() as conn:
            current = self._position_from_id(conn, position_id)
            manual_keys = sorted(set(fields) & _MANUAL_FINANCIAL_FIELDS)
            if manual_keys and current.broker != "manual":
                raise BrokerPositionManagedBySync(
                    f"broker-synced position fields are managed by sync: {manual_keys}"
                )

            sets = self._validated_manual_sets(fields)
            changes = {
                field: (getattr(current, field), value)
                for field, value in sets.items()
                if getattr(current, field) != value
            }
            if sets:
                sets["updated_at"] = now
                assignments = ", ".join(f"{key}=?" for key in sets)
                conn.execute(
                    f"UPDATE portfolio_positions SET {assignments} WHERE id=?",
                    (*sets.values(), position_id),
                )

            if set(fields) & _USER_OWNED_FIELDS:
                notes = current.notes
                if fields.get("notes") is not None:
                    notes = str(fields["notes"])
                thesis = current.thesis
                if fields.get("thesis") is not None:
                    thesis = str(fields["thesis"])
                tags = current.tags
                if fields.get("tags") is not None:
                    tags = [str(tag) for tag in fields["tags"]]
                strategy_bucket = current.strategy_bucket
                if "strategy_bucket" in fields:
                    raw_bucket = fields["strategy_bucket"]
                    strategy_bucket = None if raw_bucket is None else str(raw_bucket)
                target_allocation = current.target_allocation
                if "target_allocation" in fields:
                    target_allocation = _float_or_error(
                        fields["target_allocation"], "target_allocation", allow_none=True
                    )
                self._upsert_notes(
                    conn,
                    position_id=position_id,
                    notes=notes,
                    thesis=thesis,
                    tags=tags,
                    strategy_bucket=strategy_bucket,
                    target_allocation=target_allocation,
                    now=now,
                )
            if changes:
                self._record_manual_adjustment(
                    conn,
                    account_id=current.account_id,
                    position_id=position_id,
                    action="update",
                    changes=changes,
                    now=now,
                )
            return self._position_from_id(conn, position_id)

    @staticmethod
    def _validated_manual_sets(fields: dict[str, Any]) -> dict[str, Any]:
        sets: dict[str, Any] = {}
        if "symbol" in fields:
            symbol = _norm_symbol(fields["symbol"])
            if not symbol:
                raise ValueError("symbol is required")
            sets["symbol"] = symbol
        if "asset_class" in fields:
            asset_class = str(fields["asset_class"] or "").strip().lower()
            if not asset_class:
                raise ValueError("asset_class is required")
            sets["asset_class"] = asset_class
        if "quantity" in fields:
            quantity = _float_or_error(fields["quantity"], "quantity", allow_none=False)
            if quantity == 0:
                raise ValueError("quantity must be a finite non-zero number")
            sets["quantity"] = quantity
        if "avg_cost" in fields:
            avg_cost = _float_or_error(fields["avg_cost"], "avg_cost", allow_none=True)
            if avg_cost is not None and avg_cost < 0:
                raise ValueError("avg_cost must be null or a finite non-negative number")
            sets["avg_cost"] = avg_cost
        if "currency" in fields:
            currency = str(fields["currency"] or "").strip().upper()
            if not currency:
                raise ValueError("currency is required")
            sets["currency"] = currency
        return sets

    def get_position(self, position_id: int) -> PortfolioPosition:
        with self._connect() as conn:
            return self._position_from_id(conn, position_id)

    def close_position(self, position_id: int) -> PortfolioPosition:
        """Soft-close a manual position (idempotent). Broker rows are closed by sync."""
        now = _now()
        with self._connect() as conn:
            current = self._position_from_id(conn, position_id)
            if current.broker != "manual":
                raise BrokerPositionManagedBySync(
                    "broker-synced positions are closed by the next sync, not manually"
                )
            if current.closed_at is not None:
                return current
            conn.execute(
                """
                UPDATE portfolio_positions
                SET closed_at=?, sync_status='closed', updated_at=?
                WHERE id=?
                """,
                (now, now, position_id),
            )
            self._record_manual_adjustment(
                conn,
                account_id=current.account_id,
                position_id=position_id,
                action="close",
                changes={"closed_at": (None, now)},
                now=now,
            )
            return self._position_from_id(conn, position_id)

    def list_positions(
        self,
        *,
        account_id: int | None = None,
        include_closed: bool = False,
    ) -> list[PortfolioPosition]:
        clauses: list[str] = []
        params: list[Any] = []
        if account_id is not None:
            clauses.append("p.account_id=?")
            params.append(account_id)
        if not include_closed:
            clauses.append("p.closed_at IS NULL")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT p.*, n.notes, n.thesis, n.tags_json, n.strategy_bucket, n.target_allocation
            FROM portfolio_positions p
            LEFT JOIN portfolio_position_notes n ON n.position_id=p.id
            {where}
            ORDER BY p.symbol, p.id
        """
        with self._connect() as conn:
            return [self._position_from_row(row) for row in conn.execute(sql, params)]

    def list_manual_adjustments(
        self, position_id: int | None = None
    ) -> list[ManualAdjustment]:
        where = "WHERE a.position_id=?" if position_id is not None else ""
        params: tuple[Any, ...] = (position_id,) if position_id is not None else ()
        sql = f"""
            SELECT a.id, a.account_id, a.position_id, a.action, a.note, a.source,
                   a.occurred_at_utc, c.field, c.before_json, c.after_json
            FROM portfolio_manual_adjustments a
            LEFT JOIN portfolio_manual_adjustment_changes c ON c.adjustment_id=a.id
            {where}
            ORDER BY a.id, c.field
        """
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        adjustments: list[ManualAdjustment] = []
        current_id: int | None = None
        current: dict[str, Any] | None = None
        changes: list[ManualAdjustmentChange] = []
        for row in rows:
            adjustment_id = int(row["id"])
            if adjustment_id != current_id:
                if current is not None:
                    adjustments.append(
                        ManualAdjustment(changes=tuple(changes), **current)
                    )
                current_id = adjustment_id
                current = {
                    "id": adjustment_id,
                    "account_id": int(row["account_id"]),
                    "position_id": int(row["position_id"]),
                    "action": row["action"],
                    "note": row["note"],
                    "source": row["source"],
                    "occurred_at_utc": row["occurred_at_utc"],
                }
                changes = []
            if row["field"] is not None:
                changes.append(
                    ManualAdjustmentChange(
                        field=row["field"],
                        before=_json_loads(row["before_json"], None),
                        after=_json_loads(row["after_json"], None),
                    )
                )
        if current is not None:
            adjustments.append(ManualAdjustment(changes=tuple(changes), **current))
        return adjustments

    def snapshot(
        self,
        *,
        account_id: int | None = None,
        include_closed: bool = False,
        included_only: bool = False,
    ) -> PortfolioSnapshot:
        accounts = self.list_accounts()
        if account_id is not None:
            accounts = [account for account in accounts if account.id == account_id]
            if not accounts:
                raise KeyError(f"portfolio account not found: {account_id}")
        elif included_only:
            accounts = [account for account in accounts if account.include_in_total]

        selected_ids = {account.id for account in accounts}
        positions = [
            position
            for position in self.list_positions(include_closed=include_closed)
            if position.account_id in selected_ids
        ]
        # Closed rows are display-only: they may appear in ``positions`` under
        # include_closed, but totals always count open holdings only.
        open_positions = [
            position for position in positions if position.closed_at is None
        ]
        if account_id is not None or included_only:
            included_account_ids = sorted(selected_ids)
            total_positions = open_positions
        else:
            included_account_ids = sorted(
                account.id for account in accounts if account.include_in_total
            )
            total_positions = [
                position
                for position in open_positions
                if position.account_id in included_account_ids
            ]
        return PortfolioSnapshot(
            accounts=accounts,
            positions=positions,
            totals=_totals(total_positions),
            included_account_ids=included_account_ids,
        )

    def _upsert_notes(
        self,
        conn: sqlite3.Connection,
        *,
        position_id: int,
        notes: str,
        now: str,
        thesis: str = "",
        tags: list[str] | None,
        strategy_bucket: str | None = None,
        target_allocation: float | None = None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO portfolio_position_notes
            (position_id,notes,thesis,tags_json,strategy_bucket,target_allocation,updated_at)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(position_id) DO UPDATE SET
                notes=excluded.notes,
                thesis=excluded.thesis,
                tags_json=excluded.tags_json,
                strategy_bucket=excluded.strategy_bucket,
                target_allocation=excluded.target_allocation,
                updated_at=excluded.updated_at
            """,
            (
                position_id,
                notes or "",
                thesis or "",
                _json_dumps(tags or []),
                strategy_bucket,
                target_allocation,
                now,
            ),
        )

    @staticmethod
    def _record_manual_adjustment(
        conn: sqlite3.Connection,
        *,
        account_id: int,
        position_id: int,
        action: Literal["create", "update", "close"],
        changes: dict[str, tuple[Any, Any]],
        now: str,
    ) -> None:
        cur = conn.execute(
            """
            INSERT INTO portfolio_manual_adjustments
            (account_id,position_id,action,note,source,occurred_at_utc)
            VALUES (?,?,?,NULL,'manual',?)
            """,
            (account_id, position_id, action, now),
        )
        adjustment_id = int(cur.lastrowid)
        conn.executemany(
            """
            INSERT INTO portfolio_manual_adjustment_changes
            (adjustment_id,field,before_json,after_json)
            VALUES (?,?,?,?)
            """,
            [
                (adjustment_id, field, _json_dumps(before), _json_dumps(after))
                for field, (before, after) in sorted(changes.items())
            ],
        )

    def _position_from_id(self, conn: sqlite3.Connection, position_id: int) -> PortfolioPosition:
        row = conn.execute(
            """
            SELECT p.*, n.notes, n.thesis, n.tags_json, n.strategy_bucket, n.target_allocation
            FROM portfolio_positions p
            LEFT JOIN portfolio_position_notes n ON n.position_id=p.id
            WHERE p.id=?
            """,
            (position_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"portfolio position not found: {position_id}")
        return self._position_from_row(row)

    @staticmethod
    def _account_from_row(row: sqlite3.Row) -> PortfolioAccount:
        return PortfolioAccount(
            id=int(row["id"]),
            label=row["label"],
            broker=row["broker"],
            broker_account_id=row["broker_account_id"],
            broker_account_id_hash=row["broker_account_id_hash"],
            sync_mode=row["sync_mode"],
            base_currency=row["base_currency"],
            include_in_total=bool(row["include_in_total"]),
            archived_at=row["archived_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _position_from_row(row: sqlite3.Row) -> PortfolioPosition:
        return PortfolioPosition(
            id=int(row["id"]),
            account_id=int(row["account_id"]),
            broker=row["broker"],
            broker_con_id=row["broker_con_id"],
            symbol=row["symbol"],
            asset_class=row["asset_class"],
            quantity=float(row["quantity"]),
            avg_cost=row["avg_cost"],
            currency=row["currency"],
            market_value=row["market_value"],
            unrealized_pnl=row["unrealized_pnl"],
            market_value_base=row["market_value_base"],
            unrealized_pnl_base=row["unrealized_pnl_base"],
            source=row["source"],
            sync_status=row["sync_status"],
            last_sync_at=row["last_sync_at"],
            closed_at=row["closed_at"],
            notes=row["notes"] or "",
            thesis=row["thesis"] or "",
            tags=list(_json_loads(row["tags_json"], [])),
            strategy_bucket=row["strategy_bucket"],
            target_allocation=row["target_allocation"],
        )


def _validate_sync_mode(value: str) -> str:
    mode = (value or "").strip()
    if mode not in {"manual", "ibkr_review", "ibkr_auto"}:
        raise ValueError(f"invalid portfolio sync_mode: {value!r}")
    return mode


def _totals(positions: list[PortfolioPosition]) -> PortfolioTotals:
    by_currency: dict[str, dict[str, Any]] = {}
    has_base_values = bool(positions) and all(p.market_value_base is not None for p in positions)
    base_market_value = 0.0
    base_unrealized = 0.0
    for pos in positions:
        currency = (pos.currency or "USD").upper()
        bucket = by_currency.setdefault(
            currency,
            {"position_count": 0, "market_value": None, "unrealized_pnl": None},
        )
        bucket["position_count"] += 1
        if pos.market_value is not None:
            bucket["market_value"] = (bucket["market_value"] or 0.0) + float(pos.market_value)
        if pos.unrealized_pnl is not None:
            bucket["unrealized_pnl"] = (bucket["unrealized_pnl"] or 0.0) + float(pos.unrealized_pnl)
        if pos.market_value_base is not None:
            base_market_value += float(pos.market_value_base)
        if pos.unrealized_pnl_base is not None:
            base_unrealized += float(pos.unrealized_pnl_base)

    per_currency = {
        currency: CurrencyTotal(
            position_count=int(values["position_count"]),
            market_value=values["market_value"],
            unrealized_pnl=values["unrealized_pnl"],
        )
        for currency, values in sorted(by_currency.items())
    }
    if has_base_values:
        return PortfolioTotals(
            currency_basis="broker_base",
            per_currency=per_currency,
            broker_base={"market_value": base_market_value, "unrealized_pnl": base_unrealized},
        )
    return PortfolioTotals(currency_basis="per_currency", per_currency=per_currency, broker_base=None)
