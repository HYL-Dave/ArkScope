"""Read one truthful portfolio capture from a synchronized IBKR session."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
import sys
import time
from typing import Any, Callable

from data_sources.ibkr_client_id import ibkr_client_id_for
from data_sources.ibkr_source import IBKRDataSource
from src.portfolio_capture_types import (
    AccountSnapshotObservation,
    BrokerAccountRef,
    BrokerCaptureResult,
    CaptureLegResult,
    CommissionObservation,
    ExecutionObservation,
    PositionObservation,
)


_source_factory: Callable[..., IBKRDataSource] = IBKRDataSource
_PNL_WAIT_SECONDS = 2.0
_IB_UNSET_DOUBLE = sys.float_info.max

_ACCOUNT_FIELDS = {
    "NetLiquidation": "net_liquidation",
    "TotalCashValue": "total_cash_value",
    "SettledCash": "settled_cash",
    "GrossPositionValue": "gross_position_value",
    "BuyingPower": "buying_power",
    "AvailableFunds": "available_funds",
    "InitMarginReq": "initial_margin_requirement",
    "MaintMarginReq": "maintenance_margin_requirement",
}


@dataclass
class _LegStatus:
    partial_code: str | None = None
    partial_detail: str | None = None
    failed_code: str | None = None
    failed_detail: str | None = None

    def partial(self, code: str, exc: BaseException | None = None) -> None:
        if self.partial_code is None:
            self.partial_code = code
            self.partial_detail = type(exc).__name__ if exc is not None else None

    def fail(self, code: str, exc: BaseException | None = None) -> None:
        if self.failed_code is None:
            self.failed_code = code
            self.failed_detail = type(exc).__name__ if exc is not None else None

    def result(self) -> CaptureLegResult:
        if self.failed_code is not None:
            return CaptureLegResult(
                "failed", self.failed_code, self.failed_detail
            )
        if self.partial_code is not None:
            return CaptureLegResult(
                "partial", self.partial_code, self.partial_detail
            )
        return CaptureLegResult("complete")


def read_ibkr_capture() -> BrokerCaptureResult:
    source = _source_factory(
        client_id=ibkr_client_id_for("portfolio_capture"),
        readonly=True,
    )
    try:
        if not source.connect():
            return _failed_capture("ibkr_connection_failed")
        ib = getattr(source, "_ib", None)
        if ib is None:
            return _failed_capture("ibkr_session_missing")
        return _read_connected_capture(ib)
    finally:
        source.disconnect()


def _failed_capture(code: str) -> BrokerCaptureResult:
    finished_at = _utc_now()
    failed = CaptureLegResult("failed", code)
    return BrokerCaptureResult(
        finished_at_utc=finished_at,
        discovered_accounts=(),
        account_leg=failed,
        execution_leg=failed,
        position_leg=failed,
        account_snapshots=(),
        positions=(),
        executions=(),
        commissions=(),
    )


def _read_connected_capture(ib: Any) -> BrokerCaptureResult:
    account_status = _LegStatus()
    execution_status = _LegStatus()
    position_status = _LegStatus()
    account_ids: set[str] = set()

    managed_accounts = _read_rows(
        ib,
        "managedAccounts",
        account_status,
        "ibkr_managed_accounts_failed",
        failure_is_partial=True,
    )
    if managed_accounts is not None:
        for raw_account in managed_accounts:
            account = _text(raw_account)
            if account:
                account_ids.add(account)
            else:
                account_status.partial("ibkr_account_rows_invalid")

    summary_rows = _read_rows(
        ib,
        "accountSummary",
        account_status,
        "ibkr_account_summary_failed",
    )
    value_rows = _read_rows(
        ib,
        "accountValues",
        account_status,
        "ibkr_account_values_failed",
        failure_is_partial=True,
    )
    summary_by_account, explicit_bases = _parse_account_summary(
        summary_rows, account_ids, account_status
    )
    base_hints = _parse_base_hints(value_rows, account_ids, account_status)

    fill_rows = _read_rows(
        ib,
        "fills",
        execution_status,
        "ibkr_fills_failed",
    )
    executions, commissions = _parse_fills(
        fill_rows, account_ids, execution_status
    )

    raw_positions = _read_rows(
        ib,
        "positions",
        position_status,
        "ibkr_positions_failed",
    )
    raw_portfolio = _read_rows(
        ib,
        "portfolio",
        position_status,
        "ibkr_portfolio_failed",
    )
    positions = _parse_positions(
        raw_positions,
        raw_portfolio,
        account_ids,
        position_status,
    )

    base_by_account = _resolve_base_currencies(
        account_ids, explicit_bases, base_hints, account_status
    )
    pnl_by_account = _read_daily_pnl(
        ib, account_ids, account_status
    )
    finished_at = _utc_now()
    snapshots = _build_account_snapshots(
        account_ids,
        summary_by_account,
        base_by_account,
        pnl_by_account,
        finished_at,
        account_status,
    )
    positions = tuple(
        PositionObservation(
            **{
                **position.__dict__,
                "base_currency": base_by_account.get(
                    position.broker_account_id
                ),
            }
        )
        for position in positions
    )
    discovered = tuple(
        BrokerAccountRef(account, base_by_account.get(account))
        for account in sorted(account_ids)
    )
    return BrokerCaptureResult(
        finished_at_utc=finished_at,
        discovered_accounts=discovered,
        account_leg=account_status.result(),
        execution_leg=execution_status.result(),
        position_leg=position_status.result(),
        account_snapshots=snapshots,
        positions=positions,
        executions=executions,
        commissions=commissions,
    )


def _read_rows(
    ib: Any,
    method_name: str,
    status: _LegStatus,
    error_code: str,
    *,
    failure_is_partial: bool = False,
) -> list[Any] | None:
    try:
        raw = getattr(ib, method_name)()
        if raw is None or isinstance(raw, (str, bytes)):
            raise TypeError("provider cache is not a row collection")
        return list(raw)
    except Exception as exc:  # noqa: BLE001 - normalize provider boundary
        if failure_is_partial:
            status.partial(error_code, exc)
        else:
            status.fail(error_code, exc)
        return None


def _parse_account_summary(
    rows: list[Any] | None,
    account_ids: set[str],
    status: _LegStatus,
) -> tuple[dict[str, dict[str, list[tuple[str, Any]]]], dict[str, set[str]]]:
    by_account: dict[str, dict[str, list[tuple[str, Any]]]] = {}
    explicit_bases: dict[str, set[str]] = {}
    for row in rows or []:
        account = _text(getattr(row, "account", None))
        tag = _text(getattr(row, "tag", None))
        if not account or not tag:
            status.partial("ibkr_account_rows_invalid")
            continue
        account_ids.add(account)
        if tag == "BaseCurrency":
            candidate = _iso_currency(getattr(row, "value", None))
            if candidate is None:
                status.partial("ibkr_account_rows_invalid")
            else:
                explicit_bases.setdefault(account, set()).add(candidate)
            continue
        if tag not in _ACCOUNT_FIELDS:
            continue
        currency = _text(getattr(row, "currency", None)).upper()
        by_account.setdefault(account, {}).setdefault(tag, []).append(
            (currency, getattr(row, "value", None))
        )
    return by_account, explicit_bases


def _parse_base_hints(
    rows: list[Any] | None,
    account_ids: set[str],
    status: _LegStatus,
) -> dict[str, set[str]]:
    hints: dict[str, set[str]] = {}
    for row in rows or []:
        account = _text(getattr(row, "account", None))
        tag = _text(getattr(row, "tag", None))
        if not account:
            status.partial("ibkr_account_value_rows_invalid")
            continue
        account_ids.add(account)
        if tag not in {"Currency", "RealCurrency"}:
            continue
        candidates = {
            candidate
            for candidate in (
                _iso_currency(getattr(row, "value", None)),
                _iso_currency(getattr(row, "currency", None)),
            )
            if candidate is not None
        }
        if not candidates:
            status.partial("ibkr_account_value_rows_invalid")
            continue
        hints.setdefault(account, set()).update(candidates)
    return hints


def _resolve_base_currencies(
    account_ids: set[str],
    explicit: dict[str, set[str]],
    hints: dict[str, set[str]],
    status: _LegStatus,
) -> dict[str, str | None]:
    resolved: dict[str, str | None] = {}
    for account in account_ids:
        explicit_candidates = explicit.get(account, set())
        if len(explicit_candidates) == 1:
            resolved[account] = next(iter(explicit_candidates))
        elif len(explicit_candidates) > 1:
            status.partial("ibkr_base_currency_ambiguous")
            resolved[account] = None
        else:
            hint_candidates = hints.get(account, set())
            resolved[account] = (
                next(iter(hint_candidates))
                if len(hint_candidates) == 1
                else None
            )
    return resolved


def _build_account_snapshots(
    account_ids: set[str],
    summary: dict[str, dict[str, list[tuple[str, Any]]]],
    bases: dict[str, str | None],
    pnl: dict[str, tuple[float | None, float | None]],
    as_of: str,
    status: _LegStatus,
) -> tuple[AccountSnapshotObservation, ...]:
    snapshots = []
    for account in sorted(account_ids):
        values: dict[str, float | None] = {
            field: None for field in _ACCOUNT_FIELDS.values()
        }
        for tag, candidates in summary.get(account, {}).items():
            selected = _select_summary_value(candidates, bases.get(account))
            if selected is _AMBIGUOUS:
                status.partial("ibkr_account_summary_ambiguous")
                continue
            try:
                values[_ACCOUNT_FIELDS[tag]] = _finite(selected)
            except ValueError:
                status.partial("ibkr_account_rows_invalid")
        realized, unrealized = pnl.get(account, (None, None))
        snapshots.append(
            AccountSnapshotObservation(
                broker_account_id=account,
                as_of_utc=as_of,
                base_currency=bases.get(account),
                daily_realized_pnl=realized,
                daily_unrealized_pnl=unrealized,
                **values,
            )
        )
    return tuple(snapshots)


_AMBIGUOUS = object()


def _select_summary_value(
    candidates: list[tuple[str, Any]], base_currency: str | None
) -> Any:
    if base_currency is not None:
        matching = [value for currency, value in candidates if currency == base_currency]
        if len(matching) == 1:
            return matching[0]
        if len(matching) > 1:
            return _AMBIGUOUS
    base_rows = [value for currency, value in candidates if currency == "BASE"]
    if len(base_rows) == 1:
        return base_rows[0]
    if len(base_rows) > 1:
        return _AMBIGUOUS
    if len(candidates) == 1:
        return candidates[0][1]
    return _AMBIGUOUS


def _read_daily_pnl(
    ib: Any,
    account_ids: set[str],
    status: _LegStatus,
) -> dict[str, tuple[float | None, float | None]]:
    subscriptions: dict[str, Any] = {}
    try:
        for account in sorted(account_ids):
            try:
                subscriptions[account] = ib.reqPnL(account)
            except Exception as exc:  # noqa: BLE001 - normalize provider boundary
                status.partial("ibkr_pnl_request_failed", exc)

        deadline = time.monotonic() + _PNL_WAIT_SECONDS
        while subscriptions:
            values = {
                account: _pnl_values(subscription)
                for account, subscription in subscriptions.items()
            }
            if all(
                realized is not None and unrealized is not None
                for realized, unrealized in values.values()
            ):
                return values
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return values
            try:
                if not ib.waitOnUpdate(timeout=remaining):
                    return values
            except Exception as exc:  # noqa: BLE001 - normalize provider boundary
                status.partial("ibkr_pnl_wait_failed", exc)
                return values
        return {}
    finally:
        for account in subscriptions:
            try:
                ib.cancelPnL(account)
            except Exception as exc:  # noqa: BLE001 - normalize provider boundary
                status.partial("ibkr_pnl_cancel_failed", exc)


def _pnl_values(subscription: Any) -> tuple[float | None, float | None]:
    return (
        _optional_pnl(getattr(subscription, "realizedPnL", None)),
        _optional_pnl(getattr(subscription, "unrealizedPnL", None)),
    )


def _optional_pnl(value: Any) -> float | None:
    try:
        normalized = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(normalized) or abs(normalized) >= _IB_UNSET_DOUBLE:
        return None
    return normalized


def _parse_fills(
    rows: list[Any] | None,
    account_ids: set[str],
    status: _LegStatus,
) -> tuple[tuple[ExecutionObservation, ...], tuple[CommissionObservation, ...]]:
    executions = []
    commissions = []
    for fill in rows or []:
        try:
            execution = getattr(fill, "execution")
            contract = getattr(fill, "contract")
            account = _required_text(getattr(execution, "acctNumber", None))
            exec_id = _required_text(getattr(execution, "execId", None))
            observed = ExecutionObservation(
                broker_account_id=account,
                exec_id=exec_id,
                execution_time_utc=_execution_time(
                    getattr(execution, "time", None)
                ),
                broker_con_id=_required_id(getattr(contract, "conId", None)),
                symbol=_required_text(getattr(contract, "symbol", None)).upper(),
                asset_class=_asset_class(getattr(contract, "secType", None)),
                currency=_required_text(getattr(contract, "currency", None)).upper(),
                exchange=_required_text(
                    getattr(execution, "exchange", None)
                    or getattr(contract, "exchange", None)
                ),
                side=_required_text(getattr(execution, "side", None)).upper(),
                quantity=_finite(getattr(execution, "shares", None), required=True),
                price=_finite(getattr(execution, "price", None), required=True),
                order_id=_optional_int(getattr(execution, "orderId", None)),
                perm_id=_optional_int(getattr(execution, "permId", None)),
                client_id=_optional_int(getattr(execution, "clientId", None)),
                order_ref=_optional_text(getattr(execution, "orderRef", None)),
                liquidation=_optional_int(getattr(execution, "liquidation", None)),
                cumulative_quantity=_finite(getattr(execution, "cumQty", None)),
                average_price=_finite(getattr(execution, "avgPrice", None)),
            )
        except (AttributeError, TypeError, ValueError):
            status.partial("ibkr_execution_rows_invalid")
            continue
        executions.append(observed)
        account_ids.add(account)

        report = getattr(fill, "commissionReport", None)
        if report is None:
            continue
        try:
            report_exec_id = _optional_text(getattr(report, "execId", None))
            if report_exec_id is None:
                continue
            if report_exec_id != exec_id:
                raise ValueError("commission execution identity mismatch")
            commissions.append(
                CommissionObservation(
                    broker_account_id=account,
                    exec_id=exec_id,
                    commission=_finite(getattr(report, "commission", None)),
                    currency=_optional_text(getattr(report, "currency", None)),
                    realized_pnl=_finite(getattr(report, "realizedPNL", None)),
                    yield_value=_finite(
                        getattr(report, "yield_", getattr(report, "yield", None))
                    ),
                    yield_redemption_date=_optional_int(
                        getattr(report, "yieldRedemptionDate", None)
                    ),
                )
            )
        except (TypeError, ValueError):
            status.partial("ibkr_commission_rows_invalid")
    return tuple(executions), tuple(commissions)


def _parse_positions(
    raw_positions: list[Any] | None,
    raw_portfolio: list[Any] | None,
    account_ids: set[str],
    status: _LegStatus,
) -> tuple[PositionObservation, ...]:
    portfolio_by_key: dict[tuple[str, str], list[dict[str, float | None]]] = {}
    for row in raw_portfolio or []:
        try:
            account = _required_text(getattr(row, "account", None))
            contract = getattr(row, "contract")
            con_id = _required_id(getattr(contract, "conId", None))
            enrichment = {
                "market_value": _finite(getattr(row, "marketValue", None)),
                "unrealized_pnl": _finite(getattr(row, "unrealizedPNL", None)),
                "realized_pnl": _finite(getattr(row, "realizedPNL", None)),
            }
        except (AttributeError, TypeError, ValueError):
            status.partial("ibkr_portfolio_rows_invalid")
            continue
        account_ids.add(account)
        portfolio_by_key.setdefault((account, con_id), []).append(enrichment)

    if raw_positions == [] and raw_portfolio:
        status.partial("ibkr_position_sets_contradictory")

    positions = []
    for row in raw_positions or []:
        try:
            account = _required_text(getattr(row, "account", None))
            contract = getattr(row, "contract")
            con_id = _required_id(getattr(contract, "conId", None))
            quantity = _finite(getattr(row, "position", None), required=True)
            avg_cost = _finite(getattr(row, "avgCost", None))
            symbol = _required_text(getattr(contract, "symbol", None)).upper()
            currency = _required_text(getattr(contract, "currency", None)).upper()
            asset_class = _asset_class(getattr(contract, "secType", None))
        except (AttributeError, TypeError, ValueError):
            status.partial("ibkr_position_rows_invalid")
            continue
        account_ids.add(account)
        matches = portfolio_by_key.get((account, con_id), [])
        enrichment: dict[str, float | None] = {}
        if quantity != 0:
            if len(matches) != 1:
                status.partial("ibkr_position_enrichment_incomplete")
            else:
                enrichment = matches[0]
        elif len(matches) == 1:
            enrichment = matches[0]
        elif len(matches) > 1:
            status.partial("ibkr_position_enrichment_ambiguous")
        positions.append(
            PositionObservation(
                broker_account_id=account,
                broker_con_id=con_id,
                symbol=symbol,
                asset_class=asset_class,
                quantity=quantity,
                avg_cost=avg_cost,
                currency=currency,
                market_value=enrichment.get("market_value"),
                unrealized_pnl=enrichment.get("unrealized_pnl"),
                realized_pnl=enrichment.get("realized_pnl"),
                exchange=_optional_text(
                    getattr(contract, "primaryExchange", None)
                    or getattr(contract, "exchange", None)
                ),
                local_symbol=_optional_text(getattr(contract, "localSymbol", None)),
                multiplier=_optional_text(getattr(contract, "multiplier", None)),
            )
        )

    if raw_positions is not None and raw_portfolio is None and positions:
        status.partial("ibkr_portfolio_failed")
    return tuple(positions)


def _finite(value: Any, *, required: bool = False) -> float | None:
    if value is None or value == "":
        if required:
            raise ValueError("required numeric value is missing")
        return None
    try:
        normalized = float(value)
    except (TypeError, ValueError):
        raise ValueError("numeric value is malformed") from None
    if not math.isfinite(normalized):
        raise ValueError("numeric value is non-finite")
    return normalized


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("boolean is not an integer identity")
    return int(value)


def _required_id(value: Any) -> str:
    text = _required_text(value)
    if text == "0":
        raise ValueError("provider identity is unset")
    return text


def _required_text(value: Any) -> str:
    text = _text(value)
    if not text:
        raise ValueError("required text is missing")
    return text


def _optional_text(value: Any) -> str | None:
    return _text(value) or None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _iso_currency(value: Any) -> str | None:
    candidate = _text(value).upper()
    if len(candidate) == 3 and candidate.isalpha():
        return candidate
    return None


def _asset_class(value: Any) -> str:
    raw = _required_text(value).upper()
    return {
        "STK": "stock",
        "ETF": "etf",
        "OPT": "option",
        "CASH": "cash",
        "FX": "cash",
    }.get(raw, raw.lower())


def _execution_time(value: Any) -> str:
    if isinstance(value, datetime):
        observed = value
    elif isinstance(value, str):
        text = value.strip().replace("Z", "+00:00")
        try:
            observed = datetime.fromisoformat(text)
        except ValueError:
            try:
                observed = datetime.strptime(text, "%Y%m%d  %H:%M:%S")
            except ValueError:
                raise ValueError("execution time is malformed") from None
    else:
        raise ValueError("execution time is missing")
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)
    return observed.astimezone(timezone.utc).isoformat()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
