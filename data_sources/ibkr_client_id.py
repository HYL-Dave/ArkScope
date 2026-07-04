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
# option_chain_tools' original base+10 convention.
DOMAIN_OFFSETS = {
    "manual": 0,    # the base itself: manual smokes / legacy single-client paths
    "options": 10,  # option chain tools (readonly)
    "prices": 20,   # src.prices_runtime direct-local worker
    "news": 30,     # normalized IBKR news worker
    "iv": 40,       # reserved for the IV reboot line
}


def ibkr_client_id_for(domain: str) -> int:
    """Derived client id for a domain; reads the base AFTER apply_env has run."""
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
        # worker boundaries sanitize/truncate errors — name the env var here or the
        # job payload shows a context-free "invalid literal for int()".
        raise ValueError(f"IBKR_CLIENT_ID must be an integer, got {raw!r}") from None
    return base + offset
