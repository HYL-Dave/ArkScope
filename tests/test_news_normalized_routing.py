from __future__ import annotations

import sqlite3
from dataclasses import FrozenInstanceError

import pytest

from src.news_normalized.routing import (
    ENV_USE_LOCAL_NEWS,
    ENV_USE_NORMALIZED_NEWS_WRITES,
    NEWS_PG_EXIT_COMPLETED_KEY,
    USE_LOCAL_NEWS_KEY,
    USE_NORMALIZED_NEWS_WRITES_KEY,
    NewsWriteMode,
    NewsWriteRoute,
    read_news_write_route,
    resolve_news_write_route,
)


@pytest.mark.parametrize(
    ("exit_done", "normalized", "local", "expected"),
    [
        (False, True, True, NewsWriteMode.NORMALIZED),
        (False, True, False, NewsWriteMode.NORMALIZED),
        (False, True, None, NewsWriteMode.NORMALIZED),
        (False, False, True, NewsWriteMode.LEGACY_LOCAL),
        (False, False, False, NewsWriteMode.LEGACY_PG),
        (False, False, None, NewsWriteMode.LEGACY_LOCAL),
        (False, None, True, NewsWriteMode.LEGACY_LOCAL),
        (False, None, False, NewsWriteMode.LEGACY_PG),
        (False, None, None, NewsWriteMode.LEGACY_LOCAL),
        (True, True, True, NewsWriteMode.NORMALIZED),
        (True, True, False, NewsWriteMode.NORMALIZED),
        (True, True, None, NewsWriteMode.NORMALIZED),
        (True, False, True, NewsWriteMode.BLOCKED),
        (True, False, False, NewsWriteMode.BLOCKED),
        (True, False, None, NewsWriteMode.BLOCKED),
        (True, None, True, NewsWriteMode.NORMALIZED),
        (True, None, False, NewsWriteMode.NORMALIZED),
        (True, None, None, NewsWriteMode.NORMALIZED),
    ],
)
def test_route_matrix(exit_done, normalized, local, expected):
    route = resolve_news_write_route(
        exit_completed=exit_done,
        normalized_value=normalized,
        local_value=local,
    )

    assert route.mode is expected
    assert route.reason


def test_route_reuses_news_toggle_string_semantics():
    route = resolve_news_write_route(
        exit_completed="off",
        normalized_value="YES",
        local_value="0",
    )

    assert route.mode is NewsWriteMode.NORMALIZED


def test_environment_values_override_profile_values():
    route = resolve_news_write_route(
        exit_completed=False,
        normalized_value=False,
        local_value=False,
        normalized_env="on",
        local_env="off",
    )

    assert route.mode is NewsWriteMode.NORMALIZED


def test_local_environment_value_overrides_profile_value():
    route = resolve_news_write_route(
        exit_completed=False,
        normalized_value=None,
        local_value=True,
        local_env="false",
    )

    assert route.mode is NewsWriteMode.LEGACY_PG


def test_explicit_normalized_environment_false_blocks_after_exit():
    route = resolve_news_write_route(
        exit_completed=True,
        normalized_value=True,
        local_value=True,
        normalized_env="false",
    )

    assert route.mode is NewsWriteMode.BLOCKED
    assert "PG" in route.reason
    assert "retired" in route.reason.lower()


def test_route_is_immutable():
    route = NewsWriteRoute(NewsWriteMode.NORMALIZED, "test")

    with pytest.raises(FrozenInstanceError):
        route.reason = "changed"


def test_read_news_write_route_uses_profile_and_environment(tmp_path):
    db = tmp_path / "profile_state.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE profile_settings (key TEXT PRIMARY KEY, value TEXT)")
    conn.executemany(
        "INSERT INTO profile_settings VALUES (?, ?)",
        [
            (NEWS_PG_EXIT_COMPLETED_KEY, "true"),
            (USE_NORMALIZED_NEWS_WRITES_KEY, "true"),
            (USE_LOCAL_NEWS_KEY, "true"),
        ],
    )
    conn.commit()
    conn.close()

    route = read_news_write_route(
        profile_db=db,
        environ={
            ENV_USE_NORMALIZED_NEWS_WRITES: "false",
            ENV_USE_LOCAL_NEWS: "false",
        },
    )

    assert route.mode is NewsWriteMode.BLOCKED
    assert "retired" in route.reason.lower()


def test_read_news_write_route_defaults_without_profile_database(tmp_path):
    route = read_news_write_route(profile_db=tmp_path / "missing.db", environ={})

    assert route.mode is NewsWriteMode.LEGACY_LOCAL
    assert not (tmp_path / "missing.db").exists()
