from __future__ import annotations

from datetime import datetime, timezone

import pytest


def test_execution_lock_is_exclusive_and_issues_a_bounded_owner_id(
    tmp_path,
    monkeypatch,
):
    from src.service.security_lifecycle_automation_runtime import (
        LifecycleAutomationAlreadyRunning,
        lifecycle_automation_execution_lock,
    )

    monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path / "locks"))

    with lifecycle_automation_execution_lock() as first:
        assert first.execution_owner_id
        assert len(first.execution_owner_id.encode("utf-8")) <= 64
        with pytest.raises(LifecycleAutomationAlreadyRunning) as busy:
            with lifecycle_automation_execution_lock():
                pytest.fail("a second execution acquired the lifecycle lock")

    assert busy.value.code == "already_running"
    with lifecycle_automation_execution_lock() as second:
        assert second.execution_owner_id != first.execution_owner_id
        assert len(second.execution_owner_id.encode("utf-8")) <= 64


def test_progress_registry_follows_the_exact_real_stage_order_and_finishes_cleanly():
    from src.service.security_lifecycle_automation_runtime import (
        LifecycleAutomationProgressRegistry,
    )

    registry = LifecycleAutomationProgressRegistry()
    started_at = datetime(2026, 8, 31, 2, 3, 4, tzinfo=timezone.utc)
    expected_stages = (
        "preparing",
        "sec",
        "listing",
        "ibkr",
        "evaluate",
        "persist",
        "approve",
        "finalize",
    )

    first = registry.begin(
        trigger="manual_case",
        request_id="request-1",
        case_id="case-1",
        started_at=started_at,
    )
    assert first.trigger == "manual_case"
    assert first.request_id == "request-1"
    assert first.case_id == "case-1"
    assert first.started_at == started_at
    assert first.current_stage == "preparing"
    assert first.completed_stages == ()
    assert first.skipped_stages == ()

    for index, stage in enumerate(expected_stages[1:], start=1):
        current = registry.advance(
            request_id="request-1",
            case_id="case-1",
            stage=stage,
        )
        assert current.current_stage == stage
        assert current.completed_stages == expected_stages[:index]
        assert current.skipped_stages == ()

    finished = registry.finish(request_id="request-1", case_id="case-1")
    assert finished.current_stage is None
    assert finished.completed_stages == expected_stages
    assert finished.skipped_stages == ()
    assert registry.snapshot(request_id="request-1", case_id="case-1") == ()


def test_progress_registry_records_only_explicit_conditional_stage_skips():
    from src.service.security_lifecycle_automation_runtime import (
        LifecycleAutomationProgressRegistry,
    )

    registry = LifecycleAutomationProgressRegistry()
    registry.begin(
        trigger="scheduler",
        request_id="request-2",
        case_id="case-2",
        started_at=datetime(2026, 8, 31, tzinfo=timezone.utc),
    )
    registry.advance(request_id="request-2", case_id="case-2", stage="sec")
    registry.advance(request_id="request-2", case_id="case-2", stage="listing")

    without_ibkr = registry.advance(
        request_id="request-2",
        case_id="case-2",
        stage="evaluate",
        skipped_stages=("ibkr",),
    )
    assert without_ibkr.completed_stages == ("preparing", "sec", "listing")
    assert without_ibkr.skipped_stages == ("ibkr",)

    registry.advance(request_id="request-2", case_id="case-2", stage="persist")
    without_approval = registry.advance(
        request_id="request-2",
        case_id="case-2",
        stage="finalize",
        skipped_stages=("approve",),
    )
    assert without_approval.completed_stages == (
        "preparing",
        "sec",
        "listing",
        "evaluate",
        "persist",
    )
    assert without_approval.skipped_stages == ("ibkr", "approve")

    finished = registry.finish(request_id="request-2", case_id="case-2")
    assert finished.completed_stages == (
        "preparing",
        "sec",
        "listing",
        "evaluate",
        "persist",
        "finalize",
    )
    assert finished.skipped_stages == ("ibkr", "approve")


def test_progress_registry_rejects_stage_jumps_and_nonconditional_skips_without_drift():
    from src.service.security_lifecycle_automation_runtime import (
        LifecycleAutomationProgressRegistry,
    )

    registry = LifecycleAutomationProgressRegistry()
    registry.begin(
        trigger="manual_due",
        request_id="request-3",
        case_id="case-3",
        started_at=datetime(2026, 8, 31, tzinfo=timezone.utc),
    )

    with pytest.raises(ValueError, match="automation_progress_stage_order"):
        registry.advance(
            request_id="request-3",
            case_id="case-3",
            stage="listing",
        )
    with pytest.raises(ValueError, match="automation_progress_stage_skip"):
        registry.advance(
            request_id="request-3",
            case_id="case-3",
            stage="listing",
            skipped_stages=("sec",),
        )
    with pytest.raises(ValueError, match="automation_progress_not_finalizing"):
        registry.finish(request_id="request-3", case_id="case-3")

    assert (
        registry.snapshot(request_id="request-3", case_id="case-3")[0].current_stage
        == "preparing"
    )


def test_progress_registry_still_rejects_a_backwards_stage():
    from src.service.security_lifecycle_automation_runtime import (
        LifecycleAutomationProgressRegistry,
    )

    registry = LifecycleAutomationProgressRegistry()
    registry.begin(
        trigger="scheduler",
        request_id="request-backwards-stage",
        case_id="case-backwards-stage",
        started_at=datetime(2026, 8, 31, tzinfo=timezone.utc),
        initial_stage="finalize",
    )

    with pytest.raises(ValueError, match="automation_progress_stage_order"):
        registry.advance(
            request_id="request-backwards-stage",
            case_id="case-backwards-stage",
            stage="approve",
        )

    remaining = registry.snapshot(
        request_id="request-backwards-stage",
        case_id="case-backwards-stage",
    )
    assert [row.current_stage for row in remaining] == ["finalize"]


def test_progress_registry_keys_snapshots_and_clear_by_request_and_case():
    from src.service.security_lifecycle_automation_runtime import (
        LifecycleAutomationProgressRegistry,
    )

    registry = LifecycleAutomationProgressRegistry()
    started_at = datetime(2026, 8, 31, tzinfo=timezone.utc)
    identities = (
        ("request-a", "case-a"),
        ("request-a", "case-b"),
        ("request-b", "case-a"),
    )
    for request_id, case_id in identities:
        registry.begin(
            trigger="scheduler",
            request_id=request_id,
            case_id=case_id,
            started_at=started_at,
        )

    assert [row.case_id for row in registry.snapshot(request_id="request-a")] == [
        "case-a",
        "case-b",
    ]
    assert [row.request_id for row in registry.snapshot(case_id="case-a")] == [
        "request-a",
        "request-b",
    ]
    with pytest.raises(ValueError, match="automation_progress_exists"):
        registry.begin(
            trigger="scheduler",
            request_id="request-a",
            case_id="case-a",
            started_at=started_at,
        )

    removed = registry.clear(request_id="request-a", case_id="case-a")
    assert removed is not None
    assert (removed.request_id, removed.case_id) == ("request-a", "case-a")
    assert registry.clear(request_id="request-a", case_id="case-a") is None
    assert [
        (row.request_id, row.case_id) for row in registry.snapshot()
    ] == [("request-a", "case-b"), ("request-b", "case-a")]


def test_progress_registry_is_ephemeral_and_never_reconstructs_another_instance():
    from src.service.security_lifecycle_automation_runtime import (
        LifecycleAutomationProgressRegistry,
    )

    first_process = LifecycleAutomationProgressRegistry()
    first_process.begin(
        trigger="scheduler",
        request_id="request-orphaned",
        case_id="case-orphaned",
        started_at=datetime(2026, 8, 31, tzinfo=timezone.utc),
    )

    restarted_process = LifecycleAutomationProgressRegistry()
    assert restarted_process.snapshot() == ()


@pytest.mark.parametrize(
    ("field", "value", "error"),
    (
        ("trigger", "manual_global", "automation_progress_trigger"),
        ("request_id", " request-1", "automation_progress_request_id"),
        ("case_id", "case-1 ", "automation_progress_case_id"),
        (
            "started_at",
            datetime(2026, 8, 31),
            "automation_progress_started_at",
        ),
    ),
)
def test_progress_registry_rejects_noncanonical_runtime_identity(
    field,
    value,
    error,
):
    from src.service.security_lifecycle_automation_runtime import (
        LifecycleAutomationProgressRegistry,
    )

    registry = LifecycleAutomationProgressRegistry()
    values = {
        "trigger": "manual_case",
        "request_id": "request-1",
        "case_id": "case-1",
        "started_at": datetime(2026, 8, 31, tzinfo=timezone.utc),
    }
    values[field] = value

    with pytest.raises(ValueError, match=error):
        registry.begin(**values)


@pytest.mark.parametrize("initial_stage", ("approve", "finalize"))
def test_progress_registry_can_start_at_a_real_recovery_boundary(initial_stage):
    from src.service.security_lifecycle_automation_runtime import (
        LifecycleAutomationProgressRegistry,
    )

    registry = LifecycleAutomationProgressRegistry()
    snapshot = registry.begin(
        trigger="scheduler",
        request_id=f"request-{initial_stage}",
        case_id=f"case-{initial_stage}",
        started_at=datetime(2026, 8, 31, tzinfo=timezone.utc),
        initial_stage=initial_stage,
    )

    assert snapshot.current_stage == initial_stage
    assert snapshot.completed_stages == ()
    assert snapshot.skipped_stages == ()

    if initial_stage == "approve":
        registry.advance(
            request_id=snapshot.request_id,
            case_id=snapshot.case_id,
            stage="finalize",
        )
    registry.finish(request_id=snapshot.request_id, case_id=snapshot.case_id)
