"""User-selected per-task model routes, app-managed in the local state DB.

Per `CONFIG_AUTHORITY_PLAN.md` §2, a model route is a **user-facing runtime
setting** → DB/Settings authority; `user_profile.local.yaml` becomes fallback +
import/export. This is the slice that proves the DB-first pattern (alongside
`data_provider_config.py`).

A route is a STRUCTURED row, not EAV: `provider`/`model`/`effort` are written
together (atomic upsert) so a save can never leave a half-applied route, and
`updated_at` is route-level. The store is storage-only — it does NOT constrain
`task` or `provider` (the registry in `model_routing.py` owns validation), so
adding a task (`news_filtering`, …) needs a new row + a code/UI registry update,
never a DB migration.

Storage: the local gitignored SQLite (same DB as profile state / LLM credentials /
data-provider config), table ``model_route``. Routes are NOT secret — no masking.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS model_route (
    task       TEXT PRIMARY KEY,
    provider   TEXT NOT NULL,
    model      TEXT NOT NULL,
    effort     TEXT NOT NULL DEFAULT 'default',
    updated_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class ModelRouteRow:
    task: str
    provider: str
    model: str
    effort: str
    updated_at: str


class ModelRouteStore:
    """``task`` → (provider, model, effort) in the local state DB. One row per task."""

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
    def _row(r: tuple) -> ModelRouteRow:
        return ModelRouteRow(task=r[0], provider=r[1], model=r[2], effort=r[3], updated_at=r[4])

    def get(self, task: str) -> ModelRouteRow | None:
        conn = self._connect()
        try:
            r = conn.execute(
                "SELECT task, provider, model, effort, updated_at FROM model_route WHERE task = ?",
                (task,),
            ).fetchone()
        finally:
            conn.close()
        return self._row(r) if r else None

    def get_all(self) -> dict[str, ModelRouteRow]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT task, provider, model, effort, updated_at FROM model_route"
            ).fetchall()
        finally:
            conn.close()
        return {r[0]: self._row(r) for r in rows}

    def set(self, task: str, provider: str, model: str, effort: str = "default") -> ModelRouteRow:
        """Atomic upsert of the whole route — provider/model/effort always land together."""
        now = _now()
        effort = (effort or "default").strip() or "default"
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO model_route (task, provider, model, effort, updated_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(task) DO UPDATE SET "
                "provider = excluded.provider, model = excluded.model, "
                "effort = excluded.effort, updated_at = excluded.updated_at",
                (task, provider, model, effort, now),
            )
            conn.commit()
        finally:
            conn.close()
        return ModelRouteRow(task=task, provider=provider, model=model, effort=effort, updated_at=now)

    def delete(self, task: str) -> bool:
        """Remove a task's route (resolution falls back to yaml/default). Idempotent."""
        conn = self._connect()
        try:
            cur = conn.execute("DELETE FROM model_route WHERE task = ?", (task,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()
