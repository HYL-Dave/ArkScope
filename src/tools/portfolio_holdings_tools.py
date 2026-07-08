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
    payload["accounts"] = [
        {
            key: value
            for key, value in asdict(account).items()
            if key != "broker_account_id"
        }
        for account in snapshot.accounts
    ]
    payload["source"] = "local_profile"
    return payload


def _profile_db_path() -> str:
    return os.environ.get("ARKSCOPE_PROFILE_DB") or str(
        Path(__file__).resolve().parents[2] / "data" / "profile_state.db"
    )
