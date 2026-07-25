from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sqlite3

from .models import (
    CalendarDay,
    CalendarDayKind,
    ObservationHealth,
    ObservationHealthAssessment,
    ObservationHealthReason,
    ObservationReadResult,
    ProviderSyncIssue,
    RthObservation,
    RthSessionObservations,
)


_REQUIRED_PRICE_COLUMNS = frozenset({"ticker", "datetime", "interval"})
_TICKER_ALIAS_COLUMNS = frozenset({"alias", "canonical"})
_PROVIDER_SYNC_COLUMNS = frozenset(
    {"ticker", "interval", "last_error", "updated_at"}
)


class _StoredDatabaseError(Exception):
    pass


def _open_read_only_market_db(path: str | Path) -> sqlite3.Connection:
    database_path = Path(path).expanduser().resolve(strict=False)
    conn = sqlite3.connect(f"{database_path.as_uri()}?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        if conn.execute("PRAGMA query_only").fetchone() != (1,):
            raise sqlite3.OperationalError("SQLite query_only mode was not enabled")
    except BaseException:
        conn.close()
        raise
    return conn


def _unavailable(reason: ObservationHealthReason) -> ObservationReadResult:
    return ObservationReadResult(
        health=ObservationHealthAssessment(
            status=ObservationHealth.UNAVAILABLE,
            reason_code=reason,
        ),
        sessions=(),
        provider_errors=(),
    )


def _table_columns(
    conn: sqlite3.Connection,
    table_name: str,
) -> frozenset[str] | None:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    if exists is None:
        return None
    return frozenset(
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM pragma_table_info(?)",
            (table_name,),
        )
    )


def _normalize_ticker(value: object, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip().upper()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized


def _normalize_stored_ticker(value: object, *, field_name: str) -> str:
    try:
        return _normalize_ticker(value, field_name=field_name)
    except (TypeError, ValueError) as exc:
        raise _StoredDatabaseError(str(exc)) from exc


def _load_aliases(conn: sqlite3.Connection) -> dict[str, str]:
    columns = _table_columns(conn, "ticker_aliases")
    if columns is None:
        return {}
    if not _TICKER_ALIAS_COLUMNS <= columns:
        raise _StoredDatabaseError("ticker_aliases schema is incompatible")

    aliases: dict[str, str] = {}
    for raw_alias, raw_canonical in conn.execute(
        "SELECT alias, canonical FROM ticker_aliases"
    ):
        alias = _normalize_stored_ticker(
            raw_alias,
            field_name="stored ticker alias",
        )
        canonical = _normalize_stored_ticker(
            raw_canonical,
            field_name="stored canonical ticker",
        )
        existing = aliases.get(alias)
        if existing is not None and existing != canonical:
            raise _StoredDatabaseError(
                f"normalized ticker alias collision: {alias}"
            )
        aliases[alias] = canonical
    return aliases


def _canonical_universe(
    universe: Sequence[str],
    aliases: dict[str, str],
) -> tuple[str, ...]:
    if isinstance(universe, (str, bytes)):
        raise TypeError("universe must be a sequence of ticker strings")

    canonical: list[str] = []
    seen: set[str] = set()
    for raw_ticker in universe:
        ticker = _normalize_ticker(raw_ticker, field_name="universe ticker")
        ticker = aliases.get(ticker, ticker)
        if ticker not in seen:
            seen.add(ticker)
            canonical.append(ticker)
    if not canonical:
        raise ValueError("universe must contain at least one canonical ticker")
    return tuple(canonical)


def _open_sessions(sessions: Sequence[CalendarDay]) -> tuple[CalendarDay, ...]:
    if isinstance(sessions, (str, bytes)):
        raise TypeError("sessions must be a sequence of CalendarDay values")
    session_values = tuple(sessions)
    if any(not isinstance(session, CalendarDay) for session in session_values):
        raise TypeError("sessions must contain CalendarDay values")

    open_sessions = tuple(
        sorted(
            (
                session
                for session in session_values
                if session.kind is CalendarDayKind.OPEN
            ),
            key=lambda session: session.open_at_utc,
        )
    )
    market_dates = tuple(session.market_date for session in open_sessions)
    if len(market_dates) != len(set(market_dates)):
        raise ValueError("open sessions must have unique market dates")

    previous_close: datetime | None = None
    for session in open_sessions:
        open_at = session.open_at_utc
        close_at = session.close_at_utc
        assert open_at is not None
        assert close_at is not None
        if previous_close is not None and open_at < previous_close:
            raise ValueError("open session windows cannot overlap")
        previous_close = close_at
    return open_sessions


def _parse_stored_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise _StoredDatabaseError("stored price datetime must be a string")
    serialized = value.strip()
    if serialized.endswith(("Z", "z")):
        serialized = f"{serialized[:-1]}+00:00"
    elif (
        len(serialized) >= 5
        and serialized[-5] in {"+", "-"}
        and serialized[-4:].isdigit()
    ):
        serialized = f"{serialized[:-2]}:{serialized[-2:]}"
    try:
        parsed = datetime.fromisoformat(serialized)
    except ValueError as exc:
        raise _StoredDatabaseError(
            f"invalid stored price datetime: {value!r}"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _StoredDatabaseError(
            "stored price datetime must be timezone-aware"
        )
    return parsed.astimezone(timezone.utc)


def _read_provider_errors(
    conn: sqlite3.Connection,
    *,
    interval: str,
    aliases: dict[str, str],
    canonical_universe: set[str],
) -> tuple[ProviderSyncIssue, ...]:
    columns = _table_columns(conn, "provider_sync_meta")
    if columns is None:
        return ()
    if not _PROVIDER_SYNC_COLUMNS <= columns:
        raise _StoredDatabaseError("provider_sync_meta schema is incompatible")

    issues: list[ProviderSyncIssue] = []
    for raw_ticker, raw_interval, raw_error, raw_updated_at in conn.execute(
        "SELECT ticker, interval, last_error, updated_at "
        "FROM provider_sync_meta"
    ):
        ticker = _normalize_stored_ticker(
            raw_ticker,
            field_name="provider issue ticker",
        )
        if not isinstance(raw_interval, str) or (
            not raw_interval or raw_interval != raw_interval.strip()
        ):
            raise _StoredDatabaseError("provider issue interval is malformed")
        if raw_error is not None and (
            not isinstance(raw_error, str) or not raw_error.strip()
        ):
            raise _StoredDatabaseError("provider issue last_error is malformed")
        if raw_updated_at is not None and not isinstance(raw_updated_at, str):
            raise _StoredDatabaseError("provider issue updated_at is malformed")

        if raw_interval != interval or raw_error is None:
            continue
        ticker = aliases.get(ticker, ticker)
        if ticker not in canonical_universe:
            continue
        issues.append(
            ProviderSyncIssue(
                ticker=ticker,
                interval=raw_interval,
                last_error=raw_error.strip(),
                updated_at=raw_updated_at,
            )
        )

    return tuple(
        sorted(
            issues,
            key=lambda issue: (
                issue.updated_at or "",
                issue.ticker,
                issue.interval,
                issue.last_error,
            ),
            reverse=True,
        )
    )


def _read_session_observations(
    conn: sqlite3.Connection,
    *,
    sessions: tuple[CalendarDay, ...],
    interval: str,
    aliases: dict[str, str],
    canonical_universe: tuple[str, ...],
) -> tuple[RthSessionObservations, ...]:
    buckets: dict[date, list[RthObservation]] = {
        session.market_date: [] for session in sessions
    }
    if not sessions:
        return ()

    canonical_set = set(canonical_universe)
    stored_tickers = canonical_set | {
        alias for alias, canonical in aliases.items() if canonical in canonical_set
    }
    placeholders = ", ".join("?" for _ in stored_tickers)
    earliest_open = sessions[0].open_at_utc
    latest_close = sessions[-1].close_at_utc
    assert earliest_open is not None
    assert latest_close is not None
    lower_bound = (earliest_open.date() - timedelta(days=1)).isoformat()
    upper_bound = (latest_close.date() + timedelta(days=2)).isoformat()
    query = (
        "SELECT ticker, datetime FROM prices "
        f"WHERE interval = ? AND UPPER(TRIM(ticker)) IN ({placeholders}) "
        "AND datetime >= ? AND datetime < ?"
    )
    parameters = (
        interval,
        *sorted(stored_tickers),
        lower_bound,
        upper_bound,
    )

    opens = tuple(session.open_at_utc for session in sessions)
    assert all(open_at is not None for open_at in opens)
    for raw_ticker, raw_timestamp in conn.execute(query, parameters):
        ticker = _normalize_stored_ticker(
            raw_ticker,
            field_name="stored price ticker",
        )
        ticker = aliases.get(ticker, ticker)
        if ticker not in canonical_set:
            continue
        observed_at = _parse_stored_timestamp(raw_timestamp)
        session_index = bisect_right(opens, observed_at) - 1
        if session_index < 0:
            continue
        session = sessions[session_index]
        close_at = session.close_at_utc
        assert close_at is not None
        if observed_at >= close_at:
            continue
        buckets[session.market_date].append(
            RthObservation(ticker=ticker, observed_at=observed_at)
        )

    return tuple(
        RthSessionObservations(
            market_date=market_date,
            observations=tuple(
                sorted(
                    buckets[market_date],
                    key=lambda observation: (
                        observation.observed_at,
                        observation.ticker,
                    ),
                )
            ),
        )
        for market_date in sorted(buckets)
    )


class RthObservationReader:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)

    def read(
        self,
        *,
        universe: Sequence[str],
        sessions: Sequence[CalendarDay],
        interval: str,
    ) -> ObservationReadResult:
        if not isinstance(interval, str):
            raise TypeError("interval must be a string")
        if not interval or interval != interval.strip():
            raise ValueError("interval must be a non-empty database interval")
        session_windows = _open_sessions(sessions)

        try:
            path_exists = self._db_path.exists()
            path_is_file = self._db_path.is_file()
        except OSError:
            return _unavailable(ObservationHealthReason.MARKET_DB_UNREADABLE)
        if not path_exists:
            return _unavailable(ObservationHealthReason.MARKET_DB_MISSING)
        if not path_is_file:
            return _unavailable(ObservationHealthReason.MARKET_DB_UNREADABLE)

        try:
            conn = _open_read_only_market_db(self._db_path)
        except (OSError, sqlite3.Error):
            return _unavailable(ObservationHealthReason.MARKET_DB_UNREADABLE)

        try:
            price_columns = _table_columns(conn, "prices")
            if (
                price_columns is None
                or not _REQUIRED_PRICE_COLUMNS <= price_columns
            ):
                return _unavailable(
                    ObservationHealthReason.PRICES_SCHEMA_MISSING
                )

            aliases = _load_aliases(conn)
            canonical_universe = _canonical_universe(universe, aliases)
            canonical_set = set(canonical_universe)
            provider_errors = _read_provider_errors(
                conn,
                interval=interval,
                aliases=aliases,
                canonical_universe=canonical_set,
            )
            observations = _read_session_observations(
                conn,
                sessions=session_windows,
                interval=interval,
                aliases=aliases,
                canonical_universe=canonical_universe,
            )
        except (sqlite3.Error, _StoredDatabaseError):
            return _unavailable(ObservationHealthReason.MARKET_DB_UNREADABLE)
        finally:
            conn.close()

        return ObservationReadResult(
            health=ObservationHealthAssessment(
                status=ObservationHealth.OK,
                reason_code=None,
            ),
            sessions=observations,
            provider_errors=provider_errors,
        )
