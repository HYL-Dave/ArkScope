"""SA market-news pipeline health telemetry (P0.4).

Reports per-layer health for the Seeking Alpha market-news pipeline so
``/sa/market-news/health`` can answer "is anything broken?" without
mixing pipeline staleness, feed-content lulls, and detail-body gaps.

Three layers:

  - **freshness**     — pipeline activity vs data freshness, surfaced
                        side-by-side. Pipeline activity is read from
                        ``job_runs`` (extension run history); data
                        freshness is read from ``sa_market_news``
                        (last fetched/published row). Keeping the two
                        signals separate matters because
                        ``upsert_sa_market_news`` only bumps
                        ``updated_at`` on conflict — when SA returns
                        only known items, ``fetched_at`` can look
                        stale even if the extension is healthy.
  - **feed_health**   — recent metadata volume (24h / 7d).
                        Did the upstream feed actually produce items?
  - **detail_health** — fraction of last-7d rows with a stored body.
                        Detail-fetch loop healthy?

Severity ladder (overall = max across layers):

  - ``ok``        — all metrics within thresholds.
  - ``warning``   — degradation worth surfacing but pipeline may still be
                    functional (e.g. last fetch 7h ago on a Sunday).
  - ``critical``  — actionable failure (e.g. detail completeness <50%,
                    or zero published items during US market hours).

``strict=true`` callers should treat any non-``ok`` severity as 503.
Default callers get 200 plus the structured payload so dashboards /
agents / curl can read the breakdown.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

NY_TZ = ZoneInfo("America/New_York")

SEVERITY_OK = "ok"
SEVERITY_WARNING = "warning"
SEVERITY_CRITICAL = "critical"

_SEVERITY_RANK = {SEVERITY_OK: 0, SEVERITY_WARNING: 1, SEVERITY_CRITICAL: 2}


DEFAULT_THRESHOLDS: Dict[str, Any] = {
    # Pipeline staleness: time since last successful pipeline activity.
    # Preferred signal is the latest succeeded extension run in
    # ``job_runs`` (job_name = ``EXTENSION_JOB_NAME``); falls back to
    # MAX(fetched_at) on ``sa_market_news`` when no extension runs are
    # recorded yet.
    "last_fetch_warning_seconds": 6 * 3600,
    # Feed lull: items_24h_published == 0 → warning, but only critical
    # when checked during regular US trading hours (NY 09:30-16:00).
    "items_24h_warning_threshold": 1,  # zero items → warning
    # Detail completeness ladder (% of last-7d rows with body).
    "detail_completeness_warning_pct": 80.0,
    "detail_completeness_critical_pct": 50.0,
    # Minimum row count before completeness is meaningful (avoid noise
    # when a tiny rolling window has 0/1 rows).
    "detail_completeness_min_rows": 5,
}

# Canonical extension job_name whose ``succeeded`` runs gate
# pipeline-freshness. Matches ``_JOB_DEFINITIONS`` in src/service/jobs.py
# so the same row also surfaces via /jobs/status.
EXTENSION_JOB_NAME = "sa_market_news_refresh"


@dataclass(frozen=True)
class _Reason:
    severity: str
    code: str
    message: str

    def to_dict(self) -> Dict[str, str]:
        return {"severity": self.severity, "code": self.code, "message": self.message}


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def compute_market_news_health(
    dal: Any,
    *,
    now: Optional[datetime] = None,
    thresholds: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Read sa_market_news stats and return a structured health report.

    Args:
        dal: DAL instance whose ``_backend`` exposes ``_get_conn()``.
        now: clock override (UTC). Defaults to ``datetime.now(tz=UTC)``.
        thresholds: optional overrides merged onto ``DEFAULT_THRESHOLDS``.

    Returns:
        Dict with shape: ``{ok, severity, reasons[], freshness, feed_health,
        detail_health, thresholds, evaluated_at, is_market_hours}``.

    Best-effort: if the DB is unreachable returns a ``critical`` report
    with a single reason rather than raising.
    """
    if now is None:
        now = datetime.now(tz=timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    merged_thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    backend = getattr(dal, "_backend", None)
    if backend is None or not hasattr(backend, "_get_conn"):
        return _db_unavailable_report(now, merged_thresholds)

    try:
        stats = _run_health_query(backend, now=now)
    except Exception as exc:  # pragma: no cover — logged + degraded
        logger.error("sa_market_news health query failed: %s", exc)
        return _db_unavailable_report(now, merged_thresholds, error=str(exc))

    return evaluate_health(stats, now=now, thresholds=merged_thresholds)


# ---------------------------------------------------------------------------
# Pure evaluation
# ---------------------------------------------------------------------------


def evaluate_health(
    stats: Dict[str, Any],
    *,
    now: datetime,
    thresholds: Dict[str, Any],
) -> Dict[str, Any]:
    """Map raw stats → severity report. Pure function, no DB."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    last_fetched_at = _coerce_dt(stats.get("last_fetched_at"))
    last_published_at = _coerce_dt(stats.get("last_published_at"))
    extension_last_success_at = _coerce_dt(stats.get("extension_last_success_at"))
    rows_24h_fetched = int(stats.get("rows_24h_fetched") or 0)
    items_24h_published = int(stats.get("items_24h_published") or 0)
    items_7d = int(stats.get("items_7d") or 0)
    detail_present_7d = int(stats.get("detail_present_7d") or 0)

    is_market_hours = _is_us_market_hours(now)
    reasons: list[_Reason] = []

    # ---- freshness layer ------------------------------------------------
    last_fetch_age_seconds = _age_seconds(last_fetched_at, now)
    last_published_age_seconds = _age_seconds(last_published_at, now)
    extension_last_success_age_seconds = _age_seconds(extension_last_success_at, now)

    # Preferred pipeline signal: the extension's own job_runs record.
    # Falls back to last_fetched_at when no extension run has been logged
    # yet (older databases predating this signal). Avoids the case where
    # SA returns only known items: upsert no-ops update updated_at, not
    # fetched_at, so MAX(fetched_at) can look stale even though pipeline
    # is healthy.
    if extension_last_success_age_seconds is not None:
        pipeline_age_seconds = extension_last_success_age_seconds
        pipeline_signal = "extension_run"
    else:
        pipeline_age_seconds = last_fetch_age_seconds
        pipeline_signal = "last_fetched_at" if last_fetched_at is not None else None

    last_fetch_status = SEVERITY_OK
    if pipeline_signal is None:
        last_fetch_status = SEVERITY_CRITICAL
        reasons.append(_Reason(
            SEVERITY_CRITICAL,
            "no_pipeline_signal",
            "No extension run recorded and sa_market_news has no fetched_at — "
            "pipeline never ran or table is empty.",
        ))
    elif pipeline_age_seconds is not None and \
            pipeline_age_seconds > thresholds["last_fetch_warning_seconds"]:
        last_fetch_status = SEVERITY_WARNING
        signal_label = "extension run" if pipeline_signal == "extension_run" else "last fetched row"
        reasons.append(_Reason(
            SEVERITY_WARNING,
            "stale_pipeline",
            f"Last successful pipeline activity ({signal_label}) was "
            f"{_humanize_seconds(pipeline_age_seconds)} ago "
            f"(threshold {_humanize_seconds(thresholds['last_fetch_warning_seconds'])}).",
        ))

    freshness_block = {
        "last_fetched_at": _iso(last_fetched_at),
        "last_fetch_age_seconds": last_fetch_age_seconds,
        "last_fetch_age_human": _humanize_seconds(last_fetch_age_seconds),
        "latest_published_at": _iso(last_published_at),
        "latest_published_age_seconds": last_published_age_seconds,
        "latest_published_age_human": _humanize_seconds(last_published_age_seconds),
        "extension_last_success_at": _iso(extension_last_success_at),
        "extension_last_success_age_seconds": extension_last_success_age_seconds,
        "extension_last_success_age_human": _humanize_seconds(extension_last_success_age_seconds),
        "pipeline_age_seconds": pipeline_age_seconds,
        "pipeline_signal": pipeline_signal,
        "last_fetch_status": last_fetch_status,
    }

    # ---- feed_health layer ----------------------------------------------
    items_24h_status = SEVERITY_OK
    if items_24h_published < thresholds["items_24h_warning_threshold"]:
        # Zero (or below threshold) published items in 24h.
        # Off-hours: warning. Market-hours: critical (feed should be live).
        if is_market_hours:
            items_24h_status = SEVERITY_CRITICAL
            reasons.append(_Reason(
                SEVERITY_CRITICAL,
                "no_published_items_market_hours",
                f"items_24h_published={items_24h_published} during US market hours.",
            ))
        else:
            items_24h_status = SEVERITY_WARNING
            reasons.append(_Reason(
                SEVERITY_WARNING,
                "no_published_items_offhours",
                f"items_24h_published={items_24h_published} (off-hours; SA may be quiet).",
            ))

    feed_block = {
        "rows_24h_fetched": rows_24h_fetched,
        "items_24h_published": items_24h_published,
        "items_7d": items_7d,
        "items_24h_status": items_24h_status,
    }

    # ---- detail_health layer --------------------------------------------
    completeness_pct: Optional[float]
    if items_7d <= 0:
        completeness_pct = None
    else:
        completeness_pct = round((detail_present_7d / items_7d) * 100.0, 2)

    detail_status = SEVERITY_OK
    if items_7d < thresholds["detail_completeness_min_rows"]:
        # Sample too small to be meaningful.
        if items_7d == 0:
            # Already covered by feed_health critical/warning above.
            pass
        else:
            reasons.append(_Reason(
                SEVERITY_OK,
                "detail_sample_too_small",
                f"items_7d={items_7d} below min_rows="
                f"{thresholds['detail_completeness_min_rows']}; completeness inconclusive.",
            ))
    elif completeness_pct is not None:
        if completeness_pct < thresholds["detail_completeness_critical_pct"]:
            detail_status = SEVERITY_CRITICAL
            reasons.append(_Reason(
                SEVERITY_CRITICAL,
                "detail_completeness_critical",
                f"7d body completeness {completeness_pct:.1f}% "
                f"< {thresholds['detail_completeness_critical_pct']:.0f}%.",
            ))
        elif completeness_pct < thresholds["detail_completeness_warning_pct"]:
            detail_status = SEVERITY_WARNING
            reasons.append(_Reason(
                SEVERITY_WARNING,
                "detail_completeness_warning",
                f"7d body completeness {completeness_pct:.1f}% "
                f"< {thresholds['detail_completeness_warning_pct']:.0f}%.",
            ))

    detail_block = {
        "rows_7d": items_7d,
        "rows_with_detail_7d": detail_present_7d,
        "completeness_7d_pct": completeness_pct,
        "completeness_status": detail_status,
    }

    # ---- aggregate severity ---------------------------------------------
    overall = max(
        (last_fetch_status, items_24h_status, detail_status),
        key=lambda s: _SEVERITY_RANK[s],
    )

    return {
        "ok": overall == SEVERITY_OK,
        "severity": overall,
        "reasons": [r.to_dict() for r in reasons],
        "freshness": freshness_block,
        "feed_health": feed_block,
        "detail_health": detail_block,
        "thresholds": dict(thresholds),
        "evaluated_at": _iso(now),
        "is_market_hours": is_market_hours,
    }


# ---------------------------------------------------------------------------
# DB query
# ---------------------------------------------------------------------------


_HEALTH_SQL = """
    SELECT
        MAX(fetched_at)   AS last_fetched_at,
        MAX(published_at) AS last_published_at,
        COUNT(*) FILTER (
            WHERE fetched_at >= %(now)s::timestamptz - INTERVAL '24 hours'
        ) AS rows_24h_fetched,
        COUNT(*) FILTER (
            WHERE published_at >= %(now)s::timestamptz - INTERVAL '24 hours'
        ) AS items_24h_published,
        COUNT(*) FILTER (
            WHERE COALESCE(published_at, fetched_at) >=
                  %(now)s::timestamptz - INTERVAL '7 days'
        ) AS items_7d,
        COUNT(*) FILTER (
            WHERE COALESCE(published_at, fetched_at) >=
                  %(now)s::timestamptz - INTERVAL '7 days'
              AND body_markdown IS NOT NULL
              AND body_markdown <> ''
        ) AS detail_present_7d
    FROM sa_market_news
"""

_EXTENSION_RUN_SQL = """
    SELECT MAX(finished_at) FILTER (WHERE status = 'succeeded')
        AS extension_last_success_at
    FROM job_runs
    WHERE job_name = %(job_name)s
"""


def _run_health_query(backend: Any, *, now: datetime) -> Dict[str, Any]:
    """Aggregate sa_market_news + read latest extension run from job_runs.

    Two queries: the data-layer aggregation is required, and the
    extension-run lookup gracefully degrades (returns ``None``) when
    ``job_runs`` is missing or unreachable. This way pre-P0.2 deployments
    still get a usable health report.
    """
    from psycopg2 import extras as _pg_extras

    conn = backend._get_conn()
    with conn.cursor(cursor_factory=_pg_extras.RealDictCursor) as cur:
        cur.execute(_HEALTH_SQL, {"now": now})
        market_row = cur.fetchone() or {}

    extension_last_success_at: Any = None
    try:
        with conn.cursor(cursor_factory=_pg_extras.RealDictCursor) as cur:
            cur.execute(_EXTENSION_RUN_SQL, {"job_name": EXTENSION_JOB_NAME})
            row = cur.fetchone() or {}
            extension_last_success_at = row.get("extension_last_success_at")
    except Exception as exc:
        # job_runs absent (pre-P0.2) or transient DB error — fall back to
        # row-level signals only. Log once; do not raise.
        logger.warning(
            "sa_market_news health: extension_last_success_at lookup failed: %s",
            exc,
        )

    out = dict(market_row)
    out["extension_last_success_at"] = extension_last_success_at
    return out


def _db_unavailable_report(
    now: datetime,
    thresholds: Dict[str, Any],
    *,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """Fallback report when DB / DAL backend is missing."""
    msg = error or "DB backend unavailable; market-news health cannot be computed."
    return {
        "ok": False,
        "severity": SEVERITY_CRITICAL,
        "reasons": [{
            "severity": SEVERITY_CRITICAL,
            "code": "db_unavailable",
            "message": msg,
        }],
        "freshness": {
            "last_fetched_at": None,
            "last_fetch_age_seconds": None,
            "last_fetch_age_human": None,
            "latest_published_at": None,
            "latest_published_age_seconds": None,
            "latest_published_age_human": None,
            "extension_last_success_at": None,
            "extension_last_success_age_seconds": None,
            "extension_last_success_age_human": None,
            "pipeline_age_seconds": None,
            "pipeline_signal": None,
            "last_fetch_status": SEVERITY_CRITICAL,
        },
        "feed_health": {
            "rows_24h_fetched": 0,
            "items_24h_published": 0,
            "items_7d": 0,
            "items_24h_status": SEVERITY_CRITICAL,
        },
        "detail_health": {
            "rows_7d": 0,
            "rows_with_detail_7d": 0,
            "completeness_7d_pct": None,
            "completeness_status": SEVERITY_CRITICAL,
        },
        "thresholds": dict(thresholds),
        "evaluated_at": _iso(now),
        "is_market_hours": _is_us_market_hours(now),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_us_market_hours(now: datetime) -> bool:
    """Regular US equity hours (Mon-Fri 09:30-16:00 New York time)."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    ny = now.astimezone(NY_TZ)
    if ny.weekday() >= 5:  # Sat=5, Sun=6
        return False
    minute_of_day = ny.hour * 60 + ny.minute
    return 9 * 60 + 30 <= minute_of_day < 16 * 60


def _coerce_dt(value: Any) -> Optional[datetime]:
    """Accept psycopg2 datetimes, ISO strings, or None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return None


def _age_seconds(value: Optional[datetime], now: datetime) -> Optional[int]:
    if value is None:
        return None
    delta = now - value
    return max(0, int(delta.total_seconds()))


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _humanize_seconds(seconds: Optional[int]) -> Optional[str]:
    if seconds is None:
        return None
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    if seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    return f"{days}d {hours}h"