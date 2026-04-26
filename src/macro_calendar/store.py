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