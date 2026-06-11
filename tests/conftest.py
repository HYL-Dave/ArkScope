"""Suite-wide test hygiene."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _disable_app_scheduler(monkeypatch):
    """TestClient(create_app()) runs the real lifespan, which starts the data
    scheduler — its seed/tick threads reach the real PG/network (FastAPI
    dependency_overrides don't apply outside request resolution). In a PG-less
    or TCP-stalling environment the seed thread outlives the test and hangs
    pytest at the thread-pool atexit join. Hermetic by default; a test that
    really wants the scheduler can monkeypatch.delenv this key.
    """
    monkeypatch.setenv("ARKSCOPE_DISABLE_SCHEDULER", "1")


@pytest.fixture(autouse=True)
def _isolate_locks(tmp_path_factory, monkeypatch):
    """Cross-process flocks live under data/locks/ by default — tests must not
    contend with (or leave artifacts in) the real lock dir."""
    if "ARKSCOPE_LOCK_DIR" not in os.environ:
        monkeypatch.setenv(
            "ARKSCOPE_LOCK_DIR", str(tmp_path_factory.mktemp("locks")))
