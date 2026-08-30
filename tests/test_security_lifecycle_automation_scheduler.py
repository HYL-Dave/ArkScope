"""Tests for the bounded lifecycle-automation scheduler boundary."""

from __future__ import annotations

import builtins
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest


_NOW = datetime(2026, 8, 25, 13, 0, tzinfo=timezone.utc)


def _summary(**overrides):
    result = {
        "status": "succeeded",
        "reason": None,
        "selected": 0,
        "processed": 0,
        "accepted": 0,
        "drafted": 0,
        "blocked": 0,
        "failed": 0,
        "skipped_current": 0,
        "case_ids": [],
    }
    result.update(overrides)
    return result


def _v2_summary(*, case_outcomes=None, **overrides):
    result = _summary(**overrides)
    result["result_version"] = 2
    result["case_outcomes"] = dict(case_outcomes or {})
    return result


@pytest.fixture(autouse=True)
def _installed_scheduler_profile(tmp_path, monkeypatch):
    from src.security_lifecycle_investigation import (
        SecurityLifecycleInvestigationStore,
    )

    profile_path = tmp_path / "installed-profile-state.db"
    conn = sqlite3.connect(profile_path)
    try:
        SecurityLifecycleInvestigationStore(conn)
    finally:
        conn.close()
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))


def _running_run(db_path: Path, *, execution_owner_id: str):
    from src.security_lifecycle_fact_kernel import SecurityLifecycleFactKernel
    from src.security_lifecycle_investigation import (
        SecurityLifecycleInvestigationStore,
    )

    conn = sqlite3.connect(db_path, check_same_thread=False)
    store = SecurityLifecycleInvestigationStore(conn)
    case_id = store.ensure_case(
        source="sec_edgar",
        source_ref="0001409970-26-000131",
        ticker="HAPN",
        at="2026-08-25T13:00:00Z",
    )
    claim = SecurityLifecycleFactKernel(store).reserve_run(
        case_id=case_id,
        observation_fingerprint_sha256="a" * 64,
        policy_version="trusted-lifecycle-v1",
        mode="live",
        execution_revision="trusted-lifecycle-execution-r1",
        execution_owner_id=execution_owner_id,
        query_context={"case_id": case_id, "ticker": "HAPN"},
        diagnostics={},
        at="2026-08-25T13:00:00Z",
    )
    return conn, store, claim


def _patch_provider_free_empty_worker(monkeypatch, scheduler, calls):
    class Transport:
        def close(self):
            pass

    class Session:
        def __init__(self, **_kwargs):
            pass

        def close(self):
            pass

    class Worker:
        def __init__(self, execution_owner_id):
            self.execution_owner_id = execution_owner_id

        def run(self, limit, mode):
            calls.append((self.execution_owner_id, limit, mode))
            return _v2_summary()

    monkeypatch.setattr(scheduler, "ListingAuthorityTransport", Transport)
    monkeypatch.setattr(scheduler, "ListingAuthoritySession", Session)
    monkeypatch.setattr(scheduler, "provider_field_env_value", lambda *_args: None)
    monkeypatch.setattr(
        scheduler,
        "_worker",
        lambda *, execution_owner_id, **_kwargs: Worker(execution_owner_id),
    )


def test_lock_owner_blocks_a_second_connection_then_release_enables_reconciliation(
    tmp_path,
    monkeypatch,
):
    from src.security_lifecycle_investigation import (
        SecurityLifecycleInvestigationStore,
    )
    from src.service import security_lifecycle_automation_scheduler as scheduler
    from src.service.security_lifecycle_automation_runtime import (
        lifecycle_automation_execution_lock,
    )

    db_path = tmp_path / "profile_state.db"
    lock_path = tmp_path / "locks"
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(db_path))
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(lock_path))
    calls = []
    _patch_provider_free_empty_worker(monkeypatch, scheduler, calls)

    first_conn = None
    second_conn = None
    try:
        with lifecycle_automation_execution_lock() as owner:
            first_conn, first_store, claim = _running_run(
                db_path,
                execution_owner_id=owner.execution_owner_id,
            )
            second_conn = sqlite3.connect(db_path, check_same_thread=False)
            SecurityLifecycleInvestigationStore(second_conn)

            @contextmanager
            def second_profile_connection():
                yield second_conn

            monkeypatch.setattr(
                scheduler,
                "_profile_connection",
                second_profile_connection,
            )
            busy = scheduler.run_security_lifecycle_automation(now=_NOW)

            assert busy == _v2_summary(status="skipped", reason="already_running")
            assert calls == []
            assert first_store.get_automation_run(claim.run_id)["status"] == "running"

        recovered = scheduler.run_security_lifecycle_automation(now=_NOW)
        row = first_store.get_automation_run(claim.run_id)
        assert recovered == _v2_summary()
        assert len(calls) == 1
        assert row["status"] == "failed"
        assert row["failure_code"] == "internal_error"
        assert json.loads(row["diagnostics_json"]) == {
            "interrupted_execution": 1,
        }
    finally:
        if second_conn is not None:
            second_conn.close()
        if first_conn is not None:
            first_conn.close()


def test_recorded_runner_persists_result_before_releasing_execution_lock(
    monkeypatch,
):
    from src.service import security_lifecycle_automation_scheduler as scheduler

    events = []
    lock_held = False

    @contextmanager
    def execution_lock():
        nonlocal lock_held
        lock_held = True
        events.append("lock_acquired")
        try:
            yield SimpleNamespace(execution_owner_id="record-owner")
        finally:
            events.append("lock_released")
            lock_held = False

    result = _v2_summary()
    monkeypatch.setattr(
        scheduler,
        "lifecycle_automation_execution_lock",
        execution_lock,
    )
    monkeypatch.setattr(scheduler, "_reconcile_running_rows", lambda **_kwargs: ())
    monkeypatch.setattr(
        scheduler,
        "_run_owned_automation_batch",
        lambda **_kwargs: events.append("worker") or result,
    )

    def record(value, *, now):
        assert lock_held is True
        assert value == result
        assert now == _NOW
        events.append("record")
        return True

    monkeypatch.setattr(
        scheduler,
        "record_security_lifecycle_automation_result",
        record,
    )

    assert scheduler.run_and_record_security_lifecycle_automation(
        limit=1,
        now=_NOW,
    ) == result
    assert events == ["lock_acquired", "worker", "record", "lock_released"]


def test_dispatch_acquires_ownership_before_return_and_transfers_exact_lease(
    monkeypatch,
):
    from src.service import security_lifecycle_automation_scheduler as scheduler

    events = []
    pending = []
    lock_held = False

    @contextmanager
    def execution_lock():
        nonlocal lock_held
        lock_held = True
        lease = SimpleNamespace(execution_owner_id="dispatch-owner")
        events.append(("lock_acquired", lease))
        try:
            yield lease
        finally:
            events.append(("lock_released", lease))
            lock_held = False

    class DeferredThread:
        def __init__(self, *, target, kwargs, **_ignored):
            pending.append((target, kwargs))

        def start(self):
            events.append(("thread_started", None))

    result = _v2_summary()
    monkeypatch.setattr(
        scheduler,
        "lifecycle_automation_execution_lock",
        execution_lock,
    )
    monkeypatch.setattr(scheduler.threading, "Thread", DeferredThread)
    monkeypatch.setattr(
        scheduler,
        "_reconcile_running_rows",
        lambda **kwargs: events.append(("reconcile", kwargs)),
    )
    monkeypatch.setattr(
        scheduler,
        "_run_owned_automation_batch",
        lambda **kwargs: events.append(("worker", kwargs)) or result,
    )

    def record(value, *, now):
        assert lock_held is True
        assert value == result
        assert now == _NOW
        events.append(("record", value))

    monkeypatch.setattr(
        scheduler,
        "record_security_lifecycle_automation_result",
        record,
    )

    dispatched = scheduler.dispatch_and_record_security_lifecycle_automation(
        limit=1,
        now=_NOW,
        target_case_id="slc_attended",
        allow_new_attempt=True,
    )

    assert dispatched == {"status": "started"}
    assert lock_held is True
    assert [event[0] for event in events] == ["lock_acquired", "thread_started"]
    assert len(pending) == 1

    target, kwargs = pending.pop()
    target(**kwargs)

    assert lock_held is False
    assert [event[0] for event in events] == [
        "lock_acquired",
        "thread_started",
        "reconcile",
        "worker",
        "reconcile",
        "record",
        "lock_released",
    ]
    worker_kwargs = next(value for name, value in events if name == "worker")
    assert worker_kwargs == {
        "limit": 1,
        "at": "2026-08-25T13:00:00Z",
        "execution_owner_id": "dispatch-owner",
        "target_case_id": "slc_attended",
        "allow_new_attempt": True,
    }


def test_dispatch_thread_start_failure_releases_transferred_ownership(
    monkeypatch,
):
    from src.service import security_lifecycle_automation_scheduler as scheduler

    events = []
    retained_contexts = []

    @contextmanager
    def execution_lock():
        events.append("lock_acquired")
        try:
            yield SimpleNamespace(execution_owner_id="start-failure-owner")
        finally:
            events.append("lock_released")

    class FailingThread:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            raise RuntimeError("thread start failed")

    def retained_execution_lock():
        context = execution_lock()
        retained_contexts.append(context)
        return context

    monkeypatch.setattr(
        scheduler,
        "lifecycle_automation_execution_lock",
        retained_execution_lock,
    )
    monkeypatch.setattr(scheduler.threading, "Thread", FailingThread)

    with pytest.raises(RuntimeError, match="thread start failed"):
        scheduler.dispatch_and_record_security_lifecycle_automation(now=_NOW)

    assert events == ["lock_acquired", "lock_released"]


def test_scheduled_runner_grants_only_due_failed_retry_authority(monkeypatch):
    from src.service import security_lifecycle_automation_scheduler as scheduler

    captured = []

    class Worker:
        def run(self, limit, mode):
            captured.append(("run", limit, mode))
            return _v2_summary()

    @contextmanager
    def listing_session(*, at):
        captured.append(("listing", at))
        yield object()

    def worker(**kwargs):
        captured.append(("worker", kwargs))
        return Worker()

    monkeypatch.setattr(scheduler, "_listing_authority_session", listing_session)
    monkeypatch.setattr(scheduler, "_worker", worker)

    assert scheduler._run_owned_automation_batch(
        limit=2,
        at="2026-08-25T13:00:00Z",
        execution_owner_id="scheduled-owner",
    ) == _v2_summary()
    worker_kwargs = next(item[1] for item in captured if item[0] == "worker")
    assert worker_kwargs["allow_due_failed_retry"] is True
    assert worker_kwargs["allow_new_attempt"] is False
    assert worker_kwargs["target_case_id"] is None


def test_recorded_attended_runner_targets_one_case_and_grants_new_attempt_only(
    monkeypatch,
):
    from src.service import security_lifecycle_automation_scheduler as scheduler

    captured = []
    result = _v2_summary()
    monkeypatch.setattr(scheduler, "_reconcile_running_rows", lambda **_kwargs: ())

    def run_batch(**kwargs):
        captured.append(kwargs)
        return result

    monkeypatch.setattr(scheduler, "_run_owned_automation_batch", run_batch)
    monkeypatch.setattr(
        scheduler,
        "record_security_lifecycle_automation_result",
        lambda value, *, now: value == result and now == _NOW,
    )

    assert scheduler.run_and_record_security_lifecycle_automation(
        limit=1,
        now=_NOW,
        target_case_id="slc_attended",
        allow_new_attempt=True,
    ) == result
    assert captured == [
        {
            "limit": 1,
            "at": "2026-08-25T13:00:00Z",
            "execution_owner_id": captured[0]["execution_owner_id"],
            "target_case_id": "slc_attended",
            "allow_new_attempt": True,
        }
    ]


@pytest.mark.parametrize("failure_point", ("startup", "final"))
def test_recorded_runner_persists_reconciliation_failure_while_lock_is_held(
    monkeypatch,
    failure_point,
):
    from src.service import security_lifecycle_automation_scheduler as scheduler

    events = []
    lock_held = False

    @contextmanager
    def execution_lock():
        nonlocal lock_held
        lock_held = True
        events.append("lock_acquired")
        try:
            yield SimpleNamespace(execution_owner_id="reconcile-owner")
        finally:
            events.append("lock_released")
            lock_held = False

    reconcile_calls = 0

    def reconcile(**_kwargs):
        nonlocal reconcile_calls
        reconcile_calls += 1
        events.append(f"reconcile_{reconcile_calls}")
        if failure_point == "startup" or reconcile_calls == 2:
            raise RuntimeError("private reconciliation detail")

    monkeypatch.setattr(scheduler, "lifecycle_automation_execution_lock", execution_lock)
    monkeypatch.setattr(scheduler, "_reconcile_running_rows", reconcile)
    monkeypatch.setattr(
        scheduler,
        "_run_owned_automation_batch",
        lambda **_kwargs: events.append("worker") or _v2_summary(),
    )

    def record(value, *, now):
        assert lock_held is True
        assert value == _v2_summary(
            status="unavailable",
            reason="automation_scheduler_failed",
        )
        assert now == _NOW
        events.append("record")
        return True

    monkeypatch.setattr(
        scheduler,
        "record_security_lifecycle_automation_result",
        record,
    )

    result = scheduler.run_and_record_security_lifecycle_automation(
        limit=1,
        now=_NOW,
    )

    assert result == _v2_summary(
        status="unavailable",
        reason="automation_scheduler_failed",
    )
    assert events[-2:] == ["record", "lock_released"]
    assert ("worker" in events) is (failure_point == "final")


@pytest.mark.parametrize("failure_point", ("fcntl", "open"))
def test_lock_unavailable_never_reconciles_persisted_running_rows(
    failure_point,
    tmp_path,
    monkeypatch,
):
    from src.service import security_lifecycle_automation_scheduler as scheduler

    db_path = tmp_path / "profile_state.db"
    lock_root = tmp_path / "locks"
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(db_path))
    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(lock_root))
    conn, store, claim = _running_run(
        db_path,
        execution_owner_id="orphaned-owner",
    )
    monkeypatch.setattr(
        scheduler,
        "_worker",
        lambda **_kwargs: pytest.fail("worker reached without an execution lock"),
    )
    monkeypatch.setattr(
        scheduler,
        "ListingAuthorityTransport",
        lambda: pytest.fail("provider setup reached without an execution lock"),
    )

    if failure_point == "fcntl":
        real_import = builtins.__import__

        def without_fcntl(name, *args, **kwargs):
            if name == "fcntl":
                raise ImportError("test fcntl absence")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", without_fcntl)
    else:
        lock_root.write_text("not a directory", encoding="utf-8")

    try:
        result = scheduler.run_security_lifecycle_automation(now=_NOW)

        assert result == _v2_summary(
            status="unavailable",
            reason="execution_lock_unavailable",
        )
        assert store.get_automation_run(claim.run_id)["status"] == "running"
    finally:
        conn.close()


def _authority_evidence(
    evidence_id,
    *,
    adapter,
    ticker,
    market,
    listing_status,
    expected_active=True,
    directory=None,
    delisted_utc=None,
):
    locator = {
        "locator_kind": "listing_directory_snapshot",
        "adapter": adapter,
        "candidate_ticker": ticker,
        "expected_active_state": expected_active,
        "market": market,
        "listing_status": listing_status,
        "directory": directory,
    }
    if delisted_utc is not None:
        locator["delisted_utc"] = delisted_utc
    return SimpleNamespace(
        evidence_id=evidence_id,
        source_family="listing_authority",
        source_locator=locator,
        retrieved_at="2026-08-26T00:00:00Z",
    )


def _authority_fact(evidence_id, fact_type, value):
    return SimpleNamespace(
        evidence_id=evidence_id,
        fact_type=fact_type,
        normalized_value=value,
    )


def test_scheduler_runs_bounded_worker_batch_and_returns_sanitized_summary(
    monkeypatch,
):
    from src.service import security_lifecycle_automation_scheduler as scheduler

    calls = []

    class Worker:
        def run(self, limit, mode):
            calls.append((limit, mode))
            return {
                **_summary(
                    selected=2,
                    processed=2,
                    accepted=1,
                    drafted=1,
                    case_ids=["slc_a", "slc_b"],
                ),
                "private_payload": {
                    "url": "https://private.invalid",
                    "contact": "secret@example.invalid",
                },
            }

    monkeypatch.setattr(scheduler, "_worker", lambda **_kwargs: Worker())

    result = scheduler.run_security_lifecycle_automation(limit=2, now=_NOW)

    assert calls == [(2, "live")]
    assert result == _summary(
        selected=2,
        processed=2,
        accepted=1,
        drafted=1,
        case_ids=["slc_a", "slc_b"],
    )
    assert "private" not in json.dumps(result)


def test_scheduler_reports_schema_absent_as_not_installed(tmp_path, monkeypatch):
    from src.service import security_lifecycle_automation_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    real_worker = scheduler._worker

    class Worker:
        def run(self, limit, mode):
            del limit, mode
            raise scheduler.LifecycleAutomationNotInstalled()

    monkeypatch.setattr(scheduler, "_worker", lambda **_kwargs: Worker())

    result = scheduler.run_security_lifecycle_automation(now=_NOW)

    assert result == _v2_summary(
        status="not_installed",
        reason="automation_schema_absent",
    )
    profile_path = tmp_path / "missing" / "profile_state.db"
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    assert scheduler.record_security_lifecycle_automation_result(
        result,
        now=_NOW,
    )
    assert not profile_path.exists()

    pre_cutover_path = tmp_path / "pre-cutover.db"
    JobRunsLocalStore(pre_cutover_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(pre_cutover_path))
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(tmp_path / "market.db"))
    monkeypatch.setattr(scheduler, "_worker", real_worker)
    monkeypatch.setattr(
        scheduler,
        "_load_sources",
        lambda: (_ for _ in ()).throw(
            AssertionError("source loader reached before schema gate")
        ),
    )

    assert scheduler.run_security_lifecycle_automation(now=_NOW) == _v2_summary(
        status="not_installed",
        reason="automation_schema_absent",
    )


def test_failed_case_skipped_on_next_real_tick_does_not_record_recovery(
    tmp_path,
    monkeypatch,
):
    from src.scheduler_state import SchedulerStateStore
    from src.security_lifecycle_automation_worker import LifecycleAutomationWorker
    from src.security_lifecycle_investigation import (
        SecurityLifecycleInvestigationStore,
        case_id_for,
    )
    from src.service import security_lifecycle_automation_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    profile_path = tmp_path / "profile_state.db"
    telemetry = JobRunsLocalStore(profile_path)
    scheduler_state = SchedulerStateStore(profile_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    conn = sqlite3.connect(profile_path, check_same_thread=False)
    SecurityLifecycleInvestigationStore(conn)
    source_ref = "0000000001-26-000001"
    case_id = case_id_for("sec_edgar", source_ref, "FAIL")
    case = {
        "case_id": case_id,
        "source": "sec_edgar",
        "source_ref": source_ref,
        "ticker": "FAIL",
        "source_presence": "present",
        "observation_fingerprint_sha256": "a" * 64,
        "observation": {
            "ticker": "FAIL",
            "cik": "0000000001",
            "filing_date": "2026-08-25",
            "kinds": [{"event_type": "listing_status_review"}],
        },
    }

    @contextmanager
    def profile_connection():
        yield conn

    def worker(owner, evidence_loader):
        return LifecycleAutomationWorker(
            case_loader=lambda: (case,),
            profile_connection=profile_connection,
            evidence_loader=evidence_loader,
            source_loader=lambda: {"FAIL": ()},
            transition_preview=lambda **_kwargs: pytest.fail(
                "transition preview reached"
            ),
            transition_approver=lambda **_kwargs: pytest.fail(
                "transition approval reached"
            ),
            clock=lambda: "2026-08-25T13:00:00Z",
            execution_owner_id=owner,
        )

    first = worker(
        "failure-owner",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ValueError("source payload invalid")
        ),
    ).run(limit=1)
    persisted_run_id = SecurityLifecycleInvestigationStore(conn).list_automation_runs(
        case_id
    )[0]["run_id"]
    second = worker(
        "healthy-owner",
        lambda *_args, **_kwargs: pytest.fail(
            "failed semantic run must remain parked"
        ),
    ).run(limit=1)

    assert scheduler.record_security_lifecycle_automation_result(
        first,
        now=_NOW,
    )
    assert scheduler.record_security_lifecycle_automation_result(
        second,
        now=_NOW,
    )

    runs = telemetry.list_runs(job_name="security_lifecycle.automation", limit=10)
    assert first["case_outcomes"] == {case_id: "failed"}
    assert second["case_outcomes"] == {case_id: "skipped_current"}
    assert [(row["status"], row["message"]) for row in runs] == [
        ("failed", "security_lifecycle_automation_failure")
    ]
    state = scheduler_state.get("security_lifecycle.automation")
    assert state is not None
    assert state["last_result"]["active_incident"]["case_failures"] == {
        case_id: {"run_id": persisted_run_id, "recovery": "new_attempt"}
    }
    assert state["last_result"]["latest_result"] == scheduler._bounded_result(
        second
    )

    import src.security_lifecycle_automation_worker as worker_module
    from src.security_lifecycle_automation_worker import (
        LifecycleAutomationEvidenceBundle,
    )
    from src.security_lifecycle_fact_kernel import AutomationBlocker

    monkeypatch.setattr(
        worker_module,
        "AUTOMATION_EXECUTION_REVISION",
        "trusted-lifecycle-execution-r2",
    )
    repeated_failure = worker(
        "second-failure-owner",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ValueError("source payload invalid again")
        ),
    ).run(limit=1)
    repeated_run_id = SecurityLifecycleInvestigationStore(
        conn
    ).list_automation_runs(case_id)[0]["run_id"]
    assert repeated_run_id != persisted_run_id
    assert repeated_failure["case_outcomes"] == {case_id: "failed"}
    assert scheduler.record_security_lifecycle_automation_result(
        repeated_failure,
        now=_NOW,
    )
    repeated_runs = telemetry.list_runs(
        job_name="security_lifecycle.automation",
        limit=10,
    )
    assert [(row["status"], row["message"]) for row in repeated_runs] == [
        ("failed", "security_lifecycle_automation_failure")
    ]
    repeated_state = scheduler_state.get("security_lifecycle.automation")
    assert repeated_state is not None
    assert repeated_state["last_result"]["active_incident"]["case_failures"] == {
        case_id: {"run_id": repeated_run_id, "recovery": "new_attempt"}
    }

    monkeypatch.setattr(
        worker_module,
        "AUTOMATION_EXECUTION_REVISION",
        "trusted-lifecycle-execution-r3",
    )
    recovered_bundle = LifecycleAutomationEvidenceBundle(
        evidence=(),
        facts=(),
        blockers=(
            AutomationBlocker(
                code="sec_rate_limited",
                retryable=True,
                context={"attempts": 1},
            ),
        ),
        diagnostics={"sec_attempts": 1},
        retry_at="2026-08-26T13:00:00Z",
    )
    third = worker(
        "recovery-owner",
        lambda *_args, **_kwargs: recovered_bundle,
    ).run(limit=1)
    assert third["case_outcomes"] == {case_id: "blocked"}
    assert scheduler.record_security_lifecycle_automation_result(third, now=_NOW)

    recovered_runs = telemetry.list_runs(
        job_name="security_lifecycle.automation",
        limit=10,
    )
    assert [(row["status"], row["message"]) for row in recovered_runs] == [
        ("succeeded", "security_lifecycle_automation_recovered"),
        ("failed", "security_lifecycle_automation_failure"),
    ]
    recovered_state = scheduler_state.get("security_lifecycle.automation")
    assert recovered_state is not None
    assert recovered_state["last_result"]["active_incident"] is None
    conn.close()


def test_blocked_case_is_not_an_operational_failure_witness(
    tmp_path,
    monkeypatch,
):
    from src.scheduler_state import SchedulerStateStore
    from src.security_lifecycle_automation_worker import (
        LifecycleAutomationEvidenceBundle,
        LifecycleAutomationWorker,
    )
    from src.security_lifecycle_fact_kernel import AutomationBlocker
    from src.security_lifecycle_investigation import (
        SecurityLifecycleInvestigationStore,
        case_id_for,
    )
    from src.service import security_lifecycle_automation_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    profile_path = tmp_path / "profile_state.db"
    telemetry = JobRunsLocalStore(profile_path)
    scheduler_state = SchedulerStateStore(profile_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    conn = sqlite3.connect(profile_path, check_same_thread=False)
    SecurityLifecycleInvestigationStore(conn)
    source_ref = "0000000002-26-000002"
    case_id = case_id_for("sec_edgar", source_ref, "WAIT")
    case = {
        "case_id": case_id,
        "source": "sec_edgar",
        "source_ref": source_ref,
        "ticker": "WAIT",
        "source_presence": "present",
        "observation_fingerprint_sha256": "b" * 64,
        "observation": {
            "ticker": "WAIT",
            "cik": "0000000002",
            "filing_date": "2026-08-25",
            "kinds": [{"event_type": "listing_status_review"}],
        },
    }

    @contextmanager
    def profile_connection():
        yield conn

    bundle = LifecycleAutomationEvidenceBundle(
        evidence=(),
        facts=(),
        blockers=(
            AutomationBlocker(
                code="sec_rate_limited",
                retryable=True,
                context={"attempts": 1},
            ),
        ),
        diagnostics={"sec_attempts": 1},
        retry_at="2026-08-26T13:00:00Z",
    )
    result = LifecycleAutomationWorker(
        case_loader=lambda: (case,),
        profile_connection=profile_connection,
        evidence_loader=lambda *_args, **_kwargs: bundle,
        source_loader=lambda: {"WAIT": ()},
        transition_preview=lambda **_kwargs: pytest.fail(
            "transition preview reached"
        ),
        transition_approver=lambda **_kwargs: pytest.fail(
            "transition approval reached"
        ),
        clock=lambda: "2026-08-25T13:00:00Z",
        execution_owner_id="blocked-owner",
    ).run(limit=1)

    assert result["case_outcomes"] == {case_id: "blocked"}
    assert scheduler.record_security_lifecycle_automation_result(result, now=_NOW)
    assert telemetry.list_runs(
        job_name="security_lifecycle.automation",
        limit=10,
    ) == []
    state = scheduler_state.get("security_lifecycle.automation")
    assert state is not None
    assert state["last_error"] is None
    assert state["last_result"]["active_incident"] is None
    assert state["last_result"]["latest_result"] == scheduler._bounded_result(
        result
    )
    conn.close()


@pytest.mark.parametrize(
    "change",
    (
        {"selected": 2},
        {"failed": 0, "accepted": 1},
        {"case_ids": []},
        {"case_ids": [" slc_failed"]},
        {"case_outcomes": {"slc_failed": "blocked"}},
        {"case_outcomes": {"slc_failed": "failed", "extra": "skipped_current"}},
    ),
)
def test_bounded_v2_result_rejects_counter_and_outcome_drift(change):
    from src.service import security_lifecycle_automation_scheduler as scheduler

    value = _v2_summary(
        status="partial",
        reason="case_processing_failed",
        selected=1,
        processed=1,
        failed=1,
        case_ids=["slc_failed"],
        case_outcomes={"slc_failed": "failed"},
    )
    value.update(change)

    with pytest.raises(ValueError):
        scheduler._bounded_result(value)


def test_stored_result_reads_version_one_and_rejects_malformed_legacy_blobs():
    from src.service import security_lifecycle_automation_scheduler as scheduler

    case_failure = _summary(
        status="partial",
        reason="case_processing_failed",
        selected=1,
        processed=1,
        failed=1,
        case_ids=["legacy-case"],
    )
    scheduler_failure = _summary(
        status="unavailable",
        reason="automation_scheduler_failed",
    )
    assert scheduler._stored_result(json.dumps(case_failure)) == case_failure
    assert scheduler._stored_result(json.dumps(scheduler_failure)) == scheduler_failure
    assert scheduler._stored_result("not-json") is None
    assert scheduler._stored_result(json.dumps({"selected": 1})) is None


@pytest.mark.parametrize(
    ("status", "reason"),
    (
        ("succeeded", None),
        ("not_installed", "automation_schema_absent"),
        ("skipped", "already_running"),
        ("unavailable", "automation_scheduler_failed"),
    ),
)
def test_current_empty_result_producers_emit_version_two(status, reason):
    from src.service import security_lifecycle_automation_scheduler as scheduler

    result = scheduler._empty_summary(status=status, reason=reason)

    assert result["result_version"] == 2
    assert result["case_outcomes"] == {}
    assert scheduler._bounded_result(result) == result


def test_version_one_mixed_batch_reconstructs_only_the_failed_case_incident(
    tmp_path,
    monkeypatch,
):
    from src.scheduler_state import SchedulerStateStore
    from src.security_lifecycle_automation_worker import (
        LifecycleAutomationEvidenceBundle,
        LifecycleAutomationWorker,
    )
    from src.security_lifecycle_fact_kernel import AutomationBlocker
    from src.security_lifecycle_investigation import (
        SecurityLifecycleInvestigationStore,
        case_id_for,
    )
    from src.service import security_lifecycle_automation_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    profile_path = tmp_path / "profile_state.db"
    JobRunsLocalStore(profile_path)
    state_store = SchedulerStateStore(profile_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    conn = sqlite3.connect(profile_path, check_same_thread=False)
    SecurityLifecycleInvestigationStore(conn)

    def case(ticker, source_ref, fingerprint):
        return {
            "case_id": case_id_for("sec_edgar", source_ref, ticker),
            "source": "sec_edgar",
            "source_ref": source_ref,
            "ticker": ticker,
            "source_presence": "present",
            "observation_fingerprint_sha256": fingerprint * 64,
            "observation": {
                "ticker": ticker,
                "cik": "0000000003",
                "filing_date": "2026-08-25",
                "kinds": [{"event_type": "listing_status_review"}],
            },
        }

    failed_case = case("FAIL", "0000000003-26-000003", "c")
    blocked_case = case("WAIT", "0000000003-26-000004", "d")
    blocked_bundle = LifecycleAutomationEvidenceBundle(
        evidence=(),
        facts=(),
        blockers=(
            AutomationBlocker(
                code="sec_rate_limited",
                retryable=True,
                context={"attempts": 1},
            ),
        ),
        diagnostics={"sec_attempts": 1},
        retry_at="2026-08-26T13:00:00Z",
    )

    @contextmanager
    def profile_connection():
        yield conn

    def evidence_loader(row, **_kwargs):
        if row["ticker"] == "FAIL":
            raise ValueError("source payload invalid")
        return blocked_bundle

    result = LifecycleAutomationWorker(
        case_loader=lambda: (failed_case, blocked_case),
        profile_connection=profile_connection,
        evidence_loader=evidence_loader,
        source_loader=lambda: {"FAIL": (), "WAIT": ()},
        transition_preview=lambda **_kwargs: pytest.fail(
            "transition preview reached"
        ),
        transition_approver=lambda **_kwargs: pytest.fail(
            "transition approval reached"
        ),
        clock=lambda: "2026-08-25T13:00:00Z",
        execution_owner_id="legacy-mixed-owner",
    ).run(limit=2)
    legacy_result = {
        key: value
        for key, value in result.items()
        if key not in {"result_version", "case_outcomes"}
    }

    assert result["case_outcomes"] == {
        failed_case["case_id"]: "failed",
        blocked_case["case_id"]: "blocked",
    }
    assert scheduler.record_security_lifecycle_automation_result(
        legacy_result,
        now=_NOW,
    )
    state = state_store.get("security_lifecycle.automation")
    assert state is not None
    assert set(state["last_result"]["active_incident"]["case_failures"]) == {
        failed_case["case_id"]
    }
    conn.close()


@pytest.mark.parametrize(
    "recovery",
    (
        _v2_summary(),
        _v2_summary(
            status="partial",
            reason="case_processing_blocked",
            selected=1,
            processed=1,
            blocked=1,
            case_ids=["slc_blocked"],
            case_outcomes={"slc_blocked": "blocked"},
        ),
    ),
    ids=("empty-success", "completed-blocked-attempt"),
)
def test_scheduler_level_incident_recovers_after_a_nonoperational_invocation(
    tmp_path,
    monkeypatch,
    recovery,
):
    from src.scheduler_state import SchedulerStateStore
    from src.service import security_lifecycle_automation_scheduler as scheduler
    from src.service.job_runs_store import JobRunsLocalStore

    profile_path = tmp_path / "profile_state.db"
    telemetry = JobRunsLocalStore(profile_path)
    state_store = SchedulerStateStore(profile_path)
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile_path))
    failure = _v2_summary(
        status="unavailable",
        reason="automation_scheduler_failed",
    )

    assert scheduler.record_security_lifecycle_automation_result(failure, now=_NOW)
    assert scheduler.record_security_lifecycle_automation_result(recovery, now=_NOW)

    runs = telemetry.list_runs(job_name="security_lifecycle.automation", limit=10)
    assert [(row["status"], row["message"]) for row in runs] == [
        ("succeeded", "security_lifecycle_automation_recovered"),
        ("failed", "security_lifecycle_automation_failure"),
    ]
    state = state_store.get("security_lifecycle.automation")
    assert state is not None
    assert state["last_result"]["active_incident"] is None
    assert state["last_result"]["latest_result"] == recovery


def test_scheduler_program_error_is_typed_without_raw_detail(monkeypatch):
    from src.service import security_lifecycle_automation_scheduler as scheduler

    class Worker:
        def run(self, limit, mode):
            del limit, mode
            raise RuntimeError(
                "/private/profile_state.db https://secret.invalid token@example.invalid"
            )

    monkeypatch.setattr(scheduler, "_worker", lambda **_kwargs: Worker())

    result = scheduler.run_security_lifecycle_automation(now=_NOW)

    assert result == _v2_summary(
        status="unavailable",
        reason="automation_scheduler_failed",
    )
    rendered = json.dumps(result)
    assert "private" not in rendered
    assert "invalid" not in rendered
    assert "@" not in rendered


def test_scheduler_uses_real_provider_free_transition_preflight_and_approver(
    monkeypatch,
):
    from src import ticker_identity_service, ticker_identity_transition
    from src.service import security_lifecycle_automation_scheduler as scheduler

    calls = []
    marker = object()

    @contextmanager
    def profile_connection():
        yield marker

    def build_preflight(conn, *, case, request, sources):
        calls.append(("preview", conn, case, request, sources))
        return {
            "eligible": True,
            "block_reasons": (),
            "transition_kind": request["transition_kind"],
        }

    class Service:
        def __init__(self, **kwargs):
            calls.append(("service", kwargs))

        def approve_automation_case(self, case_id, *, request):
            calls.append(("approve", case_id, request))
            return {
                "transition_id": "tit_1",
                "status": "approved",
                "approval_authority": "automation_policy",
            }

    captured_worker = {}

    class Worker:
        def __init__(self, **kwargs):
            captured_worker.update(kwargs)

    monkeypatch.setattr(scheduler, "_profile_connection", profile_connection)
    monkeypatch.setattr(
        ticker_identity_transition,
        "build_automation_transition_preflight",
        build_preflight,
    )
    monkeypatch.setattr(ticker_identity_service, "TickerIdentityService", Service)
    monkeypatch.setattr(scheduler, "_profile_path", lambda: "/profile.db")
    monkeypatch.setattr(scheduler, "_market_path", lambda: "/market.db")
    monkeypatch.setattr(scheduler, "_load_sources", lambda: {"OLD": ("manual_lists",)})
    monkeypatch.setattr(scheduler, "_assert_automation_installed", lambda: None)
    monkeypatch.setattr(scheduler, "LifecycleAutomationWorker", Worker)

    case = {"case_id": "slc_1", "ticker": "OLD"}
    request = {
        "transition_kind": "symbol_continuation",
        "source_ticker": "OLD",
        "successor_ticker": "NEW",
        "effective_date": "2026-08-25",
        "outcomes": ("symbol_changed",),
    }
    assert scheduler._transition_preview(
        case=case,
        request=request,
        sources=("manual_lists",),
    )["eligible"] is True
    assert scheduler._transition_approver(
        case=case,
        request=request,
        sources=("manual_lists",),
    )["transition_id"] == "tit_1"

    scheduler._worker(
        evidence_loader=marker,
        execution_owner_id="test-scheduler-owner",
    )
    assert captured_worker["evidence_loader"] is marker
    assert captured_worker["execution_owner_id"] == "test-scheduler-owner"
    assert captured_worker["transition_preview"] is scheduler._transition_preview
    assert captured_worker["transition_approver"] is scheduler._transition_approver
    assert calls[0][0] == "preview"
    assert calls[-1] == ("approve", "slc_1", request)


def test_scheduler_identity_context_uses_bounded_local_aliases_and_ibkr_conids(
    tmp_path,
    monkeypatch,
):
    from src.service import security_lifecycle_automation_scheduler as scheduler

    market_path = tmp_path / "market.db"
    profile_path = tmp_path / "profile.db"
    with sqlite3.connect(market_path) as conn:
        conn.execute("CREATE TABLE ticker_aliases(alias TEXT, canonical TEXT)")
        conn.executemany(
            "INSERT INTO ticker_aliases VALUES (?,?)",
            (("LC", "HAPN"), ("HAPN.PRE", "LC"), ("OLD", "OTHER")),
        )
    with sqlite3.connect(profile_path) as conn:
        conn.execute(
            "CREATE TABLE portfolio_positions("
            "broker TEXT,broker_con_id TEXT,symbol TEXT)"
        )
        conn.executemany(
            "INSERT INTO portfolio_positions VALUES (?,?,?)",
            (
                ("ibkr", "1001", "HAPN"),
                ("ibkr", "1002", "LC"),
                ("ibkr", "2001", "QBTS"),
                ("manual", "ignored", "HAPN"),
            ),
        )
    before = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (market_path, profile_path)
    }

    hints = scheduler._load_local_identity_hints(
        market_path=market_path,
        profile_path=profile_path,
        tickers=("HAPN", "QBTS"),
    )

    assert hints == {
        "HAPN": {
            "ticker_aliases": ("HAPN", "HAPN.PRE", "LC"),
            "ibkr_conids": (),
            "ibkr_identity_blockers": ("ibkr_contract_ambiguous",),
        },
        "QBTS": {
            "ticker_aliases": ("QBTS",),
            "ibkr_conids": (2001,),
            "ibkr_identity_blockers": (),
        },
    }
    case = {
        "case_id": "case-hapn",
        "source": "sec_edgar",
        "ticker": "HAPN",
        "ticker_aliases": hints["HAPN"]["ticker_aliases"],
        "ibkr_conids": hints["HAPN"]["ibkr_conids"],
        "observation": {
            "ticker": "HAPN",
            "cik": "0001409970",
            "issuer_name": "Happen, Inc.",
            "filing_date": "2026-06-18",
            "source_ref": "0001409970-26-000131",
            "filing_form": "25",
            "filing_items": [],
            "kinds": [
                {"event_type": "listing_removal_notice", "effective_date": None}
            ],
        },
    }
    monkeypatch.setattr(scheduler, "_market_path", lambda: market_path)
    monkeypatch.setattr(scheduler, "_profile_path", lambda: profile_path)
    monkeypatch.setattr(scheduler, "_automation_schema_state", lambda _conn: None)
    monkeypatch.setattr(
        scheduler,
        "compose_security_lifecycle",
        lambda _market, _profile: {"cases": [case]},
    )

    loaded = scheduler._load_cases()
    assert len(loaded) == 1
    context = scheduler._identity_context(loaded[0])
    assert context.ticker_aliases == ("HAPN", "HAPN.PRE", "LC")
    assert context.ibkr_conids == ()
    assert loaded[0]["ibkr_identity_blockers"] == ("ibkr_contract_ambiguous",)
    assert {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (market_path, profile_path)
    } == before


def test_alias_closure_overflow_is_a_per_case_ibkr_ambiguity(tmp_path):
    from src.service import security_lifecycle_automation_scheduler as scheduler

    market_path = tmp_path / "market.db"
    profile_path = tmp_path / "profile.db"
    aliases = tuple(f"OV{index:02d}" for index in range(65))
    with sqlite3.connect(market_path) as conn:
        conn.execute("CREATE TABLE ticker_aliases(alias TEXT, canonical TEXT)")
        conn.executemany(
            "INSERT INTO ticker_aliases VALUES (?,?)",
            tuple(zip(aliases, aliases[1:])),
        )
    with sqlite3.connect(profile_path) as conn:
        conn.execute(
            "CREATE TABLE portfolio_positions("
            "broker TEXT,broker_con_id TEXT,symbol TEXT)"
        )

    hints = scheduler._load_local_identity_hints(
        market_path=market_path,
        profile_path=profile_path,
        tickers=(aliases[0], "GOOD"),
    )

    assert hints[aliases[0]] == {
        "ticker_aliases": (aliases[0],),
        "ibkr_conids": (),
        "ibkr_identity_blockers": ("ibkr_contract_ambiguous",),
    }
    assert hints["GOOD"] == {
        "ticker_aliases": ("GOOD",),
        "ibkr_conids": (),
        "ibkr_identity_blockers": (),
    }


def test_alias_edge_row_overflow_is_a_per_case_ibkr_ambiguity(tmp_path):
    from src.service import security_lifecycle_automation_scheduler as scheduler

    market_path = tmp_path / "market.db"
    profile_path = tmp_path / "profile.db"
    component = ("DENSE", *(f"D{index:02d}" for index in range(23)))
    edges = tuple(
        (alias, canonical)
        for alias in component
        for canonical in component
        if alias != canonical
    )
    assert len(component) == 24
    assert len(edges) == 552
    with sqlite3.connect(market_path) as conn:
        conn.execute("CREATE TABLE ticker_aliases(alias TEXT, canonical TEXT)")
        conn.executemany("INSERT INTO ticker_aliases VALUES (?,?)", edges)
    with sqlite3.connect(profile_path) as conn:
        conn.execute(
            "CREATE TABLE portfolio_positions("
            "broker TEXT,broker_con_id TEXT,symbol TEXT)"
        )

    hints = scheduler._load_local_identity_hints(
        market_path=market_path,
        profile_path=profile_path,
        tickers=("DENSE", "GOOD"),
    )

    assert hints["DENSE"] == {
        "ticker_aliases": ("DENSE",),
        "ibkr_conids": (),
        "ibkr_identity_blockers": ("ibkr_contract_ambiguous",),
    }
    assert hints["GOOD"] == {
        "ticker_aliases": ("GOOD",),
        "ibkr_conids": (),
        "ibkr_identity_blockers": (),
    }


def test_ibkr_position_row_overflow_is_a_per_case_ambiguity(tmp_path):
    from src.service import security_lifecycle_automation_scheduler as scheduler

    market_path = tmp_path / "market.db"
    profile_path = tmp_path / "profile.db"
    with sqlite3.connect(market_path) as conn:
        conn.execute("CREATE TABLE ticker_aliases(alias TEXT, canonical TEXT)")
    with sqlite3.connect(profile_path) as conn:
        conn.execute(
            "CREATE TABLE portfolio_positions("
            "broker TEXT,broker_con_id TEXT,symbol TEXT)"
        )
        conn.executemany(
            "INSERT INTO portfolio_positions VALUES (?,?,?)",
            (("ibkr", "101", "ROWS"),) * 513
            + (("ibkr", "202", "GOOD"),),
        )

    hints = scheduler._load_local_identity_hints(
        market_path=market_path,
        profile_path=profile_path,
        tickers=("ROWS", "GOOD"),
    )

    assert hints["ROWS"] == {
        "ticker_aliases": ("ROWS",),
        "ibkr_conids": (),
        "ibkr_identity_blockers": ("ibkr_contract_ambiguous",),
    }
    assert hints["GOOD"] == {
        "ticker_aliases": ("GOOD",),
        "ibkr_conids": (202,),
        "ibkr_identity_blockers": (),
    }


def test_duplicate_local_conid_rows_deduplicate_but_distinct_conids_are_ambiguous(
    tmp_path,
):
    from src.service import security_lifecycle_automation_scheduler as scheduler

    market_path = tmp_path / "market.db"
    profile_path = tmp_path / "profile.db"
    with sqlite3.connect(market_path) as conn:
        conn.execute("CREATE TABLE ticker_aliases(alias TEXT, canonical TEXT)")
        conn.execute("INSERT INTO ticker_aliases VALUES (?,?)", ("DUP.A", "DUP"))
    with sqlite3.connect(profile_path) as conn:
        conn.execute(
            "CREATE TABLE portfolio_positions("
            "broker TEXT,broker_con_id TEXT,symbol TEXT)"
        )
        conn.executemany(
            "INSERT INTO portfolio_positions VALUES (?,?,?)",
            (
                ("ibkr", "101", "DUP"),
                ("ibkr", "101", "DUP"),
                ("ibkr", "101", "DUP.A"),
                ("ibkr", "202", "MULTI"),
                ("ibkr", "303", "MULTI"),
            ),
        )

    hints = scheduler._load_local_identity_hints(
        market_path=market_path,
        profile_path=profile_path,
        tickers=("DUP", "MULTI"),
    )

    assert hints["DUP"] == {
        "ticker_aliases": ("DUP", "DUP.A"),
        "ibkr_conids": (101,),
        "ibkr_identity_blockers": (),
    }
    assert hints["MULTI"] == {
        "ticker_aliases": ("MULTI",),
        "ibkr_conids": (),
        "ibkr_identity_blockers": ("ibkr_contract_ambiguous",),
    }


def test_multiple_local_conids_do_not_poison_a_later_case(tmp_path):
    from src.service import security_lifecycle_automation_scheduler as scheduler

    market_path = tmp_path / "market.db"
    profile_path = tmp_path / "profile.db"
    with sqlite3.connect(market_path) as conn:
        conn.execute("CREATE TABLE ticker_aliases(alias TEXT, canonical TEXT)")
    with sqlite3.connect(profile_path) as conn:
        conn.execute(
            "CREATE TABLE portfolio_positions("
            "broker TEXT,broker_con_id TEXT,symbol TEXT)"
        )
        conn.executemany(
            "INSERT INTO portfolio_positions VALUES (?,?,?)",
            (
                ("ibkr", "101", "MULTI"),
                ("ibkr", "202", "MULTI"),
                ("ibkr", "303", "GOOD"),
            ),
        )

    hints = scheduler._load_local_identity_hints(
        market_path=market_path,
        profile_path=profile_path,
        tickers=("MULTI", "GOOD"),
    )

    assert hints["MULTI"] == {
        "ticker_aliases": ("MULTI",),
        "ibkr_conids": (),
        "ibkr_identity_blockers": ("ibkr_contract_ambiguous",),
    }
    assert hints["GOOD"] == {
        "ticker_aliases": ("GOOD",),
        "ibkr_conids": (303,),
        "ibkr_identity_blockers": (),
    }


def test_scheduler_ibkr_seam_forwards_an_injected_query_cap(monkeypatch):
    from src import security_lifecycle_ibkr_evidence
    from src.service import security_lifecycle_automation_scheduler as scheduler

    captured = []
    monkeypatch.setattr(scheduler, "_LifecycleIbkrGateway", lambda: SimpleNamespace())
    monkeypatch.setattr(
        security_lifecycle_ibkr_evidence,
        "read_ibkr_contract_evidence",
        lambda **kwargs: (
            captured.append(kwargs)
            or SimpleNamespace(evidence=(), blockers=(), requests_made=0)
        ),
    )
    monkeypatch.setattr(
        security_lifecycle_ibkr_evidence,
        "contract_snapshot_facts",
        lambda *_args, **_kwargs: (),
    )

    scheduler._ibkr_evidence(
        SimpleNamespace(),
        at="2026-08-26T00:00:00Z",
        regulator_successors=("NEXT",),
        max_queries=3,
    )

    assert captured[0]["max_queries"] == 3


def test_precomputed_ibkr_ambiguity_never_reaches_the_gateway(monkeypatch):
    from data_sources import sec_transport
    from src import security_lifecycle_sec_evidence
    from src.service import security_lifecycle_automation_scheduler as scheduler

    class Transport:
        def diagnostics(self, _budget):
            return {"attempt_count": 1}

        def close(self):
            pass

    sec_evidence = SimpleNamespace(
        evidence_id="sec-identity-ambiguity",
        source_family="regulator",
        source_locator={},
        retrieved_at="2026-08-26T00:00:00Z",
    )
    successor = SimpleNamespace(
        evidence_id=sec_evidence.evidence_id,
        fact_type="successor_ticker",
        value="NEXT",
    )
    monkeypatch.setattr(sec_transport, "SecTransport", Transport)
    monkeypatch.setattr(
        security_lifecycle_sec_evidence,
        "collect_sec_evidence",
        lambda **_kwargs: SimpleNamespace(
            evidence=(sec_evidence,),
            facts=(successor,),
            blockers=(),
            source_deadlines=(),
        ),
    )
    listing_session = SimpleNamespace(
        lookup=lambda **_kwargs: SimpleNamespace(
            evidence=(), facts=(), blockers=(), diagnostics={}
        )
    )
    monkeypatch.setattr(
        scheduler,
        "_ibkr_evidence",
        lambda *_args, **_kwargs: pytest.fail("ambiguous identity reached IBKR"),
    )
    case = {
        "case_id": "slc_identity_ambiguity",
        "ticker": "OLD",
        "ticker_aliases": ("OLD",),
        "ibkr_conids": (),
        "ibkr_identity_blockers": ("ibkr_contract_ambiguous",),
        "observation": {
            "ticker": "OLD",
            "cik": "0000000001",
            "issuer_name": "Ambiguous Identity Issuer",
            "filing_date": "2026-08-20",
            "source_ref": "0000000001-26-000001",
            "filing_form": "8-K",
            "filing_items": ["3.01"],
            "kinds": [{"event_type": "acquisition_completed", "effective_date": None}],
        },
    }

    bundle = scheduler._load_evidence(
        case,
        mode="live",
        at="2026-08-26T00:00:00Z",
        listing_session=listing_session,
    )

    assert tuple(row.code for row in bundle.blockers) == (
        "ibkr_contract_ambiguous",
    )
    assert bundle.diagnostics["ibkr_requests"] == 0
    assert bundle.diagnostics["ibkr_missing"] == 0
    assert bundle.diagnostics["ibkr_conflict"] == 1


def test_ibkr_identity_ambiguity_blocks_one_case_and_the_later_case_runs(tmp_path):
    from src.security_lifecycle_automation_worker import (
        LifecycleAutomationEvidenceBundle,
        LifecycleAutomationWorker,
    )
    from src.security_lifecycle_fact_kernel import AutomationBlocker
    from src.security_lifecycle_investigation import (
        SecurityLifecycleInvestigationStore,
        case_id_for,
    )

    def case(index, ticker):
        source_ref = f"000000000{index}-26-00000{index}"
        return {
            "case_id": case_id_for("sec_edgar", source_ref, ticker),
            "source": "sec_edgar",
            "source_ref": source_ref,
            "ticker": ticker,
            "source_presence": "present",
            "observation_fingerprint_sha256": str(index) * 64,
            "ticker_aliases": (ticker,),
            "ibkr_conids": (),
            "ibkr_identity_blockers": (),
            "observation": {
                "ticker": ticker,
                "cik": f"{index:010d}",
                "filing_date": "2026-08-20",
                "kinds": [{"event_type": "listing_status_review"}],
            },
        }

    first, second = sorted(
        (case(1, "AMB"), case(2, "GOOD")),
        key=lambda row: row["case_id"],
    )
    first["ibkr_identity_blockers"] = ("ibkr_contract_ambiguous",)
    conn = sqlite3.connect(tmp_path / "profile.db", check_same_thread=False)
    SecurityLifecycleInvestigationStore(conn)

    @contextmanager
    def profile_connection():
        yield conn

    calls = []

    def evidence_loader(current, *, mode, at):
        calls.append((current["case_id"], mode, at))
        code = (
            "ibkr_contract_ambiguous"
            if current["ibkr_identity_blockers"]
            else "sec_rate_limited"
        )
        return LifecycleAutomationEvidenceBundle(
            evidence=(),
            facts=(),
            blockers=(
                AutomationBlocker(
                    code=code,
                    retryable=code == "sec_rate_limited",
                    context={},
                ),
            ),
            diagnostics={},
            retry_at=(
                "2026-08-26T13:00:00Z" if code == "sec_rate_limited" else None
            ),
        )

    result = LifecycleAutomationWorker(
        case_loader=lambda: (first, second),
        profile_connection=profile_connection,
        evidence_loader=evidence_loader,
        source_loader=lambda: {first["ticker"]: (), second["ticker"]: ()},
        transition_preview=lambda **_kwargs: pytest.fail(
            "blocked cases must not preview transitions"
        ),
        transition_approver=lambda **_kwargs: pytest.fail(
            "blocked cases must not approve transitions"
        ),
        clock=lambda: "2026-08-25T13:00:00Z",
        execution_owner_id="identity-containment-owner",
    ).run(limit=2)

    assert [row[0] for row in calls] == [first["case_id"], second["case_id"]]
    assert result["processed"] == 2
    assert result["blocked"] == 2
    assert result["case_outcomes"] == {
        first["case_id"]: "blocked",
        second["case_id"]: "blocked",
    }
    conn.close()


def test_real_identity_hint_overflow_reaches_load_evidence_and_worker_continues(
    tmp_path,
    monkeypatch,
):
    from data_sources import sec_transport
    from src import security_lifecycle_sec_evidence
    from src.security_lifecycle_automation_worker import LifecycleAutomationWorker
    from src.security_lifecycle_fact_kernel import AutomationEvidence, AutomationFact
    from src.security_lifecycle_investigation import (
        SecurityLifecycleInvestigationStore,
        case_id_for,
    )
    from src.service import security_lifecycle_automation_scheduler as scheduler

    market_path = tmp_path / "market.db"
    profile_path = tmp_path / "profile.db"

    def case(index, ticker):
        source_ref = f"000000000{index}-26-00000{index}"
        observation = {
            "ticker": ticker,
            "cik": f"{index:010d}",
            "issuer_name": f"Identity seam issuer {index}",
            "filing_date": "2026-08-20",
            "source": "sec_edgar",
            "source_ref": source_ref,
            "filing_form": "8-K",
            "filing_items": ["3.01"],
            "evidence_url": (
                f"https://www.sec.gov/Archives/identity-seam/{index}.htm"
            ),
            "description": "Identity planning seam fixture.",
            "kinds": [{"event_type": "listing_status_review"}],
        }
        return {
            "case_id": case_id_for("sec_edgar", source_ref, ticker),
            "source": "sec_edgar",
            "source_ref": source_ref,
            "ticker": ticker,
            "source_presence": "present",
            "observation": observation,
        }

    first, later = sorted(
        (case(1, "CASEA"), case(2, "CASEB")),
        key=lambda row: row["case_id"],
    )
    component = (first["ticker"], *(f"X{index:02d}" for index in range(23)))
    edges = tuple(
        (alias, canonical)
        for alias in component
        for canonical in component
        if alias != canonical
    )
    with sqlite3.connect(market_path) as conn:
        conn.execute("CREATE TABLE ticker_aliases(alias TEXT, canonical TEXT)")
        conn.executemany("INSERT INTO ticker_aliases VALUES (?,?)", edges)
    with sqlite3.connect(profile_path) as conn:
        SecurityLifecycleInvestigationStore(conn)
        conn.execute(
            "CREATE TABLE portfolio_positions("
            "broker TEXT,broker_con_id TEXT,symbol TEXT)"
        )

    monkeypatch.setattr(scheduler, "_market_path", lambda: market_path)
    monkeypatch.setattr(scheduler, "_profile_path", lambda: profile_path)
    monkeypatch.setattr(
        scheduler,
        "compose_security_lifecycle",
        lambda _market, _profile: {"cases": (first, later)},
    )

    class Transport:
        def diagnostics(self, _budget):
            return {"attempt_count": 1}

        def close(self):
            pass

    def collect_sec_evidence(*, context, retrieved_at, **_kwargs):
        successor = f"{context.current_ticker}N"
        excerpt = json.dumps(
            {"successor_ticker": successor},
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        cited = json.dumps(successor).encode("utf-8")
        encoded = excerpt.encode("utf-8")
        start = encoded.index(cited)
        evidence = AutomationEvidence(
            evidence_id=f"sec-{context.case_id[-32:]}",
            source_family="regulator",
            adapter="sec_edgar",
            kind="regulator_excerpt",
            source_url=(
                f"https://www.sec.gov/Archives/{context.accession}.htm"
            ),
            title="SEC identity seam evidence",
            publisher="SEC EDGAR",
            domain="sec.gov",
            source_published_at=context.filing_date,
            retrieved_at=retrieved_at,
            excerpt=excerpt,
            content_sha256=hashlib.sha256(encoded).hexdigest(),
            source_document_sha256="d" * 64,
            source_locator={"filing_chain_complete": True},
            evidence_dedupe_key=f"sec:{context.case_id}",
        )
        fact = AutomationFact(
            evidence_id=evidence.evidence_id,
            fact_type="successor_ticker",
            normalized_value=successor,
            source_span_start=start,
            source_span_end=start + len(cited),
            cited_text_sha256=hashlib.sha256(cited).hexdigest(),
            extractor_rule_id="fixture.successor_ticker",
            extractor_rule_version="1",
        )
        return SimpleNamespace(
            evidence=(evidence,),
            facts=(fact,),
            blockers=(),
            source_deadlines=(),
        )

    monkeypatch.setattr(sec_transport, "SecTransport", Transport)
    monkeypatch.setattr(
        security_lifecycle_sec_evidence,
        "collect_sec_evidence",
        collect_sec_evidence,
    )
    listing_session = SimpleNamespace(
        lookup=lambda **_kwargs: SimpleNamespace(
            evidence=(),
            facts=(),
            blockers=(),
            diagnostics={},
        )
    )
    ibkr_calls = []

    def ibkr_evidence(context, **_kwargs):
        ibkr_calls.append(context.current_ticker)
        return (
            SimpleNamespace(
                evidence=(),
                blockers=("ibkr_contract_missing",),
                requests_made=1,
            ),
            (),
        )

    monkeypatch.setattr(scheduler, "_ibkr_evidence", ibkr_evidence)

    @contextmanager
    def profile_connection():
        conn = sqlite3.connect(profile_path, check_same_thread=False)
        try:
            yield conn
        finally:
            conn.close()

    worker = LifecycleAutomationWorker(
        case_loader=scheduler._load_cases,
        profile_connection=profile_connection,
        evidence_loader=lambda current, *, mode, at: scheduler._load_evidence(
            current,
            mode=mode,
            at=at,
            listing_session=listing_session,
        ),
        source_loader=lambda: {
            first["ticker"]: (),
            later["ticker"]: (),
        },
        transition_preview=lambda **_kwargs: pytest.fail(
            "blocked cases must not preview transitions"
        ),
        transition_approver=lambda **_kwargs: pytest.fail(
            "blocked cases must not approve transitions"
        ),
        clock=lambda: "2026-08-25T13:00:00Z",
        execution_owner_id="identity-real-seam-owner",
    )

    result = worker.run(limit=2)

    assert result["case_ids"] == [first["case_id"], later["case_id"]]
    assert result["processed"] == 2
    assert result["blocked"] == 2
    assert result["case_outcomes"] == {
        first["case_id"]: "blocked",
        later["case_id"]: "blocked",
    }
    assert ibkr_calls == [later["ticker"]]
    with sqlite3.connect(profile_path) as conn:
        store = SecurityLifecycleInvestigationStore(conn)
        first_run = store.list_automation_runs(first["case_id"])[0]
        later_run = store.list_automation_runs(later["case_id"])[0]
    assert {row["blocker_code"] for row in first_run["blockers"]} >= {
        "ibkr_contract_ambiguous",
    }
    assert "ibkr_contract_ambiguous" not in {
        row["blocker_code"] for row in later_run["blockers"]
    }


def test_sec_transport_byte_diagnostic_is_safe_for_kernel_persistence(monkeypatch):
    from data_sources import sec_transport
    from src import security_lifecycle_sec_evidence
    from src.security_lifecycle_fact_kernel import _diagnostics
    from src.service import security_lifecycle_automation_scheduler as scheduler

    class Transport:
        def diagnostics(self, _budget):
            return {
                "attempt_count": 2,
                "document_count": 1,
                "body_bytes": 4096,
                "governor_wait_ms": 25,
                "rate_limit_retries": 0,
            }

        def close(self):
            pass

    monkeypatch.setattr(sec_transport, "SecTransport", Transport)
    monkeypatch.setattr(
        security_lifecycle_sec_evidence,
        "collect_sec_evidence",
        lambda **_kwargs: SimpleNamespace(
            evidence=(),
            facts=(),
            blockers=("sec_evidence_insufficient",),
        ),
    )
    listing_session = SimpleNamespace(
        lookup=lambda **_kwargs: SimpleNamespace(
            evidence=(), facts=(), blockers=(), diagnostics={}
        )
    )
    case = {
        "case_id": "slc_diag",
        "ticker": "DIAG",
        "ticker_aliases": ("DIAG",),
        "ibkr_conids": (),
        "observation": {
            "ticker": "DIAG",
            "cik": "0000000001",
            "issuer_name": "Diagnostic Issuer",
            "filing_date": "2026-08-25",
            "source_ref": "0000000001-26-000001",
            "filing_form": "8-K",
            "filing_items": ["3.01"],
            "kinds": [
                {"event_type": "listing_status_review", "effective_date": None}
            ],
        },
    }

    bundle = scheduler._load_evidence(
        case,
        mode="live",
        at="2026-08-26T00:00:00Z",
        listing_session=listing_session,
    )

    assert _diagnostics(bundle.diagnostics) == (
        '{"ibkr_conflict":0,"ibkr_missing":0,"ibkr_requests":0,'
        '"ibkr_unavailable":0,"sec_attempt_count":2,'
        '"sec_document_count":1,"sec_governor_wait_ms":25,'
        '"sec_payload_bytes":4096,"sec_rate_limit_retries":0}'
    )


def test_listing_transport_constructor_failure_is_bounded_and_sanitized(
    monkeypatch,
):
    from src.service import security_lifecycle_automation_scheduler as scheduler

    class Transport:
        def __init__(self):
            raise RuntimeError("private constructor detail")

    monkeypatch.setattr(scheduler, "ListingAuthorityTransport", Transport)
    monkeypatch.setattr(
        scheduler,
        "_worker",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("worker must not run")
        ),
    )

    result = scheduler.run_security_lifecycle_automation(now=_NOW)

    assert result == _v2_summary(
        status="unavailable",
        reason="automation_scheduler_failed",
    )
    assert "private constructor detail" not in json.dumps(result)


def test_listing_session_constructor_failure_closes_constructed_transport(
    monkeypatch,
):
    from src.service import security_lifecycle_automation_scheduler as scheduler

    events = []

    class Transport:
        def __init__(self):
            events.append("transport")

        def close(self):
            events.append("transport_closed")

    class Budget:
        @classmethod
        def lifecycle(cls):
            events.append("budget")
            return cls()

    class Session:
        def __init__(self, **_kwargs):
            events.append("session")
            raise RuntimeError("private session detail")

    monkeypatch.setattr(scheduler, "ListingAuthorityTransport", Transport)
    monkeypatch.setattr(scheduler, "ListingRequestBudget", Budget)
    monkeypatch.setattr(scheduler, "ListingAuthoritySession", Session)

    result = scheduler.run_security_lifecycle_automation(now=_NOW)

    assert result == _v2_summary(
        status="unavailable",
        reason="automation_scheduler_failed",
    )
    assert events == ["transport", "budget", "session", "transport_closed"]
    assert "private session detail" not in json.dumps(result)


def test_listing_session_close_failure_retains_result_with_sanitized_cleanup_witness(
    caplog,
    monkeypatch,
):
    from src.service import security_lifecycle_automation_scheduler as scheduler

    events = []

    class Transport:
        def close(self):
            events.append("transport_closed")
            raise RuntimeError("private transport close detail")

    class Budget:
        @classmethod
        def lifecycle(cls):
            return cls()

    class Session:
        def __init__(self, *, transport, **_kwargs):
            self.transport = transport

        def close(self):
            events.append("session_close")
            raise RuntimeError("private close detail")

    class Worker:
        def run(self, limit, mode):
            del limit, mode
            events.append("worker")
            return _summary(
                selected=1,
                processed=1,
                drafted=1,
                case_ids=["slc_a"],
            )

    monkeypatch.setattr(scheduler, "ListingAuthorityTransport", Transport)
    monkeypatch.setattr(scheduler, "ListingRequestBudget", Budget)
    monkeypatch.setattr(scheduler, "ListingAuthoritySession", Session)
    monkeypatch.setattr(scheduler, "_worker", lambda **_kwargs: Worker())

    result = scheduler.run_security_lifecycle_automation(now=_NOW)

    assert result == _summary(
        selected=1,
        processed=1,
        drafted=1,
        case_ids=["slc_a"],
    )
    assert events == ["worker", "session_close", "transport_closed"]
    assert caplog.messages == [
        "security lifecycle listing cleanup failed code=RuntimeError",
        "security lifecycle listing transport cleanup failed code=RuntimeError",
    ]
    rendered = json.dumps(result) + "\n".join(caplog.messages)
    assert "private close detail" not in rendered
    assert "private transport close detail" not in rendered


def test_two_case_tick_uses_one_lazy_listing_session_and_closes_it(monkeypatch):
    from src.security_lifecycle_automation_worker import LifecycleAutomationEvidenceBundle
    from src.service import security_lifecycle_automation_scheduler as scheduler

    events = []

    class Budget:
        @classmethod
        def lifecycle(cls):
            value = cls()
            events.append(("budget", value))
            return value

    class Transport:
        def __init__(self):
            self.urls = []
            events.append(("transport", self))

    class Session:
        def __init__(self, *, transport, budget, retrieved_at, massive_api_key):
            self.transport = transport
            self.budget = budget
            self.retrieved_at = retrieved_at
            self.massive_api_key = massive_api_key
            self.loaded = False
            self.massive_identities = set()
            self.massive_requests = []
            self.closed = False
            events.append(("session", self))

        def lookup(self, **_kwargs):
            if not self.loaded:
                self.transport.urls.extend(
                    [scheduler.NASDAQ_LISTED_URL, scheduler.OTHER_LISTED_URL]
                )
                self.loaded = True
            identity = ("CASE", True, "otc")
            if identity not in self.massive_identities:
                self.massive_requests.append(identity)
                self.massive_identities.add(identity)
            return SimpleNamespace(
                evidence=(), facts=(), blockers=(), diagnostics={}
            )

        def close(self):
            self.closed = True
            events.append(("closed", self))

    def load(case, *, mode, at, listing_session):
        del mode, at
        listing_session.lookup(case_id=case["case_id"])
        return LifecycleAutomationEvidenceBundle(
            evidence=(), facts=(), blockers=(), diagnostics={}, retry_at=None
        )

    class Worker:
        def __init__(self, evidence_loader):
            self.evidence_loader = evidence_loader

        def run(self, limit, mode):
            assert events == [events[0], events[1], events[2]]
            for case_id in ("CASE-A", "CASE-B"):
                self.evidence_loader(
                    {"case_id": case_id}, mode=mode, at="2026-08-25T13:00:00Z"
                )
            return _summary(
                selected=2,
                processed=2,
                drafted=2,
                case_ids=["CASE-A", "CASE-B"],
            )

    monkeypatch.setenv("MASSIVE_API_KEY", "massive-primary")
    monkeypatch.setenv("POLYGON_API_KEY", "polygon-legacy")
    monkeypatch.setattr(scheduler, "ListingRequestBudget", Budget, raising=False)
    monkeypatch.setattr(scheduler, "ListingAuthorityTransport", Transport, raising=False)
    monkeypatch.setattr(scheduler, "ListingAuthoritySession", Session, raising=False)
    monkeypatch.setattr(scheduler, "_load_evidence", load)
    monkeypatch.setattr(
        scheduler,
        "_worker",
        lambda *, evidence_loader, **_kwargs: Worker(evidence_loader),
    )

    result = scheduler.run_security_lifecycle_automation(limit=2, now=_NOW)

    session = next(value for kind, value in events if kind == "session")
    assert result["processed"] == 2
    assert session.transport.urls == [
        scheduler.NASDAQ_LISTED_URL,
        scheduler.OTHER_LISTED_URL,
    ]
    assert session.massive_identities == {("CASE", True, "otc")}
    assert session.massive_requests == [("CASE", True, "otc")]
    assert session.massive_api_key == "massive-primary"
    assert session.closed is True


def test_v4_load_evidence_never_opens_local_news_databases(tmp_path, monkeypatch):
    from data_sources import sec_transport
    from src import sa_capture_store, security_lifecycle_sec_evidence
    from src.service import security_lifecycle_automation_scheduler as scheduler

    market_path = tmp_path / "market.db"
    sa_path = tmp_path / "sa.db"
    market_path.touch()
    sa_path.touch()
    original_connect = sqlite3.connect

    def reject_news_connection(database, *args, **kwargs):
        rendered = str(database)
        if str(market_path) in rendered or str(sa_path) in rendered:
            raise AssertionError("active lifecycle path opened a news database")
        return original_connect(database, *args, **kwargs)

    class Transport:
        def diagnostics(self, _budget):
            return {"attempt_count": 0}

        def close(self):
            pass

    monkeypatch.setattr(sec_transport, "SecTransport", Transport)
    monkeypatch.setattr(
        security_lifecycle_sec_evidence,
        "collect_sec_evidence",
        lambda **_kwargs: SimpleNamespace(
            evidence=(),
            facts=(),
            blockers=("sec_evidence_insufficient",),
            source_deadlines=(),
        ),
    )
    monkeypatch.setattr(scheduler, "_market_path", lambda: market_path)
    monkeypatch.setattr(sa_capture_store, "resolve_sa_db_path", lambda: sa_path)
    monkeypatch.setattr(sqlite3, "connect", reject_news_connection)
    listing_session = SimpleNamespace(
        lookup=lambda **_kwargs: SimpleNamespace(
            evidence=(), facts=(), blockers=(), diagnostics={}
        )
    )
    case = {
        "case_id": "slc_no_news",
        "ticker": "NONEWS",
        "ticker_aliases": ("NONEWS",),
        "ibkr_conids": (),
        "observation": {
            "ticker": "NONEWS",
            "cik": "0000000001",
            "issuer_name": "No News Issuer",
            "filing_date": "2026-08-25",
            "source_ref": "0000000001-26-000001",
            "filing_form": "8-K",
            "filing_items": ["3.01"],
            "kinds": [{"event_type": "listing_status_review", "effective_date": None}],
        },
    }

    bundle = scheduler._load_evidence(
        case,
        mode="live",
        at="2026-08-26T00:00:00Z",
        listing_session=listing_session,
    )

    assert all(row.source_family != "publisher" for row in bundle.evidence)
    assert "internal_news_unavailable" not in {row.code for row in bundle.blockers}
    assert all(not key.startswith("news_") for key in bundle.diagnostics)


@pytest.mark.parametrize(
    (
        "listing_codes",
        "ibkr_codes",
        "terminal",
        "expected_candidates",
        "expected_codes",
        "ibkr_diagnostics",
    ),
    [
        ((), ("ibkr_gateway_unavailable",), False, ("NEXT", "OLD"), (), (1, 0, 0)),
        ((), ("ibkr_contract_missing",), False, ("NEXT", "OLD"), (), (0, 1, 0)),
        (
            (),
            ("ibkr_contract_ambiguous",),
            False,
            ("NEXT", "OLD"),
            ("ibkr_contract_ambiguous",),
            (0, 0, 1),
        ),
        (
            ("massive_credential_missing",),
            (),
            True,
            ("OLD",),
            ("massive_credential_missing",),
            (0, 0, 0),
        ),
    ],
    ids=("ibkr-unavailable", "ibkr-missing", "ibkr-ambiguity", "massive-required"),
)
def test_listing_requiredness_and_ibkr_blocking_are_component_specific(
    monkeypatch,
    listing_codes,
    ibkr_codes,
    terminal,
    expected_candidates,
    expected_codes,
    ibkr_diagnostics,
):
    from data_sources import sec_transport
    from src import security_lifecycle_sec_evidence
    from src.service import security_lifecycle_automation_scheduler as scheduler

    class Transport:
        def diagnostics(self, _budget):
            return {"attempt_count": 1}

        def close(self):
            pass

    sec_evidence = (
        SimpleNamespace(
            evidence_id="sec-components",
            source_family="regulator",
            source_locator={},
            retrieved_at="2026-08-26T00:00:00Z",
        ),
    )
    sec_facts = (
        (
            SimpleNamespace(
                evidence_id="sec-components",
                fact_type="tracked_security_effect",
                value="terminal_delisting",
            ),
        )
        if terminal
        else (
            SimpleNamespace(
                evidence_id="sec-components",
                fact_type="successor_ticker",
                value="NEXT",
            ),
            SimpleNamespace(
                evidence_id="sec-components",
                fact_type="tracked_security_effect",
                value="symbol_change",
            ),
        )
    )
    monkeypatch.setattr(sec_transport, "SecTransport", Transport)
    monkeypatch.setattr(
        security_lifecycle_sec_evidence,
        "collect_sec_evidence",
        lambda **_kwargs: SimpleNamespace(
            evidence=sec_evidence,
            facts=sec_facts,
            blockers=(),
            source_deadlines=(),
        ),
    )
    listing_calls = []
    listing_session = SimpleNamespace(
        lookup=lambda **kwargs: (
                listing_calls.append(kwargs)
                or SimpleNamespace(
                    evidence=(),
                    facts=(),
                    blockers=listing_codes,
                    diagnostics={"massive_credential_missing": 1},
                )
        )
    )
    monkeypatch.setattr(
        scheduler,
        "_ibkr_evidence",
        lambda *_args, **_kwargs: (
            SimpleNamespace(evidence=(), blockers=ibkr_codes, requests_made=1),
            (),
        ),
    )
    case = {
        "case_id": "slc_components",
        "ticker": "OLD",
        "ticker_aliases": ("OLD",),
        "ibkr_conids": (),
        "observation": {
            "ticker": "OLD",
            "cik": "0000000001",
            "issuer_name": "Components Issuer",
            "filing_date": "2026-08-20",
            "source_ref": "0000000001-26-000001",
            "filing_form": "8-K",
            "filing_items": ["3.01"],
            "kinds": [{"event_type": "acquisition_completed", "effective_date": None}],
        },
    }

    bundle = scheduler._load_evidence(
        case,
        mode="live",
        at="2026-08-26T00:00:00Z",
        listing_session=listing_session,
    )

    assert listing_calls[0]["candidate_tickers"] == expected_candidates
    assert listing_calls[0]["require_explicit_inactive"] is terminal
    assert tuple(row.code for row in bundle.blockers) == expected_codes
    assert bundle.diagnostics["massive_credential_missing"] == 1
    assert (
        bundle.diagnostics["ibkr_unavailable"],
        bundle.diagnostics["ibkr_missing"],
        bundle.diagnostics["ibkr_conflict"],
    ) == ibkr_diagnostics


@pytest.mark.parametrize(
    ("scenario", "listing_codes", "expected_codes", "expected_state"),
    [
        (
            "massive_otc",
            ("listing_directory_unavailable",),
            (),
            "available",
        ),
        (
            "massive_otc",
            ("listing_status_unresolved",),
            (),
            "available",
        ),
        (
            "nms_missing",
            ("listing_directory_unavailable",),
            ("listing_directory_unavailable",),
            "unavailable",
        ),
        (
            "terminal_nasdaq_missing",
            ("listing_directory_stale",),
            ("listing_directory_stale",),
            "unavailable",
        ),
        (
            "terminal_massive_missing",
            ("massive_reference_unavailable",),
            ("massive_reference_unavailable",),
            "unavailable",
        ),
        (
            "nms_massive_optional",
            ("massive_credential_missing",),
            (),
            "available",
        ),
    ],
)
def test_listing_component_requiredness_filters_before_state_and_blockers(
    monkeypatch,
    scenario,
    listing_codes,
    expected_codes,
    expected_state,
):
    from data_sources import sec_transport
    from src import security_lifecycle_sec_evidence
    from src.service import security_lifecycle_automation_scheduler as scheduler

    class Transport:
        def diagnostics(self, _budget):
            return {"attempt_count": 1}

        def close(self):
            pass

    sec = SimpleNamespace(
        evidence_id="sec-requiredness",
        source_family="regulator",
        source_locator={},
        retrieved_at="2026-08-26T00:00:00Z",
    )
    sec_facts = [
        _authority_fact("sec-requiredness", "source_ticker", "OLD"),
        _authority_fact("sec-requiredness", "issuer_cik", "0000000001"),
        _authority_fact("sec-requiredness", "security_class", "common_stock"),
    ]
    listing_evidence = []
    listing_facts = []
    if scenario.startswith("terminal_"):
        sec.source_locator = {"filing_chain_complete": True}
        sec_facts.extend(
            (
                _authority_fact(
                    "sec-requiredness",
                    "tracked_security_effect",
                    "terminal_delisting",
                ),
                _authority_fact("sec-requiredness", "effective_date", "2026-08-25"),
            )
        )
        if scenario == "terminal_nasdaq_missing":
            massive = _authority_evidence(
                "massive-inactive",
                adapter="massive_reference",
                ticker="OLD",
                market="stocks",
                listing_status="inactive",
                expected_active=False,
                delisted_utc="2026-08-25T00:00:00Z",
            )
            listing_evidence.append(massive)
            listing_facts.append(
                _authority_fact("massive-inactive", "source_ticker", "OLD")
            )
        else:
            listing_evidence.extend(
                (
                    _authority_evidence(
                        "nasdaq-listed-missing",
                        adapter="nasdaq_symbol_directory",
                        ticker="OLD",
                        market="stocks",
                        listing_status="not_found",
                        directory="nasdaq_listed",
                    ),
                    _authority_evidence(
                        "other-listed-missing",
                        adapter="nasdaq_symbol_directory",
                        ticker="OLD",
                        market="stocks",
                        listing_status="not_found",
                        directory="other_listed",
                    ),
                )
            )
    else:
        sec_facts.extend(
            (
                _authority_fact("sec-requiredness", "successor_ticker", "NEXT"),
                _authority_fact(
                    "sec-requiredness", "tracked_security_effect", "symbol_change"
                ),
            )
        )
        if scenario != "massive_otc":
            sec_facts.append(
                _authority_fact(
                    "sec-requiredness", "destination_venue", "NASDAQ"
                )
            )
        if scenario in {"massive_otc", "nms_massive_optional"}:
            adapter = (
                "massive_reference"
                if scenario == "massive_otc"
                else "nasdaq_symbol_directory"
            )
            market = "otc" if scenario == "massive_otc" else "stocks"
            venue = "OTC" if scenario == "massive_otc" else "NASDAQ"
            listing = _authority_evidence(
                f"{adapter}-active",
                adapter=adapter,
                ticker="NEXT",
                market=market,
                listing_status="active",
                directory=(
                    "nasdaq_listed" if adapter == "nasdaq_symbol_directory" else None
                ),
            )
            listing_evidence.append(listing)
            listing_facts.extend(
                (
                    _authority_fact(listing.evidence_id, "successor_ticker", "NEXT"),
                    _authority_fact(listing.evidence_id, "destination_venue", venue),
                    _authority_fact(
                        listing.evidence_id,
                        "security_class",
                        "common_stock",
                    ),
                )
            )

    monkeypatch.setattr(sec_transport, "SecTransport", Transport)
    monkeypatch.setattr(
        security_lifecycle_sec_evidence,
        "collect_sec_evidence",
        lambda **_kwargs: SimpleNamespace(
            evidence=(sec,),
            facts=tuple(sec_facts),
            blockers=(),
            source_deadlines=(),
        ),
    )
    listing_session = SimpleNamespace(
        lookup=lambda **_kwargs: SimpleNamespace(
            evidence=tuple(listing_evidence),
            facts=tuple(listing_facts),
            blockers=listing_codes,
            diagnostics={},
        )
    )
    monkeypatch.setattr(
        scheduler,
        "_ibkr_evidence",
        lambda *_args, **_kwargs: (
            SimpleNamespace(evidence=(), blockers=(), requests_made=0),
            (),
        ),
    )
    states = []
    monkeypatch.setattr(
        scheduler,
        "_pending_event_monitoring",
        lambda *_args, source_family_results, **_kwargs: (
            states.append(source_family_results["listing_authority"]) or None
        ),
    )
    case = {
        "case_id": f"slc_{scenario}",
        "ticker": "OLD",
        "ticker_aliases": ("OLD",),
        "ibkr_conids": (),
        "observation": {
            "ticker": "OLD",
            "cik": "0000000001",
            "issuer_name": "Requiredness Issuer",
            "filing_date": "2026-08-20",
            "source_ref": "0000000001-26-000001",
            "filing_form": "8-K",
            "filing_items": ["3.01"],
            "kinds": [
                {"event_type": "acquisition_completed", "effective_date": None}
            ],
        },
    }

    bundle = scheduler._load_evidence(
        case,
        mode="live",
        at="2026-08-26T00:00:00Z",
        listing_session=listing_session,
    )

    assert tuple(row.code for row in bundle.blockers) == expected_codes
    assert states == [expected_state]


def test_real_session_filters_optional_massive_parser_failure_for_nms_successor(
    monkeypatch,
):
    from data_sources import sec_transport
    from data_sources.listing_authority_transport import (
        MASSIVE_TICKERS_URL,
        NASDAQ_LISTED_URL,
        OTHER_LISTED_URL,
        ListingHttpPayload,
        ListingRequestBudget,
    )
    from src import security_lifecycle_sec_evidence
    from src.security_lifecycle_listing_evidence import ListingAuthoritySession
    from src.service import security_lifecycle_automation_scheduler as scheduler

    retrieved_at = "2026-08-29T22:00:00Z"
    fixture_dir = Path(__file__).parent / "fixtures" / "listing_authority"
    exact_bodies = {
        NASDAQ_LISTED_URL: (fixture_dir / "nasdaqlisted.txt").read_bytes(),
        OTHER_LISTED_URL: (fixture_dir / "otherlisted.txt").read_bytes(),
    }

    class FakeProductionTransport:
        def __init__(self):
            self.calls = []

        def fetch_nasdaq(self, source_url, *, budget):
            self.calls.append(source_url)
            budget.reserve_nasdaq_request(source_url)
            body = exact_bodies[source_url]
            budget.record_nasdaq_body(len(body))
            return ListingHttpPayload(
                source_url=source_url,
                retrieved_at=retrieved_at,
                status_code=200,
                content_type="text/plain",
                body=body,
            )

        def fetch_massive_ticker(
            self,
            ticker,
            *,
            expected_active,
            market,
            api_key,
            budget,
        ):
            del api_key
            identity = (ticker, expected_active, market)
            self.calls.append(identity)
            budget.reserve_massive_request(identity)
            body = b'{"results":"secret-provider-surplus","status":"OK"}'
            budget.record_massive_body(len(body))
            return ListingHttpPayload(
                source_url=(
                    f"{MASSIVE_TICKERS_URL}?ticker={ticker}&active=true"
                    f"&market={market}&limit=2"
                ),
                retrieved_at=retrieved_at,
                status_code=200,
                content_type="application/json",
                body=body,
            )

        def close(self):
            pass

    class SecTransport:
        @staticmethod
        def diagnostics(_budget):
            return {"attempt_count": 1}

        def close(self):
            pass

    sec_evidence = (
        SimpleNamespace(
            evidence_id="sec-nms-parser-boundary",
            source_family="regulator",
            source_locator={"filing_chain_complete": True},
            retrieved_at=retrieved_at,
        ),
    )
    sec_facts = tuple(
        _authority_fact("sec-nms-parser-boundary", fact_type, value)
        for fact_type, value in (
            ("source_ticker", "OLD"),
            ("successor_ticker", "AAPL"),
            ("destination_venue", "NASDAQ"),
            ("effective_date", "2026-08-29"),
            ("issuer_cik", "0000320193"),
            ("security_class", "common_stock"),
            ("tracked_security_effect", "symbol_change"),
        )
    )
    monkeypatch.setattr(sec_transport, "SecTransport", SecTransport)
    monkeypatch.setattr(
        security_lifecycle_sec_evidence,
        "collect_sec_evidence",
        lambda **_kwargs: SimpleNamespace(
            evidence=sec_evidence,
            facts=sec_facts,
            blockers=(),
            source_deadlines=(),
        ),
    )
    monkeypatch.setattr(
        scheduler,
        "_ibkr_evidence",
        lambda *_args, **_kwargs: (
            SimpleNamespace(evidence=(), blockers=(), requests_made=0),
            (),
        ),
    )
    transport = FakeProductionTransport()
    session = ListingAuthoritySession(
        transport=transport,
        budget=ListingRequestBudget.lifecycle(),
        retrieved_at=retrieved_at,
        massive_api_key="fixture-key",
    )
    case = {
        "case_id": "slc_nms_parser_boundary",
        "ticker": "OLD",
        "ticker_aliases": ("OLD",),
        "ibkr_conids": (),
        "observation": {
            "ticker": "OLD",
            "cik": "0000320193",
            "issuer_name": "NMS Boundary Issuer",
            "filing_date": "2026-08-28",
            "source_ref": "0000320193-26-000001",
            "filing_form": "8-K",
            "filing_items": ["5.03"],
            "kinds": [{"event_type": "symbol_change", "effective_date": None}],
        },
    }

    bundle = scheduler._load_evidence(
        case,
        mode="live",
        at=retrieved_at,
        listing_session=session,
    )

    assert bundle.blockers == ()
    assert any(
        getattr(row, "adapter", None) == "nasdaq_symbol_directory"
        and row.source_locator["candidate_ticker"] == "AAPL"
        and row.source_locator["listing_status"] == "active"
        for row in bundle.evidence
    )
    assert ("OLD", True, "stocks") in transport.calls
    assert "secret-provider-surplus" not in repr(bundle)


def test_terminal_massive_requiredness_changes_on_effective_date_through_scheduler(
    tmp_path,
    monkeypatch,
):
    from data_sources import sec_transport
    from data_sources.listing_authority_transport import (
        NASDAQ_LISTED_URL,
        OTHER_LISTED_URL,
        ListingHttpPayload,
    )
    from src import security_lifecycle_sec_evidence
    from src.security_lifecycle_fact_kernel import AutomationEvidence, AutomationFact
    from src.security_lifecycle_investigation import (
        SecurityLifecycleInvestigationStore,
        case_id_for,
    )
    from src.service import security_lifecycle_automation_scheduler as scheduler

    fixture_dir = Path(__file__).parent / "fixtures" / "listing_authority"
    exact_bodies = {
        NASDAQ_LISTED_URL: (fixture_dir / "nasdaqlisted.txt").read_bytes(),
        OTHER_LISTED_URL: (fixture_dir / "otherlisted.txt").read_bytes(),
    }
    transport_calls = []
    transport_times = iter(
        ("2026-08-29T12:00:00Z", "2026-08-30T12:00:00Z")
    )

    class FakeProductionTransport:
        def __init__(self):
            self.retrieved_at = next(transport_times)

        def fetch_nasdaq(self, source_url, *, budget):
            transport_calls.append((self.retrieved_at, source_url))
            budget.reserve_nasdaq_request(source_url)
            body = exact_bodies[source_url]
            budget.record_nasdaq_body(len(body))
            return ListingHttpPayload(
                source_url=source_url,
                retrieved_at=self.retrieved_at,
                status_code=200,
                content_type="text/plain",
                body=body,
            )

        def fetch_massive_ticker(self, *_args, **_kwargs):
            raise AssertionError("missing key must stop before provider transport")

        @staticmethod
        def diagnostics(budget):
            return budget.diagnostics()

        def close(self):
            pass

    class SecTransport:
        @staticmethod
        def diagnostics(_budget):
            return {"attempt_count": 1}

        def close(self):
            pass

    source_ref = "0000000002-26-000001"
    case_id = case_id_for("sec_edgar", source_ref, "OLD")
    case = {
        "case_id": case_id,
        "source": "sec_edgar",
        "source_ref": source_ref,
        "ticker": "OLD",
        "ticker_aliases": ("OLD",),
        "ibkr_conids": (),
        "source_presence": "present",
        "observation_fingerprint_sha256": "a" * 64,
        "observation": {
            "ticker": "OLD",
            "cik": "0000000002",
            "issuer_name": "Boundary Issuer",
            "filing_date": "2026-08-28",
            "source": "sec_edgar",
            "source_ref": source_ref,
            "filing_form": "25",
            "filing_items": [],
            "evidence_url": "https://www.sec.gov/Archives/boundary.htm",
            "description": "Terminal listing event.",
            "kinds": [
                {"event_type": "listing_removal_notice", "effective_date": None}
            ],
        },
    }

    def collect_sec_evidence(*, retrieved_at, **_kwargs):
        values = {
            "effective_date": "2026-08-30",
            "issuer_cik": "0000000002",
            "security_class": "common_stock",
            "source_ticker": "OLD",
            "tracked_security_effect": "terminal_delisting",
        }
        excerpt = json.dumps(values, separators=(",", ":"), sort_keys=True)
        evidence = AutomationEvidence(
            evidence_id=f"sec-boundary-{retrieved_at[:10]}",
            source_family="regulator",
            adapter="sec_edgar",
            kind="regulator_excerpt",
            source_url=case["observation"]["evidence_url"],
            title="Boundary filing fixture",
            publisher="SEC EDGAR",
            domain="sec.gov",
            source_published_at="2026-08-28",
            retrieved_at=retrieved_at,
            excerpt=excerpt,
            content_sha256=hashlib.sha256(excerpt.encode()).hexdigest(),
            source_document_sha256="d" * 64,
            source_locator={"filing_chain_complete": True},
            evidence_dedupe_key=f"sec:boundary:{retrieved_at[:10]}",
        )
        facts = []
        for fact_type, value in values.items():
            cited = json.dumps(value).encode()
            start = excerpt.encode().index(cited)
            facts.append(
                AutomationFact(
                    evidence_id=evidence.evidence_id,
                    fact_type=fact_type,
                    normalized_value=value,
                    source_span_start=start,
                    source_span_end=start + len(cited),
                    cited_text_sha256=hashlib.sha256(cited).hexdigest(),
                    extractor_rule_id=f"fixture.{fact_type}",
                    extractor_rule_version="1",
                )
            )
        return SimpleNamespace(
            evidence=(evidence,),
            facts=tuple(facts),
            blockers=(),
            source_deadlines=(),
        )

    conn = sqlite3.connect(tmp_path / "profile.db", check_same_thread=False)
    SecurityLifecycleInvestigationStore(conn)

    @contextmanager
    def profile_connection():
        yield conn

    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    monkeypatch.setattr(scheduler, "ListingAuthorityTransport", FakeProductionTransport)
    monkeypatch.setattr(sec_transport, "SecTransport", SecTransport)
    monkeypatch.setattr(
        security_lifecycle_sec_evidence,
        "collect_sec_evidence",
        collect_sec_evidence,
    )
    monkeypatch.setattr(scheduler, "_assert_automation_installed", lambda: None)
    monkeypatch.setattr(scheduler, "_load_cases", lambda: (case,))
    monkeypatch.setattr(scheduler, "_profile_connection", profile_connection)
    monkeypatch.setattr(scheduler, "_load_sources", lambda: {"OLD": ("manual_lists",)})
    monkeypatch.setattr(
        scheduler,
        "_ibkr_evidence",
        lambda *_args, **_kwargs: (
            SimpleNamespace(evidence=(), blockers=(), requests_made=0),
            (),
        ),
    )
    monkeypatch.setattr(
        scheduler,
        "_transition_preview",
        lambda *, request, **_kwargs: {
            "eligible": True,
            "block_reasons": (),
            "transition_kind": request["transition_kind"],
        },
    )
    monkeypatch.setattr(
        scheduler,
        "_transition_approver",
        lambda **_kwargs: {
            "status": "approved",
            "approval_authority": "automation_policy",
        },
    )
    try:
        before = scheduler.run_security_lifecycle_automation(
            limit=1,
            now=datetime(2026, 8, 29, 12, tzinfo=timezone.utc),
        )
        store = SecurityLifecycleInvestigationStore(conn)
        assert before == _v2_summary(
            selected=1,
            processed=1,
            drafted=1,
            case_ids=[case_id],
            case_outcomes={case_id: "drafted"},
        )
        before_run = store.list_automation_runs(case_id)[0]
        assert before_run["decision_tier"] == "verified_automatic"
        assert before_run["action_readiness"] == "waiting_effective_date"
        assert store.list_assessments(case_id)[0]["status"] == "draft"

        due = scheduler.run_security_lifecycle_automation(
            limit=1,
            now=datetime(2026, 8, 30, 12, tzinfo=timezone.utc),
        )
        assert due == _v2_summary(
            status="partial",
            reason="case_processing_blocked",
            selected=1,
            processed=1,
            blocked=1,
            case_ids=[case_id],
            case_outcomes={case_id: "blocked"},
        )
        due_run = store.list_automation_runs(case_id)[0]
        assert due_run["status"] == "blocked"
        assert [row["blocker_code"] for row in due_run["blockers"]] == [
            "massive_credential_missing"
        ]
        assert transport_calls == [
            ("2026-08-29T12:00:00Z", NASDAQ_LISTED_URL),
            ("2026-08-29T12:00:00Z", OTHER_LISTED_URL),
            ("2026-08-30T12:00:00Z", NASDAQ_LISTED_URL),
            ("2026-08-30T12:00:00Z", OTHER_LISTED_URL),
        ]
    finally:
        conn.close()


def test_pending_event_monitoring_uses_explicit_dates_and_final_source_check():
    from src.security_lifecycle_sec_evidence import SecSourceDeadline
    from src.service import security_lifecycle_automation_scheduler as scheduler

    case = {
        "observation": {
            "kinds": [{"event_type": "merger_agreement", "effective_date": None}]
        }
    }
    facts = (
        SimpleNamespace(fact_type="effective_date", value="2026-09-05"),
        SimpleNamespace(
            fact_type="transaction_structure",
            value={"kind": "stock", "terms_status": "complete"},
        ),
    )
    deadline = SecSourceDeadline(
        date="2026-10-15",
        evidence_id="sle_deadline",
        span_start_byte=10,
        span_end_byte=80,
        cited_text="The merger may be terminated by October 15, 2026.",
        cited_text_sha256="a" * 64,
        rule_id="sec.explicit_transaction_termination_date",
        rule_version="4",
    )

    before_effective = scheduler._pending_event_monitoring(
        case,
        facts,
        source_family_results={
            "regulator": "available",
            "market_infrastructure": "available",
            "listing_authority": "available",
        },
        source_deadlines=(deadline,),
        at="2026-08-26T00:00:00Z",
    )
    assert before_effective is not None
    assert before_effective.retryable is True
    assert before_effective.context["monitoring_reason"] == (
        "event_completion_not_confirmed"
    )
    assert before_effective.context["next_check_at"] == "2026-09-05T00:00:00Z"

    daily = scheduler._pending_event_monitoring(
        case,
        facts,
        source_family_results={},
        source_deadlines=(deadline,),
        at="2026-09-10T00:00:00Z",
    )
    assert daily is not None
    assert daily.context["next_check_at"] == "2026-09-11T00:00:00Z"

    weekly = scheduler._pending_event_monitoring(
        case,
        facts,
        source_family_results={},
        source_deadlines=(deadline,),
        at="2026-09-13T00:00:00Z",
    )
    assert weekly is not None
    assert weekly.context["next_check_at"] == "2026-09-20T00:00:00Z"

    deadline = replace(deadline, date="2026-04-01", rule_version="4")
    final = scheduler._pending_event_monitoring(
        case,
        facts,
        source_family_results={
            "regulator": "available",
            "market_infrastructure": "available",
            "listing_authority": "available",
        },
        source_deadlines=(deadline,),
        at="2026-08-27T12:00:00Z",
    )
    assert final is not None
    assert final.retryable is False
    assert final.context["monitoring_reason"] == "not_confirmed_as_of"
    assert final.context["source_deadline"] == "2026-04-01"
    assert final.context["as_of"] == "2026-08-27"
    assert final.context["source_deadline_evidence_id"] == "sle_deadline"
    assert final.context["source_deadline_rule_version"] == "4"

    unavailable_final_check = scheduler._pending_event_monitoring(
        case,
        facts,
        source_family_results={
            "regulator": "available",
            "market_infrastructure": "available",
            "listing_authority": "unavailable",
        },
        source_deadlines=(deadline,),
        at="2026-10-15T12:00:00Z",
    )
    assert unavailable_final_check is not None
    assert unavailable_final_check.retryable is True
    assert unavailable_final_check.context["monitoring_reason"] == (
        "event_completion_not_confirmed"
    )
    assert unavailable_final_check.context["next_check_at"] == (
        "2026-10-22T12:00:00Z"
    )


def test_pending_event_monitoring_rejects_multiple_deadline_dates():
    from src.service import security_lifecycle_automation_scheduler as scheduler

    case = {
        "observation": {
            "kinds": [{"event_type": "merger_agreement", "effective_date": None}]
        }
    }

    try:
        scheduler._pending_event_monitoring(
            case,
            (),
            source_family_results={},
            source_deadlines=(
                SimpleNamespace(
                    date="2026-09-01",
                    evidence_id="deadline-a",
                    span_start_byte=0,
                    span_end_byte=1,
                    cited_text_sha256="a" * 64,
                    rule_id="sec.explicit_transaction_termination_date",
                    rule_version="4",
                ),
                SimpleNamespace(
                    date="2026-10-01",
                    evidence_id="deadline-b",
                    span_start_byte=0,
                    span_end_byte=1,
                    cited_text_sha256="b" * 64,
                    rule_id="sec.explicit_transaction_termination_date",
                    rule_version="4",
                ),
            ),
            at="2026-08-26T00:00:00Z",
        )
    except ValueError as exc:
        assert str(exc) == "source_deadlines"
    else:
        raise AssertionError("multiple deadline dates must fail closed")


def test_acquisition_scheduling_rejects_multiple_deadline_dates_before_market_work(
    monkeypatch,
):
    from data_sources import sec_transport
    from src import security_lifecycle_sec_evidence
    from src.service import security_lifecycle_automation_scheduler as scheduler

    class Transport:
        def diagnostics(self, _budget):
            return {"attempt_count": 0}

        def close(self):
            pass

    case = {
        "case_id": "slc_deadline_conflict",
        "ticker": "DEAD",
        "ticker_aliases": ("DEAD",),
        "ibkr_conids": (),
        "observation": {
            "ticker": "DEAD",
            "cik": "0000000001",
            "issuer_name": "Deadline Conflict Issuer",
            "filing_date": "2026-08-20",
            "source": "sec_edgar",
            "source_ref": "0000000001-26-000001",
            "filing_form": "8-K",
            "filing_items": ["1.01"],
            "evidence_url": "https://www.sec.gov/Archives/deadline.htm",
            "description": "Agreement with conflicting outside dates.",
            "kinds": [{"event_type": "merger_agreement", "effective_date": None}],
        },
    }
    monkeypatch.setattr(sec_transport, "SecTransport", Transport)
    monkeypatch.setattr(
        security_lifecycle_sec_evidence,
        "collect_sec_evidence",
        lambda **_kwargs: SimpleNamespace(
            evidence=(),
            facts=(),
            blockers=(),
            source_deadlines=(
                SimpleNamespace(date="2026-08-25"),
                SimpleNamespace(date="2026-08-26"),
            ),
        ),
    )
    monkeypatch.setattr(
        scheduler,
        "_ibkr_evidence",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("market work must not start")
        ),
    )

    try:
        scheduler._load_evidence(
            case,
            mode="live",
            at="2026-08-27T00:00:00Z",
            listing_session=SimpleNamespace(
                lookup=lambda **_kwargs: (_ for _ in ()).throw(
                    AssertionError("listing work must not start")
                )
            ),
        )
    except ValueError as exc:
        assert str(exc) == "source_deadlines"
    else:
        raise AssertionError("conflicting deadline dates must fail before market work")


def test_deadline_without_effective_date_caps_schedule_and_triggers_final_market_check(
    monkeypatch,
):
    from data_sources import sec_transport
    from src import security_lifecycle_sec_evidence
    from src.security_lifecycle_sec_evidence import SecSourceDeadline
    from src.service import security_lifecycle_automation_scheduler as scheduler

    case = {
        "case_id": "slc_deadline_only",
        "ticker": "DEAD",
        "ticker_aliases": ("DEAD",),
        "ibkr_conids": (),
        "observation": {
            "ticker": "DEAD",
            "cik": "0000000001",
            "issuer_name": "Deadline Only Issuer",
            "filing_date": "2026-08-20",
            "source": "sec_edgar",
            "source_ref": "0000000001-26-000001",
            "filing_form": "8-K",
            "filing_items": ["1.01"],
            "evidence_url": "https://www.sec.gov/Archives/deadline.htm",
            "description": "Agreement with an outside date.",
            "kinds": [{"event_type": "merger_agreement", "effective_date": None}],
        },
    }
    deadline = SecSourceDeadline(
        date="2026-08-30",
        evidence_id="deadline-evidence",
        span_start_byte=0,
        span_end_byte=64,
        cited_text="The outside date remains August 30, 2026.",
        cited_text_sha256="a" * 64,
        rule_id="sec.explicit_transaction_termination_date",
        rule_version="4",
    )
    before = scheduler._pending_event_monitoring(
        case,
        (),
        source_family_results={
            "regulator": "available",
            "listing_authority": "available",
        },
        source_deadlines=(deadline,),
        at="2026-08-27T12:00:00Z",
    )
    assert before is not None
    assert before.context["next_check_at"] == "2026-08-30T00:00:00Z"

    class Transport:
        def diagnostics(self, _budget):
            return {"attempt_count": 1}

        def close(self):
            pass

    market_calls = []
    monkeypatch.setattr(sec_transport, "SecTransport", Transport)
    monkeypatch.setattr(
        security_lifecycle_sec_evidence,
        "collect_sec_evidence",
        lambda **_kwargs: SimpleNamespace(
            evidence=(),
            facts=(),
            blockers=("sec_evidence_insufficient",),
            source_deadlines=(deadline,),
        ),
    )
    listing_session = SimpleNamespace(
        lookup=lambda **_kwargs: SimpleNamespace(
            evidence=(), facts=(), blockers=(), diagnostics={}
        )
    )

    def ibkr(context, *, at, regulator_successors, max_queries):
        market_calls.append((context.case_id, at, regulator_successors, max_queries))
        return SimpleNamespace(evidence=(), blockers=(), requests_made=1), ()

    monkeypatch.setattr(scheduler, "_ibkr_evidence", ibkr)
    bundle = scheduler._load_evidence(
        case,
        mode="live",
        at="2026-08-30T12:00:00Z",
        listing_session=listing_session,
        ibkr_max_queries=3,
    )

    assert market_calls == [
        ("slc_deadline_only", "2026-08-30T12:00:00Z", (), 3)
    ]
    assert bundle.diagnostics["ibkr_requests"] == 1
    assert len(bundle.blockers) == 1
    assert bundle.blockers[0].retryable is False
    assert bundle.blockers[0].context["monitoring_reason"] == "not_confirmed_as_of"
    assert bundle.retry_at is None


def test_pending_without_source_deadline_never_becomes_timeless_negative():
    from src.service import security_lifecycle_automation_scheduler as scheduler

    case = {
        "observation": {
            "kinds": [{"event_type": "merger_proxy", "effective_date": None}]
        }
    }
    blocker = scheduler._pending_event_monitoring(
        case,
        (),
        source_family_results={
            "regulator": "available",
            "market_infrastructure": "available",
            "listing_authority": "available",
        },
        source_deadlines=(),
        at="2027-08-26T00:00:00Z",
    )
    assert blocker is not None
    assert blocker.retryable is True
    assert blocker.context == {
        "monitoring_reason": "event_completion_not_confirmed",
        "next_check_at": "2027-09-02T00:00:00Z",
    }


def test_effective_date_never_substitutes_for_source_termination_deadline():
    from src.service import security_lifecycle_automation_scheduler as scheduler

    case = {
        "observation": {
            "kinds": [{"event_type": "merger_proxy", "effective_date": None}]
        }
    }
    facts = (SimpleNamespace(fact_type="effective_date", value="2026-09-05"),)

    blocker = scheduler._pending_event_monitoring(
        case,
        facts,
        source_family_results={
            "regulator": "available",
            "market_infrastructure": "available",
            "listing_authority": "available",
        },
        source_deadlines=(),
        at="2027-08-26T00:00:00Z",
    )

    assert blocker is not None
    assert blocker.retryable is True
    assert blocker.context == {
        "monitoring_reason": "event_completion_not_confirmed",
        "effective_date": "2026-09-05",
        "next_check_at": "2027-09-02T00:00:00Z",
    }


def test_completed_or_resolved_event_does_not_create_monitoring_blocker():
    from src.service import security_lifecycle_automation_scheduler as scheduler

    completed = {
        "observation": {
            "kinds": [{"event_type": "acquisition_completed", "effective_date": None}]
        }
    }
    assert scheduler._pending_event_monitoring(
        completed,
        (),
        source_family_results={},
        source_deadlines=(),
        at="2026-08-26T00:00:00Z",
    ) is None

    resolved = {
        "observation": {
            "kinds": [{"event_type": "merger_agreement", "effective_date": None}]
        }
    }
    facts = (
        SimpleNamespace(
            fact_type="tracked_security_effect",
            value="no_identity_change",
        ),
    )
    assert scheduler._pending_event_monitoring(
        resolved,
        facts,
        source_family_results={},
        source_deadlines=(),
        at="2026-08-26T00:00:00Z",
    ) is None


def test_blocker_normalization_preserves_typed_context_and_retry_schedule():
    from src.security_lifecycle_fact_kernel import AutomationBlocker
    from src.service import security_lifecycle_automation_scheduler as scheduler

    pending = AutomationBlocker(
        code="sec_evidence_insufficient",
        retryable=True,
        context={
            "monitoring_reason": "event_completion_not_confirmed",
            "next_check_at": "2026-09-05T00:00:00Z",
        },
    )
    blockers, retry_at = scheduler._blockers([pending], at="2026-08-26T00:00:00Z")
    assert blockers == (pending,)
    assert retry_at == "2026-09-05T00:00:00Z"
