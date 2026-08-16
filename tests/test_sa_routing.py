"""Tests for the single current local data-owner construction path."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.profile_state import ProfileStateStore
from src.tools.data_access import DataAccessLayer


class _StubSABackend:
    def __init__(self, *, sa_db, market_db, base_path=None):
        self._sa_db = sa_db
        self.market_db = market_db
        self.base_path = Path(base_path) if base_path is not None else None


@pytest.fixture()
def env(tmp_path, monkeypatch):
    profile = ProfileStateStore(tmp_path / "profile_state.db")
    market_db = tmp_path / "market_data.db"
    sa_db = tmp_path / "sa_capture.db"
    monkeypatch.setenv("ARKSCOPE_PROFILE_DB", str(tmp_path / "profile_state.db"))
    monkeypatch.setenv("ARKSCOPE_MARKET_DB", str(market_db))
    monkeypatch.setenv("ARKSCOPE_SA_DB", str(sa_db))
    monkeypatch.setattr("src.tools.data_access.SACaptureBackend", _StubSABackend)
    return SimpleNamespace(
        base=tmp_path,
        profile=profile,
        market_db=market_db,
        sa_db=sa_db,
    )


def _make(env, *, base_path=True):
    base = env.base if base_path else None
    return DataAccessLayer(base_path=base)._backend


def _assert_current_owner(env, backend):
    assert isinstance(backend, _StubSABackend)
    assert backend._sa_db == str(env.sa_db)
    assert backend.market_db == str(env.market_db)


def test_default_routes_sa_local(env):
    _assert_current_owner(env, _make(env))


def test_market_only(env):
    env.profile.set_setting("use_local_market", "true")
    _assert_current_owner(env, _make(env))


def test_sa_only_still_threads_local_market(env):
    env.profile.set_setting("use_local_sa", "true")
    _assert_current_owner(env, _make(env))


def test_both_on_one_instance_serves_both(env):
    env.profile.set_setting("use_local_sa", "true")
    env.profile.set_setting("use_local_market", "true")
    backend = _make(env)
    _assert_current_owner(env, backend)
    assert backend.base_path == env.base


def test_legacy_market_strict_setting_does_not_change_local_owner(env):
    env.profile.set_setting("use_local_market_strict", "true")
    _assert_current_owner(env, _make(env))


def test_legacy_strict_settings_keep_single_local_owner(env):
    env.profile.set_setting("use_local_market_strict", "true")
    env.profile.set_setting("use_local_sa", "true")
    _assert_current_owner(env, _make(env))


def test_legacy_news_exit_setting_does_not_change_local_owner(env):
    env.profile.set_setting("unused_news_route_marker", "true")
    _assert_current_owner(env, _make(env))


def test_sa_routes_local_even_without_existing_db_file(env):
    assert not env.sa_db.exists()
    _assert_current_owner(env, _make(env))
    assert not env.sa_db.exists()


def test_legacy_environment_overrides_do_not_change_local_owner(env, monkeypatch):
    monkeypatch.setenv("ARKSCOPE_USE_LOCAL_SA", "0")
    monkeypatch.setenv("ARKSCOPE_USE_LOCAL_MARKET", "0")
    _assert_current_owner(env, _make(env))


def test_explicit_false_is_provenance_only(env):
    env.profile.set_setting("use_local_sa", "false")
    env.profile.set_setting("use_local_market", "false")
    _assert_current_owner(env, _make(env))


def test_baseless_dal_constructs_current_local_owner(env):
    backend = _make(env, base_path=False)
    _assert_current_owner(env, backend)
    assert backend.base_path is not None
