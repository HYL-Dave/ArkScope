"""
universe_scope — THE ticker-scope resolver (3e-E).

The active Universe in the local profile DB is the single runtime authority for
"which tickers" (locked: config files are bootstrap/seed, not authority;
config/tickers_core.json no longer serves any runtime default). Every consumer —
the app scheduler, daily_update --scope active-universe, and the collectors' own
--scope flag — resolves through this one read-only query.

Self-contained on purpose (sqlite3 + os only): collectors lazy-import this from
script context where heavier src imports are unwelcome.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]


def resolve_active_universe() -> List[str]:
    """Active-universe tickers from the local profile DB — physically read-only
    (uri mode=ro). Returns [] when the DB/table is unavailable (callers decide
    whether that is fatal; for collection scopes it should be)."""
    db_path = os.environ.get("ARKSCOPE_PROFILE_DB") or str(
        _REPO_ROOT / "data" / "profile_state.db")
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                "SELECT DISTINCT ticker FROM watchlist_memberships ORDER BY ticker"
            ).fetchall()
        finally:
            conn.close()
        return [r[0] for r in rows]
    except sqlite3.OperationalError as e:
        logger.warning(f"active-universe scope unavailable ({e})")
        return []
