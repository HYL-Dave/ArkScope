from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
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
    ProviderSyncIssueReason,
    RthObservation,
    RthSessionObservations,
)


_REQUIRED_PRICE_COLUMNS = frozenset({"ticker", "datetime", "interval"})
_TICKER_ALIAS_COLUMNS = frozenset({"alias", "canonical"})
_PROVIDER_SYNC_COLUMNS = frozenset(
    {"ticker", "interval", "last_error", "updated_at"}
)
_STORED_UTC_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S+0000"


class _StoredDatabaseError(Exception):
    pass


@dataclass(frozen=True)
class _TickerAliasIndex:
    resolved_by_normalized: dict[str, str]
    raw_candidates_by_canonical: dict[str, frozenset[str]]

    def resolve(self, normalized_ticker: str) -> str:
        return self.resolved_by_normalized.get(
            normalized_ticker,
            normalized_ticker,
        )

    def candidates_for(self, canonical_tickers: set[str]) -> tuple[str, ...]:
        candidates = set(canonical_tickers)
        for canonical in canonical_tickers:
            candidates.update(
                self.raw_candidates_by_canonical.get(canonical, ())
            )
        return tuple(sorted(candidates))


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


def _unavailable(
    reason: ObservationHealthReason,
    *,
    canonical_universe: tuple[str, ...],
) -> ObservationReadResult:
    return ObservationReadResult(
        health=ObservationHealthAssessment(
            status=ObservationHealth.UNAVAILABLE,
            reason_code=reason,
        ),
        canonical_universe=canonical_universe,
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


def _load_aliases(conn: sqlite3.Connection) -> _TickerAliasIndex:
    columns = _table_columns(conn, "ticker_aliases")
    if columns is None:
        return _TickerAliasIndex({}, {})
    if not _TICKER_ALIAS_COLUMNS <= columns:
        raise _StoredDatabaseError("ticker_aliases schema is incompatible")

    direct_targets: dict[str, str] = {}
    raw_rows: list[tuple[str, str, str, str]] = []
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
        existing = direct_targets.get(alias)
        if existing is not None and existing != canonical:
            raise _StoredDatabaseError(
                f"normalized ticker alias collision: {alias}"
            )
        direct_targets[alias] = canonical
        assert isinstance(raw_alias, str)
        assert isinstance(raw_canonical, str)
        raw_rows.append((raw_alias, raw_canonical, alias, canonical))

    resolved: dict[str, str] = {}
    for start in sorted(set(direct_targets) | set(direct_targets.values())):
        if start in resolved:
            continue

        path: list[str] = []
        positions: dict[str, int] = {}
        current = start
        while current not in resolved:
            if current in positions:
                raise _StoredDatabaseError(
                    f"ticker alias cycle includes: {current}"
                )
            positions[current] = len(path)
            path.append(current)
            target = direct_targets.get(current)
            if target is None:
                break
            current = target

        final = resolved.get(current, current)
        for ticker in path:
            resolved[ticker] = final

    raw_candidates: dict[str, set[str]] = {}
    for raw_alias, raw_canonical, alias, canonical in raw_rows:
        final = resolved[alias]
        if resolved[canonical] != final:
            raise _StoredDatabaseError(
                f"ticker alias resolution conflict: {alias}"
            )
        raw_candidates.setdefault(final, set()).update(
            (raw_alias, raw_canonical, alias, canonical)
        )

    return _TickerAliasIndex(
        resolved_by_normalized=resolved,
        raw_candidates_by_canonical={
            canonical: frozenset(candidates)
            for canonical, candidates in raw_candidates.items()
        },
    )


def _canonical_universe(
    universe: Sequence[str],
    aliases: _TickerAliasIndex,
) -> tuple[str, ...]:
    if isinstance(universe, (str, bytes)):
        raise TypeError("universe must be a sequence of ticker strings")

    canonical: list[str] = []
    seen: set[str] = set()
    for raw_ticker in universe:
        ticker = _normalize_ticker(raw_ticker, field_name="universe ticker")
        ticker = aliases.resolve(ticker)
        if ticker not in seen:
            seen.add(ticker)
            canonical.append(ticker)
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
    try:
        parsed = datetime.strptime(value, _STORED_UTC_TIMESTAMP_FORMAT)
    except ValueError as exc:
        raise _StoredDatabaseError(
            f"invalid stored price datetime: {value!r}"
        ) from exc
    if parsed.strftime(_STORED_UTC_TIMESTAMP_FORMAT) != value:
        raise _StoredDatabaseError(
            f"non-canonical stored price datetime: {value!r}"
        )
    return parsed.replace(tzinfo=timezone.utc)


def _read_provider_errors(
    conn: sqlite3.Connection,
    *,
    interval: str,
    aliases: _TickerAliasIndex,
    canonical_universe: set[str],
) -> tuple[ProviderSyncIssue, ...]:
    columns = _table_columns(conn, "provider_sync_meta")
    if columns is None:
        return ()
    if not _PROVIDER_SYNC_COLUMNS <= columns:
        return ()

    stored_tickers = aliases.candidates_for(canonical_universe)
    if not stored_tickers:
        return ()
    placeholders = ", ".join("?" for _ in stored_tickers)
    issues: list[ProviderSyncIssue] = []
    for (
        ticker_type,
        ticker_blob,
        interval_type,
        interval_blob,
        error_type,
        error_blob,
        updated_at_type,
        updated_at_blob,
    ) in conn.execute(
        "SELECT typeof(ticker), CAST(ticker AS BLOB), "
        "typeof(interval), CAST(interval AS BLOB), "
        "typeof(last_error), CAST(last_error AS BLOB), "
        "typeof(updated_at), CAST(updated_at AS BLOB) "
        "FROM provider_sync_meta "
        f"WHERE ticker IN ({placeholders}) "
        "AND interval = ? AND last_error IS NOT NULL",
        (*stored_tickers, interval),
    ):
        try:
            if (
                ticker_type != "text"
                or interval_type != "text"
                or error_type != "text"
                or updated_at_type not in {"text", "null"}
                or not isinstance(ticker_blob, bytes)
                or not isinstance(interval_blob, bytes)
                or not isinstance(error_blob, bytes)
                or (
                    updated_at_type == "text"
                    and not isinstance(updated_at_blob, bytes)
                )
            ):
                continue
            raw_ticker = ticker_blob.decode("utf-8")
            raw_interval = interval_blob.decode("utf-8")
            raw_error = error_blob.decode("utf-8")
            raw_updated_at = (
                updated_at_blob.decode("utf-8")
                if updated_at_type == "text"
                else None
            )
            ticker = _normalize_stored_ticker(
                raw_ticker,
                field_name="provider issue ticker",
            )
        except (UnicodeDecodeError, _StoredDatabaseError):
            continue
        if not isinstance(raw_interval, str) or (
            not raw_interval
            or raw_interval != raw_interval.strip()
        ):
            continue
        if raw_error is not None and (
            not isinstance(raw_error, str)
            or not raw_error.strip()
        ):
            continue
        if raw_updated_at is not None and not isinstance(raw_updated_at, str):
            continue

        if raw_interval != interval or raw_error is None:
            continue
        ticker = aliases.resolve(ticker)
        if ticker not in canonical_universe:
            continue
        issues.append(
            ProviderSyncIssue(
                ticker=ticker,
                interval=raw_interval,
                last_error=raw_error,
                reason_code={
                    "security_definition_unavailable": (
                        ProviderSyncIssueReason.SECURITY_DEFINITION_UNAVAILABLE
                    ),
                    "price_day_unresolved_after_fetch": (
                        ProviderSyncIssueReason.PRICE_DATA_UNRESOLVED
                    ),
                    "ibkr_historical_data_request_failed": (
                        ProviderSyncIssueReason.PROVIDER_REQUEST_FAILED
                    ),
                }.get(raw_error, ProviderSyncIssueReason.UNKNOWN),
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
    aliases: _TickerAliasIndex,
    canonical_universe: tuple[str, ...],
) -> tuple[RthSessionObservations, ...]:
    buckets: dict[date, list[RthObservation]] = {
        session.market_date: [] for session in sessions
    }
    if not sessions:
        return ()
    if not canonical_universe:
        return tuple(
            RthSessionObservations(market_date=market_date, observations=())
            for market_date in sorted(buckets)
        )

    canonical_set = set(canonical_universe)
    stored_tickers = aliases.candidates_for(canonical_set)
    placeholders = ", ".join("?" for _ in stored_tickers)
    earliest_open = sessions[0].open_at_utc
    latest_close = sessions[-1].close_at_utc
    assert earliest_open is not None
    assert latest_close is not None
    lower_bound = earliest_open.strftime(_STORED_UTC_TIMESTAMP_FORMAT)
    upper_bound = latest_close.strftime(_STORED_UTC_TIMESTAMP_FORMAT)
    query = (
        "SELECT ticker, datetime FROM prices "
        f"WHERE ticker IN ({placeholders}) AND interval = ? "
        "AND datetime >= ? AND datetime < ?"
    )
    parameters = (
        *stored_tickers,
        interval,
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
        ticker = aliases.resolve(ticker)
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
        requested_universe = _canonical_universe(
            universe,
            _TickerAliasIndex({}, {}),
        )
        session_windows = _open_sessions(sessions)

        try:
            path_exists = self._db_path.exists()
            path_is_file = self._db_path.is_file()
        except OSError:
            return _unavailable(
                ObservationHealthReason.MARKET_DB_UNREADABLE,
                canonical_universe=requested_universe,
            )
        if not path_exists:
            return _unavailable(
                ObservationHealthReason.MARKET_DB_MISSING,
                canonical_universe=requested_universe,
            )
        if not path_is_file:
            return _unavailable(
                ObservationHealthReason.MARKET_DB_UNREADABLE,
                canonical_universe=requested_universe,
            )

        try:
            conn = _open_read_only_market_db(self._db_path)
        except (OSError, sqlite3.Error):
            return _unavailable(
                ObservationHealthReason.MARKET_DB_UNREADABLE,
                canonical_universe=requested_universe,
            )

        try:
            price_columns = _table_columns(conn, "prices")
            if (
                price_columns is None
                or not _REQUIRED_PRICE_COLUMNS <= price_columns
            ):
                return _unavailable(
                    ObservationHealthReason.PRICES_SCHEMA_MISSING,
                    canonical_universe=requested_universe,
                )

            if not requested_universe:
                return ObservationReadResult(
                    health=ObservationHealthAssessment(
                        status=ObservationHealth.OK,
                        reason_code=None,
                    ),
                    canonical_universe=(),
                    sessions=tuple(
                        RthSessionObservations(
                            market_date=session.market_date,
                            observations=(),
                        )
                        for session in session_windows
                    ),
                    provider_errors=(),
                )

            aliases = _load_aliases(conn)
            canonical_universe = _canonical_universe(requested_universe, aliases)
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
            return _unavailable(
                ObservationHealthReason.MARKET_DB_UNREADABLE,
                canonical_universe=requested_universe,
            )
        finally:
            conn.close()

        return ObservationReadResult(
            health=ObservationHealthAssessment(
                status=ObservationHealth.OK,
                reason_code=None,
            ),
            canonical_universe=canonical_universe,
            sessions=observations,
            provider_errors=provider_errors,
        )
