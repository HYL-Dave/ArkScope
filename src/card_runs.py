"""
Local store for generated §2 AI cards (SQLite).

Per the v1 storage decision ("1.5"): every card generation is auto-cached here as
a lightweight *run* (short-term, traceable snapshot — evidence packet + model +
as-of), separate from durable research records. A run starts ``generated``; the
user can ``archive``/``delete``/restore it, and "Save as report" promotes it to a
durable report (``research_reports`` via save_report) and flips status to
``saved``. Future thesis-versioning diffs only ``saved`` cards, never the noisy
pool of every generated card.

Local-first: this lives in the same standalone SQLite DB as the profile-state
store (``data/profile_state.db``), NOT the remote PG.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_card_runs (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker               TEXT NOT NULL,
    question             TEXT,
    horizon              TEXT,
    card_type            TEXT NOT NULL DEFAULT 'analysis',
    result_card_json     TEXT NOT NULL,
    evidence_packet_json TEXT,
    provider             TEXT,
    model                TEXT,
    generated_at         TEXT NOT NULL,
    as_of                TEXT,
    status               TEXT NOT NULL DEFAULT 'generated',
    saved_report_id      INTEGER,
    expires_at           TEXT,
    translations_json    TEXT
);

CREATE INDEX IF NOT EXISTS idx_card_runs_ticker ON ai_card_runs(ticker);
CREATE INDEX IF NOT EXISTS idx_card_runs_status ON ai_card_runs(status);
"""

VALID_STATUS = ("generated", "saved", "archived", "deleted")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _norm(ticker: Optional[str]) -> str:
    return (ticker or "").strip().upper()


@dataclass
class CardRun:
    id: int
    ticker: str
    question: Optional[str]
    horizon: Optional[str]
    card_type: str
    result_card: dict
    evidence_packet: Optional[dict]
    provider: Optional[str]
    model: Optional[str]
    generated_at: str
    as_of: Optional[str]
    status: str
    saved_report_id: Optional[int]
    expires_at: Optional[str]
    translations: Optional[dict] = None  # {lang: translated result_card dict}


class CardRunStore:
    """Local SQLite store for generated §2 card runs."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.Lock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._write_lock, self._connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(_SCHEMA)
            # Migration: add translations_json to a pre-existing table (idempotent).
            cols = {r[1] for r in conn.execute("PRAGMA table_info(ai_card_runs)").fetchall()}
            if "translations_json" not in cols:
                conn.execute("ALTER TABLE ai_card_runs ADD COLUMN translations_json TEXT")
            conn.commit()

    @staticmethod
    def _row(r: sqlite3.Row) -> CardRun:
        return CardRun(
            id=r["id"],
            ticker=r["ticker"],
            question=r["question"],
            horizon=r["horizon"],
            card_type=r["card_type"],
            result_card=json.loads(r["result_card_json"]),
            evidence_packet=json.loads(r["evidence_packet_json"]) if r["evidence_packet_json"] else None,
            provider=r["provider"],
            model=r["model"],
            generated_at=r["generated_at"],
            as_of=r["as_of"],
            status=r["status"],
            saved_report_id=r["saved_report_id"],
            expires_at=r["expires_at"],
            translations=json.loads(r["translations_json"])
            if r["translations_json"]
            else None,
        )

    # --- writes ----------------------------------------------------------

    def record(
        self,
        *,
        ticker: str,
        result_card: dict,
        evidence_packet: Optional[dict] = None,
        question: Optional[str] = None,
        horizon: Optional[str] = None,
        card_type: str = "analysis",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        as_of: Optional[str] = None,
        generated_at: Optional[str] = None,
    ) -> CardRun:
        t = _norm(ticker)
        if not t:
            raise ValueError("ticker is required")
        gen = generated_at or _now()
        with self._write_lock, self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO ai_card_runs
                    (ticker, question, horizon, card_type, result_card_json,
                     evidence_packet_json, provider, model, generated_at, as_of, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'generated')
                """,
                (
                    t,
                    question,
                    horizon,
                    card_type,
                    json.dumps(result_card),
                    json.dumps(evidence_packet) if evidence_packet is not None else None,
                    provider,
                    model,
                    gen,
                    as_of,
                ),
            )
            conn.commit()
            run_id = cur.lastrowid
        got = self.get(run_id)
        assert got is not None
        return got

    def set_status(self, run_id: int, status: str) -> Optional[CardRun]:
        if status not in VALID_STATUS:
            raise ValueError(f"invalid status: {status}")
        with self._write_lock, self._connect() as conn:
            cur = conn.execute(
                "UPDATE ai_card_runs SET status = ? WHERE id = ?",
                (status, run_id),
            )
            conn.commit()
            if cur.rowcount == 0:
                return None
        return self.get(run_id)

    def mark_saved(self, run_id: int, saved_report_id: Optional[int]) -> Optional[CardRun]:
        with self._write_lock, self._connect() as conn:
            cur = conn.execute(
                "UPDATE ai_card_runs SET status = 'saved', saved_report_id = ? WHERE id = ?",
                (saved_report_id, run_id),
            )
            conn.commit()
            if cur.rowcount == 0:
                return None
        return self.get(run_id)

    def archive_generated_before(self, cutoff_iso: str) -> int:
        """Auto-archive stale, never-promoted cards (status still 'generated')."""
        with self._write_lock, self._connect() as conn:
            cur = conn.execute(
                "UPDATE ai_card_runs SET status = 'archived' "
                "WHERE status = 'generated' AND generated_at < ?",
                (cutoff_iso,),
            )
            conn.commit()
            return cur.rowcount

    # --- reads -----------------------------------------------------------

    def get(self, run_id: int) -> Optional[CardRun]:
        with self._connect() as conn:
            r = conn.execute("SELECT * FROM ai_card_runs WHERE id = ?", (run_id,)).fetchone()
        return self._row(r) if r else None

    def recent(
        self,
        *,
        ticker: Optional[str] = None,
        limit: int = 20,
        statuses: tuple[str, ...] = ("generated", "saved"),
    ) -> list[CardRun]:
        clauses = []
        params: list = []
        if ticker:
            clauses.append("ticker = ?")
            params.append(_norm(ticker))
        if statuses:
            clauses.append(f"status IN ({','.join('?' * len(statuses))})")
            params.extend(statuses)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM ai_card_runs {where} ORDER BY generated_at DESC, id DESC LIMIT ?",
                params,
            ).fetchall()
        return [self._row(r) for r in rows]

    # --- translations (on-demand, cached) --------------------------------

    def set_translation(self, run_id: int, lang: str, card: dict) -> None:
        """Cache a per-language translated card on the run (merged by lang)."""
        with self._write_lock, self._connect() as conn:
            row = conn.execute(
                "SELECT translations_json FROM ai_card_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if row is None:
                return
            current = json.loads(row["translations_json"]) if row["translations_json"] else {}
            current[lang] = card
            conn.execute(
                "UPDATE ai_card_runs SET translations_json = ? WHERE id = ?",
                (json.dumps(current), run_id),
            )
            conn.commit()

    def get_translation(self, run_id: int, lang: str) -> Optional[dict]:
        run = self.get(run_id)
        if run and run.translations:
            return run.translations.get(lang)
        return None
