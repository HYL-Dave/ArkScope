from __future__ import annotations

import sqlite3

import pytest

import src.data_provider_config as config
from src.data_provider_config import DataProviderConfigStore


def _insert(
    path,
    *,
    provider: str,
    value: str,
    updated_at: str,
) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "INSERT INTO data_provider_config "
            "(provider, field, value, updated_at) VALUES (?, 'api_key', ?, ?)",
            (provider, value, updated_at),
        )


def _rows(path) -> list[tuple[str, str, str, str]]:
    with sqlite3.connect(path) as conn:
        return conn.execute(
            "SELECT provider, field, value, updated_at "
            "FROM data_provider_config ORDER BY provider, field"
        ).fetchall()


def test_massive_is_the_only_current_config_namespace(tmp_path) -> None:
    path = tmp_path / "profile.db"
    store = DataProviderConfigStore(path)

    assert "massive" in config.PROVIDER_FIELDS
    assert "polygon" not in config.PROVIDER_FIELDS
    store.set_field("massive", "api_key", "massive-current-secret")

    assert store.get_all() == {
        "massive": {"api_key": "massive-current-secret"},
    }
    with pytest.raises(KeyError, match=r"polygon\.api_key"):
        store.set_field("polygon", "api_key", "legacy-secret")


def test_store_startup_does_not_implicitly_migrate_a_legacy_row(tmp_path) -> None:
    path = tmp_path / "profile.db"
    DataProviderConfigStore(path)
    _insert(
        path,
        provider="polygon",
        value="legacy-secret",
        updated_at="2026-07-01T00:00:00+00:00",
    )
    before = _rows(path)

    DataProviderConfigStore(path)

    assert _rows(path) == before
