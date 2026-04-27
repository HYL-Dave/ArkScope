"""DAL helpers for P1.2 calendar + macro tables.

Three shared write patterns across the calendar tables (economic /
earnings / IPO):

  1. **Insert canonical + baseline revision** (first time we see a
     fingerprint). Without the baseline row, an as-of read targeted
     before any later mutation has nothing to match.
  2. **Update canonical + append observed revision** (subsequent
     ingestions where any tracked field differs from canonical). The
     revision row stores the **current** observed state at
     ``observed_at`` — NOT the previous canonical state. The read
     query in ``read_*_as_of`` walks the log backwards from ``as_of``;
     storing prior state would invert the time semantic.
  3. **No-op** when no tracked field differs.

All canonical + revision writes happen inside a single DB transaction
so a half-applied state cannot leak.

Macro side is simpler: FRED's vintage axis (``realtime_start`` /
``realtime_end``) IS the revision log, so a single
``UPSERT macro_observations`` per fetch is enough.

This module contains **no** Finnhub/FRED API client, **no** job
registration, and **no** API/tool wiring — those land in later P1.2
commits. See ``docs/design/P1_2_SPEC.md`` §9 for the sequence.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import psycopg2
    import psycopg2.extras
except Exception:  # pragma: no cover
    psycopg2 = None  # type: ignore[assignment]


# Tracked fields per calendar table — order doesn't matter; presence does.
ECONOMIC_TRACKED_FIELDS: Tuple[str, ...] = ("actual", "estimate", "prev")
EARNINGS_TRACKED_FIELDS: Tuple[str, ...] = (
    "eps_estimate", "eps_actual", "revenue_estimate", "revenue_actual", "hour",
)
IPO_TRACKED_FIELDS: Tuple[str, ...] = (
    "status", "price", "exchange", "number_of_shares", "total_shares_value",
)


# ---------------------------------------------------------------------------
# Fingerprint helpers
# ---------------------------------------------------------------------------


def economic_event_fingerprint(country: str, event_name: str, event_time: datetime) -> str:
    """Stable identity for an economic-calendar event.

    Inputs are normalised (country uppercased, event_name stripped, event_time
    converted to UTC and rendered as ISO 8601 with seconds) so re-fetching the
    same row from Finnhub upserts the same canonical row instead of
    duplicating it. The astimezone(UTC) step matters: the same wall-clock
    instant expressed as `+09:00` or `+00:00` must produce the same
    fingerprint, and Finnhub's `time` field is UTC anyway (smoke §5.2).
    """
    if event_time.tzinfo is None:
        raise ValueError("event_time must be timezone-aware")
    canon_country = (country or "").strip().upper()
    canon_name = (event_name or "").strip()
    canon_time = event_time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z")
    raw = f"{canon_country}|{canon_name}|{canon_time}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def earnings_event_fingerprint(symbol: str, year: int, quarter: int) -> str:
    """Stable identity for an earnings event.

    Symbol + fiscal year + quarter is unique per company per release.
    Date / hour can mutate (Finnhub flips ``''`` → ``bmo``/``amc`` as the
    report approaches), so they aren't part of the fingerprint.
    """
    raw = f"{(symbol or '').strip().upper()}|{int(year)}|{int(quarter)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def ipo_event_fingerprint(name: str, ipo_date: date) -> str:
    """Stable identity for an IPO row.

    ``symbol`` is intentionally NOT in the fingerprint because Finnhub
    returns null symbol for pre-listing rows. Name + planned ipo_date
    is the most stable available identity.
    """
    raw = f"{(name or '').strip()}|{ipo_date.isoformat()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_for_diff(value: Any) -> Any:
    """Coerce numeric-shaped values into a single canonical form for diffing.

    PostgreSQL NUMERIC columns come back as ``Decimal``; Finnhub payloads
    deliver ``float`` / ``int``. ``Decimal('4.1') != 4.1`` in vanilla
    Python, which would mark every re-ingest of an unchanged numeric row
    as a mutation and flood the revision log with no-ops.

    Strategy: numeric inputs (``Decimal`` / ``int`` / ``float`` / numeric
    strings) all collapse to ``Decimal(str(value))``. Bool inputs are
    intentionally NOT normalised — bool is a numeric subtype in Python
    but our schema uses bool semantically (no calendar field is bool
    today, but defending against the surprise costs nothing).

    Non-numeric values pass through unchanged so string / date /
    timestamp comparisons still work as expected.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return value
    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return value
    if isinstance(value, str):
        # Try to coerce numeric strings; non-numeric strings stay as-is so
        # status / hour / event_name comparisons keep their natural form.
        try:
            return Decimal(value)
        except (InvalidOperation, ValueError):
            return value
    return value


def _tracked_payload_differs(
    existing: Dict[str, Any],
    new: Dict[str, Any],
    fields: Iterable[str],
) -> bool:
    """Compare tracked fields with type-aware coercion.

    See ``_normalize_for_diff``. The TL;DR: ``Decimal('4.1')`` from the DB
    must compare equal to ``4.1`` from a Finnhub re-fetch.
    """
    for f in fields:
        if _normalize_for_diff(existing.get(f)) != _normalize_for_diff(new.get(f)):
            return True
    return False


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class MacroCalendarStore:
    """Thin SQL helper around the P1.2 schema.

    Construct with a DAL whose ``_backend`` exposes ``_get_conn()`` (the
    DatabaseBackend pattern used by the rest of the codebase). FileBackend
    DALs return ``is_available() == False`` and writes / reads short-circuit
    so callers can degrade.
    """

    def __init__(self, dal: Any) -> None:
        self._dal = dal
        self._backend = getattr(dal, "_backend", None)

    def is_available(self) -> bool:
        return self._backend is not None and hasattr(self._backend, "_get_conn")

    # =====================================================================
    # Calendar — Economic events
    # =====================================================================

    def upsert_economic_event(
        self,
        payload: Dict[str, Any],
        *,
        source_payload: Dict[str, Any],
        observed_at: Optional[datetime] = None,
    ) -> Tuple[Optional[int], str]:
        """Insert canonical + baseline revision OR update canonical + append observed revision.

        Required ``payload`` keys: ``country``, ``event_name``, ``event_time``,
        ``impact``, ``unit``, ``actual``, ``estimate``, ``prev``. Caller
        provides ``source_payload`` (raw provider row, stored in jsonb on the
        revision); ``observed_at`` defaults to now if omitted.

        Returns ``(event_id, action)`` where ``action`` ∈
        ``"inserted"`` / ``"mutated"`` / ``"unchanged"``. Returns
        ``(None, "unavailable")`` when the store has no DB.

        Atomic: canonical and revision rows are either both written or both
        rolled back. Tracked fields for change detection are
        ``ECONOMIC_TRACKED_FIELDS``.
        """
        if not self.is_available() or psycopg2 is None:
            return (None, "unavailable")
        fp = economic_event_fingerprint(
            payload["country"], payload["event_name"], payload["event_time"],
        )
        return self._upsert_calendar_event(
            canonical_table="cal_economic_events",
            revisions_table="cal_economic_event_revisions",
            id_column="event_id",
            fingerprint=fp,
            tracked_fields=ECONOMIC_TRACKED_FIELDS,
            insert_canonical_sql="""
                INSERT INTO cal_economic_events
                    (country, event_name, event_time, impact, unit,
                     actual, estimate, prev, fingerprint)
                VALUES (%s,%s,%s,%s,%s, %s,%s,%s, %s)
                RETURNING event_id
            """,
            insert_canonical_params=(
                payload["country"], payload["event_name"], payload["event_time"],
                payload.get("impact", ""), payload.get("unit"),
                payload.get("actual"), payload.get("estimate"), payload.get("prev"),
                fp,
            ),
            update_canonical_sql="""
                UPDATE cal_economic_events
                SET impact = %s, unit = %s,
                    actual = %s, estimate = %s, prev = %s,
                    updated_at = NOW()
                WHERE event_id = %s
            """,
            update_canonical_params=lambda eid: (
                payload.get("impact", ""), payload.get("unit"),
                payload.get("actual"), payload.get("estimate"), payload.get("prev"),
                eid,
            ),
            insert_revision_sql="""
                INSERT INTO cal_economic_event_revisions
                    (event_id, observed_at, actual, estimate, prev, source_payload)
                VALUES (%s, COALESCE(%s, NOW()), %s, %s, %s, %s)
            """,
            insert_revision_params=lambda eid: (
                eid, observed_at,
                payload.get("actual"), payload.get("estimate"), payload.get("prev"),
                psycopg2.extras.Json(source_payload),
            ),
            tracked_payload=payload,
        )

    def read_economic_event_as_of(
        self,
        event_id: int,
        as_of: datetime,
    ) -> Optional[Dict[str, Any]]:
        """Return the most recent revision with ``observed_at <= as_of``.

        Result shape mirrors the revision row's tracked fields plus
        ``observed_at`` and ``source_payload``. Returns None when no
        revision exists at or before ``as_of`` (i.e. caller is asking
        about a time before we ever observed the event).
        """
        return self._read_revision_as_of(
            sql="""
                SELECT observed_at, actual, estimate, prev, source_payload
                FROM cal_economic_event_revisions
                WHERE event_id = %s AND observed_at <= %s
                ORDER BY observed_at DESC
                LIMIT 1
            """,
            params=(event_id, as_of),
        )

    # =====================================================================
    # Calendar — Earnings events
    # =====================================================================

    def upsert_earnings_event(
        self,
        payload: Dict[str, Any],
        *,
        source_payload: Dict[str, Any],
        observed_at: Optional[datetime] = None,
    ) -> Tuple[Optional[int], str]:
        """Per-symbol upsert. See ``upsert_economic_event`` for contract."""
        if not self.is_available() or psycopg2 is None:
            return (None, "unavailable")
        fp = earnings_event_fingerprint(
            payload["symbol"], payload["year"], payload["quarter"],
        )
        return self._upsert_calendar_event(
            canonical_table="cal_earnings_events",
            revisions_table="cal_earnings_event_revisions",
            id_column="earnings_id",
            fingerprint=fp,
            tracked_fields=EARNINGS_TRACKED_FIELDS,
            insert_canonical_sql="""
                INSERT INTO cal_earnings_events
                    (symbol, report_date, year, quarter, hour,
                     eps_estimate, eps_actual, revenue_estimate, revenue_actual,
                     fingerprint)
                VALUES (%s,%s,%s,%s,%s, %s,%s,%s,%s, %s)
                RETURNING earnings_id
            """,
            insert_canonical_params=(
                payload["symbol"], payload["report_date"],
                payload["year"], payload["quarter"], payload.get("hour", ""),
                payload.get("eps_estimate"), payload.get("eps_actual"),
                payload.get("revenue_estimate"), payload.get("revenue_actual"),
                fp,
            ),
            update_canonical_sql="""
                UPDATE cal_earnings_events
                SET report_date = %s, hour = %s,
                    eps_estimate = %s, eps_actual = %s,
                    revenue_estimate = %s, revenue_actual = %s,
                    updated_at = NOW()
                WHERE earnings_id = %s
            """,
            update_canonical_params=lambda eid: (
                payload["report_date"], payload.get("hour", ""),
                payload.get("eps_estimate"), payload.get("eps_actual"),
                payload.get("revenue_estimate"), payload.get("revenue_actual"),
                eid,
            ),
            insert_revision_sql="""
                INSERT INTO cal_earnings_event_revisions
                    (earnings_id, observed_at,
                     eps_estimate, eps_actual,
                     revenue_estimate, revenue_actual,
                     hour, source_payload)
                VALUES (%s, COALESCE(%s, NOW()), %s, %s, %s, %s, %s, %s)
            """,
            insert_revision_params=lambda eid: (
                eid, observed_at,
                payload.get("eps_estimate"), payload.get("eps_actual"),
                payload.get("revenue_estimate"), payload.get("revenue_actual"),
                payload.get("hour", ""),
                psycopg2.extras.Json(source_payload),
            ),
            tracked_payload=payload,
        )

    def read_earnings_event_as_of(
        self,
        earnings_id: int,
        as_of: datetime,
    ) -> Optional[Dict[str, Any]]:
        return self._read_revision_as_of(
            sql="""
                SELECT observed_at, eps_estimate, eps_actual,
                       revenue_estimate, revenue_actual, hour, source_payload
                FROM cal_earnings_event_revisions
                WHERE earnings_id = %s AND observed_at <= %s
                ORDER BY observed_at DESC
                LIMIT 1
            """,
            params=(earnings_id, as_of),
        )

    # =====================================================================
    # Calendar — IPO events
    # =====================================================================

    def upsert_ipo_event(
        self,
        payload: Dict[str, Any],
        *,
        source_payload: Dict[str, Any],
        observed_at: Optional[datetime] = None,
    ) -> Tuple[Optional[int], str]:
        """Upsert IPO row. See ``upsert_economic_event`` for contract."""
        if not self.is_available() or psycopg2 is None:
            return (None, "unavailable")
        fp = ipo_event_fingerprint(payload["name"], payload["ipo_date"])
        return self._upsert_calendar_event(
            canonical_table="cal_ipo_events",
            revisions_table="cal_ipo_event_revisions",
            id_column="ipo_id",
            fingerprint=fp,
            tracked_fields=IPO_TRACKED_FIELDS,
            insert_canonical_sql="""
                INSERT INTO cal_ipo_events
                    (symbol, name, ipo_date, exchange, status,
                     number_of_shares, price, total_shares_value, fingerprint)
                VALUES (%s,%s,%s,%s,%s, %s,%s,%s, %s)
                RETURNING ipo_id
            """,
            insert_canonical_params=(
                payload.get("symbol"), payload["name"], payload["ipo_date"],
                payload.get("exchange"), payload["status"],
                payload.get("number_of_shares"), payload.get("price"),
                payload.get("total_shares_value"), fp,
            ),
            update_canonical_sql="""
                UPDATE cal_ipo_events
                SET symbol = %s, exchange = %s, status = %s,
                    number_of_shares = %s, price = %s, total_shares_value = %s,
                    updated_at = NOW()
                WHERE ipo_id = %s
            """,
            update_canonical_params=lambda eid: (
                payload.get("symbol"), payload.get("exchange"), payload["status"],
                payload.get("number_of_shares"), payload.get("price"),
                payload.get("total_shares_value"), eid,
            ),
            insert_revision_sql="""
                INSERT INTO cal_ipo_event_revisions
                    (ipo_id, observed_at, status, price, exchange,
                     number_of_shares, total_shares_value, source_payload)
                VALUES (%s, COALESCE(%s, NOW()), %s, %s, %s, %s, %s, %s)
            """,
            insert_revision_params=lambda eid: (
                eid, observed_at, payload["status"], payload.get("price"),
                payload.get("exchange"), payload.get("number_of_shares"),
                payload.get("total_shares_value"),
                psycopg2.extras.Json(source_payload),
            ),
            tracked_payload=payload,
        )

    def read_ipo_event_as_of(
        self,
        ipo_id: int,
        as_of: datetime,
    ) -> Optional[Dict[str, Any]]:
        return self._read_revision_as_of(
            sql="""
                SELECT observed_at, status, price, exchange,
                       number_of_shares, total_shares_value, source_payload
                FROM cal_ipo_event_revisions
                WHERE ipo_id = %s AND observed_at <= %s
                ORDER BY observed_at DESC
                LIMIT 1
            """,
            params=(ipo_id, as_of),
        )

    # =====================================================================
    # Macro — series catalog
    # =====================================================================

    def upsert_macro_series(self, payload: Dict[str, Any]) -> bool:
        """Upsert a FRED series's metadata catalog row."""
        if not self.is_available() or psycopg2 is None:
            return False
        try:
            conn = self._backend._get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO macro_series
                        (series_id, title, frequency, units,
                         seasonal_adjustment, last_updated, revision_strategy)
                    VALUES (%s,%s,%s,%s, %s,%s,%s)
                    ON CONFLICT (series_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        frequency = EXCLUDED.frequency,
                        units = EXCLUDED.units,
                        seasonal_adjustment = EXCLUDED.seasonal_adjustment,
                        last_updated = EXCLUDED.last_updated,
                        revision_strategy = EXCLUDED.revision_strategy,
                        updated_at = NOW()
                    """,
                    (
                        payload["series_id"], payload["title"],
                        payload["frequency"], payload["units"],
                        payload.get("seasonal_adjustment"),
                        payload.get("last_updated"),
                        payload.get("revision_strategy", "latest_only"),
                    ),
                )
            return True
        except Exception as exc:
            logger.warning("upsert_macro_series failed for %s: %s",
                           payload.get("series_id"), exc)
            return False

    def get_macro_series(self, series_id: str) -> Optional[Dict[str, Any]]:
        if not self.is_available() or psycopg2 is None:
            return None
        try:
            conn = self._backend._get_conn()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM macro_series WHERE series_id = %s",
                    (series_id,),
                )
                row = cur.fetchone()
            return dict(row) if row else None
        except Exception as exc:
            logger.warning("get_macro_series failed for %s: %s", series_id, exc)
            return None

    # =====================================================================
    # Macro — observations (FRED native vintages, no revision log)
    # =====================================================================

    def upsert_macro_observation(
        self,
        *,
        series_id: str,
        observation_date: date,
        value: Optional[Any],
        realtime_start: date,
        realtime_end: Optional[date] = None,
    ) -> bool:
        """Upsert one FRED observation. ``realtime_start`` is mandatory.

        Spec §3.2: no sentinel default. If the caller doesn't know the
        release date for a ``latest_only`` series, the ingestion job is
        expected to skip the row instead of asking us to write one.
        """
        if realtime_start is None:
            raise ValueError("realtime_start is mandatory; sentinel writes are not allowed")
        if not self.is_available() or psycopg2 is None:
            return False
        try:
            conn = self._backend._get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO macro_observations
                        (series_id, observation_date, value, realtime_start, realtime_end)
                    VALUES (%s,%s,%s,%s, COALESCE(%s, '9999-12-31'::date))
                    ON CONFLICT (series_id, observation_date, realtime_start) DO UPDATE SET
                        value = EXCLUDED.value,
                        realtime_end = EXCLUDED.realtime_end,
                        fetched_at = NOW()
                    """,
                    (series_id, observation_date, value, realtime_start, realtime_end),
                )
            return True
        except Exception as exc:
            logger.warning("upsert_macro_observation failed for %s/%s: %s",
                           series_id, observation_date, exc)
            return False

    def get_macro_value_as_of(
        self,
        series_id: str,
        observation_date: date,
        as_of: date,
    ) -> Optional[Any]:
        """Return the value of (series_id, observation_date) as known at as_of.

        Picks the row whose vintage window contains as_of:
            realtime_start <= as_of < realtime_end
        """
        if not self.is_available() or psycopg2 is None:
            return None
        try:
            conn = self._backend._get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT value
                    FROM macro_observations
                    WHERE series_id = %s
                      AND observation_date = %s
                      AND realtime_start <= %s
                      AND realtime_end > %s
                    ORDER BY realtime_start DESC
                    LIMIT 1
                    """,
                    (series_id, observation_date, as_of, as_of),
                )
                row = cur.fetchone()
            return row[0] if row else None
        except Exception as exc:
            logger.warning("get_macro_value_as_of failed for %s/%s: %s",
                           series_id, observation_date, exc)
            return None

    # =====================================================================
    # Macro — release schedule
    # =====================================================================

    def upsert_release_date(
        self,
        *,
        release_id: int,
        release_name: str,
        release_date_value: date,
    ) -> bool:
        if not self.is_available() or psycopg2 is None:
            return False
        try:
            conn = self._backend._get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO macro_release_dates
                        (release_id, release_name, release_date)
                    VALUES (%s,%s,%s)
                    ON CONFLICT (release_id, release_date) DO UPDATE SET
                        release_name = EXCLUDED.release_name,
                        fetched_at = NOW()
                    """,
                    (release_id, release_name, release_date_value),
                )
            return True
        except Exception as exc:
            logger.warning("upsert_release_date failed: %s", exc)
            return False

    def get_release_dates(
        self,
        release_id: int,
        *,
        before: Optional[date] = None,
        limit: int = 100,
    ) -> List[date]:
        if not self.is_available() or psycopg2 is None:
            return []
        params: List[Any] = [release_id]
        clause = ""
        if before is not None:
            clause = " AND release_date < %s"
            params.append(before)
        params.append(max(1, min(int(limit), 1000)))
        try:
            conn = self._backend._get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT release_date FROM macro_release_dates
                    WHERE release_id = %s {clause}
                    ORDER BY release_date DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [r[0] for r in cur.fetchall()]
        except Exception as exc:
            logger.warning("get_release_dates failed: %s", exc)
            return []

    # =====================================================================
    # Internal — shared upsert + read primitives
    # =====================================================================

    def _upsert_calendar_event(
        self,
        *,
        canonical_table: str,
        revisions_table: str,
        id_column: str,
        fingerprint: str,
        tracked_fields: Iterable[str],
        insert_canonical_sql: str,
        insert_canonical_params: tuple,
        update_canonical_sql: str,
        update_canonical_params,
        insert_revision_sql: str,
        insert_revision_params,
        tracked_payload: Dict[str, Any],
    ) -> Tuple[Optional[int], str]:
        """Common transactional flow for the three calendar tables.

        First insert: writes canonical + baseline revision in one transaction.
        Subsequent ingestion: if any tracked field differs, updates canonical
        and appends an observed-state revision in one transaction. Otherwise
        no-op (no canonical write, no revision write — even ``fetched_at``
        bump is skipped to keep the table immune to rate-of-fetch noise).
        """
        conn = self._backend._get_conn()
        old_autocommit = conn.autocommit
        conn.autocommit = False
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"""
                    SELECT {id_column},
                           {", ".join(tracked_fields)}
                    FROM {canonical_table}
                    WHERE fingerprint = %s
                    FOR UPDATE
                    """,
                    (fingerprint,),
                )
                existing = cur.fetchone()
                if existing is None:
                    cur.execute(insert_canonical_sql, insert_canonical_params)
                    new_id = cur.fetchone()[id_column]
                    cur.execute(insert_revision_sql, insert_revision_params(new_id))
                    conn.commit()
                    return (int(new_id), "inserted")

                eid = int(existing[id_column])
                if not _tracked_payload_differs(existing, tracked_payload, tracked_fields):
                    conn.commit()
                    return (eid, "unchanged")

                cur.execute(update_canonical_sql, update_canonical_params(eid))
                cur.execute(insert_revision_sql, insert_revision_params(eid))
                conn.commit()
                return (eid, "mutated")
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.error("upsert into %s failed: %s", canonical_table, exc)
            raise
        finally:
            conn.autocommit = old_autocommit

    def _read_revision_as_of(
        self,
        *,
        sql: str,
        params: tuple,
    ) -> Optional[Dict[str, Any]]:
        if not self.is_available() or psycopg2 is None:
            return None
        try:
            conn = self._backend._get_conn()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
            if row is None:
                return None
            return dict(row)
        except Exception as exc:
            logger.warning("revision as-of read failed: %s", exc)
            return None

    # =====================================================================
    # Read-only list queries (commit 6)
    # =====================================================================

    def list_economic_events(
        self,
        *,
        date_from: datetime,
        date_to: datetime,
        countries: Optional[Iterable[str]] = None,
        impacts: Optional[Iterable[str]] = None,
        as_of: Optional[datetime] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """List economic events in [date_from, date_to].

        When ``as_of`` is None: returns canonical (current) values.
        When ``as_of`` is set: returns the revision visible at that
        timestamp via ``cal_economic_event_revisions`` — events first
        observed AFTER ``as_of`` are excluded entirely (they were
        unknown at that time, so a lookahead-safe read must omit them).
        """
        if not self.is_available() or psycopg2 is None:
            return []
        country_arr = _normalize_str_array(countries, upper=True)
        impact_arr = _normalize_str_array(impacts, lower=True)
        try:
            conn = self._backend._get_conn()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if as_of is None:
                    cur.execute(_LIST_ECONOMIC_CANONICAL_SQL, {
                        "date_from": date_from,
                        "date_to": date_to,
                        "countries": country_arr,
                        "impacts": impact_arr,
                        "limit": _clamp_limit(limit, hi=1000),
                    })
                else:
                    cur.execute(_LIST_ECONOMIC_AS_OF_SQL, {
                        "date_from": date_from,
                        "date_to": date_to,
                        "countries": country_arr,
                        "impacts": impact_arr,
                        "as_of": as_of,
                        "limit": _clamp_limit(limit, hi=1000),
                    })
                return [dict(r) for r in cur.fetchall()]
        except Exception as exc:
            logger.warning("list_economic_events failed: %s", exc)
            return []

    def list_earnings_events(
        self,
        *,
        date_from: date,
        date_to: date,
        symbols: Optional[Iterable[str]] = None,
        as_of: Optional[datetime] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """List earnings events in [date_from, date_to] (report_date filter)."""
        if not self.is_available() or psycopg2 is None:
            return []
        symbol_arr = _normalize_str_array(symbols, upper=True)
        try:
            conn = self._backend._get_conn()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if as_of is None:
                    cur.execute(_LIST_EARNINGS_CANONICAL_SQL, {
                        "date_from": date_from,
                        "date_to": date_to,
                        "symbols": symbol_arr,
                        "limit": _clamp_limit(limit, hi=1000),
                    })
                else:
                    cur.execute(_LIST_EARNINGS_AS_OF_SQL, {
                        "date_from": date_from,
                        "date_to": date_to,
                        "symbols": symbol_arr,
                        "as_of": as_of,
                        "limit": _clamp_limit(limit, hi=1000),
                    })
                return [dict(r) for r in cur.fetchall()]
        except Exception as exc:
            logger.warning("list_earnings_events failed: %s", exc)
            return []

    def list_ipo_events(
        self,
        *,
        date_from: date,
        date_to: date,
        statuses: Optional[Iterable[str]] = None,
        as_of: Optional[datetime] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """List IPO events in [date_from, date_to]."""
        if not self.is_available() or psycopg2 is None:
            return []
        status_arr = _normalize_str_array(statuses, lower=True)
        try:
            conn = self._backend._get_conn()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if as_of is None:
                    cur.execute(_LIST_IPO_CANONICAL_SQL, {
                        "date_from": date_from,
                        "date_to": date_to,
                        "statuses": status_arr,
                        "limit": _clamp_limit(limit, hi=1000),
                    })
                else:
                    cur.execute(_LIST_IPO_AS_OF_SQL, {
                        "date_from": date_from,
                        "date_to": date_to,
                        "statuses": status_arr,
                        "as_of": as_of,
                        "limit": _clamp_limit(limit, hi=1000),
                    })
                return [dict(r) for r in cur.fetchall()]
        except Exception as exc:
            logger.warning("list_ipo_events failed: %s", exc)
            return []

    def get_macro_observations(
        self,
        series_id: str,
        *,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        as_of: Optional[date] = None,
        limit: int = 1000,
    ) -> Optional[Dict[str, Any]]:
        """Return series metadata + observation list for ``series_id``.

        ``as_of`` selects the vintage window that contained that date —
        i.e. ``realtime_start <= as_of < realtime_end``. Without ``as_of``
        the current vintage (``realtime_end='9999-12-31'``) is returned.
        Returns None when the series is unknown.
        """
        if not self.is_available() or psycopg2 is None:
            return None
        try:
            conn = self._backend._get_conn()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM macro_series WHERE series_id = %s",
                    (series_id,),
                )
                meta = cur.fetchone()
                if meta is None:
                    return None
                params: Dict[str, Any] = {
                    "series_id": series_id,
                    "date_from": date_from,
                    "date_to": date_to,
                    "limit": _clamp_limit(limit, hi=10000),
                }
                if as_of is None:
                    cur.execute(_OBSERVATIONS_CURRENT_SQL, params)
                else:
                    params["as_of"] = as_of
                    cur.execute(_OBSERVATIONS_AS_OF_SQL, params)
                obs = [dict(r) for r in cur.fetchall()]
            return {**dict(meta), "observations": obs}
        except Exception as exc:
            logger.warning("get_macro_observations failed for %s: %s", series_id, exc)
            return None


# ---------------------------------------------------------------------------
# Read-query SQL + helpers (commit 6)
# ---------------------------------------------------------------------------


def _normalize_str_array(
    values: Optional[Iterable[str]],
    *,
    upper: bool = False,
    lower: bool = False,
) -> Optional[List[str]]:
    """Return a normalized list for psycopg2 ``ANY(%s::text[])`` filters,
    or None when the caller passed nothing (so the SQL ``IS NULL`` branch
    skips the filter)."""
    if values is None:
        return None
    out: List[str] = []
    seen = set()
    for v in values:
        if v is None:
            continue
        s = str(v).strip()
        if not s:
            continue
        if upper:
            s = s.upper()
        elif lower:
            s = s.lower()
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out or None


def _clamp_limit(limit: Any, *, hi: int, lo: int = 1) -> int:
    try:
        n = int(limit)
    except (TypeError, ValueError):
        return hi
    return max(lo, min(hi, n))


# Canonical (current-state) reads. ``%(countries)s::text[] IS NULL OR
# country = ANY(...)`` skips the filter when the caller passed None.

_LIST_ECONOMIC_CANONICAL_SQL = """
    SELECT event_id, country, event_name, event_time, impact, unit,
           actual, estimate, prev,
           NULL::timestamptz AS as_of_observed_at
    FROM cal_economic_events
    WHERE event_time >= %(date_from)s AND event_time <= %(date_to)s
      AND (%(countries)s::text[] IS NULL OR country = ANY(%(countries)s::text[]))
      AND (%(impacts)s::text[]   IS NULL OR impact  = ANY(%(impacts)s::text[]))
    ORDER BY event_time ASC
    LIMIT %(limit)s
"""

# As-of reads use INNER JOIN LATERAL: events with no revision <= as_of are
# excluded because they were unknown at that timestamp (lookahead-safe).
_LIST_ECONOMIC_AS_OF_SQL = """
    SELECT e.event_id, e.country, e.event_name, e.event_time, e.impact, e.unit,
           rev.actual, rev.estimate, rev.prev,
           rev.observed_at AS as_of_observed_at
    FROM cal_economic_events e
    INNER JOIN LATERAL (
        SELECT actual, estimate, prev, observed_at
        FROM cal_economic_event_revisions
        WHERE event_id = e.event_id AND observed_at <= %(as_of)s
        ORDER BY observed_at DESC
        LIMIT 1
    ) rev ON TRUE
    WHERE e.event_time >= %(date_from)s AND e.event_time <= %(date_to)s
      AND (%(countries)s::text[] IS NULL OR e.country = ANY(%(countries)s::text[]))
      AND (%(impacts)s::text[]   IS NULL OR e.impact  = ANY(%(impacts)s::text[]))
    ORDER BY e.event_time ASC
    LIMIT %(limit)s
"""

_LIST_EARNINGS_CANONICAL_SQL = """
    SELECT earnings_id, symbol, report_date, year, quarter, hour,
           eps_estimate, eps_actual, revenue_estimate, revenue_actual,
           NULL::timestamptz AS as_of_observed_at
    FROM cal_earnings_events
    WHERE report_date >= %(date_from)s AND report_date <= %(date_to)s
      AND (%(symbols)s::text[] IS NULL OR symbol = ANY(%(symbols)s::text[]))
    ORDER BY report_date ASC, symbol ASC
    LIMIT %(limit)s
"""

_LIST_EARNINGS_AS_OF_SQL = """
    SELECT e.earnings_id, e.symbol, e.report_date, e.year, e.quarter,
           rev.hour,
           rev.eps_estimate, rev.eps_actual,
           rev.revenue_estimate, rev.revenue_actual,
           rev.observed_at AS as_of_observed_at
    FROM cal_earnings_events e
    INNER JOIN LATERAL (
        SELECT hour, eps_estimate, eps_actual,
               revenue_estimate, revenue_actual, observed_at
        FROM cal_earnings_event_revisions
        WHERE earnings_id = e.earnings_id AND observed_at <= %(as_of)s
        ORDER BY observed_at DESC
        LIMIT 1
    ) rev ON TRUE
    WHERE e.report_date >= %(date_from)s AND e.report_date <= %(date_to)s
      AND (%(symbols)s::text[] IS NULL OR e.symbol = ANY(%(symbols)s::text[]))
    ORDER BY e.report_date ASC, e.symbol ASC
    LIMIT %(limit)s
"""

_LIST_IPO_CANONICAL_SQL = """
    SELECT ipo_id, symbol, name, ipo_date, exchange, status,
           number_of_shares, price, total_shares_value,
           NULL::timestamptz AS as_of_observed_at
    FROM cal_ipo_events
    WHERE ipo_date >= %(date_from)s AND ipo_date <= %(date_to)s
      AND (%(statuses)s::text[] IS NULL OR status = ANY(%(statuses)s::text[]))
    ORDER BY ipo_date ASC, name ASC
    LIMIT %(limit)s
"""

_LIST_IPO_AS_OF_SQL = """
    SELECT e.ipo_id, e.symbol, e.name, e.ipo_date,
           rev.exchange, rev.status,
           rev.number_of_shares, rev.price, rev.total_shares_value,
           rev.observed_at AS as_of_observed_at
    FROM cal_ipo_events e
    INNER JOIN LATERAL (
        SELECT exchange, status, number_of_shares, price,
               total_shares_value, observed_at
        FROM cal_ipo_event_revisions
        WHERE ipo_id = e.ipo_id AND observed_at <= %(as_of)s
        ORDER BY observed_at DESC
        LIMIT 1
    ) rev ON TRUE
    WHERE e.ipo_date >= %(date_from)s AND e.ipo_date <= %(date_to)s
      AND (%(statuses)s::text[] IS NULL OR rev.status = ANY(%(statuses)s::text[]))
    ORDER BY e.ipo_date ASC, e.name ASC
    LIMIT %(limit)s
"""

# Macro observations. Current vintage = realtime_end='9999-12-31' window.
# Date filters are optional (NULL skips the clause).
_OBSERVATIONS_CURRENT_SQL = """
    SELECT observation_date, value, realtime_start, realtime_end
    FROM macro_observations
    WHERE series_id = %(series_id)s
      AND realtime_end = '9999-12-31'::date
      AND (%(date_from)s::date IS NULL OR observation_date >= %(date_from)s::date)
      AND (%(date_to)s::date   IS NULL OR observation_date <= %(date_to)s::date)
    ORDER BY observation_date ASC
    LIMIT %(limit)s
"""

# As-of: pick the vintage window that contained ``as_of``. For each
# observation_date in range, the matching row is the one whose
# [realtime_start, realtime_end) bracket contains as_of.
_OBSERVATIONS_AS_OF_SQL = """
    SELECT observation_date, value, realtime_start, realtime_end
    FROM macro_observations
    WHERE series_id = %(series_id)s
      AND realtime_start <= %(as_of)s::date
      AND realtime_end   >  %(as_of)s::date
      AND (%(date_from)s::date IS NULL OR observation_date >= %(date_from)s::date)
      AND (%(date_to)s::date   IS NULL OR observation_date <= %(date_to)s::date)
    ORDER BY observation_date ASC
    LIMIT %(limit)s
"""