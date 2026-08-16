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

USE_NORMALIZED_NEWS_WRITES_KEY = "use_normalized_news_writes"

ENV_PROFILE_DB = "ARKSCOPE_PROFILE_DB"
ENV_USE_NORMALIZED_NEWS_WRITES = "ARKSCOPE_USE_NORMALIZED_NEWS_WRITES"


class NewsWriteMode(str, Enum):
    NORMALIZED = "normalized"
    LEGACY_LOCAL = "legacy_local"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class NewsWriteRoute:
    mode: NewsWriteMode
    reason: str


class NewsWriteConfigError(RuntimeError):
    """Profile state exists but cannot be read safely."""


def _resolved_toggle(profile_value: Any, env_value: Any) -> Optional[bool]:
    env = parse_news_toggle(env_value)
    return env if env is not None else parse_news_toggle(profile_value)


def _malformed_toggle(profile_value: Any, env_value: Any) -> bool:
    if env_value is not None:
        return parse_news_toggle(env_value) is None
    return profile_value is not None and parse_news_toggle(profile_value) is None


def resolve_news_write_route(
    normalized_required: Any,
    normalized_value: Any,
    local_value: Any,
    normalized_env: Any = None,
    local_env: Any = None,
) -> NewsWriteRoute:
    """Resolve the writer route without reading external state."""
    if not isinstance(normalized_required, bool):
        return NewsWriteRoute(
            NewsWriteMode.BLOCKED,
            "Normalized-writer requirement is malformed; refusing to select a route.",
        )
    if _malformed_toggle(normalized_value, normalized_env):
        return NewsWriteRoute(
            NewsWriteMode.BLOCKED,
            "Normalized-writer setting is malformed; refusing to select a route.",
        )
    if _malformed_toggle(local_value, local_env):
        return NewsWriteRoute(
            NewsWriteMode.BLOCKED,
            "Direct-local writer setting is malformed; refusing to select a route.",
        )
    normalized = _resolved_toggle(normalized_value, normalized_env)

    if normalized_required:
        if normalized is False:
            return NewsWriteRoute(
                NewsWriteMode.BLOCKED,
                "This source requires normalized writes; they cannot be disabled.",
            )
        return NewsWriteRoute(
            NewsWriteMode.NORMALIZED,
            "This source requires normalized writes.",
        )

    if normalized is True:
        return NewsWriteRoute(
            NewsWriteMode.NORMALIZED,
            "Normalized news writes are explicitly enabled.",
        )
    return NewsWriteRoute(
        NewsWriteMode.LEGACY_LOCAL,
        "Normalized writes are disabled or unset; the direct-local writer is selected.",
    )


def _default_profile_db() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "profile_state.db"


def _read_profile_values(profile_db: Union[str, Path]) -> Mapping[str, Any]:
    path = Path(profile_db)
    if not path.exists():
        return {}
    try:
        uri = f"{path.resolve().as_uri()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        try:
            rows = conn.execute(
                "SELECT key, value FROM profile_settings WHERE key IN (?, ?)",
                (
                    USE_NORMALIZED_NEWS_WRITES_KEY,
                    USE_LOCAL_NEWS_KEY,
                ),
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        raise NewsWriteConfigError(
            f"News writer profile settings could not be read: {exc}"
        ) from exc
    return dict(rows)


def read_news_write_route(
    profile_db: Optional[Union[str, Path]] = None,
    environ: Optional[Mapping[str, str]] = None,
    *,
    normalized_required: bool = False,
) -> NewsWriteRoute:
    """Read profile/env settings without creating or modifying the profile database."""
    env = os.environ if environ is None else environ
    db = profile_db or env.get(ENV_PROFILE_DB) or _default_profile_db()
    try:
        values = _read_profile_values(db)
    except NewsWriteConfigError as exc:
        return NewsWriteRoute(NewsWriteMode.BLOCKED, str(exc))
    return resolve_news_write_route(
        normalized_required=normalized_required,
        normalized_value=values.get(USE_NORMALIZED_NEWS_WRITES_KEY),
        local_value=values.get(USE_LOCAL_NEWS_KEY),
        normalized_env=env.get(ENV_USE_NORMALIZED_NEWS_WRITES),
        local_env=env.get(ENV_USE_LOCAL_NEWS),
    )
