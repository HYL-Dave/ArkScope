"""FRED ingestion pipeline for P1.2 (commit 2/6).

Two callable entry points the job runner wraps:

  - ``fetch_fred_release_dates(dal, ...)`` — refresh
    ``macro_release_dates`` for the curated set of release_ids. The
    schedule is recorded for audit / monitoring, not used to derive
    realtime_start (FRED supplies that authoritatively per row).
  - ``fetch_fred_series(dal, ...)`` — refresh ``macro_series`` metadata
    + ``macro_observations`` for every series in
    ``config/p1_2_macro_series.yaml``. Strategy is per-series:

      * ``latest_only``: trust the FRED-supplied ``realtime_start`` /
        ``realtime_end`` on each observation row. For non-revising
        monthly series like CPIAUCNS this collapses to one row per
        observation_date with realtime_window = [first_release, ∞).
        We do NOT derive realtime_start from the release schedule:
        that gave wrong answers when an earlier release in the same
        month covered a different period (e.g. 2024-03-12 publishes
        Feb CPI; using it as realtime_start for Mar-2024 CPI would
        leak the value 4 weeks early).
      * ``full_vintages``: explicitly request the full ALFRED window
        (``realtime_start='1776-07-04'``, ``realtime_end='9999-12-31'``)
        so revising series like GDP return one row per vintage. Default
        FRED requests collapse to today's vintage only — see
        docs/design/P1_2_PROVIDER_DISCOVERY.md §6.

Both entry points are pure-Python coroutines of the FRED HTTP client
and the ``MacroCalendarStore`` from commit 1. No FastAPI / agent tool
wiring lives here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

import yaml

from data_sources.fred_client import (
    FREDClient,
    FREDError,
    FREDObservation,
    FREDReleaseDate,
    FREDSeriesMetadata,
)
from src.p1_2.store import MacroCalendarStore

logger = logging.getLogger(__name__)

DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[2] / "config" / "p1_2_macro_series.yaml"


@dataclass
class IngestionStats:
    """Per-job stats; surfaced via job_runs.result by the job dispatcher."""

    series_processed: int = 0
    series_skipped: int = 0
    observations_upserted: int = 0
    # Reserved for future use (spec §3.2 anticipates skipping rows that
    # can't have a realtime_start derived). Today's ingestion trusts FRED's
    # own realtime_start so this counter stays 0; we keep it in the schema
    # so /jobs/status surfaces it the moment skip cases appear.
    observations_skipped_no_release: int = 0
    release_dates_upserted: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "series_processed": self.series_processed,
            "series_skipped": self.series_skipped,
            "observations_upserted": self.observations_upserted,
            "observations_skipped_no_release": self.observations_skipped_no_release,
            "release_dates_upserted": self.release_dates_upserted,
            "errors": list(self.errors),
        }


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CatalogEntry:
    series_id: str
    revision_strategy: str
    release_id: Optional[int]
    description: str = ""
    observation_start: Optional[date] = None


@dataclass(frozen=True)
class Catalog:
    entries: Sequence[CatalogEntry]
    observation_start: date
    release_date_lookback_years: int

    def release_ids(self) -> List[int]:
        return sorted({e.release_id for e in self.entries if e.release_id is not None})


def load_catalog(path: Path = DEFAULT_CATALOG_PATH) -> Catalog:
    """Parse the YAML catalog. Strict validation: every entry must specify
    series_id + revision_strategy. release_id may be null."""
    with path.open("r", encoding="utf-8") as fh:
        body = yaml.safe_load(fh) or {}
    series_block = body.get("series") or []
    defaults = body.get("defaults") or {}
    obs_start = _parse_date(defaults.get("observation_start", "1990-01-01"))
    lookback_years = int(defaults.get("release_date_lookback_years", 50))

    entries: List[CatalogEntry] = []
    for raw in series_block:
        sid = (raw or {}).get("id")
        strategy = (raw or {}).get("revision_strategy")
        if not sid or strategy not in ("latest_only", "full_vintages"):
            raise ValueError(
                f"invalid catalog entry: {raw!r}; need id + valid revision_strategy"
            )
        rid_raw = raw.get("release_id")
        rid = int(rid_raw) if rid_raw is not None else None
        entry_obs_start = _parse_date(raw.get("observation_start")) if raw.get("observation_start") else None
        entries.append(CatalogEntry(
            series_id=str(sid),
            revision_strategy=str(strategy),
            release_id=rid,
            description=str(raw.get("description") or ""),
            observation_start=entry_obs_start,
        ))
    return Catalog(
        entries=entries,
        observation_start=obs_start,
        release_date_lookback_years=lookback_years,
    )


def _parse_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return date.fromisoformat(str(value))


# ---------------------------------------------------------------------------
# Release dates
# ---------------------------------------------------------------------------


def fetch_fred_release_dates(
    dal: Any,
    *,
    release_ids: Optional[Iterable[int]] = None,
    catalog_path: Path = DEFAULT_CATALOG_PATH,
    client: Optional[FREDClient] = None,
    limit: Optional[int] = None,
) -> IngestionStats:
    """Refresh ``macro_release_dates`` for the curated release_id set.

    Pass ``release_ids`` to override the catalog (useful for tests).
    The page size FRED returns per release_id is sized to cover the
    catalog's ``release_date_lookback_years`` for daily releases
    (e.g. H.15 / Treasury rates) — at ~250 trading days/year, 50 years
    is ~12,500 rows. FRED's hard cap on this endpoint is 1000 per call
    so for now we cap at 1000 and accept that very-deep history will
    arrive in batches over multiple runs (a future commit can paginate
    via the offset parameter if we discover it matters).
    """
    stats = IngestionStats()
    store = MacroCalendarStore(dal)
    if not store.is_available():
        stats.errors.append("DAL backend unavailable")
        return stats

    catalog: Optional[Catalog] = None
    if release_ids is None or limit is None:
        try:
            catalog = load_catalog(catalog_path)
        except Exception as exc:
            stats.errors.append(f"catalog load failed: {exc}")
            return stats
        if release_ids is None:
            release_ids = catalog.release_ids()
    release_ids = sorted({int(r) for r in release_ids})

    page_size = limit if limit is not None else _release_dates_page_size(catalog)

    fred = client or FREDClient()
    for rid in release_ids:
        try:
            rows = fred.get_release_dates(rid, limit=page_size, sort_order="desc")
        except FREDError as exc:
            stats.errors.append(f"release_dates({rid}): {exc}")
            continue
        for r in rows:
            ok = store.upsert_release_date(
                release_id=r.release_id,
                release_name=str(rid),  # release name resolved on demand later
                release_date_value=r.release_date,
            )
            if ok:
                stats.release_dates_upserted += 1
    return stats


def _release_dates_page_size(catalog: Optional[Catalog]) -> int:
    """Pick a release/dates page size from catalog lookback.

    Daily releases (H.15) generate ~250 release_dates/year, so 50 years
    is well past FRED's 1000-row hard cap on this endpoint. For now we
    cap at 1000; deeper history can be paged on a follow-up commit if
    we ever observe it being needed.
    """
    if catalog is None:
        return 1000
    years = max(1, int(catalog.release_date_lookback_years))
    # 250 daily releases per year is a generous upper bound for H.15.
    return min(1000, years * 250)


# ---------------------------------------------------------------------------
# Series + observations
# ---------------------------------------------------------------------------


def fetch_fred_series(
    dal: Any,
    *,
    series_ids: Optional[Iterable[str]] = None,
    catalog_path: Path = DEFAULT_CATALOG_PATH,
    client: Optional[FREDClient] = None,
    full_refresh: bool = False,
) -> IngestionStats:
    """Refresh ``macro_series`` + ``macro_observations`` for the catalog.

    By default this issues an *incremental* request (``observation_start``
    = today − 90 days for ``latest_only``; full backfill for
    ``full_vintages`` since vintage_dates is point-time). Set
    ``full_refresh=True`` to pull every observation back to the catalog's
    configured ``observation_start``.
    """
    stats = IngestionStats()
    store = MacroCalendarStore(dal)
    if not store.is_available():
        stats.errors.append("DAL backend unavailable")
        return stats

    try:
        catalog = load_catalog(catalog_path)
    except Exception as exc:
        stats.errors.append(f"catalog load failed: {exc}")
        return stats

    selected = _select_entries(catalog.entries, series_ids)
    if not selected:
        stats.errors.append("no matching series in catalog")
        return stats

    fred = client or FREDClient()
    for entry in selected:
        try:
            _ingest_one(fred, store, entry, catalog, stats, full_refresh=full_refresh)
            stats.series_processed += 1
        except FREDError as exc:
            stats.series_skipped += 1
            stats.errors.append(f"{entry.series_id}: {exc}")
        except Exception as exc:
            stats.series_skipped += 1
            stats.errors.append(f"{entry.series_id}: unexpected: {exc}")
    return stats


def _select_entries(
    entries: Sequence[CatalogEntry],
    selector: Optional[Iterable[str]],
) -> List[CatalogEntry]:
    if not selector:
        return list(entries)
    wanted = {s.upper() for s in selector}
    return [e for e in entries if e.series_id.upper() in wanted]


def _ingest_one(
    fred: FREDClient,
    store: MacroCalendarStore,
    entry: CatalogEntry,
    catalog: Catalog,
    stats: IngestionStats,
    *,
    full_refresh: bool,
) -> None:
    meta = fred.get_series_metadata(entry.series_id)
    if meta is None:
        stats.errors.append(f"{entry.series_id}: metadata missing")
        return
    store.upsert_macro_series({
        "series_id": meta.series_id,
        "title": meta.title,
        "frequency": meta.frequency,
        "units": meta.units,
        "seasonal_adjustment": meta.seasonal_adjustment,
        "last_updated": meta.last_updated,
        "revision_strategy": entry.revision_strategy,
    })

    obs_start = entry.observation_start or catalog.observation_start
    if not full_refresh and entry.revision_strategy == "latest_only":
        # Cheap incremental: ~3 months back covers any revision FRED still
        # propagates for non-revising series.
        obs_start = max(obs_start, date.today() - timedelta(days=90))

    if entry.revision_strategy == "latest_only":
        _ingest_latest_only(fred, store, entry, obs_start, stats)
    else:
        _ingest_full_vintages(fred, store, entry, obs_start, stats)


def _ingest_latest_only(
    fred: FREDClient,
    store: MacroCalendarStore,
    entry: CatalogEntry,
    obs_start: date,
    stats: IngestionStats,
) -> None:
    """Ingest one row per observation_date using FRED's authoritative
    realtime_start.

    For non-revising series the default FRED response collapses to today's
    vintage with realtime_start = today, but we want the FIRST-publication
    date (so a backtest at decision_date >= first_publication can use it).
    Pass realtime_start='1776-07-04' + realtime_end='9999-12-31' so ALFRED
    returns one row per [realtime_start, realtime_end) window. For a
    non-revising series like CPIAUCNS that's exactly one row per
    observation_date with realtime_start = first_publication.

    We don't try to infer realtime_start from the release schedule — that
    fails on series whose monthly observation_date overlaps an earlier
    release of a different period (e.g. release 2024-03-12 publishes Feb
    CPI, but a naive `release_date >= obs_date` rule would attach it to
    Mar 2024 CPI and leak the value 4 weeks early).
    """
    obs = fred.get_observations(
        entry.series_id,
        observation_start=obs_start,
        realtime_start=ALFRED_FULL_HISTORY_START,
        realtime_end=ALFRED_FULL_HISTORY_END,
        sort_order="asc",
        output_type=OUTPUT_TYPE_INITIAL_RELEASE,
    )
    for row in obs:
        # output_type=4 returns one row per observation_date already
        # matching the first-publication realtime window. No dedupe
        # needed — see P1_2_PROVIDER_DISCOVERY.md §6.3.
        ok = store.upsert_macro_observation(
            series_id=entry.series_id,
            observation_date=row.observation_date,
            value=row.value,
            realtime_start=row.realtime_start,
            realtime_end=None,  # canonical "current" tail
        )
        if ok:
            stats.observations_upserted += 1


def _ingest_full_vintages(
    fred: FREDClient,
    store: MacroCalendarStore,
    entry: CatalogEntry,
    obs_start: date,
    stats: IngestionStats,
) -> None:
    """Ingest each ALFRED-supplied vintage as its own realtime window.

    Critical: ``output_type=1`` is the parser-friendly format
    ("By Real-Time Period"). It IS the FRED default today, but we
    request it explicitly so a future server-side default change can't
    silently collapse our revision history. The wide-format
    ``output_type=2``/``=3`` responses share the endpoint name but
    return ``{date, GDP_YYYYMMDD: value, ...}`` rows our parser ignores.

    The full ALFRED window (``realtime_start='1776-07-04'``,
    ``realtime_end='9999-12-31'``) ensures FRED returns every revision
    instead of just today's vintage. See
    ``docs/design/P1_2_PROVIDER_DISCOVERY.md`` §6.3 for the spike.
    """
    obs = fred.get_observations(
        entry.series_id,
        observation_start=obs_start,
        realtime_start=ALFRED_FULL_HISTORY_START,
        realtime_end=ALFRED_FULL_HISTORY_END,
        sort_order="asc",
        output_type=OUTPUT_TYPE_REAL_TIME_PERIOD,
    )
    for row in obs:
        ok = store.upsert_macro_observation(
            series_id=entry.series_id,
            observation_date=row.observation_date,
            value=row.value,
            realtime_start=row.realtime_start,
            realtime_end=row.realtime_end,
        )
        if ok:
            stats.observations_upserted += 1


# ALFRED accepts the full history range when realtime_start='1776-07-04'
# (FRED's documented sentinel) and realtime_end='9999-12-31'. Anything
# tighter restricts the response to a sub-window of vintages.
ALFRED_FULL_HISTORY_START = date(1776, 7, 4)
ALFRED_FULL_HISTORY_END = date(9999, 12, 31)

# FRED /series/observations output_type values. We pin the two we use
# explicitly so a future API default change can't silently change our
# row shape. See P1_2_PROVIDER_DISCOVERY.md §6.3 for the spike.
OUTPUT_TYPE_REAL_TIME_PERIOD = 1   # full revision history, our parser format
OUTPUT_TYPE_INITIAL_RELEASE = 4    # first publication only