"""Background execution with a durable journal; reopening never redispatches."""

import asyncio
from threading import Event, Thread

from src.auth_drivers.lifecycle_web_models import WebModelError
from src.lifecycle_investigation.agent import AgentFailure, run_agent
from src.lifecycle_investigation.runtime import InvestigationRuntime
from src.lifecycle_investigation.store import safe_code
from src.lifecycle_investigation.target import Target
from src.lifecycle_web_controller import LifecycleWebController
from src.security_lifecycle_provider_snapshot import instant
from src.security_lifecycle_web_contract import ExecutionSelection


def project_job(row, *, at):
    binding = row["binding"]
    result = row["result"]
    status, failure = row["status"], row["failure_code"]
    if status == "running" and instant(row["lease_until"]) <= instant(at):
        status = "remote_outcome_unknown" if any(call["terminal"] is None for call in row["calls"]) else "failed"
        failure = "remote_outcome_unknown" if status == "remote_outcome_unknown" else "worker_interrupted"
    stats = result["stats"] if result else {"model_submissions": len(row["calls"]),
        "web_actions": sum(step["kind"] == "web_action" for step in row["steps"]),
        "sources": sum(step["kind"] == "source_captured" for step in row["steps"]),
        "http_requests": sum(step["payload"]["http_requests"] for step in row["steps"] if step["kind"] == "source_read"),
        "source_reads": None, "local_queries": sum(step["kind"] == "local_search" for step in row["steps"]),
        "retained_source_bytes": None, "elapsed_seconds": max(0, (instant(at) - instant(row["created_at"])).total_seconds()),
        "input_tokens": None, "output_tokens": None}
    validated = result.get("validated") if result else None
    # Result quotations are already a closed projection of supplied passages.
    return {"version": 2, "run_id": row["run_id"], "ticker": row["ticker"], "status": status,
        "phase": row["phase"], "created_at": row["created_at"], "finished_at": row["finished_at"],
        "cancel_requested": row["cancel_requested_at"] is not None, "failure_code": failure,
        "stop_reason": None if result is None else result["stop_reason"], "target": binding["target"],
        "execution": {key: binding["selection"][key] for key in ("provider", "model", "auth_mode")} | {"effort": binding["effort"]},
        "stats": stats, "finding": None if validated is None else validated["finding"],
        "action": validated["action"] if validated is not None and status == "succeeded" and not row["adopted"] else None,
        "block_reasons": [] if validated is None else validated["block_reasons"],
        "passages": [] if validated is None else validated["passages"], "gaps": [] if result is None else result["gaps"],
        "steps": [{"ordinal": step["ordinal"], "kind": step["kind"], "at": step["at"],
                   "reason": step["payload"].get("reason") if step["kind"] == "agent_action" else None,
                   "code": step["payload"].get("code") if step["kind"].startswith("rejected_") else None}
                  for step in row["steps"]]}


class InvestigationController(LifecycleWebController):
    def __init__(self, store, *, credential_loader, news_factory, before_dispatch=lambda: None,
                 runner=run_agent, reader_factory=None, heartbeat_seconds=2):
        super().__init__(store, credential_loader=credential_loader, before_dispatch=before_dispatch,
            runner=runner, reader_factory=reader_factory, heartbeat_seconds=heartbeat_seconds)
        self.news_factory = news_factory

    def reconcile(self):
        self.store.recover()

    def read(self, identity):
        return project_job(self.store.read(identity, include_sources=False), at=self.store._now())

    def latest(self, ticker):
        row = self.store.latest(ticker)
        return None if row is None else project_job(row, at=self.store._now())

    def _execute(self, identity, worker):
        heartbeat_done = Event()

        def heartbeat():
            while not heartbeat_done.wait(self.heartbeat_seconds):
                try:
                    if self.store.heartbeat(identity, owner=self.owner):
                        worker.control.request_stop()
                except Exception as exc:
                    worker.failure = safe_code(exc)
                    worker.control.request_stop()
                    return

        def step(kind, payload):
            self.before_dispatch()
            self.store.step(identity, owner=self.owner, kind=kind, payload=payload)

        heart = Thread(target=heartbeat, name="lifecycle-investigation-lease", daemon=True)
        try:
            row = self.store.read(identity)
            binding = row["binding"]
            self.before_dispatch()
            if self.store.heartbeat(identity, owner=self.owner):
                worker.control.request_stop()
                raise WebModelError("stop_requested")
            heart.start()
            selected = ExecutionSelection(**binding["selection"])
            credential = self.credential_loader(selected)
            if credential.selection != selected or credential.generation != binding["credential_generation"]:
                raise WebModelError("selected_credential_changed")
            self.before_dispatch()
            if worker.control.stop_state != "running":
                raise WebModelError("stop_requested")
            kwargs = {} if self.reader_factory is None else {"reader_factory": self.reader_factory}
            result = asyncio.run(self.runner(Target.model_validate(binding["target"]), credential, worker.control,
                runtime=InvestigationRuntime.model_validate(binding["runtime"]), effort=binding["effort"],
                news=self.news_factory(), provider_observations=binding["provider_observations"], language=binding["language"],
                on_step=step, on_source=lambda key, value: self.store.source(identity, owner=self.owner, source_id=key, payload=value), **kwargs))
            if worker.failure or worker.control.stop_state != "running":
                raise WebModelError(worker.failure or "stop_requested")
            self.store.finish(identity, owner=self.owner, status=result["status"], payload=result)
        except BaseException as exc:
            worker.control.request_stop()
            try:
                code = worker.failure or safe_code(exc)
                status = "cancelled" if code == "stop_requested" else "failed"
                self.store.finish(identity, owner=self.owner, status=status, failure_code=code,
                    payload=exc.result if isinstance(exc, AgentFailure) else None)
            except Exception:
                # Lease readback remains interrupted, never success, if recording is unavailable.
                pass
        finally:
            heartbeat_done.set()
            if heart.ident is not None:
                heart.join()
            with self._lock:
                self._workers.pop(identity, None)
