"""Immutable values shared by portfolio capture readers and persistence."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal


CaptureTrigger = Literal["startup", "scheduled", "manual"]
CaptureTerminalState = Literal[
    "succeeded", "partial", "failed", "blocked", "interrupted"
]
CaptureRunState = Literal[
    "running", "succeeded", "partial", "failed", "blocked", "interrupted"
]
CaptureLegState = Literal["not_attempted", "complete", "partial", "failed"]
ExecutionCoverage = Literal["complete", "incomplete", "gap"]


@dataclass(frozen=True)
class CaptureLegResult:
    state: CaptureLegState
    error_code: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class BrokerAccountRef:
    broker_account_id: str
    base_currency: str | None = None


@dataclass(frozen=True)
class AccountSnapshotObservation:
    broker_account_id: str
    as_of_utc: str
    base_currency: str | None = None
    net_liquidation: float | None = None
    total_cash_value: float | None = None
    settled_cash: float | None = None
    gross_position_value: float | None = None
    buying_power: float | None = None
    available_funds: float | None = None
    initial_margin_requirement: float | None = None
    maintenance_margin_requirement: float | None = None
    daily_realized_pnl: float | None = None
    daily_unrealized_pnl: float | None = None


@dataclass(frozen=True)
class PositionObservation:
    broker_account_id: str
    broker_con_id: str
    symbol: str
    asset_class: str
    quantity: float
    avg_cost: float | None = None
    currency: str = "USD"
    base_currency: str | None = None
    market_value: float | None = None
    unrealized_pnl: float | None = None
    realized_pnl: float | None = None
    market_value_base: float | None = None
    unrealized_pnl_base: float | None = None
    exchange: str | None = None
    local_symbol: str | None = None
    multiplier: str | None = None


@dataclass(frozen=True)
class ExecutionObservation:
    broker_account_id: str
    exec_id: str
    execution_time_utc: str
    broker_con_id: str
    symbol: str
    asset_class: str
    currency: str
    exchange: str
    side: str
    quantity: float
    price: float
    order_id: int | None = None
    perm_id: int | None = None
    client_id: int | None = None
    order_ref: str | None = None
    liquidation: int | None = None
    cumulative_quantity: float | None = None
    average_price: float | None = None
    origin: Literal["gateway", "flex"] = "gateway"


@dataclass(frozen=True)
class CommissionObservation:
    broker_account_id: str
    exec_id: str
    commission: float | None
    currency: str | None
    realized_pnl: float | None
    yield_value: float | None = None
    yield_redemption_date: int | None = None


@dataclass(frozen=True)
class BrokerCaptureResult:
    finished_at_utc: str
    discovered_accounts: tuple[BrokerAccountRef, ...]
    account_leg: CaptureLegResult
    execution_leg: CaptureLegResult
    position_leg: CaptureLegResult
    account_snapshots: tuple[AccountSnapshotObservation, ...]
    positions: tuple[PositionObservation, ...]
    executions: tuple[ExecutionObservation, ...]
    commissions: tuple[CommissionObservation, ...]


@dataclass(frozen=True)
class CaptureSettings:
    enabled: bool
    interval_minutes: int
    updated_at: str


@dataclass(frozen=True)
class CaptureRun:
    id: int
    trigger: CaptureTrigger
    state: CaptureRunState
    started_at: str
    finished_at: str | None
    account_leg_state: CaptureLegState
    execution_leg_state: CaptureLegState
    position_leg_state: CaptureLegState
    discovered_account_count: int
    new_account_count: int
    archived_activity_count: int
    inserted_execution_count: int
    inserted_commission_count: int
    unmatched_count: int
    data_conflict_count: int
    error_code: str | None
    error_detail: str | None
    effective_client_id: int
    coverage_notes: tuple[str, ...]


@dataclass(frozen=True)
class CaptureCommitResult:
    discovered_account_ids: tuple[int, ...]
    new_account_ids: tuple[int, ...]
    archived_activity_account_ids: tuple[int, ...]
    inserted_execution_count: int
    inserted_commission_count: int
    unmatched_count: int
    data_conflict_count: int


@dataclass(frozen=True)
class ProviderReadiness:
    configured: bool
    code: str | None = None
    status: str | None = None
    provider: str = "ibkr"
    field: str | None = None


class CaptureRunNotReviewable(ValueError):
    """The requested run has no complete broker-position set."""


class CaptureRunSuperseded(ValueError):
    """A newer complete broker-position observation owns the pending diff."""


class PortfolioCaptureBusy(RuntimeError):
    """Capture ownership is active, so review apply cannot take a stable snapshot."""


_CORRECTION_RE = re.compile(r"^(.+)\.(\d+)$")


def finite_or_none(value: Any, field: str) -> float | None:
    if value is None:
        return None
    try:
        normalized = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a finite number") from None
    if not math.isfinite(normalized):
        raise ValueError(f"{field} must be a finite number")
    return normalized


def correction_family(exec_id: str) -> str:
    match = _CORRECTION_RE.fullmatch(exec_id)
    return match.group(1) if match else exec_id


def _canonical_decimal(value: Any, field: str) -> str | None:
    normalized = finite_or_none(value, field)
    if normalized is None:
        return None
    decimal = Decimal(str(normalized)).normalize()
    if decimal == 0:
        decimal = Decimal(0)
    return format(decimal, "f")


def commission_content_hash(report: CommissionObservation) -> str:
    payload = {
        "exec_id": report.exec_id,
        "currency": report.currency,
        "commission": _canonical_decimal(report.commission, "commission"),
        "realized_pnl": _canonical_decimal(report.realized_pnl, "realized_pnl"),
        "yield": _canonical_decimal(report.yield_value, "yield_value"),
        "yield_redemption_date": report.yield_redemption_date,
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
