"""One explicitly selected installation for all managed SA acquisition.

This coordinates this installation, not SA accounts/IPs on other machines.
Reservations never expire into another collector. Recovery is an operator action.
"""

from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import time
from uuid import uuid4

from src import sa_capture_store
from src.sa.company_data import CompanyDataFailure, require
from src.sa import company_store
from src.sa.acquisition_policy import navigation_eligibility, validate_policy
from src.sa.extension_run_protocol import OPERATION_CONTRACTS


PAGE_START_GAP_SECONDS = 60
_SYMBOL = re.compile(r"[A-Z][A-Z0-9.-]{0,19}\Z")
_ID = re.compile(r"[A-Za-z0-9_.:-]{1,160}\Z")
_RESTRICTIONS = {"login_required", "human_verification_required", "rate_limited", "access_restricted"}


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


def _empty(ledger_id=None, now=0):
    return {"owner": None, "active": None, "paused_reason": None,
            "rate_limit_until": None, "rate_limit_failures": 0,
            "next_navigation_at": None, "last_seen": 0, "failures": {},
            "ledger_id": ledger_id, "managed_since": _iso(now) if ledger_id else None,
            "generation": 0, "policy": None, "policy_revision": 0,
            "financial_gap_seconds": PAGE_START_GAP_SECONDS, "capability_pauses": {},
            "navigation_attempts": 0, "task_count": 0}


class CompanyCollector:
    def __init__(self, path=None, *, clock=time.time):
        self.path = Path(path) if path is not None else Path(sa_capture_store.resolve_sa_db_path()).with_name("sa_company_refresh.db")
        self.clock = clock
        self.marker = self.path.with_suffix(self.path.suffix + ".identity")

    def public_status(self):
        """Local UI projection: no browser identity, host spawn or database install."""
        try:
            now = self.clock()
            if not self.path.exists():
                require(not self.marker.exists(), "sa_company_collector_unavailable")
                state = _empty()
            else:
                with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
                    state = self._read(conn)
            return {"status": "ok", "configured": state["policy"] is not None,
                    "observed_at": _iso(now), "paused_reason": state["paused_reason"],
                    "capability_pauses": dict(state["capability_pauses"]),
                    "rate_limited": _seconds(state["rate_limit_until"]) > now,
                    "rate_limit_until": state["rate_limit_until"],
                    "collector_browser": state["owner"]["browser"] if state["owner"] else None}
        except CompanyDataFailure as exc:
            return {"status": "error", "error_code": exc.code}
        except (OSError, sqlite3.Error, ValueError, KeyError, TypeError, OverflowError):
            return {"status": "error", "error_code": "sa_company_collector_unavailable"}

    def _read(self, conn):
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        require(version != 1, "sa_acquisition_upgrade_required")
        require(version == 2, "sa_company_collector_unavailable")
        row = conn.execute("SELECT payload FROM company_collector WHERE id=1").fetchone()
        require(row is not None, "sa_company_collector_unavailable")
        state = json.loads(row[0])
        require(type(state) is dict and set(state) == set(_empty())
                and type(state["failures"]) is dict and type(state["capability_pauses"]) is dict,
                "sa_company_collector_unavailable")
        require(type(state["ledger_id"]) is str and re.fullmatch(r"[a-f0-9]{32}", state["ledger_id"])
                and self.marker.read_text().strip() == state["ledger_id"], "sa_company_collector_unavailable")
        for key in ("generation", "policy_revision", "navigation_attempts", "task_count", "rate_limit_failures"):
            require(type(state[key]) is int and state[key] >= 0, "sa_company_collector_unavailable")
        if state["owner"] is not None:
            self._client(state["owner"])
        validate_policy(state["policy"])
        require(conn.execute("SELECT count(*) FROM acquisition_navigations").fetchone()[0] == state["navigation_attempts"]
                and conn.execute("SELECT count(*) FROM acquisition_tasks").fetchone()[0] == state["task_count"],
                "sa_company_collector_unavailable")
        if state["active"]:
            row = conn.execute("SELECT payload FROM acquisition_tasks WHERE task_id=? AND finished_at IS NULL",
                               (state["active"]["task_id"],)).fetchone()
            require(row is not None and json.loads(row[0]) == state["active"], "sa_company_collector_unavailable")
        return state

    def _create_marker(self, ledger_id):
        with self.marker.open("x", encoding="ascii") as marker:
            marker.write(ledger_id + "\n")
            marker.flush()
            os.fsync(marker.fileno())

    def verify_receipt(self, receipt, result):
        """Read immutable terminal evidence, including after an owner switch."""
        try:
            with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
                state = self._read(conn)
                if receipt["ledger_id"] != state["ledger_id"]:
                    return False
                row = conn.execute("SELECT payload, receipt FROM acquisition_tasks WHERE task_id=? AND finished_at IS NOT NULL",
                                   (receipt["task_id"],)).fetchone()
                if not row or json.loads(row[1]) != receipt:
                    return False
                task = json.loads(row[0])
                return (task["operation"] == result["operation"] and task["mode"] == result["mode"]
                        and (result["derived_outcome"] != "complete" or task["result"]["status"] == "ok"))
        except (CompanyDataFailure, OSError, sqlite3.Error, ValueError, KeyError, TypeError):
            return False

    def _connect(self, msg, now):
        fresh = not self.path.exists()
        if fresh:
            require(not self.marker.exists() and msg["operation"] == "configure"
                    and msg.get("confirm_activation") is True and msg.get("expected_generation") == 0,
                    "sa_company_collector_unavailable")
            self.path.parent.mkdir(parents=True, exist_ok=True)
            ledger_id = uuid4().hex
            self._create_marker(ledger_id)
        conn = sqlite3.connect(self.path if fresh else self.path.resolve().as_uri() + "?mode=rw",
                               uri=not fresh, timeout=5, isolation_level=None)
        try:
            conn.execute("BEGIN IMMEDIATE")
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            if fresh:
                state = _empty(ledger_id, now)
                conn.execute("CREATE TABLE company_collector (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)")
                conn.execute("CREATE TABLE company_collector_actions (at TEXT, operation TEXT, client_id TEXT, previous_owner TEXT)")
            elif version == 1:
                require(msg["operation"] == "configure" and msg.get("upgrade") is True
                        and msg.get("confirm_stopped") is True and not self.marker.exists(), "sa_acquisition_upgrade_required")
                old = json.loads(conn.execute("SELECT payload FROM company_collector WHERE id=1").fetchone()[0])
                require(old.get("active") is None, "sa_company_collector_busy")
                require(type(msg.get("expected_generation")) is int and msg["expected_generation"] == 0,
                        "sa_acquisition_generation_stale")
                require(now >= old["last_seen"], "sa_company_clock_regressed")
                ledger_id = uuid4().hex
                backup = self.path.with_name(self.path.name + ".pre-coordination-" + ledger_id + ".bak")
                with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)) as source:
                    with closing(sqlite3.connect(backup)) as destination:
                        source.backup(destination)
                self._create_marker(ledger_id)
                state = {**_empty(ledger_id, now), **old}
            else:
                return conn
            state["policy"] = validate_policy(msg["policy"])
            conn.execute("CREATE TABLE acquisition_tasks (task_id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL, "
                         "generation INTEGER NOT NULL, policy_revision INTEGER NOT NULL, payload TEXT NOT NULL, finished_at REAL, receipt TEXT)")
            conn.execute("CREATE TABLE acquisition_navigations (attempt_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, "
                         "navigation_id TEXT NOT NULL, at REAL NOT NULL, priority TEXT NOT NULL, kind TEXT NOT NULL, "
                         "destination_class TEXT NOT NULL, policy_revision INTEGER NOT NULL, UNIQUE(task_id,navigation_id))")
            conn.execute("CREATE INDEX acquisition_navigations_at ON acquisition_navigations(at)")
            conn.execute("INSERT OR REPLACE INTO company_collector VALUES (1, ?)", (json.dumps(state),))
            conn.execute("PRAGMA user_version=2")
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
        active = {key: value for key, value in state["active"].items() if key not in {"token", "request_fingerprint"}} if state["active"] else None
        return {"status": "ok", "owner": state["owner"], "is_owner": state["owner"] == client,
                "active": active, "paused_reason": state["paused_reason"],
                "rate_limit_until": state["rate_limit_until"],
                "rate_limited": _seconds(state["rate_limit_until"]) > now,
                "next_navigation_at": state["next_navigation_at"],
                "next_financial_at": state["next_navigation_at"],
                "prior_traffic_coverage": "unknown",
                **{key: state[key] for key in ("ledger_id", "managed_since", "generation", "policy", "policy_revision",
                                               "financial_gap_seconds", "capability_pauses", "navigation_attempts")}}

    def handle(self, message):
        try:
            client = self._client(message.get("client"))
            operation = message.get("operation")
            now = self.clock()
            require(type(now) in (int, float) and math.isfinite(now) and now >= 0, "sa_company_collector_unavailable")
            if operation == "configure":
                validate_policy(message.get("policy"))
                gap = message.get("financial_gap_seconds")
                require(type(gap) in (int, float) and math.isfinite(gap) and 0 < gap <= 2147483,
                        "sa_company_schedule_invalid")
                require(message.get("confirm_activation") is True, "sa_acquisition_confirmation_required")
            if operation in {"status", "validate"}:
                if not self.path.exists():
                    require(not self.marker.exists(), "sa_company_collector_unavailable")
                    require(operation == "status", "sa_company_reservation_invalid")
                    return self._status(_empty(), client, now)
                with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
                    state = self._read(conn)
                    if operation == "validate":
                        self._active(state, message, client)
                    require(message.get("ledger_id", state["ledger_id"]) == state["ledger_id"], "sa_company_collector_unavailable")
                    return self._status(state, client, now)
            require(operation in {"configure", "select", "begin_task", "admit_navigation", "observe_restriction", "finish_task", "recover", "resume"}, "sa_company_control_invalid")
            with closing(self._connect(message, now)) as conn:
                state = self._read(conn)
                require(now >= state["last_seen"], "sa_company_clock_regressed")
                if message.get("require_idle") is True:
                    require(state["active"] is None, "sa_company_collector_busy")
                previous_owner = state["owner"]
                extra = self._apply(conn, state, message, client, now)
                state["last_seen"] = now
                if state["active"]:
                    conn.execute("UPDATE acquisition_tasks SET payload=? WHERE task_id=?",
                                 (json.dumps(state["active"]), state["active"]["task_id"]))
                conn.execute("UPDATE company_collector SET payload=? WHERE id=1", (json.dumps(state),))
                if operation in {"select", "recover", "resume"}:
                    conn.execute("INSERT INTO company_collector_actions VALUES (?, ?, ?, ?)",
                                 (_iso(now), operation, client["client_id"], json.dumps(previous_owner)))
                conn.commit()
                return {**self._status(state, client, now), **extra}
        except CompanyDataFailure as exc:
            return {"status": "error", "error_code": exc.code}
        except (OSError, sqlite3.Error, ValueError, KeyError, TypeError, AttributeError, OverflowError, IndexError):
            return {"status": "error", "error_code": "sa_company_collector_unavailable"}

    @staticmethod
    def _generation(state, msg, key="generation"):
        require(type(msg.get(key)) is int and msg[key] == state["generation"], "sa_acquisition_generation_stale")

    def _active(self, state, msg, client):
        self._generation(state, msg)
        active = state["active"]
        require(active is not None and active["client"] == client and active["token"] == msg.get("token"),
                "sa_company_reservation_invalid")
        return active

    @staticmethod
    def _lane(operation):
        return "background" if operation in {"company_financial_capture", "alpha_picks_body_repair"} else "routine"

    @staticmethod
    def _capability(operation):
        if operation.startswith("alpha_picks"):
            return "alpha_picks"
        return "financials" if operation == "company_financial_capture" else "news"

    def _blocked(self, state, operation, now):
        reason = state["paused_reason"] or state["capability_pauses"].get(self._capability(operation))
        if _seconds(state["rate_limit_until"]) > now:
            return {"status": "deferred", "reason": "site_paused", "error_code": "sa_company_rate_limited",
                    "retry_after": state["rate_limit_until"]}
        if reason:
            return {"status": "deferred", "reason": "site_paused", "error_code": reason, "retry_after": None}
        # Reuse the operator-configured background page gap, not a provider quota.
        if operation == "alpha_picks_body_repair" and _seconds(state["next_navigation_at"]) > now:
            return {"status": "deferred", "reason": "site_pacing", "error_code": "sa_company_pacing",
                    "retry_after": state["next_navigation_at"]}
        return None

    @staticmethod
    def _capacity(conn, state, priority, now):
        attempts = conn.execute("SELECT at, priority FROM acquisition_navigations WHERE at>?", (now - 86400,)).fetchall()
        result = navigation_eligibility(attempts, state["policy"], priority, now)
        if not result["allowed"]:
            return {"status": "deferred", "allowed": False, "reason": "capacity_exhausted",
                    "retry_after": _iso(result["retry_at"]) if result["retry_at"] else None}
        return None

    def _apply(self, conn, state, msg, client, now):
        operation = msg["operation"]
        if operation in {"configure", "select", "recover", "resume"}:
            self._generation(state, msg, "expected_generation")
        if operation == "configure":
            # A stopped legacy installation may be upgraded from its replacement browser.
            # Ownership is preserved until the separate, explicitly confirmed selection.
            upgrading = (state["generation"] == 0 and state["policy_revision"] == 0
                         and msg.get("upgrade") is True and msg.get("confirm_stopped") is True)
            if state["owner"] is not None and not upgrading:
                self._owner(state, client)
            state["policy"] = validate_policy(msg["policy"])
            state["policy_revision"] += 1
            state["financial_gap_seconds"] = msg["financial_gap_seconds"]
            return {}
        if operation == "select":
            require(msg.get("confirm_schedules") is True, "sa_acquisition_confirmation_required")
            require(state["active"] is None, "sa_company_collector_busy")
            state["owner"] = client
            state["generation"] += 1
            return {}
        if operation == "recover":
            require(msg.get("confirm_stopped") is True, "sa_company_recovery_confirmation_required")
            if state["active"]:
                self._failure(state, "sa_company_refresh_interrupted", now)
                self._terminal(conn, state, {"status": "cancelled"}, now)
            return {}
        if operation in {"observe_restriction", "finish_task", "admit_navigation"}:
            active = self._active(state, msg, client)
            if operation == "observe_restriction":
                reason = msg.get("reason")
                require(reason in _RESTRICTIONS, "sa_acquisition_restriction_invalid")
                self._restriction(state, reason, now, msg.get("retry_after"))
                return {}
            if operation == "admit_navigation":
                nav_id, kind, destination = msg.get("navigation_id"), msg.get("kind"), msg.get("destination_class")
                require(type(nav_id) is str and _ID.fullmatch(nav_id)
                        and kind in {"create", "update", "reload", "current_tab"}
                        and destination in {"picks", "article", "news", "financials", "company"}, "sa_acquisition_navigation_invalid")
                old = conn.execute("SELECT attempt_id, kind, destination_class FROM acquisition_navigations WHERE task_id=? AND navigation_id=?",
                                   (active["task_id"], nav_id)).fetchone()
                if old:
                    require(old[1:] == (kind, destination), "sa_acquisition_navigation_invalid")
                    return {"allowed": False, "replayed": True, "attempt_id": old[0]}
                blocked = self._blocked(state, active["operation"], now) or self._capacity(conn, state, active["priority"], now)
                if blocked:
                    return blocked
                attempt_id = uuid4().hex
                conn.execute("INSERT INTO acquisition_navigations VALUES (?,?,?,?,?,?,?,?)",
                             (attempt_id, active["task_id"], nav_id, now, active["priority"], kind, destination, state["policy_revision"]))
                state["navigation_attempts"] += 1
                active["navigation_attempt_count"] += 1
                return {"allowed": True, "replayed": False, "attempt_id": attempt_id}
            require(msg.get("cleanup_confirmed") is True, "sa_acquisition_cleanup_unconfirmed")
            result = msg.get("result")
            require(type(result) is dict and result.get("status") in {"ok", "error", "cancelled", "deferred", "partial"}, "sa_company_receipt_unverified")
            if result["status"] == "ok" and active["scope"] is not None:
                require(not active["failure_reported"], "sa_company_receipt_unverified")
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
            return {"acquisition": self._terminal(conn, state, result, now)}
        self._generation(state, msg, "expected_generation" if operation == "resume" else "generation")
        self._owner(state, client)
        if operation == "resume":
            require(state["active"] is None, "sa_company_collector_busy")
            require(msg.get("confirm_handled") is True, "sa_acquisition_confirmation_required")
            state["paused_reason"] = None
            capability = msg.get("capability")
            if capability is not None:
                require(capability in {"financials", "news", "alpha_picks"}, "sa_company_control_invalid")
                state["capability_pauses"].pop(capability, None)
            return {}
        task_operation, mode = msg.get("task_operation"), msg.get("mode")
        contract = OPERATION_CONTRACTS.get(task_operation) if type(task_operation) is str else None
        require(contract is not None and mode in contract["modes"], "sa_company_control_invalid")
        if task_operation == "alpha_picks_body_repair":
            require(msg.get("trigger") == "manual", "sa_company_control_invalid")
        request_id = msg.get("request_id")
        require(type(request_id) is str and _ID.fullmatch(request_id)
                and msg.get("trigger") in {"manual", "alarm", "startup", "continuation"}
                and type(msg.get("intent_revision")) is int and msg["intent_revision"] >= 0
                and type(msg.get("build")) is str and 0 < len(msg["build"]) <= 128
                and msg.get("protocol_version") == 2, "sa_company_control_invalid")
        fingerprint = json.dumps({k: v for k, v in msg.items() if k not in {"action"}}, sort_keys=True)
        request_key = client["client_id"] + ":" + request_id
        old = conn.execute("SELECT payload, receipt FROM acquisition_tasks WHERE request_id=?", (request_key,)).fetchone()
        if old:
            task = json.loads(old[0])
            require(task["request_fingerprint"] == fingerprint, "sa_acquisition_request_conflict")
            return {"status": "completed" if old[1] else "uncertain", "replayed": True,
                    "task_id": task["task_id"], "token": task["token"],
                    "acquisition": json.loads(old[1]) if old[1] else None}
        blocked = self._blocked(state, task_operation, now)
        if blocked:
            return blocked
        require(state["active"] is None, "sa_company_collector_busy")
        scope = self._scope(msg.get("scope")) if task_operation == "company_financial_capture" and mode != "current_tab" else None
        if scope:
            reuse = self._financial_eligibility(state, msg, scope, now)
            if reuse:
                return reuse
        priority = self._lane(task_operation)
        capacity = self._capacity(conn, state, priority, now)
        if capacity:
            return capacity
        task_id, token = uuid4().hex, uuid4().hex
        queue_wait = msg.get("queue_wait_ms", 0)
        require(type(queue_wait) in (int, float) and math.isfinite(queue_wait) and queue_wait >= 0, "sa_company_control_invalid")
        state["active"] = {"task_id": task_id, "token": token, "client": client, "scope": scope,
                           "operation": task_operation, "mode": mode, "priority": priority,
                           "trigger": msg["trigger"], "build": msg["build"], "protocol_version": 2,
                           "generation": state["generation"], "batch_id": request_id,
                           "queue_wait_ms": queue_wait, "navigation_attempt_count": 0,
                           "started_at": _iso(now), "failure_reported": False, "request_fingerprint": fingerprint}
        conn.execute("INSERT INTO acquisition_tasks VALUES (?,?,?,?,?,NULL,NULL)",
                     (task_id, request_key, state["generation"], state["policy_revision"], json.dumps(state["active"])))
        state["task_count"] += 1
        return {"token": token, "task_id": task_id}

    def _financial_eligibility(self, state, msg, scope, now):
        days = msg.get("interval_days")
        require(type(days) is int and 1 <= days <= 365 and type(msg.get("force")) is bool, "sa_company_schedule_invalid")
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
        failure = state["failures"].get("/".join(scope.values()), {})
        if _seconds(failure.get("retry_after")) > now:
            return {"status": "deferred", "deferral_kind": "scope", "error_code": failure["error_code"], "retry_after": failure["retry_after"]}
        if _seconds(state["next_navigation_at"]) > now:
            return {"status": "deferred", "error_code": "sa_company_pacing", "retry_after": state["next_navigation_at"]}
        return None

    def _terminal(self, conn, state, result, now):
        active = state["active"]
        receipt = {"schema_version": 1, "ledger_id": state["ledger_id"], **active["client"],
                   **{key: active[key] for key in ("build", "protocol_version", "generation", "task_id", "batch_id",
                                                   "priority", "trigger", "navigation_attempt_count", "queue_wait_ms")},
                   "acquisition_duration_ms": round((now - _seconds(active["started_at"])) * 1000),
                   "identity_basis": "native_task_admission"}
        conn.execute("UPDATE acquisition_tasks SET payload=?, finished_at=?, receipt=? WHERE task_id=?",
                     (json.dumps({**active, "result": result}), now, json.dumps(receipt), active["task_id"]))
        if active["priority"] == "background":
            state["next_navigation_at"] = _iso(max(_seconds(state["next_navigation_at"]), now + state["financial_gap_seconds"]))
        state["active"] = None
        return receipt

    def _restriction(self, state, reason, now, retry_after=None):
        if reason == "rate_limited":
            if not state["active"].get("rate_limit_reported"):
                state["rate_limit_failures"] = min(state["rate_limit_failures"] + 1, 6)
                state["active"]["rate_limit_reported"] = True
            deadline = now + min(6 * 3600 * 2 ** (state["rate_limit_failures"] - 1), 7 * 86400)
            state["rate_limit_until"] = _iso(max(deadline, _seconds(state["rate_limit_until"]), _seconds(retry_after)))
        elif reason == "access_restricted":
            state["capability_pauses"][self._capability(state["active"]["operation"])] = reason
        else:
            state["paused_reason"] = reason
        state["active"]["failure_reported"] = True

    def _failure(self, state, code, now):
        active = state["active"]
        if active["failure_reported"]:
            return
        if type(code) is not str or not re.fullmatch(r"(?:sa_company_|data_source_)[a-z_]+", code):
            code = "sa_company_refresh_failed"
        key = "/".join(active["scope"].values()) if active["scope"] else active["operation"]
        failures = min(state["failures"].get(key, {}).get("count", 0) + 1, 6)
        delay = min(6 * 3600 * 2 ** (failures - 1), 7 * 86400)
        state["failures"][key] = {"count": failures, "error_code": code, "retry_after": _iso(now + delay)}
        reason = code.removeprefix("sa_company_")
        if reason in _RESTRICTIONS:
            self._restriction(state, reason, now)
        active["failure_reported"] = True
