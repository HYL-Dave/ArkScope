"""Independent, provider-free readback using an explicitly selected source tree."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

from src import active_universe
from src.market_coverage import service


TABLES = {
    "profile": {"watchlists", "watchlist_memberships", "portfolio_positions", "portfolio_accounts",
                "universe_source_memberships", "ticker_meta", "ticker_identity_links",
                "sa_tracking_memberships", "sa_tracking_bindings", "sa_tracking_events"},
    "sa": {"sa_alpha_picks", "sa_refresh_meta"},
    "market": {"prices", "ticker_aliases", "provider_sync_meta", "provider_sync_runs"},
}
METADATA = {"sqlite_master", "sqlite_schema", "sqlite_temp_master", "pragma_table_info"}


@contextmanager
def readonly_databases(paths):
    original = sqlite3.connect
    uris = {path.resolve().as_uri() + "?mode=ro": role for role, path in paths.items()}

    def connect(database, *args, **kwargs):
        if database not in uris or kwargs.get("uri") is not True:
            raise ValueError("readback_database_scope")
        conn = original(database, *args, **kwargs)
        conn.execute("PRAGMA query_only=ON")
        conn.execute("SELECT name FROM pragma_table_info('sqlite_master') LIMIT 0").fetchall()

        def authorize(action, table, column, db, trigger):
            allowed = action in {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_TRANSACTION}
            if action == sqlite3.SQLITE_READ:
                allowed = table in TABLES[uris[database]] | METADATA
            if action == sqlite3.SQLITE_PRAGMA:
                allowed = table in {"query_only", "table_info", "foreign_keys", "data_version"}
            return sqlite3.SQLITE_OK if allowed else sqlite3.SQLITE_DENY

        conn.set_authorizer(authorize)
        return conn

    sqlite3.connect = connect
    try:
        yield
    finally:
        sqlite3.connect = original


def no_network_or_process(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "subprocess.Popen", "os.system", "os.posix_spawn"}:
        raise ValueError("readback_external_operation_forbidden")


def main():
    parser = argparse.ArgumentParser()
    for name in ("code-root", "market", "profile", "sa"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--coverage-at", required=True)
    args = parser.parse_args()
    root = args.code_root.resolve()
    modules = (active_universe, service)
    if any(not Path(module.__file__).resolve().is_relative_to(root) for module in modules):
        raise ValueError("readback_wrong_source_tree")
    sys.addaudithook(no_network_or_process)
    with readonly_databases({name: getattr(args, name) for name in TABLES}):
        universe = active_universe.build_active_universe_snapshot(profile_db=args.profile, sa_db=args.sa)
        coverage = service.TradingDayCoverageService(
            db_path=args.market, clock=lambda: datetime.fromisoformat(args.coverage_at),
        ).get_coverage(universe=universe.tickers, lookback_days=15, interval="15min")
    result = {
        "observed_at": datetime.now(timezone.utc).isoformat(), "coverage_at": args.coverage_at,
        "source_hashes": {str(Path(module.__file__).resolve().relative_to(root)):
                          hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() for module in modules},
        "universe_count": coverage.universe_count,
        "calendar_health": coverage.calendar_health.status.value,
        "observation_health": coverage.observation_health.status.value,
        "missing_ticker_days": sum(len(row.missing_dates) for row in coverage.history_gaps),
        "partial_ticker_days": sum(len(row.partial_dates) for row in coverage.history_gaps),
        "unresolved_tickers": len(coverage.history_gaps),
        "days": [{"date": row.date, "complete": row.complete_ticker_count,
                  "partial": row.partial_ticker_count, "unknown": row.unknown_ticker_count} for row in coverage.days],
        "provider_requests": 0, "profile_writes": 0, "price_writes": 0,
    }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
