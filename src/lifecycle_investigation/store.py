"""Append-only steps and sources, durable ownership, and truthful interruption."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import sqlite3
import json
from uuid import uuid4

from src.lifecycle_investigation.runtime import InvestigationRuntime
from src.lifecycle_investigation.schema import verify_journal
from src.lifecycle_web_store import _json, _sha
from src.security_lifecycle_provider_snapshot import instant
from src.security_lifecycle_schema import assert_lifecycle_writes_available
from src.security_lifecycle_web_contract import ExecutionSelection, RunControl, validate_selection


def safe_code(exc):
    from src.lifecycle_web_controller import _failure_code
    known = {"target_not_tracked", "tracking_state_unavailable", "selected_credential_unavailable",
        "investigation_not_installed", "investigation_schema_mismatch", "investigation_runtime_version",
        "investigation_runtime_schema_mismatch", "investigation_preflight_changed", "investigation_running",
        "investigation_request_changed", "investigation_owner_changed", "investigation_not_running",
        "investigation_recording_unavailable", "investigation_integrity", "investigation_worker_busy",
        "investigation_budget_exhausted", "investigation_no_progress", "investigation_not_actionable",
        "investigation_source_gaps_not_acknowledged", "local_news_unavailable", "local_candidate_changed",
        "local_candidate_unknown", "local_body_unavailable", "local_query_invalid", "review_changed",
        "provider_review_ineligible", "provider_review_unavailable", "provider_snapshot_changed"}
    value = str(exc)
    return value if value in known else _failure_code(exc)


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,180}", value):
        raise ValueError("investigation_integrity")
    return value


def _decoded(raw, digest):
    try:
        value = json.loads(raw)
        if _sha(value) != digest:
            raise ValueError()
        return value
    except (ValueError, TypeError):
        raise ValueError("investigation_integrity") from None


class InvestigationStore:
    def __init__(self, path, *, clock=None):
        self.path = Path(path).resolve()
        self.clock = clock or (lambda: datetime.now(timezone.utc).isoformat())

    def _now(self):
        return instant(self.clock()).isoformat()

    @contextmanager
    def connection(self, *, write=False):
        conn = None
        try:
            conn = sqlite3.connect(self.path.as_uri() + ("?mode=rw" if write else "?mode=ro"), uri=True, timeout=10)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            verify_journal(conn)
            if write:
                assert_lifecycle_writes_available(conn)
            conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield conn
            if write:
                conn.commit()
        except sqlite3.Error:
            raise ValueError("investigation_recording_unavailable") from None
        finally:
            if conn is not None:
                conn.close()

    @staticmethod
    def row(conn, run_id):
        row = conn.execute("SELECT * FROM lifecycle_investigation_jobs WHERE run_id=?", (_id(run_id),)).fetchone()
        if row is None:
            raise KeyError(run_id)
        binding = _decoded(row["header_json"], row["header_sha256"])
        if binding.get("version") != 2 or binding["target"]["ticker"] != row["ticker"]:
            raise ValueError("investigation_integrity")
        return dict(row), binding

    def _owned(self, conn, run_id, owner):
        row, header = self.row(conn, run_id)
        if row["owner"] != owner:
            raise ValueError("investigation_owner_changed")
        if row["status"] != "running" or instant(row["lease_until"]) <= instant(self._now()):
            raise ValueError("investigation_not_running")
        return row, header

    def start(self, *, binding, request_key, owner):
        from src.lifecycle_investigation.target import Target
        if (type(binding) is not dict or set(binding) != {"version", "language", "target", "selection", "runtime", "effort",
                "credential_generation", "provider_observations", "provider_sha256"} or binding["version"] != 2
                or binding["language"] not in {"en", "zh-Hant"}):
            raise ValueError("investigation_integrity")
        target = Target.model_validate(binding["target"])
        InvestigationRuntime.model_validate(binding["runtime"])
        validate_selection(**binding["selection"])
        _id(request_key)
        _id(owner)
        at = self._now()
        with self.connection(write=True) as conn:
            prior = conn.execute("SELECT run_id,header_sha256 FROM lifecycle_investigation_jobs WHERE request_key=?", (request_key,)).fetchone()
            if prior:
                if prior["header_sha256"] != _sha(binding):
                    raise ValueError("investigation_request_changed")
                return {"run_id": prior["run_id"], "created": False}
            if conn.execute("SELECT 1 FROM lifecycle_investigation_jobs WHERE ticker=? AND status='running'", (target.ticker,)).fetchone():
                raise ValueError("investigation_running")
            identity = "li_" + uuid4().hex
            conn.execute("INSERT INTO lifecycle_investigation_jobs(run_id,ticker,request_key,header_json,header_sha256,owner,created_at,lease_until,status,phase) "
                "VALUES(?,?,?,?,?,?,?,?,'running','queued')", (identity, target.ticker, request_key, _json(binding), _sha(binding), owner, at,
                    (instant(at) + timedelta(seconds=60)).isoformat()))
        return {"run_id": identity, "created": True}

    def heartbeat(self, run_id, *, owner):
        with self.connection(write=True) as conn:
            row, _ = self._owned(conn, run_id, owner)
            conn.execute("UPDATE lifecycle_investigation_jobs SET lease_until=? WHERE run_id=?",
                ((instant(self._now()) + timedelta(seconds=60)).isoformat(), run_id))
            return row["cancel_requested_at"] is not None

    def step(self, run_id, *, owner, kind, payload):
        if not re.fullmatch(r"[a-z_]{1,64}", kind):
            raise ValueError("investigation_integrity")
        with self.connection(write=True) as conn:
            self._owned(conn, run_id, owner)
            ordinal = conn.execute("SELECT COALESCE(MAX(ordinal),0)+1 FROM lifecycle_investigation_steps WHERE run_id=?", (run_id,)).fetchone()[0]
            conn.execute("INSERT INTO lifecycle_investigation_steps VALUES(?,?,?,?,?,?)", (run_id, ordinal, kind, _json(payload), _sha(payload), self._now()))
            conn.execute("UPDATE lifecycle_investigation_jobs SET phase=? WHERE run_id=?", (kind, run_id))

    def source(self, run_id, *, owner, source_id, payload):
        with self.connection(write=True) as conn:
            self._owned(conn, run_id, owner)
            conn.execute("INSERT INTO lifecycle_investigation_sources VALUES(?,?,?,?)", (run_id, _id(source_id), _json(payload), _sha(payload)))

    def reserve_call(self, run_id, *, owner, call_id):
        with self.connection(write=True) as conn:
            row, header = self._owned(conn, run_id, owner)
            if row["cancel_requested_at"] is not None:
                raise ValueError("stop_requested")
            calls = conn.execute("SELECT call_id,terminal FROM lifecycle_investigation_calls WHERE run_id=?", (run_id,)).fetchall()
            if (len(calls) >= header["runtime"]["model_submissions"] or any(item["terminal"] != "completed" for item in calls)):
                raise ValueError("investigation_budget_exhausted")
            conn.execute("INSERT INTO lifecycle_investigation_calls(run_id,call_id) VALUES(?,?)", (run_id, _id(call_id)))

    def bind_call(self, run_id, *, owner, call_id, remote_id, terminal=None):
        with self.connection(write=True) as conn:
            self._owned(conn, run_id, owner)
            changed = conn.execute("UPDATE lifecycle_investigation_calls SET remote_id=?,terminal=COALESCE(?,terminal) WHERE run_id=? AND call_id=?",
                (_id(remote_id), terminal, run_id, call_id)).rowcount
            if changed != 1:
                raise ValueError("investigation_integrity")

    def finish(self, run_id, *, owner, status, payload=None, failure_code=None):
        if status not in {"succeeded", "incomplete", "failed", "cancelled", "remote_outcome_unknown"}:
            raise ValueError("investigation_integrity")
        with self.connection(write=True) as conn:
            row, _ = self._owned(conn, run_id, owner)
            pending = conn.execute("SELECT 1 FROM lifecycle_investigation_calls WHERE run_id=? AND terminal IS NULL", (run_id,)).fetchone()
            if pending:
                status, failure_code = "remote_outcome_unknown", "remote_outcome_unknown"
            elif row["cancel_requested_at"] is not None:
                status, failure_code = "cancelled", "stop_requested"
            if status == "succeeded":
                self._require_success(conn, run_id, payload)
            if payload is not None:
                conn.execute("INSERT INTO lifecycle_investigation_results VALUES(?,?,?,?)", (run_id, _json(payload), _sha(payload), self._now()))
            conn.execute("UPDATE lifecycle_investigation_jobs SET status=?,finished_at=?,failure_code=? WHERE run_id=?",
                (status, self._now(), failure_code, run_id))

    @staticmethod
    def _require_success(conn, run_id, payload):
        from src.lifecycle_investigation.agent import Step
        from src.lifecycle_investigation.findings import Finding
        calls = conn.execute("SELECT call_id,remote_id,terminal FROM lifecycle_investigation_calls WHERE run_id=? ORDER BY rowid", (run_id,)).fetchall()
        last = conn.execute("SELECT payload_json,payload_sha256 FROM lifecycle_investigation_steps WHERE run_id=? AND kind='model_result' ORDER BY ordinal DESC LIMIT 1", (run_id,)).fetchone()
        try:
            if (not calls or any(call["terminal"] != "completed" for call in calls) or last is None
                    or payload["version"] != 2 or payload["status"] != "succeeded" or payload["stop_reason"] is not None
                    or payload["stats"]["model_submissions"] != len(calls)):
                raise ValueError()
            observed = _decoded(*last)
            step = Step.model_validate(observed["output"])
            finding = Finding.model_validate(payload["validated"]["finding"])
            if (observed["phase"] != "analysis" or observed["call_id"] != calls[-1]["call_id"]
                    or observed["remote_id"] != calls[-1]["remote_id"] or observed["output_error"] is not None
                    or step.action != "conclude" or step.finding != finding or finding.event_kind == "unresolved"
                    or set(payload["validated"]["block_reasons"]) - ({"event_not_completed"} if finding.timing == "scheduled" else set())):
                raise ValueError()
        except (ValueError, KeyError, TypeError, AttributeError):
            raise ValueError("investigation_integrity") from None

    def cancel(self, run_id):
        with self.connection(write=True) as conn:
            self.row(conn, run_id)
            conn.execute("UPDATE lifecycle_investigation_jobs SET cancel_requested_at=COALESCE(cancel_requested_at,?) WHERE run_id=? AND status='running'",
                (self._now(), run_id))

    request_cancel = cancel

    def fail(self, run_id, *, owner, code, control):
        self.finish(run_id, owner=owner, status="failed", failure_code=code)

    def recover(self):
        with self.connection(write=True) as conn:
            rows = conn.execute("SELECT run_id FROM lifecycle_investigation_jobs WHERE status='running' AND lease_until<=?", (self._now(),)).fetchall()
            for row in rows:
                pending = conn.execute("SELECT 1 FROM lifecycle_investigation_calls WHERE run_id=? AND terminal IS NULL", (row[0],)).fetchone()
                status = "remote_outcome_unknown" if pending else "failed"
                conn.execute("UPDATE lifecycle_investigation_jobs SET status=?,finished_at=?,failure_code=? WHERE run_id=?",
                    (status, self._now(), "remote_outcome_unknown" if pending else "worker_interrupted", row[0]))

    @classmethod
    def read_on_connection(cls, conn, run_id, *, include_sources=True):
        row, binding = cls.row(conn, run_id)
        steps = [{"ordinal": item["ordinal"], "kind": item["kind"], "at": item["created_at"],
                  "payload": _decoded(item["payload_json"], item["payload_sha256"])}
            for item in conn.execute("SELECT * FROM lifecycle_investigation_steps WHERE run_id=? ORDER BY ordinal", (run_id,))]
        saved = conn.execute("SELECT * FROM lifecycle_investigation_results WHERE run_id=?", (run_id,)).fetchone()
        sources = {item["source_id"]: _decoded(item["payload_json"], item["payload_sha256"])
            for item in conn.execute("SELECT * FROM lifecycle_investigation_sources WHERE run_id=? ORDER BY rowid", (run_id,))} if include_sources else {}
        adopted = conn.execute("SELECT 1 FROM lifecycle_investigation_acceptances WHERE run_id=?", (run_id,)).fetchone() is not None
        return {**row, "binding": binding, "steps": steps, "sources": sources, "adopted": adopted,
            "calls": [dict(item) for item in conn.execute("SELECT call_id,remote_id,terminal FROM lifecycle_investigation_calls WHERE run_id=? ORDER BY rowid", (run_id,))],
            "result": None if saved is None else _decoded(saved["payload_json"], saved["payload_sha256"]),
            "result_sha256": None if saved is None else saved["payload_sha256"]}

    def read(self, run_id, *, include_sources=True):
        with self.connection() as conn:
            return self.read_on_connection(conn, run_id, include_sources=include_sources)

    def latest(self, ticker):
        with self.connection() as conn:
            row = conn.execute("SELECT run_id FROM lifecycle_investigation_jobs WHERE ticker=? ORDER BY rowid DESC LIMIT 1", (ticker,)).fetchone()
        return None if row is None else self.read(row[0], include_sources=False)

    def control(self, run_id, *, owner):
        row = self.read(run_id, include_sources=False)
        return InvestigationControl(self, run_id, owner, ExecutionSelection(**row["binding"]["selection"]), row["binding"]["runtime"])


class InvestigationControl(RunControl):
    def __init__(self, store, run_id, owner, selection, runtime):
        super().__init__(selection=selection, max_model_requests=runtime["model_submissions"])
        self.store, self.run_id, self.owner, self.web_limit = store, run_id, owner, runtime["web_actions"]

    def _record(self, method, **kwargs):
        try:
            method(self.run_id, owner=self.owner, **kwargs)
        except BaseException:
            self.request_stop()
            raise

    def reserve_model_request(self, call_id):
        super().reserve_model_request(call_id)
        self._record(self.store.reserve_call, call_id=call_id)

    def bind_remote_id(self, call_id, remote_id):
        super().bind_remote_id(call_id, remote_id)
        self._record(self.store.bind_call, call_id=call_id, remote_id=remote_id)

    def observe_terminal(self, call_id, *, response_id, status, selection):
        super().observe_terminal(call_id, response_id=response_id, status=status, selection=selection)
        self._record(self.store.bind_call, call_id=call_id, remote_id=response_id, terminal=status)

    def observe_web_action(self, call_id, item_id, kind):
        before = sum(self.observed_web_actions.values())
        super().observe_web_action(call_id, item_id, kind)
        count = sum(self.observed_web_actions.values())
        if count != before:
            self._record(self.store.step, kind="web_action", payload={"call_id": call_id, "item_id": item_id, "kind": kind})
        if count > self.web_limit:
            self.request_stop()
            raise ValueError("investigation_budget_exhausted")
