"""Tests for P1.2 commit 2: FRED HTTP client + ingestion + job wiring.

Strategy:
- Captured fixtures (no network) for FRED responses, hand-edited from
  the round-3 smoke results in P1_2_PROVIDER_DISCOVERY §6.
- Real MacroCalendarStore mocked at the conn level so the SQL shape
  observed during ingestion is the same as commit 1's tests.
- Live FRED calls are NOT in this test module — see
  scripts/p1_2/smoke_fred.py for that.
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from data_sources.fred_client import (
    FREDClient,
    FREDError,
    FREDObservation,
    FREDReleaseDate,
    FREDSeriesMetadata,
    _parse_offset_aware_dt,
    _parse_value,
)
from src.p1_2 import fred_ingestion as ing
from src.p1_2.fred_ingestion import (
    Catalog,
    CatalogEntry,
    IngestionStats,
    _infer_realtime_start,
    fetch_fred_release_dates,
    fetch_fred_series,
)


# ---------------------------------------------------------------------------
# Client parser tests
# ---------------------------------------------------------------------------


class TestClientParsers:
    def test_value_dot_becomes_none(self):
        assert _parse_value(".") is None
        assert _parse_value("") is None
        assert _parse_value(None) is None
        assert _parse_value("3.14") == 3.14
        assert _parse_value("nonsense") is None

    def test_offset_aware_parse_handles_minus_05(self):
        # FRED's actual format: "2026-04-10 08:08:04-05"
        dt = _parse_offset_aware_dt("2026-04-10 08:08:04-05")
        assert dt is not None
        assert dt.tzinfo is not None
        # 08:08 CST == 13:08 UTC
        assert dt.astimezone(timezone.utc).hour == 13
        assert dt.astimezone(timezone.utc).minute == 8

    def test_offset_aware_parse_returns_none_for_empty(self):
        assert _parse_offset_aware_dt(None) is None
        assert _parse_offset_aware_dt("") is None

    def test_offset_aware_parse_promotes_naive_to_utc(self):
        dt = _parse_offset_aware_dt("2026-04-10 08:08:04")
        assert dt is not None
        assert dt.tzinfo == timezone.utc


# ---------------------------------------------------------------------------
# Client HTTP-shape tests via mock requests.Session
# ---------------------------------------------------------------------------


def _mock_response(json_body, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body
    resp.text = "<text body>"
    return resp


class TestClientHttpShape:
    def _make_client(self, response):
        session = MagicMock()
        session.get.return_value = response
        return FREDClient(api_key="dummy", session=session, inter_call_delay_s=0)

    def test_get_observations_includes_token_and_file_type(self):
        client = self._make_client(_mock_response({
            "observations": [
                {"date": "2026-03-01", "value": "330.213",
                 "realtime_start": "2026-04-26", "realtime_end": "9999-12-31"},
            ],
        }))
        rows = client.get_observations("CPIAUCNS", limit=1)
        assert rows == [FREDObservation(
            observation_date=date(2026, 3, 1),
            value=330.213,
            realtime_start=date(2026, 4, 26),
            realtime_end=date(9999, 12, 31),
        )]
        params = client._session.get.call_args.kwargs["params"]
        assert params["api_key"] == "dummy"
        assert params["file_type"] == "json"
        assert params["series_id"] == "CPIAUCNS"

    def test_get_observations_threads_vintages(self):
        client = self._make_client(_mock_response({"observations": []}))
        client.get_observations(
            "GDP",
            vintage_dates=[date(2024, 4, 25), date(2024, 5, 30)],
        )
        params = client._session.get.call_args.kwargs["params"]
        assert params["vintage_dates"] == "2024-04-25,2024-05-30"

    def test_dot_in_value_becomes_none(self):
        client = self._make_client(_mock_response({
            "observations": [
                {"date": "2024-12-01", "value": ".",
                 "realtime_start": "2024-12-02", "realtime_end": "9999-12-31"},
            ],
        }))
        rows = client.get_observations("X")
        assert rows[0].value is None

    def test_429_raises_FREDError(self):
        client = self._make_client(_mock_response({}, status_code=429))
        with pytest.raises(FREDError, match="rate limit"):
            client.get_observations("X")

    def test_get_release_dates_parses_rows(self):
        client = self._make_client(_mock_response({
            "release_dates": [
                {"release_id": 10, "date": "2026-04-10"},
                {"release_id": 10, "date": "2026-03-11"},
            ],
        }))
        rows = client.get_release_dates(10, limit=5)
        assert rows == [
            FREDReleaseDate(release_id=10, release_date=date(2026, 4, 10)),
            FREDReleaseDate(release_id=10, release_date=date(2026, 3, 11)),
        ]

    def test_get_series_metadata_offset_aware(self):
        client = self._make_client(_mock_response({
            "seriess": [{
                "id": "CPIAUCNS",
                "title": "Consumer Price Index",
                "frequency_short": "M",
                "units": "Index 1982-1984=100",
                "seasonal_adjustment_short": "NSA",
                "last_updated": "2026-04-10 08:08:04-05",
            }],
        }))
        meta = client.get_series_metadata("CPIAUCNS")
        assert meta is not None
        assert meta.last_updated is not None
        assert meta.last_updated.tzinfo is not None


# ---------------------------------------------------------------------------
# Catalog loading
# ---------------------------------------------------------------------------


class TestCatalogLoad:
    def test_default_catalog_has_v1_series(self):
        catalog = ing.load_catalog()
        ids = {e.series_id for e in catalog.entries}
        assert {"CPIAUCNS", "FEDFUNDS", "UNRATE", "GDP", "GDPC1",
                "PAYEMS", "DGS10", "DGS2", "T10Y2Y", "VIXCLS",
                "CPILFESL"} <= ids
        assert "M2SL" not in ids  # explicitly deferred per spec §10

    def test_full_vintages_strategy_used_for_GDP(self):
        catalog = ing.load_catalog()
        gdp = next(e for e in catalog.entries if e.series_id == "GDP")
        assert gdp.revision_strategy == "full_vintages"

    def test_latest_only_strategy_used_for_CPIAUCNS(self):
        catalog = ing.load_catalog()
        cpi = next(e for e in catalog.entries if e.series_id == "CPIAUCNS")
        assert cpi.revision_strategy == "latest_only"
        assert cpi.release_id == 10  # CPI release


# ---------------------------------------------------------------------------
# realtime_start inference
# ---------------------------------------------------------------------------


class TestRealtimeStartInference:
    def test_picks_first_release_date_after_observation(self):
        # CPI Mar-2024 actually prints 2024-04-10. Schedule entries:
        # 2024-04-10 covers Mar; the 03-12 entry is for Feb so it's <
        # observation_date 2024-03-01 ... wait no, 03-12 IS >= 03-01.
        # Use a more realistic schedule where the only release ≥ obs_date
        # is the Apr one.
        releases = [date(2024, 1, 11), date(2024, 2, 13),
                    date(2024, 4, 10), date(2024, 5, 15)]
        rt = _infer_realtime_start(date(2024, 3, 1), releases)
        assert rt == date(2024, 4, 10)

    def test_picks_earliest_release_after_obs_even_if_lots_match(self):
        """Sanity: if multiple release_dates are >= obs_date, the first one
        wins. This is the conservative lookahead-safe choice — earliest
        date the data could possibly have been knowable."""
        releases = [date(2024, 3, 5), date(2024, 4, 10), date(2024, 5, 15)]
        rt = _infer_realtime_start(date(2024, 3, 1), releases)
        assert rt == date(2024, 3, 5)

    def test_returns_oldest_release_when_obs_predates_all(self):
        # Observation predates the entire schedule → first available release wins.
        releases = [date(2024, 4, 10), date(2024, 5, 15)]
        rt = _infer_realtime_start(date(1999, 1, 1), releases)
        assert rt == date(2024, 4, 10)

    def test_returns_none_when_obs_postdates_all_releases(self):
        # Observation is after every known release → no upper bound, skip.
        releases = [date(2024, 4, 10), date(2024, 5, 15)]
        rt = _infer_realtime_start(date(2030, 1, 1), releases)
        assert rt is None

    def test_no_releases_yields_none(self):
        assert _infer_realtime_start(date(2024, 1, 1), []) is None


# ---------------------------------------------------------------------------
# Ingestion — latest_only + full_vintages paths via mocked client + store
# ---------------------------------------------------------------------------


class _FakeStore:
    """In-memory MacroCalendarStore replacement for ingestion tests."""

    def __init__(self):
        self.series_writes = []
        self.observation_writes = []
        self.release_date_writes = []
        self._release_dates = {}

    def is_available(self):
        return True

    # macro_series
    def upsert_macro_series(self, payload):
        self.series_writes.append(payload)
        return True

    # macro_release_dates
    def upsert_release_date(self, *, release_id, release_name, release_date_value):
        self.release_date_writes.append((release_id, release_name, release_date_value))
        self._release_dates.setdefault(release_id, []).append(release_date_value)
        return True

    def get_release_dates(self, release_id, limit=1000):
        return list(self._release_dates.get(release_id, []))

    # macro_observations
    def upsert_macro_observation(self, *, series_id, observation_date, value,
                                 realtime_start, realtime_end=None):
        if realtime_start is None:
            raise ValueError("realtime_start is mandatory")
        self.observation_writes.append({
            "series_id": series_id,
            "observation_date": observation_date,
            "value": value,
            "realtime_start": realtime_start,
            "realtime_end": realtime_end,
        })
        return True


def _client_with_canned(metadata=None, observations=None, release_dates=None):
    client = MagicMock(spec=FREDClient)
    client.get_series_metadata.return_value = metadata
    client.get_observations.return_value = observations or []
    client.get_release_dates.return_value = release_dates or []
    return client


def _patch_store(store, monkeypatch):
    """Patch MacroCalendarStore() inside fred_ingestion to return our fake."""
    monkeypatch.setattr(ing, "MacroCalendarStore", lambda dal: store)


def _tiny_catalog(*entries):
    return Catalog(
        entries=tuple(entries),
        observation_start=date(2024, 1, 1),
        release_date_lookback_years=10,
    )


def _patch_catalog(catalog, monkeypatch):
    monkeypatch.setattr(ing, "load_catalog", lambda *_args, **_kwargs: catalog)


class TestLatestOnlyIngestion:
    def test_uses_release_date_for_realtime_start_and_skips_when_missing(
        self, monkeypatch,
    ):
        store = _FakeStore()
        # Pre-seed the release schedule for release_id=10.
        # NB: 2024-03-12 would also satisfy 'release >= 2024-03-01', but
        # in reality that's the Feb-2024 CPI release; for the Mar-2024
        # observation we want 2024-04-10. Drop the 03-12 entry from
        # this fixture so the schedule reflects only releases that
        # actually cover the Mar obs.
        store._release_dates[10] = [
            date(2024, 1, 11), date(2024, 2, 13),
            date(2024, 4, 10),
        ]
        client = _client_with_canned(
            metadata=FREDSeriesMetadata(
                series_id="CPIAUCNS",
                title="CPI",
                frequency="m",
                units="Index 1982-1984=100",
                seasonal_adjustment="NSA",
                last_updated=datetime(2024, 4, 10, 13, 8, tzinfo=timezone.utc),
            ),
            observations=[
                # Mar 2024 obs → realtime_start = 2024-04-10
                FREDObservation(date(2024, 3, 1), 312.332,
                                realtime_start=date(2024, 4, 10),
                                realtime_end=date(9999, 12, 31)),
                # 2099 obs → no release_date covers it → must be SKIPPED.
                FREDObservation(date(2099, 1, 1), 999.99,
                                realtime_start=date(2099, 2, 1),
                                realtime_end=date(9999, 12, 31)),
            ],
        )
        _patch_catalog(_tiny_catalog(CatalogEntry(
            series_id="CPIAUCNS",
            revision_strategy="latest_only",
            release_id=10,
        )), monkeypatch)
        _patch_store(store, monkeypatch)

        stats = fetch_fred_series(
            dal=MagicMock(_backend=MagicMock(_get_conn=MagicMock())),
            client=client,
            full_refresh=True,
        )
        assert stats.series_processed == 1
        assert stats.observations_upserted == 1
        assert stats.observations_skipped_no_release == 1
        # Verify the upserted obs uses the correct realtime_start.
        assert store.observation_writes[0]["realtime_start"] == date(2024, 4, 10)
        # No sentinel write for the skipped one.
        assert all(w["observation_date"] != date(2099, 1, 1)
                   for w in store.observation_writes)


class TestFullVintagesIngestion:
    def test_writes_one_row_per_realtime_window(self, monkeypatch):
        store = _FakeStore()
        client = _client_with_canned(
            metadata=FREDSeriesMetadata(
                series_id="GDP", title="GDP", frequency="q",
                units="$B", seasonal_adjustment="SAAR", last_updated=None,
            ),
            observations=[
                # Same observation_date in two vintages.
                FREDObservation(date(2024, 3, 1), 28000.0,
                                realtime_start=date(2024, 4, 25),
                                realtime_end=date(2024, 5, 30)),
                FREDObservation(date(2024, 3, 1), 28100.5,
                                realtime_start=date(2024, 5, 30),
                                realtime_end=date(9999, 12, 31)),
            ],
        )
        _patch_catalog(_tiny_catalog(CatalogEntry(
            series_id="GDP", revision_strategy="full_vintages",
            release_id=53,
        )), monkeypatch)
        _patch_store(store, monkeypatch)

        stats = fetch_fred_series(
            dal=MagicMock(_backend=MagicMock(_get_conn=MagicMock())),
            client=client,
            full_refresh=True,
        )
        assert stats.observations_upserted == 2
        rt_starts = {w["realtime_start"] for w in store.observation_writes}
        rt_ends = {w["realtime_end"] for w in store.observation_writes}
        assert rt_starts == {date(2024, 4, 25), date(2024, 5, 30)}
        assert rt_ends == {date(2024, 5, 30), date(9999, 12, 31)}


class TestReleaseDateIngestion:
    def test_fetches_from_catalog_release_ids(self, monkeypatch):
        store = _FakeStore()
        _patch_store(store, monkeypatch)
        _patch_catalog(_tiny_catalog(
            CatalogEntry("CPIAUCNS", "latest_only", release_id=10),
            CatalogEntry("FEDFUNDS", "latest_only", release_id=101),
        ), monkeypatch)
        client = MagicMock(spec=FREDClient)

        def _release_dates(release_id, **_kwargs):
            if release_id == 10:
                return [FREDReleaseDate(10, date(2026, 4, 10))]
            if release_id == 101:
                return [FREDReleaseDate(101, date(2026, 4, 1))]
            return []

        client.get_release_dates.side_effect = _release_dates
        stats = fetch_fred_release_dates(
            dal=MagicMock(_backend=MagicMock(_get_conn=MagicMock())),
            client=client,
        )
        assert stats.release_dates_upserted == 2
        assert {(rid, dt) for rid, _, dt in store.release_date_writes} == {
            (10, date(2026, 4, 10)),
            (101, date(2026, 4, 1)),
        }

    def test_skips_null_release_id(self, monkeypatch):
        store = _FakeStore()
        _patch_store(store, monkeypatch)
        # VIXCLS has release_id=None in our v1 catalog.
        _patch_catalog(_tiny_catalog(
            CatalogEntry("VIXCLS", "latest_only", release_id=None),
        ), monkeypatch)
        client = MagicMock(spec=FREDClient)
        stats = fetch_fred_release_dates(
            dal=MagicMock(_backend=MagicMock(_get_conn=MagicMock())),
            client=client,
        )
        assert stats.release_dates_upserted == 0
        client.get_release_dates.assert_not_called()


class TestUnavailableDal:
    def test_filebackend_short_circuits_with_error(self):
        # FileBackend == no _get_conn → store unavailable.
        dal = SimpleNamespace(_backend=object())
        stats = fetch_fred_series(dal=dal, client=MagicMock(spec=FREDClient))
        assert stats.errors and "unavailable" in stats.errors[0]
        assert stats.series_processed == 0


# ---------------------------------------------------------------------------
# Job wiring — the two new JobDefinitions and dispatcher arms
# ---------------------------------------------------------------------------


class TestJobDefinitions:
    def test_jobs_present_when_p1_2_enabled(self):
        from src.agents.config import get_agent_config
        from src.service.jobs import _JOB_DEFINITIONS, _availability_reason

        cfg = get_agent_config()
        original = cfg.p1_2_enabled
        cfg.p1_2_enabled = True
        try:
            assert "fetch_fred_series" in _JOB_DEFINITIONS
            assert "fetch_fred_release_dates" in _JOB_DEFINITIONS
            jd = _JOB_DEFINITIONS["fetch_fred_series"]
            assert jd.feature_flag == "p1_2_enabled"
            assert _availability_reason(jd, cfg) is None
        finally:
            cfg.p1_2_enabled = original

    def test_disabled_reports_availability_reason(self):
        from src.agents.config import get_agent_config
        from src.service.jobs import _JOB_DEFINITIONS, _availability_reason

        cfg = get_agent_config()
        original = cfg.p1_2_enabled
        cfg.p1_2_enabled = False
        try:
            jd = _JOB_DEFINITIONS["fetch_fred_release_dates"]
            reason = _availability_reason(jd, cfg)
            assert reason is not None
            assert "p1_2" in reason
        finally:
            cfg.p1_2_enabled = original


class TestJobDispatchers:
    def test_run_fetch_fred_release_dates_calls_ingestion(self, monkeypatch):
        from src.service.jobs import _run_fetch_fred_release_dates

        captured = {}

        def fake_ingest(dal, *, release_ids=None):
            captured["dal"] = dal
            captured["release_ids"] = release_ids
            return IngestionStats(release_dates_upserted=3)

        monkeypatch.setattr(
            "src.p1_2.fred_ingestion.fetch_fred_release_dates",
            fake_ingest,
        )
        result = _run_fetch_fred_release_dates(
            dal="dal-sentinel",
            params={"release_ids": [10]},
        )
        assert result["release_dates_upserted"] == 3
        assert captured["release_ids"] == [10]

    def test_run_fetch_fred_series_threads_full_refresh(self, monkeypatch):
        from src.service.jobs import _run_fetch_fred_series

        captured = {}

        def fake_ingest(dal, *, series_ids=None, full_refresh=False):
            captured["full_refresh"] = full_refresh
            captured["series_ids"] = series_ids
            return IngestionStats(series_processed=2, observations_upserted=10)

        monkeypatch.setattr(
            "src.p1_2.fred_ingestion.fetch_fred_series",
            fake_ingest,
        )
        result = _run_fetch_fred_series(
            dal="dal-sentinel",
            params={"full_refresh": True, "series_ids": ["CPIAUCNS"]},
        )
        assert result["series_processed"] == 2
        assert captured["full_refresh"] is True


class TestJobSummaries:
    def test_summary_for_release_dates(self):
        from src.service.jobs import _summarize_result
        msg = _summarize_result(
            "fetch_fred_release_dates",
            {"release_dates_upserted": 7, "errors": []},
        )
        assert "Upserted 7" in msg

    def test_summary_for_series_includes_skipped_obs(self):
        from src.service.jobs import _summarize_result
        msg = _summarize_result("fetch_fred_series", {
            "series_processed": 11,
            "series_skipped": 0,
            "observations_upserted": 1234,
            "observations_skipped_no_release": 5,
        })
        assert "Processed 11" in msg
        assert "1234 obs upserted" in msg
        assert "5 obs skipped" in msg