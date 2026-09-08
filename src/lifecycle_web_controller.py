"""Explicit local workers; the journal, not this registry, owns durable status."""

import asyncio
from dataclasses import dataclass
import math
from threading import Event, RLock, Thread
from uuid import uuid4

from src.auth_drivers.lifecycle_web_models import WebModelError
from src.auth_drivers.lifecycle_web_usage import phase_usage, project_usage_report, validate_usage_report
from src.lifecycle_public_sources import SourceReadError
from src.lifecycle_web_projection import project_web_run
from src.lifecycle_web_store import RUNNING, WebJournalError
from src.model_routing import ModelRouteUnavailable
from src.security_lifecycle_web_contract import WebContractError
from src.security_lifecycle_web_pipeline import investigate


def _failure_code(exc):
    if isinstance(exc, (WebModelError, WebJournalError, WebContractError, SourceReadError, ModelRouteUnavailable)):
        value = str(exc)
        if value and len(value) <= 100 and all(character in "abcdefghijklmnopqrstuvwxyz_" for character in value):
            return value
    return "web_execution_failed"


@dataclass
class _Worker:
    control: object
    thread: Thread | None = None
    failure: str | None = None


class LifecycleWebController:
    def __init__(self, store, *, credential_loader, before_dispatch=lambda: None,
                 runner=investigate, reader_factory=None, heartbeat_seconds=2.0):
        if not math.isfinite(heartbeat_seconds) or not 0 < heartbeat_seconds < 30:
            raise ValueError("web_heartbeat_interval")
        self.store = store
        self.credential_loader = credential_loader
        self.before_dispatch = before_dispatch
        self.runner = runner
        self.reader_factory = reader_factory
        self.heartbeat_seconds = heartbeat_seconds
        self.owner = "worker-" + uuid4().hex
        self._lock = RLock()
        self._workers = {}
        self._closed = False

    def reconcile(self):
        self.store.recover_expired(at=self.store._now())

    def start(self, **request):
        with self._lock:
            if self._closed:
                raise WebModelError("web_worker_unavailable")
            self.before_dispatch()
            self.reconcile()
            # No unbounded pending queue whose lease expires before dispatch.
            if len(self._workers) >= 2:
                raise WebModelError("web_worker_busy")
            result = self.store.start(**request, owner=self.owner)
            if not result["created"]:
                return result
            identity = result["run_id"]
            control = self.store.control(identity, owner=self.owner)
            worker = _Worker(control)
            worker.thread = Thread(target=self._execute, args=(identity, worker), name="lifecycle-web", daemon=True)
            self._workers[identity] = worker
            try:
                worker.thread.start()
            except BaseException:
                self._workers.pop(identity, None)
                self.store.fail(identity, owner=self.owner, code="web_worker_unavailable", control=control)
                raise
            return result

    def _execute(self, identity, worker):
        heartbeat_done = Event()
        usage_phases = []

        def reply(call, value):
            if call.selection != worker.control.selection:
                raise WebModelError("execution_identity_changed")
            candidate = {"version": 1, "phases": [*usage_phases, phase_usage(call, value)]}
            with self.store.connection() as conn:
                calls = self.store._calls(conn, identity)
                candidate = validate_usage_report(candidate, calls)
                project_usage_report(candidate, calls)
            usage_phases[:] = candidate["phases"]

        def heartbeat():
            while not heartbeat_done.wait(self.heartbeat_seconds):
                try:
                    if self.store.heartbeat(identity, owner=self.owner):
                        worker.control.request_stop()
                except Exception as exc:
                    worker.failure = _failure_code(exc)
                    worker.control.request_stop()
                    return

        def phase(value):
            if value != "completed":
                self.before_dispatch()
                self.store.set_phase(identity, owner=self.owner, phase=value)

        heart = Thread(target=heartbeat, name="lifecycle-web-lease", daemon=True)
        try:
            row = self.store.read(identity)
            if self.store.heartbeat(identity, owner=self.owner):
                worker.control.request_stop()
                raise WebModelError("stop_requested")
            self.before_dispatch()
            if worker.control.stop_state != "running":
                raise WebModelError("stop_requested")
            heart.start()
            credential = self.credential_loader(row["selection"])
            if credential.selection != row["selection"]:
                raise WebModelError("execution_identity_changed")
            if row.get("credential_generation") is not None and row["credential_generation"] != credential.generation:
                raise WebModelError("selected_credential_changed")
            if worker.control.stop_state != "running":
                raise WebModelError("stop_requested")
            kwargs = {} if self.reader_factory is None else {"reader_factory": self.reader_factory}
            result = asyncio.run(self.runner(
                row["request"], credential, worker.control, options=row["options"], on_stage=phase,
                on_reply=reply,
                on_source=lambda source_id, page: self.store.add_page(identity, owner=self.owner, source_id=source_id, page=page),
                **kwargs,
            ))
            if worker.failure or worker.control.stop_state != "running":
                raise WebModelError(worker.failure or "stop_requested")
            self.store.complete(identity, owner=self.owner, payload=result.finding.finding.model_dump(),
                                source_failures=result.source_failures, usage=result.usage, source_requests=result.source_requests,
                                source_context=result.source_context, source_read_report=result.source_read_report,
                                source_failure_urls=result.source_failure_urls,
                                usage_report={"version": 1, "phases": usage_phases} if usage_phases else None)
        except BaseException as exc:
            worker.control.request_stop()
            try:
                self.store.fail(identity, owner=self.owner, code=worker.failure or _failure_code(exc), control=worker.control,
                                source_read_report=getattr(exc, "source_read_report", None),
                                usage_report={"version": 1, "phases": usage_phases})
            except Exception:
                # A failed write cannot manufacture success. Lease expiry is the
                # durable fallback; readback will explicitly show interruption.
                pass
        finally:
            heartbeat_done.set()
            if heart.ident is not None:
                heart.join()
            with self._lock:
                self._workers.pop(identity, None)

    def is_local_running(self, identity):
        with self._lock:
            return identity in self._workers

    def read(self, identity):
        return project_web_run(self.store.read(identity, include_running_sources=False), at=self.store._now())

    def latest(self, case_id):
        with self.store.connection() as conn:
            row = conn.execute("SELECT run_id FROM lifecycle_web_runs WHERE case_id=? ORDER BY rowid DESC LIMIT 1", (case_id,)).fetchone()
        return None if row is None else self.read(row[0])

    def cancel(self, identity):
        # Stop locally even if recording this request fails; do not claim that
        # an unavailable journal contains the cancellation acknowledgement.
        with self._lock:
            worker = self._workers.get(identity)
            if worker is not None:
                worker.control.request_stop()
        self.store.request_cancel(identity)
        return self.read(identity)

    def close(self):
        with self._lock:
            self._closed = True
            workers = list(self._workers.items())
            for _, worker in workers:
                worker.control.request_stop()
        for identity, _ in workers:
            try:
                self.store.request_cancel(identity)
            except Exception:
                # The already-signalled worker still owns remote cleanup. An
                # unavailable journal must not bypass joining that worker.
                pass
        for _, worker in workers:
            worker.thread.join()
