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
from src.macro_calendar import fred_ingestion as ing
from src.macro_calendar.fred_ingestion import (
    ALFRED_FULL_HISTORY_END,
    ALFRED_FULL_HISTORY_START,
    OUTPUT_TYPE_INITIAL_RELEASE,
    OUTPUT_TYPE_REAL_TIME_PERIOD,
    Catalog,
    CatalogEntry,
    IngestionStats,
    _release_dates_page_size,
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

    def test_output_type_sent_as_param(self):
        """output_type must appear in the FRED request params when specified."""
        client = self._make_client(_mock_response({"observations": []}))
        client.get_observations("GDP", output_type=1)
        params = client._session.get.call_args.kwargs["params"]
        assert params["output_type"] == 1

    def test_no_output_type_omits_param(self):
        """When output_type is not given the param must be absent so FRED
        applies its own default (currently =1) rather than receiving an
        explicit value from us."""
        client = self._make_client(_mock_response({"observations": []}))
        client.get_observations("CPIAUCNS")
        params = client._session.get.call_args.kwargs["params"]
        assert "output_type" not in params

    def test_unsupported_output_type_raises_value_error(self):
        """output_type=2/3 return wide-format SERIES_YYYYMMDD rows that our
        parser doesn't handle. The client must reject them at call time rather
        than silently returning an empty list."""
        client = self._make_client(_mock_response({"observations": []}))
        for bad_ot in (2, 3):
            with pytest.raises(ValueError, match="output_type"):
                client.get_observations("GDP", output_type=bad_ot)


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
# Release-dates page size
# ---------------------------------------------------------------------------


class TestReleaseDatesPageSize:
    def test_default_when_no_catalog(self):
        # Smoke: missing catalog still returns a usable cap.
        assert _release_dates_page_size(None) == 1000

    def test_caps_at_1000_for_long_lookback(self):
        catalog = Catalog(
            entries=(),
            observation_start=date(2024, 1, 1),
            release_date_lookback_years=50,
        )
        # 50y * 250 daily releases = 12500, but capped at FRED's 1000.
        assert _release_dates_page_size(catalog) == 1000

    def test_short_lookback_returns_proportional_size(self):
        catalog = Catalog(
            entries=(),
            observation_start=date(2024, 1, 1),
            release_date_lookback_years=2,
        )
        # 2y * 250 = 500.
        assert _release_dates_page_size(catalog) == 500


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
    def test_uses_FRED_realtime_start_authoritatively(self, monkeypatch):
        """Spec §3.2: realtime_start comes from FRED, not from the release
        schedule. The earlier release-schedule join was wrong because a
        within-month release of a different period (Feb CPI on Mar 12)
        would pre-date the observation_date for the new period (Mar 1)
        and leak the value 4 weeks early."""
        store = _FakeStore()
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
                # Mar-2024 CPI was first published 2024-04-10 — that's
                # what FRED returns as realtime_start when ALFRED is engaged.
                FREDObservation(date(2024, 3, 1), 312.332,
                                realtime_start=date(2024, 4, 10),
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
        assert stats.observations_skipped_no_release == 0
        assert store.observation_writes[0]["realtime_start"] == date(2024, 4, 10)

    def test_latest_only_passes_full_alfred_window_to_client(self, monkeypatch):
        """The latest_only path must request the full ALFRED window so the
        returned realtime_start equals the FIRST publication date, not
        today (FRED's default vintage). Without this, realtime_start
        collapses to today and a backtest at decision_date < today
        cannot see the value at all."""
        store = _FakeStore()
        client = _client_with_canned(
            metadata=FREDSeriesMetadata(
                series_id="CPIAUCNS", title="x", frequency="m",
                units="x", seasonal_adjustment=None, last_updated=None,
            ),
            observations=[],
        )
        _patch_catalog(_tiny_catalog(CatalogEntry(
            series_id="CPIAUCNS",
            revision_strategy="latest_only",
            release_id=10,
        )), monkeypatch)
        _patch_store(store, monkeypatch)

        fetch_fred_series(
            dal=MagicMock(_backend=MagicMock(_get_conn=MagicMock())),
            client=client,
            full_refresh=True,
        )
        kwargs = client.get_observations.call_args.kwargs
        assert kwargs["realtime_start"] == ALFRED_FULL_HISTORY_START
        assert kwargs["realtime_end"] == ALFRED_FULL_HISTORY_END

    def test_latest_only_passes_each_row_to_store(self, monkeypatch):
        """With output_type=4, FRED returns at most one row per observation_date
        (the initial release). The ingestion path passes each row straight to
        the store; deduplication is handled at the DB layer via ON CONFLICT.
        Two observation_dates → two store writes."""
        store = _FakeStore()
        client = _client_with_canned(
            metadata=FREDSeriesMetadata(
                series_id="CPIAUCNS", title="x", frequency="m",
                units="x", seasonal_adjustment=None, last_updated=None,
            ),
            observations=[
                # Separate observation_dates — one row each (output_type=4
                # guarantees this in production; we verify the write-through).
                FREDObservation(date(2024, 2, 1), 311.054,
                                realtime_start=date(2024, 3, 12),
                                realtime_end=date(9999, 12, 31)),
                FREDObservation(date(2024, 3, 1), 312.332,
                                realtime_start=date(2024, 4, 10),
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
        assert stats.observations_upserted == 2
        obs_dates = {w["observation_date"] for w in store.observation_writes}
        assert obs_dates == {date(2024, 2, 1), date(2024, 3, 1)}

    def test_latest_only_uses_output_type_initial_release(self, monkeypatch):
        """latest_only ingestion must pass output_type=4 (Initial Release Only)
        so FRED returns exactly one row per observation_date carrying the
        first-publication realtime_start. Live evidence (GDP 2024-Q1 spike,
        §6.3): output_type=4 → 1 row vs output_type=1 → 5 revision rows."""
        store = _FakeStore()
        client = _client_with_canned(
            metadata=FREDSeriesMetadata(
                series_id="CPIAUCNS", title="x", frequency="m",
                units="x", seasonal_adjustment=None, last_updated=None,
            ),
            observations=[],
        )
        _patch_catalog(_tiny_catalog(CatalogEntry(
            series_id="CPIAUCNS",
            revision_strategy="latest_only",
            release_id=10,
        )), monkeypatch)
        _patch_store(store, monkeypatch)

        fetch_fred_series(
            dal=MagicMock(_backend=MagicMock(_get_conn=MagicMock())),
            client=client,
            full_refresh=True,
        )
        kwargs = client.get_observations.call_args.kwargs
        assert kwargs["output_type"] == OUTPUT_TYPE_INITIAL_RELEASE  # 4


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

    def test_full_vintages_passes_full_alfred_window_to_client(self, monkeypatch):
        """Without these params FRED collapses the response to today's
        vintage and the 'full revision history' contract silently breaks.
        The previous implementation forgot this and stored only current
        values for GDP / GDPC1 / PAYEMS — see review of f03cf86."""
        store = _FakeStore()
        client = _client_with_canned(
            metadata=FREDSeriesMetadata(
                series_id="GDP", title="GDP", frequency="q",
                units="$B", seasonal_adjustment="SAAR", last_updated=None,
            ),
            observations=[],
        )
        _patch_catalog(_tiny_catalog(CatalogEntry(
            series_id="GDP", revision_strategy="full_vintages",
            release_id=53,
        )), monkeypatch)
        _patch_store(store, monkeypatch)

        fetch_fred_series(
            dal=MagicMock(_backend=MagicMock(_get_conn=MagicMock())),
            client=client,
            full_refresh=True,
        )
        kwargs = client.get_observations.call_args.kwargs
        assert kwargs["realtime_start"] == ALFRED_FULL_HISTORY_START
        assert kwargs["realtime_end"] == ALFRED_FULL_HISTORY_END

    def test_full_vintages_uses_output_type_real_time_period(self, monkeypatch):
        """full_vintages ingestion must pass output_type=1 (By Real-Time Period)
        explicitly. output_type=1 IS the current FRED default, but we pin it
        defensively so a future server-side default change can't silently
        collapse revision history into a single today's-vintage row.
        Live evidence (§6.3 spike): output_type=1 → 5 rows for GDP 2024-Q1
        vs output_type=4 → 1 row."""
        store = _FakeStore()
        client = _client_with_canned(
            metadata=FREDSeriesMetadata(
                series_id="GDP", title="GDP", frequency="q",
                units="$B", seasonal_adjustment="SAAR", last_updated=None,
            ),
            observations=[],
        )
        _patch_catalog(_tiny_catalog(CatalogEntry(
            series_id="GDP", revision_strategy="full_vintages",
            release_id=53,
        )), monkeypatch)
        _patch_store(store, monkeypatch)

        fetch_fred_series(
            dal=MagicMock(_backend=MagicMock(_get_conn=MagicMock())),
            client=client,
            full_refresh=True,
        )
        kwargs = client.get_observations.call_args.kwargs
        assert kwargs["output_type"] == OUTPUT_TYPE_REAL_TIME_PERIOD  # 1


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

    def test_uses_catalog_lookback_for_page_size(self, monkeypatch):
        """Default catalog asks for 50 years; that maps to the FRED-cap
        1000 page size (vs. the previous hardcoded 200)."""
        store = _FakeStore()
        _patch_store(store, monkeypatch)
        _patch_catalog(Catalog(
            entries=(CatalogEntry("CPIAUCNS", "latest_only", release_id=10),),
            observation_start=date(2024, 1, 1),
            release_date_lookback_years=50,
        ), monkeypatch)
        client = MagicMock(spec=FREDClient)
        client.get_release_dates.return_value = []
        fetch_fred_release_dates(
            dal=MagicMock(_backend=MagicMock(_get_conn=MagicMock())),
            client=client,
        )
        kwargs = client.get_release_dates.call_args.kwargs
        assert kwargs["limit"] == 1000

    def test_explicit_limit_overrides_catalog(self, monkeypatch):
        store = _FakeStore()
        _patch_store(store, monkeypatch)
        _patch_catalog(_tiny_catalog(
            CatalogEntry("CPIAUCNS", "latest_only", release_id=10),
        ), monkeypatch)
        client = MagicMock(spec=FREDClient)
        client.get_release_dates.return_value = []
        fetch_fred_release_dates(
            dal=MagicMock(_backend=MagicMock(_get_conn=MagicMock())),
            client=client,
            limit=42,
        )
        kwargs = client.get_release_dates.call_args.kwargs
        assert kwargs["limit"] == 42


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
    def test_jobs_present_when_macro_calendar_enabled(self):
        from src.agents.config import get_agent_config
        from src.service.jobs import _JOB_DEFINITIONS, _availability_reason

        cfg = get_agent_config()
        original = cfg.macro_calendar_enabled
        cfg.macro_calendar_enabled = True
        try:
            assert "fetch_fred_series" in _JOB_DEFINITIONS
            assert "fetch_fred_release_dates" in _JOB_DEFINITIONS
            jd = _JOB_DEFINITIONS["fetch_fred_series"]
            assert jd.feature_flag == "macro_calendar_enabled"
            assert _availability_reason(jd, cfg) is None
        finally:
            cfg.macro_calendar_enabled = original

    def test_disabled_reports_availability_reason(self):
        from src.agents.config import get_agent_config
        from src.service.jobs import _JOB_DEFINITIONS, _availability_reason

        cfg = get_agent_config()
        original = cfg.macro_calendar_enabled
        cfg.macro_calendar_enabled = False
        try:
            jd = _JOB_DEFINITIONS["fetch_fred_release_dates"]
            reason = _availability_reason(jd, cfg)
            assert reason is not None
            assert "macro_calendar" in reason
        finally:
            cfg.macro_calendar_enabled = original


class TestJobDispatchers:
    def test_run_fetch_fred_release_dates_calls_ingestion(self, monkeypatch):
        from src.service.jobs import _run_fetch_fred_release_dates

        captured = {}

        def fake_ingest(dal, *, release_ids=None):
            captured["dal"] = dal
            captured["release_ids"] = release_ids
            return IngestionStats(release_dates_upserted=3)

        monkeypatch.setattr(
            "src.macro_calendar.fred_ingestion.fetch_fred_release_dates",
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
            "src.macro_calendar.fred_ingestion.fetch_fred_series",
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