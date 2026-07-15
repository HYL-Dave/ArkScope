"""User-owned annotations over immutable portfolio activity facts."""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Collection, Literal, get_args
from zoneinfo import ZoneInfo

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


@dataclass(frozen=True)
class ActivityAccount:
    id: int
    label: str
    broker: str
    broker_account_id_hash: str | None
    archived: bool


@dataclass(frozen=True)
class CommissionRevision:
    id: int
    first_observed_run_id: int
    first_observed_at_utc: str
    commission: float | None
    currency: str | None
    realized_pnl: float | None
    yield_value: float | None
    yield_redemption_date: int | None
    is_latest: bool


@dataclass(frozen=True)
class ExecutionRevision:
    id: int
    exec_id: str
    origin: Literal["gateway", "flex"]
    first_observed_run_id: int
    first_observed_at_utc: str
    execution_time_utc: str
    broker_con_id: str
    symbol: str
    asset_class: str
    currency: str
    exchange: str
    side: str
    quantity: float
    price: float
    order_id: int | None
    perm_id: int | None
    client_id: int | None
    order_ref: str | None
    liquidation: int | None
    cumulative_quantity: float | None
    average_price: float | None
    corrects_exec_id: str | None
    is_effective: bool
    commission_revisions: list[CommissionRevision]


@dataclass(frozen=True)
class ActivityFill:
    family_root_id: int
    effective_revision_id: int
    revisions: list[ExecutionRevision]


@dataclass(frozen=True)
class EffectiveFill:
    quantity: float
    price: float


@dataclass(frozen=True)
class ProviderTotals:
    commission: float | None
    commission_currency: str | None
    realized_pnl: float | None
    realized_outcome: Literal["gain", "loss", "flat", "unknown"]


@dataclass(frozen=True)
class PositionEffect:
    position_direction: Literal["increase", "reduce", "unknown"]
    close_scope: Literal["none", "partial", "complete", "unknown"]
    position_context: Literal["complete", "unknown"]


@dataclass(frozen=True)
class ActivityObjective:
    side: Literal["buy", "sell", "mixed", "unknown"]
    quantity: float
    average_price: float | None
    gross_notional: float | None
    gross_notional_kind: Literal["deterministic_arithmetic"]
    commission: float | None
    commission_currency: str | None
    realized_pnl: float | None
    realized_outcome: Literal["gain", "loss", "flat", "unknown"]
    position_direction: Literal["increase", "reduce", "unknown"]
    close_scope: Literal["none", "partial", "complete", "unknown"]
    position_context: Literal["complete", "unknown"]


@dataclass(frozen=True)
class BrokerActivityItem:
    id: str
    kind: Literal["order", "execution"]
    occurred_at_utc: str
    account: ActivityAccount
    symbol: str | None
    asset_class: str | None
    currency: str | None
    source: Literal["broker"]
    state: Literal[
        "realized_gain", "realized_loss", "realized_flat", "outcome_unknown"
    ]
    objective: ActivityObjective
    annotation: ActivityAnnotation | None
    fills: list[ActivityFill]


@dataclass(frozen=True)
class ActivitySummary:
    item_count: int
    unmatched_count: int
    recent_window_days: int | None


@dataclass(frozen=True)
class PortfolioActivityPage:
    accounts: list[ActivityAccount]
    history_started_at_utc: str | None
    items: list[BrokerActivityItem]
    summary: ActivitySummary
    next_cursor: str | None


_EASTERN = ZoneInfo("America/New_York")
_UNKNOWN_POSITION_EFFECT = PositionEffect("unknown", "unknown", "unknown")


def _signed_quantity(side: str, quantity: float) -> float | None:
    normalized = side.upper()
    if normalized in {"BUY", "BOT"}:
        return quantity
    if normalized in {"SELL", "SLD"}:
        return -quantity
    return None


def _finite_sum(values: Collection[float]) -> float | None:
    try:
        result = math.fsum(values)
    except OverflowError:
        return None
    return result if math.isfinite(result) else None


def _weighted_average(fills: Collection[EffectiveFill]) -> float | None:
    denominator = _finite_sum([abs(fill.quantity) for fill in fills])
    numerator = _finite_sum(
        [abs(fill.quantity) * fill.price for fill in fills]
    )
    if denominator is None or numerator is None or denominator == 0:
        return None
    result = numerator / denominator
    return result if math.isfinite(result) else None


def _provider_totals(fills: Collection[ActivityFill]) -> ProviderTotals:
    effective = [
        next(
            revision
            for revision in fill.revisions
            if revision.id == fill.effective_revision_id
        )
        for fill in fills
    ]
    latest = [
        next(
            (report for report in revision.commission_revisions if report.is_latest),
            None,
        )
        for revision in effective
    ]
    execution_currencies = {revision.currency for revision in effective}
    report_currencies = {
        report.currency for report in latest if report is not None and report.currency
    }
    compatible_currency = (
        len(execution_currencies) == 1
        and len(report_currencies) == 1
        and len(latest) == len(fills)
        and all(report is not None and report.currency for report in latest)
        and execution_currencies == report_currencies
    )

    commission = None
    if compatible_currency and all(
        report is not None and report.commission is not None for report in latest
    ):
        commission = _finite_sum(
            [report.commission for report in latest if report is not None]
        )

    realized_pnl = None
    if compatible_currency and all(
        report is not None and report.realized_pnl is not None for report in latest
    ):
        realized_pnl = _finite_sum(
            [report.realized_pnl for report in latest if report is not None]
        )
    if realized_pnl is None:
        outcome = "unknown"
    elif realized_pnl > 0:
        outcome = "gain"
    elif realized_pnl < 0:
        outcome = "loss"
    else:
        outcome = "flat"
    return ProviderTotals(
        commission=commission,
        commission_currency=(
            next(iter(report_currencies)) if commission is not None else None
        ),
        realized_pnl=realized_pnl,
        realized_outcome=outcome,
    )


def _position_effect(
    *,
    before_quantity: float,
    after_quantity: float,
    signed_quantity: float,
    context_complete: bool,
) -> PositionEffect:
    epsilon = 1e-9
    if (
        not context_complete
        or not all(
            math.isfinite(value)
            for value in (before_quantity, after_quantity, signed_quantity)
        )
        or abs(after_quantity - (before_quantity + signed_quantity)) > epsilon
    ):
        return _UNKNOWN_POSITION_EFFECT

    before_zero = abs(before_quantity) <= epsilon
    after_zero = abs(after_quantity) <= epsilon
    if before_zero and not after_zero:
        return PositionEffect("increase", "none", "complete")
    if not before_zero and after_zero:
        return PositionEffect("reduce", "complete", "complete")
    if before_quantity * after_quantity <= 0:
        return _UNKNOWN_POSITION_EFFECT
    if abs(after_quantity) > abs(before_quantity) + epsilon:
        return PositionEffect("increase", "none", "complete")
    if abs(after_quantity) < abs(before_quantity) - epsilon:
        return PositionEffect("reduce", "partial", "complete")
    return _UNKNOWN_POSITION_EFFECT


_ACTIVITY_ID_SQL = """
CASE WHEN perm_id > 0
     THEN 'order:' || portfolio_account_id || ':' || perm_id
     ELSE 'execution:' || portfolio_account_id || ':' || family_root_id
END
"""

_BROKER_HEADER_CTE = f"""
WITH ranked_execution AS (
    SELECT e.*,
           MIN(e.id) OVER (
               PARTITION BY e.portfolio_account_id, e.correction_family
           ) AS family_root_id,
           ROW_NUMBER() OVER (
               PARTITION BY e.portfolio_account_id, e.correction_family
               ORDER BY e.first_observed_run_id DESC, e.id DESC
           ) AS effective_rank
    FROM portfolio_broker_executions e
), effective_execution AS (
    SELECT * FROM ranked_execution WHERE effective_rank=1
), ranked_commission AS (
    SELECT c.*,
           ROW_NUMBER() OVER (
               PARTITION BY c.broker, c.portfolio_account_id, c.exec_id
               ORDER BY c.first_observed_run_id DESC, c.id DESC
           ) AS commission_rank
    FROM portfolio_broker_commission_reports c
), effective_with_commission AS (
    SELECT e.*,
           c.id AS commission_revision_id,
           c.commission,
           c.currency AS commission_currency,
           c.realized_pnl
    FROM effective_execution e
    LEFT JOIN ranked_commission c
      ON c.broker=e.broker
     AND c.portfolio_account_id=e.portfolio_account_id
     AND c.exec_id=e.exec_id
     AND c.commission_rank=1
), grouped_header AS (
    SELECT portfolio_account_id,
           CASE WHEN perm_id > 0 THEN 'order' ELSE 'execution' END AS kind,
           CASE WHEN perm_id > 0 THEN perm_id ELSE family_root_id END AS group_ref,
           {_ACTIVITY_ID_SQL} AS activity_id,
           MAX(execution_time_utc) AS occurred_at_utc,
           CASE WHEN COUNT(DISTINCT symbol)=1 THEN MIN(symbol) END AS symbol,
           CASE WHEN COUNT(DISTINCT asset_class)=1 THEN MIN(asset_class) END
                AS asset_class,
           CASE WHEN COUNT(DISTINCT currency)=1 THEN MIN(currency) END AS currency,
           COUNT(*) AS fill_count,
           COUNT(commission_currency) AS commission_currency_count,
           COUNT(DISTINCT commission_currency) AS distinct_commission_currencies,
           MIN(commission_currency) AS provider_currency,
           COUNT(realized_pnl) AS realized_count,
           SUM(realized_pnl) AS realized_sum,
           MAX(CASE WHEN UPPER(symbol)=UPPER(?) THEN 1 ELSE 0 END)
                AS symbol_matches
    FROM effective_with_commission
    WHERE (? IS NULL OR portfolio_account_id=?)
    GROUP BY portfolio_account_id, kind, group_ref, activity_id
), classified_header AS (
    SELECT *,
           CASE
             WHEN realized_count=fill_count
              AND commission_currency_count=fill_count
              AND distinct_commission_currencies=1
              AND currency IS NOT NULL
              AND provider_currency=currency
              AND realized_sum BETWEEN -1.7976931348623157e308
                                   AND 1.7976931348623157e308
             THEN CASE
                    WHEN realized_sum > 0 THEN 'realized_gain'
                    WHEN realized_sum < 0 THEN 'realized_loss'
                    ELSE 'realized_flat'
                  END
             ELSE 'outcome_unknown'
           END AS state
    FROM grouped_header
)
"""


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
        self, filters: ActivityFilters, *, now_utc: datetime | None = None
    ) -> PortfolioActivityPage:
        if not isinstance(filters.limit, int) or not 1 <= filters.limit <= 200:
            raise ValueError("activity limit must be between 1 and 200")
        if filters.cursor is not None:
            raise ValueError("activity cursors are implemented in Task 3")
        if filters.recent and (filters.date_from_et or filters.date_to_et):
            raise ValueError("recent cannot be combined with explicit dates")

        date_from_utc, date_to_utc = self._time_bounds(filters, now_utc)
        conditions = ["(? IS NULL OR ?='broker')"]
        params: list[object] = [
            filters.symbol or "",
            filters.account_id,
            filters.account_id,
            filters.source,
            filters.source,
        ]
        if filters.symbol:
            conditions.append("symbol_matches=1")
        if date_from_utc:
            conditions.append("occurred_at_utc >= ?")
            params.append(date_from_utc)
        if date_to_utc:
            conditions.append("occurred_at_utc < ?")
            params.append(date_to_utc)
        if filters.state:
            conditions.append("state=?")
            params.append(filters.state)
        query = (
            _BROKER_HEADER_CTE
            + " SELECT * FROM classified_header WHERE "
            + " AND ".join(conditions)
            + " ORDER BY occurred_at_utc DESC, activity_id DESC LIMIT ?"
        )
        params.append(filters.limit + 1)

        with self._connect() as conn:
            header_rows = list(conn.execute(query, params))
            selected_headers = header_rows[: filters.limit]
            account_map = self._activity_accounts()
            if not selected_headers:
                items: list[BrokerActivityItem] = []
            else:
                fills_by_activity = self._load_selected_fills(
                    conn, [row["activity_id"] for row in selected_headers]
                )
                items = [
                    self._broker_item(
                        conn,
                        header,
                        account_map[int(header["portfolio_account_id"])],
                        fills_by_activity[header["activity_id"]],
                    )
                    for header in selected_headers
                ]

        accounts = list(account_map.values())
        return PortfolioActivityPage(
            accounts=accounts,
            history_started_at_utc=None,
            items=items,
            summary=ActivitySummary(
                item_count=len(items),
                unmatched_count=0,
                recent_window_days=7 if filters.recent else None,
            ),
            next_cursor=None,
        )

    @staticmethod
    def _time_bounds(
        filters: ActivityFilters, now_utc: datetime | None
    ) -> tuple[str | None, str | None]:
        def parse(value: str, field: str) -> date:
            try:
                return date.fromisoformat(value)
            except (TypeError, ValueError):
                raise ValueError(f"{field} must use YYYY-MM-DD") from None

        start_date = (
            parse(filters.date_from_et, "date_from_et")
            if filters.date_from_et
            else None
        )
        end_date = (
            parse(filters.date_to_et, "date_to_et")
            if filters.date_to_et
            else None
        )
        if filters.recent:
            current = now_utc or datetime.now(timezone.utc)
            if current.tzinfo is None:
                current = current.replace(tzinfo=timezone.utc)
            end_date = current.astimezone(_EASTERN).date()
            start_date = end_date - timedelta(days=6)
        if start_date and end_date and start_date > end_date:
            raise ValueError("date_from_et must not be later than date_to_et")

        start = (
            datetime.combine(start_date, time.min, _EASTERN)
            .astimezone(timezone.utc)
            .isoformat()
            if start_date
            else None
        )
        end = (
            datetime.combine(end_date + timedelta(days=1), time.min, _EASTERN)
            .astimezone(timezone.utc)
            .isoformat()
            if end_date
            else None
        )
        return start, end

    def _activity_accounts(self) -> dict[int, ActivityAccount]:
        return {
            account.id: ActivityAccount(
                id=account.id,
                label=safe_portfolio_account_label(account),
                broker=account.broker,
                broker_account_id_hash=account.broker_account_id_hash,
                archived=account.archived_at is not None,
            )
            for account in self.portfolio.list_accounts(
                include_archived=True, ensure_manual=False
            )
        }

    @staticmethod
    def _load_selected_fills(
        conn: sqlite3.Connection, activity_ids: list[str]
    ) -> dict[str, list[ActivityFill]]:
        placeholders = ",".join("?" for _ in activity_ids)
        selected_cte = f"""
        WITH ranked_execution AS (
            SELECT e.*,
                   MIN(e.id) OVER (
                       PARTITION BY e.portfolio_account_id, e.correction_family
                   ) AS family_root_id,
                   ROW_NUMBER() OVER (
                       PARTITION BY e.portfolio_account_id, e.correction_family
                       ORDER BY e.first_observed_run_id DESC, e.id DESC
                   ) AS effective_rank
            FROM portfolio_broker_executions e
        ), selected_family AS (
            SELECT *, {_ACTIVITY_ID_SQL} AS activity_id
            FROM ranked_execution
            WHERE effective_rank=1
              AND {_ACTIVITY_ID_SQL} IN ({placeholders})
        )
        """
        revision_rows = list(
            conn.execute(
                selected_cte
                + """
                SELECT r.*, s.activity_id,
                       s.id AS effective_revision_id,
                       s.family_root_id AS selected_family_root_id
                FROM ranked_execution r
                JOIN selected_family s
                  ON s.portfolio_account_id=r.portfolio_account_id
                 AND s.correction_family=r.correction_family
                ORDER BY s.activity_id, s.family_root_id,
                         r.first_observed_run_id, r.id
                """,
                activity_ids,
            )
        )
        commission_rows = list(
            conn.execute(
                selected_cte
                + """
                SELECT c.*, s.activity_id
                FROM portfolio_broker_commission_reports c
                JOIN ranked_execution r
                  ON r.broker=c.broker
                 AND r.portfolio_account_id=c.portfolio_account_id
                 AND r.exec_id=c.exec_id
                JOIN selected_family s
                  ON s.portfolio_account_id=r.portfolio_account_id
                 AND s.correction_family=r.correction_family
                ORDER BY s.activity_id, c.exec_id,
                         c.first_observed_run_id, c.id
                """,
                activity_ids,
            )
        )
        commissions: dict[tuple[int, str], list[CommissionRevision]] = {}
        grouped_commission_rows: dict[tuple[int, str], list[sqlite3.Row]] = {}
        for row in commission_rows:
            grouped_commission_rows.setdefault(
                (int(row["portfolio_account_id"]), row["exec_id"]), []
            ).append(row)
        for key, rows in grouped_commission_rows.items():
            commissions[key] = [
                CommissionRevision(
                    id=int(row["id"]),
                    first_observed_run_id=int(row["first_observed_run_id"]),
                    first_observed_at_utc=row["first_observed_at_utc"],
                    commission=row["commission"],
                    currency=row["currency"],
                    realized_pnl=row["realized_pnl"],
                    yield_value=row["yield_value"],
                    yield_redemption_date=row["yield_redemption_date"],
                    is_latest=index == len(rows) - 1,
                )
                for index, row in enumerate(rows)
            ]

        revisions_by_family: dict[
            tuple[str, int, str], list[ExecutionRevision]
        ] = {}
        fill_identity: dict[tuple[str, int, str], tuple[int, int]] = {}
        for row in revision_rows:
            key = (
                row["activity_id"],
                int(row["portfolio_account_id"]),
                row["correction_family"],
            )
            effective_id = int(row["effective_revision_id"])
            fill_identity[key] = (
                int(row["selected_family_root_id"]),
                effective_id,
            )
            revisions_by_family.setdefault(key, []).append(
                ExecutionRevision(
                    id=int(row["id"]),
                    exec_id=row["exec_id"],
                    origin=row["origin"],
                    first_observed_run_id=int(row["first_observed_run_id"]),
                    first_observed_at_utc=row["first_observed_at_utc"],
                    execution_time_utc=row["execution_time_utc"],
                    broker_con_id=row["broker_con_id"],
                    symbol=row["symbol"],
                    asset_class=row["asset_class"],
                    currency=row["currency"],
                    exchange=row["exchange"],
                    side=row["side"],
                    quantity=float(row["quantity"]),
                    price=float(row["price"]),
                    order_id=row["order_id"],
                    perm_id=row["perm_id"],
                    client_id=row["client_id"],
                    order_ref=row["order_ref"],
                    liquidation=row["liquidation"],
                    cumulative_quantity=row["cumulative_quantity"],
                    average_price=row["average_price"],
                    corrects_exec_id=row["corrects_exec_id"],
                    is_effective=int(row["id"]) == effective_id,
                    commission_revisions=commissions.get(
                        (int(row["portfolio_account_id"]), row["exec_id"]), []
                    ),
                )
            )
        result = {activity_id: [] for activity_id in activity_ids}
        for key, revisions in revisions_by_family.items():
            root_id, effective_id = fill_identity[key]
            result[key[0]].append(
                ActivityFill(
                    family_root_id=root_id,
                    effective_revision_id=effective_id,
                    revisions=revisions,
                )
            )
        for fills in result.values():
            fills.sort(key=lambda fill: fill.family_root_id)
        return result

    def _broker_item(
        self,
        conn: sqlite3.Connection,
        header: sqlite3.Row,
        account: ActivityAccount,
        fills: list[ActivityFill],
    ) -> BrokerActivityItem:
        effective = [
            next(
                revision
                for revision in fill.revisions
                if revision.id == fill.effective_revision_id
            )
            for fill in fills
        ]
        normalized_sides = {
            "buy" if revision.side in {"BUY", "BOT"}
            else "sell" if revision.side in {"SELL", "SLD"}
            else "unknown"
            for revision in effective
        }
        if normalized_sides == {"buy"}:
            side = "buy"
        elif normalized_sides == {"sell"}:
            side = "sell"
        elif "unknown" in normalized_sides:
            side = "unknown"
        else:
            side = "mixed"

        arithmetic_fills = [
            EffectiveFill(revision.quantity, revision.price)
            for revision in effective
        ]
        gross_notional = _finite_sum(
            [abs(fill.quantity * fill.price) for fill in arithmetic_fills]
        )
        provider = _provider_totals(fills)
        position = self._position_effect_for_item(
            conn,
            account_id=int(header["portfolio_account_id"]),
            fills=fills,
            effective=effective,
            side=side,
        )
        kind = header["kind"]
        target_ref = str(header["group_ref"])
        annotation_row = conn.execute(
            """
            SELECT intent_label, note, updated_at_utc
            FROM portfolio_activity_annotations
            WHERE target_kind=? AND portfolio_account_id=? AND target_ref=?
            """,
            (kind, int(header["portfolio_account_id"]), target_ref),
        ).fetchone()
        annotation = (
            None
            if annotation_row is None
            else ActivityAnnotation(
                intent_label=annotation_row["intent_label"],
                note=annotation_row["note"],
                updated_at_utc=annotation_row["updated_at_utc"],
            )
        )
        objective = ActivityObjective(
            side=side,
            quantity=sum(abs(revision.quantity) for revision in effective),
            average_price=_weighted_average(arithmetic_fills),
            gross_notional=gross_notional,
            gross_notional_kind="deterministic_arithmetic",
            commission=provider.commission,
            commission_currency=provider.commission_currency,
            realized_pnl=provider.realized_pnl,
            realized_outcome=provider.realized_outcome,
            position_direction=position.position_direction,
            close_scope=position.close_scope,
            position_context=position.position_context,
        )
        return BrokerActivityItem(
            id=header["activity_id"],
            kind=kind,
            occurred_at_utc=header["occurred_at_utc"],
            account=account,
            symbol=header["symbol"],
            asset_class=header["asset_class"],
            currency=header["currency"],
            source="broker",
            state=header["state"],
            objective=objective,
            annotation=annotation,
            fills=fills,
        )

    @staticmethod
    def _position_effect_for_item(
        conn: sqlite3.Connection,
        *,
        account_id: int,
        fills: list[ActivityFill],
        effective: list[ExecutionRevision],
        side: str,
    ) -> PositionEffect:
        if side not in {"buy", "sell"}:
            return _UNKNOWN_POSITION_EFFECT
        con_ids = {revision.broker_con_id for revision in effective}
        first_runs = {fill.revisions[0].first_observed_run_id for fill in fills}
        signed = _finite_sum(
            [
                value
                for revision in effective
                if (value := _signed_quantity(revision.side, revision.quantity))
                is not None
            ]
        )
        if len(con_ids) != 1 or len(first_runs) != 1 or signed is None:
            return _UNKNOWN_POSITION_EFFECT
        con_id = next(iter(con_ids))
        to_run_id = next(iter(first_runs))
        to_run = conn.execute(
            """
            SELECT r.*, MAX(s.as_of_utc) AS as_of_utc
            FROM portfolio_capture_runs r
            JOIN portfolio_capture_run_accounts ra ON ra.capture_run_id=r.id
            LEFT JOIN portfolio_account_snapshots s
              ON s.capture_run_id=r.id
             AND s.portfolio_account_id=ra.portfolio_account_id
            WHERE r.id=? AND ra.portfolio_account_id=?
            GROUP BY r.id
            """,
            (to_run_id, account_id),
        ).fetchone()
        if (
            to_run is None
            or to_run["state"] not in {"succeeded", "partial"}
            or to_run["account_leg_state"] != "complete"
            or to_run["execution_leg_state"] != "complete"
            or to_run["position_leg_state"] != "complete"
        ):
            return _UNKNOWN_POSITION_EFFECT
        previous = conn.execute(
            """
            SELECT r.*, MAX(s.as_of_utc) AS as_of_utc
            FROM portfolio_capture_runs r
            JOIN portfolio_capture_run_accounts ra ON ra.capture_run_id=r.id
            LEFT JOIN portfolio_account_snapshots s
              ON s.capture_run_id=r.id
             AND s.portfolio_account_id=ra.portfolio_account_id
            WHERE ra.portfolio_account_id=? AND r.id < ?
              AND r.state IN ('succeeded','partial')
              AND r.position_leg_state='complete'
            GROUP BY r.id
            ORDER BY r.id DESC LIMIT 1
            """,
            (account_id, to_run_id),
        ).fetchone()
        if previous is None:
            return _UNKNOWN_POSITION_EFFECT
        before_at = previous["as_of_utc"] or previous["finished_at"]
        after_at = to_run["as_of_utc"] or to_run["finished_at"]
        if not before_at or not after_at:
            return _UNKNOWN_POSITION_EFFECT
        before_dt = datetime.fromisoformat(before_at)
        after_dt = datetime.fromisoformat(after_at)
        if before_dt.astimezone(_EASTERN).date() != after_dt.astimezone(_EASTERN).date():
            return _UNKNOWN_POSITION_EFFECT
        if any(
            not (before_dt < datetime.fromisoformat(row.execution_time_utc) <= after_dt)
            for row in effective
        ):
            return _UNKNOWN_POSITION_EFFECT
        incomplete_leg = conn.execute(
            """
            SELECT 1
            FROM portfolio_capture_runs r
            JOIN portfolio_capture_run_accounts ra ON ra.capture_run_id=r.id
            WHERE ra.portfolio_account_id=?
              AND r.id > ? AND r.id <= ?
              AND r.execution_leg_state != 'complete'
            LIMIT 1
            """,
            (account_id, int(previous["id"]), to_run_id),
        ).fetchone()
        if incomplete_leg is not None:
            return _UNKNOWN_POSITION_EFFECT

        ambiguity = conn.execute(
            f"""
            WITH ranked_execution AS (
                SELECT e.*,
                       MIN(e.id) OVER (
                           PARTITION BY e.portfolio_account_id, e.correction_family
                       ) AS family_root_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY e.portfolio_account_id, e.correction_family
                           ORDER BY e.first_observed_run_id DESC, e.id DESC
                       ) AS effective_rank,
                       MIN(e.first_observed_run_id) OVER (
                           PARTITION BY e.portfolio_account_id, e.correction_family
                       ) AS family_first_run_id
                FROM portfolio_broker_executions e
            )
            SELECT COUNT(DISTINCT {_ACTIVITY_ID_SQL}) AS activity_count
            FROM ranked_execution
            WHERE effective_rank=1
              AND portfolio_account_id=?
              AND broker_con_id=?
              AND family_first_run_id > ?
              AND family_first_run_id <= ?
            """,
            (account_id, con_id, int(previous["id"]), to_run_id),
        ).fetchone()
        if ambiguity is None or int(ambiguity["activity_count"]) != 1:
            return _UNKNOWN_POSITION_EFFECT

        def observed_quantity(run_id: int) -> float:
            row = conn.execute(
                """
                SELECT quantity FROM portfolio_broker_position_observations
                WHERE capture_run_id=? AND portfolio_account_id=?
                  AND broker_con_id=?
                """,
                (run_id, account_id, con_id),
            ).fetchone()
            return 0.0 if row is None else float(row["quantity"])

        return _position_effect(
            before_quantity=observed_quantity(int(previous["id"])),
            after_quantity=observed_quantity(to_run_id),
            signed_quantity=signed,
            context_complete=True,
        )

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
