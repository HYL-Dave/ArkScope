"""Tests for the 3d SA-capture flip mechanism (prep-4): use_local_sa selection matrix."""

from __future__ import annotations

import sys
import types

import pytest

from src.profile_state import ProfileStateStore
from src.tools.data_access import DataAccessLayer


class _StubSABackend:
    """Stands in for SACaptureDatabaseBackend (built in parallel by prep-2) so the
    matrix tests are hermetic — they assert SELECTION, not backend behavior."""

    def __init__(self, dsn, sslmode="prefer", *, sa_db, market_db="", strict=False):
        self.dsn, self.sa_db, self.market_db, self.strict = dsn, sa_db, market_db, strict


class _StubLMDB:
    def __init__(self, dsn, sslmode="prefer", *, market_db, strict=False):
        self.dsn, self.market_db, self.strict = dsn, market_db, strict


class _StubPG:
    def __init__(self, dsn, sslmode="prefer"):
        self.dsn = dsn


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Isolated profile DB + DB paths; both toggles off; stub backend classes."""
    profile = tmp_path / "profile_state.db"
    ProfileStateStore(profile)  # create schema
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(profile))
    monkeypatch.delenv("ARKSCOPE_USE_LOCAL_MARKET", raising=False)
    monkeypatch.delenv("ARKSCOPE_USE_LOCAL_SA", raising=False)
    market_db = tmp_path / "market_data.db"
    sa_db = tmp_path / "sa_capture.db"
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(market_db))
    monkeypatch.setenv("ARKSCOPE_SA_DB", str(sa_db))

    # stub modules so selection works without the real (parallel-built) backend
    sa_mod = types.ModuleType("src.tools.backends.sa_capture_backend")
    sa_mod.SACaptureDatabaseBackend = _StubSABackend
    monkeypatch.setitem(sys.modules, "src.tools.backends.sa_capture_backend", sa_mod)
    lm_mod = types.ModuleType("src.tools.backends.local_market_backend")
    lm_mod.LocalMarketDatabaseBackend = _StubLMDB
    monkeypatch.setitem(sys.modules, "src.tools.backends.local_market_backend", lm_mod)
    monkeypatch.setattr("src.tools.data_access.DatabaseBackend", _StubPG)

    dal = DataAccessLayer.__new__(DataAccessLayer)
    dal._base = tmp_path
    return types.SimpleNamespace(
        dal=dal, profile=ProfileStateStore(profile),
        market_db=market_db, sa_db=sa_db,
    )


def _make(env):
    return env.dal._make_db_backend("postgresql://fake/db", "prefer")


def test_both_off_plain_pg(env):
    assert isinstance(_make(env), _StubPG)


def test_market_only(env):
    env.profile.set_setting("use_local_market", "true")
    env.market_db.write_bytes(b"")  # exists
    b = _make(env)
    assert isinstance(b, _StubLMDB) and b.market_db == str(env.market_db)
    assert b.strict is False


def test_sa_only_market_inert(env):
    env.profile.set_setting("use_local_sa", "true")
    env.sa_db.write_bytes(b"")
    b = _make(env)
    assert isinstance(b, _StubSABackend)
    assert b.sa_db == str(env.sa_db)
    assert b.market_db == ""  # market routing inert


def test_both_on_one_instance_serves_both(env):
    env.profile.set_setting("use_local_sa", "true")
    env.profile.set_setting("use_local_market", "true")
    env.sa_db.write_bytes(b"")
    env.market_db.write_bytes(b"")
    b = _make(env)
    assert isinstance(b, _StubSABackend)
    assert b.sa_db == str(env.sa_db) and b.market_db == str(env.market_db)
    assert b.strict is False


def test_market_strict_threads_to_selected_backend(env):
    env.profile.set_setting("use_local_market", "true")
    env.profile.set_setting("use_local_market_strict", "true")
    env.market_db.write_bytes(b"")
    b = _make(env)
    assert isinstance(b, _StubLMDB)
    assert b.market_db == str(env.market_db)
    assert b.strict is True


def test_sa_plus_market_strict_threads_to_single_backend(env):
    env.profile.set_setting("use_local_sa", "true")
    env.profile.set_setting("use_local_market", "true")
    env.profile.set_setting("use_local_market_strict", "true")
    env.sa_db.write_bytes(b"")
    env.market_db.write_bytes(b"")
    b = _make(env)
    assert isinstance(b, _StubSABackend)
    assert b.sa_db == str(env.sa_db) and b.market_db == str(env.market_db)
    assert b.strict is True


def test_sa_toggle_without_db_stays_pg(env):
    # flip-before-migration safety: enabling the toggle with no sa_capture.db on
    # disk must keep PG — identical to the market-toggle guard.
    env.profile.set_setting("use_local_sa", "true")
    assert isinstance(_make(env), _StubPG)


def test_env_override_flips_without_setting(env, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_USE_LOCAL_SA", "1")
    env.sa_db.write_bytes(b"")
    assert isinstance(_make(env), _StubSABackend)


def test_rollback_is_instant_per_construction(env):
    # the flip/rollback story: fresh DAL constructions (native host = one per
    # message) re-read the persisted key each time.
    env.profile.set_setting("use_local_sa", "true")
    env.sa_db.write_bytes(b"")
    assert isinstance(_make(env), _StubSABackend)
    env.profile.set_setting("use_local_sa", "false")   # rollback = flip back
    assert isinstance(_make(env), _StubPG)


def test_migration_cli_refuses_rebuild_post_flip(env, monkeypatch):
    # runbook L1/L5: after the flip sa_capture.db is the AUTHORITY — a rebuild from
    # PG would destroy captures PG never saw. The build path must refuse, no override.
    import scripts.migrate_sa_to_sqlite as mig
    env.profile.set_setting("use_local_sa", "true")
    monkeypatch.setattr(sys, "argv", ["migrate_sa_to_sqlite.py", "--out", str(env.sa_db)])
    assert mig.main() == 2  # refused

    env.profile.set_setting("use_local_sa", "false")  # deliberate rollback → allowed
    monkeypatch.setattr(mig, "_pg_conn", lambda: (_ for _ in ()).throw(RuntimeError("no PG in test")))
    with pytest.raises(RuntimeError):
        mig.main()  # passes the guard, fails only at the (stubbed) PG connect
