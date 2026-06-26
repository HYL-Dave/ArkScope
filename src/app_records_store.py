"""Local-primary store for app-records — research_reports / agent_memories / agent_queries.

PG-exit Slice 1: these are the PG-only, user/agent-authored, NOT-regenerable records (unlike
market data, which is re-fetchable). This SQLite store lives in ``profile_state.db`` (the local
app-state DB — same home + path helper as ProfileStateStore / CardRunStore / CredentialStore) and
is the local twin of ``db_backend``'s app-record surface, returning the SAME shapes so it is a
drop-in once the DAL routes to it (Slice 1b):

- ``query_reports`` / ``query_memories`` / ``list_memories_meta`` → pandas DataFrames with the
  exact columns db_backend returns; ``tickers`` / ``tags`` are Python lists (JSON-text ↔ list, the
  parity psycopg2 gives for ``TEXT[]``); ``created_at`` is ``'YYYY-MM-DDTHH:MM:SS'`` (matches the
  PG ``TO_CHAR`` reads).
- inserts return the new id (``INTEGER PRIMARY KEY AUTOINCREMENT`` ↔ ``BIGSERIAL``).

PG-ism port: BIGSERIAL→AUTOINCREMENT; TEXT[]→JSON text; JSONB→TEXT; TIMESTAMPTZ→ISO TEXT;
``= ANY(arr)`` / ``arr && arr`` overlap filters → applied in Python after the SQL date/category
filter (app-records are low-volume); PG full-text (``to_tsvector``/``plainto_tsquery``) → a
case-insensitive substring match over title+content (documented v1 simplification — ranked FTS can
come later if volume warrants). Inserts accept an optional ``created_at`` (keyword) so the Slice-1c
PG→local migration can preserve each record's ORIGINAL timestamp; it defaults to now (parity with
``DEFAULT NOW()``).

Slice 1a is the store only — no DAL wiring, no migration.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Toggle for routing app-records local (PG-exit 1b). Default-OFF. Per-domain (mirrors
# use_local_market / _macro / _sa); read by DataAccessLayer._local_records_enabled.
USE_LOCAL_RECORDS_KEY = "use_local_records"
ENV_USE_LOCAL_RECORDS = "ARKSCOPE_USE_LOCAL_RECORDS"

_REPORT_COLS = ["id", "title", "tickers", "report_type", "summary", "conclusion",
                "confidence", "model", "file_path", "tool_calls", "duration_seconds", "created_at"]
_MEM_COLS = ["id", "title", "content", "category", "tickers", "tags", "importance", "source", "created_at"]
_MEM_META_COLS = ["id", "title", "category", "tickers", "tags", "importance", "created_at"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_reports (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    title            TEXT NOT NULL,
    tickers          TEXT,            -- JSON array (TEXT[] in PG)
    report_type      TEXT,
    summary          TEXT,
    conclusion       TEXT,
    confidence       REAL,
    provider         TEXT,
    model            TEXT,
    file_path        TEXT,
    tools_used       TEXT,            -- JSON array (JSONB in PG)
    tool_calls       INTEGER,
    duration_seconds REAL,
    tokens_in        INTEGER,
    tokens_out       INTEGER,
    created_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reports_created ON research_reports(created_at DESC);

CREATE TABLE IF NOT EXISTS agent_memories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category    TEXT NOT NULL,
    title       TEXT NOT NULL,
    content     TEXT NOT NULL,
    tickers     TEXT,                 -- JSON array
    tags        TEXT,                 -- JSON array
    source      TEXT,
    provider    TEXT,
    model       TEXT,
    importance  INTEGER DEFAULT 5,
    file_path   TEXT,
    expires_at  TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memories_created ON agent_memories(importance DESC, created_at DESC);

CREATE TABLE IF NOT EXISTS agent_queries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    question    TEXT NOT NULL,
    answer      TEXT,
    provider    TEXT,
    model       TEXT,
    tools_used  TEXT,                 -- JSON array
    duration_ms INTEGER,
    tokens_in   INTEGER,
    tokens_out  INTEGER,
    created_at  TEXT NOT NULL
);
"""


def _now_iso() -> str:
    """UTC now in the PG TO_CHAR read format ('YYYY-MM-DDTHH:MM:SS', no tz/micros)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _json_or_none(v: Optional[List[str]]) -> Optional[str]:
    return json.dumps(v) if v else None


def _list(v: Any) -> List[str]:
    """JSON-text → list (parity with psycopg2's TEXT[] → list); tolerant of NULL / bad JSON."""
    if not v:
        return []
    if isinstance(v, list):
        return v
    try:
        out = json.loads(v)
        return out if isinstance(out, list) else []
    except (ValueError, TypeError):
        return []


class AppRecordsLocalStore:
    """SQLite app-records store over ``profile_state.db`` (local-primary; no PG)."""

    def __init__(self, db_path: str | Path):
        self._db_path = str(db_path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
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
    def _cutoff(days: int, today: Optional[str]) -> str:
        base = date.fromisoformat(today) if today else datetime.now(timezone.utc).date()
        return (base - timedelta(days=days)).isoformat()

    # --- reports --------------------------------------------------------------------

    def insert_report(self, title: str, tickers: List[str], report_type: str, summary: str,
                      conclusion: Optional[str] = None, confidence: Optional[float] = None,
                      provider: Optional[str] = None, model: Optional[str] = None,
                      file_path: Optional[str] = None, tools_used: Optional[List[str]] = None,
                      tool_calls: Optional[int] = None, duration_seconds: Optional[float] = None,
                      tokens_in: Optional[int] = None, tokens_out: Optional[int] = None,
                      *, created_at: Optional[str] = None) -> Optional[int]:
        conn = self._connect()
        try:
            cur = conn.execute(
                "INSERT INTO research_reports (title,tickers,report_type,summary,conclusion,"
                "confidence,provider,model,file_path,tools_used,tool_calls,duration_seconds,"
                "tokens_in,tokens_out,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (title, _json_or_none(tickers), report_type, summary, conclusion, confidence,
                 provider, model, file_path, _json_or_none(tools_used), tool_calls,
                 duration_seconds, tokens_in, tokens_out, created_at or _now_iso()))
            conn.commit()
            return int(cur.lastrowid)
        except sqlite3.Error as e:
            logger.error("insert_report failed: %s", e)
            return None
        finally:
            conn.close()

    def query_reports(self, ticker: Optional[str] = None, days: int = 30,
                      report_type: Optional[str] = None, limit: int = 20,
                      *, today: Optional[str] = None) -> pd.DataFrame:
        conn = self._connect()
        try:
            clause, params = "created_at >= ?", [self._cutoff(days, today)]
            if report_type:
                clause += " AND report_type = ?"; params.append(report_type)
            rows = conn.execute(
                f"SELECT id,title,tickers,report_type,summary,conclusion,confidence,model,"
                f"file_path,tool_calls,duration_seconds,created_at FROM research_reports "
                f"WHERE {clause} ORDER BY created_at DESC", params).fetchall()
        finally:
            conn.close()
        recs = []
        for r in rows:
            d = dict(r)
            d["tickers"] = _list(d["tickers"])
            if ticker and ticker.upper() not in d["tickers"]:   # = ANY(tickers), in Python
                continue
            recs.append(d)
            if len(recs) >= limit:
                break
        return pd.DataFrame(recs, columns=_REPORT_COLS)

    def get_report_metadata(self, report_id: int) -> Optional[Dict[str, Any]]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM research_reports WHERE id = ?", (report_id,)).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        d = dict(row)
        d["tickers"] = _list(d.get("tickers"))
        d["tools_used"] = _list(d.get("tools_used"))
        return d

    # --- memories -------------------------------------------------------------------

    def insert_memory(self, title: str, content: str, category: str = "note",
                      tickers: Optional[List[str]] = None, tags: Optional[List[str]] = None,
                      importance: int = 5, source: Optional[str] = None,
                      provider: Optional[str] = None, model: Optional[str] = None,
                      file_path: Optional[str] = None, expires_at: Optional[str] = None,
                      *, created_at: Optional[str] = None) -> Optional[int]:
        conn = self._connect()
        try:
            cur = conn.execute(
                "INSERT INTO agent_memories (title,content,category,tickers,tags,importance,"
                "source,provider,model,file_path,expires_at,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (title, content, category, _json_or_none(tickers), _json_or_none(tags),
                 importance, source, provider, model, file_path, expires_at, created_at or _now_iso()))
            conn.commit()
            return int(cur.lastrowid)
        except sqlite3.Error as e:
            logger.error("insert_memory failed: %s", e)
            return None
        finally:
            conn.close()

    def query_memories(self, query: str = "", category: Optional[str] = None,
                       tickers: Optional[List[str]] = None, tags: Optional[List[str]] = None,
                       days: int = 90, limit: int = 10, *, today: Optional[str] = None) -> pd.DataFrame:
        conn = self._connect()
        try:
            clause, params = "created_at >= ?", [self._cutoff(days, today)]
            if category:
                clause += " AND category = ?"; params.append(category)
            if query.strip():  # substring over title+content (v1 simplification vs PG FTS)
                clause += " AND (lower(title) LIKE ? OR lower(content) LIKE ?)"
                like = f"%{query.strip().lower()}%"; params += [like, like]
            rows = conn.execute(
                f"SELECT id,title,content,category,tickers,tags,importance,source,created_at "
                f"FROM agent_memories WHERE {clause} ORDER BY importance DESC, created_at DESC",
                params).fetchall()
        finally:
            conn.close()
        return self._filter_overlap_df(rows, _MEM_COLS, tickers, tags, limit)

    def list_memories_meta(self, category: Optional[str] = None, days: int = 90,
                           limit: int = 20, *, today: Optional[str] = None) -> pd.DataFrame:
        conn = self._connect()
        try:
            clause, params = "created_at >= ?", [self._cutoff(days, today)]
            if category:
                clause += " AND category = ?"; params.append(category)
            rows = conn.execute(
                f"SELECT id,title,category,tickers,tags,importance,created_at FROM agent_memories "
                f"WHERE {clause} ORDER BY importance DESC, created_at DESC LIMIT ?",
                params + [limit]).fetchall()
        finally:
            conn.close()
        recs = [{**dict(r), "tickers": _list(r["tickers"]), "tags": _list(r["tags"])} for r in rows]
        return pd.DataFrame(recs, columns=_MEM_META_COLS)

    @staticmethod
    def _filter_overlap_df(rows, cols, tickers, tags, limit) -> pd.DataFrame:
        want_t = {t.upper() for t in (tickers or [])}
        want_g = set(tags or [])
        recs = []
        for r in rows:
            d = dict(r)
            d["tickers"] = _list(d["tickers"])
            d["tags"] = _list(d["tags"])
            if want_t and not (want_t & {t.upper() for t in d["tickers"]}):  # tickers && arr
                continue
            if want_g and not (want_g & set(d["tags"])):                     # tags && arr
                continue
            recs.append(d)
            if len(recs) >= limit:
                break
        return pd.DataFrame(recs, columns=cols)

    def delete_memory(self, memory_id: int) -> Optional[str]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT file_path FROM agent_memories WHERE id = ?",
                               (memory_id,)).fetchone()
            if row is None:
                return None
            conn.execute("DELETE FROM agent_memories WHERE id = ?", (memory_id,))
            conn.commit()
            return row["file_path"]
        finally:
            conn.close()

    # --- agent_queries (write-only log, mirrors db_backend) -------------------------

    def insert_agent_query(self, question: str, answer: Optional[str] = None,
                           provider: Optional[str] = None, model: Optional[str] = None,
                           tools_used: Optional[List[str]] = None, duration_ms: Optional[int] = None,
                           tokens_in: Optional[int] = None, tokens_out: Optional[int] = None,
                           *, created_at: Optional[str] = None) -> Optional[int]:
        conn = self._connect()
        try:
            cur = conn.execute(
                "INSERT INTO agent_queries (question,answer,provider,model,tools_used,duration_ms,"
                "tokens_in,tokens_out,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (question, answer, provider, model, _json_or_none(tools_used), duration_ms,
                 tokens_in, tokens_out, created_at or _now_iso()))
            conn.commit()
            return int(cur.lastrowid)
        except sqlite3.Error as e:
            logger.error("insert_agent_query failed: %s", e)
            return None
        finally:
            conn.close()

    def count_agent_queries(self) -> int:
        conn = self._connect()
        try:
            return int(conn.execute("SELECT COUNT(*) FROM agent_queries").fetchone()[0])
        finally:
            conn.close()


def resolve_profile_state_db_path(dal: Any = None) -> str:
    """Path to the local app-state DB — same resolution as api.dependencies._local_state_db_path
    but WITHOUT importing the API layer (gate #3: no core→API reverse coupling): ARKSCOPE_PROFILE_DB
    env, else ``<dal._base>/data/profile_state.db``, else ``<repo>/data/profile_state.db``."""
    env = os.environ.get("ARKSCOPE_PROFILE_DB")
    if env:
        return env
    base = getattr(dal, "_base", None) if dal is not None else None
    if base:
        return str(Path(base) / "data" / "profile_state.db")
    return str(Path(__file__).resolve().parents[1] / "data" / "profile_state.db")


def get_app_records_store(dal: Any):
    """Return the app-records store for the active mode (PG-exit 1b). When use_local_records is
    on (env ARKSCOPE_USE_LOCAL_RECORDS or the persisted profile_settings key) → the local
    AppRecordsLocalStore over profile_state.db. OFF (default) → ``dal._backend`` (PG/File),
    i.e. exactly the current behavior. Both expose the same app-record surface, so the 10 call
    sites are mode-agnostic. A dal lacking the toggle (older/test double) → OFF.

    NOTE (gate #1): there is intentionally NO Settings UI to flip this in 1b — the local store
    autoincrements ids from 1, so writing local rows BEFORE the 1c id-preserving PG→local
    migration would collide with the migrated PG ids. Keep it env/profile-flag-only until 1c."""
    if getattr(dal, "_local_records_enabled", None) and dal._local_records_enabled():
        return AppRecordsLocalStore(resolve_profile_state_db_path(dal))
    return getattr(dal, "_backend", None)
