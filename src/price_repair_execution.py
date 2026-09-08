"""Bounded, resumable IBKR repairs; ordinary collection keeps its own cadence."""

from collections.abc import Callable
from contextlib import closing, nullcontext
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import time
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from data_sources.ibkr_source import (
    IBKRPriceDataError, historical_intraday_bars, historical_intraday_chunks,
    _ibkr_equity_end_of_day,
)
from src import market_data_direct as writer
from src.ibkr_gateway_lock import ibkr_gateway_lock
from src.market_coverage.repair import preview_price_repair
from src.market_coverage.service import TradingDayCoverageService


class PriceRepairError(IBKRPriceDataError):
    pass


_SCHEMA = """
CREATE TABLE manifest (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL, sha256 TEXT NOT NULL);
CREATE TABLE dispatches (request_key TEXT PRIMARY KEY, spec TEXT NOT NULL, started_at REAL NOT NULL);
CREATE TABLE responses (request_key TEXT PRIMARY KEY REFERENCES dispatches(request_key), payload TEXT NOT NULL, sha256 TEXT NOT NULL);
"""
_KINDS = {"qualification", "history"}
_CONTRACT_FIELDS = ("conId", "symbol", "secType", "exchange", "primaryExchange", "currency", "localSymbol", "tradingClass")
_PLAN_FIELDS = {"version", "market_db", "coverage_at", "preview", "windows", "slots", "requests", "request_budget", "pacing_seconds", "plan_sha256"}
_TICKER = re.compile(r"[A-Z0-9][A-Z0-9 ._-]{0,11}")
_RESUMABLE_ERRORS = {"price_repair_dispatch_unknown", "ibkr_historical_data_request_failed", "security_definition_unavailable",
                     "price_repair_response_invalid", "price_repair_scope_changed", "ibkr_gateway_unavailable"}


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _digest(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _stored_at(value):
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")


def _require(condition, code="price_repair_integrity"):
    if not condition:
        raise PriceRepairError(code)


def _request_specs(windows):
    return [{"kind": kind, "ticker": ticker, "start": start.isoformat(), "end": end.isoformat(),
             "interval": "15 mins", "extended": False}
            for ticker, window in sorted(windows.items())
            for start, end in historical_intraday_chunks(date.fromisoformat(window["start"]), date.fromisoformat(window["end"]))
            for kind in ("qualification", "history")]


def build_repair_plan(coverage, market_db, *, pacing_seconds=1.0):
    preview = preview_price_repair(coverage)
    _require(preview["tickers"], "price_repair_empty")
    windows = {row["ticker"]: {"start": min(row["missing_dates"] + row["partial_dates"]),
                               "end": max(row["missing_dates"] + row["partial_dates"])} for row in preview["gaps"]}
    dates = {day for row in preview["gaps"] for day in row["missing_dates"] + row["partial_dates"]}
    slots = {}
    for day in coverage.days:
        if day.date not in dates:
            continue
        _require(day.session_open_at_utc and day.session_close_at_utc and day.expected_slot_count,
                 "price_coverage_unavailable")
        at, close = datetime.fromisoformat(day.session_open_at_utc), datetime.fromisoformat(day.session_close_at_utc)
        values = []
        while at < close:
            values.append(writer._normalize_utc(at))
            at += timedelta(minutes=15)
        _require(len(values) == day.expected_slot_count, "price_coverage_unavailable")
        slots[day.date] = values
    _require(set(slots) == dates, "price_coverage_unavailable")
    requests = _request_specs(windows)
    payload = {"version": 1, "market_db": str(Path(market_db).resolve()), "coverage_at": coverage.generated_at_et, "preview": preview,
               "windows": windows, "slots": slots, "requests": requests,
               "request_budget": {kind: sum(row["kind"] == kind for row in requests) for kind in sorted(_KINDS)} | {"total": len(requests)},
               "pacing_seconds": pacing_seconds}
    plan = {**payload, "plan_sha256": _digest(payload)}
    validate_repair_plan(plan)
    return plan


def validate_repair_plan(plan):
    try:
        _require(isinstance(plan, dict) and set(plan) == _PLAN_FIELDS and type(plan["version"]) is int and plan["version"] == 1)
        _require(plan["plan_sha256"] == _digest({key: value for key, value in plan.items() if key != "plan_sha256"}))
        _require(isinstance(plan["market_db"], str) and str(Path(plan["market_db"]).resolve()) == plan["market_db"])
        preview = plan["preview"]
        _require(set(preview) == {"provider", "fallback_allowed", "interval", "lookback_days", "as_of_date", "tickers", "blocked_tickers", "gaps", "preview_sha256"})
        _require(preview["provider"] == "ibkr" and preview["fallback_allowed"] is False and preview["interval"] == "15min")
        _require(preview["preview_sha256"] == _digest({key: value for key, value in preview.items() if key != "preview_sha256"}))
        _require(type(preview["lookback_days"]) is int and 1 <= preview["lookback_days"] <= 120)
        end = date.fromisoformat(preview["as_of_date"])
        observed = datetime.fromisoformat(plan["coverage_at"])
        _require(observed.tzinfo is not None and observed.astimezone(ZoneInfo("America/New_York")).date() == end)
        start = end - timedelta(days=preview["lookback_days"])
        tickers = preview["tickers"]
        _require(isinstance(tickers, list) and tickers and tickers == sorted(set(tickers)))
        _require(all(isinstance(t, str) and _TICKER.fullmatch(t) for t in tickers))
        _require(not set(tickers).intersection(preview["blocked_tickers"]))
        _require([row["ticker"] for row in preview["gaps"]] == tickers)
        windows, all_dates = {}, set()
        for row in preview["gaps"]:
            _require(set(row) == {"ticker", "missing_dates", "partial_dates"})
            for key in ("missing_dates", "partial_dates"):
                _require(isinstance(row[key], list) and row[key] == sorted(set(row[key])))
            dates = row["missing_dates"] + row["partial_dates"]
            _require(dates and len(dates) == len(set(dates)))
            _require(all(isinstance(day, str) and start <= date.fromisoformat(day) <= end for day in dates))
            windows[row["ticker"]] = {"start": min(dates), "end": max(dates)}
            all_dates.update(dates)
        _require(plan["windows"] == windows and set(plan["slots"]) == all_dates)
        for day, slots in plan["slots"].items():
            _require(isinstance(slots, list) and slots and slots == sorted(set(slots)))
            _require(all(writer._normalize_utc(_stored_at(at)) == at and at[:10] == day for at in slots))
            _require(all(_stored_at(b) - _stored_at(a) == timedelta(minutes=15) for a, b in zip(slots, slots[1:])))
        requests = _request_specs(windows)
        _require(plan["requests"] == requests)
        _require(plan["request_budget"] == {kind: sum(row["kind"] == kind for row in requests) for kind in sorted(_KINDS)} | {"total": len(requests)})
        _require(all(type(value) is int for value in plan["request_budget"].values()))
        pace = plan["pacing_seconds"]
        _require(type(pace) in (int, float) and math.isfinite(pace) and pace >= 0)
    except (KeyError, TypeError, ValueError, OverflowError):
        raise PriceRepairError("price_repair_integrity") from None
    return plan


def repair_directory(market_db, repair_id):
    _require(isinstance(repair_id, str) and re.fullmatch(r"[a-f0-9]{32}", repair_id), "price_repair_plan_changed")
    return Path(market_db).resolve().parent / "price_repairs" / repair_id


def load_repair_plan(directory):
    directory = Path(directory)
    path = directory / "requests.sqlite3"
    _require(path.exists(), "price_repair_not_prepared")
    _require(not directory.is_symlink() and stat.S_ISREG(path.lstat().st_mode))
    try:
        conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            rows = conn.execute("SELECT payload, sha256 FROM manifest WHERE id=1").fetchall()
            _require(len(rows) == 1)
            plan = json.loads(rows[0][0])
            _require(_digest(plan) == rows[0][1])
            return validate_repair_plan(plan)
        finally:
            conn.close()
    except (sqlite3.Error, ValueError, TypeError):
        raise PriceRepairError("price_repair_integrity") from None


def prepared_repair_request(*, repair_id, tickers, lookback_days, provider, no_provider_fallback, as_of_date):
    directory = repair_directory(writer.resolve_market_db_path(), repair_id)
    plan = load_repair_plan(directory)
    requested = [ticker.strip() for ticker in tickers.split(",")]
    _require(plan["market_db"] == str(Path(writer.resolve_market_db_path()).resolve())
             and provider == "ibkr" and no_provider_fallback is True
             and sorted(requested) == plan["preview"]["tickers"]
             and lookback_days == plan["preview"]["lookback_days"]
             and isinstance(as_of_date, date) and as_of_date.isoformat() == plan["preview"]["as_of_date"],
             "price_repair_plan_changed")
    return plan, directory


def _contract(value):
    return {key: getattr(value, key) for key in _CONTRACT_FIELDS}


def _encode_response(kind, values):
    _require(isinstance(values, (list, tuple)), "price_repair_response_invalid")
    if kind == "qualification":
        return [_contract(value) for value in values]
    return [{"date": value.date.isoformat(), "open": value.open, "high": value.high,
             "low": value.low, "close": value.close, "volume": value.volume} for value in values]


def _decode_response(spec, values):
    _require(isinstance(values, list), "price_repair_response_invalid")
    if spec["kind"] == "qualification":
        from ib_insync import Contract
        _require(len(values) <= 1, "price_repair_response_invalid")
        for row in values:
            _require(set(row) == set(_CONTRACT_FIELDS) and type(row["conId"]) is int and row["conId"] > 0,
                     "price_repair_response_invalid")
            _require(row["symbol"] == spec["ticker"] and row["secType"] == "STK" and row["currency"] == "USD",
                     "price_repair_response_invalid")
            _require(all(isinstance(row[key], str) for key in _CONTRACT_FIELDS if key != "conId"), "price_repair_response_invalid")
        return [Contract.create(**row) for row in values]
    result = []
    for row in values:
        _require(isinstance(row, dict) and set(row) == {"date", "open", "high", "low", "close", "volume"}, "price_repair_response_invalid")
        _require(all(type(row[key]) in (int, float) and math.isfinite(row[key]) for key in ("open", "high", "low", "close", "volume")),
                 "price_repair_response_invalid")
        at = datetime.fromisoformat(row["date"])
        result.append(SimpleNamespace(**{**row, "date": at}))
    return result


class RepairJournal:
    """A private per-repair artifact, not a migration of profile or market data."""

    def __init__(self, directory, plan, *, readonly=False):
        self.plan = validate_repair_plan(plan)
        self.directory = Path(directory)
        _require(not self.directory.is_symlink())
        self.readonly = readonly
        self.path = self.directory / "requests.sqlite3"
        created = False
        if readonly:
            _require(self.path.exists(), "price_repair_not_prepared")
            _require(stat.S_ISREG(self.path.lstat().st_mode))
            self.conn = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)
        else:
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
                os.close(fd)
                created = True
            except FileExistsError:
                _require(stat.S_ISREG(self.path.lstat().st_mode))
            self.conn = sqlite3.connect(self.path, timeout=10)
        try:
            if readonly:
                self.conn.execute("PRAGMA query_only=ON")
                self.conn.execute("BEGIN")
            else:
                self.conn.execute("PRAGMA foreign_keys=ON")
                self.conn.execute("PRAGMA synchronous=FULL")
            if created:
                self.conn.executescript("BEGIN IMMEDIATE;" + _SCHEMA)
                self.conn.execute("INSERT INTO manifest VALUES (1, ?, ?)", (_json(plan), _digest(plan)))
                self.conn.commit()
            self.expected = {_digest(spec): spec for spec in plan["requests"]}
            self.verify()
            self.start_count = self.count()
        except BaseException:
            self.conn.close()
            raise

    def close(self):
        self.conn.close()

    def verify(self):
        try:
            rows = self.conn.execute("SELECT payload, sha256 FROM manifest WHERE id=1").fetchall()
            _require(len(rows) == 1)
            stored = json.loads(rows[0][0])
            _require(_digest(stored) == rows[0][1] and stored == self.plan)
            dispatches = self.conn.execute("SELECT request_key, spec, started_at FROM dispatches").fetchall()
            _require(len(dispatches) <= self.plan["request_budget"]["total"])
            for key, value, started in dispatches:
                _require(key in self.expected and json.loads(value) == self.expected[key] and math.isfinite(started))
            for key, payload, seal in self.conn.execute("SELECT request_key, payload, sha256 FROM responses"):
                _require(key in {row[0] for row in dispatches})
                value = json.loads(payload)
                _require(set(value) == {"request_key", "code", "data"} and value["request_key"] == key and _digest(value) == seal)
                _require(value["code"] is None or value["code"] in _RESUMABLE_ERRORS)
                if value["code"] is None:
                    _decode_response(self.expected[key], value["data"])
                else:
                    _require(value["data"] is None)
        except (sqlite3.Error, ValueError, TypeError, AttributeError, KeyError):
            raise PriceRepairError("price_repair_integrity") from None

    def count(self):
        return self.conn.execute("SELECT count(*) FROM dispatches").fetchone()[0]

    def response(self, spec):
        # A read-only journal holds the same verified SQLite snapshot until close.
        if not self.readonly:
            self.verify()
        key = _digest(spec)
        _require(key in self.expected, "price_repair_unplanned_request")
        row = self.conn.execute("SELECT payload FROM responses WHERE request_key=?", (key,)).fetchone()
        if row:
            value = json.loads(row[0])
            if value["code"]:
                raise PriceRepairError(value["code"])
            return _decode_response(spec, value["data"])
        if self.conn.execute("SELECT 1 FROM dispatches WHERE request_key=?", (key,)).fetchone():
            raise PriceRepairError("price_repair_dispatch_unknown")
        return None

    def cached_bars(self, ticker):
        bars, complete = [], True
        for spec in self.plan["requests"]:
            if spec["ticker"] != ticker:
                continue
            value = self.response(spec)
            if value is None:
                complete = False
            elif spec["kind"] == "qualification" and not value:
                raise PriceRepairError("security_definition_unavailable")
            elif spec["kind"] == "history":
                bars.extend(historical_intraday_bars(ticker, value, date.fromisoformat(spec["start"]), date.fromisoformat(spec["end"])))
        return bars if complete else None

    def dispatch(self, kind, context, operation, args, kwargs, *, active_scope):
        spec = {"kind": kind, **context}
        key = _digest(spec)
        _require(key in self.expected and spec == self.expected[key], "price_repair_unplanned_request")
        _require(spec["ticker"] in set(active_scope()), "price_repair_scope_changed")
        _require(len(args) == 1, "price_repair_unplanned_request")
        contract = _contract(args[0])
        _require(contract["symbol"] == spec["ticker"] and contract["secType"] == "STK" and contract["currency"] == "USD",
                 "price_repair_unplanned_request")
        if kind == "qualification":
            _require(kwargs == {} and contract["exchange"] == "SMART" and contract["conId"] == 0, "price_repair_unplanned_request")
        else:
            start, end = date.fromisoformat(spec["start"]), date.fromisoformat(spec["end"])
            options = dict(endDateTime=_ibkr_equity_end_of_day(end), durationStr=f"{(end-start).days+1} D", barSizeSetting="15 mins",
                           whatToShow="TRADES", useRTH=True, formatDate=1)
            _require(kwargs == options, "price_repair_unplanned_request")
            qualified = self.response({**spec, "kind": "qualification"})
            _require(qualified and _contract(qualified[0]) == contract, "price_repair_unplanned_request")
        cached = self.response(spec)
        if cached is not None:
            return cached
        # Reservation and pacing are shared by all processes resuming this journal.
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            self.verify()
            _require(not self.conn.execute("SELECT 1 FROM dispatches WHERE request_key=?", (key,)).fetchone(), "price_repair_dispatch_unknown")
            _require(self.count() < self.plan["request_budget"]["total"], "price_repair_budget_exhausted")
            previous = self.conn.execute("SELECT max(started_at) FROM dispatches").fetchone()[0]
            if previous is not None:
                elapsed = time.time() - previous
                _require(elapsed >= 0, "price_repair_clock_changed")
                remaining = self.plan["pacing_seconds"] - elapsed
                if remaining > 0:
                    time.sleep(remaining)
            _require(spec["ticker"] in set(active_scope()), "price_repair_scope_changed")
            self.conn.execute("INSERT INTO dispatches VALUES (?, ?, ?)", (key, _json(spec), time.time()))
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise
        code, data = None, None
        try:
            raw = operation(*args, **kwargs)
        except Exception:
            code = "ibkr_historical_data_request_failed"
        else:
            try:
                data = _encode_response(kind, raw)
                _decode_response(spec, data)
                _json(data)
            except (ValueError, TypeError, AttributeError, KeyError, OverflowError, PriceRepairError):
                code, data = "price_repair_response_invalid", None
        value = {"request_key": key, "code": code, "data": data}
        self.conn.execute("INSERT INTO responses VALUES (?, ?, ?)", (key, _json(value), _digest(value)))
        self.conn.commit()
        if code:
            raise PriceRepairError(code)
        return _decode_response(spec, data)


def _current_coverage(plan, ticker, reader):
    coverage = reader(universe=[ticker], lookback_days=plan["preview"]["lookback_days"], interval="15min")
    try:
        current = preview_price_repair(coverage)
    except ValueError:
        raise PriceRepairError("price_coverage_unavailable") from None
    _require(current["as_of_date"] == plan["preview"]["as_of_date"], "price_repair_clock_changed")
    return coverage


def _write_ticker(plan, ticker, bars, active_scope):
    target = next(row for row in plan["preview"]["gaps"] if row["ticker"] == ticker)
    slots = {slot for day in target["missing_dates"] + target["partial_dates"] for slot in plan["slots"][day]}
    rows = [row for row in writer._ibkr_bars_to_rows(ticker, bars, "15min") if row[1] in slots]
    with writer.market_write_lock():
        _require(ticker in set(active_scope()), "price_repair_scope_changed")
        with closing(sqlite3.connect(Path(plan["market_db"]).as_uri() + "?mode=rw", uri=True, timeout=10)) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            aliases = writer._load_ticker_aliases(conn)
            _require(aliases.get(ticker, ticker) == ticker, "price_repair_scope_changed")
            # No global canonicalization, DDL, deletion or overwrite of old prices.
            return writer._insert_rows(conn, rows)


def execute_price_repair(plan, directory, *, source=None, active_scope: Callable,
                         coverage_reader=None, acquire_gateway_lock=True, pacing_seconds=None):
    plan = validate_repair_plan(plan)
    if pacing_seconds is not None:
        _require(pacing_seconds == plan["pacing_seconds"], "price_repair_plan_changed")
    if coverage_reader is None:
        anchor = datetime.fromisoformat(plan["coverage_at"])
        coverage_reader = TradingDayCoverageService(db_path=plan["market_db"], clock=lambda: anchor).get_coverage
    journal = RepairJournal(directory, plan)
    owned_source = source is None
    connection_attempted = False
    connection_ready = False
    result = {"status": "succeeded", "provider": "ibkr", "tickers_scanned": len(plan["preview"]["tickers"]),
              "succeeded_ticker_count": 0, "gaps_found": sum(len(row["missing_dates"]) for row in plan["preview"]["gaps"]),
              "rows_added": 0, "errors": {}, "unresolved_after_fetch_count": 0, "unresolved_after_fetch_tickers": []}
    gateway = ibkr_gateway_lock() if acquire_gateway_lock else nullcontext()
    try:
        with gateway:
            for ticker in plan["preview"]["tickers"]:
                try:
                    _require(ticker in set(active_scope()), "price_repair_scope_changed")
                    before = _current_coverage(plan, ticker, coverage_reader)
                    if not before.history_gaps:
                        continue
                    bars = journal.cached_bars(ticker)
                    if bars is None:
                        if source is None:
                            source = writer._default_ibkr_src()
                        if not connection_attempted:
                            connection_attempted = True
                            connection_ready = source.connect()
                        if not connection_ready or not source._connected or not source._ib.isConnected():
                            raise PriceRepairError("ibkr_gateway_unavailable")
                        window = plan["windows"][ticker]
                        def dispatch(kind, context, operation, args, kwargs):
                            return journal.dispatch(kind, context, operation, args, kwargs, active_scope=active_scope)
                        returned = source.fetch_historical_intraday([ticker], date.fromisoformat(window["start"]), date.fromisoformat(window["end"]),
                                                                   interval="15 mins", include_extended=False, request_runner=dispatch)
                        bars = journal.cached_bars(ticker)
                        _require(bars is not None and isinstance(returned, dict) and ticker in returned, "price_repair_unmetered_response")
                    result["rows_added"] += _write_ticker(plan, ticker, bars, active_scope)
                    after = _current_coverage(plan, ticker, coverage_reader)
                    if after.history_gaps:
                        result["errors"][ticker] = "price_coverage_incomplete_after_repair"
                        result["unresolved_after_fetch_tickers"].append(ticker)
                except IBKRPriceDataError as exc:
                    if exc.error_code not in _RESUMABLE_ERRORS:
                        raise
                    result["errors"][ticker] = exc.error_code
                except sqlite3.Error:
                    result["errors"][ticker] = "price_repair_write_failed"
            # Success is the real coverage readback, not an HTTP/collector result.
            for ticker in plan["preview"]["tickers"]:
                if ticker not in result["errors"] and _current_coverage(plan, ticker, coverage_reader).history_gaps:
                    result["errors"][ticker] = "price_coverage_incomplete_after_repair"
                    result["unresolved_after_fetch_tickers"].append(ticker)
        journal.verify()
        result["unresolved_after_fetch_tickers"] = sorted(set(result["unresolved_after_fetch_tickers"]))
        result["unresolved_after_fetch_count"] = len(result["unresolved_after_fetch_tickers"])
        result["succeeded_ticker_count"] = result["tickers_scanned"] - len(result["errors"])
        result["status"] = writer._derive_price_collection_status(result["tickers_scanned"], len(result["errors"]))
        result["repair_execution"] = {"plan_sha256": plan["plan_sha256"], "request_budget": plan["request_budget"],
                                       "requests_total": journal.count(), "requests_this_execution": journal.count() - journal.start_count,
                                       "retry": False, "fallback": False}
        return result
    finally:
        if owned_source and source is not None:
            source.disconnect()
        journal.close()
