"""Scoped production reads and simulated IBKR accounting; no execution authority."""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import sqlite3
import sys


TARGETS = ("ARCH", "LTHM", "TA")
ROOT = Path(__file__).resolve().parents[5]
SCOPES = {
    "profile": {
        "watchlists": {"id", "name", "archived_at"},
        "watchlist_memberships": {"list_id", "ticker", "position", "archived_at"},
        "portfolio_positions": {"symbol", "asset_class", "closed_at", "account_id"},
        "portfolio_accounts": {"id", "archived_at"},
        "universe_source_memberships": {"source_key", "ticker", "archived_at"},
        "ticker_meta": {"ticker", "hidden_at"},
        "ticker_identity_links": {"source_ticker", "successor_ticker", "reversed_at"},
        "ticker_identity_transitions": {"source_ticker", "successor_ticker", "status", "kind", "execute_on"},
        "sa_tracking_memberships": {"membership_id", "ticker", "picked_date", "portfolio_status", "accepted_at", "removed_at",
                                    "current_tracking", "reason", "created_at", "updated_at"},
        "sa_tracking_bindings": {"lineage_id", "membership_id", "ticker", "picked_date", "observation_sha256", "observed_at"},
        "sa_tracking_events": {"membership_id", "action", "occurred_at"},
        "security_lifecycle_provider_checks": {"check_id", "ticker", "observed_at", "observation_json", "evidence_json",
                                                "diagnostics_json", "blockers_json", "state", "content_sha256", "created_at", "ROWID"},
    },
    "sa": {
        "sa_alpha_picks": {"lineage_id", "symbol", "picked_date", "portfolio_status", "is_stale",
                           "last_seen_snapshot", "updated_at", "fetched_at"},
        "sa_refresh_meta": {"scope", "last_attempt_at", "last_success_at", "ok"},
    },
    "market": {
        "prices": {"ticker", "datetime", "interval"},
        "ticker_aliases": {"alias", "canonical"},
        "provider_sync_meta": {"ticker", "interval", "last_error", "updated_at"},
    },
}
_FUNCTIONS = {"abs", "coalesce", "count", "length", "lower", "max", "min", "substr", "sum", "trim", "typeof", "upper"}
_METADATA = {"sqlite_master", "sqlite_schema", "sqlite_temp_master", "pragma_table_info"}


class InventoryStopped(RuntimeError):
    pass


def require(condition, code):
    if not condition:
        raise InventoryStopped(code)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def readonly_uris(paths):
    return {path.resolve().as_uri() + "?mode=ro": role for role, path in paths.items()}


def audit_for(paths):
    uris = readonly_uris(paths)
    raw_paths = {path.resolve() for path in paths.values()}

    def audit(event, args):
        if event in {"socket.connect", "socket.getaddrinfo", "subprocess.Popen", "os.system", "os.posix_spawn"}:
            raise InventoryStopped("inventory_external_execution_forbidden")
        if event == "sqlite3.connect":
            require(os.fsdecode(args[0]) in uris, "inventory_connection_scope")
        if event == "open" and isinstance(args[0], (str, bytes)):
            path = Path(os.fsdecode(args[0]))
            require(not path.name.startswith(".env") and path.name not in {"auth.json", "credentials.json"},
                    "inventory_ambient_auth_forbidden")
            require(path.resolve() not in raw_paths, "inventory_raw_database_read_forbidden")
    return audit


class ReadScope:
    def __init__(self):
        self.accessed = set()
        self.denials = []

    def authorizer(self, role):
        tables = SCOPES[role]

        def authorize(action, first, second, database, source):
            permitted = False
            if action == sqlite3.SQLITE_READ:
                permitted = first in _METADATA or (first in tables and (
                    not second or second in tables[first]))
                if permitted:
                    self.accessed.add((role, first, second or ""))
            elif action == sqlite3.SQLITE_SELECT:
                permitted = True
            elif action == sqlite3.SQLITE_TRANSACTION:
                permitted = first in {"BEGIN", "COMMIT", "ROLLBACK"}
            elif action == sqlite3.SQLITE_FUNCTION:
                permitted = second in _FUNCTIONS
            elif action == sqlite3.SQLITE_PRAGMA:
                permitted = (
                    first in {"query_only", "foreign_keys"} and second in {None, "ON", "1"}
                    or first == "data_version" and second is None
                    or first == "table_info" and second in tables
                )
            if not permitted:
                self.denials.append({"database": role, "action": action, "object": first, "field": second})
            return sqlite3.SQLITE_OK if permitted else sqlite3.SQLITE_DENY
        return authorize


@contextmanager
def guarded_connections(paths):
    original = sqlite3.connect
    uris = readonly_uris(paths)
    scope = ReadScope()

    def connect(database, *args, **kwargs):
        uri = os.fsdecode(database)
        require(uri in uris and kwargs.get("uri") is True, "inventory_connection_scope")
        conn = original(database, *args, **kwargs)
        conn.execute("PRAGMA query_only=ON")
        # Initialize SQLite's read-only schema wrapper before its transient
        # virtual-table registration can be mistaken for a persistent write.
        conn.execute("SELECT name FROM pragma_table_info('sqlite_master') LIMIT 0").fetchall()
        conn.set_authorizer(scope.authorizer(uris[uri]))
        return conn

    sqlite3.connect = connect
    try:
        yield scope
    finally:
        sqlite3.connect = original


def data_versions(connections):
    return {role: conn.execute("PRAGMA data_version").fetchone()[0] for role, conn in connections.items()}


def require_stable(before, after):
    require(before == after, "inventory_inputs_changed")


def file_identities(paths):
    return {role: (path.stat().st_dev, path.stat().st_ino) for role, path in paths.items()}


def target_inventory(conn, ticker, sources, *, now):
    from src.sa_tracking_memberships import terminal_tracking_memberships
    from src.security_lifecycle_provider_authority import classify_provider_listing
    from src.security_lifecycle_provider_store import ProviderCheckStore
    from src.ticker_identity_transition import _legacy_effects, _watchlist_effects

    check = ProviderCheckStore.latest_for_connection(conn, ticker)
    require(check is not None, "inventory_target_evidence_absent")
    result = classify_provider_listing(ticker=ticker, evidence=check["evidence"], today=now.date(), provider_codes=check["blockers"])
    open_position = bool(conn.execute(
        "SELECT EXISTS(SELECT 1 FROM portfolio_positions p JOIN portfolio_accounts a ON a.id=p.account_id "
        "WHERE UPPER(TRIM(p.symbol))=? AND p.closed_at IS NULL AND a.archived_at IS NULL "
        "AND LOWER(TRIM(p.asset_class)) IN ('stock','etf','option'))", (ticker,)).fetchone()[0])
    effects = {
        "watchlists": _watchlist_effects(conn, source_ticker=ticker, successor_ticker=None),
        "legacy_config_seed": _legacy_effects(conn, source_ticker=ticker, successor_ticker=None),
        "sa_tracking_memberships": terminal_tracking_memberships(conn, ticker),
    }
    hidden = bool(conn.execute("SELECT 1 FROM ticker_meta WHERE ticker=? AND hidden_at IS NOT NULL", (ticker,)).fetchone())
    transitions = conn.execute("SELECT kind,status,execute_on FROM ticker_identity_transitions WHERE source_ticker=? ORDER BY execute_on,status", (ticker,)).fetchall()
    active_transition = any(row[1] in {"approved", "needs_review", "applied"} for row in transitions)
    summary = {
        "ticker": ticker, "tracked": ticker in sources, "sources": list(sources.get(ticker, ())),
        "listing_state": result.listing_state, "listing_end_date": result.listing_end_date,
        "listing_reasons": list(result.listing_reasons), "continuation_state": result.continuation_state,
        "continuation_reasons": list(result.continuation_reasons), "candidate_tickers": list(result.candidate_tickers),
        "stored_state": check["state"], "provider_codes": check["blockers"], "observed_at": check["at"],
        "provider_check_sha256": check["digest"], "evidence_records": len(check["evidence"]),
        "evidence_observed_at": sorted({row["retrieved_at"] for row in check["evidence"]}),
        "evidence_sources": sorted({row["adapter"] for row in check["evidence"]}),
        "open_position": open_position, "already_hidden": hidden,
        "watchlist_archives": len(effects["watchlists"]["archive"]),
        "legacy_archives": len(effects["legacy_config_seed"]["archive"]),
        "sa_memberships_to_suppress": len(effects["sa_tracking_memberships"]),
        "sa_current_sources_to_stop": sum(row["current_tracking"] for row in effects["sa_tracking_memberships"]),
        "existing_transitions": [dict(zip(("kind", "status", "execute_on"), row)) for row in transitions],
        "ready_for_new_attended_preview": result.listing_state == "inactive" and not open_position
            and not active_transition and ticker in sources,
        "application_authorized": False,
    }
    private = {"ticker": ticker, "effects": effects, "hide_source_if_approved": not hidden and not open_position,
               "no_alias": True, "input_sha256": digest({"check": check["digest"], "effects": effects,
                   "sources": sources.get(ticker, ()), "open_position": open_position, "hidden": hidden, "transitions": transitions})}
    return summary, private


def simulate_requests(plan, *, now):
    from data_sources.ibkr_source import IBKRDataSource
    from src.market_data_direct import _fetch_rows_for_gaps
    from src.market_sessions import complete_trading_days, normalize_now_et

    require(plan["provider"] == "ibkr" and plan["fallback_allowed"] is False and plan["interval"] == "15min",
            "inventory_repair_provider_scope")
    now_et = normalize_now_et(now)
    end = date.fromisoformat(plan["as_of_date"])
    days = complete_trading_days(end - timedelta(days=plan["lookback_days"]), end, now_et)
    qualifications, chunks = [], []

    class Bridge:
        def disconnect(self):
            pass

        def qualifyContracts(self, contract):
            qualifications.append(contract.symbol)
            return [contract]

        def reqHistoricalData(self, contract, **kwargs):
            require(kwargs["barSizeSetting"] == "15 mins" and kwargs["whatToShow"] == "TRADES"
                    and kwargs["useRTH"] is True and kwargs["formatDate"] == 1, "inventory_unexpected_request_shape")
            chunk_end = datetime.strptime(kwargs["endDateTime"].split(" ")[0], "%Y%m%d").date()
            duration = int(kwargs["durationStr"].removesuffix(" D"))
            chunks.append({"ticker": contract.symbol, "start": (chunk_end - timedelta(days=duration - 1)).isoformat(),
                           "end": chunk_end.isoformat(), "calendar_days": duration, "interval": kwargs["barSizeSetting"],
                           "rth_only": kwargs["useRTH"]})
            return []

    # Run the actual fetch/chunk implementation, replacing only external effects.
    source = object.__new__(IBKRDataSource)
    source._ib = Bridge()
    source._ensure_connected = lambda: None
    source._rate_limit_wait = lambda: None
    for ticker in plan["tickers"]:
        if days:
            _fetch_rows_for_gaps(ticker, days, plan["interval"], "ibkr", source, None)
    require(len(qualifications) == len(chunks), "inventory_request_count_mismatch")
    return {
        "observed_provider_requests": 0, "simulation_only": True,
        "fetch_start": min(days).isoformat() if days else None, "fetch_end": max(days).isoformat() if days else None,
        "completed_session_dates": [day.isoformat() for day in days],
        "qualification_requests": len(qualifications), "historical_requests": len(chunks),
        "total_data_requests": len(qualifications) + len(chunks), "chunks": chunks,
        "retry": False, "fallback": False, "quotes": 0,
        "gateway_connection_traffic_in_data_request_count": False,
        "current_chunk_delay_s": IBKRDataSource.REQUEST_DELAY,
    }


def coverage_inventory(path, universe, *, now, lookback):
    from src.market_coverage.repair import preview_price_repair
    from src.market_coverage.service import TradingDayCoverageService

    coverage = TradingDayCoverageService(db_path=path, clock=lambda: now).get_coverage(
        universe=universe, lookback_days=lookback, interval="15min")
    plan = preview_price_repair(coverage)
    simulated = simulate_requests(plan, now=now)
    gap_dates = {day for row in plan["gaps"] for key in ("missing_dates", "partial_dates") for day in row[key]}
    require(gap_dates <= set(simulated["completed_session_dates"]), "inventory_coverage_worker_calendar_disagreement")
    summary = {
        "lookback_days": lookback, "as_of_date": plan["as_of_date"], "universe_count": coverage.universe_count,
        "calendar_health": coverage.calendar_health.status, "observation_health": coverage.observation_health.status,
        "repair_tickers": len(plan["tickers"]), "blocked_tickers": plan["blocked_tickers"],
        "missing_ticker_days": sum(len(row.missing_dates) for row in coverage.history_gaps),
        "partial_ticker_days": sum(len(row.partial_dates) for row in coverage.history_gaps),
        "gap_reason_counts": dict(sorted(Counter(row.reason for row in coverage.history_gaps).items())),
        "provider_issue_reason_counts": dict(sorted(Counter(row.reason_code for row in coverage.provider_errors).items())),
        "preview_sha256": plan["preview_sha256"],
        "qualification_requests": simulated["qualification_requests"], "historical_requests": simulated["historical_requests"],
        "total_data_requests": simulated["total_data_requests"],
        "fetch_start": simulated["fetch_start"], "fetch_end": simulated["fetch_end"],
    }
    private = {"preview": plan, "budget_simulation": simulated,
               "history_gaps": [row.model_dump(mode="json") for row in coverage.history_gaps],
               "provider_issues": [{"ticker": row.ticker, "reason": row.reason_code, "updated_at": row.updated_at} for row in coverage.provider_errors],
               "days": [row.model_dump(mode="json") for row in coverage.days]}
    return summary, private


def collect(paths, *, now):
    from src.active_universe import build_active_universe_snapshot
    from src.sa_tracking_memberships import SaTrackingMembershipStore, read_sa_tracking_observations

    monitors = {role: sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) for role, path in paths.items()}
    try:
        identities = file_identities(paths)
        before = data_versions(monitors)
        sources = build_active_universe_snapshot(profile_db=paths["profile"], sa_db=paths["sa"], now=now)
        observations = read_sa_tracking_observations(paths["sa"])
        sync = SaTrackingMembershipStore(paths["profile"]).synchronization_status(observations)
        targets, effects = [], []
        for ticker in TARGETS:
            summary, private = target_inventory(monitors["profile"], ticker, sources.sources_by_ticker, now=now)
            targets.append(summary)
            effects.append(private)
        eligible = [row["ticker"] for row in targets if row["ready_for_new_attended_preview"]]
        post = tuple(ticker for ticker in sources.tickers if ticker not in eligible)
        pre_coverage, details = {}, {}
        # The current display and the hypothetical target-only removal are distinct.
        for label, universe in (("current", sources.tickers), ("hypothetical_after_approved_removal", post)):
            for lookback in (5, 15, 120):
                summary, private = coverage_inventory(paths["market"], universe, now=now, lookback=lookback)
                key = f"{label}_{lookback}"
                pre_coverage[key], details[key] = summary, private
        after = data_versions(monitors)
        require_stable(before, after)
        require_stable(identities, file_identities(paths))
        summary = {
            "at": now.isoformat(timespec="seconds"), "status": "readonly_inventory_complete_no_execution",
            "provider_requests": 0, "production_writes": 0, "production_backup_created": False,
            "credential_fields_read": False, "stable_read_interval": True,
            "universe_before": len(sources.tickers), "hypothetical_universe_after": len(post),
            "hypothetical_removed_targets": eligible,
            "source_counts": dict(sorted(Counter(source for row in sources.sources_by_ticker.values() for source in row).items())),
            "universe_sha256": digest(sources.sources_by_ticker),
            "unchanged_other_sources_sha256": digest({ticker: values for ticker, values in sources.sources_by_ticker.items() if ticker not in eligible}),
            "sa_sync_status": sync, "sa_observed_lineages": len(observations), "sa_observations_sha256": digest(observations),
            "source_status": {key: asdict(value) for key, value in sources.source_status.items()},
            "targets": targets, "coverage": pre_coverage,
            "effects_sha256": digest(effects), "price_requests_authorized": False,
        }
        private = {"sources_by_ticker": sources.sources_by_ticker, "hypothetical_universe": post,
                   "target_effects": effects, "coverage": details}
        return summary, private
    finally:
        for conn in monitors.values():
            conn.close()


def private_write(directory, name, value):
    descriptor = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(encoded(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser()
    for role in SCOPES:
        parser.add_argument("--" + role, type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = {role: getattr(args, role).resolve(strict=True) for role in SCOPES}
    require(len(set(paths.values())) == 3, "inventory_database_roles_overlap")
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    sys.addaudithook(audit_for(paths))
    logging.disable(logging.CRITICAL)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    guard = None
    try:
        with guarded_connections(paths) as guard:
            summary, private = collect(paths, now=now)
        require(not guard.denials, "inventory_read_scope_denied")
        private["read_columns"] = sorted(guard.accessed)
        private_write(args.output, "private-inventory.json", private)
        source_files = ["src/market_data_direct.py", "data_sources/ibkr_source.py", "src/market_sessions.py",
                        "src/market_coverage/service.py", "src/market_coverage/observations.py", "src/market_coverage/repair.py",
                        "src/security_lifecycle_provider_authority.py", "src/security_lifecycle_provider_store.py",
                        "src/security_lifecycle_provider_snapshot.py", "src/active_universe.py", "src/sa_tracking_memberships.py",
                        "src/ticker_identity_transition.py"]
        summary["source_files_sha256"] = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in source_files}
        summary["runner_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        summary["completed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        summary["read_columns_sha256"] = digest(sorted(guard.accessed))
        private_write(args.output, "summary.json", summary)
        print(json.dumps(summary, sort_keys=True))
    except Exception as exc:
        error = {"status": "stopped", "code": str(exc) if isinstance(exc, InventoryStopped) else "inventory_failed",
                 "exception_type": type(exc).__name__, "denials": guard.denials if guard is not None else []}
        private_write(args.output, "stopped.json", error)
        print(json.dumps(error, sort_keys=True))
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
