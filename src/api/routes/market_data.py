"""
Market-data lifecycle routes (slice 3a.1) — local SQLite bootstrap/status/validate.

Productizes the PG → local market_data.db migration so the desktop app owns it
(no CLI required): status, a background bootstrap job the UI can poll, validation,
and a persisted "use local market" toggle (stored in profile_settings, read by the
DAL at construction). Domains: 3a PRICES + 3b NEWS (articles + FTS5) + 3c-A
IV_HISTORY + FUNDAMENTALS + 3c-C FINANCIAL_CACHE (local-primary: status reports its
rows/valid/expired, but it is NOT validated against PG and NOT touched by the
incremental updater). See ``docs/design/DATA_COLLECTION_AND_LOCAL_STORAGE_PLAN.md`` §8.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.dependencies import get_profile_store
from src.api.permissions import require_db_write, require_profile_state_write
from src.market_data_admin import (
    USE_LOCAL_MARKET_KEY,
    USE_LOCAL_MARKET_STRICT_KEY,
    env_routing_enabled,
    env_strict_enabled,
    get_job,
    local_market_stats,
    local_ticker_coverage,
    read_sync_meta,
    resolve_market_db_path,
    start_bootstrap_job,
    start_update_job,
    validate_market,
)
from src.market_data_direct import summarize_trading_day_coverage
from src.news_normalized.routing import NEWS_PG_EXIT_COMPLETED_KEY
from src.news_providers import parse_news_toggle
from src.news_sync_status import overlay_news_sync_status
from src.profile_state import ProfileStateStore

router = APIRouter(tags=["market-data"])

_TRUTHY = ("1", "true", "yes", "on")


def _setting_truthy(store: ProfileStateStore, key: str) -> bool:
    return (store.get_setting(key) or "").strip().lower() in _TRUTHY


def _news_pg_exit_audit_state(db_path: str) -> bool | None:
    path = Path(db_path)
    if not path.exists():
        return False
    try:
        uri = f"{path.resolve().as_uri()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        try:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                ("news_pg_exit_runs",),
            ).fetchone()
            if not exists:
                return False
            row = conn.execute(
                "SELECT 1 FROM news_pg_exit_runs WHERE status = 'completed' LIMIT 1"
            ).fetchone()
            return row is not None
        finally:
            conn.close()
    except sqlite3.Error:
        return None


def _manual_update_domains(store: ProfileStateStore) -> tuple[str, ...] | None:
    profile_done = parse_news_toggle(store.get_setting(NEWS_PG_EXIT_COMPLETED_KEY)) is True
    audit_state = _news_pg_exit_audit_state(resolve_market_db_path())
    if profile_done or audit_state is True or audit_state is None:
        return ("prices", "iv")
    return None


def _setting_enabled(store: ProfileStateStore) -> bool:
    return _setting_truthy(store, USE_LOCAL_MARKET_KEY)


def _strict_setting_enabled(store: ProfileStateStore) -> bool:
    return _setting_truthy(store, USE_LOCAL_MARKET_STRICT_KEY)


@router.get("/market-data/status")
def market_data_status(store: ProfileStateStore = Depends(get_profile_store)):
    """Local market-data status (PURE READ; does not touch PG).

    Reports the local per-domain stats (prices + news + iv + fundamentals + the
    local-primary financial_cache), whether routing is enabled (persisted setting or
    env override), and whether PG fallback is therefore active.
    """
    path = resolve_market_db_path()
    stats = local_market_stats(path)
    setting_on = _setting_enabled(store)
    env_on = env_routing_enabled()
    strict_setting_on = _strict_setting_enabled(store)
    strict_env_on = env_strict_enabled()
    # Routing only actually engages when enabled AND the DB exists (DAL guards this).
    routing_enabled = (setting_on or env_on) and stats["exists"]
    # Strict is a modifier of local-market routing: it only has runtime effect when
    # routing itself is active.
    strict_enabled = routing_enabled and (strict_setting_on or strict_env_on)
    sync = overlay_news_sync_status(read_sync_meta(path), path)
    return {
        "market_db": path,
        "exists": stats["exists"],
        "prices": stats["prices"],
        "news": stats["news"],
        "iv": stats["iv"],
        "fundamentals": stats["fundamentals"],
        "financial_cache": stats["financial_cache"],  # 3c-C local-primary cache (rows/valid/expired)
        "sync": sync,  # mirror domains + direct-news telemetry when its writer is active
        "use_local_market_setting": setting_on,
        "env_override": env_on,
        "local_market_strict_setting": strict_setting_on,
        "strict_env_override": strict_env_on,
        "strict_enabled": strict_enabled,
        "routing_enabled": routing_enabled,
        "pg_fallback_active": routing_enabled and not strict_enabled,
    }


@router.post("/market-data/bootstrap")
def bootstrap_route():
    """Start (or attach to) a background full rebuild of the local market DB
    (prices + news + iv + fundamentals).

    Returns the job; poll ``GET /market-data/jobs/{id}`` for progress. Idempotent
    while running. The rebuild validates ALL (PG-mirrored) domains before atomically
    swapping in, so a failure never destroys an existing good DB. The local-primary
    financial_cache is carried over (preserved), not rebuilt from PG.
    """
    require_db_write("market_bootstrap", {"db": resolve_market_db_path()})
    return start_bootstrap_job()


@router.post("/market-data/update")
def update_route(store: ProfileStateStore = Depends(get_profile_store)):
    """Start (or attach to) a background INCREMENTAL update (delta since latest;
    prices + news + iv + fundamentals before news PG exit; prices + iv after
    news/fundamentals PG-exit slices). Append-only to the live DB — routing can stay
    active. A provider/PG failure in one domain is recorded (last_error), not
    fatal to the others. Requires an existing local DB (bootstrap first)."""
    require_db_write("market_update", {"db": resolve_market_db_path()})
    return start_update_job(domains=_manual_update_domains(store))


@router.get("/market-data/jobs/{job_id}")
def market_data_job(job_id: str):
    """Poll a market-data background job (e.g. bootstrap).

    When a bootstrap finishes successfully the market DB has just appeared/changed,
    so we drop the lru_cache'd DAL → the next read re-evaluates routing (covers the
    enable-before-build order without a restart). Idempotent; the client stops
    polling at done, so this fires ~once.
    """
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    if job.get("kind") == "bootstrap_market" and job.get("status") == "done":
        from src.api.dependencies import get_dal

        get_dal.cache_clear()
    return job


@router.get("/market-data/coverage/{ticker}")
def market_data_coverage(ticker: str):
    """Per-domain LOCAL coverage for ``ticker`` (PURE READ; routing-independent).

    Reports whether the local market DB actually holds rows for this ticker in each
    domain — a fact about the local DB, NOT a claim about where a given read was
    served (per-call local-vs-PG provenance is a separate future signal). Powers the
    detail page's honest "本地覆蓋：有/無" hint.
    """
    return local_ticker_coverage(ticker)


@router.get("/market-data/trading-days")
def market_data_trading_days(
    lookback_days: int = Query(10, ge=1, le=120),
    interval: str = Query("15min"),
):
    """READ-ONLY trading-day / price-coverage diagnostics across the active universe.

    For the trailing window: weekend / US-holiday / trading-day per date, session-complete,
    and how many universe tickers are full / partial / missing (+ the ticker lists), plus a
    provider-error summary (e.g. an IBKR contract that won't resolve). PURE READ of
    ``market_data.db`` — no PG, no provider call, no write, no scheduling. Powers the
    Settings → Data Storage coverage panel.
    """
    from src.universe_scope import resolve_active_universe

    universe = list(resolve_active_universe() or [])
    return summarize_trading_day_coverage(
        universe, interval=interval, lookback_days=lookback_days,
        db_path=resolve_market_db_path(),
    )


@router.post("/market-data/validate")
def validate_route():
    """Validate the local market DB against PG per domain (row count + checksum):
    prices + news + iv + fundamentals."""
    return validate_market()


class LocalMarketToggle(BaseModel):
    enabled: bool


@router.put("/market-data/settings")
def set_local_market(
    body: LocalMarketToggle,
    store: ProfileStateStore = Depends(get_profile_store),
):
    """Persist the "use local market data" toggle (read by the DAL at startup).

    Note: routing only engages once ``market_data.db`` exists — enabling the
    toggle without a bootstrap simply keeps PG (status reflects that).
    """
    require_profile_state_write("set_use_local_market", {"enabled": body.enabled})
    store.set_setting(USE_LOCAL_MARKET_KEY, "true" if body.enabled else "false")
    # The DAL reads this setting at construction and is an lru_cache singleton, so
    # drop it → the next request rebuilds the DAL with the new routing (no restart).
    from src.api.dependencies import get_dal

    get_dal.cache_clear()
    return {"use_local_market_setting": body.enabled}
