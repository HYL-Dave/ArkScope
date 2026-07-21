"""Investor Profile calibration journal and proposal store (Track A.5).

Raw calibration dialogue is profile-state journal data. It must never be used as
research/card prompt input; only approved structured investor_profile rows may
shape research synthesis.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.investor_profile import normalize_profile_payload
from src.investor_profile_calibration_schema import assert_calibration_schema_v2

SESSION_STATUSES = ("active", "closed", "superseded")
MESSAGE_ROLES = ("user", "assistant")
PROPOSAL_STATUSES = ("draft", "approved", "rejected", "superseded")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _loads(raw: str | None, fallback):
    if not raw:
        return fallback
    data = json.loads(raw)
    return data if data is not None else fallback


@dataclass
class CalibrationSession:
    id: str
    status: str
    created_at: str
    updated_at: str
    closed_at: Optional[str]


@dataclass
class CalibrationMessage:
    id: str
    session_id: str
    role: str
    content: str
    created_at: str


@dataclass
class CalibrationProposal:
    id: str
    session_id: str
    status: str
    profile_patch: dict
    raw_profile_patch: dict
    rationales: dict
    changed_fields: list[str]
    created_at: str
    approved_at: Optional[str]
    rejected_at: Optional[str]


def normalize_proposal_payload(profile_patch: dict, rationales: dict | None) -> tuple[dict, dict, dict]:
    if "risk_mismatch" in profile_patch:
        raise ValueError("risk_mismatch is server-derived and cannot be proposed")
    normalized = normalize_profile_payload(profile_patch)
    raw = dict(profile_patch)
    patch = {
        "enabled": normalized.enabled,
        "primary_preset": normalized.primary_preset,
        "risk_appetite": normalized.risk_appetite,
        "risk_capacity": normalized.risk_capacity,
        "risk_mismatch": normalized.risk_mismatch,
        "holding_horizon": normalized.holding_horizon,
        "drawdown_tolerance_pct": normalized.drawdown_tolerance_pct,
        "concentration_limit_pct": normalized.concentration_limit_pct,
        "preferred_edge": normalized.preferred_edge,
        "avoidances": normalized.avoidances,
        "behavioral_flags": normalized.behavioral_flags,
        "freeform_notes": normalized.freeform_notes,
        "default_stance": normalized.default_stance,
        "skill_mode": normalized.skill_mode,
    }
    return patch, raw, dict(rationales or {})


class CalibrationStore:
    """SQLite store for Investor Profile calibration sessions/messages/proposals."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        assert_calibration_schema_v2(self.db_path)
        self._write_lock = threading.Lock()

    def _connect(self) -> sqlite3.Connection:
        uri = f"{Path(self.db_path).resolve().as_uri()}?mode=rw"
        conn = sqlite3.connect(uri, uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @staticmethod
    def _session(row: sqlite3.Row) -> CalibrationSession:
        return CalibrationSession(
            row["id"], row["status"], row["created_at"], row["updated_at"], row["closed_at"]
        )

    @staticmethod
    def _message(row: sqlite3.Row) -> CalibrationMessage:
        return CalibrationMessage(row["id"], row["session_id"], row["role"], row["content"], row["created_at"])

    @staticmethod
    def _proposal(row: sqlite3.Row) -> CalibrationProposal:
        return CalibrationProposal(
            id=row["id"],
            session_id=row["session_id"],
            status=row["status"],
            profile_patch=_loads(row["profile_patch_json"], {}),
            raw_profile_patch=_loads(row["raw_profile_patch_json"], {}),
            rationales=_loads(row["rationales_json"], {}),
            changed_fields=_loads(row["changed_fields_json"], []),
            created_at=row["created_at"],
            approved_at=row["approved_at"],
            rejected_at=row["rejected_at"],
        )

    def get_active_session(self) -> Optional[CalibrationSession]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM investor_profile_calibration_sessions WHERE status = 'active'"
            ).fetchone()
        return self._session(row) if row else None

    def get_session(self, session_id: str) -> Optional[CalibrationSession]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM investor_profile_calibration_sessions WHERE id = ?", (session_id,)
            ).fetchone()
        return self._session(row) if row else None

    def list_sessions(self, *, limit: int = 20) -> list[CalibrationSession]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM investor_profile_calibration_sessions "
                "ORDER BY updated_at DESC, rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._session(r) for r in rows]

    def start_session(self, *, supersede_active: bool = False) -> CalibrationSession:
        ts = _now()
        with self._write_lock, self._connect() as conn:
            active = conn.execute(
                "SELECT id FROM investor_profile_calibration_sessions WHERE status = 'active'"
            ).fetchone()
            if active and not supersede_active:
                raise ValueError("calibration_session_active")
            if active:
                conn.execute(
                    "UPDATE investor_profile_calibration_sessions SET status='superseded', "
                    "updated_at=?, closed_at=? WHERE id=?",
                    (ts, ts, active["id"]),
                )
            sid = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO investor_profile_calibration_sessions "
                "(id, status, created_at, updated_at) VALUES (?, 'active', ?, ?)",
                (sid, ts, ts),
            )
            conn.commit()
        got = self.get_session(sid)
        assert got is not None
        return got

    def close_session(self, session_id: str) -> CalibrationSession:
        ts = _now()
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "UPDATE investor_profile_calibration_sessions SET status='closed', "
                "updated_at=?, closed_at=? WHERE id=? AND status='active'",
                (ts, ts, session_id),
            )
            conn.commit()
        got = self.get_session(session_id)
        if got is None:
            raise ValueError("calibration_session_not_found")
        return got

    def append_message(self, session_id: str, *, role: str, content: str) -> CalibrationMessage:
        if role not in MESSAGE_ROLES:
            raise ValueError(f"invalid calibration role: {role}")
        text = (content or "").strip()
        if not text:
            raise ValueError("content is required")
        sess = self.get_session(session_id)
        if sess is None:
            raise ValueError("calibration_session_not_found")
        if sess.status != "active":
            raise ValueError("calibration_session_not_active")
        ts, mid = _now(), str(uuid.uuid4())
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO investor_profile_calibration_messages "
                "(id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (mid, session_id, role, text, ts),
            )
            conn.execute(
                "UPDATE investor_profile_calibration_sessions SET updated_at=? WHERE id=?",
                (ts, session_id),
            )
            conn.commit()
        return self.list_messages(session_id)[-1]

    def list_messages(self, session_id: str) -> list[CalibrationMessage]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM investor_profile_calibration_messages WHERE session_id=? "
                "ORDER BY created_at ASC, rowid ASC",
                (session_id,),
            ).fetchall()
        return [self._message(r) for r in rows]

    def create_proposal(self, *, session_id: str, profile_patch: dict, rationales: dict | None) -> CalibrationProposal:
        patch, raw, rats = normalize_proposal_payload(profile_patch, rationales)
        ts, pid = _now(), str(uuid.uuid4())
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO investor_profile_calibration_proposals "
                "(id, session_id, status, profile_patch_json, raw_profile_patch_json, "
                "rationales_json, created_at) VALUES (?, ?, 'draft', ?, ?, ?, ?)",
                (
                    pid,
                    session_id,
                    json.dumps(patch, ensure_ascii=False),
                    json.dumps(raw, ensure_ascii=False),
                    json.dumps(rats, ensure_ascii=False),
                    ts,
                ),
            )
            conn.commit()
        got = self.get_proposal(pid)
        assert got is not None
        return got

    def get_proposal(self, proposal_id: str) -> Optional[CalibrationProposal]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM investor_profile_calibration_proposals WHERE id=?", (proposal_id,)
            ).fetchone()
        return self._proposal(row) if row else None

    def latest_proposal(self, session_id: str) -> Optional[CalibrationProposal]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM investor_profile_calibration_proposals WHERE session_id=? "
                "ORDER BY created_at DESC, rowid DESC LIMIT 1",
                (session_id,),
            ).fetchone()
        return self._proposal(row) if row else None

    def mark_proposal_approved(self, proposal_id: str, *, changed_fields: list[str]) -> CalibrationProposal:
        proposal = self.get_proposal(proposal_id)
        if proposal is None:
            raise ValueError("proposal_not_found")
        if proposal.status != "draft":
            raise ValueError("proposal_not_draft")
        ts = _now()
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "UPDATE investor_profile_calibration_proposals SET status='approved', "
                "approved_at=?, changed_fields_json=? WHERE id=? AND status='draft'",
                (ts, json.dumps(sorted(changed_fields)), proposal_id),
            )
            conn.commit()
        got = self.get_proposal(proposal_id)
        assert got is not None
        return got

    def reject_proposal(self, proposal_id: str) -> CalibrationProposal:
        proposal = self.get_proposal(proposal_id)
        if proposal is None:
            raise ValueError("proposal_not_found")
        if proposal.status != "draft":
            raise ValueError("proposal_not_draft")
        ts = _now()
        with self._write_lock, self._connect() as conn:
            conn.execute(
                "UPDATE investor_profile_calibration_proposals SET status='rejected', "
                "rejected_at=? WHERE id=? AND status='draft'",
                (ts, proposal_id),
            )
            conn.commit()
        got = self.get_proposal(proposal_id)
        assert got is not None
        return got
