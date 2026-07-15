"""User-owned annotations over immutable portfolio activity facts."""

from __future__ import annotations

import base64
import binascii
import json
import math
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Collection, Literal, TypeAlias, get_args
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
class UnmatchedActivityItem:
    id: str
    kind: Literal["unmatched"]
    occurred_at_utc: str
    account: ActivityAccount
    symbol: str | None
    asset_class: str | None
    currency: str | None
    source: Literal["broker"]
    state: Literal["unmatched"]
    annotation: ActivityAnnotation | None
    from_run_id: int
    to_run_id: int
    from_as_of_utc: str
    to_as_of_utc: str
    before_quantity: float
    after_quantity: float
    expected_quantity: float
    residual_quantity: float
    execution_coverage: Literal["complete", "incomplete", "gap"]
    reason_code: str


@dataclass(frozen=True)
class ActivityFieldChange:
    field: str
    before: Any
    after: Any


@dataclass(frozen=True)
class ManualActivityItem:
    id: str
    kind: Literal["manual_adjustment"]
    occurred_at_utc: str
    account: ActivityAccount
    symbol: str
    source: Literal["manual"]
    state: Literal["manual_adjustment"]
    annotation: ActivityAnnotation | None
    position_id: int
    action: Literal["create", "update", "close"]
    changes: list[ActivityFieldChange]


@dataclass(frozen=True)
class CoverageGapItem:
    id: str
    kind: Literal["coverage_gap"]
    occurred_at_utc: str
    account: ActivityAccount | None
    source: Literal["system"]
    state: Literal["coverage_gap"]
    from_run_id: int | None
    to_run_id: int
    from_as_of_utc: str | None
    to_as_of_utc: str
    reason_code: Literal["execution_leg_incomplete", "broker_day_gap"]


@dataclass(frozen=True)
class HistoryStartItem:
    id: str
    kind: Literal["history_start"]
    occurred_at_utc: str
    account: ActivityAccount
    source: Literal["system"]
    state: Literal["history_start"]
    capture_run_id: int


PortfolioActivityItem: TypeAlias = (
    BrokerActivityItem
    | UnmatchedActivityItem
    | ManualActivityItem
    | CoverageGapItem
    | HistoryStartItem
)


@dataclass(frozen=True)
class ActivitySummary:
    item_count: int
    unmatched_count: int
    recent_window_days: int | None


@dataclass(frozen=True)
class PortfolioActivityPage:
    accounts: list[ActivityAccount]
    history_started_at_utc: str | None
    items: list[PortfolioActivityItem]
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


@dataclass(frozen=True)
class _ActivityCursor:
    occurred_at_utc: str
    activity_id: str


@dataclass(frozen=True)
class _NormalizedActivityFilters:
    date_from_utc: str | None
    date_to_utc: str | None
    account_id: int | None
    symbol: str | None
    source: ActivitySource | None
    state: ActivityState | None
    recent: bool
    limit: int
    cursor: _ActivityCursor | None


def _parse_utc_datetime(value: str, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{field} must be an ISO timestamp") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a UTC offset")
    return parsed


def _decode_cursor(value: str) -> _ActivityCursor:
    if not isinstance(value, str) or not value or "=" in value:
        raise ValueError("invalid activity cursor")
    try:
        encoded = value.encode("ascii")
        padding = b"=" * ((4 - len(encoded) % 4) % 4)
        raw = base64.b64decode(encoded + padding, altchars=b"-_", validate=True)

        def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, item in pairs:
                if key in result:
                    raise ValueError("duplicate cursor key")
                result[key] = item
            return result

        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
    except (binascii.Error, UnicodeError, json.JSONDecodeError, ValueError):
        raise ValueError("invalid activity cursor") from None
    if not isinstance(payload, dict) or set(payload) != {
        "occurred_at_utc",
        "activity_id",
    }:
        raise ValueError("invalid activity cursor")
    occurred_at = payload["occurred_at_utc"]
    activity_id = payload["activity_id"]
    if not isinstance(activity_id, str) or not activity_id:
        raise ValueError("invalid activity cursor")
    parsed_occurred_at = _parse_utc_datetime(occurred_at, "cursor occurred_at_utc")
    if occurred_at != parsed_occurred_at.astimezone(timezone.utc).isoformat():
        raise ValueError("invalid activity cursor")
    return _ActivityCursor(occurred_at, activity_id)


def _encode_cursor(item: PortfolioActivityItem) -> str:
    payload = {"occurred_at_utc": item.occurred_at_utc, "activity_id": item.id}
    return base64.urlsafe_b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")


def _et_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).astimezone(_EASTERN).date().isoformat()
    except (TypeError, ValueError):
        return None


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
        conn.create_function("portfolio_et_date", 1, _et_date, deterministic=True)
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def list_activity(
        self, filters: ActivityFilters, *, now_utc: datetime | None = None
    ) -> PortfolioActivityPage:
        normalized = self._normalize_filters(filters, now_utc)
        with self._connect() as conn:
            account_map = self._activity_accounts()
            headers = [
                *self._broker_headers(conn, normalized),
                *self._manual_headers(conn, normalized),
                *self._unmatched_headers(conn, normalized),
                *self._coverage_gap_headers(conn, normalized),
                *self._history_headers(conn, normalized),
            ]
            headers.sort(
                key=lambda row: (row["occurred_at_utc"], row["activity_id"]),
                reverse=True,
            )
            if normalized.cursor is not None:
                cursor_key = (
                    normalized.cursor.occurred_at_utc,
                    normalized.cursor.activity_id,
                )
                headers = [
                    row
                    for row in headers
                    if (row["occurred_at_utc"], row["activity_id"]) < cursor_key
                ]
            selected_headers = headers[: normalized.limit]
            broker_headers = [
                row for row in selected_headers if row["projection"] == "broker"
            ]
            manual_headers = [
                row for row in selected_headers if row["projection"] == "manual"
            ]
            unmatched_headers = [
                row for row in selected_headers if row["projection"] == "unmatched"
            ]
            if broker_headers:
                fills_by_activity = self._load_selected_fills(
                    conn, [row["activity_id"] for row in broker_headers]
                )
            else:
                fills_by_activity = {}
            manual_changes = self._load_manual_changes(
                conn, [int(row["local_id"]) for row in manual_headers]
            )
            annotations = self._load_selected_annotations(
                conn, manual_headers + unmatched_headers
            )
            items = [
                self._item_from_header(
                    conn,
                    header,
                    account_map,
                    fills_by_activity,
                    manual_changes,
                    annotations,
                )
                for header in selected_headers
            ]

        accounts = list(account_map.values())
        return PortfolioActivityPage(
            accounts=accounts,
            history_started_at_utc=self._history_started_at(normalized),
            items=items,
            summary=ActivitySummary(
                item_count=len(items),
                unmatched_count=self._unmatched_count(normalized),
                recent_window_days=7 if normalized.recent else None,
            ),
            next_cursor=(
                _encode_cursor(items[-1])
                if items and len(headers) > normalized.limit
                else None
            ),
        )

    @classmethod
    def _normalize_filters(
        cls, filters: ActivityFilters, now_utc: datetime | None
    ) -> _NormalizedActivityFilters:
        if not isinstance(filters, ActivityFilters):
            raise ValueError("activity filters are required")
        if isinstance(filters.limit, bool) or not isinstance(filters.limit, int):
            raise ValueError("activity limit must be between 1 and 200")
        if not 1 <= filters.limit <= 200:
            raise ValueError("activity limit must be between 1 and 200")
        if filters.source is not None and filters.source not in get_args(ActivitySource):
            raise ValueError("unsupported activity source")
        if filters.state is not None and filters.state not in get_args(ActivityState):
            raise ValueError("unsupported activity state")
        if filters.account_id is not None and (
            isinstance(filters.account_id, bool)
            or not isinstance(filters.account_id, int)
            or filters.account_id <= 0
        ):
            raise ValueError("account_id must be a positive integer")
        if not isinstance(filters.recent, bool):
            raise ValueError("recent must be boolean")
        if filters.recent and (
            filters.date_from_et is not None or filters.date_to_et is not None
        ):
            raise ValueError("recent cannot be combined with explicit dates")
        if now_utc is not None:
            if not isinstance(now_utc, datetime):
                raise ValueError("now_utc must be a datetime or None")
            if now_utc.tzinfo is None or now_utc.utcoffset() is None:
                raise ValueError("now_utc must include a UTC offset")
        symbol = None
        if filters.symbol is not None:
            if not isinstance(filters.symbol, str) or not filters.symbol.strip():
                raise ValueError("symbol must be non-empty text")
            symbol = filters.symbol.strip().upper()

        date_from_utc, date_to_utc = cls._time_bounds(filters, now_utc)
        return _NormalizedActivityFilters(
            date_from_utc=date_from_utc,
            date_to_utc=date_to_utc,
            account_id=filters.account_id,
            symbol=symbol,
            source=filters.source,
            state=filters.state,
            recent=filters.recent,
            limit=filters.limit,
            cursor=_decode_cursor(filters.cursor) if filters.cursor is not None else None,
        )

    @staticmethod
    def _time_bounds(
        filters: ActivityFilters, now_utc: datetime | None
    ) -> tuple[str | None, str | None]:
        def parse(value: str, field: str) -> date:
            if not isinstance(value, str) or len(value) != 10:
                raise ValueError(f"{field} must use YYYY-MM-DD")
            try:
                parsed = date.fromisoformat(value)
            except ValueError:
                raise ValueError(f"{field} must use YYYY-MM-DD") from None
            if parsed.isoformat() != value:
                raise ValueError(f"{field} must use YYYY-MM-DD")
            return parsed

        start_date = (
            parse(filters.date_from_et, "date_from_et")
            if filters.date_from_et is not None
            else None
        )
        end_date = (
            parse(filters.date_to_et, "date_to_et")
            if filters.date_to_et is not None
            else None
        )
        if filters.recent:
            current = now_utc or datetime.now(timezone.utc)
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

    @staticmethod
    def _bounded_headers(
        conn: sqlite3.Connection,
        select_sql: str,
        conditions: list[str],
        params: list[object],
        filters: _NormalizedActivityFilters,
    ) -> list[dict[str, Any]]:
        if filters.date_from_utc is not None:
            conditions.append("occurred_at_utc >= ?")
            params.append(filters.date_from_utc)
        if filters.date_to_utc is not None:
            conditions.append("occurred_at_utc < ?")
            params.append(filters.date_to_utc)
        if filters.cursor is not None:
            conditions.append(
                "(occurred_at_utc < ? OR "
                "(occurred_at_utc = ? AND activity_id < ?))"
            )
            params.extend(
                [
                    filters.cursor.occurred_at_utc,
                    filters.cursor.occurred_at_utc,
                    filters.cursor.activity_id,
                ]
            )
        params.append(filters.limit + 1)
        rows = conn.execute(
            select_sql
            + " WHERE "
            + " AND ".join(conditions or ["1=1"])
            + " ORDER BY occurred_at_utc DESC, activity_id DESC LIMIT ?",
            params,
        )
        return [dict(row) for row in rows]

    def _broker_headers(
        self, conn: sqlite3.Connection, filters: _NormalizedActivityFilters
    ) -> list[dict[str, Any]]:
        broker_states = {
            "realized_gain",
            "realized_loss",
            "realized_flat",
            "outcome_unknown",
        }
        if filters.source not in {None, "broker"}:
            return []
        if filters.state is not None and filters.state not in broker_states:
            return []
        conditions: list[str] = []
        params: list[object] = [
            filters.symbol or "",
            filters.account_id,
            filters.account_id,
        ]
        if filters.symbol is not None:
            conditions.append("symbol_matches=1")
        if filters.state is not None:
            conditions.append("state=?")
            params.append(filters.state)
        return self._bounded_headers(
            conn,
            _BROKER_HEADER_CTE
            + " SELECT classified_header.*, 'broker' AS projection, "
            + "NULL AS local_id FROM classified_header",
            conditions,
            params,
            filters,
        )

    def _manual_headers(
        self, conn: sqlite3.Connection, filters: _NormalizedActivityFilters
    ) -> list[dict[str, Any]]:
        if filters.source not in {None, "manual"}:
            return []
        if filters.state not in {None, "manual_adjustment"}:
            return []
        conditions: list[str] = []
        params: list[object] = []
        if filters.account_id is not None:
            conditions.append("portfolio_account_id=?")
            params.append(filters.account_id)
        if filters.symbol is not None:
            conditions.append("UPPER(symbol)=?")
            params.append(filters.symbol)
        sql = """
        WITH manual_header AS (
            SELECT a.id AS local_id,
                   'manual:' || a.id AS activity_id,
                   a.occurred_at_utc,
                   a.account_id AS portfolio_account_id,
                   a.position_id,
                   a.action,
                   COALESCE(
                     (
                       SELECT json_extract(c2.after_json, '$')
                       FROM portfolio_manual_adjustments a2
                       JOIN portfolio_manual_adjustment_changes c2
                         ON c2.adjustment_id=a2.id AND c2.field='symbol'
                       WHERE a2.position_id=a.position_id AND a2.id<=a.id
                       ORDER BY a2.id DESC LIMIT 1
                     ),
                     p.symbol
                   ) AS symbol,
                   'manual' AS projection
            FROM portfolio_manual_adjustments a
            JOIN portfolio_positions p ON p.id=a.position_id
        )
        SELECT * FROM manual_header
        """
        return self._bounded_headers(conn, sql, conditions, params, filters)

    def _unmatched_headers(
        self, conn: sqlite3.Connection, filters: _NormalizedActivityFilters
    ) -> list[dict[str, Any]]:
        if filters.source not in {None, "broker"}:
            return []
        if filters.state not in {None, "unmatched"}:
            return []
        conditions: list[str] = []
        params: list[object] = []
        if filters.account_id is not None:
            conditions.append("portfolio_account_id=?")
            params.append(filters.account_id)
        if filters.symbol is not None:
            conditions.append("UPPER(symbol)=?")
            params.append(filters.symbol)
        sql = """
        SELECT id AS local_id,
               'unmatched:' || id AS activity_id,
               to_as_of_utc AS occurred_at_utc,
               portfolio_account_id,
               symbol,
               asset_class,
               currency,
               from_run_id,
               to_run_id,
               from_as_of_utc,
               to_as_of_utc,
               before_quantity,
               after_quantity,
               expected_quantity,
               residual_quantity,
               execution_coverage,
               reason_code,
               'unmatched' AS projection
        FROM portfolio_unmatched_position_changes
        """
        return self._bounded_headers(conn, sql, conditions, params, filters)

    def _history_headers(
        self, conn: sqlite3.Connection, filters: _NormalizedActivityFilters
    ) -> list[dict[str, Any]]:
        if filters.source not in {None, "system"}:
            return []
        if filters.state not in {None, "history_start"}:
            return []
        if filters.symbol is not None:
            return []
        conditions: list[str] = ["history_rank=1"]
        params: list[object] = []
        if filters.account_id is not None:
            conditions.append("portfolio_account_id=?")
            params.append(filters.account_id)
        sql = """
        WITH complete_run AS (
            SELECT r.id AS capture_run_id,
                   ra.portfolio_account_id,
                   COALESCE(MAX(s.as_of_utc), r.finished_at) AS occurred_at_utc
            FROM portfolio_capture_runs r
            JOIN portfolio_capture_run_accounts ra ON ra.capture_run_id=r.id
            LEFT JOIN portfolio_account_snapshots s
              ON s.capture_run_id=r.id
             AND s.portfolio_account_id=ra.portfolio_account_id
            WHERE r.state IN ('succeeded','partial')
              AND r.account_leg_state='complete'
              AND r.execution_leg_state='complete'
              AND r.position_leg_state='complete'
            GROUP BY r.id, ra.portfolio_account_id
        ), ranked_history AS (
            SELECT *,
                   'history:' || portfolio_account_id || ':' || capture_run_id
                     AS activity_id,
                   ROW_NUMBER() OVER (
                     PARTITION BY portfolio_account_id ORDER BY capture_run_id
                   ) AS history_rank,
                   'history' AS projection,
                   capture_run_id AS local_id
            FROM complete_run
        )
        SELECT * FROM ranked_history
        """
        return self._bounded_headers(conn, sql, conditions, params, filters)

    def _coverage_gap_headers(
        self, conn: sqlite3.Connection, filters: _NormalizedActivityFilters
    ) -> list[dict[str, Any]]:
        if filters.source not in {None, "system"}:
            return []
        if filters.state not in {None, "coverage_gap"}:
            return []
        if filters.symbol is not None:
            return []
        account_condition = []
        account_params: list[object] = []
        if filters.account_id is not None:
            account_condition.append(
                "(portfolio_account_id IS NULL OR portfolio_account_id=?)"
            )
            account_params.append(filters.account_id)
        incomplete_sql = """
        WITH account_gap AS (
            SELECT r.id AS to_run_id,
                   ra.portfolio_account_id,
                   COALESCE((
                       SELECT MAX(previous.id)
                       FROM portfolio_capture_runs previous
                       JOIN portfolio_capture_run_accounts previous_ra
                         ON previous_ra.capture_run_id=previous.id
                       WHERE previous_ra.portfolio_account_id=
                               ra.portfolio_account_id
                         AND previous.id < r.id
                         AND previous.state IN ('succeeded','partial')
                         AND previous.account_leg_state='complete'
                         AND previous.execution_leg_state='complete'
                         AND previous.position_leg_state='complete'
                   ), 0) AS from_run_id,
                   COALESCE(MAX(s.as_of_utc), r.finished_at) AS occurred_at_utc
            FROM portfolio_capture_runs r
            JOIN portfolio_capture_run_accounts ra ON ra.capture_run_id=r.id
            LEFT JOIN portfolio_account_snapshots s
              ON s.capture_run_id=r.id
             AND s.portfolio_account_id=ra.portfolio_account_id
            WHERE r.state IN ('succeeded','partial','failed','blocked','interrupted')
              AND r.execution_leg_state IN ('partial','failed','not_attempted')
            GROUP BY r.id, ra.portfolio_account_id
        ), global_gap AS (
            SELECT r.id AS to_run_id,
                   NULL AS portfolio_account_id,
                   0 AS from_run_id,
                   r.finished_at AS occurred_at_utc
            FROM portfolio_capture_runs r
            WHERE r.state IN ('succeeded','partial','failed','blocked','interrupted')
              AND r.execution_leg_state IN ('partial','failed','not_attempted')
              AND NOT EXISTS (
                SELECT 1 FROM portfolio_capture_run_accounts ra
                WHERE ra.capture_run_id=r.id
              )
        ), execution_gap AS (
            SELECT * FROM account_gap
            UNION ALL
            SELECT * FROM global_gap
        ), projected_gap AS (
            SELECT *,
                   'gap:' ||
                     COALESCE(CAST(portfolio_account_id AS TEXT), 'global') ||
                     ':' || from_run_id || ':' || to_run_id
                     AS activity_id,
                   'gap_execution' AS projection,
                   to_run_id AS local_id,
                   'execution_leg_incomplete' AS reason_code
            FROM execution_gap
        )
        SELECT * FROM projected_gap
        """
        incomplete = self._bounded_headers(
            conn,
            incomplete_sql,
            list(account_condition),
            list(account_params),
            filters,
        )

        cross_conditions: list[str] = [
            "from_run_id IS NOT NULL",
            "portfolio_et_date(from_as_of_utc) "
            "!= portfolio_et_date(occurred_at_utc)",
        ]
        cross_params: list[object] = []
        if filters.account_id is not None:
            cross_conditions.append("portfolio_account_id=?")
            cross_params.append(filters.account_id)
        cross_sql = """
        WITH complete_run AS (
            SELECT r.id AS capture_run_id,
                   ra.portfolio_account_id,
                   COALESCE(MAX(s.as_of_utc), r.finished_at) AS occurred_at_utc
            FROM portfolio_capture_runs r
            JOIN portfolio_capture_run_accounts ra ON ra.capture_run_id=r.id
            LEFT JOIN portfolio_account_snapshots s
              ON s.capture_run_id=r.id
             AND s.portfolio_account_id=ra.portfolio_account_id
            WHERE r.state IN ('succeeded','partial')
              AND r.account_leg_state='complete'
              AND r.execution_leg_state='complete'
              AND r.position_leg_state='complete'
            GROUP BY r.id, ra.portfolio_account_id
        ), sequenced_run AS (
            SELECT *,
                   LAG(capture_run_id) OVER (
                     PARTITION BY portfolio_account_id ORDER BY capture_run_id
                   ) AS from_run_id,
                   LAG(occurred_at_utc) OVER (
                     PARTITION BY portfolio_account_id ORDER BY capture_run_id
                   ) AS from_as_of_utc
            FROM complete_run
        ), projected_gap AS (
            SELECT *, capture_run_id AS to_run_id,
                   'gap:' || portfolio_account_id || ':' || from_run_id || ':' ||
                     capture_run_id
                     AS activity_id,
                   'gap_day' AS projection,
                   capture_run_id AS local_id,
                   'broker_day_gap' AS reason_code
            FROM sequenced_run
        )
        SELECT * FROM projected_gap
        """
        cross_day = self._bounded_headers(
            conn, cross_sql, cross_conditions, cross_params, filters
        )
        return incomplete + cross_day

    def _history_started_at(
        self, filters: _NormalizedActivityFilters
    ) -> str | None:
        account_clause = ""
        params: tuple[object, ...] = ()
        if filters.account_id is not None:
            account_clause = " AND ra.portfolio_account_id=?"
            params = (filters.account_id,)
        with self._connect() as conn:
            row = conn.execute(
                """
                WITH complete_run AS (
                    SELECT r.id,
                           ra.portfolio_account_id,
                           COALESCE(MAX(s.as_of_utc), r.finished_at) AS observed_at
                    FROM portfolio_capture_runs r
                    JOIN portfolio_capture_run_accounts ra ON ra.capture_run_id=r.id
                    LEFT JOIN portfolio_account_snapshots s
                      ON s.capture_run_id=r.id
                     AND s.portfolio_account_id=ra.portfolio_account_id
                    WHERE r.state IN ('succeeded','partial')
                      AND r.account_leg_state='complete'
                      AND r.execution_leg_state='complete'
                      AND r.position_leg_state='complete'
                """
                + account_clause
                + """
                    GROUP BY r.id, ra.portfolio_account_id
                ), first_run AS (
                    SELECT *, ROW_NUMBER() OVER (
                      PARTITION BY portfolio_account_id ORDER BY id
                    ) AS history_rank
                    FROM complete_run
                )
                SELECT MIN(observed_at) AS history_started_at_utc
                FROM first_run WHERE history_rank=1
                """,
                params,
            ).fetchone()
        return None if row is None else row["history_started_at_utc"]

    def _unmatched_count(self, filters: _NormalizedActivityFilters) -> int:
        if filters.source not in {None, "broker"}:
            return 0
        if filters.state not in {None, "unmatched"}:
            return 0
        conditions: list[str] = []
        params: list[object] = []
        if filters.account_id is not None:
            conditions.append("portfolio_account_id=?")
            params.append(filters.account_id)
        if filters.symbol is not None:
            conditions.append("UPPER(symbol)=?")
            params.append(filters.symbol)
        if filters.date_from_utc is not None:
            conditions.append("to_as_of_utc >= ?")
            params.append(filters.date_from_utc)
        if filters.date_to_utc is not None:
            conditions.append("to_as_of_utc < ?")
            params.append(filters.date_to_utc)
        sql = "SELECT COUNT(*) AS unmatched_count FROM portfolio_unmatched_position_changes"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        with self._connect() as conn:
            row = conn.execute(sql, params).fetchone()
        return int(row["unmatched_count"])

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
    def _load_manual_changes(
        conn: sqlite3.Connection, adjustment_ids: list[int]
    ) -> dict[int, list[ActivityFieldChange]]:
        if not adjustment_ids:
            return {}
        placeholders = ",".join("?" for _ in adjustment_ids)
        result = {adjustment_id: [] for adjustment_id in adjustment_ids}
        for row in conn.execute(
            f"""
            SELECT adjustment_id, field, before_json, after_json
            FROM portfolio_manual_adjustment_changes
            WHERE adjustment_id IN ({placeholders})
            ORDER BY adjustment_id, field
            """,
            adjustment_ids,
        ):
            result[int(row["adjustment_id"])].append(
                ActivityFieldChange(
                    field=row["field"],
                    before=(
                        None
                        if row["before_json"] is None
                        else json.loads(row["before_json"])
                    ),
                    after=(
                        None
                        if row["after_json"] is None
                        else json.loads(row["after_json"])
                    ),
                )
            )
        return result

    @staticmethod
    def _load_selected_annotations(
        conn: sqlite3.Connection, headers: list[dict[str, Any]]
    ) -> dict[str, ActivityAnnotation]:
        result: dict[str, ActivityAnnotation] = {}
        for header in headers:
            target_kind = (
                "manual_adjustment"
                if header["projection"] == "manual"
                else "unmatched"
            )
            row = conn.execute(
                """
                SELECT intent_label, note, updated_at_utc
                FROM portfolio_activity_annotations
                WHERE target_kind=? AND portfolio_account_id=? AND target_ref=?
                """,
                (
                    target_kind,
                    int(header["portfolio_account_id"]),
                    str(header["local_id"]),
                ),
            ).fetchone()
            if row is not None:
                result[header["activity_id"]] = ActivityAnnotation(
                    intent_label=row["intent_label"],
                    note=row["note"],
                    updated_at_utc=row["updated_at_utc"],
                )
        return result

    def _item_from_header(
        self,
        conn: sqlite3.Connection,
        header: dict[str, Any],
        account_map: dict[int, ActivityAccount],
        fills_by_activity: dict[str, list[ActivityFill]],
        manual_changes: dict[int, list[ActivityFieldChange]],
        annotations: dict[str, ActivityAnnotation],
    ) -> PortfolioActivityItem:
        projection = header["projection"]
        activity_id = header["activity_id"]
        if projection == "broker":
            account_id = int(header["portfolio_account_id"])
            return self._broker_item(
                conn,
                header,  # type: ignore[arg-type]
                account_map[account_id],
                fills_by_activity[activity_id],
            )
        if projection == "manual":
            adjustment_id = int(header["local_id"])
            return ManualActivityItem(
                id=activity_id,
                kind="manual_adjustment",
                occurred_at_utc=header["occurred_at_utc"],
                account=account_map[int(header["portfolio_account_id"])],
                symbol=header["symbol"],
                source="manual",
                state="manual_adjustment",
                annotation=annotations.get(activity_id),
                position_id=int(header["position_id"]),
                action=header["action"],
                changes=manual_changes[adjustment_id],
            )
        if projection == "unmatched":
            return UnmatchedActivityItem(
                id=activity_id,
                kind="unmatched",
                occurred_at_utc=header["occurred_at_utc"],
                account=account_map[int(header["portfolio_account_id"])],
                symbol=header["symbol"],
                asset_class=header["asset_class"],
                currency=header["currency"],
                source="broker",
                state="unmatched",
                annotation=annotations.get(activity_id),
                from_run_id=int(header["from_run_id"]),
                to_run_id=int(header["to_run_id"]),
                from_as_of_utc=header["from_as_of_utc"],
                to_as_of_utc=header["to_as_of_utc"],
                before_quantity=float(header["before_quantity"]),
                after_quantity=float(header["after_quantity"]),
                expected_quantity=float(header["expected_quantity"]),
                residual_quantity=float(header["residual_quantity"]),
                execution_coverage=header["execution_coverage"],
                reason_code=header["reason_code"],
            )
        if projection == "history":
            return HistoryStartItem(
                id=activity_id,
                kind="history_start",
                occurred_at_utc=header["occurred_at_utc"],
                account=account_map[int(header["portfolio_account_id"])],
                source="system",
                state="history_start",
                capture_run_id=int(header["capture_run_id"]),
            )
        if projection == "gap_execution":
            raw_account_id = header["portfolio_account_id"]
            account_id = None if raw_account_id is None else int(raw_account_id)
            previous = (
                None
                if account_id is None
                else self._previous_complete_run(
                    conn, account_id=account_id, before_run_id=int(header["to_run_id"])
                )
            )
            return CoverageGapItem(
                id=activity_id,
                kind="coverage_gap",
                occurred_at_utc=header["occurred_at_utc"],
                account=None if account_id is None else account_map[account_id],
                source="system",
                state="coverage_gap",
                from_run_id=None if previous is None else int(previous["capture_run_id"]),
                to_run_id=int(header["to_run_id"]),
                from_as_of_utc=None if previous is None else previous["observed_at"],
                to_as_of_utc=header["occurred_at_utc"],
                reason_code="execution_leg_incomplete",
            )
        return CoverageGapItem(
            id=activity_id,
            kind="coverage_gap",
            occurred_at_utc=header["occurred_at_utc"],
            account=account_map[int(header["portfolio_account_id"])],
            source="system",
            state="coverage_gap",
            from_run_id=int(header["from_run_id"]),
            to_run_id=int(header["to_run_id"]),
            from_as_of_utc=header["from_as_of_utc"],
            to_as_of_utc=header["occurred_at_utc"],
            reason_code="broker_day_gap",
        )

    @staticmethod
    def _previous_complete_run(
        conn: sqlite3.Connection, *, account_id: int, before_run_id: int
    ) -> sqlite3.Row | None:
        return conn.execute(
            """
            SELECT r.id AS capture_run_id,
                   COALESCE(MAX(s.as_of_utc), r.finished_at) AS observed_at
            FROM portfolio_capture_runs r
            JOIN portfolio_capture_run_accounts ra ON ra.capture_run_id=r.id
            LEFT JOIN portfolio_account_snapshots s
              ON s.capture_run_id=r.id
             AND s.portfolio_account_id=ra.portfolio_account_id
            WHERE ra.portfolio_account_id=? AND r.id < ?
              AND r.state IN ('succeeded','partial')
              AND r.account_leg_state='complete'
              AND r.execution_leg_state='complete'
              AND r.position_leg_state='complete'
            GROUP BY r.id
            ORDER BY r.id DESC LIMIT 1
            """,
            (account_id, before_run_id),
        ).fetchone()

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
