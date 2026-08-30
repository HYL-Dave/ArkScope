from __future__ import annotations

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
