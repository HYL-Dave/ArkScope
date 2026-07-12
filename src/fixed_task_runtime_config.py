"""Runtime limits for fixed, single-result AI tasks."""

from __future__ import annotations

import logging
import math
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Mapping, cast

from src.model_routing import TASKS, TaskId

logger = logging.getLogger(__name__)

RuntimeSource = Literal["env", "db", "default"]
DEFAULT_MODEL_TIMEOUT_S = 900.0
MIN_MODEL_TIMEOUT_S = 60.0
MAX_MODEL_TIMEOUT_S = 3600.0


@dataclass(frozen=True)
class FixedTaskRuntimeDefinition:
    task: TaskId
    label: str
    env_key: str
    default_timeout_s: float = DEFAULT_MODEL_TIMEOUT_S


FIXED_TASK_RUNTIME_TASKS: dict[TaskId, FixedTaskRuntimeDefinition] = {
    "card_synthesis": FixedTaskRuntimeDefinition(
        task="card_synthesis",
        label="AI 卡片生成",
        env_key="ARKSCOPE_CARD_SYNTHESIS_TIMEOUT_S",
    ),
    "card_translation": FixedTaskRuntimeDefinition(
        task="card_translation",
        label="卡片翻譯",
        env_key="ARKSCOPE_CARD_TRANSLATION_TIMEOUT_S",
    ),
}

_MODEL_ROUTE_TASKS = {task.id for task in TASKS}
assert all(
    key == definition.task and key in _MODEL_ROUTE_TASKS
    for key, definition in FIXED_TASK_RUNTIME_TASKS.items()
), "fixed-task runtime registry must use existing model-routing TaskId values"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS fixed_task_runtime_config (
    task            TEXT PRIMARY KEY,
    model_timeout_s REAL NOT NULL,
    updated_at      TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class FixedTaskRuntimeRow:
    task: TaskId
    model_timeout_s: float
    updated_at: str


@dataclass(frozen=True)
class FixedTaskRuntimeSettings:
    task: TaskId
    model_timeout_s: float
    source: RuntimeSource
    db_saved: bool = False
    warning: str | None = None

    def model_dump(self) -> dict:
        return asdict(self)


def validate_fixed_task_runtime_updates(
    updates: Mapping[str, object],
) -> dict[TaskId, float]:
    validated: dict[TaskId, float] = {}
    for raw_task, raw_value in updates.items():
        if raw_task not in FIXED_TASK_RUNTIME_TASKS:
            raise ValueError(f"unknown fixed task: {raw_task}")
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{raw_task}: model_timeout_s must be numeric") from exc
        if not math.isfinite(value) or not (
            MIN_MODEL_TIMEOUT_S <= value <= MAX_MODEL_TIMEOUT_S
        ):
            raise ValueError(
                f"{raw_task}: model_timeout_s must be between 60 and 3600"
            )
        validated[cast(TaskId, raw_task)] = value
    return validated


class FixedTaskRuntimeStore:
    """Task-keyed fixed runtime settings in the local profile DB."""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = os.environ.get("ARKSCOPE_PROFILE_DB") or str(
                Path(__file__).resolve().parents[1] / "data" / "profile_state.db"
            )
        self._db_path = str(db_path)
        self._ensure_schema()

    @property
    def db_path(self) -> str:
        return self._db_path

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

    def get_all(self) -> dict[TaskId, FixedTaskRuntimeRow]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT task, model_timeout_s, updated_at "
                "FROM fixed_task_runtime_config"
            ).fetchall()
        finally:
            conn.close()
        return {
            cast(TaskId, task): FixedTaskRuntimeRow(
                task=cast(TaskId, task),
                model_timeout_s=float(timeout_s),
                updated_at=updated_at,
            )
            for task, timeout_s, updated_at in rows
            if task in FIXED_TASK_RUNTIME_TASKS
        }

    def set_many(
        self,
        updates: Mapping[str, object],
    ) -> dict[TaskId, FixedTaskRuntimeRow]:
        validated = validate_fixed_task_runtime_updates(updates)
        now = _now()
        conn = self._connect()
        try:
            conn.executemany(
                "INSERT INTO fixed_task_runtime_config "
                "(task, model_timeout_s, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(task) DO UPDATE SET "
                "model_timeout_s = excluded.model_timeout_s, "
                "updated_at = excluded.updated_at",
                [(task, value, now) for task, value in validated.items()],
            )
            conn.commit()
        finally:
            conn.close()
        return {
            task: FixedTaskRuntimeRow(task, value, now)
            for task, value in validated.items()
        }

    def delete_all(self) -> bool:
        conn = self._connect()
        try:
            cursor = conn.execute("DELETE FROM fixed_task_runtime_config")
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


def _default_store() -> FixedTaskRuntimeStore:
    return FixedTaskRuntimeStore()


def resolve_all_fixed_task_runtime(
    *,
    store: FixedTaskRuntimeStore | None = None,
) -> dict[TaskId, FixedTaskRuntimeSettings]:
    warnings: list[str] = []
    try:
        rows = (store or _default_store()).get_all()
    except Exception:  # pragma: no cover - defensive fallback
        logger.warning(
            "fixed_task_runtime_config DB read failed; using defaults",
            exc_info=True,
        )
        rows = {}
        warnings.append("fixed-task runtime DB read failed; using defaults")

    resolved: dict[TaskId, FixedTaskRuntimeSettings] = {}
    for task, definition in FIXED_TASK_RUNTIME_TASKS.items():
        row = rows.get(task)
        value = row.model_timeout_s if row is not None else definition.default_timeout_s
        source: RuntimeSource = "db" if row is not None else "default"
        task_warnings = list(warnings)

        raw_env = os.environ.get(definition.env_key)
        if raw_env is not None:
            try:
                value = validate_fixed_task_runtime_updates({task: raw_env})[task]
                source = "env"
            except ValueError as exc:
                task_warnings.append(f"{definition.env_key} ignored: {exc}")

        resolved[task] = FixedTaskRuntimeSettings(
            task=task,
            model_timeout_s=value,
            source=source,
            db_saved=row is not None,
            warning=" ".join(task_warnings) or None,
        )
    return resolved


def resolve_fixed_task_runtime(
    task: TaskId,
    *,
    store: FixedTaskRuntimeStore | None = None,
) -> FixedTaskRuntimeSettings:
    if task not in FIXED_TASK_RUNTIME_TASKS:
        raise ValueError(f"unknown fixed task: {task}")
    return resolve_all_fixed_task_runtime(store=store)[task]
