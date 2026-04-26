"""Tests for P1.2 macro/calendar store (commit 1: schema + DAL only).

Coverage rationale: this commit ships the foundation that every later
P1.2 commit (ingestion, health, API) will sit on. The two invariants
the spec hangs everything on are:

  - **Baseline-on-first-insert**: the very first time we see a
    fingerprint, the canonical row AND a baseline revision row are
    written in one transaction. Without the baseline an as-of read
    targeted before any later mutation has nothing to find.
  - **Observed-state-not-prior-state**: revision rows store the state
    we OBSERVED at observed_at — not the previous canonical state.
    The read query walks observed_at backwards from as_of; storing
    prior state would invert the time semantic.

Tests use a mock connection so the SQL shape is fully observable
without a live DB. The live PG probe in the commit message exercises
the same paths against real PostgreSQL.
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.macro_calendar.store import (
    EARNINGS_TRACKED_FIELDS,
    ECONOMIC_TRACKED_FIELDS,
    IPO_TRACKED_FIELDS,
    MacroCalendarStore,
    _normalize_for_diff,
    _tracked_payload_differs,
    earnings_event_fingerprint,
    economic_event_fingerprint,
    ipo_event_fingerprint,
)


def _make_db_dal():
    dal = MagicMock()
    backend = MagicMock()
    backend._get_conn = MagicMock()
    dal._backend = backend
    return dal, backend


def _make_file_dal():
    dal = MagicMock()
    dal._backend = object()
    return dal


def _make_conn(executions, fetchone_returns):
    """Mock conn that records every cur.execute call and returns supplied
    fetchone values in order."""
    conn = MagicMock()
    conn.autocommit = True

    def cursor_factory(**_kwargs):
        cur = MagicMock()
        cur.__enter__ = MagicMock(return_value=cur)
        cur.__exit__ = MagicMock(return_value=False)
        cur._fetchone_iter = iter(fetchone_returns)

        def _exec(sql, params=()):
            executions.append({"sql": sql, "params": params})

        def _fetchone():
            try:
                return next(cur._fetchone_iter)
            except StopIteration:
                return None

        cur.execute.side_effect = _exec
        cur.fetchone.side_effect = _fetchone
        return cur

    conn.cursor.side_effect = cursor_factory
    return conn


class TestFingerprints:
    def test_economic_fingerprint_deterministic_and_normalised(self):
        t = datetime(2024, 12, 18, 19, 0, tzinfo=timezone.utc)
        a = economic_event_fingerprint("us", " Fed Interest Rate Decision ", t)
        b = economic_event_fingerprint("US", "Fed Interest Rate Decision", t)
        assert a == b

    def test_economic_fingerprint_rejects_naive_datetime(self):
        t = datetime(2024, 12, 18, 19, 0)
        with pytest.raises(ValueError):
            economic_event_fingerprint("US", "x", t)

    def test_economic_fingerprint_distinct_per_time(self):
        t1 = datetime(2024, 12, 18, 19, 0, tzinfo=timezone.utc)
        t2 = datetime(2024, 12, 18, 19, 1, tzinfo=timezone.utc)
        assert economic_event_fingerprint("US", "X", t1) != \
               economic_event_fingerprint("US", "X", t2)

    def test_economic_fingerprint_same_instant_different_offsets(self):
        """A given UTC instant must produce the same fingerprint regardless of
        which timezone the caller represents it in."""
        utc = datetime(2024, 12, 18, 19, 0, tzinfo=timezone.utc)
        # Same instant, expressed in JST (+09:00).
        jst = utc.astimezone(timezone(timedelta(hours=9)))
        assert utc != jst.replace(tzinfo=utc.tzinfo)  # sanity: different tz objects
        assert economic_event_fingerprint("US", "X", utc) == \
               economic_event_fingerprint("US", "X", jst)

    def test_earnings_fingerprint_normalises_symbol(self):
        a = earnings_event_fingerprint("nvda", 2026, 1)
        b = earnings_event_fingerprint("NVDA", 2026, 1)
        assert a == b

    def test_earnings_fingerprint_distinct_per_quarter(self):
        a = earnings_event_fingerprint("NVDA", 2026, 1)
        b = earnings_event_fingerprint("NVDA", 2026, 2)
        assert a != b

    def test_ipo_fingerprint_is_name_plus_date(self):
        a = ipo_event_fingerprint("Acme Inc", date(2026, 5, 1))
        b = ipo_event_fingerprint("Acme Inc", date(2026, 5, 1))
        c = ipo_event_fingerprint("Acme Inc", date(2026, 5, 2))
        assert a == b
        assert a != c


class TestAvailability:
    def test_unavailable_with_no_backend(self):
        dal = MagicMock()
        dal._backend = None
        store = MacroCalendarStore(dal)
        assert store.is_available() is False
        eid, action = store.upsert_economic_event(
            payload={
                "country": "US", "event_name": "X",
                "event_time": datetime(2024, 1, 1, tzinfo=timezone.utc),
                "actual": None, "estimate": None, "prev": None,
            },
            source_payload={},
        )
        assert (eid, action) == (None, "unavailable")

    def test_unavailable_with_filebackend(self):
        dal = _make_file_dal()
        store = MacroCalendarStore(dal)
        assert store.is_available() is False


class TestBaselineOnFirstInsert:
    def _payload(self):
        return {
            "country": "US",
            "event_name": "Fed Interest Rate Decision",
            "event_time": datetime(2024, 12, 18, 19, 0, tzinfo=timezone.utc),
            "impact": "high",
            "unit": "%",
            "actual": None,
            "estimate": 4.5,
            "prev": 4.75,
        }

    def test_economic_first_insert_writes_canonical_and_baseline_revision(self):
        dal, backend = _make_db_dal()
        store = MacroCalendarStore(dal)
        executions = []
        conn = _make_conn(executions, [None, {"event_id": 42}])
        backend._get_conn.return_value = conn

        eid, action = store.upsert_economic_event(
            payload=self._payload(),
            source_payload={"raw": "row"},
        )
        assert eid == 42
        assert action == "inserted"
        assert len(executions) == 3
        assert "SELECT" in executions[0]["sql"]
        assert "INSERT INTO cal_economic_events" in executions[1]["sql"]
        assert "INSERT INTO cal_economic_event_revisions" in executions[2]["sql"]
        assert conn.autocommit is True
        conn.commit.assert_called_once()
        conn.rollback.assert_not_called()

    def test_earnings_first_insert_writes_baseline(self):
        dal, backend = _make_db_dal()
        store = MacroCalendarStore(dal)
        executions = []
        conn = _make_conn(executions, [None, {"earnings_id": 7}])
        backend._get_conn.return_value = conn

        eid, action = store.upsert_earnings_event(
            payload={
                "symbol": "NVDA", "report_date": date(2026, 5, 22),
                "year": 2026, "quarter": 1, "hour": "amc",
                "eps_estimate": 0.6, "eps_actual": None,
                "revenue_estimate": 4e10, "revenue_actual": None,
            },
            source_payload={"raw": "..."},
        )
        assert (eid, action) == (7, "inserted")
        assert "INSERT INTO cal_earnings_events" in executions[1]["sql"]
        assert "INSERT INTO cal_earnings_event_revisions" in executions[2]["sql"]

    def test_ipo_first_insert_writes_baseline(self):
        dal, backend = _make_db_dal()
        store = MacroCalendarStore(dal)
        executions = []
        conn = _make_conn(executions, [None, {"ipo_id": 99}])
        backend._get_conn.return_value = conn

        eid, action = store.upsert_ipo_event(
            payload={
                "symbol": None, "name": "Acme Inc",
                "ipo_date": date(2026, 5, 1), "exchange": None,
                "status": "filed", "number_of_shares": None,
                "price": None, "total_shares_value": None,
            },
            source_payload={},
        )
        assert (eid, action) == (99, "inserted")
        assert "INSERT INTO cal_ipo_events" in executions[1]["sql"]
        assert "INSERT INTO cal_ipo_event_revisions" in executions[2]["sql"]


class TestMutationAppendsObservedState:
    def _payload(self, **overrides):
        base = {
            "country": "US",
            "event_name": "Fed Interest Rate Decision",
            "event_time": datetime(2024, 12, 18, 19, 0, tzinfo=timezone.utc),
            "impact": "high",
            "unit": "%",
            "actual": 4.5,
            "estimate": 4.5,
            "prev": 4.75,
        }
        base.update(overrides)
        return base

    def test_subsequent_mutation_appends_revision_with_NEW_state(self):
        dal, backend = _make_db_dal()
        store = MacroCalendarStore(dal)
        executions = []
        existing_row = {
            "event_id": 42, "actual": None, "estimate": 4.5, "prev": 4.75,
        }
        conn = _make_conn(executions, [existing_row])
        backend._get_conn.return_value = conn

        eid, action = store.upsert_economic_event(
            payload=self._payload(),
            source_payload={"raw": "post-release"},
        )
        assert (eid, action) == (42, "mutated")
        assert len(executions) == 3
        assert "SELECT" in executions[0]["sql"]
        assert "UPDATE cal_economic_events" in executions[1]["sql"]
        assert "INSERT INTO cal_economic_event_revisions" in executions[2]["sql"]

        rev_params = executions[2]["params"]
        assert rev_params[0] == 42
        assert rev_params[2] == 4.5
        assert rev_params[3] == 4.5
        assert rev_params[4] == 4.75

    def test_unchanged_payload_skips_writes(self):
        dal, backend = _make_db_dal()
        store = MacroCalendarStore(dal)
        executions = []
        existing_row = {
            "event_id": 42, "actual": 4.5, "estimate": 4.5, "prev": 4.75,
        }
        conn = _make_conn(executions, [existing_row])
        backend._get_conn.return_value = conn

        eid, action = store.upsert_economic_event(
            payload=self._payload(),
            source_payload={"raw": "duplicate fetch"},
        )
        assert (eid, action) == (42, "unchanged")
        assert len(executions) == 1
        assert "SELECT" in executions[0]["sql"]
        conn.commit.assert_called_once()

    def test_canonical_revision_atomicity_rollback_on_revision_failure(self):
        dal, backend = _make_db_dal()
        store = MacroCalendarStore(dal)
        existing_row = {
            "event_id": 42, "actual": None, "estimate": 4.5, "prev": 4.75,
        }
        conn = MagicMock()
        conn.autocommit = True
        call_count = {"n": 0}

        def cursor_factory(**_kwargs):
            cur = MagicMock()
            cur.__enter__ = MagicMock(return_value=cur)
            cur.__exit__ = MagicMock(return_value=False)
            cur.fetchone.return_value = existing_row

            def _exec(sql, params=()):
                call_count["n"] += 1
                if call_count["n"] == 3:
                    raise RuntimeError("revision insert exploded")

            cur.execute.side_effect = _exec
            return cur

        conn.cursor.side_effect = cursor_factory
        backend._get_conn.return_value = conn

        with pytest.raises(RuntimeError, match="revision insert exploded"):
            store.upsert_economic_event(
                payload=self._payload(),
                source_payload={},
            )
        conn.rollback.assert_called_once()
        conn.commit.assert_not_called()
        assert conn.autocommit is True


class TestReadAsOf:
    def test_economic_read_as_of_walks_revision_log_backwards(self):
        dal, backend = _make_db_dal()
        store = MacroCalendarStore(dal)
        executions = []
        conn = _make_conn(executions, [{
            "observed_at": datetime(2024, 12, 18, 18, 30, tzinfo=timezone.utc),
            "actual": None, "estimate": 4.5, "prev": 4.75,
            "source_payload": {"raw": "pre-release"},
        }])
        backend._get_conn.return_value = conn

        as_of = datetime(2024, 12, 18, 18, 59, tzinfo=timezone.utc)
        result = store.read_economic_event_as_of(event_id=42, as_of=as_of)
        assert result is not None
        assert result["actual"] is None
        assert "observed_at <= %s" in executions[0]["sql"]
        assert "ORDER BY observed_at DESC" in executions[0]["sql"]
        assert executions[0]["params"] == (42, as_of)

    def test_read_as_of_returns_none_when_no_revision_predates(self):
        dal, backend = _make_db_dal()
        store = MacroCalendarStore(dal)
        conn = _make_conn([], [None])
        backend._get_conn.return_value = conn

        result = store.read_economic_event_as_of(
            event_id=42,
            as_of=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        assert result is None


class TestMacro:
    def test_realtime_start_required_no_sentinel(self):
        dal, backend = _make_db_dal()
        store = MacroCalendarStore(dal)
        with pytest.raises(ValueError, match="realtime_start is mandatory"):
            store.upsert_macro_observation(
                series_id="CPIAUCNS",
                observation_date=date(2024, 3, 1),
                value=312.332,
                realtime_start=None,
            )

    def test_macro_value_as_of_filters_vintage_window(self):
        dal, backend = _make_db_dal()
        store = MacroCalendarStore(dal)
        executions = []
        conn = _make_conn(executions, [(312.332,)])
        backend._get_conn.return_value = conn

        v = store.get_macro_value_as_of(
            series_id="CPIAUCNS",
            observation_date=date(2024, 3, 1),
            as_of=date(2024, 5, 15),
        )
        assert v == 312.332
        sql = executions[0]["sql"]
        assert "realtime_start <= %s" in sql
        assert "realtime_end > %s" in sql
        assert "ORDER BY realtime_start DESC" in sql
        assert executions[0]["params"] == (
            "CPIAUCNS", date(2024, 3, 1), date(2024, 5, 15), date(2024, 5, 15),
        )

    def test_upsert_macro_observation_passes_realtime_window(self):
        dal, backend = _make_db_dal()
        store = MacroCalendarStore(dal)
        executions = []
        conn = _make_conn(executions, [])
        backend._get_conn.return_value = conn

        ok = store.upsert_macro_observation(
            series_id="CPIAUCNS",
            observation_date=date(2024, 3, 1),
            value=312.332,
            realtime_start=date(2024, 4, 10),
            realtime_end=None,
        )
        assert ok is True
        params = executions[0]["params"]
        assert params[0] == "CPIAUCNS"
        assert params[1] == date(2024, 3, 1)
        assert params[2] == 312.332
        assert params[3] == date(2024, 4, 10)
        assert params[4] is None


class TestNumericDiffNormalisation:
    """Decimal vs float vs int vs numeric-string must all compare equal when
    they represent the same number. Without this, every re-fetch of an
    unchanged numeric row would mark a mutation and flood the revision log.
    """

    def test_decimal_vs_float_equal(self):
        assert _normalize_for_diff(Decimal("4.1")) == _normalize_for_diff(4.1)

    def test_decimal_vs_int_equal(self):
        assert _normalize_for_diff(Decimal("5")) == _normalize_for_diff(5)

    def test_decimal_vs_numeric_string_equal(self):
        assert _normalize_for_diff(Decimal("4.50")) == _normalize_for_diff("4.50")

    def test_none_passes_through(self):
        assert _normalize_for_diff(None) is None

    def test_non_numeric_string_passes_through(self):
        assert _normalize_for_diff("amc") == "amc"
        assert _normalize_for_diff("") == ""

    def test_bool_not_normalised_to_decimal(self):
        # bool is a numeric subtype in Python but we never want True coerced
        # into Decimal('1') for our diff (semantic difference).
        assert _normalize_for_diff(True) is True
        assert _normalize_for_diff(False) is False

    def test_tracked_payload_differs_decimal_vs_float_no_mutation(self):
        """The headline invariant: Decimal('4.1') from DB vs 4.1 from
        Finnhub re-fetch must NOT register as a mutation."""
        existing = {"actual": Decimal("4.1"), "estimate": Decimal("4.5"), "prev": Decimal("4.75")}
        new = {"actual": 4.1, "estimate": 4.5, "prev": 4.75}
        assert _tracked_payload_differs(existing, new, ECONOMIC_TRACKED_FIELDS) is False

    def test_tracked_payload_differs_real_change_still_detected(self):
        existing = {"actual": Decimal("4.1"), "estimate": Decimal("4.5"), "prev": Decimal("4.75")}
        new = {"actual": 4.2, "estimate": 4.5, "prev": 4.75}  # actual changed
        assert _tracked_payload_differs(existing, new, ECONOMIC_TRACKED_FIELDS) is True

    def test_mutation_detection_treats_none_to_value_as_change(self):
        """null → populated is the most common revision (release prints actual)."""
        existing = {"actual": None, "estimate": Decimal("4.5"), "prev": Decimal("4.75")}
        new = {"actual": 4.5, "estimate": 4.5, "prev": 4.75}
        assert _tracked_payload_differs(existing, new, ECONOMIC_TRACKED_FIELDS) is True


class TestUpsertEconomicNoOpOnDecimalFloatEqual:
    """End-to-end check: store.upsert_economic_event must return action='unchanged'
    (no canonical UPDATE, no revision INSERT) when the only 'change' is
    Decimal-vs-float type difference."""

    def test_decimal_existing_vs_float_payload_is_unchanged(self):
        dal = MagicMock()
        backend = MagicMock()
        backend._get_conn = MagicMock()
        dal._backend = backend

        store = MacroCalendarStore(dal)
        executions = []
        existing_row = {
            "event_id": 42,
            "actual": Decimal("4.5"),
            "estimate": Decimal("4.5"),
            "prev": Decimal("4.75"),
        }
        conn = _make_conn(executions, [existing_row])
        backend._get_conn.return_value = conn

        eid, action = store.upsert_economic_event(
            payload={
                "country": "US",
                "event_name": "Fed Interest Rate Decision",
                "event_time": datetime(2024, 12, 18, 19, 0, tzinfo=timezone.utc),
                "impact": "high",
                "unit": "%",
                "actual": 4.5,    # float — same number as Decimal('4.5')
                "estimate": 4.5,
                "prev": 4.75,
            },
            source_payload={"raw": "noisy refetch"},
        )
        assert (eid, action) == (42, "unchanged")
        assert len(executions) == 1  # only the SELECT
        conn.commit.assert_called_once()


class TestTrackedFields:
    def test_economic_tracked_fields(self):
        assert set(ECONOMIC_TRACKED_FIELDS) == {"actual", "estimate", "prev"}

    def test_earnings_tracked_fields_include_hour(self):
        assert "hour" in EARNINGS_TRACKED_FIELDS
        assert "eps_estimate" in EARNINGS_TRACKED_FIELDS
        assert "eps_actual" in EARNINGS_TRACKED_FIELDS

    def test_ipo_tracked_fields_include_status(self):
        assert "status" in IPO_TRACKED_FIELDS
        assert "exchange" in IPO_TRACKED_FIELDS
        assert "price" in IPO_TRACKED_FIELDS