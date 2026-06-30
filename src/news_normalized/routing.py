"""Pure news-writer routing policy and read-only profile resolution."""
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Optional, Union

from src.news_providers import (
    ENV_USE_LOCAL_NEWS,
    USE_LOCAL_NEWS_KEY,
    parse_news_toggle,
)

NEWS_PG_EXIT_COMPLETED_KEY = "news_pg_exit_completed"
USE_NORMALIZED_NEWS_WRITES_KEY = "use_normalized_news_writes"

ENV_PROFILE_DB = "ARKSCOPE_PROFILE_DB"
ENV_USE_NORMALIZED_NEWS_WRITES = "ARKSCOPE_USE_NORMALIZED_NEWS_WRITES"


class NewsWriteMode(str, Enum):
    NORMALIZED = "normalized"
    LEGACY_LOCAL = "legacy_local"
    LEGACY_PG = "legacy_pg"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class NewsWriteRoute:
    mode: NewsWriteMode
    reason: str


def _resolved_toggle(profile_value: Any, env_value: Any) -> Optional[bool]:
    env = parse_news_toggle(env_value)
    return env if env is not None else parse_news_toggle(profile_value)


def resolve_news_write_route(
    exit_completed: Any,
    normalized_value: Any,
    local_value: Any,
    normalized_env: Any = None,
    local_env: Any = None,
) -> NewsWriteRoute:
    """Resolve the writer route without reading external state."""
    exit_done = parse_news_toggle(exit_completed) is True
    normalized = _resolved_toggle(normalized_value, normalized_env)
    local = _resolved_toggle(local_value, local_env)

    if exit_done:
        if normalized is False:
            return NewsWriteRoute(
                NewsWriteMode.BLOCKED,
                "PG news write route is retired after exit; normalized writes cannot be disabled.",
            )
        return NewsWriteRoute(
            NewsWriteMode.NORMALIZED,
            "PG exit is complete; normalized writes are required.",
        )

    if normalized is True:
        return NewsWriteRoute(
            NewsWriteMode.NORMALIZED,
            "Normalized news writes are explicitly enabled.",
        )
    if local is not False:
        return NewsWriteRoute(
            NewsWriteMode.LEGACY_LOCAL,
            "Normalized writes are disabled or unset; legacy local writes are enabled by default.",
        )
    return NewsWriteRoute(
        NewsWriteMode.LEGACY_PG,
        "Normalized and legacy local writes are disabled; use the pre-exit PG route.",
    )


def _default_profile_db() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "profile_state.db"


def _read_profile_values(profile_db: Union[str, Path]) -> Mapping[str, Any]:
    path = Path(profile_db)
    if not path.exists():
        return {}
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                "SELECT key, value FROM profile_settings WHERE key IN (?, ?, ?)",
                (
                    NEWS_PG_EXIT_COMPLETED_KEY,
                    USE_NORMALIZED_NEWS_WRITES_KEY,
                    USE_LOCAL_NEWS_KEY,
                ),
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.OperationalError:
        return {}
    return dict(rows)


def read_news_write_route(
    profile_db: Optional[Union[str, Path]] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> NewsWriteRoute:
    """Read profile/env settings without creating or modifying the profile database."""
    env = os.environ if environ is None else environ
    db = profile_db or env.get(ENV_PROFILE_DB) or _default_profile_db()
    values = _read_profile_values(db)
    return resolve_news_write_route(
        exit_completed=values.get(NEWS_PG_EXIT_COMPLETED_KEY),
        normalized_value=values.get(USE_NORMALIZED_NEWS_WRITES_KEY),
        local_value=values.get(USE_LOCAL_NEWS_KEY),
        normalized_env=env.get(ENV_USE_NORMALIZED_NEWS_WRITES),
        local_env=env.get(ENV_USE_LOCAL_NEWS),
    )
