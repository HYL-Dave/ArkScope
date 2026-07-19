"""Complete, read-only active-universe snapshots from local SQLite state."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src import sa_capture_store


SOURCE_KEYS = (
    "manual_lists",
    "portfolio_open",
    "sa_alpha_picks_current",
    "legacy_config_seed",
)
EQUITY_ASSET_CLASSES = frozenset({"stock", "etf", "option"})
SA_STALE_AFTER_HOURS = 48

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_PROFILE_SOURCE_KEYS = tuple(
    key for key in SOURCE_KEYS if key != "sa_alpha_picks_current"
)
_ALLOWED_UNAVAILABLE_REASONS = frozenset(
    {"source_db_missing", "source_db_unreadable", "required_schema_missing"}
)
_PROFILE_REQUIRED_TABLES = {
    "manual_lists": frozenset(
        {"watchlist_memberships", "watchlists", "ticker_meta"}
    ),
    "portfolio_open": frozenset(
        {"portfolio_positions", "portfolio_accounts", "ticker_meta"}
    ),
    "legacy_config_seed": frozenset(
        {"universe_source_memberships", "ticker_meta"}
    ),
}
_SA_REQUIRED_TABLES = frozenset({"sa_alpha_picks", "sa_refresh_meta"})


@dataclass(frozen=True)
class SourceStatus:
    available: bool
    last_success_at: str | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActiveUniverseSnapshot:
    tickers: tuple[str, ...]
    sources_by_ticker: dict[str, tuple[str, ...]]
    source_status: dict[str, SourceStatus]
    unavailable_sources: tuple[str, ...]
    generated_at: str


class ActiveUniverseUnavailable(RuntimeError):
    code = "active_universe_unavailable"

    def __init__(self, source_reasons: Mapping[str, str]):
        normalized = {
            key: (
                source_reasons[key]
                if source_reasons[key] in _ALLOWED_UNAVAILABLE_REASONS
                else "source_db_unreadable"
            )
            for key in SOURCE_KEYS
            if key in source_reasons
        }
        self.source_reasons = normalized
        self.unavailable_sources = tuple(normalized)
        super().__init__(f"{self.code}: {','.join(self.unavailable_sources)}")

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "status": "unavailable",
            "unavailable_sources": list(self.unavailable_sources),
            "source_reasons": dict(self.source_reasons),
        }


class _RequiredSchemaMissing(Exception):
    def __init__(self, source_keys: tuple[str, ...]):
        self.source_keys = source_keys
        super().__init__("required schema missing")


def _open_read_only(path: str | Path) -> sqlite3.Connection:
    candidate = Path(path)
    if not candidate.is_file():
        raise FileNotFoundError
    conn = sqlite3.connect(f"{candidate.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only=ON")
    conn.execute("BEGIN")
    return conn


def _normalize_symbol(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().upper()


def _normalize_asset_class(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower()


def _utc_seconds(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).replace(microsecond=0)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {row["name"] for row in rows}


def _profile_missing_sources(conn: sqlite3.Connection) -> tuple[str, ...]:
    tables = _table_names(conn)
    return tuple(
        key
        for key in _PROFILE_SOURCE_KEYS
        if not _PROFILE_REQUIRED_TABLES[key].issubset(tables)
    )


def _normalized_row_symbols(
    rows: list[sqlite3.Row], column: str
) -> tuple[set[str], int]:
    symbols: set[str] = set()
    invalid_count = 0
    for row in rows:
        symbol = _normalize_symbol(row[column])
        if symbol:
            symbols.add(symbol)
        else:
            invalid_count += 1
    return symbols, invalid_count


def _count_warnings(**counts: int) -> tuple[str, ...]:
    return tuple(
        f"{key}={value}" for key, value in sorted(counts.items()) if value
    )


def _read_profile_sources(
    path: str | Path,
) -> tuple[dict[str, set[str]], set[str], dict[str, tuple[str, ...]]]:
    conn = _open_read_only(path)
    try:
        missing_sources = _profile_missing_sources(conn)
        if missing_sources:
            raise _RequiredSchemaMissing(missing_sources)

        manual_rows = conn.execute(
            """
            SELECT DISTINCT m.ticker
            FROM watchlist_memberships m
            JOIN watchlists w ON w.id = m.list_id
            WHERE m.archived_at IS NULL AND w.archived_at IS NULL
            """
        ).fetchall()
        portfolio_rows = conn.execute(
            """
            SELECT p.symbol, LOWER(TRIM(p.asset_class)) AS asset_class
            FROM portfolio_positions p
            JOIN portfolio_accounts a ON a.id = p.account_id
            WHERE p.closed_at IS NULL AND a.archived_at IS NULL
            """
        ).fetchall()
        legacy_rows = conn.execute(
            """
            SELECT ticker
            FROM universe_source_memberships
            WHERE source_key='legacy_config_seed' AND archived_at IS NULL
            """
        ).fetchall()
        hidden_rows = conn.execute(
            "SELECT ticker FROM ticker_meta WHERE hidden_at IS NOT NULL"
        ).fetchall()
    finally:
        conn.close()

    manual, manual_invalid = _normalized_row_symbols(manual_rows, "ticker")
    legacy, legacy_invalid = _normalized_row_symbols(legacy_rows, "ticker")
    hidden, _ = _normalized_row_symbols(hidden_rows, "ticker")

    portfolio: set[str] = set()
    portfolio_invalid = 0
    unsupported_asset_class_count = 0
    for row in portfolio_rows:
        symbol = _normalize_symbol(row["symbol"])
        if not symbol:
            portfolio_invalid += 1
            continue
        asset_class = _normalize_asset_class(row["asset_class"])
        if asset_class not in EQUITY_ASSET_CLASSES:
            unsupported_asset_class_count += 1
            continue
        portfolio.add(symbol)

    memberships = {
        "manual_lists": manual,
        "portfolio_open": portfolio,
        "legacy_config_seed": legacy,
    }
    warnings = {
        "manual_lists": _count_warnings(invalid_symbol_count=manual_invalid),
        "portfolio_open": _count_warnings(
            invalid_symbol_count=portfolio_invalid,
            unsupported_asset_class_count=unsupported_asset_class_count,
        ),
        "legacy_config_seed": _count_warnings(
            invalid_symbol_count=legacy_invalid
        ),
    }
    return memberships, hidden, warnings


def _read_sa_source(
    path: str | Path, *, now: datetime
) -> tuple[set[str], SourceStatus]:
    conn = _open_read_only(path)
    try:
        if not _SA_REQUIRED_TABLES.issubset(_table_names(conn)):
            raise _RequiredSchemaMissing(("sa_alpha_picks_current",))
        pick_rows = conn.execute(
            """
            SELECT DISTINCT symbol
            FROM sa_alpha_picks
            WHERE portfolio_status='current' AND is_stale=0
            """
        ).fetchall()
        refresh = conn.execute(
            """
            SELECT last_attempt_at, last_success_at, ok
            FROM sa_refresh_meta WHERE scope='current'
            """
        ).fetchone()
    finally:
        conn.close()

    symbols, invalid_count = _normalized_row_symbols(pick_rows, "symbol")
    warnings = list(_count_warnings(invalid_symbol_count=invalid_count))
    last_success_at: str | None = None
    if refresh is None:
        warnings.append("never_refreshed")
    else:
        raw_last_success = refresh["last_success_at"]
        if isinstance(raw_last_success, str) and raw_last_success.strip():
            last_success_at = raw_last_success
        if refresh["ok"] == 0:
            warnings.append("latest_refresh_failed")
        parsed_success = _parse_timestamp(last_success_at)
        if parsed_success is not None and now - parsed_success > timedelta(
            hours=SA_STALE_AFTER_HOURS
        ):
            warnings.append("stale_refresh")

    return symbols, SourceStatus(
        available=True,
        last_success_at=last_success_at,
        warnings=tuple(sorted(warnings)),
    )


def build_active_universe_snapshot(
    *,
    profile_db: str | Path | None = None,
    sa_db: str | Path | None = None,
    now: datetime | None = None,
) -> ActiveUniverseSnapshot:
    generated_at = _utc_seconds(now)
    profile_path = profile_db or os.environ.get("ARKSCOPE_PROFILE_DB") or (
        _PROJECT_ROOT / "data" / "profile_state.db"
    )
    sa_path = sa_db or sa_capture_store.resolve_sa_db_path()

    source_memberships: dict[str, set[str]] = {}
    source_status: dict[str, SourceStatus] = {}
    hidden: set[str] = set()
    source_reasons: dict[str, str] = {}
    causes: list[BaseException] = []

    try:
        profile_memberships, hidden, profile_warnings = _read_profile_sources(
            profile_path
        )
        source_memberships.update(profile_memberships)
        for key in _PROFILE_SOURCE_KEYS:
            source_status[key] = SourceStatus(
                available=True, warnings=profile_warnings[key]
            )
    except FileNotFoundError as exc:
        source_reasons.update(
            {key: "source_db_missing" for key in _PROFILE_SOURCE_KEYS}
        )
        causes.append(exc)
    except _RequiredSchemaMissing as exc:
        source_reasons.update(
            {key: "required_schema_missing" for key in exc.source_keys}
        )
        causes.append(exc)
    except sqlite3.DatabaseError as exc:
        source_reasons.update(
            {key: "source_db_unreadable" for key in _PROFILE_SOURCE_KEYS}
        )
        causes.append(exc)

    try:
        sa_symbols, sa_status = _read_sa_source(sa_path, now=generated_at)
        source_memberships["sa_alpha_picks_current"] = sa_symbols
        source_status["sa_alpha_picks_current"] = sa_status
    except FileNotFoundError as exc:
        source_reasons["sa_alpha_picks_current"] = "source_db_missing"
        causes.append(exc)
    except _RequiredSchemaMissing as exc:
        source_reasons.update(
            {key: "required_schema_missing" for key in exc.source_keys}
        )
        causes.append(exc)
    except sqlite3.DatabaseError as exc:
        source_reasons["sa_alpha_picks_current"] = "source_db_unreadable"
        causes.append(exc)

    if source_reasons:
        unavailable = ActiveUniverseUnavailable(source_reasons)
        if causes:
            raise unavailable from causes[0]
        raise unavailable

    sources_by_ticker_sets: dict[str, set[str]] = {}
    for source_key in SOURCE_KEYS:
        for ticker in source_memberships[source_key]:
            sources_by_ticker_sets.setdefault(ticker, set()).add(source_key)
    for ticker in hidden:
        sources_by_ticker_sets.pop(ticker, None)

    tickers = tuple(sorted(sources_by_ticker_sets))
    sources_by_ticker = {
        ticker: tuple(sorted(sources_by_ticker_sets[ticker])) for ticker in tickers
    }
    sorted_status = {key: source_status[key] for key in sorted(source_status)}
    return ActiveUniverseSnapshot(
        tickers=tickers,
        sources_by_ticker=sources_by_ticker,
        source_status=sorted_status,
        unavailable_sources=(),
        generated_at=generated_at.isoformat(timespec="seconds"),
    )
