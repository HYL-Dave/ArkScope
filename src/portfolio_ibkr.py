"""Read-only IBKR portfolio snapshot helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from data_sources.ibkr_client_id import ibkr_client_id_for
from data_sources.ibkr_source import IBKRDataSource

from src.portfolio_state import BrokerPosition, PortfolioStore


class IBKRHoldingsUnavailable(RuntimeError):
    """IBKR holdings snapshot cannot be read safely."""


@dataclass(frozen=True)
class BrokerAccountSnapshot:
    account_id: str
    label: str
    base_currency: str | None = None


@dataclass(frozen=True)
class BrokerPositionSnapshot:
    account_id: str
    con_id: str
    symbol: str
    asset_class: str
    quantity: float
    currency: str = "USD"
    avg_cost: float | None = None
    market_value: float | None = None
    unrealized_pnl: float | None = None
    market_value_base: float | None = None
    unrealized_pnl_base: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BrokerSnapshot:
    accounts: list[BrokerAccountSnapshot]
    positions: list[BrokerPositionSnapshot]


@dataclass(frozen=True)
class PortfolioSyncChange:
    kind: str
    account_id: int
    broker_account_id: str
    broker_con_id: str
    symbol: str
    quantity: float
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None


@dataclass(frozen=True)
class PortfolioSyncPreview:
    changes: list[PortfolioSyncChange]
    applies: bool


def read_ibkr_portfolio_snapshot() -> BrokerSnapshot:
    source = IBKRDataSource(client_id=ibkr_client_id_for("holdings"), readonly=True)
    try:
        if not source.connect():
            raise IBKRHoldingsUnavailable("IBKR Gateway connection failed")
        return _read_connected_ibkr(source)
    finally:
        source.disconnect()


def _read_connected_ibkr(source: IBKRDataSource) -> BrokerSnapshot:
    ib = getattr(source, "_ib", None)
    if ib is None:
        raise IBKRHoldingsUnavailable("IBKR session is not connected")

    base_currency_by_account = _base_currency_by_account(ib)
    portfolio_by_key = _portfolio_items_by_key(ib)

    positions: list[BrokerPositionSnapshot] = []
    accounts: dict[str, BrokerAccountSnapshot] = {}
    try:
        raw_positions = ib.positions()
    except Exception as exc:  # noqa: BLE001 - boundary conversion
        raise IBKRHoldingsUnavailable(f"IBKR positions read failed: {exc}") from exc

    for raw in raw_positions or []:
        account_id = str(getattr(raw, "account", "") or "").strip()
        contract = getattr(raw, "contract", None)
        con_id = str(getattr(contract, "conId", "") or "").strip()
        symbol = str(getattr(contract, "symbol", "") or "").strip().upper()
        if not account_id or not con_id or not symbol:
            continue
        currency = str(getattr(contract, "currency", "") or "USD").strip().upper()
        asset_class = _asset_class(getattr(contract, "secType", ""))
        pkey = (account_id, con_id)
        pitem = portfolio_by_key.get(pkey, {})
        accounts.setdefault(
            account_id,
            BrokerAccountSnapshot(
                account_id=account_id,
                label=f"IBKR {account_id}",
                base_currency=base_currency_by_account.get(account_id),
            ),
        )
        positions.append(
            BrokerPositionSnapshot(
                account_id=account_id,
                con_id=con_id,
                symbol=symbol,
                asset_class=asset_class,
                quantity=float(getattr(raw, "position", 0) or 0),
                avg_cost=_float_or_none(getattr(raw, "avgCost", None)),
                currency=currency,
                market_value=_float_or_none(pitem.get("market_value")),
                unrealized_pnl=_float_or_none(pitem.get("unrealized_pnl")),
                metadata={"secType": getattr(contract, "secType", None)},
            )
        )

    for account_id, base_currency in base_currency_by_account.items():
        accounts.setdefault(
            account_id,
            BrokerAccountSnapshot(
                account_id=account_id,
                label=f"IBKR {account_id}",
                base_currency=base_currency,
            ),
        )
    return BrokerSnapshot(accounts=list(accounts.values()), positions=positions)


def preview_or_apply_ibkr_snapshot(
    store: PortfolioStore,
    snapshot: BrokerSnapshot,
    *,
    apply: bool,
) -> PortfolioSyncPreview:
    account_by_broker_id = {
        account.broker_account_id: account
        for account in store.list_accounts()
        if account.broker == "ibkr" and account.broker_account_id
    }
    for broker_account in snapshot.accounts:
        existing = account_by_broker_id.get(broker_account.account_id)
        if existing is None:
            existing = store.upsert_broker_account(
                "ibkr",
                broker_account.account_id,
                broker_account.label,
                sync_mode="ibkr_review",
                base_currency=broker_account.base_currency,
            )
            account_by_broker_id[broker_account.account_id] = existing

    changes: list[PortfolioSyncChange] = []
    positions_by_account: dict[int, list[BrokerPosition]] = {}
    for broker_pos in snapshot.positions:
        account = account_by_broker_id.get(broker_pos.account_id)
        if account is None:
            account = store.upsert_broker_account(
                "ibkr",
                broker_pos.account_id,
                f"IBKR {broker_pos.account_id}",
                sync_mode="ibkr_review",
            )
            account_by_broker_id[broker_pos.account_id] = account

        existing = next(
            (
                p
                for p in store.list_positions(account_id=account.id, include_closed=True)
                if p.broker == "ibkr" and p.broker_con_id == broker_pos.con_id
            ),
            None,
        )
        after = _position_after_dict(broker_pos)
        kind = "add" if existing is None else ("update" if _position_changed(existing, broker_pos) else "unchanged")
        if kind != "unchanged":
            changes.append(
                PortfolioSyncChange(
                    kind=kind,
                    account_id=account.id,
                    broker_account_id=broker_pos.account_id,
                    broker_con_id=broker_pos.con_id,
                    symbol=broker_pos.symbol,
                    quantity=broker_pos.quantity,
                    before=_position_before_dict(existing) if existing else None,
                    after=after,
                )
            )
        positions_by_account.setdefault(account.id, []).append(_to_store_position(broker_pos))

    if apply:
        for account_id, positions in positions_by_account.items():
            store.apply_broker_positions(account_id=account_id, positions=positions, source="ibkr")
    return PortfolioSyncPreview(changes=changes, applies=apply)


def _base_currency_by_account(ib: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        rows = ib.accountSummary()
    except Exception:
        return out
    for row in rows or []:
        if getattr(row, "tag", None) == "BaseCurrency":
            account = str(getattr(row, "account", "") or "").strip()
            value = str(getattr(row, "value", "") or "").strip().upper()
            if account and value:
                out[account] = value
    return out


def _portfolio_items_by_key(ib: Any) -> dict[tuple[str, str], dict[str, float | None]]:
    out: dict[tuple[str, str], dict[str, float | None]] = {}
    try:
        rows = ib.portfolio()
    except Exception:
        return out
    for row in rows or []:
        account = str(getattr(row, "account", "") or "").strip()
        contract = getattr(row, "contract", None)
        con_id = str(getattr(contract, "conId", "") or "").strip()
        if not account or not con_id:
            continue
        out[(account, con_id)] = {
            "market_value": _float_or_none(getattr(row, "marketValue", None)),
            "unrealized_pnl": _float_or_none(getattr(row, "unrealizedPNL", None)),
        }
    return out


def _asset_class(sec_type: Any) -> str:
    raw = str(sec_type or "").strip().upper()
    if raw == "OPT":
        return "option"
    if raw in {"CASH", "FX"}:
        return "cash"
    if raw == "STK":
        return "stock"
    if raw == "ETF":
        return "etf"
    return raw.lower() or "unknown"


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_store_position(pos: BrokerPositionSnapshot) -> BrokerPosition:
    return BrokerPosition(
        broker="ibkr",
        broker_account_id=pos.account_id,
        broker_con_id=pos.con_id,
        symbol=pos.symbol,
        asset_class=pos.asset_class,
        quantity=pos.quantity,
        avg_cost=pos.avg_cost,
        currency=pos.currency,
        market_value=pos.market_value,
        unrealized_pnl=pos.unrealized_pnl,
        market_value_base=pos.market_value_base,
        unrealized_pnl_base=pos.unrealized_pnl_base,
        metadata=pos.metadata,
    )


def _position_changed(existing: Any, pos: BrokerPositionSnapshot) -> bool:
    return _position_before_dict(existing) != _position_after_dict(pos)


def _position_before_dict(pos: Any) -> dict[str, Any]:
    return {
        "symbol": pos.symbol,
        "asset_class": pos.asset_class,
        "quantity": pos.quantity,
        "avg_cost": pos.avg_cost,
        "currency": pos.currency,
        "market_value": pos.market_value,
        "unrealized_pnl": pos.unrealized_pnl,
    }


def _position_after_dict(pos: BrokerPositionSnapshot) -> dict[str, Any]:
    return {
        "symbol": pos.symbol,
        "asset_class": pos.asset_class,
        "quantity": pos.quantity,
        "avg_cost": pos.avg_cost,
        "currency": pos.currency,
        "market_value": pos.market_value,
        "unrealized_pnl": pos.unrealized_pnl,
    }
