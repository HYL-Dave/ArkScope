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
not_configured | missing_key | disabled``.
  - ``maintenance`` is DERIVED-only in v1: an IBKR signal that would read stale
    during the US-market weekend is reported as maintenance instead — gateway
    weekend maintenance is expected, not an error (locked F1+F2 directive:
    display "IBKR maintenance / last success").
Key presence is READ-ONLY (locked fork F5): presence + source
(``app`` / ``env`` / ``config/.env`` / ``missing``). Values stay masked; health
may suggest importing file-backed values into the app-managed provider store.

Signal sources merged (all already persisted; each degrades independently):
  - local capability ``query_health_stats()`` — news per source / prices /
    financial_cache per source (+ MAX(fetched_at))
  - sa_refresh_meta (get_sa_refresh_meta) — SA capture per-scope success/error
  - job_runs (get_job_runs_store(...).latest_runs_by_name) — latest run per job
  - market_sync_meta (read_sync_meta)     — legacy sync telemetry; prices is marked
    retired/local-authority after P0-C
  - provider_sync_runs/meta (read_news_sync_status) - current news ingest telemetry
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from src.macro_calendar.local_store import read_macro_table_stats, resolve_macro_calendar_db_path
from src.service.data_scheduler import read_macro_schedule_automation

logger = logging.getLogger(__name__)

_NY_TZ = ZoneInfo("America/New_York")
_REPO_ROOT = Path(__file__).resolve().parents[2]

# Heuristic "recent enough" windows (hours) per provider — v1 numbers, sized to
# each source's collection cadence with weekend allowance. None = never judged
# stale by age (financial sources report retained acquisition evidence separately).
_THRESHOLD_HOURS: Dict[str, Optional[float]] = {
    "massive": 48,
    "finnhub": 48,
    "ibkr": 72,
    "fred": 8 * 24,           # weekly-cadence macro jobs
    "seeking_alpha": 48,
    "sec_edgar": None,
    "financial_datasets": None,
}
_DEFAULT_THRESHOLD = object()


def _effective_threshold(pid: str, threshold_hours: Any) -> Optional[float]:
    if threshold_hours is _DEFAULT_THRESHOLD:
        return _THRESHOLD_HOURS.get(pid)
    return threshold_hours


def _is_us_weekend(now: datetime) -> bool:
    """Saturday/Sunday in New York — IBKR gateway maintenance territory."""
    return now.astimezone(_NY_TZ).weekday() >= 5


def _to_dt(value: Any) -> Optional[datetime]:
    """Datetime / ISO string / None -> aware UTC datetime."""
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


def _first_key_info(
    loaded_from_file: frozenset, app_keys: frozenset, *names: str
) -> Dict[str, Any]:
    selected = next((name for name in names if os.getenv(name)), None)
    if selected is None:
        return {"present": False, "source": "missing", "vars": list(names)}
    if selected in app_keys:
        source = "app"
    elif selected in loaded_from_file:
        source = "config/.env"
    else:
        source = "env"
    return {"present": True, "source": source, "vars": list(names)}


def _status(*, key_present: bool, enabled: Optional[bool],
            last_success_at: Optional[datetime], threshold_hours: Optional[float],
            now: datetime, weekend_maintenance: bool = False,
            config_error: Optional[dict] = None) -> str:
    # disabled OUTRANKS missing_key: a provider the user explicitly turned off is
    # "disabled" regardless of credentials — surfacing missing_key for it would
    # nag about a key the user does not want used.
    if enabled is False:
        return "disabled"
    if config_error:
        return "not_configured"
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

    loaded_file_keys: frozenset = frozenset()
    app_keys: frozenset = frozenset()
    missing_required_provider_fields = None
    try:
        from src.env_keys import keys_loaded_from_file
        loaded_file_keys = keys_loaded_from_file()
    except Exception as e:
        notes.append(f"env provenance read failed: {e}")
    try:
        from src.data_provider_config import app_applied_keys, missing_required_provider_fields
        app_keys = app_applied_keys()
    except Exception as e:  # noqa: BLE001
        notes.append(f"app key tracking failed: {e}")

    def _config_error(pid: str) -> Optional[dict]:
        if missing_required_provider_fields is None:
            return None
        try:
            missing = missing_required_provider_fields(pid)
            return missing[0] if missing else None
        except Exception as e:  # noqa: BLE001
            notes.append(f"{pid} config check failed: {e}")
            return None

    # --- signal collection (each best-effort) ---------------------------------
    stats: Dict[str, Any] = {}
    if backend is not None:
        try:
            stats = backend.query_health_stats() or {}
        except Exception as e:
            notes.append(f"query_health_stats failed: {e}")

    sa_meta: Dict[str, Any] = {}
    if backend is not None:
        try:
            sa_meta = backend.get_sa_refresh_meta() or {}
        except Exception as e:
            notes.append(f"sa_refresh_meta failed: {e}")

    jobs: Dict[str, Any] = {}
    sa_extension_summary: Dict[str, Any] = {}
    try:
        from src.service.job_runs_store import get_job_runs_store
        job_store = get_job_runs_store(dal)
        jobs = job_store.latest_runs_by_name() or {}
        structured = job_store.structured_extension_summary_by_name(
            ["sa_alpha_picks_refresh", "sa_market_news_refresh"]
        )
        if structured is None:
            notes.append("structured extension job_runs summary unavailable")
        else:
            sa_extension_summary = structured
    except Exception as e:
        notes.append(f"job_runs failed: {e}")

    sync: Dict[str, Any] = {}
    direct_news: Optional[Dict[str, Any]] = None
    db_exists = False
    try:
        from src.market_data_admin import (
            overlay_price_authority,
            read_sync_meta,
            resolve_market_db_path,
        )
        from src.news_sync_status import read_news_sync_status

        db_path = resolve_market_db_path()
        sync = overlay_price_authority(read_sync_meta(db_path))
        sync = dict(sync)
        # Legacy news cannot survive a failed path probe or current read.
        sync["news"] = None
        db_exists = Path(db_path).exists()
        direct_news = read_news_sync_status(db_path)
        sync["news"] = direct_news
    except Exception as e:
        notes.append(f"market sync meta failed: {e}")

    fd_enabled: Optional[bool] = None
    try:
        from src.tools.analysis_tools import _is_fd_enabled
        fd_enabled = bool(_is_fd_enabled(dal))
    except Exception as e:
        notes.append(f"fd enabled check failed: {e}")

    macro_schedule: Optional[Dict[str, bool]] = None
    try:
        macro_schedule = read_macro_schedule_automation()
        if macro_schedule is None:
            notes.append("macro schedule read failed")
    except Exception as e:
        notes.append(f"macro schedule read failed: {e}")

    macro_stats: Dict[str, Any] = {}
    try:
        macro_stats = read_macro_table_stats(resolve_macro_calendar_db_path())
    except Exception as e:
        notes.append(f"macro local stats failed: {e}")

    # --- per-source decomposition ---------------------------------------------
    # news rows: (source, latest, recent_count) per provider
    news_by_src: Dict[str, Dict[str, Any]] = {}
    for row in (stats.get("news") or {}).get("rows", []):
        news_by_src[row[0]] = {"latest": _to_dt(row[1]), "recent_7d": row[2] or 0}
    # prices rows: [(max_datetime,)] — collected via IBKR (§2)
    price_rows = (stats.get("prices") or {}).get("rows", [])
    prices_latest = _to_dt(price_rows[0][0]) if price_rows and price_rows[0] else None
    # TTL controls reuse, not whether a successful acquisition happened.
    financial_stats = stats.get("financial_cache")
    financial_readable = isinstance(financial_stats, dict) and not financial_stats.get("error")
    fin_by_src: Dict[str, Dict[str, Any]] = {}
    for row in (financial_stats.get("rows", []) if financial_readable else []):
        fin_by_src[row[0]] = {
            "cached": row[1] or 0,
            "expired": row[2] or 0,
            "latest_fetched": _to_dt(row[3]) if len(row) > 3 else None,
        }

    def _financial_signals(source: str) -> Dict[str, Any]:
        record = fin_by_src.get(source, {})
        if not financial_readable:
            evidence = "unavailable"
        elif not (record.get("cached", 0) + record.get("expired", 0)):
            evidence = "empty"
        elif record.get("latest_fetched") is None:
            evidence = "timestamp_unknown"
        else:
            evidence = "recorded"
        return dict(record, latest_fetched=_iso(record.get("latest_fetched")),
                    acquisition_evidence=evidence)

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
             signals: Optional[dict] = None,
             disabled_reason: Optional[str] = None,
             config_error: Optional[dict] = None,
             last_attempt_outcome: Optional[str] = None,
             last_attempt_scope: Optional[str] = None,
             last_error_at: Optional[datetime] = None,
             last_error_scope: Optional[str] = None,
             last_complete: Optional[datetime] = None,
             last_complete_scope: Optional[str] = None,
             threshold_hours: Any = _DEFAULT_THRESHOLD) -> None:
        effective_threshold = _effective_threshold(pid, threshold_hours)
        providers.append({
            "id": pid,
            "label": label,
            "kind": kind,
            "key_present": key["present"],
            "key_source": key["source"],
            "key_import_suggested": key["source"] == "config/.env" and config_error is None,
            "key_vars": key["vars"],
            "enabled": enabled,
            "disabled_reason": disabled_reason,
            "status": _status(
                key_present=key["present"], enabled=enabled,
                last_success_at=last_success,
                threshold_hours=effective_threshold, now=now,
                weekend_maintenance=weekend_maintenance,
                config_error=config_error,
            ),
            "config_error": config_error,
            "last_success_at": _iso(last_success),
            "last_attempt_at": _iso(last_attempt),
            "last_error": last_error,
            "last_attempt_outcome": last_attempt_outcome,
            "last_attempt_scope": last_attempt_scope,
            "last_error_at": _iso(last_error_at),
            "last_error_scope": last_error_scope,
            "last_complete_at": _iso(last_complete),
            "last_complete_scope": last_complete_scope,
            "detail": detail,
            "signals": signals or {},
        })

    # IBKR — gateway: prices + its news feed; host/port = the "key" (F5)
    ibkr_news = news_by_src.get("ibkr", {})
    ibkr_success = max(filter(None, [prices_latest, ibkr_news.get("latest")]),
                       default=None)
    _add(
        "ibkr", "IBKR Gateway", "market",
        _key_info(loaded_file_keys, app_keys, "IBKR_HOST", "IBKR_PORT"),
        config_error=_config_error("ibkr"),
        last_success=ibkr_success,
        weekend_maintenance=True,
        detail=(f"prices latest {_iso(prices_latest) or '—'} · "
                f"news 7d {ibkr_news.get('recent_7d', 0)}"),
        signals={"prices_latest": _iso(prices_latest),
                 "news_latest": _iso(ibkr_news.get("latest")),
                 "news_recent_7d": ibkr_news.get("recent_7d", 0)},
    )

    for pid, source_pid, label in (
        ("massive", "polygon", "Massive"),
        ("finnhub", "finnhub", "Finnhub"),
    ):
        n = news_by_src.get(source_pid, {})
        direct = (direct_news or {}).get("providers", {}).get(source_pid)
        key = (
            _first_key_info(
                loaded_file_keys,
                app_keys,
                "MASSIVE_API_KEY",
            )
            if pid == "massive"
            else _key_info(loaded_file_keys, app_keys, "FINNHUB_API_KEY")
        )
        _add(
            pid, label, "news",
            key,
            config_error=_config_error(pid),
            last_success=(_to_dt(direct.get("last_success")) if direct else None),
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
    macro_obs = macro_stats.get("macro_observations") or {}
    macro_series = macro_stats.get("macro_series") or {}
    macro_releases = macro_stats.get("macro_release_dates") or {}
    snapshot_latest = _to_dt(macro_obs.get("last_fetched_at"))
    snapshot_count = int(macro_obs.get("row_count") or 0)
    fred_snapshot = {
        "available": snapshot_count > 0,
        "series_count": int(macro_series.get("row_count") or 0),
        "observation_count": snapshot_count,
        "release_dates_count": int(macro_releases.get("row_count") or 0),
        "latest_fetched_at": _iso(snapshot_latest),
    }
    fred_schedule_sources = ("fred_series", "fred_release_dates")
    fred_enabled_source_count = (
        None
        if macro_schedule is None
        else sum(bool(macro_schedule.get(source)) for source in fred_schedule_sources)
    )
    fred_refresh_enabled = (
        None
        if fred_enabled_source_count is None
        else fred_enabled_source_count > 0
    )
    fred_schedule_detail = (
        "scheduled-source state unknown"
        if fred_enabled_source_count is None
        else f"{fred_enabled_source_count} scheduled source(s) enabled"
    )
    _add(
        "fred", "FRED", "macro",
        _key_info(loaded_file_keys, app_keys, "FRED_API_KEY"),
        config_error=_config_error("fred"),
        enabled=None,
        last_success=snapshot_latest or fred["last_success"], last_attempt=fred["last_attempt"],
        last_error=fred["last_error"],
        threshold_hours=(
            _THRESHOLD_HOURS.get("fred") if fred_refresh_enabled is True else None
        ),
        detail=(
            f"local snapshot {fred_snapshot['observation_count']} observations"
            f" · {fred_snapshot['series_count']} series"
            f" · latest fetched {_iso(snapshot_latest) or '—'}"
            f" · {fred_schedule_detail}"
        ),
        signals={
            "jobs_prefix": "fetch_fred",
            "auto_refresh_enabled": fred_refresh_enabled,
            "enabled_schedule_source_count": fred_enabled_source_count,
            "local_snapshot": fred_snapshot,
        },
        disabled_reason=None,
    )

    # Retained acquisition evidence is not a live connection/entitlement check
    # or a statement about which reporting period is current.
    sec = fin_by_src.get("sec_edgar", {})
    _add(
        "sec_edgar", "SEC EDGAR", "fundamentals",
        {"present": True, "source": "not_required", "vars": []},
        last_success=sec.get("latest_fetched"),
        detail=f"cache {sec.get('cached', 0)} valid · {sec.get('expired', 0)} expired",
        signals=_financial_signals("sec_edgar"),
    )

    fd = fin_by_src.get("financial_datasets", {})
    _add(
        "financial_datasets", "Financial Datasets (paid)", "fundamentals",
        _key_info(loaded_file_keys, app_keys, "FINANCIAL_DATASETS_API_KEY"),
        config_error=_config_error("financial_datasets"),
        enabled=fd_enabled,
        last_success=fd.get("latest_fetched"),
        detail=f"cache {fd.get('cached', 0)} valid · {fd.get('expired', 0)} expired",
        signals=_financial_signals("financial_datasets"),
    )

    # Seeking Alpha — extension capture path; no API key
    # Freshness remains compatible with list captures. Only structured,
    # healthy-anchor-eligible results establish a full job completion.
    successes: Dict[str, datetime] = {}
    attempts: List[dict] = []
    errors: List[dict] = []
    completions: List[dict] = []
    for scope, meta in (sa_meta or {}).items():
        s = _to_dt(meta.get("last_success_at"))
        a = _to_dt(meta.get("last_attempt_at"))
        if s:
            successes[scope] = s
        failed = not meta.get("ok", True)
        if a:
            attempts.append({"at": a, "scope": scope,
                             "outcome": "failed" if failed else "succeeded"})
        if s and (a is None or s > a):
            attempts.append({"at": s, "scope": scope, "outcome": "succeeded"})
        if failed:
            errors.append({"at": a, "scope": scope,
                           "error": meta.get("last_error") or "refresh_failed"})

    extension_signals: Dict[str, dict] = {}
    for scope, job_name in (
        ("alpha_picks", "sa_alpha_picks_refresh"),
        ("market_news", "sa_market_news_refresh"),
    ):
        summary = sa_extension_summary.get(job_name) or {}
        attempt = summary.get("latest_attempt") or {}
        complete = summary.get("latest_derived_complete") or {}
        attempt_at = _to_dt(attempt.get("finished_at")) or _to_dt(attempt.get("started_at"))
        complete_at = _to_dt(complete.get("finished_at")) or _to_dt(complete.get("started_at"))
        result = attempt.get("result") if isinstance(attempt.get("result"), dict) else {}
        outcome = result.get("derived_outcome")
        if attempt_at:
            attempts.append({"at": attempt_at, "scope": scope, "outcome": outcome})
        if complete_at:
            successes[scope] = max(successes.get(scope, complete_at), complete_at)
            completions.append({"at": complete_at, "scope": scope})
        if outcome in {"degraded", "failed"}:
            errors.append({"at": attempt_at, "scope": scope,
                           "error": f"{scope}_extension_{outcome}"})
        extension_signals[f"{scope}_extension"] = {
            "latest_attempt_run_id": attempt.get("id"),
            "latest_attempt_outcome": outcome,
            "latest_attempt_counts": result.get("counts") if isinstance(result.get("counts"), dict) else {},
            "latest_complete_run_id": complete.get("id"),
        }

    # An error's timestamp belongs to that scope, never to the provider-wide
    # latest attempt. Undated errors remain undated and cannot be auto-resolved.
    unresolved = [error for error in errors if not (
        error["at"] is not None
        and successes.get(error["scope"]) is not None
        and successes[error["scope"]] >= error["at"]
    )]
    oldest = datetime.min.replace(tzinfo=timezone.utc)
    latest_error = max(unresolved, key=lambda e: (e["at"] or oldest, e["scope"]), default={})
    latest_attempt = max(attempts, key=lambda e: e["at"], default={})
    latest_complete = max(completions, key=lambda e: e["at"], default={})
    sa_success = max(successes.values(), default=None)
    sa_error = latest_error.get("error")
    mn = jobs.get("sa_market_news_refresh") or {}
    _add(
        "seeking_alpha", "Seeking Alpha (extension)", "capture",
        {"present": True, "source": "not_required", "vars": []},
        last_success=sa_success, last_attempt=latest_attempt.get("at"),
        last_attempt_outcome=latest_attempt.get("outcome"),
        last_attempt_scope=latest_attempt.get("scope"),
        last_complete=latest_complete.get("at"),
        last_complete_scope=latest_complete.get("scope"),
        last_error=sa_error,
        last_error_at=latest_error.get("at"),
        last_error_scope=latest_error.get("scope"),
        detail=f"capture last success {_iso(sa_success) or '—'}"
               + (f" · {latest_error['scope']} refresh FAILED" if sa_error else ""),
        signals={
            "refresh_meta": sa_meta,
            "market_news_job": bool(mn),
            **extension_signals,
        },
    )

    return {
        "generated_at": _iso(now),
        "providers": providers,
        "jobs": jobs,                       # latest run per job_name (raw passthrough)
        "local_market": {"db_exists": db_exists, "sync": sync},
        "notes": notes,                     # per-section degradation, if any
    }
