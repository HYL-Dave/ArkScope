"""Durable guided calibration journal and partial-proposal store.

Raw calibration dialogue is profile-state journal data. It must never be used as
research/card prompt input; only an approved structured Investor Profile may
shape synthesis.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.investor_profile import (
    InvestorProfile,
    InvestorProfileStore,
    _read_profile_on_connection,
    _write_profile_on_connection,
    normalize_profile_payload,
)
from src.investor_profile_calibration_policy import (
    CALIBRATION_TOPICS,
    CALIBRATION_TOPIC_IDS,
    OPENING_PROMPT_ID,
    OPENING_PROMPTS,
    clamp_proposal_patch,
    fields_for_topics,
    validate_addressed_topic,
    validate_next_topic,
)
from src.investor_profile_calibration_schema import assert_calibration_schema_v2

SESSION_STATUSES = ("active", "closed", "superseded")
MESSAGE_ROLES = ("user", "assistant")
TURN_KINDS = ("answer", "proposal_request")
TURN_STATUSES = ("pending", "completed", "failed", "interrupted")
PROPOSAL_STATUSES = ("draft", "approved", "rejected", "superseded")
INTERVIEW_VERSION = 2
MAX_DIAGNOSTIC_LENGTH = 240
_SESSION_SUPERSEDED_DIAGNOSTIC = (
    "Calibration session was superseded before Provider completion."
)

_PROPOSABLE_FIELD_ORDER = tuple(
    field for topic in CALIBRATION_TOPICS for field in topic.fields
)
_LIST_CONFLICT_FIELDS = frozenset(
    {"preferred_edge", "avoidances", "behavioral_flags"}
)
_APPROVAL_AUDIT_FIELDS = (*_PROPOSABLE_FIELD_ORDER, "risk_mismatch")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _loads(raw: str | None, fallback):
    if not raw:
        return fallback
    data = json.loads(raw)
    return data if data is not None else fallback


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _bounded_diagnostic(value: Any) -> str:
    text = " ".join(str(value or "").split())
    return text[:MAX_DIAGNOSTIC_LENGTH]


def _ordered_topics(topic_ids) -> list[str]:
    source = [str(topic_id) for topic_id in topic_ids]
    selected = set(source)
    ordered = [topic_id for topic_id in CALIBRATION_TOPIC_IDS if topic_id in selected]
    ordered.extend(topic_id for topic_id in source if topic_id not in CALIBRATION_TOPIC_IDS and topic_id not in ordered)
    return ordered


def _ordered_proposed_fields(patch: Mapping[str, Any]) -> list[str]:
    return [field for field in _PROPOSABLE_FIELD_ORDER if field in patch]


class CalibrationOperationError(ValueError):
    """Typed product error whose text never contains rejected field values."""

    def __init__(self, code: str, diagnostic: str = ""):
        self.code = code
        self.diagnostic = _bounded_diagnostic(diagnostic)
        super().__init__(f"{code}: {self.diagnostic}" if self.diagnostic else code)


class ProposalConflictError(CalibrationOperationError):
    def __init__(self, conflict_fields: list[str]):
        self.conflict_fields = tuple(conflict_fields)
        super().__init__("proposal_conflict", ", ".join(conflict_fields))


@dataclass(frozen=True)
class CalibrationSession:
    id: str
    status: str
    interview_version: Optional[int]
    covered_topics: list[str]
    current_topic_id: Optional[str]
    current_question_message_id: Optional[str]
    superseded_reason: Optional[str]
    created_at: str
    updated_at: str
    closed_at: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CalibrationMessage:
    id: str
    session_id: str
    role: str
    content: str
    turn_id: Optional[str]
    topic_id: Optional[str]
    prompt_id: Optional[str]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CalibrationTurn:
    id: str
    session_id: str
    kind: str
    status: str
    question_message_id: Optional[str]
    addressed_topic_id: Optional[str]
    next_topic_id: Optional[str]
    error_code: Optional[str]
    diagnostic: Optional[str]
    attempt_count: int
    created_at: str
    updated_at: str
    completed_at: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CalibrationProposal:
    id: str
    session_id: str
    status: str
    profile_patch: dict[str, Any]
    proposed_fields: list[str]
    covered_topics: list[str]
    rationales: dict[str, str]
    changed_fields: list[str]
    conflict_fields: list[str]
    created_at: str
    approved_at: Optional[str]
    rejected_at: Optional[str]
    conflicted_at: Optional[str]
    superseded_at: Optional[str]
    superseded_reason: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProviderWork:
    """Frozen provider intent reconstructed entirely from persisted state."""

    turn: CalibrationTurn
    call_provider: bool
    kind: str
    provider: Optional[str]
    model: Optional[str]
    question_message_id: Optional[str]
    current_topic_id: Optional[str]
    covered_topics: tuple[str, ...]
    answer: Optional[str]
    request_proposal: bool
    messages: tuple[CalibrationMessage, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_id": self.turn.id,
            "status": self.turn.status,
            "call_provider": self.call_provider,
            "message_count": len(self.messages),
            "covered_topics": list(self.covered_topics),
            "current_topic_id": self.current_topic_id,
        }


def normalize_proposal_payload(
    profile_patch: dict,
    rationales: dict | None,
) -> tuple[dict, dict, dict]:
    """Legacy route compatibility; guided proposals never call this helper."""
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
    """SQLite store for guided calibration sessions, turns, and proposals."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        assert_calibration_schema_v2(self.db_path)
        self._write_lock = threading.Lock()

    def _connect_with_mode(self, mode: str) -> sqlite3.Connection:
        uri = f"{Path(self.db_path).resolve().as_uri()}?mode={mode}"
        conn = sqlite3.connect(uri, uri=True, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _connect_read_only(self) -> sqlite3.Connection:
        return self._connect_with_mode("ro")

    def _connect_writable(self) -> sqlite3.Connection:
        return self._connect_with_mode("rw")

    @contextmanager
    def _write_transaction(self):
        with self._write_lock:
            conn = self._connect_writable()
            try:
                conn.execute("BEGIN IMMEDIATE")
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
            finally:
                conn.close()

    @staticmethod
    def _session(row: sqlite3.Row) -> CalibrationSession:
        return CalibrationSession(
            id=row["id"],
            status=row["status"],
            interview_version=row["interview_version"],
            covered_topics=_ordered_topics(_loads(row["covered_topics_json"], [])),
            current_topic_id=row["current_topic_id"],
            current_question_message_id=row["current_question_message_id"],
            superseded_reason=row["superseded_reason"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            closed_at=row["closed_at"],
        )

    @staticmethod
    def _message(row: sqlite3.Row) -> CalibrationMessage:
        return CalibrationMessage(
            id=row["id"],
            session_id=row["session_id"],
            role=row["role"],
            content=row["content"],
            turn_id=row["turn_id"],
            topic_id=row["topic_id"],
            prompt_id=row["prompt_id"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _turn(row: sqlite3.Row) -> CalibrationTurn:
        diagnostic = _bounded_diagnostic(row["diagnostic"]) if row["diagnostic"] else None
        return CalibrationTurn(
            id=row["id"],
            session_id=row["session_id"],
            kind=row["kind"],
            status=row["status"],
            question_message_id=row["question_message_id"],
            addressed_topic_id=row["addressed_topic_id"],
            next_topic_id=row["next_topic_id"],
            error_code=row["error_code"],
            diagnostic=diagnostic,
            attempt_count=row["attempt_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
        )

    @staticmethod
    def _proposal(row: sqlite3.Row) -> CalibrationProposal:
        patch = _loads(row["profile_patch_json"], {})
        return CalibrationProposal(
            id=row["id"],
            session_id=row["session_id"],
            status=row["status"],
            profile_patch=patch,
            proposed_fields=_ordered_proposed_fields(patch),
            covered_topics=_ordered_topics(_loads(row["covered_topics_json"], [])),
            rationales=_loads(row["rationales_json"], {}),
            changed_fields=_loads(row["changed_fields_json"], []),
            conflict_fields=_loads(row["conflict_fields_json"], []),
            created_at=row["created_at"],
            approved_at=row["approved_at"],
            rejected_at=row["rejected_at"],
            conflicted_at=row["conflicted_at"],
            superseded_at=row["superseded_at"],
            superseded_reason=row["superseded_reason"],
        )

    @staticmethod
    def _session_row(conn: sqlite3.Connection, session_id: str):
        return conn.execute(
            "SELECT * FROM investor_profile_calibration_sessions WHERE id=?",
            (session_id,),
        ).fetchone()

    @staticmethod
    def _turn_row(conn: sqlite3.Connection, turn_id: str):
        return conn.execute(
            "SELECT * FROM investor_profile_calibration_turns WHERE id=?",
            (turn_id,),
        ).fetchone()

    @staticmethod
    def _proposal_row(conn: sqlite3.Connection, proposal_id: str):
        return conn.execute(
            "SELECT * FROM investor_profile_calibration_proposals WHERE id=?",
            (proposal_id,),
        ).fetchone()

    @staticmethod
    def _approval_proposal_row(conn: sqlite3.Connection, proposal_id: str):
        return conn.execute(
            "SELECT id, session_id, status, profile_patch_json, rationales_json, "
            "changed_fields_json, created_at, approved_at, rejected_at, "
            "covered_topics_json, base_values_json, conflicted_at, "
            "conflict_fields_json, superseded_at, superseded_reason "
            "FROM investor_profile_calibration_proposals WHERE id=?",
            (proposal_id,),
        ).fetchone()

    def get_active_session(self) -> Optional[CalibrationSession]:
        with self._connect_read_only() as conn:
            row = conn.execute(
                "SELECT * FROM investor_profile_calibration_sessions WHERE status='active'"
            ).fetchone()
        return self._session(row) if row else None

    def get_session(self, session_id: str) -> Optional[CalibrationSession]:
        with self._connect_read_only() as conn:
            row = self._session_row(conn, session_id)
        return self._session(row) if row else None

    def list_sessions(self, *, limit: int = 20) -> list[CalibrationSession]:
        with self._connect_read_only() as conn:
            rows = conn.execute(
                "SELECT * FROM investor_profile_calibration_sessions "
                "ORDER BY updated_at DESC, rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._session(row) for row in rows]

    def start_session(self, *, supersede_active: bool = False) -> CalibrationSession:
        ts = _now()
        session_id = str(uuid.uuid4())
        message_id = str(uuid.uuid4())
        with self._write_transaction() as conn:
            active = conn.execute(
                "SELECT id FROM investor_profile_calibration_sessions WHERE status='active'"
            ).fetchone()
            if active and not supersede_active:
                raise ValueError("calibration_session_active")
            if active:
                conn.execute(
                    "UPDATE investor_profile_calibration_turns SET status='failed', "
                    "error_code='calibration_session_superseded', diagnostic=?, "
                    "updated_at=? WHERE session_id=? AND status='pending'",
                    (_SESSION_SUPERSEDED_DIAGNOSTIC, ts, active["id"]),
                )
                conn.execute(
                    "UPDATE investor_profile_calibration_sessions SET status='superseded', "
                    "updated_at=?, closed_at=?, superseded_reason=? WHERE id=?",
                    (ts, ts, "replaced_by_new_guided_session", active["id"]),
                )
            conn.execute(
                "INSERT INTO investor_profile_calibration_sessions "
                "(id, status, created_at, updated_at, interview_version, "
                "covered_topics_json, current_topic_id, current_question_message_id) "
                "VALUES (?, 'active', ?, ?, ?, '[]', 'loss_response', ?)",
                (session_id, ts, ts, INTERVIEW_VERSION, message_id),
            )
            conn.execute(
                "INSERT INTO investor_profile_calibration_messages "
                "(id, session_id, role, content, created_at, topic_id, prompt_id) "
                "VALUES (?, ?, 'assistant', ?, ?, 'loss_response', ?)",
                (
                    message_id,
                    session_id,
                    OPENING_PROMPTS[OPENING_PROMPT_ID],
                    ts,
                    OPENING_PROMPT_ID,
                ),
            )
            row = self._session_row(conn, session_id)
        return self._session(row)

    def close_session(self, session_id: str) -> CalibrationSession:
        ts = _now()
        with self._write_transaction() as conn:
            row = self._session_row(conn, session_id)
            if row is None:
                raise ValueError("calibration_session_not_found")
            if row["status"] == "active":
                conn.execute(
                    "UPDATE investor_profile_calibration_sessions SET status='closed', "
                    "updated_at=?, closed_at=?, current_topic_id=NULL, "
                    "current_question_message_id=NULL WHERE id=?",
                    (ts, ts, session_id),
                )
                row = self._session_row(conn, session_id)
        return self._session(row)

    def append_message(
        self,
        session_id: str,
        *,
        role: str,
        content: str,
    ) -> CalibrationMessage:
        """Legacy Task 2 route seam; guided calls use begin/complete turn."""
        if role not in MESSAGE_ROLES:
            raise ValueError(f"invalid calibration role: {role}")
        text = (content or "").strip()
        if not text:
            raise ValueError("content is required")
        ts, message_id = _now(), str(uuid.uuid4())
        with self._write_transaction() as conn:
            session = self._session_row(conn, session_id)
            if session is None:
                raise ValueError("calibration_session_not_found")
            if session["status"] != "active":
                raise ValueError("calibration_session_not_active")
            conn.execute(
                "INSERT INTO investor_profile_calibration_messages "
                "(id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (message_id, session_id, role, text, ts),
            )
            conn.execute(
                "UPDATE investor_profile_calibration_sessions SET updated_at=? WHERE id=?",
                (ts, session_id),
            )
            row = conn.execute(
                "SELECT * FROM investor_profile_calibration_messages WHERE id=?",
                (message_id,),
            ).fetchone()
        return self._message(row)

    def list_messages(self, session_id: str) -> list[CalibrationMessage]:
        with self._connect_read_only() as conn:
            rows = conn.execute(
                "SELECT * FROM investor_profile_calibration_messages WHERE session_id=? "
                "ORDER BY created_at ASC, rowid ASC",
                (session_id,),
            ).fetchall()
        # The untouched legacy message route expects its old two-message view.
        # Guided user messages always carry turn_id and retain the opening prompt.
        has_legacy_user = any(
            row["role"] == "user" and row["turn_id"] is None for row in rows
        )
        if has_legacy_user:
            rows = [row for row in rows if row["prompt_id"] is None]
        return [self._message(row) for row in rows]

    def get_turn(self, turn_id: str) -> Optional[CalibrationTurn]:
        with self._connect_read_only() as conn:
            row = self._turn_row(conn, turn_id)
        return self._turn(row) if row else None

    def list_turns(self, session_id: str) -> list[CalibrationTurn]:
        with self._connect_read_only() as conn:
            rows = conn.execute(
                "SELECT * FROM investor_profile_calibration_turns WHERE session_id=? "
                "ORDER BY created_at ASC, rowid ASC",
                (session_id,),
            ).fetchall()
        return [self._turn(row) for row in rows]

    def get_pending_turn(self, session_id: str) -> Optional[CalibrationTurn]:
        with self._connect_read_only() as conn:
            row = conn.execute(
                "SELECT * FROM investor_profile_calibration_turns "
                "WHERE session_id=? AND status='pending'",
                (session_id,),
            ).fetchone()
        return self._turn(row) if row else None

    def _require_guided_session(
        self,
        conn: sqlite3.Connection,
        session_id: str,
    ) -> sqlite3.Row:
        session = self._session_row(conn, session_id)
        if session is None:
            raise ValueError("calibration_session_not_found")
        if session["status"] != "active":
            raise ValueError("calibration_session_not_active")
        if session["interview_version"] != INTERVIEW_VERSION:
            raise ValueError("calibration_session_not_guided_v2")
        topic_id = session["current_topic_id"]
        question_id = session["current_question_message_id"]
        if topic_id not in CALIBRATION_TOPIC_IDS or not question_id:
            raise ValueError("calibration_current_question_invalid")
        question = conn.execute(
            "SELECT role, topic_id FROM investor_profile_calibration_messages "
            "WHERE id=? AND session_id=?",
            (question_id, session_id),
        ).fetchone()
        if (
            question is None
            or question["role"] != "assistant"
            or question["topic_id"] != topic_id
        ):
            raise ValueError("calibration_current_question_invalid")
        return session

    def _work_on_connection(
        self,
        conn: sqlite3.Connection,
        turn_row: sqlite3.Row,
        *,
        call_provider: bool,
    ) -> ProviderWork:
        session = self._session_row(conn, turn_row["session_id"])
        message_rows = conn.execute(
            "SELECT * FROM investor_profile_calibration_messages WHERE session_id=? "
            "ORDER BY created_at ASC, rowid ASC",
            (turn_row["session_id"],),
        ).fetchall()
        answer = None
        if turn_row["user_message_id"]:
            answer_row = conn.execute(
                "SELECT content FROM investor_profile_calibration_messages WHERE id=?",
                (turn_row["user_message_id"],),
            ).fetchone()
            answer = answer_row["content"] if answer_row else None
        return ProviderWork(
            turn=self._turn(turn_row),
            call_provider=call_provider,
            kind=turn_row["kind"],
            provider=turn_row["provider"],
            model=turn_row["model"],
            question_message_id=turn_row["question_message_id"],
            current_topic_id=turn_row["addressed_topic_id"],
            covered_topics=tuple(
                _ordered_topics(_loads(session["covered_topics_json"], []))
            ),
            answer=answer,
            request_proposal=bool(turn_row["request_proposal"]),
            messages=tuple(self._message(row) for row in message_rows),
        )

    def _begin_turn(
        self,
        *,
        session_id: str,
        turn_id: str,
        kind: str,
        answer: Optional[str],
        provider: Optional[str],
        model: Optional[str],
    ) -> ProviderWork:
        if not isinstance(turn_id, str) or not turn_id.strip():
            raise ValueError("calibration_turn_id_required")
        if kind not in TURN_KINDS:
            raise ValueError("invalid_calibration_turn_kind")
        if kind == "answer" and (
            not isinstance(answer, str) or not answer.strip()
        ):
            raise ValueError("content is required")

        ts = _now()
        with self._write_transaction() as conn:
            existing = self._turn_row(conn, turn_id)
            if existing is not None:
                if existing["session_id"] != session_id or existing["kind"] != kind:
                    raise ValueError("calibration_turn_id_conflict")
                if kind == "answer":
                    answer_row = conn.execute(
                        "SELECT content FROM investor_profile_calibration_messages WHERE id=?",
                        (existing["user_message_id"],),
                    ).fetchone()
                    if answer_row is None or answer_row["content"] != answer:
                        raise ValueError("calibration_turn_id_conflict")
                if existing["status"] in {"pending", "completed"}:
                    return self._work_on_connection(
                        conn, existing, call_provider=False
                    )
                raise ValueError("calibration_turn_retry_required")

            session = self._require_guided_session(conn, session_id)
            pending = conn.execute(
                "SELECT id FROM investor_profile_calibration_turns "
                "WHERE session_id=? AND status='pending'",
                (session_id,),
            ).fetchone()
            if pending is not None:
                raise ValueError("calibration_turn_pending")

            user_message_id = None
            if kind == "answer":
                user_message_id = str(uuid.uuid4())
                prompt_row = conn.execute(
                    "SELECT prompt_id FROM investor_profile_calibration_messages WHERE id=?",
                    (session["current_question_message_id"],),
                ).fetchone()
                conn.execute(
                    "INSERT INTO investor_profile_calibration_messages "
                    "(id, session_id, role, content, created_at, turn_id, topic_id, prompt_id) "
                    "VALUES (?, ?, 'user', ?, ?, ?, ?, ?)",
                    (
                        user_message_id,
                        session_id,
                        answer,
                        ts,
                        turn_id,
                        session["current_topic_id"],
                        prompt_row["prompt_id"],
                    ),
                )

            conn.execute(
                "INSERT INTO investor_profile_calibration_turns "
                "(id, session_id, kind, status, question_message_id, "
                "addressed_topic_id, request_proposal, provider, model, "
                "user_message_id, attempt_count, created_at, updated_at) "
                "VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, 1, ?, ?)",
                (
                    turn_id,
                    session_id,
                    kind,
                    session["current_question_message_id"],
                    session["current_topic_id"],
                    int(kind == "proposal_request"),
                    provider,
                    model,
                    user_message_id,
                    ts,
                    ts,
                ),
            )
            conn.execute(
                "UPDATE investor_profile_calibration_sessions SET updated_at=? WHERE id=?",
                (ts, session_id),
            )
            turn_row = self._turn_row(conn, turn_id)
            return self._work_on_connection(conn, turn_row, call_provider=True)

    def begin_answer_turn(
        self,
        *,
        session_id: str,
        turn_id: str,
        answer: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> ProviderWork:
        return self._begin_turn(
            session_id=session_id,
            turn_id=turn_id,
            kind="answer",
            answer=answer,
            provider=provider,
            model=model,
        )

    def begin_proposal_turn(
        self,
        *,
        session_id: str,
        turn_id: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> ProviderWork:
        return self._begin_turn(
            session_id=session_id,
            turn_id=turn_id,
            kind="proposal_request",
            answer=None,
            provider=provider,
            model=model,
        )

    def fail_turn(
        self,
        turn_id: str,
        *,
        error_code: str,
        diagnostic: str = "",
    ) -> CalibrationTurn:
        ts = _now()
        code = _bounded_diagnostic(error_code)[:80] or "calibration_responder_failed"
        detail = _bounded_diagnostic(diagnostic)
        with self._write_transaction() as conn:
            row = self._turn_row(conn, turn_id)
            if row is None:
                raise ValueError("calibration_turn_not_found")
            if row["status"] == "pending":
                conn.execute(
                    "UPDATE investor_profile_calibration_turns SET status='failed', "
                    "error_code=?, diagnostic=?, updated_at=? WHERE id=?",
                    (code, detail, ts, turn_id),
                )
                row = self._turn_row(conn, turn_id)
            elif row["status"] not in {"failed", "interrupted"}:
                raise ValueError("calibration_turn_not_pending")
        return self._turn(row)

    def reconcile_interrupted_turns(self) -> int:
        ts = _now()
        with self._write_transaction() as conn:
            cursor = conn.execute(
                "UPDATE investor_profile_calibration_turns SET status='interrupted', "
                "error_code='calibration_turn_interrupted', "
                "diagnostic='Provider completion was interrupted before startup.', "
                "updated_at=? WHERE status='pending'",
                (ts,),
            )
            return cursor.rowcount

    def retry_turn(
        self,
        turn_id: str,
        *,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ) -> ProviderWork:
        ts = _now()
        with self._write_transaction() as conn:
            row = self._turn_row(conn, turn_id)
            if row is None:
                raise ValueError("calibration_turn_not_found")
            if row["status"] in {"pending", "completed"}:
                return self._work_on_connection(conn, row, call_provider=False)
            if row["error_code"] == "calibration_session_superseded":
                raise ValueError("calibration_turn_not_retryable")
            if row["status"] not in {"failed", "interrupted"}:
                raise ValueError("calibration_turn_not_retryable")
            session = self._require_guided_session(conn, row["session_id"])
            if (
                session["current_question_message_id"] != row["question_message_id"]
                or session["current_topic_id"] != row["addressed_topic_id"]
            ):
                raise ValueError("calibration_turn_identity_changed")
            pending = conn.execute(
                "SELECT id FROM investor_profile_calibration_turns "
                "WHERE session_id=? AND status='pending' AND id<>?",
                (row["session_id"], turn_id),
            ).fetchone()
            if pending is not None:
                raise ValueError("calibration_turn_pending")
            conn.execute(
                "UPDATE investor_profile_calibration_turns SET status='pending', "
                "provider=COALESCE(?, provider), model=COALESCE(?, model), "
                "error_code=NULL, diagnostic=NULL, next_topic_id=NULL, "
                "assistant_message_id=NULL, completed_at=NULL, "
                "attempt_count=attempt_count+1, updated_at=? WHERE id=?",
                (provider, model, ts, turn_id),
            )
            row = self._turn_row(conn, turn_id)
            return self._work_on_connection(conn, row, call_provider=True)

    @staticmethod
    def _result_member(result: Any, name: str, default: Any = None) -> Any:
        if isinstance(result, Mapping):
            return result.get(name, default)
        return getattr(result, name, default)

    @staticmethod
    def _fail_turn_on_connection(
        conn: sqlite3.Connection,
        turn_id: str,
        *,
        code: str,
        diagnostic: str,
        updated_at: str,
    ) -> None:
        conn.execute(
            "UPDATE investor_profile_calibration_turns SET status='failed', "
            "error_code=?, diagnostic=?, updated_at=? WHERE id=? AND status='pending'",
            (code, _bounded_diagnostic(diagnostic), updated_at, turn_id),
        )

    def complete_turn(self, turn_id: str, *, result: Any) -> CalibrationTurn:
        ts = _now()
        surfaced_error: CalibrationOperationError | None = None
        completed: CalibrationTurn | None = None
        with self._write_transaction() as conn:
            turn_row = self._turn_row(conn, turn_id)
            if turn_row is None:
                raise ValueError("calibration_turn_not_found")
            if turn_row["status"] == "completed":
                return self._turn(turn_row)
            if turn_row["status"] != "pending":
                raise ValueError("calibration_turn_retry_required")
            session = self._require_guided_session(conn, turn_row["session_id"])
            if (
                session["current_question_message_id"] != turn_row["question_message_id"]
                or session["current_topic_id"] != turn_row["addressed_topic_id"]
            ):
                surfaced_error = CalibrationOperationError(
                    "calibration_catalog_validation_failed",
                    "The persisted question identity no longer matches the turn.",
                )

            proposal_data: tuple[dict, dict, dict, tuple[str, ...]] | None = None
            covered_after = _ordered_topics(
                _loads(session["covered_topics_json"], [])
            )
            assistant_message = self._result_member(result, "assistant_message")
            addressed_topic_id = self._result_member(result, "addressed_topic_id")
            topic_covered = self._result_member(result, "topic_covered")
            next_topic_id = self._result_member(result, "next_topic_id")
            raw_patch = self._result_member(result, "profile_patch")
            raw_rationales = self._result_member(result, "rationales", {})
            rationales_source: Mapping[str, Any] = {}

            if surfaced_error is None:
                try:
                    if not isinstance(assistant_message, str) or not assistant_message.strip():
                        raise CalibrationOperationError(
                            "calibration_result_validation_failed",
                            "Assistant message is required.",
                        )
                    if not isinstance(addressed_topic_id, str) or type(topic_covered) is not bool:
                        raise CalibrationOperationError(
                            "calibration_result_validation_failed",
                            "Addressed topic and coverage must be structured.",
                        )
                    if next_topic_id is not None and not isinstance(next_topic_id, str):
                        raise CalibrationOperationError(
                            "calibration_result_validation_failed",
                            "Next topic must be a catalog ID or null.",
                        )
                    validate_addressed_topic(
                        addressed_topic_id,
                        turn_row["addressed_topic_id"],
                    )
                    if turn_row["kind"] == "answer" and topic_covered:
                        covered_after = _ordered_topics(
                            [*covered_after, addressed_topic_id]
                        )
                    validate_next_topic(
                        next_topic_id,
                        covered_topics=covered_after,
                    )
                except CalibrationOperationError as exc:
                    surfaced_error = exc
                except ValueError:
                    surfaced_error = CalibrationOperationError(
                        "calibration_catalog_validation_failed",
                        "Addressed or next topic failed backend catalog validation.",
                    )

            if surfaced_error is None:
                if raw_rationales is None:
                    rationales_source = {}
                elif isinstance(raw_rationales, Mapping):
                    rationales_source = raw_rationales
                else:
                    surfaced_error = CalibrationOperationError(
                        "calibration_result_validation_failed",
                        "Proposal rationales must be an object or null.",
                    )

            if surfaced_error is None and raw_patch is not None:
                if not isinstance(raw_patch, Mapping):
                    surfaced_error = CalibrationOperationError(
                        "calibration_result_validation_failed",
                        "Proposal patch must be an object or null.",
                    )
                else:
                    try:
                        for field in _LIST_CONFLICT_FIELDS:
                            if field not in raw_patch:
                                continue
                            values = raw_patch[field]
                            if not isinstance(values, list) or any(
                                not isinstance(value, str) for value in values
                            ):
                                raise ValueError("invalid calibration proposal list")
                        current_profile = _read_profile_on_connection(conn)
                        patch, rejected_fields = clamp_proposal_patch(
                            raw_patch,
                            covered_topics=covered_after,
                            current_profile=current_profile,
                        )
                    except (TypeError, ValueError):
                        surfaced_error = CalibrationOperationError(
                            "calibration_proposal_validation_failed",
                            "Legal proposal fields failed backend normalization.",
                        )
                    else:
                        if patch is not None:
                            pending = conn.execute(
                                "SELECT id FROM investor_profile_calibration_proposals "
                                "WHERE session_id=? AND status='draft'",
                                (turn_row["session_id"],),
                            ).fetchone()
                            if pending is not None:
                                surfaced_error = CalibrationOperationError(
                                    "calibration_proposal_pending",
                                    "The session already has a pending proposal.",
                                )
                            else:
                                rationales: dict[str, str] = {}
                                for field in patch:
                                    value = rationales_source.get(field)
                                    if value is not None:
                                        if not isinstance(value, str):
                                            surfaced_error = CalibrationOperationError(
                                                "calibration_result_validation_failed",
                                                "Proposal rationales must be source strings.",
                                            )
                                            break
                                        rationales[field] = value
                                if surfaced_error is None:
                                    base_values = {
                                        field: getattr(current_profile, field)
                                        for field in patch
                                    }
                                    proposal_data = (
                                        patch,
                                        base_values,
                                        rationales,
                                        rejected_fields,
                                    )

            if surfaced_error is not None:
                self._fail_turn_on_connection(
                    conn,
                    turn_id,
                    code=surfaced_error.code,
                    diagnostic=surfaced_error.diagnostic,
                    updated_at=ts,
                )
            else:
                assistant_message_id = str(uuid.uuid4())
                conn.execute(
                    "INSERT INTO investor_profile_calibration_messages "
                    "(id, session_id, role, content, created_at, turn_id, topic_id) "
                    "VALUES (?, ?, 'assistant', ?, ?, ?, ?)",
                    (
                        assistant_message_id,
                        turn_row["session_id"],
                        assistant_message,
                        ts,
                        turn_id,
                        next_topic_id,
                    ),
                )
                if proposal_data is not None:
                    patch, base_values, rationales, rejected_fields = proposal_data
                    conn.execute(
                        "INSERT INTO investor_profile_calibration_proposals "
                        "(id, session_id, status, profile_patch_json, "
                        "raw_profile_patch_json, rationales_json, created_at, "
                        "covered_topics_json, base_values_json, rejected_fields_json) "
                        "VALUES (?, ?, 'draft', ?, '{}', ?, ?, ?, ?, ?)",
                        (
                            str(uuid.uuid4()),
                            turn_row["session_id"],
                            _json(patch),
                            _json(rationales),
                            ts,
                            _json(covered_after),
                            _json(base_values),
                            _json(list(rejected_fields)),
                        ),
                    )
                if next_topic_id is None:
                    conn.execute(
                        "UPDATE investor_profile_calibration_sessions SET status='closed', "
                        "covered_topics_json=?, current_topic_id=NULL, "
                        "current_question_message_id=NULL, updated_at=?, closed_at=? "
                        "WHERE id=?",
                        (_json(covered_after), ts, ts, turn_row["session_id"]),
                    )
                else:
                    conn.execute(
                        "UPDATE investor_profile_calibration_sessions SET "
                        "covered_topics_json=?, current_topic_id=?, "
                        "current_question_message_id=?, updated_at=? WHERE id=?",
                        (
                            _json(covered_after),
                            next_topic_id,
                            assistant_message_id,
                            ts,
                            turn_row["session_id"],
                        ),
                    )
                conn.execute(
                    "UPDATE investor_profile_calibration_turns SET status='completed', "
                    "assistant_message_id=?, next_topic_id=?, error_code=NULL, "
                    "diagnostic=NULL, updated_at=?, completed_at=? WHERE id=?",
                    (assistant_message_id, next_topic_id, ts, ts, turn_id),
                )
                completed = self._turn(self._turn_row(conn, turn_id))

        if surfaced_error is not None:
            raise surfaced_error
        assert completed is not None
        return completed

    def create_proposal(
        self,
        *,
        session_id: str,
        profile_patch: dict,
        rationales: dict | None,
    ) -> CalibrationProposal:
        """Legacy Task 2 route seam; guided completion stores partial patches."""
        patch, raw, source_rationales = normalize_proposal_payload(
            profile_patch, rationales
        )
        ts, proposal_id = _now(), str(uuid.uuid4())
        with self._write_transaction() as conn:
            if self._session_row(conn, session_id) is None:
                raise ValueError("calibration_session_not_found")
            pending = conn.execute(
                "SELECT id FROM investor_profile_calibration_proposals "
                "WHERE session_id=? AND status='draft'",
                (session_id,),
            ).fetchone()
            if pending is not None:
                raise ValueError("calibration_proposal_pending")
            conn.execute(
                "INSERT INTO investor_profile_calibration_proposals "
                "(id, session_id, status, profile_patch_json, raw_profile_patch_json, "
                "rationales_json, created_at) VALUES (?, ?, 'draft', ?, ?, ?, ?)",
                (
                    proposal_id,
                    session_id,
                    _json(patch),
                    _json(raw),
                    _json(source_rationales),
                    ts,
                ),
            )
            row = self._proposal_row(conn, proposal_id)
        return self._proposal(row)

    def get_proposal(self, proposal_id: str) -> Optional[CalibrationProposal]:
        with self._connect_read_only() as conn:
            row = self._proposal_row(conn, proposal_id)
        return self._proposal(row) if row else None

    def latest_proposal(self, session_id: str) -> Optional[CalibrationProposal]:
        with self._connect_read_only() as conn:
            row = conn.execute(
                "SELECT * FROM investor_profile_calibration_proposals WHERE session_id=? "
                "ORDER BY created_at DESC, rowid DESC LIMIT 1",
                (session_id,),
            ).fetchone()
        return self._proposal(row) if row else None

    def list_proposals(self, session_id: str) -> list[CalibrationProposal]:
        with self._connect_read_only() as conn:
            rows = conn.execute(
                "SELECT * FROM investor_profile_calibration_proposals WHERE session_id=? "
                "ORDER BY created_at ASC, rowid ASC",
                (session_id,),
            ).fetchall()
        return [self._proposal(row) for row in rows]

    def _mark_proposal_approved_on_connection(
        self,
        conn: sqlite3.Connection,
        *,
        proposal_id: str,
        changed_fields: list[str],
        approved_at: str,
    ) -> None:
        cursor = conn.execute(
            "UPDATE investor_profile_calibration_proposals SET status='approved', "
            "approved_at=?, changed_fields_json=? WHERE id=? AND status='draft'",
            (approved_at, _json(changed_fields), proposal_id),
        )
        if cursor.rowcount != 1:
            raise ValueError("proposal_not_draft")

    @staticmethod
    def _mark_proposal_conflicted_on_connection(
        conn: sqlite3.Connection,
        *,
        proposal_id: str,
        conflict_fields: list[str],
        conflicted_at: str,
    ) -> None:
        cursor = conn.execute(
            "UPDATE investor_profile_calibration_proposals SET conflicted_at=?, "
            "conflict_fields_json=? WHERE id=? AND status='draft'",
            (conflicted_at, _json(conflict_fields), proposal_id),
        )
        if cursor.rowcount != 1:
            raise ValueError("proposal_not_draft")

    def mark_proposal_approved(
        self,
        proposal_id: str,
        *,
        changed_fields: list[str],
    ) -> CalibrationProposal:
        """Legacy Task 2 route seam; guided approval uses approve_proposal."""
        ts = _now()
        with self._write_transaction() as conn:
            row = self._proposal_row(conn, proposal_id)
            if row is None:
                raise ValueError("proposal_not_found")
            if row["status"] != "draft":
                raise ValueError("proposal_not_draft")
            self._mark_proposal_approved_on_connection(
                conn,
                proposal_id=proposal_id,
                changed_fields=sorted(set(changed_fields)),
                approved_at=ts,
            )
            row = self._proposal_row(conn, proposal_id)
        return self._proposal(row)

    @staticmethod
    def _same_physical_database(
        calibration_path: str | Path,
        profile_path: str | Path,
    ) -> bool:
        raw_calibration = os.fspath(calibration_path)
        raw_profile = os.fspath(profile_path)
        for raw in (raw_calibration, raw_profile):
            lowered = raw.lower()
            if lowered == ":memory:" or "mode=memory" in lowered or lowered.startswith("file::memory:"):
                return False
        calibration = Path(raw_calibration).expanduser().resolve()
        profile = Path(raw_profile).expanduser().resolve()
        if calibration == profile:
            return True
        try:
            return os.path.samefile(calibration, profile)
        except (FileNotFoundError, OSError):
            return False

    @staticmethod
    def _validated_approval_patch(
        proposal_row: sqlite3.Row,
        current: InvestorProfile,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        patch = _loads(proposal_row["profile_patch_json"], {})
        covered_topics = _loads(proposal_row["covered_topics_json"], [])
        base_values = _loads(proposal_row["base_values_json"], {})
        if (
            not isinstance(patch, dict)
            or not patch
            or not isinstance(covered_topics, list)
            or not covered_topics
            or any(topic not in CALIBRATION_TOPIC_IDS for topic in covered_topics)
            or covered_topics != _ordered_topics(covered_topics)
            or not isinstance(base_values, dict)
        ):
            raise ValueError("invalid_guided_proposal")
        legal_fields = fields_for_topics(covered_topics)
        expected_order = [field for field in legal_fields if field in patch]
        if list(patch) != expected_order or set(base_values) != set(patch):
            raise ValueError("invalid_guided_proposal")
        try:
            normalized, rejected = clamp_proposal_patch(
                patch,
                covered_topics=covered_topics,
                current_profile=current,
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_guided_proposal") from exc
        if rejected or normalized is None or _json(normalized) != _json(patch):
            raise ValueError("invalid_guided_proposal")
        return patch, base_values

    @staticmethod
    def _conflict_fields(
        current: InvestorProfile,
        patch: Mapping[str, Any],
        base_values: Mapping[str, Any],
    ) -> list[str]:
        conflicts: list[str] = []
        for field in patch:
            current_value = getattr(current, field)
            base_value = base_values[field]
            if field in _LIST_CONFLICT_FIELDS:
                matches = (
                    isinstance(current_value, list)
                    and isinstance(base_value, list)
                    and all(isinstance(value, str) for value in current_value)
                    and all(isinstance(value, str) for value in base_value)
                    and set(current_value) == set(base_value)
                )
            else:
                matches = type(current_value) is type(base_value) and current_value == base_value
            if not matches:
                conflicts.append(field)
        return conflicts

    def approve_proposal(
        self,
        proposal_id: str,
        *,
        profile_store: InvestorProfileStore,
    ) -> tuple[InvestorProfile, CalibrationProposal]:
        if not self._same_physical_database(self.db_path, profile_store._db_path):
            raise ValueError("calibration_profile_database_mismatch")

        approved_profile: InvestorProfile | None = None
        approved_proposal: CalibrationProposal | None = None
        conflict_error: ProposalConflictError | None = None
        ts = _now()
        # Fixed in-process order. BEGIN IMMEDIATE remains the cross-instance lock.
        with profile_store._write_lock:
            with self._write_lock:
                conn = profile_store._connect()
                try:
                    conn.execute("BEGIN IMMEDIATE")
                    proposal_row = self._approval_proposal_row(conn, proposal_id)
                    if proposal_row is None:
                        raise ValueError("proposal_not_found")
                    if proposal_row["status"] != "draft":
                        raise ValueError("proposal_not_draft")
                    current = _read_profile_on_connection(conn)
                    patch, base_values = self._validated_approval_patch(
                        proposal_row, current
                    )
                    conflict_fields = self._conflict_fields(
                        current, patch, base_values
                    )
                    if conflict_fields:
                        self._mark_proposal_conflicted_on_connection(
                            conn,
                            proposal_id=proposal_id,
                            conflict_fields=conflict_fields,
                            conflicted_at=ts,
                        )
                        approved_proposal = self._proposal(
                            self._approval_proposal_row(conn, proposal_id)
                        )
                        conflict_error = ProposalConflictError(conflict_fields)
                    else:
                        merged = normalize_profile_payload(patch, existing=current)
                        merged = replace(
                            merged,
                            last_reviewed_at=ts,
                            updated_at=ts,
                        )
                        changed_fields = [
                            field
                            for field in _APPROVAL_AUDIT_FIELDS
                            if getattr(current, field) != getattr(merged, field)
                        ]
                        _write_profile_on_connection(conn, merged)
                        self._mark_proposal_approved_on_connection(
                            conn,
                            proposal_id=proposal_id,
                            changed_fields=changed_fields,
                            approved_at=ts,
                        )
                        approved_profile = merged
                        approved_proposal = self._proposal(
                            self._approval_proposal_row(conn, proposal_id)
                        )
                    conn.commit()
                except BaseException:
                    conn.rollback()
                    raise
                finally:
                    conn.close()

        if conflict_error is not None:
            raise conflict_error
        assert approved_profile is not None and approved_proposal is not None
        return approved_profile, approved_proposal

    def reject_proposal(self, proposal_id: str) -> CalibrationProposal:
        ts = _now()
        with self._write_transaction() as conn:
            row = self._proposal_row(conn, proposal_id)
            if row is None:
                raise ValueError("proposal_not_found")
            if row["status"] != "draft":
                raise ValueError("proposal_not_draft")
            conn.execute(
                "UPDATE investor_profile_calibration_proposals SET status='rejected', "
                "rejected_at=? WHERE id=? AND status='draft'",
                (ts, proposal_id),
            )
            row = self._proposal_row(conn, proposal_id)
        return self._proposal(row)
