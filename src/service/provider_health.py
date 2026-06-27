"""
provider_health — slice 3e-A read model: ONE aggregation of every persisted
health signal, per PROVIDER, in a unified status vocabulary.

PURE READ: no provider fetches, no writes, and no feature-flag 503s — a disabled
provider is a STATE in the response, not an HTTP error (unlike /macro/health and
/sa/market-news/health, which gate on their feature flags).

The per-provider DTO is ProviderRun-COMPATIBLE by design (locked fork F4): the
{status, last_success_at, last_attempt_at, last_error} fields align with the DSA
ProviderRun telemetry so Slice 5's per-call layer can plug in without reshaping
the API — but 3e deliberately ports NO DSA code.

Status vocabulary (plan §2): ``connected | stale | maintenance | no_signal |
missing_key | disabled``.
  - ``maintenance`` is DERIVED-only in v1: an IBKR signal that would read stale
    during the US-market weekend is reported as maintenance instead — gateway
    weekend maintenance is expected, not an error (locked F1+F2 directive:
    display "IBKR maintenance / last success").
Key presence is READ-ONLY (locked fork F5): presence + source
(``env`` / ``config/.env`` / ``missing``); keys stay in config/.env, no entry UI.

Signal sources merged (all already persisted; each degrades independently):
  - DatabaseBackend.query_health_stats()  — news per source / prices / iv /
    financial_cache per source (+ MAX(fetched_at))
  - sa_refresh_meta (get_sa_refresh_meta) — SA capture per-scope success/error
  - job_runs (JobRunsStore.latest_runs_by_name) — latest run per job
  - market_sync_meta (read_sync_meta)     — local mirror incremental sync
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

_NY_TZ = ZoneInfo("America/New_York")
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Heuristic "recent enough" windows (hours) per provider — v1 numbers, sized to
# each source's collection cadence with weekend allowance. None = never judged
# stale by age (cache-TTL-governed sources report connected while valid rows exist).
_THRESHOLD_HOURS: Dict[str, Optional[float]] = {
    "polygon": 48,
    "finnhub": 48,
    "ibkr": 72,
    "fred": 8 * 24,           # weekly-cadence macro jobs
    "seeking_alpha": 48,
    "sec_edgar": None,
    "financial_datasets": None,
}


def _is_us_weekend(now: datetime) -> bool:
    """Saturday/Sunday in New York — IBKR gateway maintenance territory."""
    return now.astimezone(_NY_TZ).weekday() >= 5


def _to_dt(value: Any) -> Optional[datetime]:
    """psycopg2 datetime / ISO string / None → aware UTC datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        text = value.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            if len(text) >= 5 and text[-5] in ("+", "-") and text[-4:].isdigit():
                try:
                    dt = datetime.fromisoformat(f"{text[:-2]}:{text[-2:]}")
                    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    return None
            return None
    return None


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _key_info(loaded_from_file: frozenset, app_keys: frozenset, *names: str) -> Dict[str, Any]:
    """READ-ONLY key presence for one provider (F5). ``present`` requires ALL
    ``names``. Source is the EFFECTIVE origin per var: ``app`` (injected by the
    app's data-provider store) > ``config/.env`` (set by the loader) > ``env``
    (real environment variable — present but set by neither). ``mixed`` when a
    multi-var key (IBKR host+port) spans different origins."""
    present = all(os.getenv(n) for n in names)
    if not present:
        return {"present": False, "source": "missing", "vars": list(names)}
    sources = set()
    for n in names:
        if n in app_keys:
            sources.add("app")
        elif n in loaded_from_file:
            sources.add("config/.env")
        else:
            sources.add("env")
    return {"present": True,
            "source": sources.pop() if len(sources) == 1 else "mixed",
            "vars": list(names)}


def _status(*, key_present: bool, enabled: Optional[bool],
            last_success_at: Optional[datetime], threshold_hours: Optional[float],
            now: datetime, weekend_maintenance: bool = False) -> str:
    # disabled OUTRANKS missing_key: a provider the user explicitly turned off is
    # "disabled" regardless of credentials — surfacing missing_key for it would
    # nag about a key the user does not want used.
    if enabled is False:
        return "disabled"
    if not key_present:
        return "missing_key"
    if last_success_at is None:
        return "no_signal"
    if threshold_hours is None:
        return "connected"
    age_h = (now - last_success_at).total_seconds() / 3600
    if age_h <= threshold_hours:
        return "connected"
    if weekend_maintenance and _is_us_weekend(now):
        return "maintenance"
    return "stale"


def compute_provider_health(dal: Any, now: Optional[datetime] = None) -> dict:
    """The 3e-A aggregation. Every signal fetch degrades independently —
    a failing section yields its providers ``no_signal`` + a note, never a raise."""
    now = now or datetime.now(timezone.utc)
    backend = getattr(dal, "_backend", None)
    notes: List[str] = []

    # Keys live in config/.env, not the system environment (project convention) —
    # make sure they are loaded before any os.getenv presence check (idempotent).
    loaded_file_keys: frozenset = frozenset()
    app_keys: frozenset = frozenset()
    try:
        from src.env_keys import ensure_env_loaded, keys_loaded_from_file
        ensure_env_loaded()
        loaded_file_keys = keys_loaded_from_file()
    except Exception as e:
        notes.append(f"env load failed: {e}")
    try:
        from src.data_provider_config import app_applied_keys
        app_keys = app_applied_keys()
    except Exception as e:  # noqa: BLE001
        notes.append(f"app key tracking failed: {e}")

    # --- signal collection (each best-effort) ---------------------------------
    stats: Dict[str, Any] = {}
    if backend is not None and hasattr(backend, "query_health_stats"):
        try:
            stats = backend.query_health_stats() or {}
        except Exception as e:
            notes.append(f"query_health_stats failed: {e}")

    sa_meta: Dict[str, Any] = {}
    if backend is not None and hasattr(backend, "get_sa_refresh_meta"):
        try:
            sa_meta = backend.get_sa_refresh_meta() or {}
        except Exception as e:
            notes.append(f"sa_refresh_meta failed: {e}")

    jobs: Dict[str, Any] = {}
    try:
        from src.service.job_runs_store import JobRunsStore
        jobs = JobRunsStore(dal).latest_runs_by_name() or {}
    except Exception as e:
        notes.append(f"job_runs failed: {e}")

    sync: Dict[str, Any] = {}
    direct_news: Optional[Dict[str, Any]] = None
    direct_news_enabled = False
    db_exists = False
    try:
        from src.market_data_admin import read_sync_meta, resolve_market_db_path
        from src.news_providers import use_local_news_enabled
        from src.news_sync_status import read_news_sync_status

        db_path = resolve_market_db_path()
        sync = read_sync_meta(db_path)
        db_exists = Path(db_path).exists()
        direct_news_enabled = use_local_news_enabled()
        if direct_news_enabled:
            direct_news = read_news_sync_status(db_path)
            sync = dict(sync)
            sync["news"] = direct_news
    except Exception as e:
        notes.append(f"market sync meta failed: {e}")

    fd_enabled: Optional[bool] = None
    try:
        from src.tools.analysis_tools import _is_fd_enabled
        fd_enabled = bool(_is_fd_enabled(dal))
    except Exception as e:
        notes.append(f"fd enabled check failed: {e}")

    macro_enabled: Optional[bool] = None
    try:
        from src.agents.config import get_agent_config
        macro_enabled = bool(get_agent_config().macro_calendar_enabled)
    except Exception as e:
        notes.append(f"macro config check failed: {e}")

    # --- per-source decomposition ---------------------------------------------
    # news rows: (source, latest, recent_count) per provider
    news_by_src: Dict[str, Dict[str, Any]] = {}
    for row in (stats.get("news") or {}).get("rows", []):
        news_by_src[row[0]] = {"latest": _to_dt(row[1]), "recent_7d": row[2] or 0}
    # prices rows: [(max_datetime,)] — collected via IBKR (§2)
    price_rows = (stats.get("prices") or {}).get("rows", [])
    prices_latest = _to_dt(price_rows[0][0]) if price_rows and price_rows[0] else None
    iv_rows = (stats.get("iv_history") or {}).get("rows", [])
    iv_latest = _to_dt(iv_rows[0][0]) if iv_rows and iv_rows[0] else None
    # financial_cache rows: (source, cached, expired[, latest_fetched])
    fin_by_src: Dict[str, Dict[str, Any]] = {}
    for row in (stats.get("financial_cache") or {}).get("rows", []):
        fin_by_src[row[0]] = {
            "cached": row[1] or 0,
            "expired": row[2] or 0,
            "latest_fetched": _to_dt(row[3]) if len(row) > 3 else None,
        }

    def _job_signal(prefix: str) -> Dict[str, Any]:
        """Latest success + latest error across job_runs whose name starts with prefix."""
        success: Optional[datetime] = None
        attempt: Optional[datetime] = None
        error: Optional[str] = None
        for name, row in jobs.items():
            if not name.startswith(prefix):
                continue
            fin = _to_dt(row.get("finished_at")) or _to_dt(row.get("started_at"))
            if fin and (attempt is None or fin > attempt):
                attempt = fin
            if row.get("status") == "succeeded" and fin and (success is None or fin > success):
                success = fin
            elif row.get("status") == "failed" and row.get("error"):
                error = str(row["error"])[:300]
        return {"last_success": success, "last_attempt": attempt, "last_error": error}

    providers: List[dict] = []

    def _add(pid: str, label: str, kind: str, key: Dict[str, Any], *,
             enabled: Optional[bool] = None, last_success: Optional[datetime] = None,
             last_attempt: Optional[datetime] = None, last_error: Optional[str] = None,
             weekend_maintenance: bool = False, detail: str = "",
             signals: Optional[dict] = None) -> None:
        providers.append({
            "id": pid,
            "label": label,
            "kind": kind,
            "key_present": key["present"],
            "key_source": key["source"],
            "key_vars": key["vars"],
            "enabled": enabled,
            "status": _status(
                key_present=key["present"], enabled=enabled,
                last_success_at=last_success,
                threshold_hours=_THRESHOLD_HOURS.get(pid), now=now,
                weekend_maintenance=weekend_maintenance,
            ),
            "last_success_at": _iso(last_success),
            "last_attempt_at": _iso(last_attempt),
            "last_error": last_error,
            "detail": detail,
            "signals": signals or {},
        })

    # IBKR — gateway: prices + iv + its news feed; host/port = the "key" (F5)
    ibkr_news = news_by_src.get("ibkr", {})
    ibkr_success = max(filter(None, [prices_latest, iv_latest, ibkr_news.get("latest")]),
                       default=None)
    _add(
        "ibkr", "IBKR Gateway", "market",
        _key_info(loaded_file_keys, app_keys, "IBKR_HOST", "IBKR_PORT"),
        last_success=ibkr_success,
        weekend_maintenance=True,
        detail=(f"prices latest {_iso(prices_latest) or '—'} · iv latest "
                f"{_iso(iv_latest) or '—'} · news 7d {ibkr_news.get('recent_7d', 0)}"),
        signals={"prices_latest": _iso(prices_latest), "iv_latest": _iso(iv_latest),
                 "news_latest": _iso(ibkr_news.get("latest")),
                 "news_recent_7d": ibkr_news.get("recent_7d", 0)},
    )

    for pid, label in (("polygon", "Polygon"), ("finnhub", "Finnhub")):
        n = news_by_src.get(pid, {})
        direct = (direct_news or {}).get("providers", {}).get(pid) if direct_news_enabled else None
        _add(
            pid, label, "news",
            _key_info(loaded_file_keys, app_keys, f"{pid.upper()}_API_KEY"),
            last_success=(_to_dt(direct.get("last_success")) if direct else None)
            if direct_news_enabled else n.get("latest"),
            last_attempt=(_to_dt(direct.get("last_attempt")) if direct else None),
            last_error=(direct.get("last_error") if direct else None),
            detail=f"news latest {_iso(n.get('latest')) or '—'} · 7d {n.get('recent_7d', 0)}",
            signals={
                "news_latest": _iso(n.get("latest")),
                "news_recent_7d": n.get("recent_7d", 0),
                "direct_sync": direct,
            },
        )

    fred = _job_signal("fetch_fred")
    _add(
        "fred", "FRED", "macro",
        _key_info(loaded_file_keys, app_keys, "FRED_API_KEY"),
        enabled=macro_enabled,
        last_success=fred["last_success"], last_attempt=fred["last_attempt"],
        last_error=fred["last_error"],
        detail=f"latest fred job success {_iso(fred['last_success']) or '—'}",
        signals={"jobs_prefix": "fetch_fred"},
    )

    # SEC EDGAR — free, no key; TTL-governed cache, never age-judged
    sec = fin_by_src.get("sec_edgar", {})
    _add(
        "sec_edgar", "SEC EDGAR", "fundamentals",
        {"present": True, "source": "not_required", "vars": []},
        last_success=sec.get("latest_fetched") if sec.get("cached") else None,
        detail=f"cache {sec.get('cached', 0)} valid · {sec.get('expired', 0)} expired",
        signals=dict(sec, latest_fetched=_iso(sec.get("latest_fetched"))) if sec else {},
    )

    fd = fin_by_src.get("financial_datasets", {})
    _add(
        "financial_datasets", "Financial Datasets (paid)", "fundamentals",
        _key_info(loaded_file_keys, app_keys, "FINANCIAL_DATASETS_API_KEY"),
        enabled=fd_enabled,
        last_success=fd.get("latest_fetched") if fd.get("cached") else None,
        detail=f"cache {fd.get('cached', 0)} valid · {fd.get('expired', 0)} expired",
        signals=dict(fd, latest_fetched=_iso(fd.get("latest_fetched"))) if fd else {},
    )

    # Seeking Alpha — extension capture path; no API key
    sa_success: Optional[datetime] = None
    sa_attempt: Optional[datetime] = None
    sa_error: Optional[str] = None
    sa_ok = True
    for scope, meta in (sa_meta or {}).items():
        s = _to_dt(meta.get("last_success_at"))
        a = _to_dt(meta.get("last_attempt_at"))
        if s and (sa_success is None or s > sa_success):
            sa_success = s
        if a and (sa_attempt is None or a > sa_attempt):
            sa_attempt = a
        if not meta.get("ok", True):
            sa_ok = False
            sa_error = sa_error or meta.get("last_error")
    mn = jobs.get("sa_market_news_refresh") or {}
    mn_fin = _to_dt(mn.get("finished_at"))
    if mn.get("status") == "succeeded" and mn_fin and (sa_success is None or mn_fin > sa_success):
        sa_success = mn_fin
    _add(
        "seeking_alpha", "Seeking Alpha (extension)", "capture",
        {"present": True, "source": "not_required", "vars": []},
        last_success=sa_success, last_attempt=sa_attempt,
        last_error=sa_error if not sa_ok else None,
        detail=f"capture last success {_iso(sa_success) or '—'}"
               + ("" if sa_ok else " · last refresh FAILED"),
        signals={"refresh_meta": sa_meta, "market_news_job": bool(mn)},
    )

    return {
        "generated_at": _iso(now),
        "providers": providers,
        "jobs": jobs,                       # latest run per job_name (raw passthrough)
        "local_market": {"db_exists": db_exists, "sync": sync},
        "notes": notes,                     # per-section degradation, if any
    }
