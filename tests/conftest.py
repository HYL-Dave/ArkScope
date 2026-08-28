"""Suite-wide test hygiene."""

from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path
from urllib.parse import unquote

import pytest


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_PROJECT_PROFILE_DB = (_PROJECT_ROOT / "data" / "profile_state.db").resolve()
_SESSION_PROFILE_DIR = tempfile.TemporaryDirectory(prefix="arkscope-pytest-profile-")
_SESSION_PROFILE_DB = Path(_SESSION_PROFILE_DIR.name) / "profile_state.db"
os.environ["ARKSCOPE_PROFILE_DB"] = str(_SESSION_PROFILE_DB)

_REAL_SQLITE_CONNECT = sqlite3.connect


def _sqlite_target_path(database) -> Path | None:
    try:
        raw = os.fspath(database)
    except TypeError:
        return None
    if isinstance(raw, bytes):
        raw = os.fsdecode(raw)
    if raw == ":memory:" or raw.startswith("file::memory:"):
        return None
    if raw.startswith("file:"):
        raw = unquote(raw.removeprefix("file:").split("?", 1)[0])
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


def _guarded_sqlite_connect(database, *args, **kwargs):
    if _sqlite_target_path(database) == _PROJECT_PROFILE_DB:
        raise RuntimeError("pytest attempted to access the production profile DB")
    return _REAL_SQLITE_CONNECT(database, *args, **kwargs)


# Install before test-module collection. Per-test fixtures are too late to stop
# import-time stores from resolving the developer's profile database.
sqlite3.connect = _guarded_sqlite_connect


@pytest.fixture(autouse=True)
def _disable_app_scheduler(monkeypatch):
    """TestClient(create_app()) runs the real lifespan, which starts the data
    scheduler — its seed/tick threads can reach external services (FastAPI
    dependency_overrides don't apply outside request resolution). In a
    TCP-stalling environment the seed thread outlives the test and hangs
    pytest at the thread-pool atexit join. Hermetic by default; a test that
    really wants the scheduler can monkeypatch.delenv this key.
    """
    monkeypatch.setenv("ARKSCOPE_DISABLE_SCHEDULER", "1")


@pytest.fixture(autouse=True)
def _isolate_locks(tmp_path_factory, monkeypatch):
    """Cross-process flocks live under data/locks/ by default — tests must not
    contend with (or leave artifacts in) the real lock dir."""
    if "ARKSCOPE_LOCK_DIR" not in os.environ:
        monkeypatch.setenv("ARKSCOPE_LOCK_DIR", str(tmp_path_factory.mktemp("locks")))


@pytest.fixture(autouse=True)
def _isolate_profile_db(tmp_path_factory, monkeypatch):
    """The profile-state DB (LLM credentials, model routes, data-provider config)
    defaults to data/profile_state.db. Any DEFAULT-path store — e.g. the model-route
    store behind ``task_route``/``resolve_research_route`` — must read a throwaway DB,
    never the real dev one, or a route saved via the app would leak into resolution-
    layer tests. Override UNCONDITIONALLY (unlike _isolate_locks): a profile DB carries
    credentials + routes, so honoring an ambient ARKSCOPE_PROFILE_DB would leak real dev
    state into tests; monkeypatch restores any prior value on teardown. Tests that inject
    an explicit db_path are unaffected."""
    monkeypatch.setenv(
        "ARKSCOPE_PROFILE_DB",
        str(tmp_path_factory.mktemp("profile") / "profile_state.db"),
    )


@pytest.fixture(autouse=True)
def _isolate_agent_local_config(tmp_path_factory, monkeypatch):
    """Operator-only model overrides must never become test authority."""
    from src.agents import config as config_module

    cached_get_agent_config = config_module.get_agent_config
    monkeypatch.setattr(
        config_module,
        "_LOCAL_CONFIG_PATH",
        tmp_path_factory.mktemp("agent_config") / "user_profile.local.yaml",
    )
    cached_get_agent_config.cache_clear()
    yield
    cached_get_agent_config.cache_clear()


@pytest.fixture(autouse=True)
def _isolate_macro_calendar_db(tmp_path_factory, monkeypatch):
    """Macro/calendar runtime defaults to data/macro_calendar.db.

    After N9 batch-2 the macro store no longer depends on DAL backend shape, so
    tests that pass a dummy/FileBackend DAL can still instantiate the real local
    store. Point the default at a throwaway DB to avoid touching the developer's
    live macro_calendar.db.
    """
    monkeypatch.setenv(
        "ARKSCOPE_MACRO_CALENDAR_DB",
        str(tmp_path_factory.mktemp("macro_calendar") / "macro_calendar.db"),
    )


@pytest.fixture(autouse=True)
def _isolate_sa_db(tmp_path_factory, monkeypatch):
    """SA capture runtime defaults to data/sa_capture.db.

    Every DAL construction routes the SA domain to the current capture backend,
    so a test that builds a DAL would
    otherwise resolve the developer's real sa_capture.db. Override
    unconditionally like _isolate_macro_calendar_db; tests that need a specific
    DB set it themselves after this autouse fixture.
    """
    monkeypatch.setenv(
        "ARKSCOPE_SA_DB", str(tmp_path_factory.mktemp("sa_capture") / "sa_capture.db")
    )
