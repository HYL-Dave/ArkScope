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

# The active tickers_core tiers (``legacy_reference`` is intentionally omitted —
# it is the old reference dump, not part of the active tracked universe).
#
# Tier is RETIRED as a list/tag/priority concept (it duplicated research priority
# — if a user wants tiers they create Tier 1/2/3 as their own custom lists). These
# keys now serve ONE role: scoping the active universe (``active_universe_tickers``
# / ``config_tag_seeds``).
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


def all_universe_tickers() -> list[str]:
    """Every distinct ticker across all tiers (incl. legacy_reference), sorted.

    The local seed for the symbol catalog — so add-ticker autocomplete works
    offline / when SEC is unreachable, and always covers what we track.
    """
    core = load_tickers_core()
    seen: set[str] = set()
    for key, tier in core.items():
        if key.startswith("_") or not isinstance(tier, dict):
            continue
        for cat_key, cat_val in tier.items():
            if cat_key.startswith("_"):
                continue
            for t in _category_tickers(cat_val):
                seen.add(t.upper())
    return sorted(seen)


def active_universe_tickers() -> list[str]:
    """The ACTIVE tracked universe — every ticker across the curated tiers
    (:data:`TIER_NAMES`), EXCLUDING ``legacy_reference``, sorted.

    This is the inventory base for 全部標的 ("active-universe direct"): the
    universe is sourced from the config catalog, decoupled from list membership,
    so retiring the tier *lists* never shrinks the inventory. Distinct from
    :func:`all_universe_tickers` (which also includes ``legacy_reference`` to make
    the broad search catalog as complete as possible).
    """
    core = load_tickers_core()
    seen: set[str] = set()
    for tier_key in TIER_NAMES:
        tier = core.get(tier_key)
        if not isinstance(tier, dict):
            continue
        for cat_key, cat_val in tier.items():
            if cat_key.startswith("_"):
                continue
            for t in _category_tickers(cat_val):
                seen.add(t.upper())
    return sorted(seen)


def _prettify_category(key: str) -> str:
    """``mega_cap_tech`` → ``Mega Cap Tech`` (display label for a tickers_core category)."""
    return " ".join(w.capitalize() for w in str(key).replace("-", "_").split("_") if w)


# Category keys whose membership encodes PROVENANCE (where a ticker came from),
# not a sector — these become read-only ``provenance`` tags, not categories.
_ALPHA_PICKS_KEY = "sa_alpha_picks_auto"
_SEEKING_PREFIX = "seeking_picks_"


def config_tag_seeds() -> list[dict]:
    """Bootstrap classification tags derived from ``tickers_core.json``.

    Tier is intentionally NOT emitted (retired → priority). Each active-tier
    category contributes, by its nature:
      - ``seeking_picks_*`` → a read-only ``provenance`` "Seeking Alpha" tag PLUS
        a ``legacy:category`` for the sector hint (e.g. "Financials");
      - ``sa_alpha_picks_auto`` → a read-only ``provenance`` "Alpha Picks" tag;
      - any other category → a ``legacy:category`` tag (e.g. "Mega Cap Tech"),
        editable/takeover-able until a real provider category supersedes it.

    Returns ``{facet, value, source, tickers}`` aggregated per ``(facet, value,
    source)``; ``[]`` when the config is missing. Feeds
    :meth:`ProfileStateStore.seed_tags` (additive bootstrap).
    """
    core = load_tickers_core()
    groups: dict[tuple[str, str, str], list[str]] = {}

    def _add(facet: str, value: str, source: str, tickers: list[str]) -> None:
        bucket = groups.setdefault((facet, value, source), [])
        for t in tickers:
            u = t.upper()
            if u not in bucket:
                bucket.append(u)

    for tier_key in TIER_NAMES:
        tier = core.get(tier_key)
        if not isinstance(tier, dict):
            continue
        for cat_key, cat_val in tier.items():
            if cat_key.startswith("_"):
                continue
            tickers = _category_tickers(cat_val)
            if not tickers:
                continue
            if cat_key == _ALPHA_PICKS_KEY:
                _add("provenance", "Alpha Picks", "system", tickers)
            elif cat_key.startswith(_SEEKING_PREFIX):
                _add("provenance", "Seeking Alpha", "system", tickers)
                sector = _prettify_category(cat_key[len(_SEEKING_PREFIX):])
                if sector:
                    _add("category", sector, "legacy", tickers)
            else:
                _add("category", _prettify_category(cat_key), "legacy", tickers)

    return [
        {"facet": facet, "value": value, "source": source, "tickers": tickers}
        for (facet, value, source), tickers in groups.items()
    ]
