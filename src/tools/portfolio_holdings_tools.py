"""Agent-readable local portfolio holdings tool."""

from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from src.portfolio_state import PortfolioStore


def get_portfolio_holdings(
    account_id: int | None = None,
    include_closed: bool = False,
) -> dict[str, Any]:
    """Read local portfolio holdings from profile_state.db.

    This is a local read primitive: it does not sync, does not call IBKR, and
    does not mutate profile state.
    """
    store = PortfolioStore(_profile_db_path())
    snapshot = store.snapshot(
        account_id=account_id,
        include_closed=include_closed,
        included_only=account_id is None,
    )
    payload = asdict(snapshot)
    payload["accounts"] = [_agent_account(account) for account in snapshot.accounts]
    payload["source"] = "local_profile"
    return payload


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
