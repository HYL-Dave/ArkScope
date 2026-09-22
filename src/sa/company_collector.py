"""One explicitly selected local browser for SA financial page acquisition.

This coordinates this installation, not SA accounts/IPs on other machines.
Reservations never expire into another collector. Recovery is an operator action.
"""

from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import sqlite3
import time
from uuid import uuid4

from src import sa_capture_store
from src.sa.company_data import CompanyDataFailure, require
from src.sa import company_store


PAGE_START_GAP_SECONDS = 60
_PAUSE = re.compile(r"human_verification|access_restricted|login_required|layout_unrecognized|structure_changed|identity_mismatch|units_unrecognized|value_unrecognized")
_SYMBOL = re.compile(r"[A-Z][A-Z0-9.-]{0,19}\Z")


def watchlist_targets():
    from src.active_universe import ActiveUniverseUnavailable, build_active_universe_snapshot

    try:
        snapshot = build_active_universe_snapshot()
    except ActiveUniverseUnavailable as exc:
        return {**exc.as_dict(), "status": "error", "error_code": exc.code}
    return {
        "status": "ok", "total_count": len(snapshot.tickers),
        "tickers": [symbol for symbol in snapshot.tickers if _SYMBOL.fullmatch(symbol)],
        "unsupported": [{"ticker": symbol, "reason": "sa_company_symbol_unmapped"}
                        for symbol in snapshot.tickers if not _SYMBOL.fullmatch(symbol)],
        "sources_by_ticker": {symbol: list(sources) for symbol, sources in snapshot.sources_by_ticker.items()},
        "source_status": {key: asdict(value) for key, value in snapshot.source_status.items()},
        "generated_at": snapshot.generated_at,
    }


def _iso(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


def _seconds(value):
    if value is None:
        return 0
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.tzinfo is not None, "sa_company_collector_unavailable")
    return parsed.timestamp()


def _empty():
    return {"owner": None, "active": None, "paused_reason": None,
            "rate_limit_until": None, "rate_limit_failures": 0,
            "next_navigation_at": None, "last_seen": 0, "failures": {}}


class CompanyCollector:
    def __init__(self, path=None, *, clock=time.time):
        self.path = Path(path) if path is not None else Path(sa_capture_store.resolve_sa_db_path()).with_name("sa_company_refresh.db")
        self.clock = clock

    def _read(self, conn):
        require(conn.execute("PRAGMA user_version").fetchone()[0] == 1, "sa_company_collector_unavailable")
        row = conn.execute("SELECT payload FROM company_collector WHERE id=1").fetchone()
        require(row is not None, "sa_company_collector_unavailable")
        state = json.loads(row[0])
        require(type(state) is dict and set(state) == set(_empty())
                and type(state["failures"]) is dict, "sa_company_collector_unavailable")
        return state

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        try:
            conn.execute("BEGIN IMMEDIATE")
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if not tables and version == 0:
                conn.execute("CREATE TABLE company_collector (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)")
                conn.execute("CREATE TABLE company_collector_actions (at TEXT, operation TEXT, client_id TEXT, previous_owner TEXT)")
                conn.execute("INSERT INTO company_collector VALUES (1, ?)", (json.dumps(_empty()),))
                conn.execute("PRAGMA user_version=1")
            return conn
        except Exception:
            conn.close()
            raise

    @staticmethod
    def _client(value):
        require(type(value) is dict and value.get("browser") in {"firefox", "chrome"}
                and type(value.get("client_id")) is str
                and re.fullmatch(r"[a-f0-9-]{32,36}", value["client_id"]), "sa_company_client_invalid")
        return {"client_id": value["client_id"], "browser": value["browser"]}

    @staticmethod
    def _owner(state, client):
        require(state["owner"] is not None, "sa_company_collector_unselected")
        require(state["owner"] == client, "sa_company_collector_other_browser")

    @staticmethod
    def _scope(value):
        require(type(value) is dict and type(value.get("ticker")) is str
                and _SYMBOL.fullmatch(value["ticker"])
                and value.get("statement") in {"income_statement", "balance_sheet", "cash_flow_statement"}
                and value.get("view") in {"annual", "quarterly"}, "sa_company_schedule_invalid")
        return {key: value[key] for key in ("ticker", "statement", "view")}

    @staticmethod
    def _status(state, client, now):
        # The reservation secret is never needed by a status reader or another browser.
        active = {key: value for key, value in state["active"].items() if key != "token"} if state["active"] else None
        return {"status": "ok", "owner": state["owner"], "is_owner": state["owner"] == client,
                "active": active, "paused_reason": state["paused_reason"],
                "rate_limit_until": state["rate_limit_until"],
                "rate_limited": _seconds(state["rate_limit_until"]) > now,
                "next_navigation_at": state["next_navigation_at"]}

    def handle(self, message):
        try:
            client = self._client(message.get("client"))
            operation = message.get("operation")
            now = float(self.clock())
            require(math.isfinite(now) and now >= 0, "sa_company_collector_unavailable")
            if operation in {"status", "validate"}:
                if not self.path.exists():
                    require(operation == "status", "sa_company_reservation_invalid")
                    return self._status(_empty(), client, now)
                with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
                    state = self._read(conn)
                    if operation == "validate":
                        active = state["active"]
                        require(active is not None and active["client"] == client and active["token"] == message.get("token"),
                                "sa_company_reservation_invalid")
                    return self._status(state, client, now)
            require(operation in {"select", "begin", "report_failure", "finish", "recover", "resume"}, "sa_company_control_invalid")
            with closing(self._connect()) as conn:
                state = self._read(conn)
                require(now >= state["last_seen"], "sa_company_clock_regressed")
                previous_owner = state["owner"]
                extra = self._apply(state, message, client, now)
                state["last_seen"] = now
                conn.execute("UPDATE company_collector SET payload=? WHERE id=1", (json.dumps(state),))
                if operation in {"select", "recover", "resume"}:
                    conn.execute("INSERT INTO company_collector_actions VALUES (?, ?, ?, ?)",
                                 (_iso(now), operation, client["client_id"], json.dumps(previous_owner)))
                conn.commit()
                return {**self._status(state, client, now), **extra}
        except CompanyDataFailure as exc:
            return {"status": "error", "error_code": exc.code}
        except (OSError, sqlite3.Error, ValueError, KeyError, TypeError, AttributeError, OverflowError):
            return {"status": "error", "error_code": "sa_company_collector_unavailable"}

    def _apply(self, state, msg, client, now):
        operation = msg["operation"]
        if operation == "select":
            require(state["active"] is None, "sa_company_collector_busy")
            state["owner"] = client
            return {}
        if operation == "recover":
            require(msg.get("confirm_stopped") is True, "sa_company_recovery_confirmation_required")
            if state["active"]:
                self._failure(state, "sa_company_refresh_interrupted", now)
                state["next_navigation_at"] = _iso(max(_seconds(state["next_navigation_at"]), now + PAGE_START_GAP_SECONDS))
            state["active"] = None
            return {}
        if operation in {"report_failure", "finish"}:
            active = state["active"]
            require(active is not None and active["client"] == client and active["token"] == msg.get("token"),
                    "sa_company_reservation_invalid")
            result = msg.get("result")
            require(type(result) is dict and result.get("status") in {"ok", "error", "cancelled"}, "sa_company_receipt_unverified")
            if result["status"] == "ok":
                require(operation == "finish" and not active["failure_reported"], "sa_company_receipt_unverified")
                scope = active["scope"]
                observation_id = result.get("observation_id")
                require(type(observation_id) is str and re.fullmatch(r"[a-f0-9]{64}", observation_id), "sa_company_receipt_unverified")
                stored = company_store.read_capture(scope["ticker"], scope["statement"], scope["view"], "USD", observation_id=observation_id)
                require(stored is not None and _seconds(active["started_at"]) <= _seconds(stored["last_captured_at"]) <= now,
                        "sa_company_receipt_unverified")
                state["failures"].pop("/".join(scope.values()), None)
                state["rate_limit_failures"] = 0
            elif result["status"] == "error":
                self._failure(state, result.get("error_code"), now)
            if operation == "finish":
                state["active"] = None
                # The browser may have suspended after reservation but before navigation.
                state["next_navigation_at"] = _iso(max(_seconds(state["next_navigation_at"]), now + PAGE_START_GAP_SECONDS))
            return {}
        self._owner(state, client)
        if operation == "resume":
            require(state["active"] is None, "sa_company_collector_busy")
            state["paused_reason"] = None
            return {}
        scope = self._scope(msg.get("scope"))
        days = msg.get("interval_days")
        require(type(days) is int and 1 <= days <= 365 and type(msg.get("force")) is bool, "sa_company_schedule_invalid")
        require(_seconds(state["rate_limit_until"]) <= now, "sa_company_rate_limited")
        require(not state["paused_reason"], state["paused_reason"] or "sa_company_collector_paused")
        require(state["active"] is None, "sa_company_collector_busy")
        requested_at = msg.get("requested_at")
        if requested_at is not None:
            require(type(requested_at) is str and 0 < _seconds(requested_at) <= now, "sa_company_schedule_invalid")
        stored = company_store.read_capture(scope["ticker"], scope["statement"], scope["view"], "USD")
        if stored and _seconds(stored["last_captured_at"]) <= now:
            captured = _seconds(stored["last_captured_at"])
            if (not msg["force"] and now - captured < days * 86400
                    or requested_at is not None and captured >= _seconds(requested_at)):
                return {"status": "reused", "observation_id": stored["observation_id"], "currency": "USD", **scope,
                        "last_success_at": stored["last_captured_at"]}
        if not msg["force"]:
            failure = state["failures"].get("/".join(scope.values()), {})
            if _seconds(failure.get("retry_after")) > now:
                return {"status": "deferred", "deferral_kind": "scope", "error_code": failure["error_code"], "retry_after": failure["retry_after"]}
        if _seconds(state["next_navigation_at"]) > now:
            return {"status": "deferred", "error_code": "sa_company_pacing", "retry_after": state["next_navigation_at"]}
        token = uuid4().hex
        state["active"] = {"token": token, "client": client, "scope": scope, "started_at": _iso(now), "failure_reported": False}
        state["next_navigation_at"] = _iso(now + PAGE_START_GAP_SECONDS)
        return {"token": token}

    @staticmethod
    def _failure(state, code, now):
        active = state["active"]
        if active["failure_reported"]:
            return
        if type(code) is not str or not re.fullmatch(r"(?:sa_company_|data_source_)[a-z_]+", code):
            code = "sa_company_refresh_failed"
        key = "/".join(active["scope"].values())
        failures = min(state["failures"].get(key, {}).get("count", 0) + 1, 6)
        delay = min(6 * 3600 * 2 ** (failures - 1), 7 * 86400)
        state["failures"][key] = {"count": failures, "error_code": code, "retry_after": _iso(now + delay)}
        if code == "sa_company_rate_limited":
            state["rate_limit_failures"] = min(state["rate_limit_failures"] + 1, 6)
            state["rate_limit_until"] = _iso(now + min(6 * 3600 * 2 ** (state["rate_limit_failures"] - 1), 7 * 86400))
        if _PAUSE.search(code):
            state["paused_reason"] = code
        active["failure_reported"] = True
