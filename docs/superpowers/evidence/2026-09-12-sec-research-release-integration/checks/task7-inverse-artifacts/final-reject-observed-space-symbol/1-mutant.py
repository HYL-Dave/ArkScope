"""Bounded current-universe recent catalog/facts acquisition, without documents."""

from dataclasses import dataclass
from contextlib import ExitStack
import time
from uuid import uuid4

from data_sources.sec_transport import SecTransportFailure
from .capture_lock import research_operation
from .common import SourceError
from .issuers import parse_issuer
from .schedule_store import FORMS, MAX_MEMBERS, ScheduleStore, normalize_member, receipt_counts
from .service import ResearchService, _storage_code


@dataclass(frozen=True)
class Limits:
    max_issuers: int = 500
    max_requests: int = 1001
    wall_seconds: float = 900

    def __post_init__(self):
        if (type(self.max_issuers) is not int or not 1 <= self.max_issuers <= 500
                or type(self.max_requests) is not int or not 1 <= self.max_requests <= 1001
                or type(self.wall_seconds) not in (int, float) or not 0 < self.wall_seconds <= 900):
            raise ValueError("sec_schedule_limits_invalid")


def run_current_universe(*, universe_reader, issuer_resolver, service, limits, clock,
                         progress_cb=None, check=None):
    if not isinstance(limits, Limits):
        raise ValueError("sec_schedule_limits_invalid")
    with research_operation(service.store.paths.capture_root):
        batches = ScheduleStore(service.store)
        previous = batches.status()["last_attempt"]
        start = clock()
        batch = dict(batch_id=uuid4().hex, status="running", started_at=service.clock(),
            finished_at=None, acquired_at=None, universe_tickers=[], universe_status="unknown",
            rotation=previous["rotation"] if previous else [], scope="recent", forms=list(FORMS),
            attempted_ciks=[], confirmed_ciks=[], failed_ciks=[], deferred_ciks=[],
            unresolved=[], outcomes=[], request_count=0, filing_count=0, fact_count=0,
            gaps=[], stop_reason=None, elapsed_seconds=0, issuer_map_observation_id=None)

        def persist():
            batch["elapsed_seconds"] = max(0, clock() - start)
            return batches.record(batch)

        def checkpoint():
            if clock() - start >= limits.wall_seconds:
                batch["stop_reason"] = "deadline"
                raise SecTransportFailure("sec_request_cancelled")
            if check is not None:
                try:
                    check()
                except Exception:
                    batch["stop_reason"] = "cancelled"
                    raise SecTransportFailure("sec_request_cancelled") from None

        class BatchTransport:
            def get(self, url, **kwargs):
                checkpoint()
                if batch["request_count"] >= limits.max_requests:
                    batch["stop_reason"] = "request_limit"
                    raise SecTransportFailure("sec_request_budget_exhausted")
                # Admission is not HTTP confirmation. Keep transport's 16 MiB
                # per-response bound, no batch-wide default byte budget.
                batch["request_count"] += 1
                persist()
                return service.transport.get(url, **dict(kwargs, check=checkpoint,
                    timeout=min(30, max(0.001, limits.wall_seconds - (clock() - start)))))

        transport = BatchTransport()
        persist()
        try:
            members = universe_reader()
            if not isinstance(members, (list, tuple)) or len(members) > MAX_MEMBERS:
                raise ValueError("active_universe_invalid")
            normalized = []
            for member in members:
                parse_issuer(member)
                normalized.append(normalize_member(member))
            batch["universe_tickers"] = sorted(set(normalized))
            batch["universe_status"] = "available"
            active = set(batch["universe_tickers"])
            batch["rotation"] = [dict(cik=row["cik"], tickers=sorted(set(row["tickers"]) & active))
                for row in batch["rotation"] if set(row["tickers"]) & active]
        except Exception:
            batch.update(status="failed", universe_status="unavailable",
                         gaps=[{"code": "active_universe_unavailable"}])
        else:
            try:
                _collect(batch, previous, issuer_resolver, service, transport, limits,
                         checkpoint, persist, progress_cb)
            except Exception as exc:
                batch["gaps"].append({"code": _storage_code(exc)})
            acquired = any(row["completed_sources"] for row in batch["outcomes"])
            incomplete = (batch["failed_ciks"] or batch["deferred_ciks"] or batch["unresolved"]
                          or batch["gaps"] or batch["stop_reason"])
            batch["status"] = ("partial" if acquired else "failed") if incomplete else "succeeded"
        batch["finished_at"] = service.clock()
        return persist()


def _collect(batch, previous, resolver, service, transport, limits, check, persist, progress):
    members = batch["universe_tickers"]
    resolvable = []
    needs_map = False
    for member in members:
        try:
            kind, _ = parse_issuer(member)
        except SourceError:
            batch["unresolved"].append(dict(ticker=member, candidates=[], code="sec_issuer_invalid"))
        else:
            resolvable.append(member)
            needs_map = needs_map or kind == "ticker"
    if needs_map:
        observation = resolver.refresh(transport, service.captures, clock=service.clock, check=check)
        batch["issuer_map_observation_id"] = observation["observation_id"]
    current = {}
    for member in resolvable:
        resolution = resolver.resolve(member)
        if resolution["status"] != "ok":
            batch["unresolved"].append(dict(ticker=member, candidates=resolution["candidates"],
                code=resolution["gaps"][0]["code"]))
        else:
            current.setdefault(resolution["cik"], []).append(member)
    # Keep surviving members in their old rotation position, then append new
    # CIKs. Every attempted member moves behind those waiting, even on failure.
    queue = [row["cik"] for row in previous["rotation"] if row["cik"] in current] if previous else []
    queue.extend(cik for cik in sorted(current) if cik not in queue)
    unresolved = {row["ticker"] for row in batch["unresolved"]}
    # A failed map is not evidence that pending CIKs vanished. Retain only
    # current unresolved tickers in rotation, but never dispatch stale CIKs.
    rotation = []
    for row in batch["rotation"]:
        tickers = current.get(row["cik"], sorted(set(row["tickers"]) & unresolved))
        if tickers:
            rotation.append(dict(cik=row["cik"], tickers=tickers))
    retained = {row["cik"] for row in rotation}
    rotation.extend(dict(cik=cik, tickers=current[cik]) for cik in queue if cik not in retained)
    batch["rotation"] = rotation
    batch["deferred_ciks"] = list(queue)
    persist()
    research = ResearchService(service.store, service.captures, transport, clock=service.clock)
    for cik in queue:
        if len(batch["attempted_ciks"]) >= limits.max_issuers:
            batch["stop_reason"] = "issuer_limit"
            break
        try:
            check()
        except SecTransportFailure:
            break
        if batch["request_count"] >= limits.max_requests:
            batch["stop_reason"] = "request_limit"
            break
        batch["attempted_ciks"].append(cik)
        batch["deferred_ciks"].remove(cik)
        row = next(row for row in batch["rotation"] if row["cik"] == cik)
        batch["rotation"].remove(row)
        batch["rotation"].append(row)
        persist()
        try:
            receipt = research.refresh(cik, scope="recent", max_sources=2, check=check)
        except Exception as exc:
            code = "sec_research_refresh_busy" if str(exc) == "sec_research_refresh_busy" else _storage_code(exc)
            batch["outcomes"].append(dict(cik=cik, receipt_id=None, status="unavailable",
                completed_sources=0, filing_count=0, fact_count=0))
            batch["failed_ciks"].append(cik)
            batch["gaps"].append(dict(cik=cik, code=code))
            persist()
            if progress is not None:
                progress(len(batch["attempted_ciks"]), len(queue), cik)
            continue
        outcome = dict(cik=cik, receipt_id=receipt["receipt_id"], status=receipt["status"],
                       completed_sources=len(receipt["completed"]), filing_count=0, fact_count=0)
        for key, count in receipt_counts(service.store, receipt).items():
            outcome[key] = count
            batch[key] += count
        batch["outcomes"].append(outcome)
        if receipt["status"] == "ok":
            batch["confirmed_ciks"].append(cik)
            batch["acquired_at"] = service.clock()
        else:
            batch["failed_ciks"].append(cik)
        batch["gaps"].extend(dict(cik=cik, **gap) for gap in receipt["gaps"])
        if any(gap["code"] in {"capture_budget_exceeded", "storage_space_insufficient",
                               "capture_store_write_failed"} for gap in receipt["gaps"]):
            batch["stop_reason"] = next(gap["code"] for gap in receipt["gaps"])
        persist()
        if progress is not None:
            progress(len(batch["attempted_ciks"]), len(queue), cik)
        if batch["stop_reason"]:
            break


def run_incremental(*, progress_cb=None):
    """Compose lazy profile-owned acquisition; an empty universe needs no SEC identity."""
    from . import runtime
    from .paths import SecResearchPaths
    from .store import Store
    from .issuer_store import IssuerStore
    from src.universe_scope import resolve_active_universe

    store = Store(SecResearchPaths.resolve())
    runtime.require_acquisition("sec_research_filings")
    with research_operation(store.paths.capture_root), ExitStack() as stack:
        store.install()
        acquired = None

        def sources():
            nonlocal acquired
            if acquired is None:
                acquired = stack.enter_context(runtime._acquisition(store))
            return acquired

        class LazySources:
            def preflight(self):
                return sources()[0].preflight()

            def put(self, body):
                return sources()[0].put(body)

            def get(self, url, **kwargs):
                return sources()[1].get(url, **kwargs)

        lazy = LazySources()
        return run_current_universe(universe_reader=resolve_active_universe,
            issuer_resolver=IssuerStore(store), service=ResearchService(store, lazy, lazy),
            limits=Limits(), clock=time.monotonic, progress_cb=progress_cb)
