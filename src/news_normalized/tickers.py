"""Shared ticker canonicalization for normalized-news reads and writes."""

from __future__ import annotations

import sqlite3
from typing import Mapping


def load_ticker_aliases(conn: sqlite3.Connection) -> dict[str, str]:
    """Load one alias snapshot; pre-canonical databases safely return an empty map."""
    try:
        rows = conn.execute(
            "SELECT alias,canonical FROM ticker_aliases ORDER BY alias"
        ).fetchall()
    except sqlite3.OperationalError:
        return {}
    return {
        str(alias).strip().upper(): str(canonical).strip().upper()
        for alias, canonical in rows
    }


def canonical_ticker(ticker: str, aliases: Mapping[str, str]) -> str:
    """Normalize one ticker and resolve it through a preloaded alias snapshot."""
    value = (ticker or "").strip().upper()
    return aliases.get(value, value)
