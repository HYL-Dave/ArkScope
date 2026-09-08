"""One profile authority for the finite, snapshotted investigation budget."""

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from pydantic import BaseModel, ConfigDict, Field


class InvestigationRuntime(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    model_submissions: int = Field(default=24, ge=1, le=128)
    web_actions: int = Field(default=24, ge=1, le=192)
    source_reads: int = Field(default=32, ge=1, le=128)
    http_requests: int = Field(default=96, ge=1, le=512)
    local_queries: int = Field(default=20, ge=1, le=128)
    deadline_seconds: int = Field(default=1800, ge=60, le=7200)
    model_timeout_seconds: int = Field(default=600, ge=30, le=1800)
    api_output_tokens: int = Field(default=8192, ge=1024, le=131072)
    retained_source_mib: int = Field(default=512, ge=128, le=2048)


SQL = """CREATE TABLE lifecycle_investigation_runtime (
    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
    version INTEGER NOT NULL CHECK(version=1),
    config_json TEXT NOT NULL, updated_at TEXT NOT NULL)"""


def install_runtime(conn):
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='lifecycle_investigation_runtime'").fetchone()
    if row is None:
        conn.execute(SQL)
    elif " ".join(row[0].split()) != " ".join(SQL.split()):
        raise ValueError("investigation_runtime_schema_mismatch")


class RuntimeStore:
    def __init__(self, path):
        self.path = Path(path)

    def read(self):
        if not self.path.is_file():
            return InvestigationRuntime()
        with closing(sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='lifecycle_investigation_runtime'").fetchone():
                return InvestigationRuntime()
            install_runtime(conn)  # Existing tables are verified; a read never creates one.
            row = conn.execute("SELECT version,config_json FROM lifecycle_investigation_runtime WHERE singleton=1").fetchone()
        if row is None:
            return InvestigationRuntime()
        if row[0] != 1:
            raise ValueError("investigation_runtime_version")
        return InvestigationRuntime.model_validate_json(row[1])

    def save(self, value):
        value = InvestigationRuntime.model_validate(value.model_dump() if isinstance(value, InvestigationRuntime) else value)
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.execute("BEGIN IMMEDIATE")
            install_runtime(conn)
            conn.execute("INSERT INTO lifecycle_investigation_runtime VALUES(1,1,?,?) "
                "ON CONFLICT(singleton) DO UPDATE SET config_json=excluded.config_json,updated_at=excluded.updated_at",
                (value.model_dump_json(), datetime.now(timezone.utc).isoformat()))
        return value

    def reset(self):
        return self.save(InvestigationRuntime())
