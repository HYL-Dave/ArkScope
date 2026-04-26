#!/usr/bin/env python3
"""Manual P1.2 FRED smoke probe — does NOT run as part of pytest.

Hits the live FRED API with the key from config/.env. Token is redacted
from any output. Verifies:

  - FREDClient.get_series_metadata reads CPIAUCNS and parses last_updated
  - get_release_dates(10) returns recent CPI publish dates
  - Vintage replay: realtime_start=realtime_end=2025-01-15 returns the
    state of the series as known on that date
  - Ingestion path against an in-memory FakeStore (no DB write)

Run: python scripts/p1_2/smoke_fred.py
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

# Ensure project root is on sys.path before importing src.* modules.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from data_sources.fred_client import FREDClient, FREDError  # noqa: E402
from src.macro_calendar.fred_ingestion import (  # noqa: E402
    Catalog, CatalogEntry, fetch_fred_series, load_catalog,
)


def _redacted(s: str, secret: str) -> str:
    return s.replace(secret, "REDACTED") if secret else s


def main() -> int:
    try:
        client = FREDClient()
    except ValueError as exc:
        print(f"FATAL: {exc}")
        return 2
    secret = client._api_key  # only used for redaction

    # 1. Series metadata
    print("\n=== get_series_metadata(CPIAUCNS) ===")
    try:
        meta = client.get_series_metadata("CPIAUCNS")
        print(f"  freq={meta.frequency} units={meta.units!r}")
        print(f"  last_updated={meta.last_updated}")
    except FREDError as exc:
        print(f"  FAILED: {_redacted(str(exc), secret)}")
        return 1

    # 2. Release dates for CPI (release_id=10)
    print("\n=== get_release_dates(10) ===")
    try:
        rds = client.get_release_dates(10, limit=5)
        for r in rds:
            print(f"  {r.release_id} {r.release_date}")
    except FREDError as exc:
        print(f"  FAILED: {_redacted(str(exc), secret)}")
        return 1

    # 3. Vintage replay — value of CPIAUCNS as known on 2025-01-15.
    # Smoke §6 confirmed: latest known then was 2024-12-01 = 315.605.
    print("\n=== vintage replay CPIAUCNS @ 2025-01-15 ===")
    try:
        obs = client.get_observations(
            "CPIAUCNS",
            realtime_start=date(2025, 1, 15),
            realtime_end=date(2025, 1, 15),
            limit=3,
            sort_order="desc",
        )
        for o in obs[:3]:
            print(f"  {o.observation_date} value={o.value} "
                  f"realtime=[{o.realtime_start}, {o.realtime_end}]")
    except FREDError as exc:
        print(f"  FAILED: {_redacted(str(exc), secret)}")
        return 1

    # 4. Catalog load — confirm v1 series resolve
    print("\n=== catalog load ===")
    catalog = load_catalog()
    print(f"  {len(catalog.entries)} series")
    for e in catalog.entries:
        print(f"  {e.series_id:10s} {e.revision_strategy:14s} release_id={e.release_id}")

    # 5. Tiny in-memory ingestion run — single CPIAUCNS observation pulled live.
    # We don't write to the real DB; we use a fake store so the smoke
    # script stays read-only against PG.
    print("\n=== ingestion dry-run (FakeStore, no DB write) ===")

    class FakeStore:
        def __init__(self):
            self.series, self.obs, self.releases = [], [], []
            self._release_dates = {}

        def is_available(self): return True
        def upsert_macro_series(self, p):
            self.series.append(p); return True
        def upsert_release_date(self, *, release_id, release_name, release_date_value):
            self.releases.append((release_id, release_date_value))
            self._release_dates.setdefault(release_id, []).append(release_date_value)
            return True
        def get_release_dates(self, release_id, limit=1000):
            return list(self._release_dates.get(release_id, []))
        def upsert_macro_observation(self, **kw):
            if kw.get("realtime_start") is None:
                raise ValueError("realtime_start mandatory")
            self.obs.append(kw); return True

    store = FakeStore()
    # Pre-seed release schedule manually so latest_only can find a realtime_start.
    for r in client.get_release_dates(10, limit=200):
        store.upsert_release_date(
            release_id=r.release_id, release_name="CPI",
            release_date_value=r.release_date,
        )

    from src.macro_calendar import fred_ingestion as ing
    real_store_factory = ing.MacroCalendarStore
    ing.MacroCalendarStore = lambda dal: store

    # Restrict to one series so the smoke is fast and obvious.
    try:
        stats = fetch_fred_series(
            dal=object(),
            series_ids=["CPIAUCNS"],
            client=client,
            full_refresh=False,
        )
        print(f"  series_processed={stats.series_processed}")
        print(f"  observations_upserted={stats.observations_upserted}")
        print(f"  observations_skipped_no_release={stats.observations_skipped_no_release}")
        print(f"  errors={stats.errors}")
        if store.obs:
            sample = store.obs[0]
            print(f"  first obs upserted: {sample['observation_date']} "
                  f"value={sample['value']} "
                  f"realtime=[{sample['realtime_start']}, {sample['realtime_end']}]")
    finally:
        ing.MacroCalendarStore = real_store_factory

    return 0


if __name__ == "__main__":
    sys.exit(main())