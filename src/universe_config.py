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


def _prettify_category(key: str) -> str:
    """``mega_cap_tech`` → ``Mega Cap Tech`` (display tag for a tickers_core category)."""
    return " ".join(w.capitalize() for w in str(key).replace("-", "_").split("_") if w)


def config_tag_groups() -> list[dict]:
    """Classification tag groups derived from ``tickers_core.json``.

    Each named tier contributes two tag families per category:
      - a ``config:tier`` tag (e.g. "Tier 1 · Core"), and
      - a ``config:category`` tag (e.g. "Mega Cap Tech").
    ``legacy_reference`` is excluded (mirrors :func:`tier_named_lists`). Returns
    a list of ``{tag, source, tickers}`` aggregated per ``(source, tag)``; empty
    when the config is missing. Feeds ``ProfileStateStore.seed_tags`` so the
    tag axis stays decoupled from list membership.
    """
    core = load_tickers_core()
    groups: dict[tuple[str, str], list[str]] = {}

    def _add(source: str, tag: str, tickers: list[str]) -> None:
        bucket = groups.setdefault((source, tag), [])
        for t in tickers:
            u = t.upper()
            if u not in bucket:
                bucket.append(u)

    for tier_key, tier_name in TIER_NAMES.items():
        tier = core.get(tier_key)
        if not isinstance(tier, dict):
            continue
        for cat_key, cat_val in tier.items():
            if cat_key.startswith("_"):
                continue
            tickers = _category_tickers(cat_val)
            if not tickers:
                continue
            _add("config:tier", tier_name, tickers)
            _add("config:category", _prettify_category(cat_key), tickers)

    return [
        {"tag": tag, "source": source, "tickers": tickers}
        for (source, tag), tickers in groups.items()
    ]


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
