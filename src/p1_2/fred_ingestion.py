"""FRED ingestion pipeline for P1.2 (commit 2/6).

Two callable entry points the job runner wraps:

  - ``fetch_fred_release_dates(dal, ...)`` — refresh
    ``macro_release_dates`` for the curated set of release_ids. Run this
    before ``fetch_fred_series`` so ``latest_only`` ingestion has a
    realtime_start lookup table.
  - ``fetch_fred_series(dal, ...)`` — refresh ``macro_series`` metadata
    + ``macro_observations`` for every series in
    ``config/p1_2_macro_series.yaml``. Strategy is per-series:

      * ``latest_only``: one row per ``observation_date``,
        ``realtime_start = first release_date >= observation_date``
        (joined from ``macro_release_dates``). If no release_date can
        be inferred (e.g. release_id is null or no row in the schedule
        table covers the observation), the row is logged and skipped —
        no sentinel writes (spec §3.2).
      * ``full_vintages``: ALFRED ``vintage_dates`` request returns
        rows already split per realtime window; we upsert each one as
        FRED supplies it.

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
) -> IngestionStats:
    """Refresh ``macro_release_dates`` for the curated release_id set.

    Pass ``release_ids`` to override the catalog (useful for tests).
    Returns an ``IngestionStats`` with ``release_dates_upserted`` populated.
    """
    stats = IngestionStats()
    store = MacroCalendarStore(dal)
    if not store.is_available():
        stats.errors.append("DAL backend unavailable")
        return stats

    if release_ids is None:
        try:
            catalog = load_catalog(catalog_path)
        except Exception as exc:
            stats.errors.append(f"catalog load failed: {exc}")
            return stats
        release_ids = catalog.release_ids()
    release_ids = sorted({int(r) for r in release_ids})

    fred = client or FREDClient()
    for rid in release_ids:
        try:
            rows = fred.get_release_dates(rid, limit=200, sort_order="desc")
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
    """Ingest one row per observation_date with realtime_start derived from
    the release schedule. Skip rows whose realtime_start can't be inferred."""
    obs = fred.get_observations(
        entry.series_id,
        observation_start=obs_start,
        sort_order="asc",
    )
    if not obs:
        return

    release_dates = _release_dates_sorted(store, entry.release_id) if entry.release_id else []
    for row in obs:
        rt = _infer_realtime_start(row.observation_date, release_dates)
        if rt is None:
            stats.observations_skipped_no_release += 1
            logger.debug(
                "skip %s/%s: no release_date covers it",
                entry.series_id, row.observation_date,
            )
            continue
        ok = store.upsert_macro_observation(
            series_id=entry.series_id,
            observation_date=row.observation_date,
            value=row.value,
            realtime_start=rt,
            realtime_end=None,
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

    We don't request specific vintage_dates — FRED's default response
    already collapses each observation to one row per realtime window
    (start → end). For revising series like GDP we therefore see multiple
    rows per observation_date, each with its own [realtime_start,
    realtime_end) range.
    """
    obs = fred.get_observations(
        entry.series_id,
        observation_start=obs_start,
        sort_order="asc",
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


def _release_dates_sorted(store: MacroCalendarStore, release_id: int) -> List[date]:
    """Pull the release schedule from macro_release_dates, ascending."""
    return sorted(store.get_release_dates(release_id, limit=1000))


def _infer_realtime_start(
    observation_date: date,
    release_dates_asc: Sequence[date],
) -> Optional[date]:
    """Return the first scheduled release_date that is >= observation_date.

    That is the earliest date the source would have published this
    observation, so it's a faithful lower bound for ``realtime_start`` in
    a ``latest_only`` series. Returns None when no release covers the
    observation (e.g. observation predates our schedule fetch window) —
    the caller skips the row in that case (spec §3.2).
    """
    if not release_dates_asc:
        return None
    for rd in release_dates_asc:
        if rd >= observation_date:
            return rd
    return None