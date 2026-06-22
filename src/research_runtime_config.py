"""AI Research runtime limits, app-managed in the local profile DB.

These settings are intentionally scoped to the AI 研究 surface. They control the
Research runtime loop/driver limits, not global card synthesis/translation agent
behavior. File config remains fallback + import seed; DB is the Settings authority.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from src.agents.config import _load_user_profile, get_agent_config

logger = logging.getLogger(__name__)

RuntimeSource = Literal["env", "db", "profile", "default"]

DEFAULT_MAX_TOOL_CALLS = 60
DEFAULT_SESSION_TIMEOUT_S = 900.0
DEFAULT_PER_TOOL_TIMEOUT_S = 45.0

ENV_MAX_TOOL_CALLS = "ARKSCOPE_RESEARCH_MAX_TOOL_CALLS"
ENV_SESSION_TIMEOUT_S = "ARKSCOPE_RESEARCH_SESSION_TIMEOUT_S"
ENV_PER_TOOL_TIMEOUT_S = "ARKSCOPE_RESEARCH_PER_TOOL_TIMEOUT_S"

YAML_MAX_TOOL_CALLS = "max_tool_calls"
YAML_SESSION_TIMEOUT_S = "claude_subscription_timeout_s"
YAML_PER_TOOL_TIMEOUT_S = "research_per_tool_timeout_s"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_runtime_config (
    id                 INTEGER PRIMARY KEY CHECK (id = 1),
    max_tool_calls     INTEGER NOT NULL,
    session_timeout_s  REAL NOT NULL,
    per_tool_timeout_s REAL NOT NULL,
    updated_at         TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class ResearchRuntimeRow:
    max_tool_calls: int
    session_timeout_s: float
    per_tool_timeout_s: float
    updated_at: str


@dataclass(frozen=True)
class ResearchRuntimeSettings:
    max_tool_calls: int
    session_timeout_s: float
    per_tool_timeout_s: float
    source: RuntimeSource
    db_saved: bool = False
    warning: str | None = None

    def model_dump(self) -> dict:
        return asdict(self)


def _validate(
    *,
    max_tool_calls: int,
    session_timeout_s: float,
    per_tool_timeout_s: float,
) -> tuple[int, float, float]:
    try:
        mt = int(max_tool_calls)
        st = float(session_timeout_s)
        pt = float(per_tool_timeout_s)
    except (TypeError, ValueError) as exc:
        raise ValueError("research runtime values must be numeric") from exc
    if not (1 <= mt <= 500):
        raise ValueError("max_tool_calls must be between 1 and 500")
    if not (0 <= st <= 86400):
        raise ValueError("session_timeout_s must be between 0 and 86400")
    if not (1 <= pt <= 3600):
        raise ValueError("per_tool_timeout_s must be between 1 and 3600")
    return mt, st, pt


class ResearchRuntimeStore:
    """Single-row Research runtime limits in the local profile DB."""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = os.environ.get("ARKSCOPE_PROFILE_DB") or str(
                Path(__file__).resolve().parents[1] / "data" / "profile_state.db")
        self._db_path = str(db_path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10.0)
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn

    def _ensure_schema(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _row(r: tuple) -> ResearchRuntimeRow:
        return ResearchRuntimeRow(
            max_tool_calls=int(r[0]),
            session_timeout_s=float(r[1]),
            per_tool_timeout_s=float(r[2]),
            updated_at=r[3],
        )

    def get(self) -> ResearchRuntimeRow | None:
        conn = self._connect()
        try:
            r = conn.execute(
                "SELECT max_tool_calls, session_timeout_s, per_tool_timeout_s, updated_at "
                "FROM research_runtime_config WHERE id = 1"
            ).fetchone()
        finally:
            conn.close()
        return self._row(r) if r else None

    def set(
        self,
        *,
        max_tool_calls: int,
        session_timeout_s: float,
        per_tool_timeout_s: float,
    ) -> ResearchRuntimeRow:
        mt, st, pt = _validate(
            max_tool_calls=max_tool_calls,
            session_timeout_s=session_timeout_s,
            per_tool_timeout_s=per_tool_timeout_s,
        )
        now = _now()
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO research_runtime_config "
                "(id, max_tool_calls, session_timeout_s, per_tool_timeout_s, updated_at) "
                "VALUES (1, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET "
                "max_tool_calls = excluded.max_tool_calls, "
                "session_timeout_s = excluded.session_timeout_s, "
                "per_tool_timeout_s = excluded.per_tool_timeout_s, "
                "updated_at = excluded.updated_at",
                (mt, st, pt, now),
            )
            conn.commit()
        finally:
            conn.close()
        return ResearchRuntimeRow(mt, st, pt, now)

    def delete(self) -> bool:
        conn = self._connect()
        try:
            cur = conn.execute("DELETE FROM research_runtime_config WHERE id = 1")
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def _profile_fallback() -> tuple[int, float, float, bool, list[str]]:
    cfg = get_agent_config()
    profile = _load_user_profile()
    llm = profile.get("llm_preferences", {})
    if not isinstance(llm, dict):
        llm = {}
    raw_per_tool = llm.get(YAML_PER_TOOL_TIMEOUT_S, DEFAULT_PER_TOOL_TIMEOUT_S)
    source_present = any(k in llm for k in (YAML_MAX_TOOL_CALLS, YAML_SESSION_TIMEOUT_S, YAML_PER_TOOL_TIMEOUT_S))
    warnings: list[str] = []
    try:
        max_calls = int(cfg.max_tool_calls)
        session_timeout = float(cfg.claude_subscription_timeout_s)
        per_tool = float(raw_per_tool)
        mt, st, pt = _validate(
            max_tool_calls=max_calls,
            session_timeout_s=session_timeout,
            per_tool_timeout_s=per_tool,
        )
        return mt, st, pt, source_present, warnings
    except ValueError as exc:
        warnings.append(f"profile research runtime ignored: {exc}")
        return DEFAULT_MAX_TOOL_CALLS, DEFAULT_SESSION_TIMEOUT_S, DEFAULT_PER_TOOL_TIMEOUT_S, False, warnings


def _default_store() -> ResearchRuntimeStore:
    return ResearchRuntimeStore()


def resolve_research_runtime(store: ResearchRuntimeStore | None = None) -> ResearchRuntimeSettings:
    """Resolve Research runtime limits: real env → DB → yaml profile → defaults."""
    warnings: list[str] = []
    max_calls, session_timeout, per_tool, has_profile, profile_warnings = _profile_fallback()
    warnings.extend(profile_warnings)
    source: RuntimeSource = "profile" if has_profile else "default"

    try:
        row = (store or _default_store()).get()
    except Exception:  # pragma: no cover - defensive fallback
        logger.warning("research_runtime_config DB read failed; using profile/default", exc_info=True)
        row = None
    if row is not None:
        max_calls = row.max_tool_calls
        session_timeout = row.session_timeout_s
        per_tool = row.per_tool_timeout_s
        source = "db"
    db_saved = row is not None

    env_used = False
    for env_name, field in (
        (ENV_MAX_TOOL_CALLS, "max_tool_calls"),
        (ENV_SESSION_TIMEOUT_S, "session_timeout_s"),
        (ENV_PER_TOOL_TIMEOUT_S, "per_tool_timeout_s"),
    ):
        raw = os.environ.get(env_name)
        if raw is None:
            continue
        try:
            if field == "max_tool_calls":
                max_calls = int(raw)
            elif field == "session_timeout_s":
                session_timeout = float(raw)
            else:
                per_tool = float(raw)
            env_used = True
        except ValueError:
            warnings.append(f"{env_name} ignored: not numeric")

    try:
        max_calls, session_timeout, per_tool = _validate(
            max_tool_calls=max_calls,
            session_timeout_s=session_timeout,
            per_tool_timeout_s=per_tool,
        )
    except ValueError as exc:
        warnings.append(str(exc))
        max_calls, session_timeout, per_tool = (
            DEFAULT_MAX_TOOL_CALLS, DEFAULT_SESSION_TIMEOUT_S, DEFAULT_PER_TOOL_TIMEOUT_S)
        source = "default"

    if env_used:
        source = "env"
    return ResearchRuntimeSettings(
        max_tool_calls=max_calls,
        session_timeout_s=session_timeout,
        per_tool_timeout_s=per_tool,
        source=source,
        db_saved=db_saved,
        warning=" ".join(warnings) or None,
    )
