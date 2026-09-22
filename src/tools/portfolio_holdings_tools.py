"""Agent-readable local portfolio holdings tool."""

from __future__ import annotations

import os
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from src.portfolio_state import PortfolioStore
from src.tools.retained_read_results import (
    RetainedReadFailure, bounded_result, content_id, page_integer, require, valid_snapshot_id,
)


def get_portfolio_holdings(
    account_id: int | None = None,
    include_closed: bool = False,
    row_offset: int = 0,
    row_limit: int = 10,
    snapshot_id: str | None = None,
) -> dict[str, Any]:
    """Read local portfolio holdings from profile_state.db.

    This is a local read primitive: it does not sync, does not call IBKR, and
    does not mutate profile state.
    """
    try:
        require(account_id is None or page_integer(account_id, minimum=1), "portfolio_account_id_invalid")
        require(type(include_closed) is bool, "portfolio_query_invalid")
        require(page_integer(row_offset) and page_integer(row_limit, minimum=1), "portfolio_pagination_invalid")
        require(valid_snapshot_id(snapshot_id), "portfolio_snapshot_id_invalid")
        require(not row_offset or snapshot_id is not None, "portfolio_snapshot_required")
        snapshot = PortfolioStore.read_snapshot(
            _profile_db_path(), account_id=account_id, include_closed=include_closed,
            included_only=account_id is None,
        )
        payload = asdict(snapshot)
        payload["accounts"] = [_agent_account(account) for account in snapshot.accounts]
        _qualify_totals(payload)
        current_id = content_id({"version": 1, "account_id": account_id,
                                 "include_closed": include_closed, "snapshot": payload})
        require(snapshot_id is None or current_id == snapshot_id, "portfolio_snapshot_changed")
        positions = payload["positions"]
        require(row_offset <= len(positions), "portfolio_offset_out_of_range")
        payload["positions"] = positions[row_offset:row_offset + row_limit]
        payload.update(
            status="ok", source="local_profile", retrieval="stored", snapshot_id=current_id,
            empty_reason="no_retained_positions_in_scope" if not positions else None,
            valuation_basis="stored_values_not_live", totals_scope="all_open_positions_in_selected_accounts",
            totals_value_basis="sum_of_available_stored_values",
            pagination={"row_offset": row_offset, "row_count": len(payload["positions"]),
                        "total_rows": len(positions),
                        "next_row_offset": row_offset + row_limit if row_offset + row_limit < len(positions) else None},
            limitations=["local_snapshot_not_broker_authoritative", "market_values_not_refreshed_by_this_read",
                         "snapshot_id_detects_changes_not_historical_archive"],
        )
        return bounded_result("get_portfolio_holdings", payload)
    except RetainedReadFailure as exc:
        code = exc.code
    except FileNotFoundError:
        code = "portfolio_snapshot_missing"
    except KeyError:
        code = "portfolio_account_not_found"
    except (sqlite3.Error, OSError):
        code = "portfolio_store_unavailable"
    return {"status": "unavailable", "error_code": code, "source": "local_profile", "retrieval": "stored"}


def _qualify_totals(payload):
    """Do not imply full valuation coverage or add unrelated base currencies."""
    open_positions = [p for p in payload["positions"] if p["closed_at"] is None]
    accounts = {account["id"]: account for account in payload["accounts"]}
    payload["totals_coverage"] = {
        currency: {
            "position_count": totals["position_count"],
            "market_value_count": sum(p["market_value"] is not None for p in open_positions if p["currency"].upper() == currency),
            "unrealized_pnl_count": sum(p["unrealized_pnl"] is not None for p in open_positions if p["currency"].upper() == currency),
        } for currency, totals in payload["totals"]["per_currency"].items()
    }
    base_currencies = {accounts[p["account_id"]]["base_currency"] for p in open_positions}
    payload["broker_base_currency"] = None
    payload["totals_gaps"] = []
    if payload["totals"]["broker_base"] is not None:
        if len(base_currencies) == 1 and None not in base_currencies and "" not in base_currencies:
            payload["broker_base_currency"] = next(iter(base_currencies))
            if any(p["unrealized_pnl_base"] is None for p in open_positions):
                payload["totals"]["broker_base"]["unrealized_pnl"] = None
                payload["totals_gaps"].append("broker_base_unrealized_pnl_incomplete")
        else:
            payload["totals"]["broker_base"] = None
            payload["totals"]["currency_basis"] = "per_currency"
            payload["totals_gaps"].append("broker_base_currency_unverified")


def _agent_account(account: Any) -> dict[str, Any]:
    row = asdict(account)
    raw_id = row.pop("broker_account_id", None)
    label = row.get("label")
    account_hash = row.get("broker_account_id_hash")
    if raw_id and label and raw_id in label:
        row["label"] = (
            f"{str(row.get('broker') or 'broker').upper()} · {str(account_hash)[:8]}"
            if account_hash
            else str(row.get("broker") or "Broker").upper()
        )
    return row


def _profile_db_path() -> str:
    return os.environ.get("ARKSCOPE_PROFILE_DB") or str(
        Path(__file__).resolve().parents[2] / "data" / "profile_state.db"
    )
