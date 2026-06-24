"""SQLite-backed twin of MacroCalendarStore — macro/cal local store (PG-exit §4c slice 1).

Same public method surface as ``MacroCalendarStore`` (upsert_economic/earnings/ipo_event +
read_*_as_of, upsert_macro_series/get_macro_series, upsert_macro_observation/
get_macro_value_as_of, upsert_release_date/get_release_dates, list_*), backed by its own
``macro_calendar.db`` (topology decision) with ZERO PostgreSQL. The canonical+revision
upsert semantics, fingerprints, and tracked-field change detection are REUSED from
``store.py`` (imported, not re-derived) so parity is structural, not hand-copied.

PG-ism port (vs sql/013): BIGSERIAL → INTEGER PRIMARY KEY AUTOINCREMENT; TIMESTAMPTZ/DATE →
TEXT (UTC ISO); JSONB → TEXT (json.dumps); ``%s`` → ``?``; RealDictCursor → sqlite3.Row;
``NOW()`` → CURRENT_TIMESTAMP; partial-index ``WHERE`` recreated as real partial indexes;
FK ``ON DELETE CASCADE`` kept (PRAGMA foreign_keys=ON per connection). The ``9999-12-31``
open-vintage sentinel for macro_observations.realtime_end is preserved verbatim.

This is slice 1: store + schema + hermetic parity tests only. No runtime wiring, no toggle,
no FRED/Finnhub ingestion, no PG migration — those are later slices.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.macro_calendar.store import (
    ECONOMIC_TRACKED_FIELDS,
    EARNINGS_TRACKED_FIELDS,
    IPO_TRACKED_FIELDS,
    _clamp_limit,
    _normalize_str_array,
    _tracked_payload_differs,
    economic_event_fingerprint,
    earnings_event_fingerprint,
    ipo_event_fingerprint,
)

logger = logging.getLogger(__name__)

_OPEN_VINTAGE = "9999-12-31"  # macro_observations.realtime_end sentinel (open window)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cal_economic_events (
    event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    country     TEXT NOT NULL,
    event_name  TEXT NOT NULL,
    event_time  TEXT NOT NULL,
    impact      TEXT NOT NULL DEFAULT '' CHECK (impact IN ('low','medium','high','')),
    unit        TEXT,
    actual      REAL,
    estimate    REAL,
    prev        REAL,
    fingerprint TEXT NOT NULL UNIQUE,
    fetched_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_cal_econ_event_time ON cal_economic_events(event_time DESC);
CREATE INDEX IF NOT EXISTS idx_cal_econ_high_impact ON cal_economic_events(impact, event_time DESC) WHERE impact = 'high';
CREATE TABLE IF NOT EXISTS cal_economic_event_revisions (
    revision_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id       INTEGER NOT NULL REFERENCES cal_economic_events(event_id) ON DELETE CASCADE,
    observed_at    TEXT NOT NULL,
    actual         REAL,
    estimate       REAL,
    prev           REAL,
    source_payload TEXT NOT NULL,
    UNIQUE (event_id, observed_at)
);
CREATE INDEX IF NOT EXISTS idx_cal_econ_rev ON cal_economic_event_revisions(event_id, observed_at DESC);

CREATE TABLE IF NOT EXISTS cal_earnings_events (
    earnings_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol           TEXT NOT NULL,
    report_date      TEXT NOT NULL,
    year             INTEGER NOT NULL,
    quarter          INTEGER NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    hour             TEXT NOT NULL DEFAULT '' CHECK (hour IN ('bmo','amc','dmh','')),
    eps_estimate     REAL,
    eps_actual       REAL,
    revenue_estimate REAL,
    revenue_actual   REAL,
    fingerprint      TEXT NOT NULL UNIQUE,
    fetched_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_cal_earn_symbol ON cal_earnings_events(symbol, report_date DESC);
CREATE INDEX IF NOT EXISTS idx_cal_earn_date ON cal_earnings_events(report_date DESC);
CREATE TABLE IF NOT EXISTS cal_earnings_event_revisions (
    revision_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    earnings_id      INTEGER NOT NULL REFERENCES cal_earnings_events(earnings_id) ON DELETE CASCADE,
    observed_at      TEXT NOT NULL,
    hour             TEXT NOT NULL DEFAULT '',
    eps_estimate     REAL,
    eps_actual       REAL,
    revenue_estimate REAL,
    revenue_actual   REAL,
    source_payload   TEXT NOT NULL,
    UNIQUE (earnings_id, observed_at)
);
CREATE INDEX IF NOT EXISTS idx_cal_earn_rev ON cal_earnings_event_revisions(earnings_id, observed_at DESC);

CREATE TABLE IF NOT EXISTS cal_ipo_events (
    ipo_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol             TEXT,
    name               TEXT NOT NULL,
    ipo_date           TEXT NOT NULL,
    exchange           TEXT,
    status             TEXT NOT NULL CHECK (status IN ('priced','filed','expected','withdrawn')),
    number_of_shares   REAL,
    price              TEXT,   -- PG is NUMERIC; TEXT here tolerates Finnhub range strings ("18-20")
    total_shares_value REAL,
    fingerprint        TEXT NOT NULL UNIQUE,
    fetched_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE INDEX IF NOT EXISTS idx_cal_ipo_date ON cal_ipo_events(ipo_date DESC);
CREATE INDEX IF NOT EXISTS idx_cal_ipo_status ON cal_ipo_events(status, ipo_date DESC);
CREATE TABLE IF NOT EXISTS cal_ipo_event_revisions (
    revision_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ipo_id             INTEGER NOT NULL REFERENCES cal_ipo_events(ipo_id) ON DELETE CASCADE,
    observed_at        TEXT NOT NULL,
    status             TEXT NOT NULL,
    price              TEXT,
    exchange           TEXT,
    number_of_shares   REAL,
    total_shares_value REAL,
    source_payload     TEXT NOT NULL,
    UNIQUE (ipo_id, observed_at)
);
CREATE INDEX IF NOT EXISTS idx_cal_ipo_rev ON cal_ipo_event_revisions(ipo_id, observed_at DESC);

CREATE TABLE IF NOT EXISTS macro_series (
    series_id           TEXT PRIMARY KEY,
    title               TEXT NOT NULL,
    frequency           TEXT NOT NULL,
    units               TEXT NOT NULL,
    seasonal_adjustment TEXT,
    last_updated        TEXT,
    revision_strategy   TEXT NOT NULL DEFAULT 'latest_only'
                        CHECK (revision_strategy IN ('latest_only','full_vintages')),
    fetched_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
CREATE TABLE IF NOT EXISTS macro_observations (
    observation_id   INTEGER PRIMARY KEY AUTOINCREMENT,   -- surrogate (PG BIGSERIAL parity)
    series_id        TEXT NOT NULL REFERENCES macro_series(series_id) ON DELETE CASCADE,
    observation_date TEXT NOT NULL,
    value            REAL,
    realtime_start   TEXT NOT NULL,
    realtime_end     TEXT NOT NULL DEFAULT '9999-12-31',
    fetched_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    UNIQUE (series_id, observation_date, realtime_start)
);
CREATE INDEX IF NOT EXISTS idx_macro_obs ON macro_observations(series_id, observation_date DESC);
CREATE INDEX IF NOT EXISTS idx_macro_obs_realtime ON macro_observations(series_id, realtime_start DESC);
CREATE TABLE IF NOT EXISTS macro_release_dates (
    release_id   INTEGER NOT NULL,
    release_name TEXT NOT NULL,
    release_date TEXT NOT NULL,
    fetched_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    PRIMARY KEY (release_id, release_date)
);
"""


def _iso(v: Any) -> Any:
    """Render a datetime/date as a comparable UTC-ISO TEXT; pass through others.
    SQLite has no native datetime, so all temporal columns are lexicographically
    comparable ISO strings (the same discipline as market_data.db's UTC PK).
    Datetimes carry MICROSECOND precision so a default observed_at (NOW) for two
    back-to-back upserts differs — matching PG's per-statement NOW() and respecting
    UNIQUE(id, observed_at) on the revision log (PG uses COALESCE(%s, NOW())); a
    second-resolution stamp would collide on a fast insert→mutate."""
    if isinstance(v, datetime):
        if v.tzinfo is not None:
            v = v.astimezone(timezone.utc)
        return v.strftime("%Y-%m-%dT%H:%M:%S.%f+0000")
    if isinstance(v, date):
        return v.isoformat()
    return v


def _now_observed() -> str:
    """Default observed_at when the caller passes None — the local twin of PG's
    COALESCE(observed_at, NOW()). Microsecond-precise so back-to-back revisions on one
    event don't violate UNIQUE(id, observed_at)."""
    return _iso(datetime.now(timezone.utc))


def _in_clause(col: str, values: Optional[List[str]]) -> Tuple[str, list]:
    """Build an ``' AND col IN (?,?,…)'`` fragment + params, or ``('', [])`` when there's
    no filter — the SQLite twin of PG's ``%(arr)s::text[] IS NULL OR col = ANY(...)``."""
    if not values:
        return "", []
    placeholders = ",".join("?" * len(values))
    return f" AND {col} IN ({placeholders})", list(values)


def resolve_macro_calendar_db_path(db_path: str | Path | None = None) -> str:
    if db_path is not None:
        return str(db_path)
    return os.environ.get("ARKSCOPE_MACRO_CALENDAR_DB") or str(
        Path(__file__).resolve().parents[2] / "data" / "macro_calendar.db")


class MacroCalendarLocalStore:
    """SQLite twin of MacroCalendarStore over ``macro_calendar.db`` (no PG)."""

    def __init__(self, db_path: str | Path | None = None):
        self._db_path = resolve_macro_calendar_db_path(db_path)
        self._ensure_schema()

    def is_available(self) -> bool:
        return True  # local store is always available (unlike the PG-gated twin)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.execute("PRAGMA foreign_keys = ON")  # honor the revision-log FK CASCADE
        return conn

    def _ensure_schema(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    # --- shared canonical+revision upsert (mirrors store._upsert_calendar_event) ----

    def _upsert_calendar_event(
        self, *, canonical_table: str, id_column: str, fingerprint: str,
        tracked_fields: Iterable[str], insert_canonical_sql: str, insert_canonical_params: tuple,
        update_canonical_sql: str, update_canonical_params, insert_revision_sql: str,
        insert_revision_params, tracked_payload: Dict[str, Any],
    ) -> Tuple[Optional[int], str]:
        """First insert → canonical + baseline revision (one txn). Re-ingest with a tracked
        change → update canonical + append revision. Unchanged → no-op (no fetched_at bump).
        Atomic per the connection's implicit transaction; identical action semantics to the
        PG store, with the change detection reused from store._tracked_payload_differs."""
        conn = self._connect()
        try:
            tracked = ", ".join(tracked_fields)
            row = conn.execute(
                f"SELECT {id_column}, {tracked} FROM {canonical_table} WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchone()
            if row is None:
                cur = conn.execute(insert_canonical_sql, insert_canonical_params)
                new_id = int(cur.lastrowid)
                conn.execute(insert_revision_sql, insert_revision_params(new_id))
                conn.commit()
                return (new_id, "inserted")
            eid = int(row[id_column])
            if not _tracked_payload_differs(dict(row), tracked_payload, tracked_fields):
                return (eid, "unchanged")
            conn.execute(update_canonical_sql, update_canonical_params(eid))
            conn.execute(insert_revision_sql, insert_revision_params(eid))
            conn.commit()
            return (eid, "mutated")
        except Exception as exc:
            conn.rollback()
            logger.error("local upsert into %s failed: %s", canonical_table, exc)
            raise
        finally:
            conn.close()

    def _read_revision_as_of(self, *, sql: str, params: tuple) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None
        except sqlite3.OperationalError as exc:
            logger.warning("local revision as-of read failed: %s", exc)
            return None
        finally:
            conn.close()

    # --- economic events ------------------------------------------------------------

    def upsert_economic_event(self, payload: Dict[str, Any], *, source_payload: Dict[str, Any],
                              observed_at: Optional[datetime] = None) -> Tuple[Optional[int], str]:
        fp = economic_event_fingerprint(payload["country"], payload["event_name"], payload["event_time"])
        obs = _iso(observed_at) if observed_at else _now_observed()
        return self._upsert_calendar_event(
            canonical_table="cal_economic_events", id_column="event_id", fingerprint=fp,
            tracked_fields=ECONOMIC_TRACKED_FIELDS,
            insert_canonical_sql="INSERT INTO cal_economic_events (country,event_name,event_time,"
                "impact,unit,actual,estimate,prev,fingerprint) VALUES (?,?,?,?,?,?,?,?,?)",
            insert_canonical_params=(payload["country"], payload["event_name"], _iso(payload["event_time"]),
                payload.get("impact", ""), payload.get("unit"), payload.get("actual"),
                payload.get("estimate"), payload.get("prev"), fp),
            update_canonical_sql="UPDATE cal_economic_events SET impact=?,unit=?,actual=?,estimate=?,"
                "prev=?,updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE event_id=?",
            update_canonical_params=lambda eid: (payload.get("impact", ""), payload.get("unit"),
                payload.get("actual"), payload.get("estimate"), payload.get("prev"), eid),
            insert_revision_sql="INSERT INTO cal_economic_event_revisions (event_id,observed_at,"
                "actual,estimate,prev,source_payload) VALUES (?,?,?,?,?,?)",
            insert_revision_params=lambda eid: (eid, obs, payload.get("actual"),
                payload.get("estimate"), payload.get("prev"), json.dumps(source_payload)),
            tracked_payload=payload,
        )

    def read_economic_event_as_of(self, event_id: int, as_of: datetime) -> Optional[Dict[str, Any]]:
        return self._read_revision_as_of(
            sql="SELECT observed_at,actual,estimate,prev,source_payload FROM "
                "cal_economic_event_revisions WHERE event_id=? AND observed_at<=? "
                "ORDER BY observed_at DESC LIMIT 1",
            params=(event_id, _iso(as_of)))

    # --- earnings events ------------------------------------------------------------

    def upsert_earnings_event(self, payload: Dict[str, Any], *, source_payload: Dict[str, Any],
                              observed_at: Optional[datetime] = None) -> Tuple[Optional[int], str]:
        fp = earnings_event_fingerprint(payload["symbol"], payload["year"], payload["quarter"])
        obs = _iso(observed_at) if observed_at else _now_observed()
        return self._upsert_calendar_event(
            canonical_table="cal_earnings_events", id_column="earnings_id", fingerprint=fp,
            tracked_fields=EARNINGS_TRACKED_FIELDS,
            insert_canonical_sql="INSERT INTO cal_earnings_events (symbol,report_date,year,quarter,"
                "hour,eps_estimate,eps_actual,revenue_estimate,revenue_actual,fingerprint) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
            insert_canonical_params=(payload["symbol"], _iso(payload["report_date"]), payload["year"],
                payload["quarter"], payload.get("hour", ""), payload.get("eps_estimate"),
                payload.get("eps_actual"), payload.get("revenue_estimate"), payload.get("revenue_actual"), fp),
            update_canonical_sql="UPDATE cal_earnings_events SET hour=?,eps_estimate=?,eps_actual=?,"
                "revenue_estimate=?,revenue_actual=?,updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') "
                "WHERE earnings_id=?",
            update_canonical_params=lambda eid: (payload.get("hour", ""), payload.get("eps_estimate"),
                payload.get("eps_actual"), payload.get("revenue_estimate"), payload.get("revenue_actual"), eid),
            insert_revision_sql="INSERT INTO cal_earnings_event_revisions (earnings_id,observed_at,hour,"
                "eps_estimate,eps_actual,revenue_estimate,revenue_actual,source_payload) "
                "VALUES (?,?,?,?,?,?,?,?)",
            insert_revision_params=lambda eid: (eid, obs, payload.get("hour", ""),
                payload.get("eps_estimate"), payload.get("eps_actual"), payload.get("revenue_estimate"),
                payload.get("revenue_actual"), json.dumps(source_payload)),
            tracked_payload=payload,
        )

    def read_earnings_event_as_of(self, earnings_id: int, as_of: datetime) -> Optional[Dict[str, Any]]:
        return self._read_revision_as_of(
            sql="SELECT observed_at,hour,eps_estimate,eps_actual,revenue_estimate,revenue_actual,"
                "source_payload FROM cal_earnings_event_revisions WHERE earnings_id=? AND observed_at<=? "
                "ORDER BY observed_at DESC LIMIT 1",
            params=(earnings_id, _iso(as_of)))

    # --- IPO events -----------------------------------------------------------------

    def upsert_ipo_event(self, payload: Dict[str, Any], *, source_payload: Dict[str, Any],
                         observed_at: Optional[datetime] = None) -> Tuple[Optional[int], str]:
        fp = ipo_event_fingerprint(payload["name"], payload["ipo_date"])
        obs = _iso(observed_at) if observed_at else _now_observed()
        return self._upsert_calendar_event(
            canonical_table="cal_ipo_events", id_column="ipo_id", fingerprint=fp,
            tracked_fields=IPO_TRACKED_FIELDS,
            insert_canonical_sql="INSERT INTO cal_ipo_events (symbol,name,ipo_date,exchange,status,"
                "number_of_shares,price,total_shares_value,fingerprint) VALUES (?,?,?,?,?,?,?,?,?)",
            insert_canonical_params=(payload.get("symbol"), payload["name"], _iso(payload["ipo_date"]),
                payload.get("exchange"), payload["status"], payload.get("number_of_shares"),
                payload.get("price"), payload.get("total_shares_value"), fp),
            update_canonical_sql="UPDATE cal_ipo_events SET symbol=?,exchange=?,status=?,number_of_shares=?,"
                "price=?,total_shares_value=?,updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE ipo_id=?",
            update_canonical_params=lambda eid: (payload.get("symbol"), payload.get("exchange"),
                payload["status"], payload.get("number_of_shares"), payload.get("price"),
                payload.get("total_shares_value"), eid),
            insert_revision_sql="INSERT INTO cal_ipo_event_revisions (ipo_id,observed_at,status,price,"
                "exchange,number_of_shares,total_shares_value,source_payload) VALUES (?,?,?,?,?,?,?,?)",
            insert_revision_params=lambda eid: (eid, obs, payload["status"], payload.get("price"),
                payload.get("exchange"), payload.get("number_of_shares"),
                payload.get("total_shares_value"), json.dumps(source_payload)),
            tracked_payload=payload,
        )

    def read_ipo_event_as_of(self, ipo_id: int, as_of: datetime) -> Optional[Dict[str, Any]]:
        return self._read_revision_as_of(
            sql="SELECT observed_at,status,price,exchange,number_of_shares,total_shares_value,"
                "source_payload FROM cal_ipo_event_revisions WHERE ipo_id=? AND observed_at<=? "
                "ORDER BY observed_at DESC LIMIT 1",
            params=(ipo_id, _iso(as_of)))

    # --- macro series + observations + release dates --------------------------------

    def upsert_macro_series(self, payload: Dict[str, Any]) -> bool:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO macro_series (series_id,title,frequency,units,seasonal_adjustment,"
                "last_updated,revision_strategy) VALUES (?,?,?,?,?,?,?) "
                "ON CONFLICT(series_id) DO UPDATE SET title=excluded.title,frequency=excluded.frequency,"
                "units=excluded.units,seasonal_adjustment=excluded.seasonal_adjustment,"
                "last_updated=excluded.last_updated,revision_strategy=excluded.revision_strategy,"
                "updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')",
                (payload["series_id"], payload["title"], payload["frequency"], payload["units"],
                 payload.get("seasonal_adjustment"), _iso(payload.get("last_updated")),
                 payload.get("revision_strategy", "latest_only")))
            conn.commit()
            return True
        except Exception as exc:
            logger.warning("local upsert_macro_series failed for %s: %s", payload.get("series_id"), exc)
            return False
        finally:
            conn.close()

    def get_macro_series(self, series_id: str) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM macro_series WHERE series_id=?", (series_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def upsert_macro_observation(self, *, series_id: str, observation_date: date, value: Optional[Any],
                                 realtime_start: date, realtime_end: Optional[date] = None) -> bool:
        if realtime_start is None:
            raise ValueError("realtime_start is mandatory; sentinel writes are not allowed")
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO macro_observations (series_id,observation_date,value,realtime_start,realtime_end) "
                "VALUES (?,?,?,?,COALESCE(?, ?)) "
                "ON CONFLICT(series_id,observation_date,realtime_start) DO UPDATE SET "
                "value=excluded.value,realtime_end=excluded.realtime_end,"
                "fetched_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')",
                (series_id, _iso(observation_date), value, _iso(realtime_start),
                 _iso(realtime_end), _OPEN_VINTAGE))
            conn.commit()
            return True
        except Exception as exc:
            logger.warning("local upsert_macro_observation failed for %s/%s: %s",
                           series_id, observation_date, exc)
            return False
        finally:
            conn.close()

    def get_macro_value_as_of(self, series_id: str, observation_date: date, as_of: date) -> Optional[Any]:
        """Value of (series_id, observation_date) as known at ``as_of``: the vintage whose
        window contains as_of (realtime_start <= as_of < realtime_end)."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT value FROM macro_observations WHERE series_id=? AND observation_date=? "
                "AND realtime_start<=? AND realtime_end>?",
                (series_id, _iso(observation_date), _iso(as_of), _iso(as_of))).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def upsert_release_date(self, *, release_id: int, release_name: str, release_date_value: date) -> bool:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO macro_release_dates (release_id,release_name,release_date) VALUES (?,?,?) "
                "ON CONFLICT(release_id,release_date) DO UPDATE SET release_name=excluded.release_name,"
                "fetched_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')",
                (release_id, release_name, _iso(release_date_value)))
            conn.commit()
            return True
        except Exception as exc:
            logger.warning("local upsert_release_date failed: %s", exc)
            return False
        finally:
            conn.close()

    def get_release_dates(self, release_id: int, *, before: Optional[date] = None,
                          limit: int = 100) -> List[date]:
        params: List[Any] = [release_id]
        clause = ""
        if before is not None:
            clause = " AND release_date < ?"
            params.append(_iso(before))
        params.append(max(1, min(int(limit), 1000)))
        conn = self._connect()
        try:
            rows = conn.execute(
                f"SELECT release_date FROM macro_release_dates WHERE release_id=?{clause} "
                "ORDER BY release_date DESC LIMIT ?", tuple(params)).fetchall()
            return [date.fromisoformat(r[0]) for r in rows]
        finally:
            conn.close()

    # --- list reads (canonical + as-of), parity with store.list_* / get_macro_observations
    # NOTE on shape: temporal columns come back as ISO-TEXT (not datetime objects like the
    # PG RealDictCursor) and NUMERIC as float — consistent with SQLite storage; slice 2's
    # wiring maps these to the route DTOs. Keys match the PG result (incl. as_of_observed_at).

    def _list_query(self, conn, sql: str, params: list) -> List[Dict[str, Any]]:
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        except sqlite3.OperationalError as exc:
            logger.warning("local list query failed: %s", exc)
            return []

    def list_economic_events(self, *, date_from: datetime, date_to: datetime,
                             countries: Optional[Iterable[str]] = None,
                             impacts: Optional[Iterable[str]] = None,
                             as_of: Optional[datetime] = None, limit: int = 200) -> List[Dict[str, Any]]:
        c_arr = _normalize_str_array(countries, upper=True)
        i_arr = _normalize_str_array(impacts, lower=True)
        lim = _clamp_limit(limit, hi=1000)
        conn = self._connect()
        try:
            if as_of is None:
                sql = ("SELECT event_id,country,event_name,event_time,impact,unit,actual,estimate,"
                       "prev,NULL AS as_of_observed_at FROM cal_economic_events "
                       "WHERE event_time>=? AND event_time<=?")
                params = [_iso(date_from), _iso(date_to)]
                cc, pc = _in_clause("country", c_arr); ci, pi = _in_clause("impact", i_arr)
                sql += cc + ci + " ORDER BY event_time ASC LIMIT ?"; params += pc + pi + [lim]
            else:
                # INNER JOIN the latest revision <= as_of (MAX subquery → events with no
                # revision <= as_of yield NULL → excluded, matching PG's INNER JOIN LATERAL).
                sql = ("SELECT e.event_id,e.country,e.event_name,e.event_time,e.impact,e.unit,"
                       "rev.actual,rev.estimate,rev.prev,rev.observed_at AS as_of_observed_at "
                       "FROM cal_economic_events e JOIN cal_economic_event_revisions rev "
                       "ON rev.event_id=e.event_id AND rev.observed_at=("
                       "SELECT MAX(observed_at) FROM cal_economic_event_revisions "
                       "WHERE event_id=e.event_id AND observed_at<=?) "
                       "WHERE e.event_time>=? AND e.event_time<=?")
                params = [_iso(as_of), _iso(date_from), _iso(date_to)]
                cc, pc = _in_clause("e.country", c_arr); ci, pi = _in_clause("e.impact", i_arr)
                sql += cc + ci + " ORDER BY e.event_time ASC LIMIT ?"; params += pc + pi + [lim]
            return self._list_query(conn, sql, params)
        finally:
            conn.close()

    def list_earnings_events(self, *, date_from: date, date_to: date,
                             symbols: Optional[Iterable[str]] = None,
                             as_of: Optional[datetime] = None, limit: int = 200) -> List[Dict[str, Any]]:
        s_arr = _normalize_str_array(symbols, upper=True)
        lim = _clamp_limit(limit, hi=1000)
        conn = self._connect()
        try:
            if as_of is None:
                sql = ("SELECT earnings_id,symbol,report_date,year,quarter,hour,eps_estimate,"
                       "eps_actual,revenue_estimate,revenue_actual,NULL AS as_of_observed_at "
                       "FROM cal_earnings_events WHERE report_date>=? AND report_date<=?")
                params = [_iso(date_from), _iso(date_to)]
                cs, ps = _in_clause("symbol", s_arr)
                sql += cs + " ORDER BY report_date ASC, symbol ASC LIMIT ?"; params += ps + [lim]
            else:
                sql = ("SELECT e.earnings_id,e.symbol,e.report_date,e.year,e.quarter,rev.hour,"
                       "rev.eps_estimate,rev.eps_actual,rev.revenue_estimate,rev.revenue_actual,"
                       "rev.observed_at AS as_of_observed_at FROM cal_earnings_events e "
                       "JOIN cal_earnings_event_revisions rev ON rev.earnings_id=e.earnings_id "
                       "AND rev.observed_at=(SELECT MAX(observed_at) FROM cal_earnings_event_revisions "
                       "WHERE earnings_id=e.earnings_id AND observed_at<=?) "
                       "WHERE e.report_date>=? AND e.report_date<=?")
                params = [_iso(as_of), _iso(date_from), _iso(date_to)]
                cs, ps = _in_clause("e.symbol", s_arr)
                sql += cs + " ORDER BY e.report_date ASC, e.symbol ASC LIMIT ?"; params += ps + [lim]
            return self._list_query(conn, sql, params)
        finally:
            conn.close()

    def list_ipo_events(self, *, date_from: date, date_to: date,
                        statuses: Optional[Iterable[str]] = None,
                        as_of: Optional[datetime] = None, limit: int = 200) -> List[Dict[str, Any]]:
        st_arr = _normalize_str_array(statuses, lower=True)
        lim = _clamp_limit(limit, hi=1000)
        conn = self._connect()
        try:
            if as_of is None:
                sql = ("SELECT ipo_id,symbol,name,ipo_date,exchange,status,number_of_shares,price,"
                       "total_shares_value,NULL AS as_of_observed_at FROM cal_ipo_events "
                       "WHERE ipo_date>=? AND ipo_date<=?")
                params = [_iso(date_from), _iso(date_to)]
                cs, ps = _in_clause("status", st_arr)
                sql += cs + " ORDER BY ipo_date ASC, name ASC LIMIT ?"; params += ps + [lim]
            else:
                # as-of status filter is on the REVISION status (parity: _LIST_IPO_AS_OF_SQL).
                sql = ("SELECT e.ipo_id,e.symbol,e.name,e.ipo_date,rev.exchange,rev.status,"
                       "rev.number_of_shares,rev.price,rev.total_shares_value,"
                       "rev.observed_at AS as_of_observed_at FROM cal_ipo_events e "
                       "JOIN cal_ipo_event_revisions rev ON rev.ipo_id=e.ipo_id "
                       "AND rev.observed_at=(SELECT MAX(observed_at) FROM cal_ipo_event_revisions "
                       "WHERE ipo_id=e.ipo_id AND observed_at<=?) "
                       "WHERE e.ipo_date>=? AND e.ipo_date<=?")
                params = [_iso(as_of), _iso(date_from), _iso(date_to)]
                cs, ps = _in_clause("rev.status", st_arr)
                sql += cs + " ORDER BY e.ipo_date ASC, e.name ASC LIMIT ?"; params += ps + [lim]
            return self._list_query(conn, sql, params)
        finally:
            conn.close()

    def get_macro_observations(self, series_id: str, *, date_from: Optional[date] = None,
                               date_to: Optional[date] = None, as_of: Optional[date] = None,
                               limit: int = 1000) -> Optional[Dict[str, Any]]:
        """Series metadata + observation list. ``as_of`` selects the vintage window
        (realtime_start<=as_of<realtime_end); without it, the current vintage
        (realtime_end='9999-12-31'). None when the series is unknown."""
        conn = self._connect()
        try:
            meta = conn.execute("SELECT * FROM macro_series WHERE series_id=?", (series_id,)).fetchone()
            if meta is None:
                return None
            lim = _clamp_limit(limit, hi=10000)
            clause, params = "", [series_id]
            if as_of is None:
                clause = " AND realtime_end='9999-12-31'"
            else:
                clause = " AND realtime_start<=? AND realtime_end>?"
                params += [_iso(as_of), _iso(as_of)]
            if date_from is not None:
                clause += " AND observation_date>=?"; params.append(_iso(date_from))
            if date_to is not None:
                clause += " AND observation_date<=?"; params.append(_iso(date_to))
            params.append(lim)
            obs = conn.execute(
                "SELECT observation_date,value,realtime_start,realtime_end FROM macro_observations "
                f"WHERE series_id=?{clause} ORDER BY observation_date ASC LIMIT ?", params).fetchall()
            return {**dict(meta), "observations": [dict(o) for o in obs]}
        except sqlite3.OperationalError as exc:
            logger.warning("get_macro_observations failed for %s: %s", series_id, exc)
            return None
        finally:
            conn.close()

    # --- health support (local twin of macro_calendar_health._TABLE_STATS_SQL) ---------

    _HEALTH_TABLES = ("cal_economic_events", "cal_earnings_events", "cal_ipo_events",
                      "macro_series", "macro_observations", "macro_release_dates")

    def table_stats(self) -> Dict[str, Dict[str, Any]]:
        """Per-table MAX(fetched_at) + COUNT(*) for the 6 macro/cal tables — the local twin
        of the PG health ``_TABLE_STATS_SQL``. Returns ``{table: {last_fetched_at: str|None,
        row_count: int}}`` (last_fetched_at is ISO-TEXT; the health evaluator's _coerce_dt
        parses it)."""
        conn = self._connect()
        out: Dict[str, Dict[str, Any]] = {}
        try:
            for t in self._HEALTH_TABLES:
                row = conn.execute(f"SELECT MAX(fetched_at) AS f, COUNT(*) AS c FROM {t}").fetchone()
                out[t] = {"last_fetched_at": row["f"], "row_count": int(row["c"] or 0)}
        finally:
            conn.close()
        return out
