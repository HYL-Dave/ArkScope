"""
universe_scope — THE ticker-scope resolver (3e-E).

The active Universe in the local profile DB is the single runtime authority for
"which tickers" (locked: config files are bootstrap/seed, not authority;
config/tickers_core.json no longer serves any runtime default IN THIS PATH —
the scheduler, daily_update, and the maintained collectors). Every consumer
resolves through this one read-only query.

Remaining tickers_core.json touchpoints OUTSIDE this path (scoped, not zero):
  - sa_native_host._try_ticker_sync WRITES the tier3 ``sa_alpha_picks_auto``
    bucket on every SA refresh (live, protected extension path — slated for
    retirement once the native-host path is moved under src/).

Self-contained on purpose (sqlite3 + os only): provider runners import this
without pulling in the heavier DAL stack.
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
