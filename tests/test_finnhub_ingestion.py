"""Tests for P1.2 commit 3: Finnhub calendar client + ingestion.

Strategy:
- Captured fixtures (no network) for Finnhub response shapes, hand-edited
  from the smoke results in P1_2_PROVIDER_DISCOVERY §5.
- FinnhubCalendarClient tested via mock requests.Session.
- Ingestion functions tested via a stateful _FakeCalendarStore that returns
  configurable (event_id, action) pairs per call.
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

from data_sources.finnhub_calendar_client import (
    FinnhubCalendarClient,
    FinnhubEarningsEvent,
    FinnhubEconomicEvent,
    FinnhubError,
    FinnhubIPOEvent,
    _earnings_from_json,
    _economic_from_json,
    _ipo_from_json,
    _normalize_hour,
    _normalize_impact,
    _parse_finnhub_time,
)
from src.macro_calendar import finnhub_ingestion as ing
from src.macro_calendar.finnhub_ingestion import (
    FinnhubIngestionStats,
    fetch_finnhub_earnings_events,
    fetch_finnhub_economic_events,
    fetch_finnhub_ipo_events,
)


# ---------------------------------------------------------------------------
# Parser unit tests (no network, no DB)
# ---------------------------------------------------------------------------


class TestParseFinnhubTime:
    def test_fomc_19_utc(self):
        """Smoke §5.2 anchor: FOMC at "2024-12-18 19:00:00" = 14:00 ET → UTC."""
        dt = _parse_finnhub_time("2024-12-18 19:00:00")
        assert dt is not None
        assert dt.tzinfo == timezone.utc
        assert dt.year == 2024
        assert dt.month == 12
        assert dt.day == 18
        assert dt.hour == 19
        assert dt.minute == 0

    def test_returns_none_for_empty(self):
        assert _parse_finnhub_time(None) is None
        assert _parse_finnhub_time("") is None

    def test_returns_none_for_malformed(self):
        assert _parse_finnhub_time("not-a-date") is None
        assert _parse_finnhub_time("2024-12-18") is None  # missing time component


class TestNormalizeImpactHour:
    def test_valid_impact_lowercased(self):
        assert _normalize_impact("LOW") == "low"
        assert _normalize_impact("Medium") == "medium"
        assert _normalize_impact("HIGH") == "high"

    def test_unknown_impact_becomes_empty(self):
        assert _normalize_impact("critical") == ""
        assert _normalize_impact(None) == ""
        assert _normalize_impact("") == ""

    def test_valid_hour_lowercased(self):
        assert _normalize_hour("BMO") == "bmo"
        assert _normalize_hour("amc") == "amc"
        assert _normalize_hour("DMH") == "dmh"

    def test_unknown_hour_becomes_empty(self):
        assert _normalize_hour("premarket") == ""
        assert _normalize_hour(None) == ""


class TestEconomicFromJson:
    def _row(self, **overrides):
        base = {
            "country": "US",
            "event": "Fed Interest Rate Decision",
            "time": "2024-12-18 19:00:00",
            "impact": "high",
            "unit": "%",
            "actual": 4.25,
            "estimate": 4.5,
            "prev": 4.75,
        }
        base.update(overrides)
        return base

    def test_parses_full_row(self):
        ev = _economic_from_json(self._row())
        assert ev is not None
        assert ev.country == "US"
        assert ev.event == "Fed Interest Rate Decision"
        assert ev.event_time == datetime(2024, 12, 18, 19, 0, tzinfo=timezone.utc)
        assert ev.impact == "high"
        assert ev.unit == "%"
        assert ev.actual == 4.25
        assert ev.estimate == 4.5
        assert ev.prev == 4.75

    def test_null_actual_becomes_none(self):
        ev = _economic_from_json(self._row(actual=None, estimate=None, prev=None))
        assert ev is not None
        assert ev.actual is None
        assert ev.estimate is None
        assert ev.prev is None

    def test_missing_country_yields_none(self):
        assert _economic_from_json(self._row(country="")) is None
        assert _economic_from_json(self._row(country=None)) is None

    def test_missing_event_yields_none(self):
        assert _economic_from_json(self._row(event="")) is None

    def test_missing_time_yields_none(self):
        assert _economic_from_json(self._row(time=None)) is None
        assert _economic_from_json(self._row(time="")) is None

    def test_unknown_impact_normalised_to_empty(self):
        ev = _economic_from_json(self._row(impact="EXTREME"))
        assert ev is not None
        assert ev.impact == ""

    def test_unit_empty_string_preserved(self):
        ev = _economic_from_json(self._row(unit=""))
        assert ev is not None
        assert ev.unit == ""

    def test_country_uppercased(self):
        ev = _economic_from_json(self._row(country="cn"))
        assert ev is not None
        assert ev.country == "CN"


class TestEarningsFromJson:
    def _row(self, **overrides):
        base = {
            "symbol": "AAPL",
            "date": "2026-04-30",
            "year": 2026,
            "quarter": 2,
            "hour": "amc",
            "epsEstimate": 1.98,
            "epsActual": None,
            "revenueEstimate": 94000000000.0,
            "revenueActual": None,
        }
        base.update(overrides)
        return base

    def test_parses_full_row(self):
        ev = _earnings_from_json(self._row())
        assert ev is not None
        assert ev.symbol == "AAPL"
        assert ev.report_date == date(2026, 4, 30)
        assert ev.year == 2026
        assert ev.quarter == 2
        assert ev.hour == "amc"
        assert ev.eps_estimate == 1.98
        assert ev.eps_actual is None

    def test_symbol_uppercased(self):
        ev = _earnings_from_json(self._row(symbol="nvda"))
        assert ev is not None
        assert ev.symbol == "NVDA"

    def test_missing_symbol_yields_none(self):
        assert _earnings_from_json(self._row(symbol="")) is None
        assert _earnings_from_json(self._row(symbol=None)) is None

    def test_missing_date_yields_none(self):
        assert _earnings_from_json(self._row(date=None)) is None

    def test_invalid_quarter_yields_none(self):
        assert _earnings_from_json(self._row(quarter=0)) is None
        assert _earnings_from_json(self._row(quarter=5)) is None

    def test_unknown_hour_normalised(self):
        ev = _earnings_from_json(self._row(hour="PREMARKET"))
        assert ev is not None
        assert ev.hour == ""


class TestIpoFromJson:
    def _row(self, **overrides):
        base = {
            "name": "CoreWeave Inc",
            "date": "2025-03-28",
            "symbol": "CRWV",
            "exchange": "NASDAQ Global Select",
            "status": "priced",
            "numberOfShares": 37500000,
            "price": 40.0,
            "totalSharesValue": 1500000000.0,
        }
        base.update(overrides)
        return base

    def test_parses_full_row(self):
        ev = _ipo_from_json(self._row())
        assert ev is not None
        assert ev.name == "CoreWeave Inc"
        assert ev.ipo_date == date(2025, 3, 28)
        assert ev.symbol == "CRWV"
        assert ev.exchange == "NASDAQ Global Select"
        assert ev.status == "priced"
        assert ev.number_of_shares == 37500000
        assert ev.price == 40.0

    def test_null_symbol_becomes_none(self):
        ev = _ipo_from_json(self._row(symbol=None))
        assert ev is not None
        assert ev.symbol is None

    def test_empty_exchange_becomes_none(self):
        ev = _ipo_from_json(self._row(exchange=""))
        assert ev is not None
        assert ev.exchange is None

    def test_missing_name_yields_none(self):
        assert _ipo_from_json(self._row(name="")) is None

    def test_missing_date_yields_none(self):
        assert _ipo_from_json(self._row(date=None)) is None

    def test_invalid_status_yields_none(self):
        assert _ipo_from_json(self._row(status="cancelled")) is None
        assert _ipo_from_json(self._row(status="")) is None

    def test_status_lowercased(self):
        ev = _ipo_from_json(self._row(status="PRICED"))
        assert ev is not None
        assert ev.status == "priced"


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
        return FinnhubCalendarClient(
            api_key="dummy", session=session, inter_call_delay_s=0
        )

    def test_token_in_every_request(self):
        client = self._make_client(_mock_response({"economicCalendar": []}))
        client.get_economic_events(date(2024, 1, 1), date(2024, 1, 7))
        params = client._session.get.call_args.kwargs["params"]
        assert params["token"] == "dummy"

    def test_economic_events_threads_date_range(self):
        client = self._make_client(_mock_response({"economicCalendar": []}))
        client.get_economic_events(date(2024, 1, 1), date(2024, 1, 7))
        params = client._session.get.call_args.kwargs["params"]
        assert params["from"] == "2024-01-01"
        assert params["to"] == "2024-01-07"

    def test_economic_events_parses_rows(self):
        client = self._make_client(_mock_response({
            "economicCalendar": [{
                "country": "US",
                "event": "Fed Interest Rate Decision",
                "time": "2024-12-18 19:00:00",
                "impact": "high",
                "unit": "%",
                "actual": 4.25,
                "estimate": 4.5,
                "prev": 4.75,
            }],
        }))
        rows = client.get_economic_events(date(2024, 12, 17), date(2024, 12, 19))
        assert len(rows) == 1
        assert isinstance(rows[0], FinnhubEconomicEvent)
        assert rows[0].country == "US"
        assert rows[0].event_time == datetime(2024, 12, 18, 19, 0, tzinfo=timezone.utc)

    def test_economic_events_skips_bad_rows(self):
        """Rows without required fields are silently dropped; valid rows kept."""
        client = self._make_client(_mock_response({
            "economicCalendar": [
                {"country": "", "event": "x", "time": "2024-01-01 00:00:00"},  # no country
                {"country": "US", "event": "CPI", "time": "2024-01-12 13:30:00",
                 "impact": "high", "unit": "%", "actual": None, "estimate": 3.1, "prev": 3.4},
            ],
        }))
        rows = client.get_economic_events(date(2024, 1, 1), date(2024, 1, 31))
        assert len(rows) == 1
        assert rows[0].event == "CPI"

    def test_earnings_events_threads_symbol_param(self):
        client = self._make_client(_mock_response({"earningsCalendar": []}))
        client.get_earnings_events(date(2026, 4, 1), date(2026, 4, 30), symbol="aapl")
        params = client._session.get.call_args.kwargs["params"]
        assert params["symbol"] == "AAPL"

    def test_earnings_events_no_symbol_omits_param(self):
        client = self._make_client(_mock_response({"earningsCalendar": []}))
        client.get_earnings_events(date(2026, 4, 1), date(2026, 4, 30))
        params = client._session.get.call_args.kwargs["params"]
        assert "symbol" not in params

    def test_ipo_events_parses_status_and_null_exchange(self):
        client = self._make_client(_mock_response({
            "ipoCalendar": [{
                "name": "Acme Corp",
                "date": "2026-06-15",
                "symbol": "ACME",
                "exchange": None,
                "status": "expected",
                "numberOfShares": 5000000,
                "price": 12.0,
                "totalSharesValue": 60000000.0,
            }],
        }))
        rows = client.get_ipo_events(date(2026, 6, 1), date(2026, 6, 30))
        assert len(rows) == 1
        assert rows[0].status == "expected"
        assert rows[0].exchange is None

    def test_401_raises_finnhub_error(self):
        client = self._make_client(_mock_response({}, status_code=401))
        with pytest.raises(FinnhubError, match="401"):
            client.get_economic_events(date(2024, 1, 1), date(2024, 1, 7))

    def test_429_raises_finnhub_error(self):
        client = self._make_client(_mock_response({}, status_code=429))
        with pytest.raises(FinnhubError, match="rate limit"):
            client.get_ipo_events(date(2026, 1, 1), date(2026, 4, 30))

    def test_500_raises_finnhub_error(self):
        client = self._make_client(_mock_response({}, status_code=500))
        with pytest.raises(FinnhubError, match="HTTP 500"):
            client.get_earnings_events(date(2026, 4, 1), date(2026, 4, 30))


# ---------------------------------------------------------------------------
# Ingestion — mocked client + stateful fake store
# ---------------------------------------------------------------------------


class _FakeCalendarStore:
    """Stateful store replacement for ingestion tests.

    ``responses`` is a list of ``(event_id, action)`` tuples popped in
    order. When exhausted, defaults to ``(call_count, "inserted")``.
    """

    def __init__(self, responses=None):
        self.economic_calls = []
        self.earnings_calls = []
        self.ipo_calls = []
        self._responses = list(responses or [])

    def is_available(self):
        return True

    def _pop(self, call_list, payload):
        call_list.append(payload)
        if self._responses:
            return self._responses.pop(0)
        return (len(call_list), "inserted")

    def upsert_economic_event(self, payload, *, source_payload, observed_at=None):
        return self._pop(self.economic_calls, payload)

    def upsert_earnings_event(self, payload, *, source_payload, observed_at=None):
        return self._pop(self.earnings_calls, payload)

    def upsert_ipo_event(self, payload, *, source_payload, observed_at=None):
        return self._pop(self.ipo_calls, payload)


def _client_with_economic(*events):
    client = MagicMock(spec=FinnhubCalendarClient)
    client.get_economic_events.return_value = list(events)
    return client


def _client_with_earnings(*events):
    client = MagicMock(spec=FinnhubCalendarClient)
    client.get_earnings_events.return_value = list(events)
    return client


def _client_with_ipo(*events):
    client = MagicMock(spec=FinnhubCalendarClient)
    client.get_ipo_events.return_value = list(events)
    return client


def _patch_store(store, monkeypatch):
    monkeypatch.setattr(ing, "MacroCalendarStore", lambda dal: store)


_FOMC_EVENT = FinnhubEconomicEvent(
    country="US",
    event="Fed Interest Rate Decision",
    event_time=datetime(2024, 12, 18, 19, 0, tzinfo=timezone.utc),
    impact="high",
    unit="%",
    actual=4.25,
    estimate=4.5,
    prev=4.75,
)

_CPI_EVENT = FinnhubEconomicEvent(
    country="US",
    event="CPI m/m",
    event_time=datetime(2024, 1, 11, 13, 30, tzinfo=timezone.utc),
    impact="high",
    unit="%",
    actual=None,
    estimate=0.2,
    prev=0.1,
)

_AAPL_EARNINGS = FinnhubEarningsEvent(
    symbol="AAPL",
    report_date=date(2026, 4, 30),
    year=2026,
    quarter=2,
    hour="amc",
    eps_estimate=1.9801,
    eps_actual=None,
    revenue_estimate=94000000000.0,
    revenue_actual=None,
)

_NVDA_EARNINGS = FinnhubEarningsEvent(
    symbol="NVDA",
    report_date=date(2026, 5, 28),
    year=2026,
    quarter=1,
    hour="amc",
    eps_estimate=0.89,
    eps_actual=None,
    revenue_estimate=43500000000.0,
    revenue_actual=None,
)

_COREWEAVE_IPO = FinnhubIPOEvent(
    name="CoreWeave Inc",
    ipo_date=date(2025, 3, 28),
    symbol="CRWV",
    exchange="NASDAQ Global Select",
    status="priced",
    number_of_shares=37500000,
    price=40.0,
    total_shares_value=1500000000.0,
)


class TestEconomicIngestion:
    def test_calls_store_with_correct_payload(self, monkeypatch):
        store = _FakeCalendarStore()
        _patch_store(store, monkeypatch)
        client = _client_with_economic(_FOMC_EVENT)

        stats = fetch_finnhub_economic_events(
            dal=MagicMock(),
            date_from=date(2024, 12, 17),
            date_to=date(2024, 12, 19),
            client=client,
        )
        assert stats.events_inserted == 1
        assert len(store.economic_calls) == 1
        p = store.economic_calls[0]
        assert p["country"] == "US"
        assert p["event_name"] == "Fed Interest Rate Decision"
        assert p["event_time"] == datetime(2024, 12, 18, 19, 0, tzinfo=timezone.utc)
        assert p["impact"] == "high"
        assert p["actual"] == 4.25
        assert p["estimate"] == 4.5
        assert p["prev"] == 4.75

    def test_counts_inserted_mutated_unchanged(self, monkeypatch):
        store = _FakeCalendarStore(responses=[
            (1, "inserted"),
            (1, "mutated"),
            (2, "unchanged"),
        ])
        _patch_store(store, monkeypatch)
        client = _client_with_economic(_FOMC_EVENT, _CPI_EVENT, _FOMC_EVENT)

        stats = fetch_finnhub_economic_events(
            dal=MagicMock(),
            date_from=date(2024, 12, 1),
            date_to=date(2024, 12, 31),
            client=client,
        )
        assert stats.events_inserted == 1
        assert stats.events_mutated == 1
        assert stats.events_unchanged == 1
        assert stats.events_skipped == 0

    def test_api_error_recorded_in_stats(self, monkeypatch):
        store = _FakeCalendarStore()
        _patch_store(store, monkeypatch)
        client = MagicMock(spec=FinnhubCalendarClient)
        client.get_economic_events.side_effect = FinnhubError("rate limit")

        stats = fetch_finnhub_economic_events(
            dal=MagicMock(),
            date_from=date(2024, 1, 1),
            date_to=date(2024, 1, 31),
            client=client,
        )
        assert stats.events_inserted == 0
        assert len(stats.errors) == 1
        assert "rate limit" in stats.errors[0]

    def test_store_exception_increments_skipped(self, monkeypatch):
        """If upsert raises (e.g. DB error), the row is counted as skipped
        and the ingestion continues with subsequent rows."""
        class _BrokenStore(_FakeCalendarStore):
            def upsert_economic_event(self, payload, **_kw):
                raise RuntimeError("DB connection lost")

        _patch_store(_BrokenStore(), monkeypatch)
        client = _client_with_economic(_FOMC_EVENT, _CPI_EVENT)

        stats = fetch_finnhub_economic_events(
            dal=MagicMock(),
            date_from=date(2024, 12, 1),
            date_to=date(2024, 12, 31),
            client=client,
        )
        assert stats.events_skipped == 2
        assert len(stats.errors) == 2

    def test_unavailable_dal_short_circuits(self):
        dal = SimpleNamespace(_backend=object())
        stats = fetch_finnhub_economic_events(
            dal=dal,
            date_from=date(2024, 1, 1),
            date_to=date(2024, 1, 31),
            client=MagicMock(spec=FinnhubCalendarClient),
        )
        assert stats.errors and "unavailable" in stats.errors[0]
        assert stats.events_inserted == 0


class TestEarningsIngestion:
    def test_per_symbol_issues_one_call_per_symbol(self, monkeypatch):
        """With symbols=['AAPL','NVDA'], two API calls should be issued."""
        store = _FakeCalendarStore()
        _patch_store(store, monkeypatch)
        client = MagicMock(spec=FinnhubCalendarClient)
        client.get_earnings_events.return_value = []

        fetch_finnhub_earnings_events(
            dal=MagicMock(),
            date_from=date(2026, 4, 1),
            date_to=date(2026, 5, 31),
            symbols=["AAPL", "NVDA"],
            client=client,
        )
        assert client.get_earnings_events.call_count == 2
        called_symbols = {
            call.kwargs.get("symbol")
            for call in client.get_earnings_events.call_args_list
        }
        assert called_symbols == {"AAPL", "NVDA"}

    def test_no_symbols_issues_one_unfiltered_call(self, monkeypatch):
        store = _FakeCalendarStore()
        _patch_store(store, monkeypatch)
        client = MagicMock(spec=FinnhubCalendarClient)
        client.get_earnings_events.return_value = []

        fetch_finnhub_earnings_events(
            dal=MagicMock(),
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 30),
            client=client,
        )
        assert client.get_earnings_events.call_count == 1
        _, kwargs = client.get_earnings_events.call_args
        assert kwargs.get("symbol") is None

    def test_deduplicates_same_symbol_year_quarter(self, monkeypatch):
        """If AAPL Q2 2026 appears in both per-symbol queries (e.g. from a
        sweep that queries AAPL then a broader list), it must be written
        exactly once."""
        store = _FakeCalendarStore()
        _patch_store(store, monkeypatch)
        client = MagicMock(spec=FinnhubCalendarClient)
        # Both calls return the same AAPL Q2 row.
        client.get_earnings_events.return_value = [_AAPL_EARNINGS]

        stats = fetch_finnhub_earnings_events(
            dal=MagicMock(),
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 30),
            symbols=["AAPL", "AAPL"],  # duplicate in caller list
            client=client,
        )
        assert stats.events_inserted == 1
        assert len(store.earnings_calls) == 1

    def test_maps_camelcase_to_snake_case_in_payload(self, monkeypatch):
        """epsEstimate from Finnhub must land as eps_estimate in the store
        payload so it matches the SQL column name."""
        store = _FakeCalendarStore()
        _patch_store(store, monkeypatch)
        client = _client_with_earnings(_AAPL_EARNINGS)

        fetch_finnhub_earnings_events(
            dal=MagicMock(),
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 30),
            client=client,
        )
        p = store.earnings_calls[0]
        assert "eps_estimate" in p
        assert p["eps_estimate"] == 1.9801
        assert "epsEstimate" not in p


class TestIPOIngestion:
    def test_calls_store_with_correct_payload(self, monkeypatch):
        store = _FakeCalendarStore()
        _patch_store(store, monkeypatch)
        client = _client_with_ipo(_COREWEAVE_IPO)

        stats = fetch_finnhub_ipo_events(
            dal=MagicMock(),
            date_from=date(2025, 3, 1),
            date_to=date(2025, 3, 31),
            client=client,
        )
        assert stats.events_inserted == 1
        p = store.ipo_calls[0]
        assert p["name"] == "CoreWeave Inc"
        assert p["ipo_date"] == date(2025, 3, 28)
        assert p["status"] == "priced"
        assert p["price"] == 40.0
        assert p["number_of_shares"] == 37500000

    def test_camelcase_fields_mapped_correctly(self, monkeypatch):
        """numberOfShares → number_of_shares and totalSharesValue →
        total_shares_value must be present in the payload (SQL column names)
        and absent in camelCase form."""
        store = _FakeCalendarStore()
        _patch_store(store, monkeypatch)
        client = _client_with_ipo(_COREWEAVE_IPO)

        fetch_finnhub_ipo_events(
            dal=MagicMock(),
            date_from=date(2025, 3, 1),
            date_to=date(2025, 3, 31),
            client=client,
        )
        p = store.ipo_calls[0]
        assert "number_of_shares" in p
        assert "numberOfShares" not in p
        assert "total_shares_value" in p
        assert "totalSharesValue" not in p

    def test_revision_action_counted(self, monkeypatch):
        store = _FakeCalendarStore(responses=[(1, "mutated")])
        _patch_store(store, monkeypatch)
        client = _client_with_ipo(_COREWEAVE_IPO)

        stats = fetch_finnhub_ipo_events(
            dal=MagicMock(),
            date_from=date(2025, 3, 1),
            date_to=date(2025, 3, 31),
            client=client,
        )
        assert stats.events_mutated == 1
        assert stats.events_inserted == 0

    def test_api_error_recorded(self, monkeypatch):
        store = _FakeCalendarStore()
        _patch_store(store, monkeypatch)
        client = MagicMock(spec=FinnhubCalendarClient)
        client.get_ipo_events.side_effect = FinnhubError("timeout")

        stats = fetch_finnhub_ipo_events(
            dal=MagicMock(),
            date_from=date(2025, 1, 1),
            date_to=date(2025, 3, 31),
            client=client,
        )
        assert stats.events_inserted == 0
        assert any("timeout" in e for e in stats.errors)


# ---------------------------------------------------------------------------
# Job wiring — JobDefinitions, dispatchers, summaries
# ---------------------------------------------------------------------------


class TestFinnhubJobDefinitions:
    """Verify the four Finnhub calendar JobDefinitions are registered and
    correctly gated on macro_calendar_enabled."""

    _JOB_NAMES = (
        "fetch_economic_calendar_recent",
        "fetch_economic_calendar_backfill",
        "fetch_earnings_calendar",
        "fetch_ipo_calendar",
    )

    def test_jobs_present_when_macro_calendar_enabled(self):
        from src.agents.config import get_agent_config
        from src.service.jobs import _JOB_DEFINITIONS, _availability_reason

        cfg = get_agent_config()
        original = cfg.macro_calendar_enabled
        cfg.macro_calendar_enabled = True
        try:
            for name in self._JOB_NAMES:
                assert name in _JOB_DEFINITIONS, f"{name} missing from registry"
                jd = _JOB_DEFINITIONS[name]
                assert jd.feature_flag == "macro_calendar_enabled"
                assert jd.runnable_via_api is True
                assert jd.source == "api"
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
            for name in self._JOB_NAMES:
                reason = _availability_reason(_JOB_DEFINITIONS[name], cfg)
                assert reason is not None
                assert "macro_calendar" in reason
        finally:
            cfg.macro_calendar_enabled = original


def _capture_call(monkeypatch, ingestion_path):
    """Patch the named ingestion function and return a dict that captures
    its kwargs on each invocation, plus a stub return value."""
    captured: Dict[str, Any] = {}

    def fake(dal, **kwargs):
        captured["dal"] = dal
        captured.update(kwargs)
        return FinnhubIngestionStats(events_inserted=1)

    monkeypatch.setattr(ingestion_path, fake)
    return captured


class TestEconomicRecentDispatcher:
    PATH = "src.macro_calendar.finnhub_ingestion.fetch_finnhub_economic_events"

    def test_default_window_is_minus7_plus14(self, monkeypatch):
        from src.service.jobs import _run_fetch_economic_calendar_recent

        captured = _capture_call(monkeypatch, self.PATH)
        result = _run_fetch_economic_calendar_recent(dal="dal-x", params={})
        today = date.today()
        assert captured["date_from"] == today - __import__("datetime").timedelta(days=7)
        assert captured["date_to"] == today + __import__("datetime").timedelta(days=14)
        assert result["events_inserted"] == 1

    def test_explicit_dates_override_defaults(self, monkeypatch):
        from src.service.jobs import _run_fetch_economic_calendar_recent

        captured = _capture_call(monkeypatch, self.PATH)
        _run_fetch_economic_calendar_recent(
            dal="dal-x",
            params={"from_date": "2026-01-01", "to_date": "2026-01-15"},
        )
        assert captured["date_from"] == date(2026, 1, 1)
        assert captured["date_to"] == date(2026, 1, 15)

    def test_invalid_iso_date_raises(self):
        from src.service.jobs import _run_fetch_economic_calendar_recent

        with pytest.raises(ValueError, match="from_date"):
            _run_fetch_economic_calendar_recent(
                dal="dal-x", params={"from_date": "not-a-date"}
            )

    def test_to_before_from_raises(self):
        from src.service.jobs import _run_fetch_economic_calendar_recent

        with pytest.raises(ValueError, match="must be >="):
            _run_fetch_economic_calendar_recent(
                dal="dal-x",
                params={"from_date": "2026-01-15", "to_date": "2026-01-01"},
            )


class TestEconomicBackfillDispatcher:
    PATH = "src.macro_calendar.finnhub_ingestion.fetch_finnhub_economic_events"

    def test_default_years_back_is_one(self, monkeypatch):
        from src.service.jobs import _run_fetch_economic_calendar_backfill

        captured = _capture_call(monkeypatch, self.PATH)
        _run_fetch_economic_calendar_backfill(dal="dal-x", params={})
        today = date.today()
        # ~365 day spread (allow ±1 day for date arithmetic).
        spread = (captured["date_to"] - captured["date_from"]).days
        assert 364 <= spread <= 366
        assert captured["date_to"] == today

    def test_years_back_param_widens_window(self, monkeypatch):
        from src.service.jobs import _run_fetch_economic_calendar_backfill

        captured = _capture_call(monkeypatch, self.PATH)
        _run_fetch_economic_calendar_backfill(
            dal="dal-x", params={"years_back": 2}
        )
        spread = (captured["date_to"] - captured["date_from"]).days
        assert 729 <= spread <= 731

    def test_explicit_from_date_overrides_years_back(self, monkeypatch):
        from src.service.jobs import _run_fetch_economic_calendar_backfill

        captured = _capture_call(monkeypatch, self.PATH)
        _run_fetch_economic_calendar_backfill(
            dal="dal-x",
            params={"from_date": "2020-01-01", "years_back": 5},
        )
        assert captured["date_from"] == date(2020, 1, 1)

    def test_zero_years_back_raises(self):
        from src.service.jobs import _run_fetch_economic_calendar_backfill

        with pytest.raises(ValueError, match="years_back"):
            _run_fetch_economic_calendar_backfill(
                dal="dal-x", params={"years_back": 0}
            )


class TestEarningsDispatcher:
    PATH = "src.macro_calendar.finnhub_ingestion.fetch_finnhub_earnings_events"

    def _watchlist_dal(self, tickers):
        dal = MagicMock()
        dal.get_watchlist.return_value = SimpleNamespace(tickers=tickers)
        return dal

    def test_uses_watchlist_when_no_symbols_param(self, monkeypatch):
        from src.service.jobs import _run_fetch_earnings_calendar

        captured = _capture_call(monkeypatch, self.PATH)
        dal = self._watchlist_dal(["AAPL", "NVDA"])
        _run_fetch_earnings_calendar(dal=dal, params={})
        assert captured["symbols"] == ["AAPL", "NVDA"]

    def test_explicit_symbols_override_watchlist(self, monkeypatch):
        from src.service.jobs import _run_fetch_earnings_calendar

        captured = _capture_call(monkeypatch, self.PATH)
        dal = self._watchlist_dal(["AAPL", "NVDA"])
        _run_fetch_earnings_calendar(
            dal=dal, params={"symbols": ["TSLA", "MSFT"]},
        )
        # Explicit symbols win — watchlist not consulted.
        assert captured["symbols"] == ["TSLA", "MSFT"]
        dal.get_watchlist.assert_not_called()

    def test_empty_watchlist_falls_back_to_unfiltered(self, monkeypatch):
        from src.service.jobs import _run_fetch_earnings_calendar

        captured = _capture_call(monkeypatch, self.PATH)
        dal = self._watchlist_dal([])
        _run_fetch_earnings_calendar(dal=dal, params={})
        # symbols=None signals the ingestion to issue one unfiltered call.
        assert captured["symbols"] is None

    def test_default_window_today_to_plus30(self, monkeypatch):
        from src.service.jobs import _run_fetch_earnings_calendar

        captured = _capture_call(monkeypatch, self.PATH)
        dal = self._watchlist_dal(["AAPL"])
        _run_fetch_earnings_calendar(dal=dal, params={})
        today = date.today()
        assert captured["date_from"] == today
        assert captured["date_to"] == today + __import__("datetime").timedelta(days=30)


class TestIpoDispatcher:
    PATH = "src.macro_calendar.finnhub_ingestion.fetch_finnhub_ipo_events"

    def test_default_window_minus30_plus90(self, monkeypatch):
        from src.service.jobs import _run_fetch_ipo_calendar

        captured = _capture_call(monkeypatch, self.PATH)
        _run_fetch_ipo_calendar(dal="dal-x", params={})
        today = date.today()
        assert captured["date_from"] == today - __import__("datetime").timedelta(days=30)
        assert captured["date_to"] == today + __import__("datetime").timedelta(days=90)

    def test_explicit_dates_threaded(self, monkeypatch):
        from src.service.jobs import _run_fetch_ipo_calendar

        captured = _capture_call(monkeypatch, self.PATH)
        _run_fetch_ipo_calendar(
            dal="dal-x",
            params={"from_date": "2026-01-01", "to_date": "2026-04-30"},
        )
        assert captured["date_from"] == date(2026, 1, 1)
        assert captured["date_to"] == date(2026, 4, 30)


class TestFinnhubJobSummaries:
    def test_summary_for_economic_recent(self):
        from src.service.jobs import _summarize_result

        msg = _summarize_result("fetch_economic_calendar_recent", {
            "events_inserted": 12,
            "events_mutated": 3,
            "events_unchanged": 50,
            "events_skipped": 0,
            "errors": [],
        })
        assert "12 new" in msg
        assert "3 updated" in msg
        assert "50 unchanged" in msg

    def test_summary_for_earnings_with_errors(self):
        from src.service.jobs import _summarize_result

        msg = _summarize_result("fetch_earnings_calendar", {
            "events_inserted": 5,
            "events_mutated": 0,
            "events_unchanged": 1,
            "events_skipped": 2,
            "errors": ["AAPL: 429", "NVDA: 429"],
        })
        assert "5 new" in msg
        assert "2 skipped" in msg
        assert "2 error(s)" in msg

    def test_summary_for_ipo_unchanged_only(self):
        from src.service.jobs import _summarize_result

        msg = _summarize_result("fetch_ipo_calendar", {
            "events_inserted": 0,
            "events_mutated": 0,
            "events_unchanged": 200,
            "events_skipped": 0,
            "errors": [],
        })
        assert "0 new" in msg
        assert "200 unchanged" in msg
        # No skipped / errors fragments when zero.
        assert "skipped" not in msg
        assert "error" not in msg

    def test_summary_for_backfill_uses_event_keys(self):
        from src.service.jobs import _summarize_result

        msg = _summarize_result("fetch_economic_calendar_backfill", {
            "events_inserted": 642,
            "events_mutated": 0,
            "events_unchanged": 0,
            "events_skipped": 0,
            "errors": [],
        })
        assert "642 new" in msg

    def test_unknown_result_shape_falls_back_to_generic(self):
        from src.service.jobs import _summarize_result

        # No events_inserted key → generic fallback.
        msg = _summarize_result(
            "fetch_economic_calendar_recent", {"errors": ["boom"]}
        )
        assert "completed successfully" in msg.lower()