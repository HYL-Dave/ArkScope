"""Attended execution of the already approved recent-price manifest."""

import argparse
from collections import Counter
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import logging
import os
from pathlib import Path
import sqlite3
import sys

from data_sources.ibkr_client_id import DOMAIN_OFFSETS
from data_sources.ibkr_source import IBKRDataSource
from src.active_universe import build_active_universe_snapshot
from src import market_data_direct as writer
from src.market_coverage.service import TradingDayCoverageService
from src.price_repair_execution import (
    RepairJournal, execute_price_repair, repair_directory, validate_repair_plan,
)


APPROVED_PLAN = "907a6f80ff8593db7134203d9807b06fee1692d9c2b7e96b84b6a5676c9289e5"
ROOT = Path(__file__).resolve().parents[5]
_CONNECT = sqlite3.connect
_METADATA = {"sqlite_master", "sqlite_schema", "sqlite_temp_master", "pragma_table_info"}
_PROFILE_TABLES = {
    "watchlists", "watchlist_memberships", "portfolio_positions", "portfolio_accounts",
    "universe_source_memberships", "ticker_meta", "ticker_identity_links",
    "sa_tracking_memberships", "sa_tracking_bindings", "sa_tracking_events",
}
_SA_TABLES = {"sa_alpha_picks", "sa_refresh_meta"}
_MARKET_TABLES = {"prices", "ticker_aliases", "provider_sync_meta", "provider_sync_runs"}


class Stopped(RuntimeError):
    pass


def require(condition, code):
    if not condition:
        raise Stopped(code)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def private_write(path, value):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(encoded(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def readonly(path):
    conn = _CONNECT(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")
    return conn


def approved_slots(plan):
    return {(row["ticker"], slot, "15min") for row in plan["preview"]["gaps"]
            for day in row["missing_dates"] + row["partial_dates"] for slot in plan["slots"][day]}


def admit(plan, expected=APPROVED_PLAN):
    validate_repair_plan(plan)
    require(plan["plan_sha256"] == expected, "live_plan_not_approved")
    require(plan["request_budget"]["total"] <= 64 and len(approved_slots(plan)) <= 4940,
            "live_budget_not_approved")
    require(all("2026-08-21" <= day <= "2026-08-28" for day in plan["slots"]), "live_dates_not_approved")


def settings(profile):
    with closing(readonly(profile)) as conn:
        def authorize(action, table, column, database, trigger):
            if action == sqlite3.SQLITE_READ:
                return sqlite3.SQLITE_OK if table == "data_provider_config" and column in {"provider", "field", "value"} else sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK if action == sqlite3.SQLITE_SELECT else sqlite3.SQLITE_DENY
        conn.set_authorizer(authorize)
        rows = conn.execute("SELECT field,value FROM data_provider_config WHERE provider='ibkr' AND field IN ('host','port','client_id')").fetchall()
    values = dict(rows)
    require(set(values) == {"host", "port", "client_id"} and len(rows) == 3, "live_ibkr_settings_incomplete")
    try:
        host = str(ipaddress.ip_address(values["host"]))
        port, base = int(values["port"]), int(values["client_id"])
        require(1 <= port <= 65535 and 0 <= base <= 19, "live_ibkr_settings_invalid")
    except (TypeError, ValueError):
        raise Stopped("live_ibkr_settings_invalid") from None
    return {"host": host, "port": port, "client_id": base + DOMAIN_OFFSETS["prices"], "readonly": True, "timeout": 15}


def backup(market, destination):
    fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    with closing(readonly(market)) as source, closing(_CONNECT(destination)) as target:
        source.execute("BEGIN")
        source.execute("SELECT count(*) FROM sqlite_master").fetchone()
        source.backup(target, pages=1024)
        require(target.execute("PRAGMA quick_check").fetchall() == [("ok",)], "live_backup_invalid")
    sha = hashlib.sha256()
    with open(destination, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
    return {"sha256": sha.hexdigest(), "bytes": Path(destination).stat().st_size, "quick_check": "ok"}


def read_rows(path, tickers):
    with closing(readonly(path)) as conn:
        return [tuple(row) for row in conn.execute(
            "SELECT ticker,datetime,interval,open,high,low,close,volume FROM prices "
            "WHERE ticker IN (" + ",".join("?" for _ in tickers) + ") AND interval='15min' ORDER BY ticker,datetime", tickers)]


def coverage_summary(value):
    return {
        "universe_count": value.universe_count,
        "calendar_health": value.calendar_health.status.value,
        "observation_health": value.observation_health.status.value,
        "missing_ticker_days": sum(len(row.missing_dates) for row in value.history_gaps),
        "partial_ticker_days": sum(len(row.partial_dates) for row in value.history_gaps),
        "unresolved_tickers": len(value.history_gaps),
        "days": [{"date": row.date, "complete": row.complete_ticker_count,
                  "partial": row.partial_ticker_count, "unknown": row.unknown_ticker_count} for row in value.days],
    }


@contextmanager
def guarded_connections(paths, journal, slots, metrics):
    original = sqlite3.connect
    ro = {path.resolve().as_uri() + "?mode=ro": role for role, path in paths.items()}
    write_uri = paths["market"].resolve().as_uri() + "?mode=rw"
    tables = {"profile": _PROFILE_TABLES, "sa": _SA_TABLES, "market": _MARKET_TABLES}

    class PriceConnection(sqlite3.Connection):
        insert_authorized = False

        def executemany(self, sql, rows):
            rows = list(rows)
            require(sql == writer._PRICE_INSERT, "live_write_statement_scope")
            require(all(tuple(row[:3]) in slots for row in rows), "live_write_row_scope")
            self.insert_authorized = True
            before = self.total_changes
            try:
                return super().executemany(sql, rows)
            finally:
                self.insert_authorized = False
                metrics["inserted_on_guarded_connections"] += self.total_changes - before

    def authorize(role, conn, writable):
        def check(action, table, column, database, trigger):
            allowed = action in {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_TRANSACTION}
            if action == sqlite3.SQLITE_READ:
                allowed = table in _METADATA or table in tables[role]
            if action == sqlite3.SQLITE_PRAGMA:
                allowed = table in {"query_only", "table_info", "foreign_keys", "data_version"}
            if action == sqlite3.SQLITE_INSERT:
                allowed = writable and table == "prices" and conn.insert_authorized and trigger is None
            if not allowed:
                metrics["sqlite_denials"] += 1
            return sqlite3.SQLITE_OK if allowed else sqlite3.SQLITE_DENY
        return check

    def connect(database, *args, **kwargs):
        name = os.fsdecode(database)
        if Path(name) == journal:
            return original(database, *args, **kwargs)
        writable = name == write_uri
        require((name in ro or writable) and kwargs.get("uri") is True, "live_database_scope")
        kwargs["cached_statements"] = 0
        if writable:
            kwargs["factory"] = PriceConnection
        conn = original(database, *args, **kwargs)
        if not writable:
            conn.execute("PRAGMA query_only=ON")
        conn.execute("SELECT name FROM pragma_table_info('sqlite_master') LIMIT 0").fetchall()
        conn.set_authorizer(authorize("market" if writable else ro[name], conn, writable))
        return conn

    sqlite3.connect = connect
    try:
        yield
    finally:
        sqlite3.connect = original


class MeteredSource(IBKRDataSource):
    def __init__(self, config, metrics, progress):
        super().__init__(**config)
        self.metrics = metrics
        self.progress = progress

    def connect(self):
        require(self.metrics["connection_attempts"] == 0, "live_second_connection_forbidden")
        self.metrics["connection_attempts"] += 1
        if not super().connect():
            return False
        for name, kind in (("qualifyContracts", "qualification"), ("reqHistoricalData", "history")):
            operation = getattr(self._ib, name)
            def metered(*args, _operation=operation, _kind=kind, **kwargs):
                self.metrics["actual_data_calls"][_kind] += 1
                self.progress({"phase": "dispatch", "kind": _kind, "calls": dict(self.metrics["actual_data_calls"])})
                return _operation(*args, **kwargs)
            setattr(self._ib, name, metered)
        return True

    def _on_ib_error(self, reqId, errorCode, errorString, contract):
        self.metrics["ibkr_codes"][str(errorCode)] += 1


def network_guard(config, metrics):
    def audit(event, args):
        if event in {"subprocess.Popen", "os.system", "os.posix_spawn"}:
            raise Stopped("live_subprocess_forbidden")
        if event == "socket.getaddrinfo":
            require(args[0] == config["host"] and args[1] == config["port"], "live_network_scope")
        if event == "socket.connect":
            address = args[1]
            require(isinstance(address, tuple) and address[:2] == (config["host"], config["port"]), "live_network_scope")
            metrics["socket_connection_attempts"] += 1
        if event == "open" and isinstance(args[0], (str, bytes)):
            name = Path(os.fsdecode(args[0])).name
            require(not name.startswith(".env") and name not in {"auth.json", "credentials.json"}, "live_ambient_secret_forbidden")
    return audit


def execute(args, *, expected=APPROVED_PLAN):
    started = datetime.now(timezone.utc).isoformat()
    plan = json.loads(args.plan.read_text())
    admit(plan, expected)
    paths = {"market": Path(plan["market_db"]), "profile": args.profile.resolve(), "sa": args.sa.resolve()}
    require(all(path.is_file() for path in paths.values()), "live_database_missing")
    config = settings(paths["profile"])
    args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
    journal_dir = repair_directory(paths["market"], args.repair_id)
    require(not journal_dir.exists(), "live_operation_already_exists")
    metrics = {"connection_attempts": 0, "socket_connection_attempts": 0,
               "actual_data_calls": Counter(), "ibkr_codes": Counter(),
               "inserted_on_guarded_connections": 0, "sqlite_denials": 0}
    progress = lambda event: print(json.dumps(event, sort_keys=True), flush=True)
    anchor = datetime.fromisoformat(plan["coverage_at"])
    service = TradingDayCoverageService(db_path=paths["market"], clock=lambda: anchor)
    active = lambda: build_active_universe_snapshot(profile_db=paths["profile"], sa_db=paths["sa"])
    tickers = plan["preview"]["tickers"]
    slots = approved_slots(plan)
    journal_path = journal_dir / "requests.sqlite3"
    with guarded_connections(paths, journal_path, slots, metrics):
        before_universe = active()
        require(set(tickers) <= set(before_universe.tickers), "live_target_no_longer_active")
        before = service.get_coverage(universe=before_universe.tickers, lookback_days=15, interval="15min")
        require(before.calendar_health.status.value == before.observation_health.status.value == "ok", "live_coverage_unavailable")
    progress({"phase": "backup", "provider_calls": 0})
    backup_result = backup(paths["market"], args.output / "market.before.db")
    before_rows = read_rows(args.output / "market.before.db", tickers)
    private_write(args.output / "preflight.json", {
        "started_at": started, "plan_sha256": plan["plan_sha256"], "repair_id": args.repair_id,
        "backup": backup_result, "before_coverage": coverage_summary(before),
        "target_rows_sha256": digest(before_rows), "universe_count": len(before_universe.tickers),
        "settings_source": "profile_db_ibkr_only", "gateway_readonly": True,
        "settings_sha256": digest(config),
    })
    require(settings(paths["profile"]) == config, "live_gateway_settings_changed")
    logging.disable(logging.CRITICAL)
    sys.addaudithook(network_guard(config, metrics))
    source = MeteredSource(config, metrics, progress)
    error = None
    result = None
    try:
        with guarded_connections(paths, journal_path, slots, metrics):
            result = execute_price_repair(plan, journal_dir, source=source, active_scope=lambda: active().tickers)
    except Exception as exc:
        error = {"class": type(exc).__name__, "code": getattr(exc, "error_code", str(exc) if isinstance(exc, Stopped) else None)}
    finally:
        source.disconnect()
    with guarded_connections(paths, journal_path, slots, metrics):
        after_universe = active()
        after = service.get_coverage(universe=after_universe.tickers, lookback_days=15, interval="15min")
        journal = RepairJournal(journal_dir, plan)
        try:
            dispatches = journal.count()
            received = journal.conn.execute("SELECT count(*) FROM responses").fetchone()[0]
            response_rows = journal.conn.execute("SELECT d.spec,r.payload FROM dispatches d LEFT JOIN responses r USING(request_key) ORDER BY d.started_at").fetchall()
        finally:
            journal.close()
    after_rows = read_rows(paths["market"], tickers)
    before_by_key = {row[:3]: row for row in before_rows}
    after_by_key = {row[:3]: row for row in after_rows}
    changed_old = [key for key, row in before_by_key.items() if after_by_key.get(key) != row]
    inserted_keys = set(after_by_key) - set(before_by_key)
    inside = inserted_keys & slots
    outside = inserted_keys - slots
    private_response = []
    for spec_json, payload_json in response_rows:
        spec = json.loads(spec_json)
        value = json.loads(payload_json) if payload_json is not None else None
        private_response.append({**spec, "code": value["code"] if value else "dispatch_outcome_unknown",
                                 "row_count": len(value["data"]) if value and isinstance(value["data"], list) else None})
    private_write(args.output / "responses-summary.private.json", private_response)
    private_write(args.output / "inserted-keys.private.json", sorted(inside))
    summary = {
        "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
        "plan_sha256": plan["plan_sha256"], "backup": backup_result,
        "metrics": metrics, "dispatch_reservations": dispatches, "received_responses": received,
        "unknown_dispatches": dispatches - received, "result": result, "exception": error,
        "before_coverage": coverage_summary(before), "after_coverage": coverage_summary(after),
        "before_universe_count": len(before_universe.tickers), "after_universe_count": len(after_universe.tickers),
        "target_sources_unchanged": all(before_universe.sources_by_ticker.get(t) == after_universe.sources_by_ticker.get(t) for t in tickers),
        "preexisting_target_rows_changed": len(changed_old), "new_target_rows_inside_scope": len(inside),
        "new_target_rows_outside_scope_observed": len(outside),
        "other_concurrent_writers_not_frozen": True, "profile_writes": 0,
        "automatic_retry": False, "provider_fallback": False, "schema_migration": False,
    }
    private_write(args.output / "result.private.json", summary)
    require(sum(metrics["actual_data_calls"].values()) <= dispatches <= 64, "live_request_count_mismatch")
    require(not changed_old and metrics["inserted_on_guarded_connections"] <= len(inside) <= 4940, "live_write_readback_mismatch")
    progress({"phase": "complete", "status": result["status"] if result else "failed",
              "calls": metrics["actual_data_calls"], "rows_added": len(inside),
              "remaining_missing": summary["after_coverage"]["missing_ticker_days"],
              "remaining_partial": summary["after_coverage"]["partial_ticker_days"], "exception": error})
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--sa", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repair-id", required=True)
    args = parser.parse_args()
    try:
        execute(args)
    except Exception as exc:
        print(json.dumps({"phase": "stopped", "error_class": type(exc).__name__,
                          "code": str(exc) if isinstance(exc, Stopped) else None}), flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
