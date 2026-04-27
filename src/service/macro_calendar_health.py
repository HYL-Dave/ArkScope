"""Macro/calendar pipeline health telemetry (P1.2 commit 5).

Reports per-layer health for the macro_calendar layer so
``/macro/health`` can answer "is anything broken?" without mixing
job-cadence freshness, table-level coverage, and DB outages.

Three layers:

  - **jobs**   — per-job freshness vs expected cadence. Last successful
                 run is read from ``job_runs`` (the same table populated
                 by the dispatcher in ``src/service/jobs.py``). Never-run
                 jobs surface as ``never_run`` (warning), not critical:
                 a fresh deployment legitimately has no runs yet.
  - **tables** — per-table coverage. Reads ``MAX(fetched_at)`` + row count
                 from each ``cal_*`` / ``macro_*`` table. Empty tables
                 show as warning (probably never ingested); rows present
                 with NULL fetched_at would be a data-corruption critical.
  - **aggregate** — max severity across all per-job and per-table signals.

Severity ladder (overall = max across layers):

  - ``ok``         — within cadence + non-empty tables.
  - ``warning``    — degraded but pipeline likely functional (job 1.5×
                     overdue, table empty, last run failed but recent
                     success exists).
  - ``critical``   — actionable failure (job 3× overdue, last run
                     failed and no successful run exists, recent
                     calendar stale during US market hours).

``strict=true`` callers should treat any non-``ok`` severity as 503.
Default callers get 200 plus the structured payload so dashboards /
agents / curl can read the breakdown.

This module is **read-only**. It does NOT mutate ingestion state, does
NOT trigger jobs, does NOT touch the catalog. Health logic stays out of
the runner so the runner can stay narrow.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

NY_TZ = ZoneInfo("America/New_York")

SEVERITY_OK = "ok"
SEVERITY_WARNING = "warning"
SEVERITY_CRITICAL = "critical"
STATUS_NEVER_RUN = "never_run"
STATUS_EMPTY = "empty"

_SEVERITY_RANK = {
    SEVERITY_OK: 0,
    STATUS_EMPTY: 1,        # tables-only state, ranks like warning
    STATUS_NEVER_RUN: 1,    # jobs-only state, ranks like warning
    SEVERITY_WARNING: 1,
    SEVERITY_CRITICAL: 2,
}


# Per-job expected cadence (seconds). Derived from the cadences documented
# in P1_2_SPEC.md §4. backfill is one-shot — no cadence — so health rules
# only flag never_run for it.
_JOB_CADENCES_SECONDS: Dict[str, Optional[int]] = {
    "fetch_economic_calendar_recent": 3600,           # hourly
    "fetch_economic_calendar_backfill": None,         # one-shot
    "fetch_earnings_calendar": 4 * 3600,              # every 4h
    "fetch_ipo_calendar": 86400,                      # daily
    "fetch_fred_series": 86400,                       # daily
    "fetch_fred_release_dates": 7 * 86400,            # weekly
}

# Tables this layer owns. Listed in the order they appear in the report.
_TABLES: Tuple[str, ...] = (
    "cal_economic_events",
    "cal_earnings_events",
    "cal_ipo_events",
    "macro_series",
    "macro_observations",
    "macro_release_dates",
)

# Cadence multipliers: warning at 1.5×, critical at 3×.
DEFAULT_THRESHOLDS: Dict[str, Any] = {
    "warning_cadence_multiplier": 1.5,
    "critical_cadence_multiplier": 3.0,
    # Table-level: any table older than this is warning regardless of job.
    # 14d is generous — a healthy weekly cadence is well inside it.
    "table_stale_warning_seconds": 14 * 86400,
    # Backfill never_run severity. Use SEVERITY_OK to mute it on installs
    # that don't run backfill, SEVERITY_WARNING (default) to surface as
    # an actionable hint, SEVERITY_CRITICAL to gate strict-mode 503s on it.
    # Must be one of the three canonical severity values — anything else
    # raises KeyError when overall severity is computed.
    "backfill_never_run_severity": SEVERITY_WARNING,
}


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


def compute_macro_calendar_health(
    dal: Any,
    *,
    now: Optional[datetime] = None,
    thresholds: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Read job_runs + 6 macro/cal tables and return a structured health report.

    Best-effort: if the DB is unreachable returns a ``critical`` report
    with a single reason rather than raising. The two underlying queries
    (job_runs aggregation + table aggregation) each degrade independently;
    a missing job_runs table (pre-P0.2) still produces a usable tables-only
    report.
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
        stats = _run_health_queries(backend)
    except Exception as exc:  # pragma: no cover — logged + degraded
        logger.error("macro_calendar health query failed: %s", exc)
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
    """Map raw stats → severity report. Pure function, no DB.

    ``stats`` shape::

        {
          "jobs": {
            "fetch_economic_calendar_recent": {
              "last_success_at": <datetime|None>,
              "last_any_at":     <datetime|None>,
            },
            ...
          },
          "tables": {
            "cal_economic_events": {
              "last_fetched_at": <datetime|None>,
              "row_count":       <int>,
            },
            ...
          },
        }
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    is_market_hours = _is_us_market_hours(now)
    reasons: List[_Reason] = []

    job_blocks: List[Dict[str, Any]] = []
    job_severities: List[str] = []
    raw_jobs = stats.get("jobs") or {}
    for job_name, cadence_seconds in _JOB_CADENCES_SECONDS.items():
        record = raw_jobs.get(job_name) or {}
        block, severity = _evaluate_job(
            job_name=job_name,
            cadence_seconds=cadence_seconds,
            last_success_at=_coerce_dt(record.get("last_success_at")),
            last_any_at=_coerce_dt(record.get("last_any_at")),
            now=now,
            thresholds=thresholds,
            is_market_hours=is_market_hours,
            reasons=reasons,
        )
        job_blocks.append(block)
        job_severities.append(severity)

    table_blocks: List[Dict[str, Any]] = []
    table_severities: List[str] = []
    raw_tables = stats.get("tables") or {}
    for table_name in _TABLES:
        record = raw_tables.get(table_name) or {}
        block, severity = _evaluate_table(
            table_name=table_name,
            last_fetched_at=_coerce_dt(record.get("last_fetched_at")),
            row_count=int(record.get("row_count") or 0),
            now=now,
            thresholds=thresholds,
            reasons=reasons,
        )
        table_blocks.append(block)
        table_severities.append(severity)

    overall = max(
        job_severities + table_severities + [SEVERITY_OK],
        key=lambda s: _SEVERITY_RANK[s],
    )
    # Map status vocabulary → the three canonical severity values for the
    # top-level ``severity`` field. ``never_run`` and ``empty`` aren't
    # severity values; they're per-row statuses that rank like warnings.
    if overall in (STATUS_NEVER_RUN, STATUS_EMPTY):
        overall = SEVERITY_WARNING

    return {
        "ok": overall == SEVERITY_OK,
        "severity": overall,
        "reasons": [r.to_dict() for r in reasons],
        "jobs": job_blocks,
        "tables": table_blocks,
        "thresholds": dict(thresholds),
        "evaluated_at": _iso(now),
        "is_market_hours": is_market_hours,
    }


def _evaluate_job(
    *,
    job_name: str,
    cadence_seconds: Optional[int],
    last_success_at: Optional[datetime],
    last_any_at: Optional[datetime],
    now: datetime,
    thresholds: Dict[str, Any],
    is_market_hours: bool,
    reasons: List[_Reason],
) -> Tuple[Dict[str, Any], str]:
    """One job row + severity. Status vocabulary: ok / warning / critical /
    never_run."""
    age_seconds = _age_seconds(last_success_at, now)
    last_run_age_seconds = _age_seconds(last_any_at, now)

    block: Dict[str, Any] = {
        "name": job_name,
        "expected_cadence_seconds": cadence_seconds,
        "last_success_at": _iso(last_success_at),
        "last_any_at": _iso(last_any_at),
        "age_seconds": age_seconds,
        "age_human": _humanize_seconds(age_seconds),
    }

    # Never run at all
    if last_any_at is None:
        if cadence_seconds is None:
            sev = thresholds["backfill_never_run_severity"]
        else:
            sev = STATUS_NEVER_RUN
        if sev != SEVERITY_OK:
            reasons.append(_Reason(
                _normalize_severity(sev),
                "job_never_run",
                f"Job {job_name} has no recorded run.",
            ))
        block["status"] = sev
        return block, sev

    # Has runs but no successful one yet
    if last_success_at is None:
        sev = SEVERITY_CRITICAL
        reasons.append(_Reason(
            sev,
            "job_no_successful_run",
            f"Job {job_name} has runs but none succeeded.",
        ))
        block["status"] = sev
        return block, sev

    # One-shot job (no cadence) — having any successful run is enough
    if cadence_seconds is None:
        block["status"] = SEVERITY_OK
        # Surface failed-since-last-success as a soft signal but don't
        # raise severity for a one-shot job.
        if last_run_age_seconds is not None and last_any_at > last_success_at:
            reasons.append(_Reason(
                SEVERITY_WARNING,
                "job_recent_failure",
                f"Job {job_name} failed after its last success "
                f"({_humanize_seconds(_age_seconds(last_success_at, now))} ago).",
            ))
            block["status"] = SEVERITY_WARNING
            return block, SEVERITY_WARNING
        return block, SEVERITY_OK

    warning_threshold = cadence_seconds * thresholds["warning_cadence_multiplier"]
    critical_threshold = cadence_seconds * thresholds["critical_cadence_multiplier"]

    # Compute cadence-based severity first; failure-after-success layers
    # on top so a stale critical doesn't get downgraded by a recent failure
    # reason and a fresh-but-with-recent-failure case still warns.
    cadence_severity = SEVERITY_OK

    # Market-hours upgrade for the recent economic feed: stale during US
    # market hours is more concerning than off-hours staleness because
    # economic events fire at 08:30/10:00/14:00 ET.
    if (
        job_name == "fetch_economic_calendar_recent"
        and is_market_hours
        and age_seconds is not None
        and age_seconds > warning_threshold
    ):
        reasons.append(_Reason(
            SEVERITY_CRITICAL,
            "job_stale_market_hours",
            f"Job {job_name} last succeeded {_humanize_seconds(age_seconds)} ago "
            f"during US market hours (cadence "
            f"{_humanize_seconds(cadence_seconds)}).",
        ))
        cadence_severity = SEVERITY_CRITICAL
    elif age_seconds is not None and age_seconds > critical_threshold:
        reasons.append(_Reason(
            SEVERITY_CRITICAL,
            "job_stale_critical",
            f"Job {job_name} last succeeded {_humanize_seconds(age_seconds)} ago "
            f"(>{thresholds['critical_cadence_multiplier']:.0f}× cadence "
            f"{_humanize_seconds(cadence_seconds)}).",
        ))
        cadence_severity = SEVERITY_CRITICAL
    elif age_seconds is not None and age_seconds > warning_threshold:
        reasons.append(_Reason(
            SEVERITY_WARNING,
            "job_stale_warning",
            f"Job {job_name} last succeeded {_humanize_seconds(age_seconds)} ago "
            f"(>{thresholds['warning_cadence_multiplier']:.1f}× cadence "
            f"{_humanize_seconds(cadence_seconds)}).",
        ))
        cadence_severity = SEVERITY_WARNING

    final_severity = cadence_severity
    if last_run_age_seconds is not None and last_any_at > last_success_at:
        # A run failed after the last success. Independent signal from
        # cadence — a fresh job with a recent failure is degraded, and
        # a stale-critical job with a recent failure stays critical
        # while still surfacing the failure as an additional reason.
        reasons.append(_Reason(
            SEVERITY_WARNING,
            "job_recent_failure",
            f"Job {job_name} failed after its last success "
            f"({_humanize_seconds(_age_seconds(last_success_at, now))} ago).",
        ))
        if _SEVERITY_RANK[SEVERITY_WARNING] > _SEVERITY_RANK[final_severity]:
            final_severity = SEVERITY_WARNING

    block["status"] = final_severity
    return block, final_severity


def _evaluate_table(
    *,
    table_name: str,
    last_fetched_at: Optional[datetime],
    row_count: int,
    now: datetime,
    thresholds: Dict[str, Any],
    reasons: List[_Reason],
) -> Tuple[Dict[str, Any], str]:
    """One table row + severity. Status vocabulary: ok / warning / critical
    / empty."""
    age_seconds = _age_seconds(last_fetched_at, now)
    block: Dict[str, Any] = {
        "name": table_name,
        "row_count": row_count,
        "last_fetched_at": _iso(last_fetched_at),
        "age_seconds": age_seconds,
        "age_human": _humanize_seconds(age_seconds),
    }

    if row_count == 0:
        block["status"] = STATUS_EMPTY
        reasons.append(_Reason(
            SEVERITY_WARNING,
            "table_empty",
            f"Table {table_name} has 0 rows; ingestion has never written to it.",
        ))
        return block, STATUS_EMPTY

    if last_fetched_at is None:
        # Rows present but no fetched_at — schema corruption / manual seed
        # / pre-fetched-at migration. Critical because as-of reads will
        # mis-attribute these rows.
        block["status"] = SEVERITY_CRITICAL
        reasons.append(_Reason(
            SEVERITY_CRITICAL,
            "table_null_fetched_at",
            f"Table {table_name} has {row_count} rows but NULL MAX(fetched_at); "
            f"cannot age-check.",
        ))
        return block, SEVERITY_CRITICAL

    if age_seconds is not None and age_seconds > thresholds["table_stale_warning_seconds"]:
        block["status"] = SEVERITY_WARNING
        reasons.append(_Reason(
            SEVERITY_WARNING,
            "table_stale",
            f"Table {table_name} last ingestion {_humanize_seconds(age_seconds)} "
            f"ago (>{_humanize_seconds(thresholds['table_stale_warning_seconds'])}).",
        ))
        return block, SEVERITY_WARNING

    block["status"] = SEVERITY_OK
    return block, SEVERITY_OK


# ---------------------------------------------------------------------------
# DB queries
# ---------------------------------------------------------------------------


_JOB_RUNS_SQL = """
    SELECT job_name,
           MAX(finished_at) FILTER (WHERE status = 'succeeded') AS last_success_at,
           MAX(finished_at) AS last_any_at
    FROM job_runs
    WHERE job_name = ANY(%(job_names)s)
    GROUP BY job_name
"""

# One round-trip for all six tables. Each branch coerces COUNT(*) to BIGINT
# and MAX(fetched_at) to TIMESTAMPTZ so the union-typed columns stay sane.
_TABLE_STATS_SQL = """
    SELECT 'cal_economic_events'   AS table_name, MAX(fetched_at) AS last_fetched_at, COUNT(*)::bigint AS row_count FROM cal_economic_events
    UNION ALL
    SELECT 'cal_earnings_events',                 MAX(fetched_at), COUNT(*)::bigint FROM cal_earnings_events
    UNION ALL
    SELECT 'cal_ipo_events',                      MAX(fetched_at), COUNT(*)::bigint FROM cal_ipo_events
    UNION ALL
    SELECT 'macro_series',                        MAX(fetched_at), COUNT(*)::bigint FROM macro_series
    UNION ALL
    SELECT 'macro_observations',                  MAX(fetched_at), COUNT(*)::bigint FROM macro_observations
    UNION ALL
    SELECT 'macro_release_dates',                 MAX(fetched_at), COUNT(*)::bigint FROM macro_release_dates
"""


def _run_health_queries(backend: Any) -> Dict[str, Any]:
    """Aggregate job_runs + 6 macro/cal tables.

    Each query degrades independently — a missing ``job_runs`` table
    (pre-P0.2) still leaves the table-level coverage report usable.
    """
    from psycopg2 import extras as _pg_extras

    conn = backend._get_conn()
    jobs: Dict[str, Dict[str, Any]] = {}
    try:
        with conn.cursor(cursor_factory=_pg_extras.RealDictCursor) as cur:
            cur.execute(_JOB_RUNS_SQL, {"job_names": list(_JOB_CADENCES_SECONDS)})
            for row in cur.fetchall():
                jobs[row["job_name"]] = {
                    "last_success_at": row.get("last_success_at"),
                    "last_any_at": row.get("last_any_at"),
                }
    except Exception as exc:
        logger.warning("macro_calendar health: job_runs lookup failed: %s", exc)

    tables: Dict[str, Dict[str, Any]] = {}
    with conn.cursor(cursor_factory=_pg_extras.RealDictCursor) as cur:
        cur.execute(_TABLE_STATS_SQL)
        for row in cur.fetchall():
            tables[row["table_name"]] = {
                "last_fetched_at": row.get("last_fetched_at"),
                "row_count": int(row.get("row_count") or 0),
            }

    return {"jobs": jobs, "tables": tables}


def _db_unavailable_report(
    now: datetime,
    thresholds: Dict[str, Any],
    *,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    msg = error or "DB backend unavailable; macro_calendar health cannot be computed."
    return {
        "ok": False,
        "severity": SEVERITY_CRITICAL,
        "reasons": [{
            "severity": SEVERITY_CRITICAL,
            "code": "db_unavailable",
            "message": msg,
        }],
        "jobs": [
            {
                "name": name,
                "expected_cadence_seconds": cadence,
                "last_success_at": None,
                "last_any_at": None,
                "age_seconds": None,
                "age_human": None,
                "status": SEVERITY_CRITICAL,
            }
            for name, cadence in _JOB_CADENCES_SECONDS.items()
        ],
        "tables": [
            {
                "name": name,
                "row_count": 0,
                "last_fetched_at": None,
                "age_seconds": None,
                "age_human": None,
                "status": SEVERITY_CRITICAL,
            }
            for name in _TABLES
        ],
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
    if ny.weekday() >= 5:
        return False
    minute_of_day = ny.hour * 60 + ny.minute
    return 9 * 60 + 30 <= minute_of_day < 16 * 60


def _coerce_dt(value: Any) -> Optional[datetime]:
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
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
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


def _normalize_severity(value: Any) -> str:
    """Coerce raw threshold strings to the canonical severity vocabulary."""
    s = str(value or "").lower().strip()
    if s in (SEVERITY_CRITICAL, SEVERITY_WARNING, SEVERITY_OK):
        return s
    if s in (STATUS_NEVER_RUN, STATUS_EMPTY):
        return SEVERITY_WARNING
    return SEVERITY_WARNING