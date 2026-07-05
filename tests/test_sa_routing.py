"""Tests for SA-capture plus post-N9 local-market selection matrix."""

from __future__ import annotations

import sys
import types

import pytest

from src.profile_state import ProfileStateStore
from src.tools.data_access import DataAccessLayer


class _StubSABackend:
    """Stands in for SACaptureDatabaseBackend (built in parallel by prep-2) so the
    matrix tests are hermetic — they assert SELECTION, not backend behavior."""

    def __init__(self, dsn, sslmode="prefer", *, sa_db, market_db="", strict=False,
                 news_strict=False):
        self.dsn, self.sa_db, self.market_db, self.strict = dsn, sa_db, market_db, strict
        self.news_strict = news_strict


class _StubLMDB:
    def __init__(self, dsn, sslmode="prefer", *, market_db, strict=False, news_strict=False):
        self.dsn, self.market_db, self.strict = dsn, market_db, strict
        self.news_strict = news_strict


class _StubPG:
    def __init__(self, dsn, sslmode="prefer"):
        self.dsn = dsn


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Isolated profile DB + DB paths; local market defaults on; stub backend classes."""
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


def test_default_routes_sa_local(env):
    b = _make(env)
    assert isinstance(b, _StubSABackend)
    assert b.sa_db == str(env.sa_db)
    assert b.market_db == str(env.market_db)
    assert b.strict is True


def test_market_only(env):
    env.profile.set_setting("use_local_market", "true")
    env.market_db.write_bytes(b"")  # exists
    b = _make(env)
    assert isinstance(b, _StubSABackend)
    assert b.sa_db == str(env.sa_db)
    assert b.market_db == str(env.market_db)
    assert b.strict is True


def test_sa_only_still_threads_local_market(env):
    env.profile.set_setting("use_local_sa", "true")
    env.sa_db.write_bytes(b"")
    b = _make(env)
    assert isinstance(b, _StubSABackend)
    assert b.sa_db == str(env.sa_db)
    assert b.market_db == str(env.market_db)
    assert b.strict is True


def test_both_on_one_instance_serves_both(env):
    env.profile.set_setting("use_local_sa", "true")
    env.profile.set_setting("use_local_market", "true")
    env.sa_db.write_bytes(b"")
    env.market_db.write_bytes(b"")
    b = _make(env)
    assert isinstance(b, _StubSABackend)
    assert b.sa_db == str(env.sa_db) and b.market_db == str(env.market_db)
    assert b.strict is True


def test_market_strict_threads_to_selected_backend(env):
    env.profile.set_setting("use_local_market", "true")
    env.profile.set_setting("use_local_market_strict", "true")
    env.market_db.write_bytes(b"")
    b = _make(env)
    assert isinstance(b, _StubSABackend)
    assert b.sa_db == str(env.sa_db)
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


def test_news_exit_threads_news_strict_to_sa_backend_without_market_strict(env):
    env.profile.set_setting("use_local_sa", "true")
    env.profile.set_setting("use_local_market", "false")
    env.profile.set_setting("news_pg_exit_completed", "true")
    env.sa_db.write_bytes(b"")
    env.market_db.write_bytes(b"")
    b = _make(env)
    assert isinstance(b, _StubSABackend)
    assert b.sa_db == str(env.sa_db)
    assert b.market_db == str(env.market_db)
    assert b.news_strict is True
    assert b.strict is True


def test_sa_routes_local_even_without_existing_db_file(env):
    # PG sa_* tables are dropped (N9 batch-1): a missing local file must still
    # route local (honest empty), never resurrect the PG path.
    assert not env.sa_db.exists()
    b = _make(env)
    assert isinstance(b, _StubSABackend)
    assert b.sa_db == str(env.sa_db)


def test_env_override_flips_without_setting(env, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_USE_LOCAL_SA", "1")
    env.sa_db.write_bytes(b"")
    assert isinstance(_make(env), _StubSABackend)


def test_explicit_false_is_provenance_only(env):
    env.profile.set_setting("use_local_sa", "false")
    b = _make(env)
    assert isinstance(b, _StubSABackend)
    assert b.sa_db == str(env.sa_db)


def test_migration_cli_permanently_refuses_pg_paths(env, monkeypatch):
    # N9 batch-1 dropped PG sa_* — there is nothing to rebuild from, validate
    # against, or dry-run count. The batch-1 archive dump is the recovery basis.
    import scripts.migrate_sa_to_sqlite as mig

    monkeypatch.setattr(
        mig,
        "_pg_conn",
        lambda: (_ for _ in ()).throw(AssertionError("must not touch PG")),
    )

    for setting in ("true", "false", None):
        env.profile.set_setting("use_local_sa", setting)
        monkeypatch.setattr(
            sys, "argv", ["migrate_sa_to_sqlite.py", "--out", str(env.sa_db)]
        )
        assert mig.main() == 2

    monkeypatch.setattr(
        sys,
        "argv",
        ["migrate_sa_to_sqlite.py", "--out", str(env.sa_db), "--validate-only"],
    )
    assert mig.main() == 2

    monkeypatch.setattr(
        sys, "argv", ["migrate_sa_to_sqlite.py", "--out", str(env.sa_db), "--dry-run"]
    )
    assert mig.main() == 2


def test_baseless_dal_gets_no_implicit_local_routing(env, monkeypatch):
    # A DAL without a detected project root (virgin checkout before data/ exists,
    # zip-and-go before first boot) must keep the pre-collapse contract: no
    # implicit local routing, so the auto path falls through to FileBackend's
    # loud construction failure instead of a half-built DAL whose config reads
    # crash later with _base=None. Mirrors the market_db `if self._base` guard.
    monkeypatch.delenv("ARKSCOPE_MARKET_DB", raising=False)
    env.dal._base = None
    b = _make(env)
    assert isinstance(b, _StubPG)
