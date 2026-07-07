"""Domain-partitioned IBKR client ids.

One Gateway session accepts many API clients, but each concurrent connection
needs a unique clientId — sharing one id across the prices worker, the news
worker, option tools, and manual smokes means any overlap rejects the second
connector and pollutes cross-domain diagnostics. Deriving per-domain ids from
the single IBKR_CLIENT_ID base (app-DB authority via the S-J env bridge) keeps
Settings to one field while giving every domain its own connection identity.

This is isolation hardening, NOT a throughput lever: Gateway pacing and the
shared ibkr_gateway_lock stay exactly as they are.
"""

from __future__ import annotations

import os

# Wire-level contract (Gateway logs identify domains by these ids); change only
# with a decision-log entry. options=+10 predates this module — it mirrors
# option_chain_tools' original base+10 convention. Legacy occupants to stay clear
# of: collect_ibkr_news.py defaults to 50, collect_ibkr_fundamentals.py hardcodes
# 103, and archived scan/iv scripts stomp the env with random 100–999 — keep the
# base well under 60 so derived ids never enter that band.
DOMAIN_OFFSETS = {
    "manual": 0,    # the base itself: manual smokes / legacy single-client paths
    "options": 10,  # option chain tools (readonly)
    "prices": 20,   # src.prices_runtime direct-local worker
    "news": 30,     # normalized IBKR news worker
    "iv": 40,       # reserved for the IV reboot line
    # Next 10-wide band. With the seeded base 1 the effective id is 51 —
    # deliberately DISTINCT from legacy collect_ibkr_news.py's absolute
    # default 50 (adjacent but never equal for any base, since base >= 1).
    "quotes": 50,   # ad hoc read-through quote snapshots
}

# Display labels for the Settings hint — kept HERE so adding a domain is a
# one-file change (offset + label) that the API view and UI pick up automatically.
DOMAIN_LABELS_ZH = {
    "manual": "基底",
    "options": "選擇權",
    "prices": "股價",
    "news": "新聞",
    "iv": "IV",
    "quotes": "即時股價",
}


def ibkr_client_id_for(domain: str) -> int:
    """Derived client id for a domain.

    Reads the env at call time: in the sidecar and both workers apply_env runs
    first, so the app-DB base wins there. Standalone CLIs that never bridge the
    store (e.g. the agent CLI) derive from config/.env — same family, possibly a
    different base; the guarded Settings field is authoritative only for
    sidecar-managed processes.
    """
    try:
        offset = DOMAIN_OFFSETS[domain]
    except KeyError:
        raise ValueError(
            f"unknown IBKR client-id domain: {domain!r} (known: {sorted(DOMAIN_OFFSETS)})"
        ) from None
    raw = (os.getenv("IBKR_CLIENT_ID") or "").strip() or "1"
    try:
        base = int(raw)
    except ValueError:
        # Name the env var: the prices worker keeps a 240-char error message (the
        # news worker keeps only the class), and sidecar logs get the full text.
        raise ValueError(f"IBKR_CLIENT_ID must be an integer, got {raw!r}") from None
    return base + offset
