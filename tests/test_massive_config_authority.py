from __future__ import annotations

import sqlite3

import pytest

import src.data_provider_config as config
from src.data_provider_config import DataProviderConfigStore
from src.massive_config_migration import (
    MassiveConfigMigrationApprovalMismatch,
    MassiveConfigMigrationConflict,
    migrate_massive_config_authority,
    preflight_massive_config_migration,
)


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


def test_legacy_only_row_moves_exactly_and_preserves_timestamp(tmp_path) -> None:
    path = tmp_path / "profile.db"
    DataProviderConfigStore(path)
    secret = "legacy-massive-secret"
    updated_at = "2026-07-25T03:04:05+00:00"
    _insert(path, provider="polygon", value=secret, updated_at=updated_at)
    before_preflight = path.read_bytes()

    approval = preflight_massive_config_migration(profile_path=path)

    assert path.read_bytes() == before_preflight
    assert approval.state == "legacy_only"
    assert approval.eligible is True
    assert secret not in repr(approval)

    result = migrate_massive_config_authority(
        profile_path=path,
        approval_sha256=approval.approval_sha256,
    )

    assert result.changed is True
    assert result.before_state == "legacy_only"
    assert result.after_state == "current_only"
    assert _rows(path) == [("massive", "api_key", secret, updated_at)]


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


def test_equal_duplicate_keeps_current_row_and_removes_legacy(tmp_path) -> None:
    path = tmp_path / "profile.db"
    DataProviderConfigStore(path)
    _insert(
        path,
        provider="polygon",
        value="same-secret",
        updated_at="2026-07-01T00:00:00+00:00",
    )
    _insert(
        path,
        provider="massive",
        value="same-secret",
        updated_at="2026-08-01T00:00:00+00:00",
    )
    approval = preflight_massive_config_migration(profile_path=path)

    assert approval.state == "duplicate_equal"
    result = migrate_massive_config_authority(
        profile_path=path,
        approval_sha256=approval.approval_sha256,
    )

    assert result.changed is True
    assert _rows(path) == [
        ("massive", "api_key", "same-secret", "2026-08-01T00:00:00+00:00")
    ]


def test_different_duplicate_fails_closed_without_writes(tmp_path) -> None:
    path = tmp_path / "profile.db"
    DataProviderConfigStore(path)
    _insert(
        path,
        provider="polygon",
        value="legacy-secret",
        updated_at="2026-07-01T00:00:00+00:00",
    )
    _insert(
        path,
        provider="massive",
        value="current-secret",
        updated_at="2026-08-01T00:00:00+00:00",
    )
    before = _rows(path)
    approval = preflight_massive_config_migration(profile_path=path)

    assert approval.state == "conflict"
    assert approval.eligible is False
    with pytest.raises(MassiveConfigMigrationConflict):
        migrate_massive_config_authority(
            profile_path=path,
            approval_sha256=approval.approval_sha256,
        )

    assert _rows(path) == before


@pytest.mark.parametrize("provider", [None, "massive"])
def test_absent_or_current_only_migration_is_an_idempotent_noop(
    tmp_path,
    provider: str | None,
) -> None:
    path = tmp_path / "profile.db"
    DataProviderConfigStore(path)
    if provider:
        _insert(
            path,
            provider=provider,
            value="current-secret",
            updated_at="2026-08-01T00:00:00+00:00",
        )
    before = _rows(path)
    approval = preflight_massive_config_migration(profile_path=path)

    result = migrate_massive_config_authority(
        profile_path=path,
        approval_sha256=approval.approval_sha256,
    )

    assert result.changed is False
    assert _rows(path) == before


def test_apply_rejects_a_stale_preflight_under_the_write_lock(tmp_path) -> None:
    path = tmp_path / "profile.db"
    DataProviderConfigStore(path)
    _insert(
        path,
        provider="polygon",
        value="legacy-secret",
        updated_at="2026-07-01T00:00:00+00:00",
    )
    approval = preflight_massive_config_migration(profile_path=path)
    with sqlite3.connect(path) as conn:
        conn.execute(
            "UPDATE data_provider_config SET updated_at = ? "
            "WHERE provider = 'polygon' AND field = 'api_key'",
            ("2026-07-02T00:00:00+00:00",),
        )
    before = _rows(path)

    with pytest.raises(MassiveConfigMigrationApprovalMismatch):
        migrate_massive_config_authority(
            profile_path=path,
            approval_sha256=approval.approval_sha256,
        )

    assert _rows(path) == before
