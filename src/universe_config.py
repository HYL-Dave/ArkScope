"""
Explicit loader for the tracked-ticker universe (``config/tickers_core.json``).

This is the first-class config reader for the ~130-ticker tracking universe, so
the API layer does not have to reach into ``DataAccessLayer._load_json`` (a
private method) to seed watchlist tiers. The file groups tickers as
``tier → category → {"tickers": [...]}``; this module flattens each tier into a
single named list for the profile-state importer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Friendly names for the tickers_core tiers. ``legacy_reference`` is intentionally
# omitted from the default import.
TIER_NAMES = {
    "tier1_core": "Tier 1 · Core",
    "tier2_expanded": "Tier 2 · Expanded",
    "tier3_user_watchlist": "Tier 3 · Watchlist",
}


def _config_path() -> Path:
    # src/universe_config.py → parents[1] == repo root, regardless of cwd.
    return Path(__file__).resolve().parents[1] / "config" / "tickers_core.json"


def load_tickers_core() -> dict[str, Any]:
    """Load ``config/tickers_core.json`` (returns {} if missing/unreadable)."""
    path = _config_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _category_tickers(cat_val: Any) -> list[str]:
    """Tickers from one category — usually ``{"tickers": [...]}``, tolerant of a
    bare ``[...]`` list too."""
    if isinstance(cat_val, dict):
        seq = cat_val.get("tickers") or []
    elif isinstance(cat_val, list):
        seq = cat_val
    else:
        seq = []
    return [str(t) for t in seq if isinstance(t, str)]


def tier_named_lists() -> list[dict]:
    """Flatten each tier into one named list ``{name, kind='tier', tickers}``.

    Best-effort: a missing/odd config simply yields fewer (or no) tier lists.
    """
    core = load_tickers_core()
    out: list[dict] = []
    for tier_key, list_name in TIER_NAMES.items():
        tier = core.get(tier_key)
        if not isinstance(tier, dict):
            continue
        tickers: list[str] = []
        for cat_key, cat_val in tier.items():
            if cat_key.startswith("_"):
                continue
            tickers.extend(_category_tickers(cat_val))
        if tickers:
            out.append({"name": list_name, "kind": "tier", "tickers": tickers})
    return out
