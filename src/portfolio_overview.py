"""Provider-free account overview projection for the Holdings surface."""

from __future__ import annotations

import math
from dataclasses import dataclass

from src.portfolio_capture_types import AccountSnapshotRecord
from src.portfolio_observations import PortfolioObservationStore
from src.portfolio_state import PortfolioAccount, PortfolioStore, PortfolioTotals


@dataclass(frozen=True)
class AccountValueOverview:
    capture_run_id: int
    as_of_utc: str
    base_currency: str | None
    net_liquidation: float | None
    total_cash_value: float | None
    settled_cash: float | None
    gross_position_value: float | None
    buying_power: float | None
    available_funds: float | None
    initial_margin_requirement: float | None
    maintenance_margin_requirement: float | None
    daily_realized_pnl: float | None
    daily_unrealized_pnl: float | None
    daily_total_pnl: float | None
    source: str
    as_of_kind: str


@dataclass(frozen=True)
class PortfolioAccountOverviewRow:
    id: int
    label: str
    broker: str
    broker_account_id_hash: str | None
    sync_mode: str
    base_currency: str | None
    include_in_total: bool
    canonical_last_sync_at: str | None
    latest_snapshot: AccountValueOverview | None


@dataclass(frozen=True)
class ManualPortfolioSubtotal:
    included_account_ids: list[int]
    totals: PortfolioTotals


@dataclass(frozen=True)
class PortfolioOverview:
    accounts: list[PortfolioAccountOverviewRow]
    manual_subtotal: ManualPortfolioSubtotal


def build_portfolio_overview(
    portfolio: PortfolioStore,
    observations: PortfolioObservationStore,
) -> PortfolioOverview:
    accounts = portfolio.list_accounts()
    broker_ids = {account.id for account in accounts if account.broker != "manual"}
    snapshots = observations.latest_account_snapshots(broker_ids)
    canonical_times = portfolio.last_position_sync_at_by_account(broker_ids)
    manual_ids = sorted(
        account.id
        for account in accounts
        if account.broker == "manual" and account.include_in_total
    )
    rows = [
        PortfolioAccountOverviewRow(
            id=account.id,
            label=_safe_label(account),
            broker=account.broker,
            broker_account_id_hash=account.broker_account_id_hash,
            sync_mode=account.sync_mode,
            base_currency=account.base_currency,
            include_in_total=account.include_in_total,
            canonical_last_sync_at=canonical_times.get(account.id),
            latest_snapshot=_values(snapshots.get(account.id)),
        )
        for account in accounts
    ]
    return PortfolioOverview(
        accounts=rows,
        manual_subtotal=ManualPortfolioSubtotal(
            included_account_ids=manual_ids,
            totals=portfolio.totals_for_accounts(manual_ids),
        ),
    )


def _safe_label(account: PortfolioAccount) -> str:
    raw_id = account.broker_account_id
    if raw_id and raw_id in account.label:
        if account.broker_account_id_hash:
            return f"{account.broker.upper()} · {account.broker_account_id_hash[:8]}"
        return account.broker.upper()
    return account.label


def _values(record: AccountSnapshotRecord | None) -> AccountValueOverview | None:
    if record is None:
        return None
    total = None
    if (
        record.daily_realized_pnl is not None
        and record.daily_unrealized_pnl is not None
    ):
        candidate = record.daily_realized_pnl + record.daily_unrealized_pnl
        total = candidate if math.isfinite(candidate) else None
    return AccountValueOverview(
        capture_run_id=record.capture_run_id,
        as_of_utc=record.as_of_utc,
        base_currency=record.base_currency,
        net_liquidation=record.net_liquidation,
        total_cash_value=record.total_cash_value,
        settled_cash=record.settled_cash,
        gross_position_value=record.gross_position_value,
        buying_power=record.buying_power,
        available_funds=record.available_funds,
        initial_margin_requirement=record.initial_margin_requirement,
        maintenance_margin_requirement=record.maintenance_margin_requirement,
        daily_realized_pnl=record.daily_realized_pnl,
        daily_unrealized_pnl=record.daily_unrealized_pnl,
        daily_total_pnl=total,
        source=record.source,
        as_of_kind=record.as_of_kind,
    )
